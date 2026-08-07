import folder_paths
import torch
from comfy.utils import ProgressBar

from .backend.runtime import (
    FlashVSRModelHandle,
    chunk_starts,
    decode_chunk,
    load_dit_pipeline,
    load_vae_pipeline,
    merge_chunk,
    release_pipeline,
    resize_images,
    sample_chunk,
    validate_paths,
)


MODEL_TYPE = "TOOBUSY_FLASHVSR_MODEL"
LATENT_TYPE = "TOOBUSY_FLASHVSR_LATENT"


def _flashvsr_names(text):
    extensions = (".safetensors", ".ckpt", ".pth", ".pt")
    return [
        name
        for name in folder_paths.get_filename_list("toobusy_flashvsr")
        if text in name.lower() and name.lower().endswith(extensions)
    ]


class ToobusyFlashVSRLoader:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "dit": (_flashvsr_names("dmd"),),
                "projection": (_flashvsr_names("proj"),),
                "prompt_tensor": (_flashvsr_names("prompt"),),
                "offload": ("BOOLEAN", {"default": False}),
            }
        }

    RETURN_TYPES = (MODEL_TYPE,)
    RETURN_NAMES = ("flashvsr_model",)
    FUNCTION = "load"
    CATEGORY = "toobusy/video/FlashVSR"

    def load(self, dit, projection, prompt_tensor, offload):
        paths = [folder_paths.get_full_path("toobusy_flashvsr", name) for name in (dit, projection, prompt_tensor)]
        validate_paths(*paths)
        return (FlashVSRModelHandle(*paths, bool(offload)),)


class ToobusyFlashVSRSampler:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "flashvsr_model": (MODEL_TYPE,),
                "images": ("IMAGE",),
                "width": ("INT", {"default": 1024, "min": 128, "max": 8192, "step": 64}),
                "height": ("INT", {"default": 576, "min": 128, "max": 8192, "step": 64}),
                "scale": ("INT", {"default": 2, "min": 2, "max": 4}),
                "seed": ("INT", {"default": 0, "min": 0, "max": 2147483647}),
                "chunk_frames": ("INT", {"default": 21, "min": 5, "max": 81, "step": 8}),
                "chunk_overlap": ("INT", {"default": 8, "min": 0, "max": 80}),
                "local_range": ("INT", {"default": 11, "min": 1, "max": 50}),
                "kv_ratio": ("FLOAT", {"default": 3.0, "min": 0.0, "max": 10.0, "step": 0.1}),
                "sparse_ratio": ("FLOAT", {"default": 2.0, "min": 0.0, "max": 10.0, "step": 0.1}),
                "steps": ("INT", {"default": 1, "min": 1, "max": 8}),
            }
        }

    RETURN_TYPES = (LATENT_TYPE,)
    RETURN_NAMES = ("flashvsr_latent",)
    FUNCTION = "sample"
    CATEGORY = "toobusy/video/FlashVSR"

    def sample(self, flashvsr_model, images, width, height, scale, seed, chunk_frames, chunk_overlap, local_range, kv_ratio, sparse_ratio, steps):
        total_frames = int(images.shape[0])
        chunk_frames = min(int(chunk_frames), total_frames)
        chunk_overlap = min(int(chunk_overlap), max(0, chunk_frames - 1))
        starts = chunk_starts(total_frames, chunk_frames, chunk_overlap)
        resized = resize_images(images, width, height)
        progress = ProgressBar(len(starts))
        pipe = manager = None
        chunks = []
        overlaps = []
        previous_end = 0
        try:
            pipe, manager = load_dit_pipeline(flashvsr_model)
            for index, start in enumerate(starts):
                end = min(total_frames, start + chunk_frames)
                chunks.append(sample_chunk(pipe, resized[start:end], seed, scale, kv_ratio, local_range, steps, sparse_ratio))
                overlaps.append(max(0, previous_end - start) if index else 0)
                previous_end = end
                progress.update(1)
        finally:
            release_pipeline(pipe, manager)
            pipe = manager = None
        return ({"chunks": chunks, "overlaps": overlaps, "total_frames": total_frames},)


class ToobusyFlashVSRDecoder:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "flashvsr_latent": (LATENT_TYPE,),
                "vae": (folder_paths.get_filename_list("vae"),),
                "tiled": ("BOOLEAN", {"default": True}),
                "color_fix": ("BOOLEAN", {"default": True}),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("images",)
    FUNCTION = "decode"
    CATEGORY = "toobusy/video/FlashVSR"

    def decode(self, flashvsr_latent, vae, tiled, color_fix):
        vae_path = folder_paths.get_full_path("vae", vae)
        validate_paths(vae_path)
        chunks = flashvsr_latent["chunks"]
        overlaps = flashvsr_latent["overlaps"]
        progress = ProgressBar(len(chunks))
        pipe = manager = None
        images = None
        try:
            pipe, manager = load_vae_pipeline(vae_path)
            for index, item in enumerate(chunks):
                decoded = decode_chunk(pipe, item, tiled, color_fix)
                images = decoded if images is None else merge_chunk(images, decoded, overlaps[index])
                chunks[index] = None
                progress.update(1)
        finally:
            release_pipeline(pipe, manager)
            pipe = manager = None
        return (images[: int(flashvsr_latent["total_frames"])],)


NODE_CLASS_MAPPINGS = {
    "ToobusyFlashVSRLoader": ToobusyFlashVSRLoader,
    "ToobusyFlashVSRSampler": ToobusyFlashVSRSampler,
    "ToobusyFlashVSRDecoder": ToobusyFlashVSRDecoder,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ToobusyFlashVSRLoader": "toobusy FlashVSR Loader",
    "ToobusyFlashVSRSampler": "toobusy FlashVSR Long Sampler",
    "ToobusyFlashVSRDecoder": "toobusy FlashVSR Full Decoder",
}
