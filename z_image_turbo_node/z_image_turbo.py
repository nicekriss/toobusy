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
    return names or ["ZIT/zImage_turbo.safetensors"]


def _clip_names():
    names = _folder_list("text_encoders", [])
    if not names:
        names = _folder_list("clip", [])
    return names or ["ZIT/zImage_textEncoder.safetensors"]


def _vae_names():
    return _folder_list("vae", ["FLUX1/ae.safetensors"])


def _lora_names():
    return ["None"] + _folder_list("loras", ["Lora/ZIT/ZIT_Neobabae_v1.safetensors"])


def _default_lora_name(lora_names):
    preferred = ["Lora/ZIT/ZIT_Neobabae_v1.safetensors", "ZIT/ZIT_Neobabae_v1.safetensors"]
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


def _image_dims(image):
    """Pixel (width, height) of a ComfyUI IMAGE tensor, cropped to the VAE's
    factor of 8. IMAGE tensors are shaped [batch, height, width, channels]."""
    try:
        height = int(image.shape[1])
        width = int(image.shape[2])
    except (AttributeError, IndexError, TypeError):
        return 0, 0
    return (width // 8) * 8, (height // 8) * 8


def _apply_zit_control(model, vae, control, width, height):
    """Apply a `toobusy ZIT ControlNet` bundle to the final model. Each active
    entry stacks its own Fun-ControlNet-Union patch (model patches append, so
    depth + canny + pose can drive the model together); control maps are
    resized to the actual generation size first."""
    entries = list(control.get("entries", [])) if isinstance(control, dict) else []
    if not entries:
        return model

    model_patch = _call_node("ModelPatchLoader", name=control.get("patch_name"))[0]
    for entry in entries:
        image = entry.get("image")
        if image is None:
            continue
        sized = _call_node(
            "ImageScale",
            image=image,
            upscale_method="lanczos",
            width=int(width),
            height=int(height),
            crop="center",
        )[0]
        strength = float(entry.get("strength", 1.0))
        model = _call_node(
            "QwenImageDiffsynthControlnet",
            model=model,
            model_patch=model_patch,
            vae=vae,
            image=sized,
            strength=strength,
        )[0]
        print(f"[toobusy Z-Image Turbo] ControlNet patch applied: {entry.get('type')} @ {strength}")
    return model


def _resolution_from_megapixels(ratio_preset, megapixels, divisible_by):
    ratio_w, ratio_h = RATIO_PRESETS.get(ratio_preset, RATIO_PRESETS["1:1"])
    pixels = max(0.01, float(megapixels)) * 1_000_000
    scale = math.sqrt(pixels / (ratio_w * ratio_h))
    width = _round_to(ratio_w * scale, int(divisible_by))
    height = _round_to(ratio_h * scale, int(divisible_by))
    return width, height


class ToobusyZImageTurbo:
    """Folds a full Z-Image Turbo text-to-image graph into one node.

    Replaces, in order: UNETLoader + CLIPLoader + VAELoader + (optional
    LoraLoader chain) + ModelSamplingAuraFlow + CLIPTextEncode x2 +
    EmptyLatentImage + KSampler + VAEDecode (~10 nodes -> 1).
    Connecting the optional `image` input auto-switches to img2img: the image
    is VAE-encoded as the starting latent (EmptyLatentImage -> VAEEncode, with
    an optional ImageScale when width/height are set) and `denoise` controls
    the change strength.
    Needs Z-Image Turbo model + lumina2 text encoder + VAE in your model folders.
    """

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
                "model_name": (model_names, {"default": _first_existing(model_names, ["ZIT/zImage_turbo.safetensors"])}),
                "clip_name": (clip_names, {"default": _first_existing(clip_names, ["ZIT/zImage_textEncoder.safetensors"])}),
                "vae_name": (vae_names, {"default": _first_existing(vae_names, ["FLUX1/ae.safetensors"])}),
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
                "lora_slots": ("INT", {"default": 0, "min": 0, "max": MAX_LORA_SLOTS}),
            },
            "optional": {
                "image": (
                    "IMAGE",
                    {"tooltip": "Connect an image to switch this node to img2img. The image is VAE-encoded as the starting latent and 'denoise' becomes the change strength (lower = closer to the source). Leave unconnected for plain text-to-image."},
                ),
                "width": (
                    "INT",
                    {"default": 0, "min": 0, "max": 8192, "step": 8,
                     "tooltip": "0 = use ratio_preset + megapixels. Set width AND height > 0 to enter the resolution directly (rounded to divisible_by). In img2img this scales the source image to the given size."},
                ),
                "height": (
                    "INT",
                    {"default": 0, "min": 0, "max": 8192, "step": 8,
                     "tooltip": "0 = use ratio_preset + megapixels. Set width AND height > 0 to enter the resolution directly (rounded to divisible_by). In img2img this scales the source image to the given size."},
                ),
                "model_override": ("MODEL",),
                "clip_override": ("CLIP",),
                "vae_override": ("VAE",),
                "zit_control": (
                    "ZIT_CONTROL",
                    {"tooltip": "Connect a 'toobusy ZIT ControlNet' module to apply depth/canny/pose Fun-ControlNet-Union model patches. Leave unconnected for plain generation."},
                ),
            },
        }

        required = base["required"]
        for slot in range(1, MAX_LORA_SLOTS + 1):
            # No LoRA auto-enabled: the node starts with zero active slots. Slot 1
            # is still pre-filled with the recommended LoRA name so that *adding*
            # a slot is one click, but nothing is applied until it's enabled.
            required[f"lora_{slot}_enable"] = ("BOOLEAN", {"default": False})
            required[f"lora_{slot}_name"] = (
                lora_names,
                {"default": _default_lora_name(lora_names) if slot == 1 else "None"},
            )
            required[f"lora_{slot}_strength"] = (
                "FLOAT",
                {"default": 1.0, "min": -10.0, "max": 10.0, "step": 0.01},
            )

        return base

    # Passthrough outputs of what this node loaded and prepared, so follow-up
    # stages (toobusy Hires Upscale + a second sampler pass) need no external
    # loaders or re-typed prompts. Two model flavors:
    #   model       — exactly what sampled here: LoRA + shift + any zit_control
    #                 patches (control maps are bound to THIS run's resolution;
    #                 at a different second-pass size prefer model_clean).
    #   model_clean — the model as loaded (override or internal), before LoRA /
    #                 shift / controlnet: swap LoRAs or re-shift externally.
    # Appended after the original outputs so existing workflows keep their slots.
    RETURN_TYPES = ("IMAGE", "LATENT", "INT", "INT", "MODEL", "MODEL", "CLIP", "VAE", "CONDITIONING", "CONDITIONING")
    RETURN_NAMES = ("image", "latent", "width", "height", "model", "model_clean", "clip", "vae", "positive", "negative")
    FUNCTION = "generate"
    CATEGORY = "toobusy/Make"

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
        image=None,
        width=0,
        height=0,
        model_override=None,
        clip_override=None,
        vae_override=None,
        zit_control=None,
        **lora_kwargs,
    ):
        # Resolution: explicit width AND height win (rounded to divisible_by);
        # otherwise derive from ratio_preset + megapixels.
        if int(width) > 0 and int(height) > 0:
            target_w = _round_to(int(width), divisible_by)
            target_h = _round_to(int(height), divisible_by)
        else:
            target_w, target_h = _resolution_from_megapixels(ratio_preset, megapixels, divisible_by)

        if model_override is not None:
            print("[toobusy Z-Image Turbo] Using external MODEL override. Internal model loader ignored.")
            model = model_override
        else:
            print("[toobusy Z-Image Turbo] Using internal MODEL loader.")
            model = _call_node("UNETLoader", unet_name=model_name, weight_dtype="default")[0]

        if clip_override is not None:
            print("[toobusy Z-Image Turbo] Using external CLIP override. Internal CLIP loader ignored.")
            clip = clip_override
        else:
            print("[toobusy Z-Image Turbo] Using internal CLIP loader.")
            clip = _call_node("CLIPLoader", clip_name=clip_name, type="lumina2", device="default")[0]

        if vae_override is not None:
            print("[toobusy Z-Image Turbo] Using external VAE override. Internal VAE loader ignored.")
            vae = vae_override
        else:
            print("[toobusy Z-Image Turbo] Using internal VAE loader.")
            vae = _call_node("VAELoader", vae_name=vae_name)[0]

        # Clean passthrough: the model exactly as loaded, before LoRA / shift /
        # controlnet — for swapping LoRAs in a second pass.
        model_clean = model

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

        # Latent source. A connected image auto-switches the node to img2img:
        # the image is VAE-encoded into the starting latent and 'denoise' acts
        # as the change strength. Otherwise we start from an empty latent (t2i).
        if image is not None:
            explicit_size = int(width) > 0 and int(height) > 0
            if explicit_size:
                print(f"[toobusy Z-Image Turbo] Image input detected -> img2img. Scaling source to {target_w}x{target_h} (denoise = strength).")
                pixels = _call_node(
                    "ImageScale",
                    image=image,
                    upscale_method="lanczos",
                    width=target_w,
                    height=target_h,
                    crop="center",
                )[0]
                width, height = target_w, target_h
            else:
                print("[toobusy Z-Image Turbo] Image input detected -> img2img. Using source image size (denoise = strength).")
                pixels = image
                width, height = _image_dims(image)
            latent_image = _call_node("VAEEncode", pixels=pixels, vae=vae)[0]
        else:
            latent_image = _call_node(
                "EmptyLatentImage",
                width=target_w,
                height=target_h,
                batch_size=batch_size,
            )[0]
            width, height = target_w, target_h

        # ControlNet module (optional): patch the final model — override/LoRA
        # included — once the generation size is known, so control maps match
        # the latent. Without a connected module nothing changes.
        if zit_control is not None:
            model = _apply_zit_control(model, vae, zit_control, width, height)

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

        return (image, sampled, width, height, model, model_clean, clip, vae, positive_cond, negative_cond)


NODE_CLASS_MAPPINGS = {
    "ToobusyZImageTurbo": ToobusyZImageTurbo,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ToobusyZImageTurbo": "toobusy Z-Image Turbo",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
