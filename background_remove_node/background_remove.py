"""toobusy Background Remove (optional rembg-based node).

Kept lightweight at import time: heavy deps (torch, numpy, PIL, rembg) are
imported lazily inside the run method so the node loads even when rembg is not
installed. Dependencies are checked only when the node actually runs.
"""

import importlib


REMBG_INSTALL_MESSAGE = """Background Remove optional dependencies are missing.

Install only if you want to use toobusy Background Remove:

pip install -r custom_nodes/toobusy/requirements_rembg.txt

(For GPU, install onnxruntime-gpu instead of onnxruntime.)
"""

OPTIONAL_DEPENDENCIES = (
    ("rembg", "rembg"),
    ("onnxruntime", "onnxruntime"),
)

# rembg model names (downloaded on first use). u2net is the general default.
REMBG_MODELS = [
    "u2net",
    "u2netp",
    "u2net_human_seg",
    "isnet-general-use",
    "isnet-anime",
    "silueta",
    "birefnet-general",
]

# RGB fill (0-1) used for the IMAGE output where the subject is cut out. The
# MASK output always carries the real alpha, so this only affects the preview/
# composited IMAGE.
BACKGROUND_COLORS = {
    "white": (1.0, 1.0, 1.0),
    "black": (0.0, 0.0, 0.0),
    "green": (0.0, 1.0, 0.0),
    "gray": (0.5, 0.5, 0.5),
    "magenta": (1.0, 0.0, 1.0),
}


def _missing_optional_dependencies(importer=importlib.import_module):
    missing = []
    for module_name, package_name in OPTIONAL_DEPENDENCIES:
        try:
            importer(module_name)
        except Exception:
            missing.append(package_name)
    return missing


def _ensure_rembg(importer=importlib.import_module):
    missing = _missing_optional_dependencies(importer)
    if missing:
        details = "\nMissing: " + ", ".join(missing)
        raise RuntimeError(REMBG_INSTALL_MESSAGE + details)


def _background_rgb(name):
    return BACKGROUND_COLORS.get(name, BACKGROUND_COLORS["white"])


def _composite_frame(rgba, bg_rgb, np):
    """Composite an HxWx4 float32 RGBA array over a solid bg color.

    Returns (rgb HxWx3, alpha HxW), both float32 in 0-1.
    """
    alpha = rgba[..., 3:4]
    rgb = rgba[..., :3]
    bg = np.array(bg_rgb, dtype="float32").reshape(1, 1, 3)
    composited = rgb * alpha + bg * (1.0 - alpha)
    return composited.astype("float32"), alpha[..., 0].astype("float32")


class ToobusyBackgroundRemove:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "model": (REMBG_MODELS, {"default": "u2net"}),
                "background": (list(BACKGROUND_COLORS.keys()), {"default": "white"}),
            },
            "optional": {
                "alpha_matting": ("BOOLEAN", {"default": False, "tooltip": "Refine edges (slower). Good for hair/fur."}),
                "post_process_mask": ("BOOLEAN", {"default": False, "tooltip": "Clean up the mask after segmentation."}),
            },
        }

    RETURN_TYPES = ("IMAGE", "MASK")
    RETURN_NAMES = ("image", "mask")
    FUNCTION = "remove_background"
    CATEGORY = "toobusy/Image"

    def remove_background(self, image, model, background, alpha_matting=False, post_process_mask=False):
        _ensure_rembg()
        import numpy as np
        import torch
        from PIL import Image as PILImage
        from rembg import new_session, remove

        session = new_session(model)
        bg_rgb = _background_rgb(background)

        out_images = []
        out_masks = []
        for frame in image:
            arr = (frame[..., :3].clamp(0.0, 1.0).cpu().numpy() * 255.0).astype("uint8")
            pil = PILImage.fromarray(arr, mode="RGB")
            cut = remove(
                pil,
                session=session,
                alpha_matting=bool(alpha_matting),
                post_process_mask=bool(post_process_mask),
            ).convert("RGBA")
            rgba = np.asarray(cut).astype("float32") / 255.0
            rgb, alpha = _composite_frame(rgba, bg_rgb, np)
            out_images.append(torch.from_numpy(rgb))
            out_masks.append(torch.from_numpy(alpha))

        image_out = torch.stack(out_images, dim=0)
        mask_out = torch.stack(out_masks, dim=0)
        return (image_out, mask_out)


NODE_CLASS_MAPPINGS = {
    "ToobusyBackgroundRemove": ToobusyBackgroundRemove,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ToobusyBackgroundRemove": "toobusy Background Remove",
}
