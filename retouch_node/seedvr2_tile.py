"""SeedVR2 restore for an image of any size, in VRAM-sized tiles.

The core SeedVR2 nodes condition on the encoded input itself, so a generic tiler
such as Ultimate SD Upscale (one conditioning for every tile) cannot drive them.
This node runs the core chain (Pre-Process -> VAE Encode -> Apply SeedVR2
Conditioning -> 1-step sample -> VAE Decode -> Post-Process) once per tile with
that tile's own conditioning, feathers the overlaps together and returns the
result at the input size, ready for 2BZ Frequency Detail Transfer.
"""

import torch
import torch.nn.functional as F

import comfy.model_management
import comfy.utils

from ..ltx23_compact_sampler_node.ltx23_compact_sampler import _call_node
from .tile_plan import edge_ramps, feather_width, plan_tiles, work_scale

_VAE_TILE = {"tile_size": 512, "overlap": 128, "temporal_size": 64, "temporal_overlap": 8}


def _resize(image_bhwc, width, height, method):
    samples = image_bhwc.movedim(-1, 1)
    out = comfy.utils.common_upscale(samples, width, height, method, "disabled")
    return out.movedim(1, -1)


def _shrink(image_bhwc, width, height):
    samples = image_bhwc.movedim(-1, 1).float()
    out = F.interpolate(samples, size=(height, width), mode="bicubic", align_corners=False, antialias=True)
    return out.movedim(1, -1).clamp(0.0, 1.0)


def _feather(w, h, ramps, device):
    left, right, top, bottom = ramps
    wx = torch.ones(w, device=device)
    wy = torch.ones(h, device=device)
    if left:
        wx[:left] = torch.linspace(0.0, 1.0, left + 2, device=device)[1:-1]
    if right:
        wx[w - right:] = torch.linspace(1.0, 0.0, right + 2, device=device)[1:-1]
    if top:
        wy[:top] = torch.linspace(0.0, 1.0, top + 2, device=device)[1:-1]
    if bottom:
        wy[h - bottom:] = torch.linspace(1.0, 0.0, bottom + 2, device=device)[1:-1]
    return (wy[:, None] * wx[None, :])[None, :, :, None]


def _fit(image_bhwc, w, h):
    """Post-Process trims to even sizes; pad back by edge replication if needed."""
    image_bhwc = image_bhwc[:, :h, :w, :]
    ph, pw = h - image_bhwc.shape[1], w - image_bhwc.shape[2]
    if ph or pw:
        image_bhwc = F.pad(image_bhwc.movedim(-1, 1), (0, pw, 0, ph), mode="replicate").movedim(1, -1)
    return image_bhwc


def _restore_tile(model, vae, tile, seed, color_correction):
    padded = _call_node("SeedVR2Preprocess", resized_images=tile)[0]
    latent = _call_node("VAEEncodeTiled", pixels=padded, vae=vae, **_VAE_TILE)[0]
    positive, negative = _call_node("SeedVR2Conditioning", model=model, vae_conditioning=latent)[:2]
    sampled = _call_node(
        "KSampler", model=model, seed=seed, steps=1, cfg=1.0, sampler_name="euler", scheduler="simple",
        positive=positive, negative=negative, latent_image=latent, denoise=1.0,
    )[0]
    decoded = _call_node("VAEDecodeTiled", samples=sampled, vae=vae, **_VAE_TILE)[0]
    out = _call_node(
        "SeedVR2PostProcessing", images=decoded, original_resized_images=tile,
        color_correction_method=color_correction,
    )[0]
    if out.ndim == 5:
        out = out.reshape(-1, out.shape[-3], out.shape[-2], out.shape[-1])
    return out[:1, ..., :3]


class ToobusySeedVR2TileRestore:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model": ("MODEL", {"tooltip": "SeedVR2 3B/7B (Load Diffusion Model)."}),
                "vae": ("VAE", {"tooltip": "SeedVR2 VAE (seedvr2_ema_vae)."}),
                "image": ("IMAGE",),
                "tile_megapixels": ("FLOAT", {
                    "default": 2.0, "min": 0.5, "max": 16.0, "step": 0.25,
                    "tooltip": "VRAM knob: how much SeedVR2 processes at once. Bigger images are split into "
                               "tiles of this size. Lower it if you run out of memory. "
                               "Rough guide (3B int8): 8 GB -> 1, 12 GB -> 1.5-2, 16 GB -> 2-3, 24 GB -> 3-4.",
                }),
                "upscale_small_to": ("FLOAT", {
                    "default": 3.0, "min": 0.0, "max": 16.0, "step": 0.5,
                    "tooltip": "Quality knob (MP): images smaller than this are enlarged to it before restoring, "
                               "then returned at their own size. Face texture saturates around 2-3 MP. 0 = never enlarge.",
                }),
                "tile_overlap": ("INT", {
                    "default": 128, "min": 32, "max": 512, "step": 16,
                    "tooltip": "Pixels shared by neighbouring tiles and feathered together.",
                }),
                "seed": ("INT", {"default": 42, "min": 0, "max": 0xFFFFFFFFFFFFFFFF}),
                "color_correction": (["lab", "wavelet", "adain", "none"], {
                    "default": "lab", "tooltip": "Match each tile's colours to the input (lab is the most faithful).",
                }),
            }
        }

    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("restored", "info")
    FUNCTION = "restore"
    CATEGORY = "toobusy/retouch"
    DESCRIPTION = (
        "SeedVR2 restore for any image size. Splits into VRAM-sized tiles, restores each with its own "
        "conditioning, blends the overlaps and returns the input size. Feed `restored` and the original "
        "into 2BZ Frequency Detail Transfer to keep the original shapes and add only fine texture."
    )

    def restore(self, model, vae, image, tile_megapixels, upscale_small_to, tile_overlap, seed, color_correction):
        results, infos = [], []
        for b in range(image.shape[0]):
            src = image[b:b + 1, ..., :3]
            height, width = src.shape[1], src.shape[2]
            scale = work_scale(width, height, upscale_small_to)
            ww, wh = max(16, round(width * scale)), max(16, round(height * scale))
            work = _resize(src, ww, wh, "lanczos") if scale > 1.0 else src

            tiles = plan_tiles(ww, wh, tile_megapixels, tile_overlap)
            ramp = feather_width(tiles, tile_overlap)
            store = comfy.model_management.intermediate_device()
            acc = torch.zeros((1, wh, ww, 3), dtype=torch.float32, device=store)
            wsum = torch.zeros((1, wh, ww, 1), dtype=torch.float32, device=store)
            pbar = comfy.utils.ProgressBar(len(tiles))
            for x, y, w, h in tiles:
                comfy.model_management.throw_exception_if_processing_interrupted()
                tile = work[:, y:y + h, x:x + w, :]
                out = _fit(_restore_tile(model, vae, tile, seed, color_correction).float().to(store), w, h)
                mask = _feather(w, h, edge_ramps(x, y, w, h, ww, wh, ramp) if len(tiles) > 1 else (0, 0, 0, 0), store)
                acc[:, y:y + h, x:x + w, :] += out * mask
                wsum[:, y:y + h, x:x + w, :] += mask
                pbar.update(1)
            merged = acc / wsum.clamp(min=1e-6)
            if scale > 1.0:
                merged = _shrink(merged, width, height)
            results.append(merged.clamp(0.0, 1.0))
            cols = len({t[0] for t in tiles})
            rows = len({t[1] for t in tiles})
            infos.append(
                f"input {width}x{height} ({width * height / 1e6:.1f}MP) -> work {ww}x{wh} (x{scale:.2f}), "
                f"{cols}x{rows} tiles of {tiles[0][2]}x{tiles[0][3]}"
            )
        return (torch.cat(results, dim=0), "\n".join(infos))


NODE_CLASS_MAPPINGS = {"ToobusySeedVR2TileRestore": ToobusySeedVR2TileRestore}
NODE_DISPLAY_NAME_MAPPINGS = {"ToobusySeedVR2TileRestore": "2BZ SeedVR2 Tile Restore"}
