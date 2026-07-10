"""Regression tests for toobusy Wan SCAIL Extend Sampler.

Covers the pure fold logic that must never drift:

  * the chunk plan (base + N extend segments, per-chunk seeds);
  * kept-frame math (extends drop the re-rendered overlap);
  * INPUT_TYPES exposing the dynamic extend_segments counter + slots;
  * generate() wiring: per-chunk WanSCAILToVideo -> SamplerCustom ->
    VAEDecode calls, offset chaining, fresh text conditioning;
  * the clear error when the installed core's WanSCAILToVideo predates
    the SCAIL-2 extend inputs.

Standalone- and pytest-runnable, no ComfyUI runtime (see test_model_overrides).
Tests that need torch are skipped when torch is not installed.
"""

import importlib.util
import os
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_CALLS = []


def _install_stubs():
    pkg = types.ModuleType("toobusy")
    pkg.__path__ = [ROOT]
    sys.modules["toobusy"] = pkg

    sub = types.ModuleType("toobusy.ltx23_compact_sampler_node")
    sub.__path__ = [os.path.join(ROOT, "ltx23_compact_sampler_node")]
    sys.modules["toobusy.ltx23_compact_sampler_node"] = sub

    samp = types.ModuleType("toobusy.ltx23_compact_sampler_node.ltx23_compact_sampler")
    samp._sampler_names = lambda: ["euler", "res_multistep"]
    samp._fill_input_defaults = lambda cls, kwargs, params, has_var_keyword: kwargs
    sys.modules["toobusy.ltx23_compact_sampler_node.ltx23_compact_sampler"] = samp


def _load(modname, relpath):
    path = os.path.join(ROOT, relpath)
    spec = importlib.util.spec_from_file_location(modname, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[modname] = module
    spec.loader.exec_module(module)
    return module


_install_stubs()
_mod = _load(
    "toobusy.wan_scail_extend_sampler_node.wan_scail_extend_sampler",
    os.path.join("wan_scail_extend_sampler_node", "wan_scail_extend_sampler.py"),
)

try:
    import torch  # noqa: F401

    _HAS_TORCH = True
except ImportError:
    _HAS_TORCH = False


class _FakeFrames:
    """Stand-in for an IMAGE tensor [T, H, W, C] supporting the slicing the
    node does (drop overlap, take last frame)."""

    def __init__(self, count):
        self.count = count

    @property
    def shape(self):
        return (self.count, 8, 8, 3)

    def __getitem__(self, item):
        if isinstance(item, slice):
            return _FakeFrames(len(range(*item.indices(self.count))))
        raise TypeError(item)


def _fake_call_core(class_name, hint="", **kwargs):
    _CALLS.append((class_name, kwargs))
    if class_name == "WanSCAILToVideo":
        offset = kwargs["video_frame_offset"]
        prev = kwargs["previous_frames"]
        if prev is not None:
            offset = max(0, offset - kwargs["previous_frame_count"])
        return ("pos+", "neg+", {"samples": f"latent{kwargs['length']}"}, offset + kwargs["length"])
    if class_name == "SamplerCustom":
        return ("output-latent", "denoised-latent")
    if class_name == "VAEDecode":
        # Find the matching chunk length from the last SCAIL call.
        length = next(kw["length"] for name, kw in reversed(_CALLS) if name == "WanSCAILToVideo")
        return (_FakeFrames(length),)
    return (f"<{class_name}-out>",)


def _generate(**overrides):
    _CALLS.clear()
    _mod._call_core = _fake_call_core
    _mod._scail_missing_params = lambda: []

    # generate() only needs torch.cat; feed it a fake so these wiring tests run
    # on _FakeFrames with or without a real torch install.
    fake_torch = types.ModuleType("torch")

    def fake_cat(chunks, dim=0):
        assert dim == 0
        return _FakeFrames(sum(chunk.count for chunk in chunks))

    fake_torch.cat = fake_cat

    kwargs = dict(
        model="m", clip="c", vae="v", reference_image="ref", pose_video="pose",
        positive="p", negative="n", width=512, height=896,
        base_frames=65, extend_segments=0, seed=7, steps=6, cfg=1.0,
        sampler_name="euler", scheduler="simple", shift=5.0,
        previous_frame_count=5, color_match=False, color_anchor="first chunk",
        replacement_mode=False,
        pose_strength=1.0, pose_start=0.0, pose_end=1.0, clip_vision_crop="none",
    )
    kwargs.update(overrides)

    real_torch = sys.modules.get("torch")
    sys.modules["torch"] = fake_torch
    try:
        return _mod.ToobusyWanSCAILExtendSampler().generate(**kwargs)
    finally:
        if real_torch is not None:
            sys.modules["torch"] = real_torch
        else:
            del sys.modules["torch"]


def _called(node_type):
    return [kw for nt, kw in _CALLS if nt == node_type]


# --- pure helpers ------------------------------------------------------------

def test_chunk_plan_base_only():
    assert _mod._chunk_plan(65, 0, [81] * 8, 7) == [(65, 7)]


def test_chunk_plan_with_segments_steps_seed():
    plan = _mod._chunk_plan(65, 2, [81, 49] + [81] * 6, 7)
    assert plan == [(65, 7), (81, 8), (49, 9)]


def test_chunk_plan_clamps_segment_count():
    assert len(_mod._chunk_plan(65, 99, [81] * 8, 0)) == 1 + _mod.MAX_EXTEND_SEGMENTS


def test_kept_frame_counts_trims_overlap_on_extends_only():
    plan = [(65, 0), (81, 1), (81, 2)]
    assert _mod._kept_frame_counts(plan, 5) == [65, 76, 76]


def test_kept_frame_counts_without_base_trims_every_chunk():
    # Continuation plans have no base chunk: every chunk is an extend.
    plan = [(81, 1), (81, 2)]
    assert _mod._kept_frame_counts(plan, 5, has_base=False) == [76, 76]


# --- auto ("target total") planning -----------------------------------------

def test_round_to_grid_snaps_to_4k_plus_1():
    assert _mod._round_to_grid(80, 5) == 81
    assert _mod._round_to_grid(82, 5) == 81
    assert _mod._round_to_grid(84, 5) == 85
    assert _mod._round_to_grid(83, 5) == 81  # equidistant 81/85 breaks downward
    assert _mod._round_to_grid(7, 9) == 9  # below minimum is lifted to a valid grid
    assert _mod._round_to_grid(81, 5) == 81  # already on grid is untouched


def test_auto_plan_clean_two_chunk_target():
    # base 81 + (81-5) = 157 lands exactly on the default target.
    plan = _mod._auto_plan(157, 81, 5, 7)
    assert plan == [(81, 7), (81, 8)]
    assert sum(_mod._kept_frame_counts(plan, 5)) == 157


def test_auto_plan_uniform_middle_chunks_with_adjusted_last():
    plan = _mod._auto_plan(300, 81, 5, 0)
    lengths = [length for length, _seed in plan]
    # base + full extends are the chunk size; only the last is resized.
    assert lengths[0] == 81 and all(l == 81 for l in lengths[1:-1])
    total = sum(_mod._kept_frame_counts(plan, 5))
    assert abs(total - 300) <= 4  # closest the 4k+1 grid allows


def test_auto_plan_seeds_step_per_chunk():
    plan = _mod._auto_plan(300, 81, 5, 100)
    seeds = [seed for _length, seed in plan]
    assert seeds == list(range(100, 100 + len(plan)))


def test_auto_plan_single_chunk_when_target_below_chunk():
    # Target smaller than a chunk: just the base, no tiny trailing extend.
    plan = _mod._auto_plan(40, 81, 5, 1)
    assert plan == [(41, 1)]


def test_auto_plan_no_extra_chunk_for_tiny_remainder():
    # base 81, one full extend reaches 157; target 159 is only 2 over — adding a
    # whole chunk (min +4) would overshoot further than stopping, so stop.
    plan = _mod._auto_plan(159, 81, 5, 0)
    assert plan == [(81, 0), (81, 1)]


def test_auto_plan_respects_segment_cap():
    plan = _mod._auto_plan(100000, 81, 5, 0, max_segments=3)
    assert len(plan) == 1 + 3  # base + capped extends


def test_auto_plan_with_initial_frames_plans_extends_only():
    # 81 loaded frames toward a 157 target: one 81-frame extend closes the gap
    # exactly (81 - 5 overlap = 76 kept), and there is no base chunk.
    assert _mod._auto_plan(157, 81, 5, 7, initial_frames=81) == [(81, 8)]
    # Longer continuation: full extends plus a resized last chunk, landing exact.
    plan = _mod._auto_plan(300, 81, 5, 0, initial_frames=100)
    assert plan == [(81, 1), (81, 2), (53, 3)]
    assert 100 + sum(_mod._kept_frame_counts(plan, 5, has_base=False)) == 300


def test_auto_plan_with_initial_frames_meeting_target_is_empty():
    assert _mod._auto_plan(81, 81, 5, 7, initial_frames=81) == []
    assert _mod._auto_plan(60, 81, 5, 7, initial_frames=81) == []


# --- INPUT_TYPES -------------------------------------------------------------

def test_exposes_dynamic_segment_widgets():
    required = _mod.ToobusyWanSCAILExtendSampler.INPUT_TYPES()["required"]
    assert required["extend_segments"][1]["default"] == 0
    assert required["extend_segments"][1]["max"] == _mod.MAX_EXTEND_SEGMENTS
    for slot in range(1, _mod.MAX_EXTEND_SEGMENTS + 1):
        assert required[f"extend_{slot}_frames"][0] == "INT"


def test_exposes_frame_mode_and_target_total():
    required = _mod.ToobusyWanSCAILExtendSampler.INPUT_TYPES()["required"]
    assert required["frame_mode"][0] == ["target total", "manual segments"]
    assert required["frame_mode"][1]["default"] == "target total"
    assert required["target_total_frames"][0] == "INT"
    # Appended after the extend slots so saved widget-value order stays stable.
    keys = list(required.keys())
    assert keys.index("frame_mode") > keys.index(f"extend_{_mod.MAX_EXTEND_SEGMENTS}_frames")


def test_exposes_color_sample_and_strength():
    required = _mod.ToobusyWanSCAILExtendSampler.INPUT_TYPES()["required"]
    assert required["color_sample"][0] == ["whole chunk", "last frame"]
    assert required["color_match_strength"][0] == "FLOAT"
    assert required["color_match_strength"][1]["min"] == 0.0
    assert required["color_match_strength"][1]["max"] == 1.0


def test_masks_and_clip_vision_are_optional_inputs():
    optional = _mod.ToobusyWanSCAILExtendSampler.INPUT_TYPES()["optional"]
    assert optional["pose_video_mask"][0] == "IMAGE"
    assert optional["reference_image_mask"][0] == "IMAGE"
    assert optional["clip_vision"][0] == "CLIP_VISION"
    assert optional["target_total_frames_input"][0] == "INT"
    assert optional["target_total_frames_input"][1]["forceInput"] is True
    assert optional["continue_video"][0] == "IMAGE"


# --- generate() wiring -------------------------------------------------------

def test_base_only_runs_one_chunk():
    images, frame_count = _generate()
    assert len(_called("WanSCAILToVideo")) == 1
    assert len(_called("SamplerCustom")) == 1
    assert len(_called("VAEDecode")) == 1
    assert frame_count == 65 and images.count == 65


def test_two_extends_chain_offset_and_previous_frames():
    images, frame_count = _generate(extend_segments=2, extend_1_frames=81, extend_2_frames=81)
    scail = _called("WanSCAILToVideo")
    assert len(scail) == 3
    # base: no previous frames, offset 0
    assert scail[0]["previous_frames"] is None and scail[0]["video_frame_offset"] == 0
    # ext1: offset = base length, previous frames provided
    assert scail[1]["video_frame_offset"] == 65 and scail[1]["previous_frames"] is not None
    # ext2: offset = (65-5) + 81 = 141 per the core node's adjusted-offset output
    assert scail[2]["video_frame_offset"] == 141
    # output: 65 + 76 + 76
    assert frame_count == 65 + 76 + 76 == images.count


def test_target_total_mode_auto_splits_into_chunks():
    images, frame_count = _generate(frame_mode="target total", target_total_frames=157, base_frames=81)
    scail = _called("WanSCAILToVideo")
    assert len(scail) == 2  # base + one auto extend, no slots needed
    assert frame_count == 157 == images.count


def test_target_total_mode_ignores_manual_segment_widgets():
    # In auto mode the +/- slot values are irrelevant; the plan comes from target.
    _, frame_count = _generate(
        frame_mode="target total", target_total_frames=157, base_frames=81,
        extend_segments=5, extend_1_frames=300,
    )
    assert len(_called("WanSCAILToVideo")) == 2
    assert frame_count == 157


def test_target_total_link_input_overrides_widget_value():
    _, frame_count = _generate(
        frame_mode="target total",
        target_total_frames=81,
        target_total_frames_input=157,
        base_frames=81,
    )
    assert len(_called("WanSCAILToVideo")) == 2
    assert frame_count == 157


def test_continue_video_skips_base_and_anchors_first_chunk():
    # 81 loaded frames toward a 157 target: exactly one extend chunk renders,
    # anchored on the loaded video's tail, pose walked from frame 81.
    images, frame_count = _generate(
        frame_mode="target total", target_total_frames=157, base_frames=81,
        continue_video=_FakeFrames(81),
    )
    scail = _called("WanSCAILToVideo")
    assert len(scail) == 1
    assert scail[0]["previous_frames"] is not None
    assert scail[0]["video_frame_offset"] == 81
    # Output = loaded 81 + (81 - 5 overlap) kept from the new chunk.
    assert frame_count == 81 + 76 == images.count


def test_continue_video_manual_mode_runs_extends_only():
    images, frame_count = _generate(
        extend_segments=1, extend_1_frames=81, continue_video=_FakeFrames(65),
    )
    scail = _called("WanSCAILToVideo")
    assert len(scail) == 1  # no base chunk — the loaded video takes its place
    assert scail[0]["video_frame_offset"] == 65
    assert scail[0]["previous_frames"] is not None
    assert frame_count == 65 + 76 == images.count


def test_continue_video_covering_target_passes_through():
    loaded = _FakeFrames(81)
    images, frame_count = _generate(
        frame_mode="target total", target_total_frames=81, continue_video=loaded,
    )
    assert not _called("WanSCAILToVideo")
    assert images is loaded and frame_count == 81


def test_continue_video_shorter_than_overlap_is_rejected():
    try:
        _generate(continue_video=_FakeFrames(3), previous_frame_count=5)
    except ValueError as exc:
        assert "continue_video" in str(exc)
    else:
        raise AssertionError("expected ValueError for continue_video shorter than overlap")


def test_each_chunk_gets_fresh_text_conditioning_and_own_seed():
    _generate(extend_segments=1, extend_1_frames=81, seed=10)
    # Text encoded once per prompt, reused for every chunk (fresh, not chained).
    assert len(_called("CLIPTextEncode")) == 2
    scail = _called("WanSCAILToVideo")
    assert all(kw["positive"] == "<CLIPTextEncode-out>" for kw in scail)
    seeds = [kw["noise_seed"] for kw in _called("SamplerCustom")]
    assert seeds == [10, 11]


def test_color_sample_controls_reference_frame_count():
    # 'last frame' anchors on a single seam frame; 'whole chunk' on every frame
    # of the anchor chunk (so a color-atypical tail can't dominate).
    captured = {}
    real = _mod._match_color_to_reference
    _mod._match_color_to_reference = lambda images, reference, strength=1.0: (
        captured.__setitem__("n", reference.count),
        images,
    )[1]
    try:
        _generate(extend_segments=1, extend_1_frames=81, base_frames=65,
                  color_match=True, color_sample="last frame")
        assert captured["n"] == 1
        _generate(extend_segments=1, extend_1_frames=81, base_frames=65,
                  color_match=True, color_sample="whole chunk")
        assert captured["n"] == 65  # the whole first (anchor) chunk
    finally:
        _mod._match_color_to_reference = real


def test_color_match_strength_zero_skips_transfer():
    # strength 0 must not call the transfer at all (same as color_match off).
    calls = []
    real = _mod._match_color_to_reference
    _mod._match_color_to_reference = lambda *a, **k: calls.append(1) or a[0]
    try:
        _generate(extend_segments=1, extend_1_frames=81, color_match=True, color_match_strength=0.0)
        assert calls == []
    finally:
        _mod._match_color_to_reference = real


def test_clip_vision_encoded_only_when_connected():
    _generate()
    assert not _called("CLIPVisionEncode")
    _generate(clip_vision="cv")
    encodes = _called("CLIPVisionEncode")
    assert encodes and encodes[0]["image"] == "ref" and encodes[0]["crop"] == "none"


def test_shift_zero_skips_model_patch():
    _generate(shift=0.0)
    assert not _called("ModelSamplingSD3")
    _generate(shift=5.0)
    assert _called("ModelSamplingSD3")


def test_segment_not_longer_than_overlap_is_rejected():
    try:
        _generate(extend_segments=1, extend_1_frames=5, previous_frame_count=5)
    except ValueError as exc:
        assert "extend_1_frames" in str(exc)
    else:
        raise AssertionError("expected ValueError for segment <= overlap")


def test_old_core_without_scail2_inputs_fails_clearly():
    _CALLS.clear()
    _mod._call_core = _fake_call_core
    _mod._scail_missing_params = lambda: ["previous_frames"]
    try:
        _mod.ToobusyWanSCAILExtendSampler().generate(
            model="m", clip="c", vae="v", reference_image="r", pose_video="p",
            positive="", negative="", width=512, height=896, base_frames=65,
            extend_segments=0, seed=1, steps=6, cfg=1.0, sampler_name="euler",
            scheduler="simple", shift=5.0, previous_frame_count=5,
            color_match=False, color_anchor="first chunk", replacement_mode=False,
            pose_strength=1.0, pose_start=0.0, pose_end=1.0, clip_vision_crop="none",
        )
    except RuntimeError as exc:
        assert "previous_frames" in str(exc) and "Update ComfyUI" in str(exc)
    else:
        raise AssertionError("expected RuntimeError on old core")


# --- color anchor selection --------------------------------------------------

def _spy_color_anchor(**overrides):
    """Run a 2-extend generate with color_match on, recording which chunk's
    frame each color match aimed at. Frames are tagged f0/f1/f2 so we can tell
    'first chunk' (always f0) from 'previous chunk' (f0 then f1)."""
    refs = []
    real_match = _mod._match_color_to_reference
    _mod._match_color_to_reference = lambda images, reference, strength=1.0: (refs.append(reference), images)[1]

    class _TaggedFrames:
        def __init__(self, tag, count):
            self.tag = tag
            self.count = count

        @property
        def shape(self):
            return (self.count, 8, 8, 3)

        def __getitem__(self, item):
            return self  # last-frame slice keeps the tag

    decoded_seq = [_TaggedFrames("f0", 65), _TaggedFrames("f1", 81), _TaggedFrames("f2", 81)]
    state = {"i": 0}

    def fake_call_core(class_name, hint="", **kwargs):
        _CALLS.append((class_name, kwargs))
        if class_name == "WanSCAILToVideo":
            return ("pos+", "neg+", {"samples": "lat"}, kwargs["video_frame_offset"] + kwargs["length"])
        if class_name == "SamplerCustom":
            return ("out", "den")
        if class_name == "VAEDecode":
            frame = decoded_seq[state["i"]]
            state["i"] += 1
            return (frame,)
        return (f"<{class_name}-out>",)

    _mod._call_core = fake_call_core
    _mod._scail_missing_params = lambda: []

    fake_torch = types.ModuleType("torch")
    fake_torch.cat = lambda chunks, dim=0: chunks[-1]

    kwargs = dict(
        model="m", clip="c", vae="v", reference_image="ref", pose_video="pose",
        positive="p", negative="n", width=512, height=896,
        base_frames=65, extend_segments=2, extend_1_frames=81, extend_2_frames=81,
        seed=7, steps=6, cfg=1.0, sampler_name="euler", scheduler="simple", shift=5.0,
        previous_frame_count=5, color_match=True, replacement_mode=False,
        pose_strength=1.0, pose_start=0.0, pose_end=1.0, clip_vision_crop="none",
    )
    kwargs.update(overrides)
    real_torch = sys.modules.get("torch")
    sys.modules["torch"] = fake_torch
    try:
        _CALLS.clear()
        _mod.ToobusyWanSCAILExtendSampler().generate(**kwargs)
    finally:
        _mod._match_color_to_reference = real_match
        if real_torch is not None:
            sys.modules["torch"] = real_torch
        else:
            del sys.modules["torch"]
    return [ref.tag for ref in refs]


def test_first_chunk_anchor_always_targets_first():
    tags = _spy_color_anchor(color_anchor="first chunk")
    assert tags == ["f0", "f0"], "every extend should match the first chunk (stops cumulative fade)"


def test_previous_chunk_anchor_follows_the_chain():
    tags = _spy_color_anchor(color_anchor="previous chunk")
    assert tags == ["f0", "f1"], "each extend should match the chunk before it"


# --- mask background estimation (torch only) ---------------------------------

def test_mask_background_estimation():
    if not _HAS_TORCH:
        print("SKIP test_mask_background_estimation (no torch)")
        return
    import torch

    white = torch.ones(2, 64, 64, 3)
    black = torch.zeros(2, 64, 64, 3)
    gray = torch.full((1, 64, 64, 3), 0.5)
    assert _mod._estimate_mask_background(white) == "white"
    assert _mod._estimate_mask_background(black) == "black"
    assert _mod._estimate_mask_background(gray) is None
    # A character in the middle must not flip the corner-based estimate.
    busy = torch.zeros(1, 64, 64, 3)
    busy[0, 16:48, 16:48, 2] = 1.0
    assert _mod._estimate_mask_background(busy) == "black"
    assert _mod._estimate_mask_background(None) is None


# --- color transfer (torch only) ---------------------------------------------

def test_color_match_identity_when_stats_match():
    if not _HAS_TORCH:
        print("SKIP test_color_match_identity_when_stats_match (no torch)")
        return
    import torch

    frames = torch.rand(3, 16, 16, 3)
    reference = frames[-1:]
    matched = _mod._match_color_to_reference(frames[-1:], reference)
    assert torch.allclose(matched, reference, atol=0.02), "self-transfer should be near-identity"


def test_color_match_moves_toward_reference_stats():
    if not _HAS_TORCH:
        print("SKIP test_color_match_moves_toward_reference_stats (no torch)")
        return
    import torch

    dark = torch.rand(2, 16, 16, 3) * 0.3
    bright = torch.rand(1, 16, 16, 3) * 0.3 + 0.7
    matched = _mod._match_color_to_reference(dark, bright)
    assert matched.mean() > dark.mean() + 0.2, "transfer should pull means toward the reference"
    assert matched.min() >= 0.0 and matched.max() <= 1.0


def test_color_match_strength_scales_effect():
    if not _HAS_TORCH:
        print("SKIP test_color_match_strength_scales_effect (no torch)")
        return
    import torch

    dark = torch.full((2, 8, 8, 3), 0.2)
    bright = torch.full((1, 8, 8, 3), 0.8)
    none = _mod._match_color_to_reference(dark, bright, strength=0.0)
    half = _mod._match_color_to_reference(dark, bright, strength=0.5)
    full = _mod._match_color_to_reference(dark, bright, strength=1.0)
    assert torch.allclose(none, dark, atol=1e-3), "strength 0 is a no-op"
    assert dark.mean() < half.mean() < full.mean(), "strength scales the pull"


def test_color_match_pools_reference_over_all_frames():
    # A reference whose tail frame is an outlier (bright) shouldn't dominate when
    # the whole chunk is the reference: pooled stats pull less than the lone tail.
    if not _HAS_TORCH:
        print("SKIP test_color_match_pools_reference_over_all_frames (no torch)")
        return
    import torch

    bulk = torch.full((4, 8, 8, 3), 0.2)
    outlier = torch.full((1, 8, 8, 3), 0.9)
    whole = torch.cat([bulk, outlier], dim=0)  # last frame is the bright outlier
    src = torch.full((2, 8, 8, 3), 0.5)
    to_last = _mod._match_color_to_reference(src, whole[-1:])
    to_whole = _mod._match_color_to_reference(src, whole)
    assert to_last.mean() > to_whole.mean(), "matching the whole chunk dilutes the outlier tail"


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except AssertionError as exc:
                failures += 1
                print(f"FAIL {name}: {exc}")
    if failures:
        print(f"\n{failures} test(s) failed")
        sys.exit(1)
    print("\nall tests passed")
