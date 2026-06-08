import json
import re


HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
# Keep in sync with MIN_BOX_SIZE in js/ideogram_layout_builder.js: the UI never
# lets a box get smaller than this, so anything at this size is a real box.
MIN_BOX_SIZE = 40
STYLE_PALETTE_MAX = 16
ELEMENT_PALETTE_MAX = 5
PLACEHOLDER_DESCS = {"", "new layout element", "layout element", "duplicated layout element"}

# Optional role hint appended to an element's description. Keep keys in sync with
# ROLE_PRESETS in js/ideogram_layout_builder.js.
ROLE_HINTS = {
    "headline": "large bold headline typography, dominant in the layout",
    "subtitle": "secondary subtitle text, smaller than the headline",
    "body": "body copy, evenly spaced and comfortably readable",
    "footer": "small footer text near the edge of the composition",
    "product label": "label text printed on the product surface",
    "sign": "sign text, legible despite perspective and reflections",
    "ui label": "small UI label text, crisp and precisely aligned",
    "logo": "logo / wordmark, clean and balanced",
}

# Appended to text elements when strict_text is on, to push faithful rendering.
STRICT_TEXT_HINTS = (
    "spelled exactly as written, sharp and readable, no extra or missing "
    "letters, preserve capitalization and punctuation"
)


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


def _build_desc(text, desc, role="", strict_text=False, reinforce_text=True):
    if desc.lower() in PLACEHOLDER_DESCS:
        desc = ""
    role_hint = ROLE_HINTS.get(role.strip().lower(), "") if role else ""

    if not text:
        # Object element: description plus an optional role hint (e.g. a logo
        # placed as an object rather than literal text).
        clauses = [c for c in (desc, role_hint) if c]
        return ". ".join(clauses) if clauses else "layout element"

    # Text element.
    clauses = []
    if desc and text.lower() in desc.lower():
        # The user already wrote the literal text into the description; trust it
        # and only layer on the role hint.
        clauses.append(desc)
        if role_hint:
            clauses.append(role_hint)
    else:
        if desc:
            clauses.append(desc)
        if role_hint:
            clauses.append(role_hint)
        if reinforce_text:
            clauses.append(f"text reads '{text}'")
    if not clauses:
        base = "clean rendered text integrated into the composition"
        if reinforce_text:
            base += f", text reads '{text}'"
        clauses.append(base)
    if strict_text:
        clauses.append(STRICT_TEXT_HINTS)
    return ". ".join(clauses)


def _element_type(text, desc):
    return "text" if text else "obj"


def _from_ideogram_element(element):
    # A full Ideogram payload (e.g. from Prompt Polish) stores bbox in Ideogram
    # order [y_min, x_min, y_max, x_max]; the builder works in canvas order
    # [x_min, y_min, x_max, y_max], so swap it back when ingesting one.
    if not isinstance(element, dict):
        return element
    bbox = element.get("bbox")
    if isinstance(bbox, list) and len(bbox) == 4:
        y_min, x_min, y_max, x_max = bbox
        return {**element, "bbox": [x_min, y_min, x_max, y_max]}
    return element


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
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        # Plain {"elements": [...]} (already canvas-order bbox).
        if isinstance(data.get("elements"), list):
            return data["elements"]
        # Full Ideogram payload (e.g. piped from Prompt Polish): pull the elements
        # out of compositional_deconstruction and convert bbox order back.
        comp = data.get("compositional_deconstruction")
        if isinstance(comp, dict) and isinstance(comp.get("elements"), list):
            return [_from_ideogram_element(item) for item in comp["elements"]]
    print("[toobusy ideogram] elements_json must be a JSON array, an object with an 'elements' array, or a full Ideogram payload; ignoring it.")
    return []


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
                "include_global_palette": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "label_on": "use global palette",
                        "label_off": "omit global palette",
                    },
                ),
                "strict_text": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "label_on": "strict text rendering",
                        "label_off": "relaxed text",
                    },
                ),
                "reinforce_text": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "label_on": "reinforce text (reads '...')",
                        "label_off": "compact JSON",
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
                        "default": 2048,
                        "min": 256,
                        "max": 2048,
                        "step": 1,
                    },
                ),
                "height": (
                    "INT",
                    {
                        "default": 2048,
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
    CATEGORY = "toobusy/Plan"

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
        include_global_palette=True,
        strict_text=True,
        reinforce_text=True,
    ):
        elements = []
        for item in _load_elements(elements_json):
            if not isinstance(item, dict):
                continue
            bbox = _normalize_bbox(item.get("bbox"))
            text = str(item.get("text", "")).strip()
            desc = str(item.get("desc", "")).strip()
            role = str(item.get("role", "")).strip()
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
            element["desc"] = _build_desc(
                text, desc, role=role, strict_text=strict_text, reinforce_text=reinforce_text
            )
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

        style_description = {
            "aesthetics": aesthetics.strip(),
            "lighting": lighting.strip(),
            "photo": photo.strip(),
            "medium": medium.strip(),
        }
        # Only attach a global color_palette when the user opted in. Omitting it
        # lets color conditioning be left intentionally open (color_palette is
        # the last key, so dropping it keeps the documented key order intact).
        if include_global_palette:
            style_description["color_palette"] = _parse_palette(
                global_palette, ["#111111", "#FFFFFF", "#D8C7A3"], limit=STYLE_PALETTE_MAX
            )

        payload = {
            "high_level_description": high_level_description.strip(),
            "style_description": style_description,
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
