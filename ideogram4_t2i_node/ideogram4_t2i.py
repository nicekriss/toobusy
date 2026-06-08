import math

from ..ltx23_compact_sampler_node.ltx23_compact_sampler import _call_node, _sampler_names


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

# Ideogram 4 sampling presets (steps, mu, std) — values taken from the official
# Ideogram4 text-to-image workflow's preset table.
QUALITY_PRESETS = {
    "Quality": (48, 0.0, 1.5),
    "Default": (20, 0.0, 1.75),
    "Turbo": (12, 0.5, 1.75),
}

DEFAULT_PROMPT = (
    '{\n'
    '  "high_level_description": "",\n'
    '  "style_description": {\n'
    '    "aesthetics": "",\n'
    '    "lighting": "",\n'
    '    "photo": "",\n'
    '    "medium": "photography",\n'
    '    "color_palette": []\n'
    '  },\n'
    '  "compositional_deconstruction": {\n'
    '    "background": "",\n'
    '    "elements": []\n'
    '  }\n'
    '}'
)


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
    return names[0] if names else preferred[0]


def _diffusion_model_names():
    names = _folder_list("diffusion_models", [])
    if not names:
        names = _folder_list("unet", [])
    return names or ["ideogram4_fp8_scaled.safetensors"]


def _clip_names():
    names = _folder_list("text_encoders", [])
    if not names:
        names = _folder_list("clip", [])
    return names or ["qwen3vl_8b_fp8_scaled.safetensors"]


def _vae_names():
    return _folder_list("vae", ["flux2-vae.safetensors"])


def _lora_names():
    return ["None"] + _folder_list("loras", [])


def _round_to_16(value):
    return max(256, min(2048, int(round(value / 16)) * 16))


def _resolution(ratio_preset, megapixels):
    ratio_w, ratio_h = RATIO_PRESETS.get(ratio_preset, (1, 1))
    pixels = max(0.05, float(megapixels)) * 1_000_000
    scale = math.sqrt(pixels / (ratio_w * ratio_h))
    return _round_to_16(ratio_w * scale), _round_to_16(ratio_h * scale)


class ToobusyIdeogram4T2I:
    """Folded text-to-image sampler for a LOCAL Ideogram 4 model in ComfyUI.

    This is NOT the Ideogram web API. It runs a local Ideogram 4 checkpoint
    (CLIP type `ideogram4`, `Ideogram4Scheduler`) through the whole
    load -> encode -> sample -> decode chain as a single node, and accepts the
    Layout Builder's structured-prompt JSON as its prompt.
    """

    @classmethod
    def INPUT_TYPES(cls):
        diffusion_names = _diffusion_model_names()
        clip_names = _clip_names()
        vae_names = _vae_names()
        lora_names = _lora_names()
        sampler_names = _sampler_names()

        inputs = {
            "required": {
                "model_name": (
                    diffusion_names,
                    {"default": _first_existing(diffusion_names, ["ideogram4_fp8_scaled.safetensors"])},
                ),
                "unconditional_model_name": (
                    diffusion_names,
                    {"default": _first_existing(diffusion_names, ["ideogram4_unconditional_fp8_scaled.safetensors"])},
                ),
                "clip_name": (
                    clip_names,
                    {"default": _first_existing(clip_names, ["qwen3vl_8b_fp8_scaled.safetensors"])},
                ),
                "vae_name": (vae_names, {"default": _first_existing(vae_names, ["flux2-vae.safetensors"])}),
                "prompt": ("STRING", {"default": DEFAULT_PROMPT, "multiline": True}),
                "quality": (list(QUALITY_PRESETS.keys()) + ["Custom"], {"default": "Turbo"}),
                "steps": (
                    "INT",
                    {"default": 0, "min": 0, "max": 200,
                     "tooltip": "0 = use the quality preset's step count. Any value > 0 overrides it (and is required when quality = Custom)."},
                ),
                "ratio_preset": (list(RATIO_PRESETS.keys()), {"default": "9:16"}),
                "megapixels": ("FLOAT", {"default": 1.0, "min": 0.1, "max": 4.0, "step": 0.05}),
                "seed": (
                    "INT",
                    {"default": 0, "min": 0, "max": 0xffffffffffffffff, "control_after_generate": True},
                ),
                "sampler_name": (
                    sampler_names,
                    {"default": "res_multistep" if "res_multistep" in sampler_names else sampler_names[0]},
                ),
                "cfg": ("FLOAT", {"default": 7.0, "min": 0.0, "max": 100.0, "step": 0.1}),
                "lora_slots": ("INT", {"default": 0, "min": 0, "max": MAX_LORA_SLOTS}),
            },
            "optional": {
                "width": (
                    "INT",
                    {"default": 0, "min": 0, "max": 2048, "step": 16,
                     "tooltip": "0 = use ratio_preset + megapixels. Connect Layout Builder's width here to use its resolution."},
                ),
                "height": (
                    "INT",
                    {"default": 0, "min": 0, "max": 2048, "step": 16,
                     "tooltip": "0 = use ratio_preset + megapixels. Connect Layout Builder's height here to use its resolution."},
                ),
                "mu": ("FLOAT", {"default": 0.5, "min": -10.0, "max": 10.0, "step": 0.05, "tooltip": "Used only when quality = Custom."}),
                "std": ("FLOAT", {"default": 1.75, "min": 0.1, "max": 5.0, "step": 0.05, "tooltip": "Used only when quality = Custom."}),
                "cfg_override": ("FLOAT", {"default": 3.0, "min": 0.0, "max": 100.0, "step": 0.1}),
                "cfg_override_start": ("FLOAT", {"default": 0.9, "min": 0.0, "max": 1.0, "step": 0.01}),
                "cfg_override_end": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.01}),
            },
        }

        required = inputs["required"]
        for slot in range(1, MAX_LORA_SLOTS + 1):
            required[f"lora_{slot}_enable"] = ("BOOLEAN", {"default": False})
            required[f"lora_{slot}_name"] = (lora_names, {"default": "None"})
            required[f"lora_{slot}_strength"] = (
                "FLOAT",
                {"default": 1.0, "min": -10.0, "max": 10.0, "step": 0.01},
            )

        return inputs

    RETURN_TYPES = ("IMAGE", "LATENT", "INT", "INT")
    RETURN_NAMES = ("image", "latent", "width", "height")
    FUNCTION = "generate"
    CATEGORY = "toobusy/Make"

    def generate(
        self,
        model_name,
        unconditional_model_name,
        clip_name,
        vae_name,
        prompt,
        quality,
        steps,
        ratio_preset,
        megapixels,
        seed,
        sampler_name,
        cfg,
        lora_slots,
        width=0,
        height=0,
        mu=0.5,
        std=1.75,
        cfg_override=3.0,
        cfg_override_start=0.9,
        cfg_override_end=1.0,
        **lora_kwargs,
    ):
        if quality == "Custom":
            preset_steps = int(steps) if int(steps) > 0 else 20
            preset_mu, preset_std = float(mu), float(std)
        else:
            preset_steps, preset_mu, preset_std = QUALITY_PRESETS.get(quality, QUALITY_PRESETS["Turbo"])
            if int(steps) > 0:  # manual override of the preset step count
                preset_steps = int(steps)

        steps, mu, std = preset_steps, preset_mu, preset_std

        # Resolution: explicit width/height (e.g. from the Layout Builder) wins;
        # otherwise derive from ratio_preset + megapixels.
        if int(width) > 0 and int(height) > 0:
            width, height = _round_to_16(int(width)), _round_to_16(int(height))
        else:
            width, height = _resolution(ratio_preset, megapixels)

        # Loaders
        model = _call_node("UNETLoader", unet_name=model_name, weight_dtype="default")[0]
        model_uncond = _call_node("UNETLoader", unet_name=unconditional_model_name, weight_dtype="default")[0]
        clip = _call_node("CLIPLoader", clip_name=clip_name, type="ideogram4", device="default")[0]
        vae = _call_node("VAELoader", vae_name=vae_name)[0]

        lora_slots = max(0, min(MAX_LORA_SLOTS, int(lora_slots)))
        for slot in range(1, lora_slots + 1):
            enabled = lora_kwargs.get(f"lora_{slot}_enable", False)
            lora_name = lora_kwargs.get(f"lora_{slot}_name", "None")
            lora_strength = float(lora_kwargs.get(f"lora_{slot}_strength", 1.0))
            if enabled and lora_name != "None":
                model, clip = _call_node(
                    "LoraLoader",
                    model=model,
                    clip=clip,
                    lora_name=lora_name,
                    strength_model=lora_strength,
                    strength_clip=lora_strength,
                )

        # Conditioning (asymmetric CFG: negative is a zeroed-out copy of positive)
        positive = _call_node("CLIPTextEncode", clip=clip, text=prompt)[0]
        negative = _call_node("ConditioningZeroOut", conditioning=positive)[0]

        # cfg override on the conditional model over a sigma range
        model = _call_node(
            "CFGOverride",
            model=model,
            cfg=float(cfg_override),
            start_percent=float(cfg_override_start),
            end_percent=float(cfg_override_end),
        )[0]

        guider = _call_node(
            "DualModelGuider",
            model=model,
            positive=positive,
            cfg=float(cfg),
            model_negative=model_uncond,
            negative=negative,
        )[0]

        noise = _call_node("RandomNoise", noise_seed=int(seed))[0]
        sampler = _call_node("KSamplerSelect", sampler_name=sampler_name)[0]
        sigmas = _call_node(
            "Ideogram4Scheduler",
            steps=int(steps),
            width=width,
            height=height,
            mu=float(mu),
            std=float(std),
        )[0]
        latent = _call_node("EmptyFlux2LatentImage", width=width, height=height, batch_size=1)[0]

        sampled = _call_node(
            "SamplerCustomAdvanced",
            noise=noise,
            guider=guider,
            sampler=sampler,
            sigmas=sigmas,
            latent_image=latent,
        )[0]

        image = _call_node("VAEDecode", samples=sampled, vae=vae)[0]
        return (image, sampled, width, height)


NODE_CLASS_MAPPINGS = {
    "ToobusyIdeogram4T2I": ToobusyIdeogram4T2I,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ToobusyIdeogram4T2I": "toobusy Ideogram4 T2I (local model)",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
