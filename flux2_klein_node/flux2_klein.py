import inspect
import math

from ..ltx23_compact_sampler_node.ltx23_compact_sampler import _default_sampler_name, _sampler_names


RATIO_PRESETS = {
    "1:1": (1, 1),
    "16:9": (16, 9),
    "9:16": (9, 16),
    "4:3": (4, 3),
    "3:4": (3, 4),
    "3:2": (3, 2),
    "2:3": (2, 3),
}

MAX_LORA_SLOTS = 5
MAX_REFERENCE_SLOTS = 3

# The operator workflow exports the Flux2 Klein reference conditioners with
# UUID class ids. Keep them as constants so the folded node calls the same graph.
KLEIN_REF1_NODE = "6f5ae6ae-be1f-4f5c-a5af-178cfb6f7d59"
KLEIN_REF2_NODE = "49cbf2f1-9ad3-46a0-a601-3dcd6841d1d5"
KLEIN_REF3_NODE = "27a7eb01-8cd8-445b-a655-f79d702ab0c8"


def _node_class(class_name):
    import nodes

    try:
        return nodes.NODE_CLASS_MAPPINGS[class_name]
    except KeyError as exc:
        raise RuntimeError(
            f"Required ComfyUI node '{class_name}' is not available. "
            "This folded Flux2 Klein workflow needs Flux2/Klein reference nodes "
            "installed in the current ComfyUI environment."
        ) from exc


def _call_node(class_name, **kwargs):
    cls = _node_class(class_name)
    node = cls()
    fn_name = getattr(cls, "FUNCTION", None)
    if not fn_name:
        raise RuntimeError(f"Node '{class_name}' does not define FUNCTION.")

    fn = getattr(node, fn_name)
    signature = inspect.signature(fn)
    if any(param.kind == inspect.Parameter.VAR_KEYWORD for param in signature.parameters.values()):
        return fn(**kwargs)

    filtered = {key: value for key, value in kwargs.items() if key in signature.parameters}
    return fn(**filtered)


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
    return names or ["FLUX2/flux-2-klein-9b-kv-fp8.safetensors"]


def _clip_names():
    names = _folder_list("text_encoders", [])
    if not names:
        names = _folder_list("clip", [])
    return names or ["flux2/qwen_3_8b_fp8mixed.safetensors"]


def _vae_names():
    return _folder_list("vae", ["flux2/flux2-vae.safetensors"])


def _lora_names():
    return ["None"] + _folder_list("loras", ["None"])


def _scheduler_names():
    # Flux2Scheduler drives the sigma schedule in this workflow; scheduler is
    # not a separate user-facing choice. Keep this helper for future expansion.
    return ["flux2"]


def _round_to(value, divisible_by):
    return max(int(divisible_by), int(round(value / divisible_by)) * int(divisible_by))


def _resolution_from_megapixels(ratio_preset, megapixels, divisible_by):
    ratio_w, ratio_h = RATIO_PRESETS.get(ratio_preset, RATIO_PRESETS["1:1"])
    pixels = max(0.01, float(megapixels)) * 1_000_000
    scale = math.sqrt(pixels / (ratio_w * ratio_h))
    width = _round_to(ratio_w * scale, int(divisible_by))
    height = _round_to(ratio_h * scale, int(divisible_by))
    return width, height


def _image_dims(image):
    try:
        height = int(image.shape[1])
        width = int(image.shape[2])
    except (AttributeError, IndexError, TypeError):
        return 0, 0
    return (width // 8) * 8, (height // 8) * 8


def _load_clip(clip_name):
    return _call_node("CLIPLoader", clip_name=clip_name, type="lumina2", device="default")[0]


class ToobusyFlux2Klein:
    """Folds the operator's Flux2 Klein 9B KV three-reference graph.

    Replaces: UNETLoader + FluxKVCache + CLIPLoader + VAELoader +
    CLIPTextEncode + three Klein reference conditioning nodes +
    BasicGuider + RandomNoise + KSamplerSelect + Flux2Scheduler +
    EmptyFlux2LatentImage + SamplerCustomAdvanced + VAEDecode.
    """

    @classmethod
    def INPUT_TYPES(cls):
        model_names = _model_names()
        clip_names = _clip_names()
        vae_names = _vae_names()
        lora_names = _lora_names()
        sampler_names = _sampler_names()

        base = {
            "required": {
                "model_name": (model_names, {"default": _first_existing(model_names, ["FLUX2/flux-2-klein-9b-kv-fp8.safetensors", "FLUX2\\flux-2-klein-9b-kv-fp8.safetensors"])}),
                "clip_name": (clip_names, {"default": _first_existing(clip_names, ["flux2/qwen_3_8b_fp8mixed.safetensors", "flux2\\qwen_3_8b_fp8mixed.safetensors"])}),
                "vae_name": (vae_names, {"default": _first_existing(vae_names, ["flux2/flux2-vae.safetensors", "flux2\\flux2-vae.safetensors"])}),
                "positive": (
                    "STRING",
                    {
                        "default": "shopping mall clothing detail shot, studio product photo, clean white background, mint wide pants, no human",
                        "multiline": True,
                    },
                ),
                "ratio_preset": (list(RATIO_PRESETS.keys()), {"default": "1:1"}),
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
                "steps": ("INT", {"default": 4, "min": 1, "max": 100}),
                "sampler_name": (sampler_names, {"default": "euler" if "euler" in sampler_names else _default_sampler_name(sampler_names)}),
                "lora_slots": ("INT", {"default": 0, "min": 0, "max": MAX_LORA_SLOTS}),
                "reference_slots": ("INT", {"default": 3, "min": 0, "max": MAX_REFERENCE_SLOTS}),
            },
            "optional": {
                "width": (
                    "INT",
                    {"default": 0, "min": 0, "max": 8192, "step": 8,
                     "tooltip": "0 = use reference #1 size when connected; otherwise ratio_preset + megapixels. Set width AND height > 0 for manual size."},
                ),
                "height": (
                    "INT",
                    {"default": 0, "min": 0, "max": 8192, "step": 8,
                     "tooltip": "0 = use reference #1 size when connected; otherwise ratio_preset + megapixels. Set width AND height > 0 for manual size."},
                ),
                "reference_1_image": ("IMAGE", {"tooltip": "Reference #1. In the source workflow this image also drives the default width/height."}),
                "reference_2_image": ("IMAGE", {"tooltip": "Reference #2. Applied after reference #1 in the conditioning chain."}),
                "reference_3_image": ("IMAGE", {"tooltip": "Reference #3. Applied last in the Klein conditioning chain."}),
                "model_override": ("MODEL",),
                "clip_override": ("CLIP",),
                "vae_override": ("VAE",),
            },
        }

        required = base["required"]
        for slot in range(1, MAX_REFERENCE_SLOTS + 1):
            required[f"reference_{slot}_enable"] = ("BOOLEAN", {"default": True})

        for slot in range(1, MAX_LORA_SLOTS + 1):
            required[f"lora_{slot}_enable"] = ("BOOLEAN", {"default": False})
            required[f"lora_{slot}_name"] = (lora_names, {"default": "None"})
            required[f"lora_{slot}_strength"] = (
                "FLOAT",
                {"default": 1.0, "min": -10.0, "max": 10.0, "step": 0.01},
            )

        return base

    RETURN_TYPES = ("IMAGE", "LATENT", "INT", "INT")
    RETURN_NAMES = ("image", "latent", "width", "height")
    FUNCTION = "generate"
    CATEGORY = "toobusy/Make"

    def generate(
        self,
        model_name,
        clip_name,
        vae_name,
        positive,
        ratio_preset,
        megapixels,
        divisible_by,
        batch_size,
        seed,
        steps,
        sampler_name,
        lora_slots,
        reference_slots,
        width=0,
        height=0,
        reference_1_image=None,
        reference_2_image=None,
        reference_3_image=None,
        model_override=None,
        clip_override=None,
        vae_override=None,
        **slot_kwargs,
    ):
        if model_override is not None:
            print("[toobusy Flux2 Klein] Using external MODEL override. Internal model loader ignored.")
            model = model_override
        else:
            print("[toobusy Flux2 Klein] Using internal MODEL loader.")
            model = _call_node("UNETLoader", unet_name=model_name, weight_dtype="default")[0]

        if clip_override is not None:
            print("[toobusy Flux2 Klein] Using external CLIP override. Internal CLIP loader ignored.")
            clip = clip_override
        else:
            print("[toobusy Flux2 Klein] Using internal CLIP loader.")
            clip = _load_clip(clip_name)

        if vae_override is not None:
            print("[toobusy Flux2 Klein] Using external VAE override. Internal VAE loader ignored.")
            vae = vae_override
        else:
            print("[toobusy Flux2 Klein] Using internal VAE loader.")
            vae = _call_node("VAELoader", vae_name=vae_name)[0]

        lora_slots = max(0, min(MAX_LORA_SLOTS, int(lora_slots)))
        for slot in range(1, lora_slots + 1):
            enabled = slot_kwargs.get(f"lora_{slot}_enable", False)
            lora_name = slot_kwargs.get(f"lora_{slot}_name", "None")
            lora_strength = slot_kwargs.get(f"lora_{slot}_strength", 1.0)
            if enabled and lora_name != "None":
                model, clip = _call_node(
                    "LoraLoader",
                    model=model,
                    clip=clip,
                    lora_name=lora_name,
                    strength_model=lora_strength,
                    strength_clip=lora_strength,
                )
                print(f"[toobusy Flux2 Klein] LoRA slot {slot} applied: {lora_name} @ {lora_strength}")

        model = _call_node("FluxKVCache", model=model)[0]
        conditioning = _call_node("CLIPTextEncode", clip=clip, text=positive)[0]

        reference_slots = max(0, min(MAX_REFERENCE_SLOTS, int(reference_slots)))
        references = {
            1: reference_1_image,
            2: reference_2_image,
            3: reference_3_image,
        }
        ref_nodes = {
            1: KLEIN_REF1_NODE,
            2: KLEIN_REF2_NODE,
            3: KLEIN_REF3_NODE,
        }
        base_image = None
        first_active_image = None

        for slot in range(1, reference_slots + 1):
            enabled = bool(slot_kwargs.get(f"reference_{slot}_enable", True))
            image = references.get(slot)
            if not enabled:
                print(f"[toobusy Flux2 Klein] Reference #{slot} disabled.")
                continue
            if image is None:
                print(f"[toobusy Flux2 Klein] Reference #{slot} enabled but no IMAGE connected; skipped.")
                continue
            if first_active_image is None:
                first_active_image = image

            if slot == 1:
                conditioning, base_image = _call_node(ref_nodes[slot], on_false=conditioning, vae=vae, image=image)
            elif slot == 2:
                conditioning = _call_node(ref_nodes[slot], image=image, vae=vae, conditioning=conditioning)[0]
            else:
                conditioning = _call_node(ref_nodes[slot], vae=vae, conditioning=conditioning, image=image)[0]
            print(f"[toobusy Flux2 Klein] Reference #{slot} applied.")

        if int(width) > 0 and int(height) > 0:
            target_w = _round_to(int(width), divisible_by)
            target_h = _round_to(int(height), divisible_by)
        else:
            size_image = base_image if base_image is not None else first_active_image
            target_w, target_h = _image_dims(size_image) if size_image is not None else (0, 0)
            if target_w <= 0 or target_h <= 0:
                target_w, target_h = _resolution_from_megapixels(ratio_preset, megapixels, divisible_by)

        noise = _call_node("RandomNoise", noise_seed=seed)[0]
        guider = _call_node("BasicGuider", model=model, conditioning=conditioning)[0]
        sampler = _call_node("KSamplerSelect", sampler_name=sampler_name)[0]
        sigmas = _call_node("Flux2Scheduler", steps=steps, width=target_w, height=target_h)[0]
        latent_image = _call_node("EmptyFlux2LatentImage", width=target_w, height=target_h, batch_size=batch_size)[0]
        sampled = _call_node(
            "SamplerCustomAdvanced",
            noise=noise,
            guider=guider,
            sampler=sampler,
            sigmas=sigmas,
            latent_image=latent_image,
        )[0]
        image = _call_node("VAEDecode", samples=sampled, vae=vae)[0]
        return (image, sampled, target_w, target_h)


NODE_CLASS_MAPPINGS = {
    "ToobusyFlux2Klein": ToobusyFlux2Klein,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ToobusyFlux2Klein": "toobusy Flux2 Klein",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
