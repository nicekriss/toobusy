import json

TASK_MODES = [
    "Character A + Pose",
    "Character A + Outfit",
    "Character A + Background",
    "Character A + Character B Interaction",
    "Full Character Compose",
    "Product / Packshot",
    "Poster / Thumbnail",
]

STYLE_MODES = ["realistic", "cinematic", "fashion", "advertising", "anime", "editorial"]
ANALYSIS_MODES = ["fast", "balanced"]
REFERENCE_TARGET_PIXELS = 1_000_000

# task_mode / style_mode are no longer node inputs: intent now comes from
# Reference Board text cards and structure from the button panel. These
# internal defaults keep the shared prompt helpers working.
DEFAULT_TASK_MODE = "Full Character Compose"
DEFAULT_STYLE_MODE = "cinematic"
TEXT_CATEGORIES = ("goal", "style", "negative", "custom")

REFERENCE_ROLES = (
    ("main_character", "Main Character Reference"),
    ("secondary_character", "Secondary Character Reference"),
    ("pose", "Pose Reference"),
    ("outfit", "Outfit Reference"),
    ("background", "Background Reference"),
    ("style", "Style Reference"),
    ("product", "Product Reference"),
)

STYLE_BOOSTERS = {
    "realistic": "realistic skin texture, natural proportions, believable lighting",
    "cinematic": "cinematic composition, soft dramatic lighting, natural depth, film-like atmosphere",
    "fashion": "fashion editorial, elegant styling, clean silhouette, polished wardrobe detail",
    "advertising": "commercial polish, premium look, clean focal hierarchy, high-end visual finish",
    "anime": "anime illustration style, clean line art, vivid character readability",
    "editorial": "editorial composition, refined layout, tasteful visual hierarchy, polished finish",
}

TASK_PATTERNS = {
    "Character A + Pose": [
        "Preserve the identity and facial traits of the person from Main Character Reference.",
        "Use the pose, camera angle, and composition from Pose Reference.",
        "Do not introduce a secondary character unless the goal explicitly asks for one.",
    ],
    "Character A + Outfit": [
        "Preserve the identity and facial traits of the person from Main Character Reference.",
        "Borrow only clothing, styling, silhouette, and wardrobe detail from Outfit Reference.",
        "Do not copy the outfit reference person's face or identity.",
    ],
    "Character A + Background": [
        "Preserve the identity and facial traits of the person from Main Character Reference.",
        "Place the scene in a setting inspired by Background Reference.",
        "Do not copy people from the background reference unless the goal explicitly asks for them.",
    ],
    "Character A + Character B Interaction": [
        "Keep Main Character Reference as the main subject.",
        "Include interaction with the person from Secondary Character Reference.",
        "Frame the scene so Character A remains visually dominant.",
    ],
    "Full Character Compose": [
        "Preserve the identity and facial traits of the person from Main Character Reference.",
        "Include Secondary Character Reference when connected and relevant.",
        "Use the pose and composition from Pose Reference.",
        "Use the clothing and styling from Outfit Reference without copying that person's identity.",
        "Place the scene in a setting inspired by Background Reference.",
    ],
    "Product / Packshot": [
        "Prioritize the product or package as the main subject.",
        "Use references for product form, material, color, and commercial composition.",
        "Keep the prompt clean and packshot-friendly.",
    ],
    "Poster / Thumbnail": [
        "Build a clear poster or thumbnail composition with strong focal hierarchy.",
        "Use references for character, pose, outfit, and background roles only where connected.",
        "Keep text/logo instructions explicit only if the goal asks for visible text.",
    ],
}

ROLE_HINTS = {
    "main_character": "main identity, face, hair, body type, expression, key clothing if visible",
    "secondary_character": "secondary person identity, face, styling, pose, interaction potential",
    "pose": "pose, camera angle, composition, crop, number of people, body direction",
    "outfit": "clothing, silhouette, fabric, color, accessories; note if a person is visible",
    "background": "location, lighting, mood, depth, architecture; note if a foreground person is visible",
    "style": "visual style, medium, lighting language, color treatment, texture, graphic finish",
    "product": "product form, material, label, package shape, commercial presentation, hero angle",
}

# --- Button-panel (Prompt Director composer) presets and mappings ---------
# The JS button panel offers these chips; the backend only consumes whatever
# text the panel serializes, so this list stays in sync with the JS for parity.
CAMERA_PRESETS = [
    "low angle", "high angle", "eye level", "close-up", "medium shot",
    "wide shot", "over-the-shoulder", "dutch angle",
]
LIGHTING_PRESETS = [
    "soft light", "rim light", "golden hour", "studio light",
    "hard shadow", "backlight", "neon glow", "natural daylight",
]
STYLE_CHIP_PRESETS = [
    "film grain", "editorial", "anime", "photoreal", "cinematic color", "high fashion",
]

# Button role keys -> the director's fixed 7-role summary slots (when shared).
SELECTION_SUMMARY_ROLE = {
    "character_a": "main_character",
    "main_character": "main_character",
    "character_b": "secondary_character",
    "secondary_character": "secondary_character",
    "pose_a": "pose",
    "pose": "pose",
    "outfit_a": "outfit",
    "outfit": "outfit",
    "background_a": "background",
    "background": "background",
    "style_a": "style",
    "style": "style",
    "prop_a": "product",
    "product": "product",
}

# Button role keys -> bundle prompt-block / selection category.
SELECTION_CATEGORY = {
    "character_a": "character", "character_b": "character", "character_c": "character", "character_d": "character",
    "main_character": "character", "secondary_character": "character",
    "face_a": "face", "face_b": "face",
    "outfit_a": "outfit", "outfit_b": "outfit", "outfit": "outfit",
    "pose_a": "pose", "pose": "pose",
    "background_a": "location", "background": "location",
    "style_a": "style", "style": "style",
    "prop_a": "prop", "product": "prop",
}

# Vision hints for selectable roles outside the fixed 7-role summary set.
EXTRA_ROLE_HINTS = {
    "character_c": "third person identity, face, styling, role in the scene",
    "character_d": "fourth person identity, face, styling, role in the scene",
    "face_a": "face identity, facial structure, expression for a face swap",
    "face_b": "second face identity for an alternate face swap",
    "outfit_b": "second outfit: clothing, silhouette, fabric, color, accessories",
}

REFERENCE_ROLE_LABELS = {
    "character_a": "Character A",
    "character_b": "Character B",
    "character_c": "Character C",
    "character_d": "Character D",
    "main_character": "Main Character Reference",
    "secondary_character": "Secondary Character Reference",
    "face_a": "Face A",
    "face_b": "Face B",
    "outfit_a": "Outfit A",
    "outfit_b": "Outfit B",
    "outfit": "Outfit Reference",
    "pose_a": "Pose Reference",
    "background_a": "Background Reference",
    "style_a": "Style Reference",
    "prop_a": "Product Reference",
}


def _parse_selection(raw):
    """Parse the JS button-panel selection into an ordered list of blocks.

    Returns [] for anything malformed so the node falls back to the legacy
    auto-compose flow and stays backward compatible.
    """
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except Exception:  # noqa: BLE001 - tolerate any malformed widget value
        return []
    if not isinstance(data, dict):
        return []
    blocks = data.get("blocks")
    if not isinstance(blocks, list):
        return []
    cleaned = []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        if str(block.get("kind") or "").strip() in ("reference", "flag", "modifier", "negative", "custom"):
            cleaned.append(block)
    return cleaned


def _mode(value, choices, fallback):
    return value if value in choices else fallback


def _summary_max_length(analysis_mode):
    return 128 if analysis_mode == "fast" else 192


def _final_max_length(analysis_mode):
    return 512 if analysis_mode == "fast" else 768


def _generate_text(clip, prompt, max_length, seed, image=None):
    from ..keyframe_maker_node.keyframe_maker import _generate_text as _keyframe_generate_text

    return _keyframe_generate_text(clip, prompt, max_length=max_length, seed=seed, image=image)


def _connected(image):
    if image is None:
        return False
    shape = getattr(image, "shape", None)
    if shape and len(shape) >= 3:
        width = int(shape[2])
        height = int(shape[1])
        if width <= 1 and height <= 1:
            return False
    return True


def _bundle_image(reference_bundle, role):
    if not isinstance(reference_bundle, dict):
        return None
    role_aliases = {
        "main_character": ("main_character", "character_a"),
        "secondary_character": ("secondary_character", "character_b"),
        "pose": ("pose", "pose_a"),
        "outfit": ("outfit", "outfit_a"),
        "background": ("background", "background_a"),
        "style": ("style", "style_a"),
        "product": ("product", "prop_a"),
    }
    for key in role_aliases.get(role, (role,)):
        data = reference_bundle.get(key)
        if isinstance(data, dict) and data.get("image") is not None:
            return data.get("image")
    for card in reference_bundle.get("cards", []) if isinstance(reference_bundle.get("cards"), list) else []:
        if not isinstance(card, dict):
            continue
        if card.get("role") in role_aliases.get(role, (role,)) and card.get("image") is not None:
            return card.get("image")
    data = reference_bundle.get(role)
    if isinstance(data, dict):
        return data.get("image")
    return None


def _bundle_note(reference_bundle):
    if not isinstance(reference_bundle, dict):
        return ""
    note = str(reference_bundle.get("global_note") or "").strip()
    return note


def _bundle_card_note(reference_bundle, role):
    if not isinstance(reference_bundle, dict):
        return ""
    aliases = {
        "main_character": ("main_character", "character_a"),
        "secondary_character": ("secondary_character", "character_b"),
        "pose": ("pose", "pose_a"),
        "outfit": ("outfit", "outfit_a"),
        "background": ("background", "background_a"),
        "style": ("style", "style_a"),
        "product": ("product", "prop_a"),
    }.get(role, (role,))
    for key in aliases:
        data = reference_bundle.get(key)
        if isinstance(data, dict) and str(data.get("note") or "").strip():
            return str(data.get("note") or "").strip()
    for card in reference_bundle.get("cards", []) if isinstance(reference_bundle.get("cards"), list) else []:
        if isinstance(card, dict) and card.get("role") in aliases:
            note = str(card.get("prompt") or card.get("note") or "").strip()
            if note:
                return note
    return ""


def _update_bundle(
    reference_bundle,
    final_prompt_en,
    final_prompt_ko,
    summaries,
    task_mode,
    style_mode,
    manual_blocks=None,
    manual_selections=None,
    negative_prompt=None,
    extra_flags=None,
):
    bundle = dict(reference_bundle) if isinstance(reference_bundle, dict) else {"version": 1, "cards": []}
    selections = dict(bundle.get("selections") or {})
    if manual_blocks is not None:
        # Button-panel composer: selected blocks are authoritative.
        prompt_blocks = list(manual_blocks)
        for category, role in (manual_selections or {}).items():
            selections[category] = role
    else:
        prompt_blocks = []
        category_by_role = {
            "main_character": "character",
            "secondary_character": "character",
            "pose": "pose",
            "outfit": "outfit",
            "background": "location",
            "style": "style",
            "product": "prop",
        }
        modern_role = {
            "main_character": "character_a",
            "secondary_character": "character_b",
            "pose": "pose_a",
            "outfit": "outfit_a",
            "background": "background_a",
            "style": "style_a",
            "product": "prop_a",
        }
        for role, summary in summaries.items():
            if not summary or summary == "not connected":
                continue
            block_role = modern_role.get(role, role)
            prompt_blocks.append({
                "category": category_by_role.get(role, role),
                "role": block_role,
                "text": summary,
            })
            selections.setdefault(category_by_role.get(role, role), block_role)
    resolved_negative = negative_prompt if negative_prompt else str(bundle.get("negative_prompt") or "")
    bundle.update({
        "version": int(bundle.get("version") or 1),
        "bundle_type": "TOOBUSY_BUNDLE",
        "resolved_prompt": final_prompt_en,
        "resolved_prompt_ko": final_prompt_ko,
        "negative_prompt": resolved_negative,
        "prompt_blocks": prompt_blocks,
        "selections": selections,
        "flags": {
            **(bundle.get("flags") if isinstance(bundle.get("flags"), dict) else {}),
            "prompt_director_applied": True,
            "task_mode": task_mode,
            "style_mode": style_mode,
            **(extra_flags or {}),
        },
    })
    return bundle


def _image_size(image):
    shape = getattr(image, "shape", None)
    if not shape or len(shape) < 3:
        return None
    return int(shape[2]), int(shape[1])


def _resize_size_to_total_pixels(width, height, target_pixels=REFERENCE_TARGET_PIXELS):
    width = max(1, int(width))
    height = max(1, int(height))
    pixels = width * height
    if pixels <= int(target_pixels):
        return width, height, False
    scale = (float(target_pixels) / float(pixels)) ** 0.5
    return max(1, int(round(width * scale))), max(1, int(round(height * scale))), True


def _resize_reference_image(image):
    """Downscale large Comfy IMAGE tensors to 1MP with Lanczos.

    Mirrors the Flux2 Klein reference policy for the director's vision-summary
    input: downscale only, preserve aspect ratio, no upscaling.
    """
    original = _image_size(image)
    if original is None:
        return image, "unknown", "unknown", "unchanged"

    width, height = original
    resized_w, resized_h, should_resize = _resize_size_to_total_pixels(width, height)
    original_text = f"{width}x{height}"
    resized_text = f"{resized_w}x{resized_h}"
    if not should_resize:
        return image, original_text, original_text, "unchanged"

    try:
        import numpy as np
        import torch
        from PIL import Image as PILImage

        device = image.device
        dtype = image.dtype
        frames = []
        for frame in image.detach().cpu():
            array = (frame[..., :3].clamp(0.0, 1.0).numpy() * 255.0).astype("uint8")
            pil = PILImage.fromarray(array)
            pil = pil.resize((resized_w, resized_h), PILImage.Resampling.LANCZOS)
            frames.append(np.asarray(pil).astype("float32") / 255.0)
        resized = torch.from_numpy(np.stack(frames, axis=0)).to(device=device, dtype=dtype)
        return resized, original_text, resized_text, "lanczos downscale"
    except Exception as exc:  # noqa: BLE001 - keep node usable if PIL/torch path differs
        print(f"[toobusy Flux2 Klein Prompt Director] reference resize failed: {exc}")
        return image, original_text, original_text, "resize failed"


def _compact_lines(text, limit=5):
    lines = []
    for raw in str(text or "").replace("\r", "").splitlines():
        line = raw.strip(" \t-*•`")
        if line:
            lines.append(line)
        if len(lines) >= limit:
            break
    return lines


def _summarize_reference(clip, role_key, role_label, image, analysis_mode, seed, hint=None):
    if not _connected(image):
        return "not connected", None

    summary_image, original_size, resized_size, resize_note = _resize_reference_image(image)
    focus = hint or ROLE_HINTS.get(role_key, "key visual traits, identity, pose, and composition")
    prompt = f"""Analyze this image as {role_label} for a Flux2 Klein reference prompt director.

Return 1-3 short English lines only.

Focus on: {focus}.

Rules:
- Be literal and compact.
- Do not invent names or story.
- If there is a visible person, say whether it is a single person, two-person composition, or foreground human.
- If this is an outfit or background reference, explicitly mention whether a face/person may leak into generation.
- No markdown.
- English only."""
    raw = _generate_text(
        clip,
        prompt,
        max_length=_summary_max_length(analysis_mode),
        seed=int(seed),
        image=summary_image,
    )
    lines = _compact_lines(raw, limit=3 if analysis_mode == "balanced" else 2)
    summary = "; ".join(lines) if lines else "connected image, unclear content"
    size_meta = {
        "original": original_size,
        "resized": resized_size,
        "note": resize_note,
    }
    return summary, size_meta


def _format_reference_summary(summaries, sizes=None):
    sizes = sizes or {}
    parts = []
    for key, label in REFERENCE_ROLES:
        size = sizes.get(key)
        size_line = ""
        if size:
            size_line = f"\nsize: original {size['original']} -> resized {size['resized']} ({size['note']})"
        parts.append(f"{label}:\n{summaries.get(key, 'not connected')}{size_line}")
    return "\n\n".join(parts)


def _prompt_summary(task_mode, style_mode, summaries):
    role_state = []
    for key, label in REFERENCE_ROLES:
        state = "connected" if summaries.get(key) and summaries[key] != "not connected" else "not connected"
        role_state.append(f"{label.lower()}: {state}")
    return "\n".join(
        [
            f"task_mode: {task_mode}",
            f"style_mode: {style_mode}",
            *role_state,
        ]
    )


def _contains_any(text, keywords):
    lowered = str(text or "").lower()
    return any(keyword in lowered for keyword in keywords)


def _validation_report(task_mode, summaries, sizes=None):
    sizes = sizes or {}
    warnings = []

    main_connected = summaries.get("main_character") != "not connected"
    secondary_connected = summaries.get("secondary_character") != "not connected"
    pose = summaries.get("pose", "")
    outfit = summaries.get("outfit", "")
    background = summaries.get("background", "")
    secondary = summaries.get("secondary_character", "")

    if not main_connected and task_mode.startswith("Character"):
        warnings.append("Main character image is not connected.")
    if "Interaction" in task_mode and not secondary_connected:
        warnings.append("Interaction mode selected but secondary character image is not connected.")
    if task_mode == "Full Character Compose" and not secondary_connected:
        warnings.append("Full Character Compose can use secondary character, but none is connected.")
    if _contains_any(outfit, ("person", "face", "portrait", "human", "woman", "man", "girl", "boy")):
        warnings.append("Outfit reference appears to contain a visible person; facial traits may leak.")
    if _contains_any(background, ("foreground human", "person", "portrait", "woman", "man", "girl", "boy")):
        warnings.append("Background reference may contain a foreground human subject.")
    if _contains_any(pose, ("two-person", "two person", "two people", "couple", "facing each other")):
        warnings.append("Pose reference appears to be a two-person composition.")
    if secondary_connected and _contains_any(secondary, ("dominant", "close-up", "foreground", "large portrait")):
        warnings.append("Secondary character may dominate the frame if main subject wording is weak.")

    status = "OK" if not warnings else "CHECK"
    if not warnings:
        warnings = ["none"]
    size_lines = []
    for key, label in REFERENCE_ROLES:
        size = sizes.get(key)
        if size:
            size_lines.append(f"- {label}: original {size['original']} -> resized {size['resized']} ({size['note']})")
    sections = ["status: " + status, "warnings:", *[f"- {warning}" for warning in warnings]]
    if size_lines:
        sections += ["reference_sizes:", *size_lines]
    return "\n".join(sections)


def _final_prompt_request(task_mode, style_mode, analysis_mode, goal_ko, reference_summary, prompt_summary, selected_blocks_text="", face_swap=False, product_swap=False, character_swap=False):
    pattern = "\n".join(f"- {line}" for line in TASK_PATTERNS.get(task_mode, []))
    booster = STYLE_BOOSTERS.get(style_mode, STYLE_BOOSTERS["cinematic"])
    length_rule = "Keep the final English prompt concise, about 70-110 words." if analysis_mode == "balanced" else "Keep the final English prompt concise, about 45-80 words."
    selected_section = ""
    selected_rule = ""
    if selected_blocks_text:
        selected_section = f"""

User-selected ordered composition blocks (authoritative):
{selected_blocks_text}"""
        selected_rule = "\n- The user-selected ordered blocks are authoritative: include every block, keep their order of importance, and do not add characters or elements that were not selected."
    if face_swap:
        selected_rule += (
            "\n- FACE SWAP (face only) is active: the body/character reference defines body, build, hair, pose, and clothing ONLY"
            " — never its face, expression, or identity. Facial identity and expression come exclusively from the face reference."
            " Describe exactly one face (the face reference's); do not mention the body reference's smile, expression, or facial features."
        )
    if product_swap:
        selected_rule += (
            "\n- PRODUCT SWAP is active: keep the scene, person, pose, and background from the character reference."
            " Replace only the held/displayed product with the product reference. Describe exactly one product"
            " (the new product reference's form, material, label, and shape); do not describe the original product,"
            " and do not adopt the product reference's background, lighting, or studio/packshot presentation."
        )
    if character_swap:
        selected_rule += (
            "\n- CHARACTER SWAP is active: keep the pose, composition, scene, and background from the first character"
            " reference (the scene template). Replace ONE person with the second character reference's full identity"
            " (face, hair, body). If the goal specifies which person (e.g. left/right, foreground/background, by"
            " description), replace only that person and keep every other person in the scene unchanged; if it does not"
            " specify, replace the main/foreground subject. Do not describe the replaced person's original identity;"
            " any other people keep their own appearance."
        )
    return f"""You are a Flux2 Klein prompt director.

The user writes the goal in Korean. Convert it into one coherent English positive prompt.

Task mode:
{task_mode}

Style mode:
{style_mode}
Style booster:
{booster}

User goal in Korean:
{goal_ko}

Reference summaries:
{reference_summary}

Prompt summary:
{prompt_summary}{selected_section}

Task assembly rules:
{pattern}

Global rules:{selected_rule}
- The main character reference controls the main identity and facial traits.
- Use each reference only for its assigned role.
- Never make the user write "image 1 / image 2"; express the reference relationships naturally.
- If style or product references are connected, use them only for visual style/product form, not for identity.
- Avoid copying identity from outfit/background references unless they are assigned as characters.
- Write final_prompt_en in English only.
- Also write a short Korean summary of the intended composition.
- {length_rule}
- No markdown tables.

Return exactly:
final_prompt_en:
...
final_prompt_ko:
..."""


def _parse_final_response(raw, fallback_en, fallback_ko):
    text = str(raw or "").strip()
    lower = text.lower()
    en_marker = "final_prompt_en:"
    ko_marker = "final_prompt_ko:"
    en = ""
    ko = ""
    if en_marker in lower and ko_marker in lower:
        en_start = lower.find(en_marker) + len(en_marker)
        ko_start = lower.find(ko_marker)
        en = text[en_start:ko_start].strip()
        ko = text[ko_start + len(ko_marker):].strip()
    if not en:
        en = fallback_en
    if not ko:
        ko = fallback_ko
    return en.strip(), ko.strip()


def _fallback_prompt(task_mode, style_mode, goal_ko, summaries):
    booster = STYLE_BOOSTERS.get(style_mode, "")
    clauses = [goal_ko.strip() or "Compose the scene from the assigned references."]
    if summaries.get("main_character") != "not connected":
        clauses.append("Preserve the identity and facial traits from the main character reference.")
    if summaries.get("secondary_character") != "not connected" and ("Interaction" in task_mode or task_mode == "Full Character Compose"):
        clauses.append("Include the secondary character as an interaction partner while keeping the main character dominant.")
    if summaries.get("pose") != "not connected":
        clauses.append("Use the pose and composition from the pose reference.")
    if summaries.get("outfit") != "not connected":
        clauses.append("Borrow clothing and styling from the outfit reference without copying its identity.")
    if summaries.get("background") != "not connected":
        clauses.append("Use a setting inspired by the background reference.")
    if booster:
        clauses.append(booster)
    return " ".join(clauses)


def _compose_selection(clip, active_bundle, selection_blocks, summaries, analysis_mode, seed):
    """Turn the ordered button-panel selection into authoritative bundle data.

    Returns (manual_blocks, manual_selections, ordered_lines, negative_text,
    extra_flags). ``manual_blocks`` feed the bundle prompt_blocks, while
    ``ordered_lines`` are injected into the LLM final-prompt request so the
    model only assembles the user-chosen blocks, in order.
    """
    manual_blocks = []
    manual_selections = {}
    ordered_lines = []
    negative_text = ""
    extra_flags = {}
    extra_summaries = {}

    # Face swap (face only): the character/body reference must contribute body,
    # build, hair, pose and clothing — never its face. So when it's active we
    # annotate the ordered lines the LLM sees to suppress the body's face.
    face_swap_active = any(
        isinstance(b, dict) and b.get("kind") == "flag" and b.get("flag") == "face_swap"
        for b in selection_blocks
    )
    # Product swap: keep the scene/person from the character reference and replace
    # only the held/displayed product with the prop reference (prop form only).
    product_swap_active = any(
        isinstance(b, dict) and b.get("kind") == "flag" and b.get("flag") == "product_swap"
        for b in selection_blocks
    )
    # Character swap: keep the scene/pose from the first character (A) and place
    # the second character's (B) full identity into it.
    character_swap_active = any(
        isinstance(b, dict) and b.get("kind") == "flag" and b.get("flag") == "character_swap"
        for b in selection_blocks
    )

    for block in selection_blocks:
        kind = str(block.get("kind") or "").strip()
        if kind == "reference":
            role = str(block.get("role") or "").strip()
            if not role:
                continue
            category = SELECTION_CATEGORY.get(role, "character")
            label = REFERENCE_ROLE_LABELS.get(role) or str(block.get("label") or role)
            summary_role = SELECTION_SUMMARY_ROLE.get(role)
            text = ""
            if summary_role and summaries.get(summary_role) not in (None, "", "not connected"):
                text = summaries[summary_role]
            else:
                image = _bundle_image(active_bundle, role)
                if _connected(image):
                    if role not in extra_summaries:
                        summary, _meta = _summarize_reference(
                            clip,
                            role,
                            label,
                            image,
                            analysis_mode,
                            int(seed) + 40 + len(extra_summaries),
                            hint=EXTRA_ROLE_HINTS.get(role),
                        )
                        extra_summaries[role] = summary if summary != "not connected" else ""
                    text = extra_summaries[role]
            line_label = label
            if face_swap_active and category == "character":
                line_label = f"{label} (BODY ONLY — body, build, hair, pose, clothing; ignore its face/expression/identity)"
            elif character_swap_active and role in ("character_a", "main_character"):
                line_label = f"{label} (SCENE & POSE — pose, composition, scene, background, and any other people present; only the targeted person is replaced, do NOT describe that person's original identity/face)"
            elif character_swap_active and role in ("character_b", "secondary_character"):
                line_label = f"{label} (NEW PERSON — full identity: face, hair, body of the person to place into the scene)"
            elif product_swap_active and category == "character":
                line_label = f"{label} (SCENE — person, pose, scene, background, composition; do NOT describe the product/object being held — it will be replaced)"
            elif face_swap_active and category == "face":
                line_label = f"{label} (FACE IDENTITY — facial identity and expression only)"
            elif product_swap_active and category == "prop":
                line_label = f"{label} (NEW PRODUCT — product form, material, label, shape only; ignore its background, lighting, and studio presentation)"
            manual_selections.setdefault(category, role)
            if text:
                manual_blocks.append({"category": category, "role": role, "text": text})
                ordered_lines.append(f"[{category}] {line_label}: {text}")
            else:
                ordered_lines.append(f"[{category}] {line_label}: (selected, image not connected)")
        elif kind == "flag":
            flag = str(block.get("flag") or "").strip()
            if flag == "face_swap":
                extra_flags["face_swap"] = True
                extra_flags["reference_order"] = "body_first_face_second"
                ordered_lines.append(
                    "[flag] Face swap (face only): keep body, build, hair, pose, and clothing from the body/character reference; "
                    "take facial identity and expression ONLY from the face reference; do not describe the body reference's face."
                )
            elif flag == "product_swap":
                extra_flags["product_swap"] = True
                extra_flags["reference_order"] = "product_swap"
                ordered_lines.append(
                    "[flag] Product swap: keep the person, pose, scene, and background from the character reference; "
                    "replace the product/object they hold or display with the product reference (Prop). "
                    "Use the Prop only for product form, material, and label — ignore the Prop's own background and studio presentation."
                )
            elif flag == "character_swap":
                extra_flags["character_swap"] = True
                extra_flags["reference_order"] = "character_swap"
                ordered_lines.append(
                    "[flag] Character swap: keep the pose, composition, scene, and background from the first character (Character A); "
                    "replace ONE person with the second character's (Character B) full identity — face, hair, body. "
                    "If the goal names which person (left/right, foreground/background, by description), replace only that person and "
                    "keep every other person in the scene unchanged; otherwise replace the main/foreground subject. "
                    "Do not describe Character A's face or the swapped person's original identity."
                )
        elif kind == "modifier":
            category = str(block.get("category") or "modifier").strip()
            text = str(block.get("text") or "").strip()
            if not text:
                continue
            manual_blocks.append({"category": category, "role": f"{category}_modifier", "text": text})
            ordered_lines.append(f"[{category}] {text}")
        elif kind == "negative":
            text = str(block.get("text") or "").strip()
            if text:
                negative_text = text
                ordered_lines.append(f"[negative] avoid: {text}")
        elif kind == "custom":
            text = str(block.get("text") or "").strip()
            if text:
                manual_blocks.append({"category": "custom", "role": "custom", "text": text})
                ordered_lines.append(f"[custom] {text}")

    return manual_blocks, manual_selections, ordered_lines, negative_text, extra_flags


def _bundle_text_blocks(bundle):
    """Collect Reference Board text cards as ordered {category, text} blocks.

    Reads the dedicated ``text_blocks`` list first and falls back to scanning
    ``cards`` for ``type == "text"`` entries so older bundles still work.
    """
    if not isinstance(bundle, dict):
        return []
    blocks = []
    raw = bundle.get("text_blocks")
    if isinstance(raw, list):
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            text = str(entry.get("text") or "").strip()
            if not text:
                continue
            category = str(entry.get("category") or "goal").strip().lower()
            blocks.append({"category": category if category in TEXT_CATEGORIES else "custom", "text": text})
    if not blocks:
        for card in bundle.get("cards", []) if isinstance(bundle.get("cards"), list) else []:
            if not isinstance(card, dict) or str(card.get("type") or "") != "text":
                continue
            text = str(card.get("text") or card.get("prompt") or "").strip()
            if not text:
                continue
            category = str(card.get("category") or "goal").strip().lower()
            blocks.append({"category": category if category in TEXT_CATEGORIES else "custom", "text": text})
    return blocks


def _split_text_blocks(text_blocks):
    """Split text cards by category into goal / style / negative / custom."""
    grouped = {key: [] for key in TEXT_CATEGORIES}
    for block in text_blocks:
        category = block.get("category", "custom")
        grouped.get(category, grouped["custom"]).append(block.get("text", ""))
    return grouped


class ToobusyFlux2KleinPromptDirector:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "clip": ("CLIP",),
                "analysis_mode": (
                    ANALYSIS_MODES,
                    {
                        "default": "balanced",
                        "tooltip": "fast: 짧은 참조 요약과 빠른 조립. balanced: 조금 더 풍부한 요약과 validation.",
                    },
                ),
                "seed": (
                    "INT",
                    {"default": 1, "min": 0, "max": 0xffffffffffffffff, "control_after_generate": True},
                ),
            },
            "optional": {
                "toobusy_bundle": ("TOOBUSY_BUNDLE", {"tooltip": "Universal toobusy Bundle from Reference Board. Preferred for new bundle-centered workflows."}),
                "director_selection_json": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": False,
                        "tooltip": "Serialized button-panel selection (managed by the node UI). When set, the selected blocks are authoritative and the LLM only assembles them in order.",
                    },
                ),
            },
        }

    RETURN_TYPES = ("TOOBUSY_BUNDLE", "STRING", "STRING", "STRING")
    RETURN_NAMES = (
        "toobusy_bundle",
        "resolved_prompt",
        "selected_blocks_json",
        "validation_report",
    )
    FUNCTION = "direct"
    CATEGORY = "toobusy/Plan"

    def direct(
        self,
        clip,
        analysis_mode,
        seed,
        toobusy_bundle=None,
        director_selection_json="",
    ):
        task_mode = DEFAULT_TASK_MODE
        style_mode = DEFAULT_STYLE_MODE
        analysis_mode = _mode(analysis_mode, ANALYSIS_MODES, "balanced")
        active_bundle = toobusy_bundle
        selection_blocks = _parse_selection(director_selection_json)
        text_blocks = _bundle_text_blocks(active_bundle)
        grouped_text = _split_text_blocks(text_blocks)
        images = {
            "main_character": _bundle_image(active_bundle, "main_character"),
            "secondary_character": _bundle_image(active_bundle, "secondary_character"),
            "pose": _bundle_image(active_bundle, "pose"),
            "outfit": _bundle_image(active_bundle, "outfit"),
            "background": _bundle_image(active_bundle, "background"),
            "style": _bundle_image(active_bundle, "style"),
            "product": _bundle_image(active_bundle, "product"),
        }
        # Intent now comes from "Goal" text cards plus the board global note.
        goal_parts = [part.strip() for part in grouped_text["goal"] if part.strip()]
        goal_ko = "\n\n".join(goal_parts)
        bundle_note = _bundle_note(active_bundle)
        if bundle_note and bundle_note not in goal_ko:
            prefix = f"{goal_ko}\n\n" if goal_ko else ""
            goal_ko = f"{prefix}Reference Board global note:\n{bundle_note}"

        summaries = {}
        sizes = {}
        for index, (role_key, role_label) in enumerate(REFERENCE_ROLES):
            summary, size_meta = _summarize_reference(
                clip,
                role_key,
                role_label,
                images.get(role_key),
                analysis_mode,
                int(seed) + index,
            )
            summaries[role_key] = summary
            if size_meta:
                sizes[role_key] = size_meta

        reference_summary = _format_reference_summary(summaries, sizes)
        prompt_summary = _prompt_summary(task_mode, style_mode, summaries)
        # No task_mode anymore: keep only the reference-leak warnings.
        validation_report = _validation_report("", summaries, sizes)
        fallback_en = _fallback_prompt(task_mode, style_mode, goal_ko, summaries)
        fallback_ko = f"[한글 요약]\n{goal_ko.strip()}" if goal_ko.strip() else "[한글 요약]\n버튼 선택 기반 구성"

        # Manual composition is active when the user selected buttons OR added
        # any text cards. Otherwise fall back to the legacy auto-compose.
        has_manual = bool(selection_blocks) or bool(text_blocks)
        manual_blocks = None
        manual_selections = None
        negative_text = None
        extra_flags = None
        selected_blocks_text = ""
        if has_manual:
            if selection_blocks:
                (
                    manual_blocks,
                    manual_selections,
                    ordered_lines,
                    negative_text,
                    extra_flags,
                ) = _compose_selection(clip, active_bundle, selection_blocks, summaries, analysis_mode, int(seed))
            else:
                manual_blocks, manual_selections, ordered_lines, negative_text, extra_flags = [], {}, [], "", {}
            # Fold Reference Board text cards into the ordered composition.
            for style_text in grouped_text["style"]:
                st = style_text.strip()
                if st:
                    manual_blocks.append({"category": "style", "role": "style_text", "text": st})
                    ordered_lines.append(f"[style] {st}")
            for custom_text in grouped_text["custom"]:
                ct = custom_text.strip()
                if ct:
                    manual_blocks.append({"category": "custom", "role": "custom", "text": ct})
                    ordered_lines.append(f"[custom] {ct}")
            neg_cards = [t.strip() for t in grouped_text["negative"] if t.strip()]
            if neg_cards:
                joined_neg = ", ".join(neg_cards)
                negative_text = f"{negative_text}, {joined_neg}" if negative_text else joined_neg
                ordered_lines.append(f"[negative] avoid: {joined_neg}")
            selected_blocks_text = "\n".join(
                f"{index}. {line}" for index, line in enumerate(ordered_lines, start=1)
            )

        face_swap_active = bool((extra_flags or {}).get("face_swap"))
        product_swap_active = bool((extra_flags or {}).get("product_swap"))
        character_swap_active = bool((extra_flags or {}).get("character_swap"))
        final_request = _final_prompt_request(
            task_mode,
            style_mode,
            analysis_mode,
            goal_ko,
            reference_summary,
            prompt_summary,
            selected_blocks_text,
            face_swap=face_swap_active,
            product_swap=product_swap_active,
            character_swap=character_swap_active,
        )
        raw_final = _generate_text(
            clip,
            final_request,
            max_length=_final_max_length(analysis_mode),
            seed=int(seed) + 20,
        )
        final_prompt_en, final_prompt_ko = _parse_final_response(raw_final, fallback_en, fallback_ko)
        out_bundle = _update_bundle(
            active_bundle,
            final_prompt_en,
            final_prompt_ko,
            summaries,
            task_mode,
            style_mode,
            manual_blocks=manual_blocks,
            manual_selections=manual_selections,
            negative_prompt=negative_text,
            extra_flags=extra_flags,
        )
        selected_blocks_json = json.dumps(out_bundle.get("prompt_blocks", []), ensure_ascii=False, indent=2)

        return (
            out_bundle,
            final_prompt_en,
            selected_blocks_json,
            validation_report,
        )


NODE_CLASS_MAPPINGS = {
    "ToobusyFlux2KleinPromptDirector": ToobusyFlux2KleinPromptDirector,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ToobusyFlux2KleinPromptDirector": "toobusy Flux2 Klein Prompt Director",
}
