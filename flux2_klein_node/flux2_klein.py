import math

from ..ltx23_compact_sampler_node.ltx23_compact_sampler import (
    _call_node,
    _default_sampler_name,
    _load_cached,
    _sampler_names,
    _scan_for,
)


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
MAX_REFERENCE_SLOTS = 5


def _folder_list(kind, fallback):
    try:
        import folder_paths

        names = list(folder_paths.get_filename_list(kind))
        return names or fallback
    except Exception:
        return fallback


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


def _connected_image(image):
    if image is None:
        return False
    shape = getattr(image, "shape", None)
    if shape and len(shape) >= 3:
        try:
            return int(shape[1]) > 1 and int(shape[2]) > 1
        except Exception:
            return True
    return True


def _bundle_image(reference_bundle, role):
    if not isinstance(reference_bundle, dict):
        return None
    aliases = {
        "main_character": ("main_character", "character_a"),
        "secondary_character": ("secondary_character", "character_b"),
        "face": ("face", "face_a"),
        "pose": ("pose", "pose_a"),
        "outfit": ("outfit", "outfit_a"),
        "background": ("background", "background_a"),
        "product": ("product", "prop_a"),
    }.get(role, (role,))
    for key in aliases:
        data = reference_bundle.get(key)
        if isinstance(data, dict) and data.get("image") is not None:
            return data.get("image")
    for card in reference_bundle.get("cards", []) if isinstance(reference_bundle.get("cards"), list) else []:
        if isinstance(card, dict) and card.get("role") in aliases and card.get("image") is not None:
            return card.get("image")
    return None


def _bundle_references(reference_bundle, reference_order="standard"):
    # Klein reference slots are an ordered conditioning chain, so map the board
    # roles to a practical default order. Users can still override any slot by
    # wiring the individual reference_N_image inputs.
    order_map = {
        "standard": ("main_character", "secondary_character", "pose", "outfit", "background"),
        "body_first_face_second": ("main_character", "face", "outfit", "pose", "background"),
        "face_first_body_second": ("face", "main_character", "outfit", "pose", "background"),
        "product_swap": ("main_character", "product", "pose", "background"),
        "character_swap": ("main_character", "secondary_character", "pose", "background"),
    }
    ordered_roles = order_map.get(str(reference_order or "standard"), order_map["standard"])
    images = []
    for role in ordered_roles:
        image = _bundle_image(reference_bundle, role)
        if _connected_image(image):
            images.append((role, image))
    return images


# Valid reference orders (besides "auto").
REFERENCE_ORDERS = ("standard", "body_first_face_second", "face_first_body_second", "product_swap", "character_swap")


def _resolve_reference_order(bundle_reference_order, reference_bundle):
    """Resolve the effective reference order.

    "auto" (default) follows the Bundle's ``flags.reference_order`` set by the
    Director FaceSwap button, so clicking FaceSwap upstream drives the order
    without touching this node. Any explicit choice overrides the bundle.
    """
    order = str(bundle_reference_order or "auto")
    if order != "auto":
        return order if order in REFERENCE_ORDERS else "standard"
    flags = reference_bundle.get("flags") if isinstance(reference_bundle, dict) else None
    if isinstance(flags, dict):
        flagged = str(flags.get("reference_order") or "").strip()
        if flagged in REFERENCE_ORDERS:
            return flagged
    return "standard"


def _bundle_prompt(reference_bundle):
    if not isinstance(reference_bundle, dict):
        return ""
    return str(reference_bundle.get("resolved_prompt") or "").strip()


def _bundle_loras(reference_bundle):
    if not isinstance(reference_bundle, dict):
        return []
    loras = []
    for card in reference_bundle.get("cards", []) if isinstance(reference_bundle.get("cards"), list) else []:
        if not isinstance(card, dict):
            continue
        card_type = str(card.get("type") or "").lower()
        role = str(card.get("role") or "").lower()
        if card_type != "lora" and "lora" not in role:
            continue
        name = str(card.get("lora_name") or card.get("name") or card.get("label") or "").strip()
        if not name or name == "None":
            continue
        try:
            strength = float(card.get("strength", card.get("lora_strength", 1.0)))
        except Exception:
            strength = 1.0
        loras.append((name, strength))
    selected = reference_bundle.get("selected_lora_name")
    if selected:
        try:
            strength = float(reference_bundle.get("selected_lora_strength", 1.0))
        except Exception:
            strength = 1.0
        loras.append((str(selected), strength))
    return loras[:MAX_LORA_SLOTS]


def _load_clip(clip_name):
    # Flux2 Klein uses a Qwen3-based text encoder with the "flux2" CLIP type
    # (the source workflow loads it via CLIPLoaderGGUF with type=flux2; the
    # GGUF file itself can flow in through clip_override).
    return _load_cached("CLIPLoader", clip_name=clip_name, type="flux2", device="default")


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
                # Fuzzy auto-detection (shared _scan_for): a fresh node picks
                # the Flux2 Klein files regardless of naming/foldering.
                "model_name": (
                    model_names,
                    {"default": _scan_for(
                        model_names,
                        [("flux2", "klein"), ("flux", "klein"), ("klein",), ("flux2",)],
                        fallback_preferred=["FLUX2/flux-2-klein-9b-kv-fp8.safetensors"],
                    )},
                ),
                "clip_name": (
                    clip_names,
                    {"default": _scan_for(
                        clip_names,
                        [("qwen", "klein"), ("qwen3", "8b"), ("qwen", "8b"), ("qwen",)],
                        fallback_preferred=["flux2/qwen_3_8b_fp8mixed.safetensors"],
                    )},
                ),
                "vae_name": (
                    vae_names,
                    {"default": _scan_for(
                        vae_names,
                        [("flux2", "vae"), ("flux2",), ("flux", "ae")],
                        fallback_preferred=["flux2/flux2-vae.safetensors"],
                    )},
                ),
                "positive": (
                    "STRING",
                    {
                        "default": "shopping mall clothing detail shot, studio product photo, clean white background, mint wide pants, no human",
                        "multiline": True,
                    },
                ),
                "size_mode": (
                    ["from reference", "ratio + megapixels", "manual"],
                    {
                        "default": "from reference",
                        "tooltip": "Where the output size comes from. 'from reference' = match reference #1 (Klein default — ratio/megapixels are ignored while a reference is connected); 'ratio + megapixels' = use the ratio_preset + megapixels below; 'manual' = use width/height.",
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
                "bundle_reference_order": (
                    ["auto", "standard", "body_first_face_second", "face_first_body_second", "product_swap", "character_swap"],
                    {
                        "default": "auto",
                        "tooltip": "How TOOBUSY_BUNDLE cards fill empty reference slots. 'auto' follows the Director swap buttons (flags.reference_order); pick a value to force it.",
                    },
                ),
            },
            "optional": {
                "toobusy_bundle": (
                    "TOOBUSY_BUNDLE",
                    {"tooltip": "Universal toobusy Bundle from Reference Board / Prompt Director. Empty reference slots are filled from bundle roles."},
                ),
                "use_bundle_prompt": (
                    "BOOLEAN",
                    {"default": True, "tooltip": "When enabled, Bundle resolved_prompt replaces the positive text if present."},
                ),
                "use_bundle_loras": (
                    "BOOLEAN",
                    {"default": True, "tooltip": "When enabled and no manual LoRA slot is active, LoRA cards in the Bundle are applied."},
                ),
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
                "model_override": ("MODEL",),
                "clip_override": ("CLIP",),
                "vae_override": ("VAE",),
            },
        }

        optional = base["optional"]
        # Reference image sockets are generated up to MAX_REFERENCE_SLOTS; the
        # JS +/- buttons show `reference_slots` of them. A slot is applied when
        # its image is connected. No per-slot enable flags.
        for slot in range(1, MAX_REFERENCE_SLOTS + 1):
            optional[f"reference_{slot}_image"] = (
                "IMAGE",
                {"tooltip": f"Reference #{slot}. Applied in order in the Klein conditioning chain (reference #1 also drives the default size)."},
            )

        required = base["required"]
        for slot in range(1, MAX_LORA_SLOTS + 1):
            required[f"lora_{slot}_enable"] = ("BOOLEAN", {"default": False})
            required[f"lora_{slot}_name"] = (lora_names, {"default": "None"})
            required[f"lora_{slot}_strength"] = (
                "FLOAT",
                {"default": 1.0, "min": -10.0, "max": 10.0, "step": 0.01},
            )

        return base

    # Passthrough outputs (toobusy convention, same as Z-Image Turbo):
    #   model       — what sampled here (LoRA + Flux KV cache applied)
    #   model_clean — as loaded, before any patching (swap LoRAs externally)
    # plus clip / vae / the encoded positive conditioning, so a Hires Upscale +
    # second sampler pass needs no external loaders. Appended after the
    # original outputs to keep existing link slots.
    RETURN_TYPES = ("IMAGE", "LATENT", "INT", "INT", "MODEL", "MODEL", "CLIP", "VAE", "CONDITIONING")
    RETURN_NAMES = ("image", "latent", "width", "height", "model", "model_clean", "clip", "vae", "positive")
    FUNCTION = "generate"
    CATEGORY = "toobusy/Make"

    def generate(
        self,
        model_name,
        clip_name,
        vae_name,
        positive,
        size_mode,
        ratio_preset,
        megapixels,
        divisible_by,
        batch_size,
        seed,
        steps,
        sampler_name,
        lora_slots,
        reference_slots,
        bundle_reference_order,
        width=0,
        height=0,
        toobusy_bundle=None,
        use_bundle_prompt=True,
        use_bundle_loras=True,
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
            model = _load_cached("UNETLoader", unet_name=model_name, weight_dtype="default")

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
            vae = _load_cached("VAELoader", vae_name=vae_name)

        bundle_prompt = _bundle_prompt(toobusy_bundle)
        if use_bundle_prompt and bundle_prompt:
            positive = bundle_prompt
            print("[toobusy Flux2 Klein] Using resolved_prompt from TOOBUSY_BUNDLE.")

        lora_slots = max(0, min(MAX_LORA_SLOTS, int(lora_slots)))
        manual_lora_active = False
        if use_bundle_loras:
            for slot in range(1, lora_slots + 1):
                if slot_kwargs.get(f"lora_{slot}_enable", False) and slot_kwargs.get(f"lora_{slot}_name", "None") != "None":
                    manual_lora_active = True
                    break
            if not manual_lora_active:
                for index, (lora_name, lora_strength) in enumerate(_bundle_loras(toobusy_bundle), start=1):
                    model, clip = _call_node(
                        "LoraLoader",
                        model=model,
                        clip=clip,
                        lora_name=lora_name,
                        strength_model=lora_strength,
                        strength_clip=lora_strength,
                    )
                    print(f"[toobusy Flux2 Klein] Bundle LoRA {index} applied: {lora_name} @ {lora_strength}")

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

        # Clean passthrough: the model as loaded, before LoRA / KV cache.
        model_clean = model

        model = _call_node("FluxKVCache", model=model)[0]
        conditioning = _call_node("CLIPTextEncode", clip=clip, text=positive)[0]

        # Reference conditioning. The source workflow's per-reference subgraph
        # is ImageScaleToTotalPixels (lanczos, 1MP) -> VAEEncode ->
        # ReferenceLatent, chained on the conditioning — all core nodes.
        reference_slots = max(0, min(MAX_REFERENCE_SLOTS, int(reference_slots)))
        active_bundle = toobusy_bundle
        references = {
            slot: slot_kwargs.get(f"reference_{slot}_image")
            for slot in range(1, MAX_REFERENCE_SLOTS + 1)
        }
        effective_reference_order = _resolve_reference_order(bundle_reference_order, active_bundle)
        bundle_refs = _bundle_references(active_bundle, effective_reference_order)
        bundle_index = 0
        for slot in range(1, MAX_REFERENCE_SLOTS + 1):
            if _connected_image(references.get(slot)):
                if bundle_index < len(bundle_refs):
                    bundle_index += 1
                continue
            if bundle_index >= len(bundle_refs):
                break
            role, image = bundle_refs[bundle_index]
            references[slot] = image
            bundle_index += 1
            print(f"[toobusy Flux2 Klein] Reference #{slot} filled from bundle role: {role}.")
        first_active_image = None

        for slot in range(1, reference_slots + 1):
            image = references.get(slot)
            if not _connected_image(image):
                print(f"[toobusy Flux2 Klein] Reference #{slot} has no IMAGE connected; skipped.")
                continue
            if first_active_image is None:
                first_active_image = image

            scaled = _call_node(
                "ImageScaleToTotalPixels",
                image=image,
                upscale_method="lanczos",
                megapixels=1.0,
            )[0]
            reference_latent = _call_node("VAEEncode", pixels=scaled, vae=vae)[0]
            conditioning = _call_node(
                "ReferenceLatent",
                conditioning=conditioning,
                latent=reference_latent,
            )[0]
            print(f"[toobusy Flux2 Klein] Reference #{slot} applied.")

        # Output size comes from one of three explicit sources (size_mode), so
        # a connected reference never silently overrides the ratio/megapixels.
        size_mode = str(size_mode)
        ratio_size = _resolution_from_megapixels(ratio_preset, megapixels, divisible_by)
        manual_size = None
        if int(width) > 0 and int(height) > 0:
            manual_size = (_round_to(int(width), divisible_by), _round_to(int(height), divisible_by))

        if size_mode == "manual":
            if manual_size is not None:
                target_w, target_h = manual_size
            else:
                target_w, target_h = ratio_size
                print("[toobusy Flux2 Klein] size_mode=manual but width/height are 0 — using ratio + megapixels.")
        elif size_mode == "ratio + megapixels":
            target_w, target_h = ratio_size
        else:  # "from reference"
            ref_w, ref_h = _image_dims(first_active_image) if first_active_image is not None else (0, 0)
            if ref_w > 0 and ref_h > 0:
                target_w, target_h = ref_w, ref_h
            else:
                target_w, target_h = ratio_size
                print("[toobusy Flux2 Klein] size_mode=from reference but no reference connected — using ratio + megapixels.")

        print(f"[toobusy Flux2 Klein] Output size {target_w}x{target_h} (size_mode: {size_mode}).")

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
        return (image, sampled, target_w, target_h, model, model_clean, clip, vae, conditioning)


NODE_CLASS_MAPPINGS = {
    "ToobusyFlux2Klein": ToobusyFlux2Klein,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ToobusyFlux2Klein": "toobusy Flux2 Klein",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
