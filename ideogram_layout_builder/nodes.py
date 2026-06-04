import json
import re


HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


def _parse_palette(value, fallback=None):
    fallback = fallback or []
    if isinstance(value, list):
        colors = value
    elif isinstance(value, str):
        colors = [part.strip() for part in re.split(r"[,\s]+", value) if part.strip()]
    else:
        colors = []

    normalized = []
    for color in colors:
        if not isinstance(color, str):
            continue
        color = color.strip().upper()
        if HEX_RE.match(color):
            normalized.append(color)
    return normalized or fallback


def _clamp_int(value, minimum=0, maximum=1000):
    try:
        number = int(round(float(value)))
    except (TypeError, ValueError):
        number = minimum
    return max(minimum, min(maximum, number))


def _normalize_bbox(value):
    if not isinstance(value, list) or len(value) != 4:
        return [100, 100, 900, 900]
    x_min, y_min, x_max, y_max = [_clamp_int(item) for item in value]
    if x_max <= x_min:
        x_max = min(1000, x_min + 1)
    if y_max <= y_min:
        y_max = min(1000, y_min + 1)
    return [x_min, y_min, x_max, y_max]


def _load_elements(elements_json):
    if not elements_json.strip():
        return []
    data = json.loads(elements_json)
    if isinstance(data, dict):
        data = data.get("elements", [])
    if not isinstance(data, list):
        raise ValueError("elements_json must be a JSON array or an object with an elements array.")
    return data


class IdeogramLayoutBuilder:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "high_level_description": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "A clean editorial poster with deliberate layout and readable text.",
                    },
                ),
                "aesthetics": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "clean commercial design, sharp focus, balanced negative space",
                    },
                ),
                "lighting": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "soft studio lighting with gentle shadows",
                    },
                ),
                "photo": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "professional product photography, 85mm lens",
                    },
                ),
                "medium": (
                    "STRING",
                    {
                        "default": "photography",
                    },
                ),
                "global_palette": (
                    "STRING",
                    {
                        "default": "#111111, #FFFFFF, #D8C7A3",
                    },
                ),
                "background": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "minimal studio background with subtle depth and a clean surface",
                    },
                ),
                "elements_json": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "[]",
                    },
                ),
                "width": (
                    "INT",
                    {
                        "default": 1024,
                        "min": 256,
                        "max": 2048,
                        "step": 1,
                    },
                ),
                "height": (
                    "INT",
                    {
                        "default": 1024,
                        "min": 256,
                        "max": 2048,
                        "step": 1,
                    },
                ),
            }
        }

    RETURN_TYPES = ("STRING", "INT", "INT")
    RETURN_NAMES = ("ideogram_json", "width", "height")
    FUNCTION = "build"
    CATEGORY = "drawings/ideogram"

    def build(
        self,
        high_level_description,
        aesthetics,
        lighting,
        photo,
        medium,
        global_palette,
        background,
        elements_json,
        width,
        height,
    ):
        elements = []
        for item in _load_elements(elements_json):
            if not isinstance(item, dict):
                continue
            text = str(item.get("text", "")).strip()
            desc = str(item.get("desc", "")).strip()
            if text and text.lower() not in desc.lower():
                desc = f"{desc} Text reads '{text}'.".strip()
            if not desc:
                desc = f"text reading '{text}'" if text else "layout element"

            elements.append(
                {
                    "type": "obj",
                    "bbox": _normalize_bbox(item.get("bbox")),
                    "desc": desc,
                    "color_palette": _parse_palette(item.get("color_palette"), ["#FFFFFF", "#111111"]),
                }
            )

        if not elements:
            elements.append(
                {
                    "type": "obj",
                    "bbox": [250, 250, 750, 750],
                    "desc": "main subject placed in the center of the composition",
                    "color_palette": ["#FFFFFF", "#111111"],
                }
            )

        payload = {
            "high_level_description": high_level_description.strip(),
            "style_description": {
                "aesthetics": aesthetics.strip(),
                "lighting": lighting.strip(),
                "photo": photo.strip(),
                "medium": medium.strip(),
                "color_palette": _parse_palette(global_palette, ["#111111", "#FFFFFF", "#D8C7A3"]),
            },
            "compositional_deconstruction": {
                "background": background.strip(),
                "elements": elements,
            },
        }

        return (json.dumps(payload, ensure_ascii=False, indent=2), int(width), int(height))


NODE_CLASS_MAPPINGS = {
    "IdeogramLayoutBuilder": IdeogramLayoutBuilder,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "IdeogramLayoutBuilder": "Ideogram Layout Builder",
}
