import json
import re


STYLE_MODES = ["Literal", "Cinematic", "Product", "Character", "Poster"]
LANGUAGES = ["Auto", "Korean", "English"]

STYLE_EMPHASIS = {
    "Literal": "translate faithfully with minimal embellishment",
    "Cinematic": "cinematic mood, dramatic lighting, filmic composition",
    "Product": "clean commercial product look, studio lighting, sharp focus, balanced negative space",
    "Character": "character-focused composition, expressive and detailed subject",
    "Poster": "graphic poster design, strong visual hierarchy, bold readable typography",
}

TOP_KEYS = ("high_level_description", "style_description", "compositional_deconstruction")


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
        out["compositional_deconstruction"] = comp

    # Keep the documented top-level key order, then any extras.
    ordered = {key: out[key] for key in TOP_KEYS if key in out}
    for key, value in out.items():
        if key not in ordered:
            ordered[key] = value
    return ordered


_SCHEMA_LINES = [
    "Return VALID JSON ONLY (no markdown fences, no commentary) with exactly these top-level keys:",
    '- "high_level_description": string',
    '- "style_description": object with "aesthetics", "lighting", "photo", "medium" (strings) and "color_palette" (list of #RRGGBB hex)',
    '- "compositional_deconstruction": object with "background" (string) and "elements" (list).',
    '  Each element: "type" ("obj" or "text"), "bbox" [y_min, x_min, y_max, x_max] in 0-1000, "desc" (string), and for "text" also a "text" field.',
]


def _build_prompt(scene, style_mode, language, preserve_intent, fill_missing, existing_layout_json, image_present=False):
    emphasis = STYLE_EMPHASIS.get(style_mode, STYLE_EMPHASIS["Literal"])

    if image_present:
        # Vision mode: describe what is actually in the connected image.
        lines = [
            "Analyze the provided IMAGE and describe its layout as an Ideogram 4 structured prompt.",
            "Report what is ACTUALLY in the image — its text, objects, and composition.",
            "Read all visible text EXACTLY, keeping its original language (Korean stays Korean) in the \"text\" field; write \"desc\" fields in English.",
            "Use type \"text\" for readable text (include the exact string), type \"obj\" for everything else (people, icons, panels, products, shapes).",
            "Estimate each bbox from the image. Output ONE element per distinct thing — never duplicate or near-identical boxes for the same item.",
            "Capture the meaningful layout pieces (title, sections, key icons/blocks), about 5-15 elements; skip tiny incidental details.",
        ]
        if scene and scene.strip():
            lines.append("The SCENE text below is an optional hint about the user's intent/focus; the IMAGE is the source of truth.")
    else:
        lines = [
            "Convert the user's scene description into an Ideogram 4 friendly English structured prompt.",
            "Improve clarity, composition, lighting, style, and visual specificity.",
            f"Style emphasis: {emphasis}.",
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
        hint = "consistent with the image" if image_present else "consistent with the scene"
        lines.append(f"Fill any missing fields with sensible defaults {hint}.")

    lines += ["", *_SCHEMA_LINES, "", "SCENE:", scene.strip()]
    if existing_layout_json and existing_layout_json.strip():
        lines += ["", "EXISTING LAYOUT JSON (refine this, keep its structure):", existing_layout_json.strip()]
    return "\n".join(lines)


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
    ):
        # Imported lazily so this module stays import-light (json/re only) and
        # unit-testable outside ComfyUI; reuses the same TextGenerate call the
        # rest of the pack uses (it already forwards an optional image to a
        # vision-capable model like Gemma 4).
        from ..keyframe_maker_node.keyframe_maker import _generate_text

        prompt = _build_prompt(
            scene, style_mode, language, preserve_intent, fill_missing_fields,
            existing_layout_json, image_present=image is not None,
        )

        try:
            raw = _generate_text(clip, prompt, max_length=2048, seed=int(seed), image=image)
        except Exception as exc:  # noqa: BLE001 - surface a friendly, actionable message
            message = (
                "[toobusy] Ideogram Prompt Polish needs a text-generation model on `clip` "
                "(the same kind Keyframe Maker uses, via ComfyUI TextGenerate). "
                f"Could not run it: {exc}"
            )
            print(message)
            fallback = _ensure_shape({}, scene, True)
            return (json.dumps(fallback, ensure_ascii=False, indent=2), message)

        data = _extract_json(raw)
        if data is None:
            print("[toobusy] Ideogram Prompt Polish: model did not return valid JSON; falling back to the raw scene.")
            payload = _ensure_shape({}, scene, fill_missing_fields)
            return (json.dumps(payload, ensure_ascii=False, indent=2), raw or "")

        payload = _ensure_shape(data, scene, fill_missing_fields)
        return (json.dumps(payload, ensure_ascii=False, indent=2), raw or "")


NODE_CLASS_MAPPINGS = {
    "ToobusyIdeogramPromptPolish": ToobusyIdeogramPromptPolish,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ToobusyIdeogramPromptPolish": "toobusy Ideogram Prompt Polish",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
