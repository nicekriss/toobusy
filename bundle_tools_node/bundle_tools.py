import json


IMAGE_ROLE_ALIASES = {
    "character_a": ("character_a", "main_character"),
    "character_b": ("character_b", "secondary_character"),
    "face_a": ("face_a", "face"),
    "outfit_a": ("outfit_a", "outfit"),
    "pose_a": ("pose_a", "pose"),
    "background_a": ("background_a", "background"),
    "style_a": ("style_a", "style"),
    "prop_a": ("prop_a", "product"),
}

AUDIO_ROLE_ALIASES = {
    "audio_a": ("audio_a", "audio_1"),
    "audio_b": ("audio_b", "audio_2"),
}


def _blank_image():
    try:
        import torch

        return torch.zeros((1, 1, 1, 3), dtype=torch.float32)
    except Exception:
        return None


def _blank_audio(sample_rate=44100):
    try:
        import torch

        return {"waveform": torch.zeros((1, 1, 0), dtype=torch.float32), "sample_rate": int(sample_rate)}
    except Exception:
        return {"waveform": None, "sample_rate": int(sample_rate)}


def _cards(bundle):
    if not isinstance(bundle, dict):
        return []
    cards = bundle.get("cards")
    return cards if isinstance(cards, list) else []


def _payload(bundle, role, key):
    if not isinstance(bundle, dict):
        return None
    aliases = IMAGE_ROLE_ALIASES.get(role) or AUDIO_ROLE_ALIASES.get(role) or (role,)
    for alias in aliases:
        data = bundle.get(alias)
        if isinstance(data, dict) and data.get(key) is not None:
            return data.get(key)
    for card in _cards(bundle):
        if isinstance(card, dict) and card.get("role") in aliases and card.get(key) is not None:
            return card.get(key)
    return None


def _audio_duration(audio):
    try:
        waveform = audio.get("waveform")
        sample_rate = int(audio.get("sample_rate") or 44100)
        samples = int(waveform.shape[-1])
        return float(samples) / float(sample_rate) if sample_rate > 0 else 0.0
    except Exception:
        return 0.0


def _first_lora(bundle):
    for card in _cards(bundle):
        if not isinstance(card, dict):
            continue
        card_type = str(card.get("type") or "").lower()
        role = str(card.get("role") or "").lower()
        if card_type != "lora" and "lora" not in role:
            continue
        if card.get("enabled") is False:
            continue
        name = str(card.get("lora_name") or card.get("name") or card.get("label") or "").strip()
        if not name or name == "None":
            continue
        try:
            strength = float(card.get("strength", card.get("lora_strength", 1.0)))
        except Exception:
            strength = 1.0
        return name, strength
    selected = bundle.get("selected_lora_name") if isinstance(bundle, dict) else None
    if selected:
        try:
            strength = float(bundle.get("selected_lora_strength", 1.0))
        except Exception:
            strength = 1.0
        return str(selected), strength
    return "", 0.0


class ToobusyBundleUnpack:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "toobusy_bundle": ("TOOBUSY_BUNDLE",),
            },
        }

    RETURN_TYPES = (
        "IMAGE",
        "IMAGE",
        "IMAGE",
        "IMAGE",
        "IMAGE",
        "IMAGE",
        "IMAGE",
        "IMAGE",
        "AUDIO",
        "AUDIO",
        "FLOAT",
        "FLOAT",
        "STRING",
        "STRING",
        "STRING",
        "FLOAT",
        "STRING",
    )
    RETURN_NAMES = (
        "character_a_image",
        "character_b_image",
        "face_a_image",
        "outfit_a_image",
        "pose_a_image",
        "background_a_image",
        "style_a_image",
        "prop_a_image",
        "audio_a",
        "audio_b",
        "audio_a_duration",
        "audio_b_duration",
        "resolved_prompt",
        "negative_prompt",
        "selected_lora_name",
        "selected_lora_strength",
        "debug_json",
    )
    FUNCTION = "unpack"
    CATEGORY = "toobusy/Plan"

    def unpack(self, toobusy_bundle):
        # NOTE: use explicit None checks, never `payload or blank` — a real Comfy
        # IMAGE is a multi-element torch tensor and `bool(tensor)` raises
        # "Boolean value of Tensor with more than one element is ambiguous".
        images = []
        for role in (
            "character_a",
            "character_b",
            "face_a",
            "outfit_a",
            "pose_a",
            "background_a",
            "style_a",
            "prop_a",
        ):
            payload = _payload(toobusy_bundle, role, "image")
            images.append(payload if payload is not None else _blank_image())
        audio_a = _payload(toobusy_bundle, "audio_a", "audio")
        audio_a = audio_a if audio_a is not None else _blank_audio()
        audio_b = _payload(toobusy_bundle, "audio_b", "audio")
        audio_b = audio_b if audio_b is not None else _blank_audio()
        lora_name, lora_strength = _first_lora(toobusy_bundle)
        debug = {
            "version": int(toobusy_bundle.get("version") or 1) if isinstance(toobusy_bundle, dict) else 1,
            "card_count": len(_cards(toobusy_bundle)),
            "resolved_prompt": str(toobusy_bundle.get("resolved_prompt") or "") if isinstance(toobusy_bundle, dict) else "",
            "selected_lora_name": lora_name,
        }
        return (
            *images,
            audio_a,
            audio_b,
            float(_audio_duration(audio_a)),
            float(_audio_duration(audio_b)),
            str(toobusy_bundle.get("resolved_prompt") or "") if isinstance(toobusy_bundle, dict) else "",
            str(toobusy_bundle.get("negative_prompt") or "") if isinstance(toobusy_bundle, dict) else "",
            lora_name,
            float(lora_strength),
            json.dumps(debug, ensure_ascii=False, indent=2),
        )


# All image roles a board card can hold. The JS narrows this combo to the roles
# actually registered in the connected Reference Board.
BUNDLE_GET_ROLES = [
    "character_a",
    "character_b",
    "character_c",
    "character_d",
    "face_a",
    "face_b",
    "outfit_a",
    "outfit_b",
    "pose_a",
    "background_a",
    "style_a",
    "prop_a",
    "main_character",
    "secondary_character",
    "pose",
    "outfit",
    "background",
    "style",
    "product",
]


class ToobusyBundleGet:
    """Pull a single card's image from the Bundle by role (no socket wall)."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "toobusy_bundle": ("TOOBUSY_BUNDLE",),
                "role": (BUNDLE_GET_ROLES, {"default": "character_a"}),
            },
        }

    RETURN_TYPES = ("IMAGE", "STRING", "STRING")
    RETURN_NAMES = ("image", "role", "note")
    FUNCTION = "get"
    CATEGORY = "toobusy/Plan"

    def get(self, toobusy_bundle, role):
        payload = _payload(toobusy_bundle, role, "image")
        image = payload if payload is not None else _blank_image()
        note = _payload(toobusy_bundle, role, "note")
        if note is None:
            note = _payload(toobusy_bundle, role, "prompt")
        return (image, str(role), str(note or ""))


NODE_CLASS_MAPPINGS = {
    "ToobusyBundleUnpack": ToobusyBundleUnpack,
    "ToobusyBundleGet": ToobusyBundleGet,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ToobusyBundleUnpack": "toobusy Bundle Unpack",
    "ToobusyBundleGet": "toobusy Bundle Get",
}
