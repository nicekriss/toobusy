import math

from ..ltx23_compact_sampler_node.ltx23_compact_sampler import _call_node, _default_sampler_name, _sampler_names


RATIO_PRESETS = {
    "1:1": (1, 1),
    "16:9": (16, 9),
    "9:16": (9, 16),
    "4:3": (4, 3),
    "3:4": (3, 4),
    "3:2": (3, 2),
    "2:3": (2, 3),
    "21:9": (21, 9),
    "9:21": (9, 21),
}

MAX_LORA_SLOTS = 5


def _folder_list(kind, fallback):
    try:
        import folder_paths

        names = list(folder_paths.get_filename_list(kind))
        return names or fallback
    except Exception:
        return fallback


def _first_existing(names, preferred):
    for name in preferred:
        if name in names:
            return name
    return names[0]


def _model_names():
    names = _folder_list("diffusion_models", [])
    if not names:
        names = _folder_list("unet", [])
    return names or ["ZIT\\zImage_turbo.safetensors"]


def _clip_names():
    names = _folder_list("text_encoders", [])
    if not names:
        names = _folder_list("clip", [])
    return names or ["ZIT\\zImage_textEncoder.safetensors"]


def _vae_names():
    return _folder_list("vae", ["FLUX1\\ae.safetensors"])


def _lora_names():
    return ["None"] + _folder_list("loras", ["Lora\\ZIT\\ZIT_Neobabae_v1.safetensors"])


def _default_lora_name(lora_names):
    preferred = ["Lora\\ZIT\\ZIT_Neobabae_v1.safetensors", "ZIT\\ZIT_Neobabae_v1.safetensors"]
    for name in preferred:
        if name in lora_names:
            return name

    for name in lora_names:
        if "ZIT_Neobabae" in name:
            return name

    return lora_names[1] if len(lora_names) > 1 else "None"


def _scheduler_names():
    try:
        import comfy.samplers

        names = list(comfy.samplers.KSampler.SCHEDULERS)
        if names:
            return names
    except Exception:
        pass

    return ["simple", "normal", "karras", "exponential", "sgm_uniform"]


def _round_to(value, divisible_by):
    return max(int(divisible_by), int(round(value / divisible_by)) * int(divisible_by))


def _resolution_from_megapixels(ratio_preset, megapixels, divisible_by):
    ratio_w, ratio_h = RATIO_PRESETS.get(ratio_preset, RATIO_PRESETS["1:1"])
    pixels = max(0.01, float(megapixels)) * 1_000_000
    scale = math.sqrt(pixels / (ratio_w * ratio_h))
    width = _round_to(ratio_w * scale, int(divisible_by))
    height = _round_to(ratio_h * scale, int(divisible_by))
    return width, height


class ToobusyZImageTurbo:
    @classmethod
    def INPUT_TYPES(cls):
        model_names = _model_names()
        clip_names = _clip_names()
        vae_names = _vae_names()
        lora_names = _lora_names()
        sampler_names = _sampler_names()
        scheduler_names = _scheduler_names()

        base = {
            "required": {
                "model_name": (model_names, {"default": _first_existing(model_names, ["ZIT\\zImage_turbo.safetensors"])}),
                "clip_name": (clip_names, {"default": _first_existing(clip_names, ["ZIT\\zImage_textEncoder.safetensors"])}),
                "vae_name": (vae_names, {"default": _first_existing(vae_names, ["FLUX1\\ae.safetensors"])}),
                "positive": ("STRING", {"default": "", "multiline": True}),
                "negative": ("STRING", {"default": "", "multiline": True}),
                "ratio_preset": (list(RATIO_PRESETS.keys()), {"default": "2:3"}),
                "megapixels": ("FLOAT", {"default": 1.0, "min": 0.1, "max": 4.0, "step": 0.05}),
                "divisible_by": ("INT", {"default": 32, "min": 8, "max": 128, "step": 8}),
                "batch_size": ("INT", {"default": 1, "min": 1, "max": 64}),
                "seed": (
                    "INT",
                    {
                        "default": 1,
                        "min": 0,
                        "max": 0xffffffffffffffff,
                        "control_after_generate": True,
                    },
                ),
                "steps": ("INT", {"default": 8, "min": 1, "max": 100}),
                "cfg": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 30.0, "step": 0.1}),
                "sampler_name": (sampler_names, {"default": "res_multistep" if "res_multistep" in sampler_names else _default_sampler_name(sampler_names)}),
                "scheduler": (scheduler_names, {"default": "simple" if "simple" in scheduler_names else scheduler_names[0]}),
                "denoise": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.01}),
                "aura_shift": ("FLOAT", {"default": 3.0, "min": 0.0, "max": 20.0, "step": 0.1}),
                "lora_slots": ("INT", {"default": 1, "min": 0, "max": MAX_LORA_SLOTS}),
            },
        }

        required = base["required"]
        for slot in range(1, MAX_LORA_SLOTS + 1):
            required[f"lora_{slot}_enable"] = ("BOOLEAN", {"default": slot == 1})
            required[f"lora_{slot}_name"] = (
                lora_names,
                {"default": _default_lora_name(lora_names) if slot == 1 else "None"},
            )
            required[f"lora_{slot}_strength"] = (
                "FLOAT",
                {"default": 1.0, "min": -10.0, "max": 10.0, "step": 0.01},
            )

        return base

    RETURN_TYPES = ("IMAGE", "LATENT", "INT", "INT")
    RETURN_NAMES = ("image", "latent", "width", "height")
    FUNCTION = "generate"
    CATEGORY = "toobusy/Z-Image"

    def generate(
        self,
        model_name,
        clip_name,
        vae_name,
        positive,
        negative,
        ratio_preset,
        megapixels,
        divisible_by,
        batch_size,
        seed,
        steps,
        cfg,
        sampler_name,
        scheduler,
        denoise,
        aura_shift,
        lora_slots,
        **lora_kwargs,
    ):
        width, height = _resolution_from_megapixels(ratio_preset, megapixels, divisible_by)

        model = _call_node("UNETLoader", unet_name=model_name, weight_dtype="default")[0]
        clip = _call_node("CLIPLoader", clip_name=clip_name, type="lumina2", device="default")[0]
        vae = _call_node("VAELoader", vae_name=vae_name)[0]

        lora_slots = max(0, min(MAX_LORA_SLOTS, int(lora_slots)))
        for slot in range(1, lora_slots + 1):
            enabled = lora_kwargs.get(f"lora_{slot}_enable", False)
            lora_name = lora_kwargs.get(f"lora_{slot}_name", "None")
            lora_strength = lora_kwargs.get(f"lora_{slot}_strength", 1.0)
            if enabled and lora_name != "None":
                model, clip = _call_node(
                    "LoraLoader",
                    model=model,
                    clip=clip,
                    lora_name=lora_name,
                    strength_model=lora_strength,
                    strength_clip=lora_strength,
                )

        model = _call_node("ModelSamplingAuraFlow", model=model, shift=aura_shift)[0]
        positive_cond = _call_node("CLIPTextEncode", clip=clip, text=positive)[0]
        negative_cond = _call_node("CLIPTextEncode", clip=clip, text=negative)[0]
        latent_image = _call_node(
            "EmptyLatentImage",
            width=width,
            height=height,
            batch_size=batch_size,
        )[0]

        sampled = _call_node(
            "KSampler",
            model=model,
            seed=seed,
            steps=steps,
            cfg=cfg,
            sampler_name=sampler_name,
            scheduler=scheduler,
            positive=positive_cond,
            negative=negative_cond,
            latent_image=latent_image,
            denoise=denoise,
        )[0]
        image = _call_node("VAEDecode", samples=sampled, vae=vae)[0]

        return (image, sampled, width, height)


NODE_CLASS_MAPPINGS = {
    "ToobusyZImageTurbo": ToobusyZImageTurbo,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ToobusyZImageTurbo": "toobusy Z-Image Turbo",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
