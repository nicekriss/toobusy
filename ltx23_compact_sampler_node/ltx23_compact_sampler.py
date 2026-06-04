import inspect


def _node_class(class_name):
    import nodes

    try:
        return nodes.NODE_CLASS_MAPPINGS[class_name]
    except KeyError as exc:
        raise RuntimeError(
            f"Required ComfyUI node '{class_name}' is not available. "
            "Install/enable the LTXV nodes used by this workflow first."
        ) from exc


def _call_node(class_name, **kwargs):
    cls = _node_class(class_name)
    node = cls()
    fn_name = getattr(cls, "FUNCTION", None)
    if not fn_name:
        raise RuntimeError(f"Node '{class_name}' does not define FUNCTION.")

    fn = getattr(node, fn_name)
    signature = inspect.signature(fn)
    filtered = {key: value for key, value in kwargs.items() if key in signature.parameters}
    return fn(**filtered)


def _sampler_names():
    try:
        input_types = _node_class("KSamplerSelect").INPUT_TYPES()
        return input_types["required"]["sampler_name"][0]
    except Exception:
        return ["res_2s"]


class LTX23CompactAVSampler:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "noise": ("NOISE",),
                "model": ("MODEL",),
                "positive": ("CONDITIONING",),
                "negative": ("CONDITIONING",),
                "latent_image": ("LATENT",),
                "cfg": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 30.0, "step": 0.1}),
                "sampler_name": (_sampler_names(), {"default": "res_2s"}),
                "sigmas": (
                    "STRING",
                    {
                        "default": "1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0",
                        "multiline": False,
                    },
                ),
            }
        }

    RETURN_TYPES = ("CONDITIONING", "CONDITIONING", "LATENT", "LATENT")
    RETURN_NAMES = ("positive", "negative", "video_latent", "audio_latent")
    FUNCTION = "sample"
    CATEGORY = "LTXV/compact"

    def sample(self, noise, model, positive, negative, latent_image, cfg, sampler_name, sigmas):
        guider = _call_node(
            "CFGGuider",
            model=model,
            positive=positive,
            negative=negative,
            cfg=cfg,
        )[0]

        sampler = _call_node("KSamplerSelect", sampler_name=sampler_name)[0]
        sigma_schedule = _call_node("ManualSigmas", sigmas=sigmas)[0]

        sampled_av_latent = _call_node(
            "SamplerCustomAdvanced",
            noise=noise,
            guider=guider,
            sampler=sampler,
            sigmas=sigma_schedule,
            latent_image=latent_image,
        )[0]

        video_latent, audio_latent = _call_node(
            "LTXVSeparateAVLatent",
            av_latent=sampled_av_latent,
        )[:2]

        try:
            cropped_positive, cropped_negative, cropped_video_latent = _call_node(
                "LTXVCropGuides",
                positive=positive,
                negative=negative,
                latent=video_latent,
            )[:3]
            return (cropped_positive, cropped_negative, cropped_video_latent, audio_latent)
        except RuntimeError:
            return (positive, negative, video_latent, audio_latent)


NODE_CLASS_MAPPINGS = {
    "LTX23CompactAVSampler": LTX23CompactAVSampler,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LTX23CompactAVSampler": "LTX2.3 Compact AV Sampler",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
