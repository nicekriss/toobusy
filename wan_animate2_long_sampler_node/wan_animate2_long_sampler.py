"""Compact long-video sampler for Wan Animate 2."""

from ..wan_scail_extend_sampler_node.wan_scail_extend_sampler import (
    MAX_AUTO_SEGMENTS,
    _call_core,
    _match_color_to_reference,
    _node_class,
    _round_to_grid,
)


_ANIMATE_NODE = "WanAnimate2ToVideo"
_ANIMATE_HINT = "Update ComfyUI: WanAnimate2ToVideo is required for Wan Animate 2."
_REQUIRED_OUTPUTS = 6
_OVERLAP_FRAMES = 1


def _plan_chunks(total_frames, frames_per_sampler, seed, initial_frames=0):
    """Return valid 4k+1 Wan chunk lengths and deterministic per-chunk seeds."""
    target = max(1, int(total_frames))
    initial = max(0, int(initial_frames))
    chunk = _round_to_grid(frames_per_sampler, 5)
    remaining = max(0, target - initial)
    plan = []
    index = 0

    if initial == 0 and remaining > 0:
        base = _round_to_grid(min(chunk, remaining), 5)
        plan.append((base, int(seed)))
        remaining -= base
        index = 1

    contribution = chunk - _OVERLAP_FRAMES
    while remaining > 0 and len(plan) < MAX_AUTO_SEGMENTS:
        if remaining >= contribution:
            length = chunk
        else:
            length = _round_to_grid(remaining + _OVERLAP_FRAMES, 5)
        plan.append((length, int(seed) + index))
        remaining -= length - _OVERLAP_FRAMES
        index += 1

    if remaining > 0:
        raise ValueError(
            f"The requested total needs more than {MAX_AUTO_SEGMENTS} sampler chunks. "
            "Increase frames_per_sampler or reduce total_frames."
        )
    return plan


def _animate_output_count():
    cls = _node_class(_ANIMATE_NODE, _ANIMATE_HINT)
    schema = getattr(cls, "define_schema", None)
    if schema is None:
        return None
    try:
        return len(schema().outputs)
    except Exception:
        return None


class ToobusyWanAnimate2LongSampler:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model": ("MODEL",),
                "positive": ("CONDITIONING",),
                "negative": ("CONDITIONING",),
                "sampler": ("SAMPLER",),
                "sigmas": ("SIGMAS",),
                "vae": ("VAE",),
                "reference_image": ("IMAGE",),
                "pose_video": ("IMAGE",),
                "width": ("INT", {"default": 482, "min": 64, "max": 8192, "step": 2}),
                "height": ("INT", {"default": 854, "min": 64, "max": 8192, "step": 2}),
                "total_frames": (
                    "INT",
                    {
                        "default": 241,
                        "min": 1,
                        "max": 100000,
                        "step": 1,
                        "tooltip": "Exact final output length. The last valid Wan chunk is cropped when necessary.",
                    },
                ),
                "frames_per_sampler": (
                    "INT",
                    {
                        "default": 81,
                        "min": 5,
                        "max": 1024,
                        "step": 4,
                        "tooltip": "Frames rendered by each sampler chunk. Use 81 for 24 GB, 49 for 16 GB, or 33 for 12 GB as a starting point.",
                    },
                ),
                "seed": (
                    "INT",
                    {
                        "default": 1,
                        "min": 0,
                        "max": 0xffffffffffffffff,
                        "control_after_generate": True,
                        "tooltip": "Each following chunk uses seed + chunk index.",
                    },
                ),
                "cfg": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 30.0, "step": 0.1}),
                "reference_image_strength": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 10.0, "step": 0.01}),
                "pose_strength": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 10.0, "step": 0.01}),
                "pose_start_percent": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 1.0, "step": 0.01}),
                "pose_end_percent": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.01}),
                "color_match": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "label_on": "match chunk colors",
                        "label_off": "raw chunk colors",
                    },
                ),
                "color_match_strength": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.05}),
            },
            "optional": {
                "positive_pose": (
                    "CONDITIONING",
                    {"tooltip": "Final motion-branch conditioning. When omitted, positive is used."},
                ),
                "clip_vision_output": ("CLIP_VISION_OUTPUT",),
                "clip_vision_output_pose": ("CLIP_VISION_OUTPUT",),
                "continue_video": (
                    "IMAGE",
                    {
                        "tooltip": "An existing Animate 2 result to continue. It is included in total_frames and its last frame anchors the first new chunk.",
                    },
                ),
                "total_frames_input": (
                    "INT",
                    {
                        "forceInput": True,
                        "tooltip": "Optional linked override for total_frames.",
                    },
                ),
            },
        }

    RETURN_TYPES = ("IMAGE", "INT", "INT")
    RETURN_NAMES = ("images", "frame_count", "chunk_count")
    FUNCTION = "generate"
    CATEGORY = "toobusy/Make"

    def generate(
        self,
        model,
        positive,
        negative,
        sampler,
        sigmas,
        vae,
        reference_image,
        pose_video,
        width,
        height,
        total_frames,
        frames_per_sampler,
        seed,
        cfg,
        reference_image_strength,
        pose_strength,
        pose_start_percent,
        pose_end_percent,
        color_match,
        color_match_strength,
        positive_pose=None,
        clip_vision_output=None,
        clip_vision_output_pose=None,
        continue_video=None,
        total_frames_input=None,
    ):
        output_count = _animate_output_count()
        if output_count is not None and output_count < _REQUIRED_OUTPUTS:
            raise RuntimeError(
                "This ComfyUI core's WanAnimate2ToVideo has no continuation outputs. "
                f"{_ANIMATE_HINT}"
            )

        target = int(total_frames_input if total_frames_input is not None else total_frames)
        if target < 1:
            raise ValueError("total_frames must be at least 1.")
        if float(pose_start_percent) > float(pose_end_percent):
            raise ValueError("pose_start_percent must not be greater than pose_end_percent.")

        continue_count = 0
        if continue_video is not None:
            continue_count = int(continue_video.shape[0])
            if continue_count <= 0:
                continue_video = None
            elif continue_count >= target:
                images = continue_video[:target]
                return (images, int(images.shape[0]), 0)

        plan = _plan_chunks(target, frames_per_sampler, seed, continue_count)
        if pose_video is not None and int(pose_video.shape[0]) < target:
            print(
                f"[toobusy Wan Animate 2] Warning: total_frames ({target}) exceeds pose_video "
                f"length ({int(pose_video.shape[0])}); the last pose frame will be held."
            )

        progress = None
        try:
            import comfy.utils

            progress = comfy.utils.ProgressBar(len(plan))
        except Exception:
            pass

        chunks = []
        previous_frames = None
        frame_offset = 0
        if continue_video is not None:
            chunks.append(continue_video)
            previous_frames = continue_video
            frame_offset = continue_count

        for length, chunk_seed in plan:
            animate = _call_core(
                _ANIMATE_NODE,
                hint=_ANIMATE_HINT,
                positive=positive,
                negative=negative,
                vae=vae,
                width=int(width),
                height=int(height),
                length=int(length),
                batch_size=1,
                reference_image=reference_image,
                pose_video=pose_video,
                clip_vision_output=clip_vision_output,
                positive_pose=positive_pose,
                clip_vision_output_pose=clip_vision_output_pose,
                continue_motion=previous_frames,
                video_frame_offset=int(frame_offset),
                pose_strength=float(pose_strength),
                pose_start_percent=float(pose_start_percent),
                pose_end_percent=float(pose_end_percent),
                reference_image_strength=float(reference_image_strength),
            )
            if len(animate) < _REQUIRED_OUTPUTS:
                raise RuntimeError(
                    "WanAnimate2ToVideo did not return trim/continuation outputs. "
                    f"{_ANIMATE_HINT}"
                )
            chunk_positive, chunk_negative, chunk_latent = animate[:3]
            trim_latent, trim_image, frame_offset = int(animate[3]), int(animate[4]), int(animate[5])

            sampled = _call_core(
                "SamplerCustom",
                model=model,
                add_noise=True,
                noise_seed=int(chunk_seed),
                cfg=float(cfg),
                positive=chunk_positive,
                negative=chunk_negative,
                sampler=sampler,
                sigmas=sigmas,
                latent_image=chunk_latent,
            )
            output_latent = sampled[0]
            if trim_latent > 0:
                output_latent = _call_core("TrimVideoLatent", samples=output_latent, trim_amount=trim_latent)[0]
            decoded = _call_core("VAEDecode", samples=output_latent, vae=vae)[0]
            kept = decoded[trim_image:] if trim_image > 0 else decoded

            strength = max(0.0, min(1.0, float(color_match_strength)))
            if color_match and strength > 0.0 and chunks:
                kept = _match_color_to_reference(kept, chunks[0], strength=strength)
            chunks.append(kept)
            previous_frames = kept
            if progress is not None:
                progress.update(1)

        import torch

        images = chunks[0] if len(chunks) == 1 else torch.cat(chunks, dim=0)
        images = images[:target]
        return (images, int(images.shape[0]), len(plan))


NODE_CLASS_MAPPINGS = {
    "ToobusyWanAnimate2LongSampler": ToobusyWanAnimate2LongSampler,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ToobusyWanAnimate2LongSampler": "toobusy Wan Animate 2 Long Sampler",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
