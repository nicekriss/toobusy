import gc
import os
from dataclasses import dataclass

import numpy as np
import torch
from comfy import model_management
from comfy.utils import common_upscale
from PIL import Image

from .examples.WanVSR.utils.utils import Causal_LQ4x_Proj, calculate_frame_adjustment_simple
from .models import ModelManager
from .pipelines import FlashVSRFullPipeline, TorchColorCorrectorWavelet


@dataclass(frozen=True)
class FlashVSRModelHandle:
    dit_path: str
    projection_path: str
    prompt_path: str
    offload: bool


def require_block_sparse_attention():
    try:
        from block_sparse_attn import block_sparse_attn_func
    except ImportError as exc:
        raise RuntimeError(
            "toobusy FlashVSR Full requires Block-Sparse Attention. "
            "Install the wheel matching your Python, PyTorch, and CUDA versions."
        ) from exc
    return block_sparse_attn_func


def resize_images(images, width, height):
    samples = images.movedim(-1, 1)
    samples = common_upscale(samples, int(width), int(height), "nearest-exact", "center")
    return samples.movedim(1, -1).contiguous()


def chunk_starts(total_frames, chunk_frames, overlap):
    if total_frames <= chunk_frames:
        return [0]
    step = chunk_frames - overlap
    starts = list(range(0, total_frames - chunk_frames + 1, step))
    final_start = total_frames - chunk_frames
    if starts[-1] != final_start:
        starts.append(final_start)
    return starts


def _prepare_video(images, scale, device):
    original_frames = int(images.shape[0])
    adjustment = calculate_frame_adjustment_simple(original_frames)
    frames_to_add = int(adjustment["frames_to_add"])
    pad_frames = int(adjustment["frames_to_remove"])
    if frames_to_add:
        images = torch.cat((images, images[-1:].repeat(frames_to_add, 1, 1, 1)), dim=0)

    height, width = int(images.shape[1]), int(images.shape[2])
    target_width = max(128, (width * int(scale) // 128) * 128)
    target_height = max(128, (height * int(scale) // 128) * 128)
    resized = []
    scaled_width = width * int(scale)
    scaled_height = height * int(scale)
    left = max(0, (scaled_width - target_width) // 2)
    top = max(0, (scaled_height - target_height) // 2)
    for frame in images:
        array = frame.mul(255.0).clamp(0.0, 255.0).byte().cpu().numpy()
        image = Image.fromarray(array, mode="RGB")
        image = image.resize((scaled_width, scaled_height), Image.Resampling.BICUBIC)
        image = image.crop((left, top, left + target_width, top + target_height))
        tensor = torch.from_numpy(np.asarray(image, dtype=np.uint8).copy())
        tensor = tensor.to(device=device, dtype=torch.float32).permute(2, 0, 1).div(255.0).mul(2.0).sub(1.0)
        resized.append(tensor.to(dtype=torch.bfloat16))
    frames = torch.stack(resized, dim=1).unsqueeze(0).contiguous()
    return frames, target_height, target_width, pad_frames, original_frames


def load_dit_pipeline(handle):
    require_block_sparse_attention()
    manager = ModelManager(torch_dtype=torch.bfloat16, device="cpu")
    manager.load_dit(handle.dit_path)
    pipe = FlashVSRFullPipeline.from_model_manager(manager, device="cuda", torch_dtype=torch.bfloat16)
    pipe.denoising_model().LQ_proj_in = Causal_LQ4x_Proj(in_dim=3, out_dim=1536, layer_num=1).to(
        "cpu", dtype=torch.bfloat16
    )
    projection = torch.load(handle.projection_path, map_location="cpu", weights_only=False)
    pipe.denoising_model().LQ_proj_in.load_state_dict(projection, strict=True)
    del projection
    pipe.enable_vram_management(num_persistent_param_in_dit=None)
    pipe.init_cross_kv(handle.prompt_path)
    pipe.offload = bool(handle.offload)
    return pipe, manager


def sample_chunk(pipe, images, seed, scale, kv_ratio, local_range, steps, sparse_ratio):
    device = model_management.get_torch_device()
    lq, height, width, pad_frames, original_frames = _prepare_video(images, scale, device)
    if not pipe.offload:
        pipe.to(device)
    latents, lq_index = pipe(
        prompt="",
        negative_prompt="",
        cfg_scale=1.0,
        num_inference_steps=int(steps),
        seed=int(seed),
        tiled=True,
        LQ_video=lq,
        num_frames=int(lq.shape[2]),
        height=height,
        width=width,
        is_full_block=False,
        if_buffer=True,
        topk_ratio=float(sparse_ratio) * 768 * 1280 / (height * width),
        kv_ratio=float(kv_ratio),
        local_range=int(local_range),
        color_fix=True,
        offload=bool(pipe.offload),
    )
    if not pipe.offload:
        pipe.dit.to("cpu")
    return {
        "samples": latents.cpu(),
        "lq": lq.cpu(),
        "lq_index": lq_index,
        "pad_frames": pad_frames,
        "original_frames": original_frames,
    }


def load_vae_pipeline(vae_path):
    manager = ModelManager(torch_dtype=torch.bfloat16, device="cpu")
    manager.load_vae(vae_path)
    pipe = FlashVSRFullPipeline.from_model_manager(manager, device="cuda", torch_dtype=torch.bfloat16)
    pipe.vae.model.encoder = None
    pipe.vae.model.conv1 = None
    pipe.enable_vram_management(num_persistent_param_in_dit=None, vae_only=True)
    pipe.load_models_to_device(["vae"])
    return pipe, manager


def _map_to_image(video):
    return video.add(1.0).div(2.0).clamp_(0.0, 1.0)


def decode_chunk(pipe, item, tiled, color_fix):
    samples = item["samples"]
    pipe.vae.clear_cache()
    decoded = pipe.vae.decode(
        samples,
        device="cuda",
        tiled=bool(tiled),
        tile_size=(60, 104),
        tile_stride=(30, 52),
    )
    decoded = _map_to_image(decoded.cpu().float())
    if item["pad_frames"]:
        decoded = decoded[:, :, :-int(item["pad_frames"])]
    decoded = decoded[:, :, : int(item["original_frames"])]

    if color_fix:
        lq = _map_to_image(item["lq"].cpu().float())[:, :, : decoded.shape[2]]
        decoded = torch.cat((decoded[:, :, :1], decoded), dim=2)
        lq = torch.cat((lq[:, :, :1], lq), dim=2)
        corrector = TorchColorCorrectorWavelet(levels=5)
        decoded = corrector(
            decoded.to("cuda"),
            lq.to("cuda"),
            clip_range=(-1.0, 1.0),
            chunk_size=16,
            method="wavelet",
        ).cpu()[:, :, 1:]
    return decoded.squeeze(0).permute(1, 2, 3, 0).contiguous()


def merge_chunk(images, new_images, overlap):
    overlap = min(int(overlap), int(images.shape[0]), int(new_images.shape[0]))
    if overlap <= 0:
        return torch.cat((images, new_images), dim=0)
    alpha = torch.linspace(0.0, 1.0, overlap + 2, dtype=images.dtype)[1:-1].view(-1, 1, 1, 1)
    blended = images[-overlap:] * (1.0 - alpha) + new_images[:overlap] * alpha
    return torch.cat((images[:-overlap], blended, new_images[overlap:]), dim=0)


def release_pipeline(pipe, manager=None):
    if pipe is not None:
        try:
            pipe.load_models_to_device([])
        except (AttributeError, RuntimeError):
            pass
        for name in ("dit", "vae", "VAE"):
            model = getattr(pipe, name, None)
            if model is not None:
                clear_cache = getattr(model, "clear_cache", None)
                if clear_cache is not None:
                    clear_cache()
                try:
                    model.to("cpu")
                except (AttributeError, RuntimeError):
                    pass
                setattr(pipe, name, None)
        del pipe
    if manager is not None:
        manager.models.clear()
        del manager
    gc.collect()
    model_management.soft_empty_cache()


def validate_paths(*paths):
    missing = [path for path in paths if not path or not os.path.isfile(path)]
    if missing:
        raise FileNotFoundError("Missing FlashVSR model file: " + ", ".join(str(path) for path in missing))
