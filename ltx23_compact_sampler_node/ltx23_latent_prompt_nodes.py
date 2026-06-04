from .ltx23_compact_sampler import _call_node


def _frame_counts(duration_seconds, frame_rate, add_terminal_frame=True):
    frame_count = max(1, int(round(float(duration_seconds) * float(frame_rate))))
    latent_frame_count = frame_count + 1 if add_terminal_frame else frame_count
    return frame_count, latent_frame_count


class LTX23EmptyAVLatents:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "audio_vae": ("VAE",),
                "width": ("INT", {"default": 768, "min": 16, "max": 8192, "step": 16}),
                "height": ("INT", {"default": 512, "min": 16, "max": 8192, "step": 16}),
                "duration_seconds": ("FLOAT", {"default": 4.0, "min": 0.1, "max": 600.0, "step": 0.1}),
                "frame_rate": ("FLOAT", {"default": 24.0, "min": 1.0, "max": 120.0, "step": 0.01}),
                "batch_size": ("INT", {"default": 1, "min": 1, "max": 4096}),
                "add_terminal_frame": ("BOOLEAN", {"default": True}),
                "use_custom_audio": ("BOOLEAN", {"default": False}),
            },
            "optional": {
                "audio": ("AUDIO",),
            },
        }

    RETURN_TYPES = ("LATENT", "LATENT", "INT", "INT", "INT", "FLOAT")
    RETURN_NAMES = (
        "video_latent",
        "audio_latent",
        "frame_count",
        "latent_frame_count",
        "frame_rate_int",
        "frame_rate_float",
    )
    FUNCTION = "create"
    CATEGORY = "LTXV/compact"

    def create(
        self,
        audio_vae,
        width,
        height,
        duration_seconds,
        frame_rate,
        batch_size,
        add_terminal_frame,
        use_custom_audio,
        audio=None,
    ):
        frame_rate_int = int(round(frame_rate))
        frame_rate_float = float(frame_rate)
        frame_count, latent_frame_count = _frame_counts(duration_seconds, frame_rate_float, add_terminal_frame)

        video_latent = _call_node(
            "EmptyLTXVLatentVideo",
            width=width,
            height=height,
            length=latent_frame_count,
            batch_size=batch_size,
        )[0]

        audio_latent = _call_node(
            "LTXVEmptyLatentAudio",
            audio_vae=audio_vae,
            frames_number=latent_frame_count,
            frame_rate=frame_rate_int,
        )[0]

        if use_custom_audio:
            if audio is None:
                raise RuntimeError("Connect an AUDIO input or turn off use_custom_audio.")

            audio_latent = _call_node(
                "LTXVAudioVAEEncode",
                audio=audio,
                audio_vae=audio_vae,
            )[0]
            mask = _call_node(
                "SolidMask",
                value=0.0,
                width=width,
                height=height,
            )[0]
            audio_latent = _call_node(
                "SetLatentNoiseMask",
                samples=audio_latent,
                mask=mask,
            )[0]

        return (
            video_latent,
            audio_latent,
            frame_count,
            latent_frame_count,
            frame_rate_int,
            frame_rate_float,
        )


class LTX23PromptGuide:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "clip": ("CLIP",),
                "prompt": ("STRING", {"default": "", "multiline": True}),
                "negative_prompt": (
                    "STRING",
                    {
                        "default": "pc game, console game, video game, cartoon, childish, ugly, text, subtitles, caption, overlay effect",
                        "multiline": True,
                    },
                ),
                "frame_rate": ("FLOAT", {"default": 24.0, "min": 1.0, "max": 120.0, "step": 0.01}),
                "duration_seconds": ("FLOAT", {"default": 4.0, "min": 0.1, "max": 600.0, "step": 0.1}),
                "add_terminal_frame": ("BOOLEAN", {"default": True}),
                "language": (["Auto", "Korean", "English"], {"default": "Auto"}),
            },
        }

    RETURN_TYPES = ("CONDITIONING", "CONDITIONING", "INT", "FLOAT", "INT", "INT")
    RETURN_NAMES = (
        "positive",
        "negative",
        "frame_rate_int",
        "frame_rate_float",
        "frame_count",
        "latent_frame_count",
    )
    FUNCTION = "encode"
    CATEGORY = "LTXV/compact"

    def encode(
        self,
        clip,
        prompt,
        negative_prompt,
        frame_rate,
        duration_seconds,
        add_terminal_frame,
        language="Auto",
    ):
        del language

        frame_rate_int = int(round(frame_rate))
        frame_rate_float = float(frame_rate)
        frame_count, latent_frame_count = _frame_counts(duration_seconds, frame_rate_float, add_terminal_frame)

        positive = _call_node("CLIPTextEncode", text=prompt, clip=clip)[0]
        negative = _call_node("CLIPTextEncode", text=negative_prompt, clip=clip)[0]

        positive, negative = _call_node(
            "LTXVConditioning",
            positive=positive,
            negative=negative,
            frame_rate=frame_rate_float,
        )[:2]

        return (
            positive,
            negative,
            frame_rate_int,
            frame_rate_float,
            frame_count,
            latent_frame_count,
        )


NODE_CLASS_MAPPINGS = {
    "LTX23EmptyAVLatents": LTX23EmptyAVLatents,
    "LTX23PromptGuide": LTX23PromptGuide,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LTX23EmptyAVLatents": "LTX2.3 Empty AV Latents",
    "LTX23PromptGuide": "LTX2.3 Prompt Guide",
}
