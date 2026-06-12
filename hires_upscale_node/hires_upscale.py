"""toobusy Hires Upscale.

Folds the classic hires-fix preparation combo into one node:

    Load Upscale Model -> Upscale Image (using Model) -> Upscale Image By
    (e.g. lanczos 0.50) -> VAE Encode

A 4x ESRGAN-family model takes the image up, ``scale_by`` brings it back down
to the working resolution (4x * 0.5 = a clean 2x with model detail), and the
result is VAE-encoded so it can feed a second sampler pass directly.
"""

from ..ltx23_compact_sampler_node.ltx23_compact_sampler import _call_node

PREFERRED_DEFAULT_MODELS = (
    "ESRGAN/4x_foolhardy_Remacri.pth",
    "4x_foolhardy_Remacri.pth",
)


def _upscale_model_names():
    try:
        import folder_paths

        names = list(folder_paths.get_filename_list("upscale_models"))
        if names:
            return names
    except Exception:
        pass
    return ["ESRGAN/4x_foolhardy_Remacri.pth"]


def _default_model_name(names):
    for preferred in PREFERRED_DEFAULT_MODELS:
        if preferred in names:
            return preferred
    for name in names:
        if "remacri" in name.lower():
            return name
    return names[0]


def _resample_methods():
    try:
        import nodes

        methods = nodes.NODE_CLASS_MAPPINGS["ImageScaleBy"].INPUT_TYPES()["required"]["upscale_method"][0]
        if isinstance(methods, (list, tuple)) and methods:
            return list(methods)
    except Exception:
        pass
    return ["nearest-exact", "bilinear", "area", "bicubic", "lanczos"]


class ToobusyHiresUpscale:
    """Folds UpscaleModelLoader + ImageUpscaleWithModel + ImageScaleBy +
    VAEEncode (4 nodes) into one hires-fix preparation node."""

    @classmethod
    def INPUT_TYPES(cls):
        model_names = _upscale_model_names()
        methods = _resample_methods()
        return {
            "required": {
                "image": ("IMAGE",),
                "vae": ("VAE",),
                "upscale_model_name": (
                    model_names,
                    {
                        "default": _default_model_name(model_names),
                        "tooltip": "ESRGAN-family upscale model. Skipped when the upscale_model override is connected.",
                    },
                ),
                "downscale_method": (
                    methods,
                    {"default": "lanczos" if "lanczos" in methods else methods[0]},
                ),
                "scale_by": (
                    "FLOAT",
                    {
                        "default": 0.50,
                        "min": 0.05,
                        "max": 8.0,
                        "step": 0.05,
                        "tooltip": "Resample factor applied AFTER the model upscale. A 4x model at 0.50 lands on a clean 2x. 1.0 keeps the raw model output.",
                    },
                ),
            },
            "optional": {
                "upscale_model": ("UPSCALE_MODEL",),
            },
        }

    RETURN_TYPES = ("IMAGE", "LATENT", "INT", "INT")
    RETURN_NAMES = ("image", "latent", "width", "height")
    FUNCTION = "upscale"
    CATEGORY = "toobusy/Make"

    def upscale(self, image, vae, upscale_model_name, downscale_method, scale_by, upscale_model=None):
        if upscale_model is None:
            upscale_model = _call_node("UpscaleModelLoader", model_name=upscale_model_name)[0]
        else:
            print("[toobusy Hires Upscale] Using connected upscale_model override.")

        upscaled = _call_node("ImageUpscaleWithModel", upscale_model=upscale_model, image=image)[0]

        scale_by = float(scale_by)
        if abs(scale_by - 1.0) > 1e-6:
            upscaled = _call_node(
                "ImageScaleBy",
                image=upscaled,
                upscale_method=downscale_method,
                scale_by=scale_by,
            )[0]

        latent = _call_node("VAEEncode", pixels=upscaled, vae=vae)[0]

        try:
            height = int(upscaled.shape[1])
            width = int(upscaled.shape[2])
        except (AttributeError, IndexError, TypeError):
            width = height = 0
        return (upscaled, latent, width, height)


NODE_CLASS_MAPPINGS = {
    "ToobusyHiresUpscale": ToobusyHiresUpscale,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ToobusyHiresUpscale": "toobusy Hires Upscale",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
