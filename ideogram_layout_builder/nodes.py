import json
import re


HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
# Keep in sync with MIN_BOX_SIZE in js/ideogram_layout_builder.js: the UI never
# lets a box get smaller than this, so anything at this size is a real box.
MIN_BOX_SIZE = 40
STYLE_PALETTE_MAX = 16
ELEMENT_PALETTE_MAX = 5
PLACEHOLDER_DESCS = {"", "new layout element", "layout element", "duplicated layout element"}


def _parse_palette(value, fallback=None, limit=ELEMENT_PALETTE_MAX):
    fallback = fallback or []
    if isinstance(value, list):
        colors = value
    elif isinstance(value, str):
        colors = [part.strip() for part in re.split(r"[,\s]+", value) if part.strip()]
    else:
        colors = []

    normalized = []
    seen = set()
    for color in colors:
        if not isinstance(color, str):
            continue
        color = color.strip().upper()
        if HEX_RE.match(color) and color not in seen:
            seen.add(color)
            normalized.append(color)

    result = normalized or list(fallback)
    return result[:limit] if limit else result


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
    if x_max - x_min < MIN_BOX_SIZE:
        x_max = min(1000, x_min + MIN_BOX_SIZE)
    if y_max - y_min < MIN_BOX_SIZE:
        y_max = min(1000, y_min + MIN_BOX_SIZE)
    if x_max - x_min < MIN_BOX_SIZE:
        x_min = max(0, x_max - MIN_BOX_SIZE)
    if y_max - y_min < MIN_BOX_SIZE:
        y_min = max(0, y_max - MIN_BOX_SIZE)
    return [x_min, y_min, x_max, y_max]


def _to_ideogram_bbox(value):
    x_min, y_min, x_max, y_max = _normalize_bbox(value)
    return [y_min, x_min, y_max, x_max]


def _is_placeholder_element(text, desc, bbox):
    width = bbox[2] - bbox[0]
    height = bbox[3] - bbox[1]
    has_content = bool(text) or desc.lower() not in PLACEHOLDER_DESCS
    # A box is "stray" only when it carries no real content AND is tiny in both
    # dimensions (e.g. an accidental click box, or an empty default element that
    # was never positioned). bbox is already grown to MIN_BOX_SIZE by
    # _normalize_bbox, so a described box at the UI minimum is always kept.
    is_tiny = width <= MIN_BOX_SIZE and height <= MIN_BOX_SIZE
    return not has_content and is_tiny


def _build_desc(text, desc):
    if desc.lower() in PLACEHOLDER_DESCS:
        desc = ""
    if text and desc:
        return desc if text.lower() in desc.lower() else f"{desc} Text reads '{text}'."
    if text:
        return f"clean rendered text integrated into the composition, text reads '{text}'"
    return desc or "layout element"


def _element_type(text, desc):
    return "text" if text else "obj"


def _load_elements(elements_json):
    if not elements_json.strip():
        return []
    try:
        data = json.loads(elements_json)
    except (ValueError, TypeError):
        # Malformed JSON (hand-edited or fed from another node) should not abort
        # the whole graph; fall back to "no elements" and let build() emit its
        # default centered subject.
        print("[toobusy ideogram] elements_json is not valid JSON; ignoring it.")
        return []
    if isinstance(data, dict):
        data = data.get("elements", [])
    if not isinstance(data, list):
        print("[toobusy ideogram] elements_json must be a JSON array or an object with an 'elements' array; ignoring it.")
        return []
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
                        "default": "A clean editorial poster with deliberate layout.",
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
    CATEGORY = "toobusy/ideogram"

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
            bbox = _normalize_bbox(item.get("bbox"))
            text = str(item.get("text", "")).strip()
            desc = str(item.get("desc", "")).strip()
            if _is_placeholder_element(text, desc, bbox):
                continue

            element_type = _element_type(text, desc)
            # No fallback: only keep colors the user actually chose. An unset /
            # default palette is omitted so we don't inject a meaningless color
            # hint into every element (it gets overridden by desc anyway).
            palette = _parse_palette(item.get("color_palette"), [], limit=ELEMENT_PALETTE_MAX)
            ideogram_bbox = _to_ideogram_bbox(bbox)

            # Ideogram requires a fixed key order per type:
            #   obj : type -> bbox -> desc -> [color_palette]
            #   text: type -> bbox -> text -> desc -> [color_palette]
            element = {"type": element_type, "bbox": ideogram_bbox}
            if element_type == "text":
                element["text"] = text
            element["desc"] = _build_desc(text, desc)
            if palette:
                element["color_palette"] = palette
            elements.append(element)

        # Order elements roughly top-to-bottom, then left-to-right (reading order),
        # which Ideogram recommends. bbox is [y_min, x_min, y_max, x_max].
        elements.sort(key=lambda el: (el["bbox"][0], el["bbox"][1]))

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
                "color_palette": _parse_palette(
                    global_palette, ["#111111", "#FFFFFF", "#D8C7A3"], limit=STYLE_PALETTE_MAX
                ),
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
    "IdeogramLayoutBuilder": "toobusy Ideogram Layout Builder",
}
