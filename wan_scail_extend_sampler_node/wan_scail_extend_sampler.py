"""toobusy Wan SCAIL Extend Sampler.

Folds the whole Wan 2.1 SCAIL-2 sampling-and-extend graph into one node:
prompt encoding, CLIP vision encoding, the shift patch, the scheduler, then
one WanSCAILToVideo -> SamplerCustom -> VAEDecode chain per video chunk,
with the overlap trim, the seam color match (Reinhard LAB), and the final
frame concat that the hand-built graph needed a copy-pasted 18-node block
for every extension.

Extend segments are dynamic: the `extend_segments` counter (driven by the
JS +/- buttons, like the LoRA slots on other toobusy nodes) decides how many
`extend_N_frames` chunks run after the base chunk. `video_frame_offset` and
`previous_frames` chaining between chunks is handled internally.

Requires a ComfyUI core recent enough to ship `WanSCAILToVideo` with the
SCAIL-2 inputs (pose_video_mask / reference_image_mask / previous_frames /
video_frame_offset). On older cores the node loads fine but fails at run
time with a clear "update ComfyUI" message.
"""

import inspect

from ..ltx23_compact_sampler_node.ltx23_compact_sampler import _fill_input_defaults, _sampler_names

MAX_EXTEND_SEGMENTS = 8

# Auto ("target total") mode builds its plan internally instead of from the
# +/- slots, so it isn't bound by MAX_EXTEND_SEGMENTS. This is just a sanity
# cap so a tiny chunk size against a huge target can't spin up thousands of
# chunks (every chunk's decoded frames accumulate in memory before concat).
MAX_AUTO_SEGMENTS = 64

_SCAIL_NODE = "WanSCAILToVideo"
_SCAIL_HINT = (
    "Update ComfyUI: WanSCAILToVideo with SCAIL-2 extend inputs "
    "(pose_video_mask / previous_frames / video_frame_offset) ships with "
    "recent ComfyUI cores (comfy_extras/nodes_scail.py)."
)

# Inputs of the core SCAIL node this fold depends on. If the installed core's
# WanSCAILToVideo predates them, kwarg filtering would silently drop them and
# produce a wrong video — so their absence is a hard, explained error instead.
_SCAIL_REQUIRED_PARAMS = (
    "pose_video_mask",
    "reference_image_mask",
    "replacement_mode",
    "previous_frames",
    "previous_frame_count",
    "video_frame_offset",
)


def _scheduler_names():
    try:
        import comfy.samplers

        names = list(comfy.samplers.KSampler.SCHEDULERS)
        if names:
            return names
    except Exception:
        pass

    return ["simple", "normal", "karras", "exponential", "sgm_uniform"]


def _node_class(class_name, hint=""):
    import nodes

    try:
        return nodes.NODE_CLASS_MAPPINGS[class_name]
    except KeyError as exc:
        message = f"Required ComfyUI core node '{class_name}' is not available."
        if hint:
            message = f"{message} {hint}"
        raise RuntimeError(message) from exc


def _execute_params(cls, fn):
    """Parameter mapping of the call target, looking through the V3 schema's
    *args/**kwargs normalizer to the real `execute` signature when present."""
    try:
        params = inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return None
    if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values()):
        execute = getattr(cls, "execute", None)
        if execute is not None:
            try:
                return inspect.signature(execute).parameters
            except (TypeError, ValueError):
                return None
        return None
    return params


def _call_core(class_name, hint="", **kwargs):
    """Call a core node class by registry name and return a plain tuple.

    Handles both node APIs: classic classes (FUNCTION names a method that
    returns a tuple or a {"result": ...} dict) and V3 io.ComfyNode classes
    (FUNCTION resolves to EXECUTE_NORMALIZED returning a NodeOutput whose
    values live in `.args`). Unknown kwargs are filtered out against the real
    signature so core nodes can grow inputs without breaking this fold.
    """
    cls = _node_class(class_name, hint)
    try:
        target = cls()
    except Exception:
        target = cls
    fn = getattr(target, getattr(cls, "FUNCTION", "execute"))

    params = _execute_params(cls, fn)
    has_var_keyword = params is None or any(
        p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values()
    )
    # Fill schema defaults for inputs we don't pass (the executor does this
    # in-graph; a core update adding a widget must not break the fold).
    kwargs = _fill_input_defaults(cls, dict(kwargs), None if has_var_keyword else params, has_var_keyword)
    if not has_var_keyword:
        kwargs = {key: value for key, value in kwargs.items() if key in params}

    result = fn(**kwargs)
    args = getattr(result, "args", None)
    if args is not None:
        return tuple(args)
    if isinstance(result, dict):
        return tuple(result.get("result", ()))
    return tuple(result)


def _scail_missing_params():
    cls = _node_class(_SCAIL_NODE, _SCAIL_HINT)
    fn = getattr(cls, "execute", None) or getattr(cls, getattr(cls, "FUNCTION", "execute"), None)
    params = _execute_params(cls, fn) if fn is not None else None
    if params is None:
        return []
    return [name for name in _SCAIL_REQUIRED_PARAMS if name not in params]


def _estimate_mask_background(mask_video):
    """'white' / 'black' from the corner luminance of the first mask frame, or
    None when ambiguous. SCAIL-2's mode convention lives in the mask background
    (animation = black, replacement = white), so a mismatch here almost always
    means the replacement_mode toggles on this node and on 'Create SCAIL-2
    Colored Mask' disagree."""
    try:
        frame = mask_video[0]
        height = int(frame.shape[0])
        width = int(frame.shape[1])
        patch = max(1, min(8, height // 8, width // 8))
        corners = (
            frame[:patch, :patch],
            frame[:patch, width - patch:],
            frame[height - patch:, :patch],
            frame[height - patch:, width - patch:],
        )
        luminance = sum(float(corner.mean()) for corner in corners) / 4.0
    except Exception:
        return None
    if luminance >= 0.75:
        return "white"
    if luminance <= 0.25:
        return "black"
    return None


def _chunk_plan(base_frames, extend_segments, segment_frames, seed):
    """[(length, noise_seed), ...] for the base chunk plus each active extend
    segment. Chunk seeds step from the base seed so each chunk gets fresh
    noise deterministically."""
    plan = [(int(base_frames), int(seed))]
    count = max(0, min(MAX_EXTEND_SEGMENTS, int(extend_segments)))
    for index in range(count):
        plan.append((int(segment_frames[index]), int(seed) + index + 1))
    return plan


def _kept_frame_counts(plan, previous_frame_count, has_base=True):
    """Output frames each chunk contributes: the base chunk keeps everything,
    extend chunks drop the overlap frames re-rendered from the previous tail.
    With `has_base=False` (continuing an existing video) every chunk is an
    extend, so all of them drop the overlap."""
    overlap = int(previous_frame_count)
    counts = []
    for index, (length, _seed) in enumerate(plan):
        keeps_all = has_base and index == 0
        counts.append(int(length) if keeps_all else max(0, int(length) - overlap))
    return counts


def _round_to_grid(value, minimum):
    """Nearest valid Wan length (4k+1) that is >= minimum. Wan 2.1 wants chunk
    lengths of the form 4k+1 (5, 9, ..., 65, 81); off-grid lengths degrade or
    error in the sampler, so auto mode snaps every computed length here."""
    value = int(round(float(value)))
    if value < minimum:
        value = minimum
    remainder = (value - 1) % 4
    if remainder == 0:
        grid = value
    elif remainder <= 2:
        grid = value - remainder
    else:
        grid = value + (4 - remainder)
    while grid < minimum:
        grid += 4
    return grid


def _auto_plan(target_total, chunk_frames, overlap, seed, max_segments=MAX_AUTO_SEGMENTS, initial_frames=0):
    """Build [(length, noise_seed), ...] that lands as close to `target_total`
    output frames as the 4k+1 grid allows.

    The base chunk and every full extend use `chunk_frames`; the base keeps all
    its frames while each extend contributes `chunk_frames - overlap` (the
    overlap is re-rendered from the previous tail and trimmed). The final extend
    is resized to close the gap, and is only added when doing so lands closer to
    the target than stopping — so a 1-2 frame remainder doesn't spawn a whole
    extra chunk. Mirrors the JS readout's planning so the on-canvas breakdown
    matches what actually runs.

    `initial_frames` > 0 means an existing video (continue_video) already covers
    the start of the timeline: no base chunk is planned — those frames count
    toward the target and every planned chunk is an extend. The plan may come
    back empty when the loaded video already meets the target."""
    overlap = int(overlap)
    chunk = _round_to_grid(chunk_frames, 9)
    target = max(1, int(target_total))
    initial = max(0, int(initial_frames))

    if initial > 0:
        plan = []
        remaining = target - initial
    else:
        base = _round_to_grid(min(chunk, target), 5)
        plan = [(base, int(seed))]
        remaining = target - base

    per_extend = chunk - overlap
    if per_extend <= 0:
        return plan

    min_last = max(9, overlap + 4)
    index = 1
    while remaining > 0 and index <= max_segments:
        if remaining >= per_extend:
            plan.append((chunk, int(seed) + index))
            remaining -= per_extend
            index += 1
            continue
        # Final partial chunk: snap to grid, keep only if it beats stopping.
        last_length = _round_to_grid(remaining + overlap, min_last)
        contributed = last_length - overlap
        if abs(remaining - contributed) < remaining:
            plan.append((last_length, int(seed) + index))
        break
    return plan


# ----- Reinhard color transfer in CIELAB (folds the per-chunk ColorTransfer
# nodes; matches each frame's LAB mean/std to the previous chunk's last frame
# so chunk seams don't drift in color). -----

_D65 = (0.95047, 1.0, 1.08883)


def _rgb_to_lab(rgb):
    import torch

    linear = torch.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055).clamp(min=0) ** 2.4)
    r, g, b = linear.unbind(-1)
    x = (0.4124564 * r + 0.3575761 * g + 0.1804375 * b) / _D65[0]
    y = (0.2126729 * r + 0.7151522 * g + 0.0721750 * b) / _D65[1]
    z = (0.0193339 * r + 0.1191920 * g + 0.9503041 * b) / _D65[2]
    xyz = torch.stack((x, y, z), dim=-1)

    delta = 6.0 / 29.0
    f = torch.where(xyz > delta**3, xyz.clamp(min=0) ** (1.0 / 3.0), xyz / (3 * delta**2) + 4.0 / 29.0)
    fx, fy, fz = f.unbind(-1)
    return torch.stack((116.0 * fy - 16.0, 500.0 * (fx - fy), 200.0 * (fy - fz)), dim=-1)


def _lab_to_rgb(lab):
    import torch

    l, a, b = lab.unbind(-1)
    fy = (l + 16.0) / 116.0
    fx = fy + a / 500.0
    fz = fy - b / 200.0
    f = torch.stack((fx, fy, fz), dim=-1)

    delta = 6.0 / 29.0
    xyz = torch.where(f > delta, f**3, 3 * delta**2 * (f - 4.0 / 29.0))
    x, y, z = xyz.unbind(-1)
    x = x * _D65[0]
    z = z * _D65[2]

    r = 3.2404542 * x - 1.5371385 * y - 0.4985314 * z
    g = -0.9692660 * x + 1.8760108 * y + 0.0415560 * z
    bl = 0.0556434 * x - 0.2040259 * y + 1.0572252 * z
    linear = torch.stack((r, g, bl), dim=-1)
    return torch.where(
        linear <= 0.0031308,
        linear * 12.92,
        1.055 * linear.clamp(min=0) ** (1.0 / 2.4) - 0.055,
    )


def _match_color_to_reference(images, reference, strength=1.0):
    """Per-frame Reinhard LAB transfer of `images` [T,H,W,C] toward the color
    statistics of `reference` [N,H,W,C].

    Reference stats are pooled over all reference frames AND pixels, so passing
    a whole chunk averages out a color-atypical tail (e.g. a blue close-up at
    the very end) instead of letting one frame set the target. For a single
    reference frame this is identical to the old per-frame behavior."""
    import torch

    source = images[..., :3].float()
    ref_lab = _rgb_to_lab(reference[..., :3].float().to(source.device))
    ref_mean = ref_lab.mean(dim=(0, 1, 2), keepdim=True)
    ref_std = ref_lab.std(dim=(0, 1, 2), keepdim=True)

    lab = _rgb_to_lab(source)
    mean = lab.mean(dim=(1, 2), keepdim=True)
    std = lab.std(dim=(1, 2), keepdim=True).clamp(min=1e-6)
    matched = (lab - mean) / std * ref_std + ref_mean
    out = _lab_to_rgb(matched).clamp(0.0, 1.0)

    strength = max(0.0, min(1.0, float(strength)))
    if strength < 1.0:
        out = source * (1.0 - strength) + out * strength
    if images.shape[-1] > 3:
        out = torch.cat((out, images[..., 3:].float()), dim=-1)
    return out.to(images.dtype)


class ToobusyWanSCAILExtendSampler:
    """Folds the Wan 2.1 SCAIL-2 generate + extend graph into one node.

    Replaces, per run with N extend segments: CLIPTextEncode x2 +
    CLIPVisionEncode + ModelSamplingSD3 + KSamplerSelect + BasicScheduler +
    (N+1) x (WanSCAILToVideo + SamplerCustom + VAEDecode) + N x
    (GetImageRangeFromBatch x2 + ColorTransfer) + the final image batch
    concat. At two extends that is ~22 core nodes (plus all the Get/Set
    plumbing between them) -> 1.
    """

    @classmethod
    def INPUT_TYPES(cls):
        sampler_names = _sampler_names()
        scheduler_names = _scheduler_names()

        base = {
            "required": {
                "model": ("MODEL",),
                "clip": ("CLIP",),
                "vae": ("VAE",),
                "reference_image": ("IMAGE",),
                "pose_video": ("IMAGE",),
                "positive": ("STRING", {"default": "", "multiline": True}),
                "negative": ("STRING", {"default": "", "multiline": True}),
                "width": ("INT", {"default": 512, "min": 64, "max": 8192, "step": 32}),
                "height": ("INT", {"default": 896, "min": 64, "max": 8192, "step": 32}),
                "base_frames": (
                    "INT",
                    {
                        "default": 81,
                        "min": 5,
                        "max": 1024,
                        "step": 4,
                        "tooltip": "Frames of the first chunk, and the per-chunk size auto mode extends with. Wan wants 4k+1 lengths (65, 81, ...).",
                    },
                ),
                "extend_segments": ("INT", {"default": 0, "min": 0, "max": MAX_EXTEND_SEGMENTS}),
                "seed": (
                    "INT",
                    {
                        "default": 1,
                        "min": 0,
                        "max": 0xffffffffffffffff,
                        "control_after_generate": True,
                        "tooltip": "Base noise seed. Each extend chunk uses seed + chunk index.",
                    },
                ),
                "steps": ("INT", {"default": 6, "min": 1, "max": 100}),
                "cfg": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 30.0, "step": 0.1}),
                "sampler_name": (sampler_names, {"default": "euler" if "euler" in sampler_names else sampler_names[0]}),
                "scheduler": (scheduler_names, {"default": "simple" if "simple" in scheduler_names else scheduler_names[0]}),
                "shift": (
                    "FLOAT",
                    {
                        "default": 5.0,
                        "min": 0.0,
                        "max": 100.0,
                        "step": 0.01,
                        "tooltip": "ModelSamplingSD3 sigma shift. 0 keeps the model's own sampling.",
                    },
                ),
                "previous_frame_count": (
                    "INT",
                    {
                        "default": 5,
                        "min": 1,
                        "max": 33,
                        "step": 4,
                        "tooltip": "Tail frames of the previous chunk each extend re-anchors on (SCAIL-2 is trained at 5). The overlap is trimmed from the extend output.",
                    },
                ),
                "color_match": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "label_on": "match chunk colors",
                        "label_off": "raw chunk colors",
                        "tooltip": "Reinhard LAB color transfer of every extend chunk so the colors stay consistent down the video.",
                    },
                ),
                "color_anchor": (
                    ["first chunk", "previous chunk"],
                    {
                        "default": "first chunk",
                        "tooltip": "Which chunk color_match aims at. 'first chunk' anchors every chunk to the first chunk, stopping the cumulative fade that chunk-by-chunk VAE round-trips cause. 'previous chunk' matches each chunk to the one before it (smoothest seams, but follows the drift). See color_sample for which frames set the target.",
                    },
                ),
                "replacement_mode": ("BOOLEAN", {"default": False, "label_on": "replacement mode", "label_off": "animation mode"}),
                "pose_strength": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 10.0, "step": 0.01}),
                "pose_start": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 1.0, "step": 0.01}),
                "pose_end": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.01}),
                "clip_vision_crop": (["none", "center"], {"default": "none"}),
            },
            "optional": {
                "clip_vision": ("CLIP_VISION",),
                "pose_video_mask": ("IMAGE",),
                "reference_image_mask": ("IMAGE",),
                "continue_video": (
                    "IMAGE",
                    {
                        "tooltip": (
                            "Frames of an already-generated video to continue from (load the good "
                            "part of a previous run and trim it to the last frame you want to keep). "
                            "When connected the base chunk is skipped: these frames open the output, "
                            "their tail anchors the first new chunk, and the pose video is walked "
                            "from that point on automatically — so keep the SAME pose_video and "
                            "settings as the original run. In 'target total' mode these frames "
                            "count toward the target."
                        ),
                    },
                ),
                "target_total_frames_input": (
                    "INT",
                    {
                        "forceInput": True,
                        "tooltip": (
                            "Optional linked override for target_total_frames. Use this when driving "
                            "the target with a frame counter or other INT output; when connected it "
                            "wins over the widget value."
                        ),
                    },
                ),
            },
        }

        for slot in range(1, MAX_EXTEND_SEGMENTS + 1):
            base["required"][f"extend_{slot}_frames"] = (
                "INT",
                {
                    "default": 81,
                    "min": 9,
                    "max": 1024,
                    "step": 4,
                    "tooltip": "Frames rendered for this extend chunk; the first previous_frame_count of them are the overlap and get trimmed.",
                },
            )

        # Appended AFTER the slots so saved-workflow widget value order (which
        # ends with extend_N_frames) stays intact; the JS repositions them for
        # display. 'target total' lets you type one goal frame count and let the
        # node decide how many extends to run, instead of stacking slots.
        base["required"]["frame_mode"] = (
            ["target total", "manual segments"],
            {
                "default": "target total",
                "tooltip": (
                    "target total: enter a goal frame count; the node auto-splits it into "
                    "base_frames-sized chunks and extends as needed (last chunk trims to fit). "
                    "manual segments: drive each extend chunk yourself with the +/- slots."
                ),
            },
        )
        base["required"]["target_total_frames"] = (
            "INT",
            {
                "default": 157,
                "min": 5,
                "max": 100000,
                "step": 4,
                "tooltip": "Goal output frames in 'target total' mode. The readout shows the actual landed total (4k+1 grid means it may differ by a few frames).",
            },
        )
        # Color-match tuning — appended last (like frame_mode) to keep saved
        # widget-value order stable; the JS moves them next to color_anchor.
        base["required"]["color_sample"] = (
            ["whole chunk", "last frame"],
            {
                "default": "whole chunk",
                "tooltip": (
                    "Which frames of the anchor chunk set the color target. 'whole chunk' "
                    "averages the chunk's color so a color-atypical tail (e.g. a blue close-up "
                    "right before a zoom-out) can't drag the next chunk's color. 'last frame' "
                    "matches the seam frame exactly (tightest seam, but vulnerable to that tail)."
                ),
            },
        )
        base["required"]["color_match_strength"] = (
            "FLOAT",
            {
                "default": 1.0,
                "min": 0.0,
                "max": 1.0,
                "step": 0.05,
                "tooltip": (
                    "How hard color_match pulls each chunk toward the target color. 1.0 = full "
                    "transfer, 0.0 = none (same as turning color_match off). Lower it when scenes "
                    "legitimately change color and full matching tints them."
                ),
            },
        )

        return base

    RETURN_TYPES = ("IMAGE", "INT")
    RETURN_NAMES = ("images", "frame_count")
    FUNCTION = "generate"
    CATEGORY = "toobusy/Make"

    def generate(
        self,
        model,
        clip,
        vae,
        reference_image,
        pose_video,
        positive,
        negative,
        width,
        height,
        base_frames,
        extend_segments,
        seed,
        steps,
        cfg,
        sampler_name,
        scheduler,
        shift,
        previous_frame_count,
        color_match,
        color_anchor,
        replacement_mode,
        pose_strength,
        pose_start,
        pose_end,
        clip_vision_crop,
        frame_mode="manual segments",
        target_total_frames=157,
        color_sample="whole chunk",
        color_match_strength=1.0,
        clip_vision=None,
        pose_video_mask=None,
        reference_image_mask=None,
        continue_video=None,
        target_total_frames_input=None,
        **segment_kwargs,
    ):
        missing = _scail_missing_params()
        if missing:
            raise RuntimeError(
                "This ComfyUI core's WanSCAILToVideo has no "
                f"{'/'.join(missing)} input(s). {_SCAIL_HINT}"
            )

        overlap = int(previous_frame_count)
        auto_mode = str(frame_mode) == "target total"

        # Continuation: an already-generated video replaces the base chunk. Its
        # tail (last `overlap` frames) anchors the first new chunk exactly like
        # an internal chunk seam, and the pose video is walked from its end.
        continue_count = 0
        if continue_video is not None:
            try:
                continue_count = int(continue_video.shape[0])
            except Exception:
                continue_count = 0
            if continue_count <= 0:
                continue_video = None
            elif continue_count < overlap:
                raise ValueError(
                    f"continue_video has {continue_count} frame(s) but previous_frame_count is "
                    f"{overlap}; supply at least {overlap} frames so the continuation has a full "
                    "anchor (trim the loaded video less aggressively)."
                )
        has_continue = continue_video is not None

        if auto_mode:
            if target_total_frames_input is not None:
                target_total_frames = target_total_frames_input
            plan = _auto_plan(
                target_total_frames, base_frames, overlap, seed,
                initial_frames=continue_count if has_continue else 0,
            )
        else:
            extend_segments = max(0, min(MAX_EXTEND_SEGMENTS, int(extend_segments)))
            segment_frames = [
                int(segment_kwargs.get(f"extend_{slot}_frames", 81))
                for slot in range(1, MAX_EXTEND_SEGMENTS + 1)
            ]
            for index in range(extend_segments):
                if segment_frames[index] <= overlap:
                    raise ValueError(
                        f"extend_{index + 1}_frames ({segment_frames[index]}) must be larger than "
                        f"previous_frame_count ({overlap}); the chunk would only re-render the overlap."
                    )
            plan = _chunk_plan(base_frames, extend_segments, segment_frames, seed)
            if has_continue:
                # The loaded video takes the base chunk's place; only extends run.
                plan = plan[1:]

        if not plan:
            # Only reachable with continue_video: the loaded frames already meet
            # (or exceed) the target, so there is nothing to render.
            print(
                "[toobusy Wan SCAIL] Nothing to render: continue_video already covers the "
                f"requested frames ({continue_count}). Passing it through unchanged."
            )
            return (continue_video, continue_count)

        # SCAIL-2 is pose-driven: each chunk walks the pose video at its offset,
        # so the output can't outrun the pose. Warn (don't hard-clamp) when the
        # plan asks for more frames than the pose supplies.
        if pose_video is not None:
            try:
                pose_len = int(pose_video.shape[0])
            except Exception:
                pose_len = None
            requested = continue_count + sum(
                _kept_frame_counts(plan, overlap, has_base=not has_continue)
            )
            if pose_len and requested > pose_len:
                print(
                    f"[toobusy Wan SCAIL] Warning: planned {requested} output frames exceed "
                    f"pose_video length ({pose_len}). The video can't run longer than the driving "
                    "pose — shorten the target or supply a longer pose_video."
                )

        if pose_video_mask is not None:
            estimated = _estimate_mask_background(pose_video_mask)
            expected = "white" if replacement_mode else "black"
            if estimated is not None and estimated != expected:
                mode_name = "replacement" if replacement_mode else "animation"
                print(
                    f"[toobusy Wan SCAIL] Warning: pose_video_mask background looks {estimated} "
                    f"but {mode_name} mode expects {expected}. Set replacement_mode to the SAME "
                    "value on this node and on 'Create SCAIL-2 Colored Mask' — mismatched mask "
                    "conventions degrade quality, especially with multiple people."
                )

        # Shared conditioning: fresh text encodes for every chunk (each chunk
        # attaches its own reference latent exactly once), one optional CLIP
        # vision encode of the reference.
        positive_cond = _call_core("CLIPTextEncode", clip=clip, text=positive)[0]
        negative_cond = _call_core("CLIPTextEncode", clip=clip, text=negative)[0]
        clip_vision_output = None
        if clip_vision is not None:
            clip_vision_output = _call_core(
                "CLIPVisionEncode",
                clip_vision=clip_vision,
                image=reference_image,
                crop=clip_vision_crop,
            )[0]

        work_model = model
        if float(shift) > 0.0:
            work_model = _call_core("ModelSamplingSD3", model=model, shift=float(shift))[0]
        sampler = _call_core("KSamplerSelect", sampler_name=sampler_name)[0]
        sigmas = _call_core(
            "BasicScheduler",
            model=work_model,
            scheduler=scheduler,
            steps=int(steps),
            denoise=1.0,
        )[0]

        progress = None
        try:
            import comfy.utils

            progress = comfy.utils.ProgressBar(len(plan))
        except Exception:
            pass

        chunks = []
        previous_frames = None
        frame_offset = 0
        if has_continue:
            # The loaded video opens the output and seeds the chunk chain: its
            # tail becomes the first new chunk's previous_frames anchor, and the
            # offset makes the core walk the pose video from where it left off.
            chunks.append(continue_video)
            previous_frames = continue_video
            frame_offset = continue_count
        for index, (length, chunk_seed) in enumerate(plan):
            scail = _call_core(
                _SCAIL_NODE,
                hint=_SCAIL_HINT,
                positive=positive_cond,
                negative=negative_cond,
                vae=vae,
                width=int(width),
                height=int(height),
                length=int(length),
                batch_size=1,
                pose_video=pose_video,
                pose_video_mask=pose_video_mask,
                replacement_mode=bool(replacement_mode),
                pose_strength=float(pose_strength),
                pose_start=float(pose_start),
                pose_end=float(pose_end),
                reference_image=reference_image,
                reference_image_mask=reference_image_mask,
                clip_vision_output=clip_vision_output,
                video_frame_offset=int(frame_offset),
                previous_frame_count=overlap,
                previous_frames=previous_frames,
            )
            chunk_positive, chunk_negative, chunk_latent = scail[0], scail[1], scail[2]
            frame_offset = int(scail[3]) if len(scail) > 3 else frame_offset + int(length)

            sampled = _call_core(
                "SamplerCustom",
                model=work_model,
                add_noise=True,
                noise_seed=int(chunk_seed),
                cfg=float(cfg),
                positive=chunk_positive,
                negative=chunk_negative,
                sampler=sampler,
                sigmas=sigmas,
                latent_image=chunk_latent,
            )
            denoised = sampled[1] if len(sampled) > 1 else sampled[0]
            decoded = _call_core("VAEDecode", samples=denoised, vae=vae)[0]

            if index == 0 and not has_continue:
                kept = decoded
            else:
                kept = decoded[overlap:]
                strength = max(0.0, min(1.0, float(color_match_strength)))
                if color_match and strength > 0.0 and chunks:
                    # Anchor to the first chunk (stops cumulative fade — every
                    # chunk targets the same un-drifted color) or the previous
                    # chunk (smoothest seam). color_sample decides whether the
                    # whole anchor chunk sets the target color (robust to a
                    # color-atypical tail) or just its last/seam frame.
                    anchor_chunk = chunks[0] if color_anchor == "first chunk" else chunks[-1]
                    reference = anchor_chunk if color_sample == "whole chunk" else anchor_chunk[-1:]
                    kept = _match_color_to_reference(kept, reference, strength=strength)
            chunks.append(kept)
            previous_frames = kept

            if progress is not None:
                progress.update(1)

        images = chunks[0]
        if len(chunks) > 1:
            import torch

            images = torch.cat(chunks, dim=0)
        return (images, int(images.shape[0]))


NODE_CLASS_MAPPINGS = {
    "ToobusyWanSCAILExtendSampler": ToobusyWanSCAILExtendSampler,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ToobusyWanSCAILExtendSampler": "toobusy Wan SCAIL Extend Sampler",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
