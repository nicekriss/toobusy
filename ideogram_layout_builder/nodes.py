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


def _has_hangul(value):
    for char in str(value or ""):
        code = ord(char)
        if 0xAC00 <= code <= 0xD7A3 or 0x1100 <= code <= 0x11FF or 0x3130 <= code <= 0x318F:
            return True
    return False


def _is_ascii_label_char(char):
    return char.isascii() and (char.isalnum() or char in ".+-_:/")


def _char_width_weight(char):
    if _has_hangul(char):
        return 1.0
    if char.isspace():
        return 0.35
    if char.isascii() and char.isalnum():
        return 0.62
    return 0.35


def _clean_split_run(text, keep):
    value = str(text or "")
    if keep == "gen":
        value = re.sub(r"\([^A-Za-z0-9]*\)", "", value)
        value = value.strip(" -_:/|()[]")
    else:
        value = re.sub(r"\(\s*([^)]+?)\s*\)", r"\1", value)
        value = value.strip(" -_:/|()[]")
    return re.sub(r"\s+", " ", value).strip()


def _join_split_text(left, right):
    if not left:
        return right
    if not right:
        return left
    if _has_hangul(left[-1]) and right[0].isdigit():
        return f"{left} {right}"
    if left[-1].isdigit() and _has_hangul(right[0]):
        return f"{left}{right}"
    if left[-1].isascii() and left[-1].isalnum() and right[0].isascii() and right[0].isalnum():
        return f"{left} {right}"
    return f"{left}{right}"


def _merge_adjacent_runs(runs):
    merged = []
    for run in runs:
        if merged and merged[-1]["kind"] == run["kind"]:
            merged[-1]["text"] = _join_split_text(merged[-1]["text"], run["text"])
            merged[-1]["bbox"][2] = max(merged[-1]["bbox"][2], run["bbox"][2])
            merged[-1]["bbox"][3] = max(merged[-1]["bbox"][3], run["bbox"][3])
        else:
            merged.append(dict(run))
    return merged


def _split_axis(text, bbox):
    y_min, x_min, y_max, x_max = _normalize_bbox(bbox)
    width = max(1, x_max - x_min)
    height = max(1, y_max - y_min)
    if "\n" in str(text or ""):
        return "y"
    if width / height >= 2.1 and height >= 180 and len(str(text or "")) >= 18:
        return "y"
    return "x"


def _run_bbox(axis, y_min, x_min, y_max, x_max, start, end):
    if axis == "y":
        run_y0 = _clamp_int(start)
        run_y1 = _clamp_int(end)
        if run_y1 - run_y0 < MIN_BOX_SIZE:
            run_y1 = min(1000, run_y0 + MIN_BOX_SIZE)
        return [run_y0, x_min, run_y1, x_max]
    run_x0 = _clamp_int(start)
    run_x1 = _clamp_int(end)
    if run_x1 - run_x0 < MIN_BOX_SIZE:
        run_x1 = min(1000, run_x0 + MIN_BOX_SIZE)
    return [y_min, run_x0, y_max, run_x1]


def _split_mixed_hangul_runs(text, bbox):
    """Split a mixed label into approximate sub-bboxes.

    The layout JSON only gives one bbox for a full text string. When a label
    mixes English/product text and Hangul, estimate horizontal or vertical
    sub-boxes so generation can keep the English part while overlay receives
    only Hangul.
    """
    original = str(text or "").strip()
    if not _has_hangul(original):
        return []

    y_min, x_min, y_max, x_max = _normalize_bbox(bbox)
    axis = _split_axis(original, bbox)
    span_start = y_min if axis == "y" else x_min
    span_end = y_max if axis == "y" else x_max
    total_span = max(1, span_end - span_start)
    total_weight = sum(_char_width_weight(char) for char in original) or 1.0
    cursor = float(span_start)
    runs = []
    current_kind = None
    current_text = []
    current_start = cursor

    def char_kind(char):
        if _has_hangul(char):
            return "overlay"
        if _is_ascii_label_char(char):
            return "gen"
        return current_kind or "overlay"

    def flush(end_x):
        nonlocal current_kind, current_text, current_start
        if not current_text or not current_kind:
            current_text = []
            current_kind = None
            current_start = end_x
            return
        run_kind = current_kind
        has_ascii_word = any(char.isascii() and char.isalpha() for char in current_text)
        if run_kind == "gen" and not has_ascii_word:
            run_kind = "overlay"
        cleaned = _clean_split_run("".join(current_text), run_kind)
        if cleaned:
            runs.append({
                "kind": run_kind,
                "text": cleaned,
                "bbox": _run_bbox(axis, y_min, x_min, y_max, x_max, current_start, end_x),
            })
        current_text = []
        current_kind = None
        current_start = end_x

    for char in original:
        width = total_span * (_char_width_weight(char) / total_weight)
        next_cursor = cursor + width
        kind = char_kind(char)
        if current_kind is None:
            current_kind = kind
            current_start = cursor
        elif kind != current_kind:
            flush(cursor)
            current_kind = kind
            current_start = cursor
        current_text.append(char)
        cursor = next_cursor
    flush(float(span_end))
    return _merge_adjacent_runs(runs)


def _is_split_overlay_text(element):
    return bool(element.get("_split_for_overlay"))


def _public_element(element):
    return {key: value for key, value in element.items() if not key.startswith("_")}


def _text_placeholder_desc(element):
    """Keep a text box's layout footprint without asking Ideogram to draw the
    actual lettering. The real glyphs are rendered later by Layout Text Overlay."""
    del element
    return (
        "plain blank background panel, preserve this exact layout space and "
        "composition balance, continue the surrounding design and colors, "
        "no typography, no lettering, no symbols, no logo, no words, "
        "no readable text, no Korean characters"
    )


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
                "text_overlay_mode": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "label_on": "split text for overlay (Korean)",
                        "label_off": "text in image",
                        "tooltip": "On: drop text elements from ideogram_json (Ideogram generates art only) and route them to the text_json output for Layout Text Overlay — crisp Korean instead of garbled rendering. Off: text stays in the generated image (fine for English).",
                    },
                ),
            },
            "optional": {
                # Bridge inputs for the "⟳ Pull from input" button: connect an
                # Image → Ideogram Layout draft here, run the upstream, then Pull
                # to load it onto the canvas (json) and under it (image backdrop).
                "imported_json": (
                    "STRING",
                    {
                        "forceInput": True,
                        "tooltip": "Connect an Ideogram JSON draft (e.g. from Image → Ideogram Layout). Run upstream, then press '⟳ Pull from input' on the node to load it onto the canvas.",
                    },
                ),
                "image": (
                    "IMAGE",
                    {"tooltip": "Optional: the analyzed image. Pulling lays it under the canvas as the reference backdrop so boxes land on the real image."},
                ),
            },
        }

    RETURN_TYPES = ("STRING", "INT", "INT", "STRING")
    RETURN_NAMES = ("ideogram_json", "width", "height", "text_json")
    FUNCTION = "build"
    CATEGORY = "toobusy/Plan"
    OUTPUT_NODE = True

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
        text_overlay_mode=False,
        imported_json="",
        image=None,
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
                element["_split_for_overlay"] = _has_hangul(text)
                if element["_split_for_overlay"]:
                    element["_split_runs"] = _split_mixed_hangul_runs(text, ideogram_bbox)
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

        def _payload(elems, suppress_text=False):
            high_level = high_level_description.strip()
            style = dict(style_description)
            comp_background = background.strip()
            if suppress_text:
                text_policy = (
                    "Preserve non-Korean labels and product names that remain "
                    "in the layout. For reserved Korean overlay panels only, "
                    "leave the area blank and do not render Hangul or Korean "
                    "characters; Korean text will be added later by a separate overlay."
                )
                high_level = f"{high_level} {text_policy}".strip()
                style["aesthetics"] = f"{style.get('aesthetics', '').strip()} {text_policy}".strip()
                comp_background = f"{comp_background} {text_policy}".strip()
            return {
                "high_level_description": high_level,
                "style_description": style,
                "compositional_deconstruction": {
                    "background": comp_background,
                    "elements": [_public_element(el) for el in elems],
                },
            }

        # Korean overlay mode: split Hangul text out so Ideogram generates the
        # art WITHOUT trying to render the (garbled) Korean glyphs. Non-Hangul
        # text stays in the generation payload so labels like "LTX2.3" remain.
        text_elements = []
        for el in elements:
            if not _is_split_overlay_text(el):
                continue
            overlay_runs = [run for run in el.get("_split_runs", []) if run["kind"] == "overlay"]
            if not overlay_runs:
                text_elements.append(el)
                continue
            for run in overlay_runs:
                overlay_el = {
                    "type": "text",
                    "bbox": run["bbox"],
                    "text": run["text"],
                    "desc": _build_desc(run["text"], "Korean overlay text", strict_text=strict_text, reinforce_text=reinforce_text),
                }
                if el.get("color_palette"):
                    overlay_el["color_palette"] = el["color_palette"]
                text_elements.append(overlay_el)
        if text_overlay_mode:
            gen_elements = []
            for el in elements:
                if not _is_split_overlay_text(el):
                    gen_elements.append(el)
                    continue
                split_runs = el.get("_split_runs", [])
                if not split_runs:
                    placeholder = {
                        "type": "obj",
                        "bbox": el["bbox"],
                        "desc": _text_placeholder_desc(el),
                    }
                    if el.get("color_palette"):
                        placeholder["color_palette"] = el["color_palette"]
                    gen_elements.append(placeholder)
                    continue
                for run in split_runs:
                    if run["kind"] == "gen":
                        gen_el = {
                            "type": "text",
                            "bbox": run["bbox"],
                            "text": run["text"],
                            "desc": _build_desc(run["text"], "non-Korean label text", strict_text=strict_text, reinforce_text=reinforce_text),
                        }
                    else:
                        gen_el = {
                            "type": "obj",
                            "bbox": run["bbox"],
                            "desc": _text_placeholder_desc(el),
                        }
                    if el.get("color_palette"):
                        gen_el["color_palette"] = el["color_palette"]
                    gen_elements.append(gen_el)
            if not gen_elements:
                gen_elements = [{
                    "type": "obj",
                    "bbox": [250, 250, 750, 750],
                    "desc": high_level_description.strip() or "main subject",
                }]
        else:
            gen_elements = elements

        ideogram_json = json.dumps(_payload(gen_elements, suppress_text=text_overlay_mode), ensure_ascii=False, indent=2)
        text_json = json.dumps(_payload(text_elements), ensure_ascii=False, indent=2)
        result = (ideogram_json, int(width), int(height), text_json)

        # Send the bridge inputs back to the frontend so the "⟳ Pull from input"
        # button can load them onto the canvas / backdrop. This never changes the
        # node's own output — imported_json is a frontend bridge, not merged here.
        ui = {}
        if isinstance(imported_json, str) and imported_json.strip():
            ui["toobusy_import"] = [imported_json]
        if image is not None:
            data_url = _image_to_data_url(image)
            if data_url:
                ui["toobusy_image"] = [data_url]
        if ui:
            return {"ui": ui, "result": result}
        return result


def _image_to_data_url(image, max_edge=1536):
    """First frame of an IMAGE tensor -> downscaled JPEG data URL for the canvas
    backdrop. Returns '' if PIL/numpy/torch aren't available."""
    try:
        import base64
        import io

        import numpy as np
        from PIL import Image as PILImage

        frame = image[0].detach().cpu().numpy()
        array = (frame[..., :3].clip(0.0, 1.0) * 255.0).astype("uint8")
        pil = PILImage.fromarray(array)
        w, h = pil.size
        scale = min(1.0, float(max_edge) / float(max(w, h)))
        if scale < 1.0:
            pil = pil.resize((max(1, int(w * scale)), max(1, int(h * scale))))
        buffer = io.BytesIO()
        pil.save(buffer, format="JPEG", quality=85)
        return "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")
    except Exception:
        return ""


NODE_CLASS_MAPPINGS = {
    "IdeogramLayoutBuilder": IdeogramLayoutBuilder,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "IdeogramLayoutBuilder": "toobusy Ideogram Layout Builder",
}
