from .ltx23_compact_sampler import _call_node


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


def _round_to_multiple(value, multiple):
    multiple = max(1, int(multiple))
    return max(multiple, int(round(value / multiple)) * multiple)


def _resolution_from_ratio_megapixels(ratio_preset, megapixels, divisible_by):
    ratio_width, ratio_height = RATIO_PRESETS[ratio_preset]
    aspect = ratio_width / ratio_height
    area = max(0.01, float(megapixels)) * 1_000_000
    width = _round_to_multiple((area * aspect) ** 0.5, divisible_by)
    height = _round_to_multiple((area / aspect) ** 0.5, divisible_by)
    return width, height


def _contains_hangul(text):
    return any("\uac00" <= char <= "\ud7a3" for char in text)


def _quoted_dialogue(text):
    quote_pairs = [("'", "'"), ('"', '"'), ("“", "”"), ("‘", "’"), ("「", "」"), ("『", "』")]
    parts = []

    for open_quote, close_quote in quote_pairs:
        start = 0
        while True:
            left = text.find(open_quote, start)
            if left < 0:
                break
            right = text.find(close_quote, left + len(open_quote))
            if right < 0:
                break
            value = text[left + len(open_quote) : right].strip()
            if value:
                parts.append(value)
            start = right + len(close_quote)

    return "\n".join(parts)


def _recommended_duration_seconds(prompt, language, fallback_duration):
    dialogue = _quoted_dialogue(prompt)
    if not dialogue:
        return float(fallback_duration)

    mode = language
    if mode == "Auto":
        mode = "Korean" if _contains_hangul(dialogue) else "English"

    if mode == "Korean":
        count = len([char for char in dialogue if not char.isspace()])
        speech_seconds = count / 5.5
    else:
        count = len(dialogue.split())
        speech_seconds = count / 2.4

    return round(speech_seconds + 1.0, 1)


def _ltx_length(duration_seconds, frame_rate):
    return max(1, int(round(float(duration_seconds) * float(frame_rate))) + 1)


class LTX23EmptyAVLatents:
    """Folds LTX 2.3 empty audio+video latent setup into one node.

    Replaces EmptyLTXVLatentVideo + LTXVEmptyLatentAudio (and, for custom audio,
    LTXVAudioVAEEncode + SolidMask + SetLatentNoiseMask). Requires the LTX 2.3
    (LTXV*) node set installed.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "audio_vae": ("VAE",),
                "ratio_preset": (list(RATIO_PRESETS.keys()), {"default": "16:9"}),
                "megapixels": ("FLOAT", {"default": 1.0, "min": 0.01, "max": 16.0, "step": 0.01}),
                "divisible_by": ("INT", {"default": 32, "min": 1, "max": 256}),
                "length": ("INT", {"default": 97, "min": 1, "max": 16384}),
                "frame_rate": ("INT", {"default": 24, "min": 1, "max": 120}),
                "batch_size": ("INT", {"default": 1, "min": 1, "max": 4096}),
                "use_custom_audio": ("BOOLEAN", {"default": False}),
            },
            "optional": {
                "audio": ("AUDIO",),
            },
        }

    RETURN_TYPES = ("LATENT", "LATENT", "INT", "INT", "FLOAT", "INT", "INT")
    RETURN_NAMES = (
        "video_latent",
        "audio_latent",
        "length",
        "frame_rate_int",
        "frame_rate_float",
        "width",
        "height",
    )
    FUNCTION = "create"
    CATEGORY = "toobusy/Make"

    def create(
        self,
        audio_vae,
        ratio_preset,
        megapixels,
        divisible_by,
        length,
        frame_rate,
        batch_size,
        use_custom_audio,
        audio=None,
    ):
        frame_rate_int = int(round(frame_rate))
        frame_rate_float = float(frame_rate)
        width, height = _resolution_from_ratio_megapixels(ratio_preset, megapixels, divisible_by)

        video_latent = _call_node(
            "EmptyLTXVLatentVideo",
            width=width,
            height=height,
            length=length,
            batch_size=batch_size,
        )[0]

        audio_latent = _call_node(
            "LTXVEmptyLatentAudio",
            audio_vae=audio_vae,
            frames_number=length,
            frame_rate=frame_rate_int,
            batch_size=batch_size,
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
            length,
            frame_rate_int,
            frame_rate_float,
            width,
            height,
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
                "language": (["Auto", "Korean", "English"], {"default": "Auto"}),
            },
        }

    RETURN_TYPES = ("CONDITIONING", "CONDITIONING", "INT", "FLOAT", "INT")
    RETURN_NAMES = ("positive", "negative", "frame_rate_int", "frame_rate_float", "length")
    FUNCTION = "encode"
    CATEGORY = "toobusy/Make"

    def encode(
        self,
        clip,
        prompt,
        negative_prompt,
        frame_rate,
        duration_seconds,
        language="Auto",
    ):
        frame_rate_int = int(round(frame_rate))
        frame_rate_float = float(frame_rate)
        length = _ltx_length(duration_seconds, frame_rate_float)
        recommended_duration_seconds = _recommended_duration_seconds(prompt, language, duration_seconds)

        positive = _call_node("CLIPTextEncode", text=prompt, clip=clip)[0]
        negative = _call_node("CLIPTextEncode", text=negative_prompt, clip=clip)[0]

        positive, negative = _call_node(
            "LTXVConditioning",
            positive=positive,
            negative=negative,
            frame_rate=frame_rate_float,
        )[:2]

        return {
            "ui": {
                "recommended_duration_seconds": [recommended_duration_seconds],
                "length": [length],
                "frame_rate_float": [frame_rate_float],
                "text": [
                    f"Recommended duration: {recommended_duration_seconds:.1f}s",
                    f"Length: {length} frames @ {frame_rate_float:g} fps",
                ]
            },
            "result": (
                positive,
                negative,
                frame_rate_int,
                frame_rate_float,
                length,
            ),
        }


NODE_CLASS_MAPPINGS = {
    "LTX23EmptyAVLatents": LTX23EmptyAVLatents,
    "LTX23PromptGuide": LTX23PromptGuide,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LTX23EmptyAVLatents": "toobusy LTX2.3 Empty AV Latents",
    "LTX23PromptGuide": "toobusy LTX2.3 Prompt Guide",
}
