import json
import re


STYLE_MODES = ["Literal", "Cinematic", "Product", "Character", "Poster"]
LANGUAGES = ["Auto", "Korean", "English"]
IMAGE_INSTRUCTION_MODES = ["Analyze image literally", "Transform by scene text"]
ANALYSIS_MODES = ["fast", "balanced", "detailed"]

STYLE_EMPHASIS = {
    "Literal": "translate faithfully with minimal embellishment",
    "Cinematic": "cinematic mood, dramatic lighting, filmic composition",
    "Product": "clean commercial product look, studio lighting, sharp focus, balanced negative space",
    "Character": "character-focused composition, expressive and detailed subject",
    "Poster": "graphic poster design, strong visual hierarchy, bold readable typography",
}

TOP_KEYS = ("high_level_description", "style_description", "compositional_deconstruction")
MIN_BOX_SIZE = 40
EDIT_COMMAND_RE = re.compile(
    r"\b("
    r"replac(?:e|es|ed|ing)|chang(?:e|es|ed|ing)|convert(?:s|ed|ing)?|"
    r"transform(?:s|ed|ing)?|turn(?:s|ed|ing)?|swap(?:s|ped|ping)?"
    r")\b",
    re.IGNORECASE,
)


def _extract_json(text):
    """Pull the first complete JSON object out of an LLM response.

    LLMs love to wrap JSON in ```json fences, add prose, or leave trailing
    commas. We strip fences, scan brace depth (string-aware so braces inside
    strings don't confuse it), and try a trailing-comma repair before giving up.
    """
    if not text:
        return None
    t = text.strip()
    t = re.sub(r"^```(?:json)?", "", t).strip()
    if t.endswith("```"):
        t = t[:-3].strip()

    start = t.find("{")
    if start < 0:
        return None

    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(t)):
        c = t[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            continue
        if c == '"':
            in_str = True
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                candidate = t[start : i + 1]
                repaired = re.sub(r",(\s*[}\]])", r"\1", candidate)
                for attempt in (candidate, repaired):
                    try:
                        parsed = json.loads(attempt)
                        return parsed if isinstance(parsed, dict) else None
                    except (ValueError, TypeError):
                        continue
                return None
    return None


def _ensure_shape(data, scene, fill_missing):
    """Guarantee a valid top-level Ideogram payload without mangling LLM content."""
    out = dict(data) if isinstance(data, dict) else {}

    if not str(out.get("high_level_description") or "").strip():
        out["high_level_description"] = scene.strip()

    if fill_missing:
        style = out.get("style_description")
        style = dict(style) if isinstance(style, dict) else {}
        style.setdefault("aesthetics", "clean composition, balanced negative space")
        style.setdefault("lighting", "soft studio lighting")
        style.setdefault("photo", "")
        style.setdefault("medium", "photography")
        style.setdefault("color_palette", [])
        out["style_description"] = style

        comp = out.get("compositional_deconstruction")
        comp = dict(comp) if isinstance(comp, dict) else {}
        comp.setdefault("background", "")
        if not isinstance(comp.get("elements"), list):
            comp["elements"] = []
        if not comp["elements"]:
            comp["elements"] = [
                {
                    "type": "obj",
                    "bbox": [220, 220, 820, 820],
                    "desc": "main subject from the scene, centered composition",
                }
            ]
        out["compositional_deconstruction"] = comp

    # Keep the documented top-level key order, then any extras.
    ordered = {key: out[key] for key in TOP_KEYS if key in out}
    for key, value in out.items():
        if key not in ordered:
            ordered[key] = value
    return ordered


def _strip_edit_command_language(text):
    """Keep transform outputs as final-scene descriptions, not edit commands."""
    value = str(text or "").strip()
    if not value:
        return value
    parts = re.split(r"(?<=[.!?])\s+|(?:\s+[-–—]\s+)", value)
    kept = [part.strip() for part in parts if part.strip() and not EDIT_COMMAND_RE.search(part)]
    if kept:
        return " ".join(kept)

    value = re.sub(
        r"\b(replac(?:e|es|ed|ing)|chang(?:e|es|ed|ing)|convert(?:s|ed|ing)?|transform(?:s|ed|ing)?|turn(?:s|ed|ing)?|swap(?:s|ped|ping)?)\b\s+",
        "",
        value,
        flags=re.IGNORECASE,
    )
    value = re.sub(r"\b(with|into|to)\b\s+", "", value, count=1, flags=re.IGNORECASE)
    return value.strip(" .;:-") or "Final transformed scene element"


def _remove_edit_command_language(payload):
    """Remove wording like 'replacing the SUV' from final Ideogram JSON."""
    if not isinstance(payload, dict):
        return payload

    for key in ("high_level_description",):
        if isinstance(payload.get(key), str):
            payload[key] = _strip_edit_command_language(payload[key])

    comp = payload.get("compositional_deconstruction")
    elements = comp.get("elements") if isinstance(comp, dict) else None
    if isinstance(elements, list):
        for element in elements:
            if not isinstance(element, dict):
                continue
            if isinstance(element.get("desc"), str):
                element["desc"] = _strip_edit_command_language(element["desc"])
            if isinstance(element.get("text"), str) and EDIT_COMMAND_RE.search(element["text"]):
                element["text"] = _strip_edit_command_language(element["text"])
    return payload


def _clamp_int(value, minimum=0, maximum=1000):
    try:
        number = int(round(float(value)))
    except (TypeError, ValueError):
        number = minimum
    return max(minimum, min(maximum, number))


def _normalize_bbox(value):
    if not isinstance(value, list) or len(value) != 4:
        return [100, 100, 900, 900]
    y_min, x_min, y_max, x_max = [_clamp_int(item) for item in value]
    if x_max - x_min < MIN_BOX_SIZE:
        x_max = min(1000, x_min + MIN_BOX_SIZE)
    if y_max - y_min < MIN_BOX_SIZE:
        y_max = min(1000, y_min + MIN_BOX_SIZE)
    if x_max - x_min < MIN_BOX_SIZE:
        x_min = max(0, x_max - MIN_BOX_SIZE)
    if y_max - y_min < MIN_BOX_SIZE:
        y_min = max(0, y_max - MIN_BOX_SIZE)
    return [y_min, x_min, y_max, x_max]


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
    if keep == "latin":
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
    # Large title blocks commonly stack Latin/product text above Korean copy.
    # Inline labels such as "First Frame (시작 프레임)" are short, so keep them
    # split horizontally.
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
            return "hangul"
        if _is_ascii_label_char(char):
            return "latin"
        return current_kind or "hangul"

    def flush(end_x):
        nonlocal current_kind, current_text, current_start
        if not current_text or not current_kind:
            current_text = []
            current_kind = None
            current_start = end_x
            return
        run_kind = current_kind
        has_ascii_word = any(char.isascii() and char.isalpha() for char in current_text)
        if run_kind == "latin" and not has_ascii_word:
            run_kind = "hangul"
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


def _split_mixed_text_elements(payload):
    """Normalize vision JSON so mixed Latin/Hangul labels arrive pre-separated.

    This runs before Layout Builder. If a vision LLM emits one element like
    "LTX2.3 두두등장!", split it into approximate sub-bbox text elements so the
    builder does not have to guess later.
    """
    comp = payload.get("compositional_deconstruction")
    elements = comp.get("elements") if isinstance(comp, dict) else None
    if not isinstance(elements, list):
        return payload

    normalized = []
    for element in elements:
        if not isinstance(element, dict):
            normalized.append(element)
            continue
        text = str(element.get("text", "")).strip()
        if not text or not _has_hangul(text):
            normalized.append(element)
            continue
        runs = _split_mixed_hangul_runs(text, element.get("bbox"))
        if len(runs) <= 1:
            new_element = dict(element)
            new_element["type"] = "text"
            new_element["bbox"] = _normalize_bbox(element.get("bbox"))
            new_element["text"] = text
            normalized.append(new_element)
            continue
        for run in runs:
            new_element = dict(element)
            new_element["type"] = "text"
            new_element["bbox"] = run["bbox"]
            new_element["text"] = run["text"]
            suffix = "Latin label segment" if run["kind"] == "latin" else "Korean overlay text segment"
            desc = str(element.get("desc", "")).strip()
            new_element["desc"] = f"{desc} — {suffix}" if desc else suffix
            normalized.append(new_element)
    comp["elements"] = normalized
    return payload


def _enrich_element_descriptions(payload, analysis_mode="detailed"):
    if analysis_mode != "detailed":
        return payload

    comp = payload.get("compositional_deconstruction")
    elements = comp.get("elements") if isinstance(comp, dict) else None
    if not isinstance(elements, list):
        return payload

    figure_words = ("person", "man", "woman", "male", "female", "figure", "character", "anime", "boy", "girl")
    for element in elements:
        if not isinstance(element, dict):
            continue
        desc = str(element.get("desc", "")).strip()
        bbox = _normalize_bbox(element.get("bbox"))
        height = bbox[2] - bbox[0]
        width = bbox[3] - bbox[1]
        lower = desc.lower()
        if element.get("type") == "obj" and any(word in lower for word in figure_words):
            if height > width * 1.5 and "full" not in lower and "upper" not in lower and "cropped" not in lower:
                desc = (
                    f"{desc}. Full-body head-to-toe character inside the frame, "
                    "standing pose, visible legs and feet, preserve the full figure silhouette"
                )
        if element.get("type") == "obj" and "panel" in lower and "showing" in lower and len(desc) < 90:
            desc = f"{desc}. Include the visible internal layout, small UI cards, icons, arrows, thumbnails, and labels as seen in the reference."
        if desc:
            element["desc"] = desc
    return payload


_SCHEMA_LINES = [
    "Return VALID JSON ONLY (no markdown fences, no commentary) with exactly these top-level keys:",
    '- "high_level_description": string',
    '- "style_description": object with "aesthetics", "lighting", "photo", "medium" (strings) and "color_palette" (list of #RRGGBB hex)',
    '- "compositional_deconstruction": object with "background" (string) and "elements" (list).',
    '  Each element: "type" ("obj" or "text"), "bbox" [y_min, x_min, y_max, x_max] in 0-1000, "desc" (string), optional "role" (string), and for "text" also a "text" field.',
    '  bbox order is [top, left, bottom, right], NOT [left, top, right, bottom]. Examples: top-left headline [60, 80, 180, 920], center subject [220, 300, 820, 700], bottom caption [820, 120, 940, 880].',
    '  Use optional role only when useful for text/logo/sign/UI labels, such as "headline", "subtitle", "body", "footer", "product label", "sign", "ui label", or "logo".',
]


def _analysis_mode(value):
    return value if value in ANALYSIS_MODES else "balanced"


def _analysis_max_length(analysis_mode, image_present=False):
    if not image_present:
        return 1408
    if analysis_mode == "fast":
        return 896
    if analysis_mode == "detailed":
        return 2048
    return 1408


def _visible_raw(raw, debug_raw):
    if debug_raw:
        return raw or ""
    value = str(raw or "")
    if not value:
        return ""
    return value[:512] + "\n...[llm_raw truncated; enable debug_raw for full output]" if len(value) > 512 else value


def _build_prompt(
    scene,
    style_mode,
    language,
    preserve_intent,
    fill_missing,
    existing_layout_json,
    image_present=False,
    image_instruction_mode="Analyze image literally",
    analysis_mode="balanced",
):
    emphasis = STYLE_EMPHASIS.get(style_mode, STYLE_EMPHASIS["Literal"])
    transform_image = image_present and image_instruction_mode == "Transform by scene text"
    analysis_mode = _analysis_mode(analysis_mode)

    if image_present:
        # Vision mode: either describe the source image literally or keep its
        # layout while rewriting content according to the user's scene text.
        lines = [
            "Analyze the provided IMAGE and describe its layout as an Ideogram 4 structured prompt.",
            "Use type \"text\" for readable text (include the exact string), type \"obj\" for everything else (people, icons, panels, products, shapes).",
            "Keep mixed Korean/Latin labels as one text element unless they are clearly separated into different visual blocks.",
            "Estimate each bbox from the image. Output ONE element per distinct thing — never duplicate or near-identical boxes for the same item.",
        ]
        if analysis_mode == "fast":
            lines += [
                "analysis_mode: fast. Make a quick Layout Builder draft, not a perfect inspection.",
                "Capture about 3-7 major elements only.",
                "Each desc must be compact, about 6-14 words.",
                "Describe only layout-critical traits: subject, role, crop, main color, foreground/background, and broad pose/action.",
                "Do not write long full-sentence descriptions.",
                "Do not describe tiny incidental details, small UI cards, tiny icons, small arrows, thumbnails, or minor labels.",
                "Do not over-fragment the image.",
            ]
        elif analysis_mode == "balanced":
            lines += [
                "analysis_mode: balanced. Make a practical Layout Builder draft for editing.",
                "Capture about 5-10 important elements.",
                "Each desc must be compact, about 10-22 words.",
                "Focus on important people, products, headlines, readable text, large panels, and major layout blocks.",
                "Describe panel internals only when they are central to the composition, and keep it short.",
                "Do not describe tiny incidental details or over-fragment the image.",
            ]
        else:
            lines += [
                "analysis_mode: detailed. More detailed inspection is allowed.",
                "Capture about 5-15 meaningful layout elements.",
                "For panels and diagrams, describe internal cards, icons, arrows, thumbnails, and labels.",
                "For character figures, describe clothing, expression, pose, crop, and key colors.",
                "For text, describe visible style such as outline, glow, weight, tilt, perspective, or stacked layout.",
                "If a text block is visually tilted or distorted, mention that in desc; bbox stays axis-aligned, so desc must carry the tilt/perspective cue.",
            ]
        if transform_image:
            lines[0] = "Use the provided IMAGE as a layout/composition reference and rewrite the content as an Ideogram 4 structured prompt."
            lines.insert(1, "Keep the image's visual hierarchy, panel structure, text placement, approximate bboxes, color relationships, and composition.")
            lines.insert(2, "Do NOT preserve the original subject, team, country, names, stats, or visible text when the SCENE asks to change them.")
            lines.insert(3, "Rewrite all subject descriptions and text fields according to the SCENE, while keeping the source image's layout.")
            lines.insert(4, "Output the FINAL transformed scene only. Never describe the edit operation.")
            lines.insert(5, "Do not write phrases like \"replacing the black SUV\", \"changed to\", \"converted into\", or \"turning the cars into planes\" in any desc or text field.")
            lines.insert(6, "Bad desc: \"replacing the black SUV with an airplane\". Good desc: \"sleek white airplane parked in the parking-lot space, matching the original vehicle position\".")
            lines.insert(7, "Example: if the image is a foreign athlete card and SCENE asks for Korean athlete content, output a Korean athlete card layout with Korean-player names, team labels, stats, and captions.")
            lines.append("The SCENE text below is the transformation instruction and content source; the IMAGE provides layout only.")
        else:
            lines.insert(1, "Report what is ACTUALLY in the image — its text, objects, and composition.")
            lines.insert(2, "Read all visible text EXACTLY, keeping its original language (Korean stays Korean) in the \"text\" field; write \"desc\" fields in English.")
            if scene and scene.strip():
                lines.append("The SCENE text below is an optional hint about the user's intent/focus; the IMAGE is the source of truth.")
    else:
        lines = [
            "Convert the user's scene description into an Ideogram 4 friendly English structured prompt.",
            "Improve clarity, composition, lighting, style, and visual specificity.",
            f"Style emphasis: {emphasis}.",
            "For text-only scene mode, always create layout elements.",
            "Simple natural scene: create 3-5 elements.",
            "Poster/product/UI/commercial scene: create 5-12 elements.",
            "Each element needs an approximate bbox in [top, left, bottom, right] order.",
            "Do not leave elements empty unless the scene is truly abstract.",
            "Do not over-fragment natural scenes.",
        ]
        if language == "Auto":
            lines.append("The scene may be Korean or English; detect it and output English.")
        else:
            lines.append(f"The scene is written in {language}; output English.")
        if preserve_intent:
            lines.append(
                "Stay faithful to the user's intent. Do not introduce a different subject; only add detail needed for clarity. "
                "Preserve the original mood, emotional tone, and relationships — especially subtle nuance in Korean input. "
                "Translate the user's meaning so Ideogram understands it; do NOT flatten it into generic Western stock-photo phrasing."
            )

    if fill_missing:
        if transform_image:
            hint = "consistent with the scene transformation while preserving the image layout"
        else:
            hint = "consistent with the image" if image_present else "consistent with the scene"
        lines.append(f"Fill any missing fields with sensible defaults {hint}.")

    lines += ["", *_SCHEMA_LINES, "", "SCENE:", scene.strip()]
    if existing_layout_json and existing_layout_json.strip():
        lines += ["", "EXISTING LAYOUT JSON (refine this, keep its structure):", existing_layout_json.strip()]
    return "\n".join(lines)


def _quantize_palette(pixels, limit):
    """Dominant #RRGGBB colors of an (N,3) uint8 pixel array, coarse-quantized so
    a few big regions win. Returns [] on any failure / no numpy."""
    try:
        import numpy as np

        if pixels.size == 0:
            return []
        buckets = ((pixels // 32) * 32 + 16).astype("int32")
        keys = buckets[:, 0] * 65536 + buckets[:, 1] * 256 + buckets[:, 2]
        values, counts = np.unique(keys, return_counts=True)
        order = counts.argsort()[::-1][: int(limit)]
        hexes = []
        for key in values[order]:
            r, g, b = (int(key) >> 16) & 255, (int(key) >> 8) & 255, int(key) & 255
            hexes.append(f"#{r:02X}{g:02X}{b:02X}")
        return hexes
    except Exception:
        return []


def _frame_pixels(image):
    """First IMAGE frame as an (H,W,3) uint8 numpy array, or None."""
    try:
        import numpy as np  # noqa: F401

        frame = image[0].detach().cpu().numpy()
        return (frame[..., :3].clip(0.0, 1.0) * 255.0).astype("uint8")
    except Exception:
        return None


def _enrich_palette(payload, image, element_colors=5, style_colors=8):
    """Fill empty color palettes from the actual image so the result keeps the
    source colors instead of going murky. Vision LLMs frequently return an empty
    color_palette; we sample the real pixels (whole image for style, each
    element's bbox region for elements). bbox is Ideogram order
    [y_min, x_min, y_max, x_max] in 0-1000."""
    frame = _frame_pixels(image)
    if frame is None:
        return payload
    height, width = frame.shape[0], frame.shape[1]

    style = payload.get("style_description")
    if isinstance(style, dict) and not style.get("color_palette"):
        style["color_palette"] = _quantize_palette(frame.reshape(-1, 3), style_colors)

    comp = payload.get("compositional_deconstruction")
    elements = comp.get("elements") if isinstance(comp, dict) else None
    if isinstance(elements, list):
        for element in elements:
            if not isinstance(element, dict) or element.get("color_palette"):
                continue
            bbox = element.get("bbox")
            if not (isinstance(bbox, list) and len(bbox) == 4):
                continue
            y0 = max(0, min(height, int(bbox[0] / 1000.0 * height)))
            x0 = max(0, min(width, int(bbox[1] / 1000.0 * width)))
            y1 = max(0, min(height, int(bbox[2] / 1000.0 * height)))
            x1 = max(0, min(width, int(bbox[3] / 1000.0 * width)))
            if y1 - y0 < 2 or x1 - x0 < 2:
                continue
            region = frame[y0:y1, x0:x1].reshape(-1, 3)
            palette = _quantize_palette(region, element_colors)
            if palette:
                element["color_palette"] = palette
    return payload


def _release_clip_from_vram(clip):
    """Unload only this prompt CLIP and its clones, preserving other models.

    This is the narrow hand-off needed by large chained workflows: a vision
    prompt model (for example Gemma 4) can leave VRAM before Ideogram starts,
    without the global cache destruction performed by generic VRAM cleaners.
    """
    patcher = getattr(clip, "patcher", None)
    if patcher is None:
        return False
    try:
        from comfy import model_management

        model_management.unload_model_and_clones(patcher)
        model_management.soft_empty_cache()
        return True
    except ImportError:
        return False
    except Exception as exc:  # noqa: BLE001 - cleanup must not discard a valid prompt
        print(f"[toobusy] Could not release prompt CLIP from VRAM: {exc}")
        return False


class ToobusyIdeogramPromptPolish:
    """Folds Korean/English scene writing -> English translation -> Ideogram prompt structuring into one node.

    Takes a free-form (Korean or English) scene and a text-generation model, and
    returns an Ideogram 4 ready structured-prompt JSON. The input scene is never
    overwritten — the structured prompt comes out of a separate output — so the
    user's original wording is always preserved.

    With an optional `image` and a vision-capable model (e.g. Gemma 4), it
    instead analyzes the image into the same Ideogram layout JSON (reading text,
    incl. Korean, and locating elements). Wire `ideogram_json` into the Layout
    Builder's `imported_json` and press "⟳ Pull from input" to edit it on canvas.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "clip": ("CLIP",),
                "scene": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "노을 지는 해변에서 빨간 원피스를 입은 여자가 카메라를 등지고 서 있다.",
                    },
                ),
                "style_mode": (STYLE_MODES, {"default": "Literal"}),
                "language": (LANGUAGES, {"default": "Auto"}),
                "preserve_intent": ("BOOLEAN", {"default": True}),
                "fill_missing_fields": ("BOOLEAN", {"default": True}),
                "seed": (
                    "INT",
                    {"default": 1, "min": 0, "max": 0xffffffffffffffff, "control_after_generate": True},
                ),
            },
            "optional": {
                "existing_layout_json": ("STRING", {"multiline": True, "default": ""}),
                "image": (
                    "IMAGE",
                    {
                        "tooltip": "Optional. Connect an image and a vision-capable text model (e.g. Gemma 4) to analyze the image INTO an Ideogram layout draft (reads text incl. Korean, finds elements + bboxes). Without an image this stays a scene-text polisher. Wire ideogram_json into the Layout Builder's imported_json, then press Pull.",
                    },
                ),
                "image_instruction_mode": (
                    IMAGE_INSTRUCTION_MODES,
                    {
                        "default": "Analyze image literally",
                        "tooltip": "With an image connected: literal mode transcribes the source image; transform mode keeps the layout/bboxes but rewrites subject and text according to the Scene field.",
                    },
                ),
                "analysis_mode": (
                    ANALYSIS_MODES,
                    {
                        "default": "balanced",
                        "tooltip": "Image analysis detail. fast: quick draft with few compact elements. balanced: default practical Layout Builder draft. detailed: slower, richer panel/UI/text/style analysis.",
                    },
                ),
                "debug_raw": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "tooltip": "Off: return blank/truncated llm_raw to keep workflows lighter. On: return the full raw LLM response for debugging JSON failures.",
                    },
                ),
                # Keep new widgets at the end. ComfyUI serializes widget values
                # positionally, so inserting this among existing fields breaks
                # saved workflows by shifting image/analysis mode values.
                "release_clip_after_run": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "tooltip": "After creating the prompt, unload only this CLIP model from VRAM. Recommended before a large Ideogram model; unlike a global VRAM cleaner, other models and caches are preserved.",
                    },
                ),
            },
        }

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("ideogram_json", "llm_raw")
    FUNCTION = "polish"
    CATEGORY = "toobusy/Plan"

    def polish(
        self,
        clip,
        scene,
        style_mode,
        language,
        preserve_intent,
        fill_missing_fields,
        seed,
        existing_layout_json="",
        image=None,
        image_instruction_mode="Analyze image literally",
        analysis_mode="balanced",
        debug_raw=False,
        release_clip_after_run=True,
    ):
        # Imported lazily so this module stays import-light (json/re only) and
        # unit-testable outside ComfyUI; reuses the same TextGenerate call the
        # rest of the pack uses (it already forwards an optional image to a
        # vision-capable model like Gemma 4).
        from ..keyframe_maker_node.keyframe_maker import _generate_text

        prompt = _build_prompt(
            scene, style_mode, language, preserve_intent, fill_missing_fields,
            existing_layout_json, image_present=image is not None,
            image_instruction_mode=image_instruction_mode,
            analysis_mode=analysis_mode,
        )

        try:
            raw = _generate_text(
                clip,
                prompt,
                max_length=_analysis_max_length(_analysis_mode(analysis_mode), image_present=image is not None),
                seed=int(seed),
                image=image,
            )
        except Exception as exc:  # noqa: BLE001 - surface a friendly, actionable message
            message = (
                "[toobusy] Ideogram Prompt Polish needs a text-generation model on `clip` "
                "(the same kind Keyframe Maker uses, via ComfyUI TextGenerate). "
                f"Could not run it: {exc}"
            )
            print(message)
            fallback = _ensure_shape({}, scene, True)
            return (json.dumps(fallback, ensure_ascii=False, indent=2), message)
        finally:
            if release_clip_after_run:
                _release_clip_from_vram(clip)

        data = _extract_json(raw)
        if data is None:
            print("[toobusy] Ideogram Prompt Polish: model did not return valid JSON; falling back to the raw scene.")
            payload = _ensure_shape({}, scene, True)
            return (json.dumps(payload, ensure_ascii=False, indent=2), _visible_raw(raw, debug_raw))

        payload = _ensure_shape(data, scene, fill_missing_fields)
        # Keep mixed Korean/Latin labels intact by default. The experimental
        # split/overlay route remains isolated in Layout Builder's explicit
        # text_overlay_mode and is not run here.
        payload = _enrich_element_descriptions(payload, _analysis_mode(analysis_mode))
        if image is not None and image_instruction_mode == "Transform by scene text":
            payload = _remove_edit_command_language(payload)
        if image is not None:
            # Vision LLMs often leave palettes empty -> murky generations. Backfill
            # from the real image pixels (whole image + per-element regions).
            payload = _enrich_palette(payload, image)
        return (json.dumps(payload, ensure_ascii=False, indent=2), _visible_raw(raw, debug_raw))


NODE_CLASS_MAPPINGS = {
    "ToobusyIdeogramPromptPolish": ToobusyIdeogramPromptPolish,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ToobusyIdeogramPromptPolish": "toobusy Ideogram Prompt Polish",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
