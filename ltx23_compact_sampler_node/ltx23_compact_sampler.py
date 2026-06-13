import inspect


def _node_class(class_name):
    import nodes

    try:
        return nodes.NODE_CLASS_MAPPINGS[class_name]
    except KeyError as exc:
        raise RuntimeError(
            f"Required ComfyUI node '{class_name}' is not available. "
            "This toobusy fold calls it internally — install/enable the node "
            "pack (or update ComfyUI) that provides it."
        ) from exc


def _first_existing(names, preferred):
    for name in preferred:
        if name in names:
            return name
    return names[0]


def _normalized(name):
    """Lowercased, separator-free view for fuzzy matching: 'ZIT\\Z-Image_Turbo'
    and 'z_image_turbo' both become 'zitzimageturbo'."""
    return name.lower().replace("-", "").replace("_", "").replace(" ", "")


def _scan_for(names, keyword_groups, fallback_preferred=()):
    """First name matching the earliest keyword group (all keywords of a group
    must appear in the normalized name). Groups are ordered best-first, so a
    'zimage turbo' file beats a plain 'zimage' one. Falls back to exact
    preferred names, then to the folder's first entry. Shared by every fold
    that auto-detects its default model files."""
    normalized = [(name, _normalized(name)) for name in names]
    for keywords in keyword_groups:
        for name, key in normalized:
            if all(keyword in key for keyword in keywords):
                return name
    return _first_existing(names, fallback_preferred)


def _fill_input_defaults(cls, kwargs, params, has_var_keyword):
    """Add INPUT_TYPES defaults for declared inputs the caller didn't pass.

    The graph executor does this from the node schema before calling a node;
    when we call a node class directly we must do the same, otherwise a core
    update that adds a new widget (e.g. ImageScaleToTotalPixels growing a
    required `resolution_steps`) breaks every fold that calls it. V3 nodes
    are the sharp edge: their `execute` has no Python defaults for schema
    inputs, so a missing kwarg is a hard TypeError.
    """
    try:
        spec = cls.INPUT_TYPES()
    except Exception:
        return kwargs
    if not isinstance(spec, dict):
        return kwargs
    for section in ("required", "optional"):
        for name, definition in (spec.get(section) or {}).items():
            if name in kwargs:
                continue
            if not has_var_keyword and params is not None and name not in params:
                continue
            if not isinstance(definition, (list, tuple)) or not definition:
                continue
            options = definition[1] if len(definition) > 1 else None
            if isinstance(options, dict) and "default" in options:
                kwargs[name] = options["default"]
            elif isinstance(definition[0], (list, tuple)) and definition[0]:
                # Combo without an explicit default: first entry, like the UI.
                kwargs[name] = definition[0][0]
    return kwargs


def _call_node(class_name, **kwargs):
    cls = _node_class(class_name)
    node = cls()
    fn_name = getattr(cls, "FUNCTION", None)
    if not fn_name:
        raise RuntimeError(f"Node '{class_name}' does not define FUNCTION.")

    fn = getattr(node, fn_name)
    signature = inspect.signature(fn)
    has_var_keyword = any(
        param.kind == inspect.Parameter.VAR_KEYWORD for param in signature.parameters.values()
    )

    # V3 io.ComfyNode classes expose FUNCTION as a *args/**kwargs normalizer;
    # the real parameter list lives on `execute`.
    params = None if has_var_keyword else signature.parameters
    if has_var_keyword and hasattr(cls, "execute"):
        try:
            execute_params = inspect.signature(cls.execute).parameters
            if not any(p.kind == inspect.Parameter.VAR_KEYWORD for p in execute_params.values()):
                params = execute_params
                has_var_keyword = False
        except (TypeError, ValueError):
            pass

    kwargs = _fill_input_defaults(cls, dict(kwargs), params, has_var_keyword)
    if has_var_keyword or params is None:
        return _unwrap_result(fn(**kwargs))

    filtered = {key: value for key, value in kwargs.items() if key in params}
    return _unwrap_result(fn(**filtered))


def _unwrap_result(result):
    """Normalize a node's return into the plain output tuple.

    Nodes with a preview/UI (e.g. comfyui_controlnet_aux preprocessors,
    PreviewImage) return ``{"ui": {...}, "result": (...)}`` instead of a bare
    tuple — indexing that dict with ``[0]`` raised ``KeyError: 0``. V3
    io.ComfyNode classes return a NodeOutput whose values live in ``.args``."""
    args = getattr(result, "args", None)
    if args is not None:
        return tuple(args)
    if isinstance(result, dict):
        return tuple(result.get("result", ()))
    return result


def _sampler_names():
    try:
        import comfy.samplers

        names = list(comfy.samplers.KSampler.SAMPLERS)
        if names:
            return names
    except Exception:
        pass

    try:
        input_types = _node_class("KSamplerSelect").INPUT_TYPES()
        sampler_spec = input_types["required"]["sampler_name"][0]
        if not isinstance(sampler_spec, str):
            names = list(sampler_spec)
            if names:
                return names
    except Exception:
        pass

    return ["euler", "euler_cfg_pp", "euler_ancestral", "euler_ancestral_cfg_pp"]


def _default_sampler_name(sampler_names):
    return "res_2s" if "res_2s" in sampler_names else sampler_names[0]


class LTX23CompactAVSampler:
    """Folds the LTX 2.3 audio+video sampling block into one node.

    Replaces: RandomNoise + LTXVConcatAVLatent + CFGGuider + KSamplerSelect +
    ManualSigmas + SamplerCustomAdvanced + LTXVSeparateAVLatent + LTXVCropGuides
    (8 nodes -> 1). Requires the LTX 2.3 (LTXV*) node set installed.
    """

    @classmethod
    def INPUT_TYPES(cls):
        sampler_names = _sampler_names()
        return {
            "required": {
                "model": ("MODEL",),
                "positive": ("CONDITIONING",),
                "negative": ("CONDITIONING",),
                "video_latent": ("LATENT",),
                "audio_latent": ("LATENT",),
                "seed": (
                    "INT",
                    {
                        "default": 42,
                        "min": 0,
                        "max": 0xffffffffffffffff,
                        "control_after_generate": True,
                    },
                ),
                "cfg": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 30.0, "step": 0.1}),
                "sampler_name": (sampler_names, {"default": _default_sampler_name(sampler_names)}),
                "manual_sigmas": (
                    "STRING",
                    {
                        "default": "1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0",
                        "multiline": False,
                    },
                ),
            },
            "optional": {
                "sigmas": ("SIGMAS",),
            },
        }

    RETURN_TYPES = ("CONDITIONING", "CONDITIONING", "LATENT", "LATENT")
    RETURN_NAMES = ("positive", "negative", "video_latent", "audio_latent")
    FUNCTION = "sample"
    CATEGORY = "toobusy/Make"

    def sample(
        self,
        model,
        positive,
        negative,
        video_latent,
        audio_latent,
        seed,
        cfg,
        sampler_name,
        manual_sigmas,
        sigmas=None,
    ):
        noise = _call_node("RandomNoise", noise_seed=seed)[0]
        av_latent = _call_node(
            "LTXVConcatAVLatent",
            video_latent=video_latent,
            audio_latent=audio_latent,
        )[0]

        guider = _call_node(
            "CFGGuider",
            model=model,
            positive=positive,
            negative=negative,
            cfg=cfg,
        )[0]

        sampler = _call_node("KSamplerSelect", sampler_name=sampler_name)[0]
        sigma_schedule = sigmas if sigmas is not None else _call_node("ManualSigmas", sigmas=manual_sigmas)[0]

        sampled_av_latent = _call_node(
            "SamplerCustomAdvanced",
            noise=noise,
            guider=guider,
            sampler=sampler,
            sigmas=sigma_schedule,
            latent_image=av_latent,
        )[0]

        video_latent, audio_latent = _call_node(
            "LTXVSeparateAVLatent",
            av_latent=sampled_av_latent,
        )[:2]

        cropped_positive, cropped_negative, cropped_video_latent = _call_node(
            "LTXVCropGuides",
            positive=positive,
            negative=negative,
            latent=video_latent,
        )[:3]
        return (cropped_positive, cropped_negative, cropped_video_latent, audio_latent)


NODE_CLASS_MAPPINGS = {
    "LTX23CompactAVSampler": LTX23CompactAVSampler,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LTX23CompactAVSampler": "toobusy LTX2.3 Compact AV Sampler",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
