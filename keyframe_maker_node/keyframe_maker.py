import json
import re

from ..ltx23_compact_sampler_node.ltx23_compact_sampler import _call_node


PRODUCT_IMAGE_MODES = ["exact product identity", "design reference only", "packaging/form reference"]


PRODUCT_BRIEF_PROMPT = """Analyze the product image and create a compact product/reference brief for a storyboard.

Core idea:
{IDEA}

Style:
{STYLE}

Fixed elements:
{FIXED}

Product image interpretation mode:
{PRODUCT_IMAGE_MODE}

Return only this format:

story_product_category:
story_product_usage:
story_product_action:
story_ad_grammar:
reference_container_shape:
reference_material:
reference_finish:
reference_color:
reference_top_structure:
reference_visual_tone:
reference_branding_density:
reference_apparent_category:

Rules:
- Be literal and concise.
- If the core idea explicitly defines product category or product behavior, treat the core idea as the source of truth.
- The core idea determines what the product is, how it is used, and what advertising grammar the sequence follows.
- If product_image_mode is "exact product identity", the image may define the actual product category and usage.
- If product_image_mode is "design reference only", use the image mainly for shape, material, color, silhouette, finish, and packaging tone; product category and use come from the core idea.
- If product_image_mode is "packaging/form reference", prioritize the core idea for product category and use, but borrow the container structure more strongly.
- Separate story-side product definition from reference-side visual design.
- Do not invent brand names.
- If text is unreadable, write "unreadable".
- If there is no label, write "none".
- Keep each field short.
- English only."""


SUBJECT_BRIEF_PROMPT = """Analyze the reference image and create a compact subject/visual brief for a {MODE_LABEL} storyboard.

Return only this format:

main_subject:
subject_type:
outfit_or_styling:
visible_identity_traits:
pose_or_expression:
setting_or_background:
dominant_colors:
visual_mood:
important_props:
continuity_notes:

Rules:
- Be literal and concise.
- Focus only on what is visible in the image.
- Do not invent names or backstory.
- If the subject is a human wearing a costume, describe them as a human wearing a costume.
- Do not transform a human costume into a literal animal, insect, monster, creature, or hybrid body unless the user's text explicitly asks for that transformation.
- Preserve human face, human body proportions, and ordinary costume material when visible.
- If text is unreadable, write "unreadable".
- Keep each field short.
- English only."""


TEXT_BRIEF_TEMPLATE = """Create a compact reference brief for a {MODE_LABEL} storyboard from the user's text inputs.

Core idea:
{IDEA}

Style:
{STYLE}

Fixed elements:
{FIXED}

Return only this format:

main_subject:
subject_type:
outfit_or_styling:
setting_or_background:
dominant_colors:
visual_mood:
important_props:
continuity_notes:

Rules:
- Be literal and concise.
- Do not invent names or unrelated backstory.
- Treat fixed elements as the strongest identity/continuity rules.
- If the subject is described as a human wearing a costume, keep them human.
- Do not transform a human costume into a literal animal, insect, monster, creature, or hybrid body unless the user's text explicitly asks for that transformation.
- Keep each field short.
- English only."""


PRODUCT_TEXT_BRIEF_TEMPLATE = """Create a compact product brief for a product commercial storyboard from the user's text inputs.

Core idea:
{IDEA}

Style:
{STYLE}

Fixed elements:
{FIXED}

Return only this format:

product_category:
product_type:
product_form:
main_material:
main_shape:
cap_or_closure:
visible_color:
label_or_branding:
usage_context:
key_appeal:
human_usage_needed:
must_keep_product_details:

Rules:
- Be literal and concise.
- If a product detail is not provided, infer only a generic safe value from the core idea.
- Do not invent brand names.
- Treat fixed elements as the strongest continuity rules.
- Keep product shape, material, color, and label rules stable across shots.
- Keep each field short.
- English only."""


SHOT_BEATS_TEMPLATE = """You are a storyboard planner.

Create exactly {SHOT_COUNT} short visual beats for a {MODE_LABEL}.

Reference brief:
{BRIEF}

Core idea:
{IDEA}

Style:
{STYLE}

Fixed elements:
{FIXED}

Product interpretation rules:
{PRODUCT_RULES}

Rules:
- Output exactly {SHOT_COUNT} lines.
- Each line must describe one shot beat only.
- Each line must be short, under 12 words.
- Keep the sequence visually progressive.
- Preserve the same product/main subject and same character identity when present.
- Allow planned location, outfit, lighting, mood, or transformation changes when the user's core idea requires them.
- If the reference shows a human in a costume, keep them human unless the user's core idea explicitly asks for a creature/monster/hybrid transformation.
- Do not add creature anatomy such as insect eyes, antennae, claws, wings, or exoskeleton unless clearly visible or explicitly requested.
- No numbering.
- No explanations.
- No blank lines.
- English only."""


ANCHOR_TEMPLATE = """Extract continuity anchors and planned story changes from this storyboard brief.

Reference brief:
{BRIEF}

Core idea:
{IDEA}

Style:
{STYLE}

Fixed elements:
{FIXED}

Product interpretation rules:
{PRODUCT_RULES}

Return only this format (one value per line, no extra text):

continuity_character: [main subject identity, face/body/costume traits that must stay consistent. write "none" if absent]
continuity_product_or_prop: [product or signature prop details that must stay consistent. write "none" if absent]
continuity_palette_lighting: [stable color and lighting rules]
continuity_camera_style: [overall camera/composition style]
story_arc_changes: [what should intentionally change across the sequence]
final_state: [what the last shot should visually resolve into]

Rules:
- Be specific and literal.
- Preserve only elements that truly must stay consistent.
- Do not freeze the setting, costume, or mood if the user's idea requires a transformation.
- Pull only from the reference brief, core idea, style, and fixed elements.
- Keep each value under 18 words.
- English only."""


KEYFRAME_PROMPTS_TEMPLATE = """You are writing image-generation prompts for storyboard keyframes.

Expand each shot beat into one cinematic still-image prompt.

Shot beats:
{BEATS}

Reference brief:
{BRIEF}

Continuity anchors and planned story arc:
{ANCHOR}

Global style:
{STYLE}

Fixed elements that must remain consistent in every shot:
{FIXED}

Product interpretation rules:
{PRODUCT_RULES}

Rules:
- Output exactly {SHOT_COUNT} lines.
- One line = one final still-image prompt.
- Each line should be 25 to 45 words.
- Preserve the continuity anchors across every line.
- Follow the story_arc_changes and final_state when the sequence requires transformation or progression.
- Keep the same product/main subject and same character identity across all lines when present.
- If the reference shows a human wearing a costume, write it as a realistic human in that costume unless the user explicitly asks for a creature/monster/hybrid transformation.
- Do not turn costume details into literal creature anatomy unless explicitly requested.
- Avoid insectoid, monster, hybrid, multifaceted eyes, antennae, claws, wings, or exoskeleton unless the reference visibly has them or the user explicitly asks for them.
- Make each shot visually distinct and sequential.
- Include camera/composition cues naturally.
- Do not describe motion blur unless it is visible in a still frame.
- No numbering.
- No explanations.
- No blank lines.
- English only."""


TRANSITION_PROMPTS_TEMPLATE = """You are writing video transition prompts between storyboard keyframes.

Create exactly {TRANSITION_COUNT} motion prompts for the transitions between the keyframes.

Shot beats:
{BEATS}

Reference brief:
{BRIEF}

Continuity anchors and planned story arc:
{ANCHOR}

Global style:
{STYLE}

Fixed elements:
{FIXED}

Product interpretation rules:
{PRODUCT_RULES}

Rules:
- Output exactly {TRANSITION_COUNT} lines.
- One line = motion from shot N to shot N+1.
- Each line should be 18 to 35 words.
- Describe camera motion, subject action, environmental change, or transformation between adjacent keyframes.
- Preserve continuity anchors while allowing the planned story arc to change over time.
- Do not introduce new characters, props, products, logos, or unrelated locations.
- No numbering.
- No explanations.
- No blank lines.
- English only."""


KOREAN_STORY_TEMPLATE = """You are a Korean storyboard interpreter for AI-generated storyboard keyframes.

Your job is to read the generated keyframe prompts and explain what kind of {MODE_LABEL} story they represent.

Input information:

Reference brief:
{BRIEF}

Original idea:
{IDEA}

Visual style:
{STYLE}

Shot beats:
{BEATS}

Continuity anchors and story arc:
{ANCHOR}

Final keyframe prompts:
{FINAL_PROMPTS}

Transition/motion prompts:
{TRANSITION_PROMPTS}

Rules:
- Output in Korean only.
- Do not rewrite the prompts.
- Do not generate new prompts.
- Do not mention technical prompt words unless necessary.
- Explain the story in a way that a non-prompt user can understand.
- Focus on what happens in each keyframe, the emotional flow, and the advertising/story intention.
- If the sequence feels inconsistent, mention it briefly.
- If the product identity, character identity, or transformation arc seems unclear, mention it briefly.
- Keep the answer concise and easy to read.
- Do not use markdown tables.
- Do not add extra unrelated suggestions.

Output format:

[한 줄 요약]
한 문장으로 이 시퀀스가 어떤 분위기와 메시지를 가졌는지 설명한다.

[전체 스토리 흐름]
2~4문장으로 키프레임들이 어떤 순서로 이어지는지 설명한다.

[컷별 해석]
{CUT_LIST}

[의도와 분위기]
이 키프레임들이 전달하려는 이미지, 감정, 장르 톤을 간단히 설명한다.

[체크 포인트]
레퍼런스 일관성, 장면 흐름, 전달력 관점에서 주의할 점이 있으면 1~3개만 적는다."""


_LINE_PREFIX_RE = re.compile(r"^\s*(?:[-*•]\s*|\d+[\).\:\-]\s*|shot\s*\d+\s*[:.)-]\s*|scene\s*\d+\s*[:.)-]\s*)", re.IGNORECASE)
_EXPLANATION_RE = re.compile(r"^\s*(?:note|notes|explanation|here are|sure[,!]?|overall|summary)\b", re.IGNORECASE)


def _sampling_mode(seed, temperature=0.7, top_k=64, top_p=0.95, min_p=0.05, repetition_penalty=1.05):
    return {
        "sampling_mode": "on",
        "temperature": float(temperature),
        "top_k": int(top_k),
        "top_p": float(top_p),
        "min_p": float(min_p),
        "repetition_penalty": float(repetition_penalty),
        "seed": int(seed),
    }


def _format_template(template, **values):
    result = template
    for key, value in values.items():
        result = result.replace("{" + key + "}", str(value))
    return result


def _mode_label(mode):
    return {
        "Product Commercial": "product commercial",
        "Music Video": "music video",
        "Short Drama": "short drama",
    }.get(mode, "storyboard")


def _product_image_mode(value):
    return value if value in PRODUCT_IMAGE_MODES else "design reference only"


def _product_interpretation_rules(product_image_mode, product_image_present=False):
    mode = _product_image_mode(product_image_mode)
    lines = [
        f"product_image_mode: {mode}",
        "If the core idea explicitly defines the product category or product behavior, treat the core idea as the source of truth.",
        "The core idea determines what the product is, how the product is used, and what kind of advertising grammar the sequence follows.",
    ]
    if product_image_present:
        if mode == "exact product identity":
            lines.append("The product image may define the actual product identity, category, and usage behavior.")
        elif mode == "packaging/form reference":
            lines.append("Use the product image for packaging structure, container form, silhouette, material, finish, color family, and visual tone.")
            lines.append("Do not let the reference image override product category or usage behavior when the core idea is explicit.")
        else:
            lines.append("Use the product image mainly as a visual design reference: silhouette, proportions, material feel, finish, color family, and packaging tone.")
            lines.append("Do not let the reference image override product category or usage behavior.")
        lines.append("If the core idea describes a perfume commercial, the product must be used like a perfume even if the reference resembles skincare packaging.")
        lines.append("If the core idea says perfume: do not switch to skincare application, serum/ampoule/dropper logic, or rubbing product onto skin unless explicitly requested.")
    else:
        lines.append("No product image is connected, so derive both product identity and behavior from the core idea and fixed elements.")
    return "\n".join(lines)


def _brief_prompt_for_mode(mode, product_image_mode="design reference only", idea="", style="", fixed_elements=""):
    if mode == "Product Commercial":
        return _format_template(
            PRODUCT_BRIEF_PROMPT,
            IDEA=idea,
            STYLE=style,
            FIXED=fixed_elements,
            PRODUCT_IMAGE_MODE=_product_image_mode(product_image_mode),
        )

    return _format_template(SUBJECT_BRIEF_PROMPT, MODE_LABEL=_mode_label(mode))


def _text_brief_prompt(mode, idea, style, fixed_elements):
    if mode == "Product Commercial":
        return _format_template(
            PRODUCT_TEXT_BRIEF_TEMPLATE,
            IDEA=idea,
            STYLE=style,
            FIXED=fixed_elements,
        )
    return _format_template(
        TEXT_BRIEF_TEMPLATE,
        MODE_LABEL=_mode_label(mode),
        IDEA=idea,
        STYLE=style,
        FIXED=fixed_elements,
    )


def _clean_llm_lines(text, expected_count=None, allow_empty=False):
    cleaned = []
    for raw_line in str(text or "").replace("\r", "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("```"):
            continue
        if _EXPLANATION_RE.search(line):
            continue
        line = _LINE_PREFIX_RE.sub("", line).strip()
        line = line.strip(" \t\"'`")
        if line:
            cleaned.append(line)

    if expected_count is not None and expected_count > 0 and len(cleaned) > expected_count:
        cleaned = cleaned[:expected_count]

    if not cleaned and allow_empty:
        return []
    return cleaned or [""]


def _line_count(text):
    return len(_clean_llm_lines(text, allow_empty=True))


def _prompt_lines(text, expected_count=None):
    return _clean_llm_lines(text, expected_count=expected_count)


def _lines_to_text(lines):
    return "\n".join([line for line in lines if str(line).strip()])


def _cut_list(shot_count):
    return "\n".join(f"{index}컷: ..." for index in range(1, int(shot_count) + 1))


def _generate_text(clip, prompt, max_length, seed, image=None):
    kwargs = {
        "clip": clip,
        "prompt": prompt,
        "max_length": int(max_length),
        "sampling_mode": _sampling_mode(seed),
        "thinking": False,
        "use_default_template": True,
    }
    if image is not None:
        kwargs["image"] = image

    return _call_node("TextGenerate", **kwargs)[0]


def _prompt_relay_block(keyframe_lines):
    blocks = []
    for index, prompt in enumerate(keyframe_lines, start=1):
        prompt = str(prompt).strip()
        if prompt:
            blocks.append(f"Scene {index}:\n{prompt}")
    return "\n\n".join(blocks)


def _shot_table_json(beat_lines, keyframe_lines, transition_lines):
    rows = []
    total = max(len(beat_lines), len(keyframe_lines))
    for index in range(total):
        rows.append(
            {
                "shot": index + 1,
                "beat": beat_lines[index] if index < len(beat_lines) else "",
                "image_prompt": keyframe_lines[index] if index < len(keyframe_lines) else "",
                "motion_to_next": transition_lines[index] if index < len(transition_lines) else "",
            }
        )
    return json.dumps(rows, ensure_ascii=False, indent=2)


PERFUME_KEYWORDS = (
    "perfume",
    "fragrance",
    "scent",
    "eau de parfum",
    "spray",
    "mist",
    "향수",
    "향",
    "분사",
)
SKINCARE_KEYWORDS = (
    "serum",
    "skincare",
    "ampoule",
    "dropper",
    "cica",
    "needle shot",
    "cream",
    "essence",
    "세럼",
    "앰플",
    "스킨케어",
    "크림",
)


def _contains_keyword(text, keywords):
    lowered = str(text or "").lower()
    return any(keyword.lower() in lowered for keyword in keywords)


def _product_category_hint(text):
    if _contains_keyword(text, PERFUME_KEYWORDS):
        return "perfume"
    if _contains_keyword(text, SKINCARE_KEYWORDS):
        return "skincare"
    return ""


def _product_conflict_warnings(idea, fixed_elements, product_brief, product_image_mode, product_image_present):
    if not product_image_present:
        return []

    mode = _product_image_mode(product_image_mode)
    story_text = f"{idea}\n{fixed_elements}"
    story_hint = _product_category_hint(story_text)
    reference_hint = _product_category_hint(product_brief)
    story_perfume = _contains_keyword(story_text, PERFUME_KEYWORDS)
    story_skincare = _contains_keyword(story_text, SKINCARE_KEYWORDS)
    reference_perfume = _contains_keyword(product_brief, PERFUME_KEYWORDS)
    reference_skincare = _contains_keyword(product_brief, SKINCARE_KEYWORDS)
    warnings = [f"Applied interpretation mode: {mode}."]

    if story_perfume and reference_skincare:
        warnings.append(
            "Product conflict detected: core idea suggests perfume-commercial behavior, but reference image appears to be skincare / serum packaging."
        )
        if mode != "exact product identity":
            warnings.append("Product behavior preserved as perfume-style usage.")
            warnings.append("Product behavior drift risk: the reference image may bias the model toward skincare usage.")
        else:
            warnings.append("Exact product identity mode may allow skincare / serum behavior from the reference image.")
    elif story_skincare and reference_perfume:
        warnings.append(
            "Product conflict detected: core idea suggests skincare behavior, but reference image appears closer to perfume / fragrance packaging."
        )
        if mode != "exact product identity":
            warnings.append("Product behavior preserved as skincare-style usage.")
    elif story_hint and reference_hint and story_hint != reference_hint:
        warnings.append(
            f"Product conflict detected: core idea suggests {story_hint}, but reference image appears closer to {reference_hint}."
        )
        if mode != "exact product identity":
            warnings.append(f"Product behavior preserved as {story_hint}-style usage.")
    elif story_hint:
        warnings.append(f"Story product hint: {story_hint}.")
    elif reference_hint and mode != "exact product identity":
        warnings.append(
            f"Reference product hint: {reference_hint}; core idea remains the source of truth for product behavior."
        )

    return warnings


def _validation_report(output_mode, expected_count, beat_lines, keyframe_lines, transition_lines, product_warnings=None):
    expected_count = int(expected_count)
    expected_transitions = max(0, expected_count - 1)
    beat_count = len([line for line in beat_lines if line])
    keyframe_count = len([line for line in keyframe_lines if line])
    transition_count = len([line for line in transition_lines if line])
    warnings = list(product_warnings or [])

    if beat_count != expected_count:
        warnings.append(f"Shot beat count mismatch: expected {expected_count}, got {beat_count}.")
    if keyframe_count != expected_count:
        warnings.append(f"Keyframe prompt count mismatch: expected {expected_count}, got {keyframe_count}.")
    if output_mode != "fast" and transition_count != expected_transitions:
        warnings.append(f"Transition prompt count mismatch: expected {expected_transitions}, got {transition_count}.")
    if not warnings:
        warnings.append("OK")
    status_ok = warnings == ["OK"] or all(
        warning.startswith("Applied interpretation mode:") or warning.startswith("Story product hint:")
        for warning in warnings
    )

    report = [
        f"output_mode: {output_mode}",
        f"expected_shots: {expected_count}",
        f"actual_shot_beats: {beat_count}",
        f"actual_keyframe_prompts: {keyframe_count}",
    ]
    if output_mode == "fast":
        report.append("transition_prompts: skipped")
    else:
        report.extend(
            [
                f"expected_transitions: {expected_transitions}",
                f"actual_transition_prompts: {transition_count}",
            ]
        )
    report.extend(
        [
            "status: " + ("OK" if status_ok else "CHECK"),
            "warnings:",
            *[f"- {warning}" for warning in warnings],
        ]
    )
    return "\n".join(report)


def _keyframe_max_length(shot_count, output_mode="standard"):
    if output_mode == "fast":
        return min(2048, max(640, int(shot_count) * 130))
    return min(3072, max(768, int(shot_count) * 160))


def _transition_max_length(shot_count):
    return min(2048, max(512, max(0, int(shot_count) - 1) * 120))


def _story_max_length(shot_count):
    return min(2048, max(768, int(shot_count) * 140))


class ToobusyKeyframeMaker:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "clip": ("CLIP",),
                "mode": (["Product Commercial", "Music Video", "Short Drama"], {"default": "Product Commercial"}),
                "output_mode": (
                    ["fast", "standard", "full"],
                    {
                        "default": "standard",
                        "tooltip": "fast: 가장 빠름. 키프레임 이미지 프롬프트까지만 생성 / standard: 영상 제작용. 전환 프롬프트까지 생성 / full: 설명/검수용. 한국어 스토리 해석까지 생성",
                    },
                ),
                "idea": (
                    "STRING",
                    {
                        "default": "한 여성이 집안에서 향수를 공중에 뿌리자, 집이 갑자기 궁전으로 변하며 여자의 모습도 화려한 공주로 변하게된다.",
                        "multiline": True,
                        "tooltip": "광고의 핵심 사건, 변신, 제품 사용 상황을 적습니다.",
                    },
                ),
                "style": (
                    "STRING",
                    {
                        "default": "cinematic, 고급 향수 광고, elegant composition",
                        "multiline": True,
                        "tooltip": "광고 톤, 촬영 스타일, 조명, 구도, 장르 느낌을 적습니다.",
                    },
                ),
                "fixed_elements": (
                    "STRING",
                    {
                        "default": "금빛 조명,웜톤",
                        "multiline": True,
                        "tooltip": "모든 컷에서 반드시 유지할 제품, 인물, 색감, 배경 규칙을 적습니다. 변신해야 하는 요소는 idea에 적어주세요.",
                    },
                ),
                "shot_count": (
                    "INT",
                    {"default": 6, "min": 1, "max": 24, "tooltip": "생성할 키프레임/샷 개수입니다."},
                ),
                "seed": (
                    "INT",
                    {
                        "default": 1,
                        "min": 0,
                        "max": 0xffffffffffffffff,
                        "control_after_generate": True,
                    },
                ),
            },
            "optional": {
                "product_image": (
                    "IMAGE",
                    {
                        "tooltip": "Optional product/reference image. By default this image is used as a visual design reference for shape, material, color, and packaging tone. The core idea still decides what the product is and how it is used. To let the image define product identity, set product_image_mode to exact product identity.",
                    },
                ),
                "product_image_mode": (
                    PRODUCT_IMAGE_MODES,
                    {
                        "default": "design reference only",
                        "tooltip": "exact product identity: image defines product/category. design reference only: idea defines product/use; image supplies shape/material/color. packaging/form reference: idea defines product/use, image form is borrowed more strongly.",
                    },
                ),
                "product_brief_override": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "tooltip": "제품/주제 분석 결과를 직접 넣으면 이미지/텍스트 분석 단계를 건너뜁니다.",
                    },
                ),
                "shot_beats_override": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "tooltip": "샷 비트를 직접 넣으면 샷 비트 생성 단계를 건너뜁니다.",
                    },
                ),
            },
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING", "STRING", "STRING", "STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES = (
        "product_brief",
        "shot_beats",
        "visual_anchor",
        "keyframe_prompts",
        "keyframe_prompt_line",
        "korean_story",
        "transition_prompts",
        "prompt_relay_block",
        "shot_table_json",
        "validation_report",
    )
    OUTPUT_IS_LIST = (False, False, False, False, True, False, False, False, False, False)
    FUNCTION = "make"
    CATEGORY = "toobusy/Plan"

    def make(
        self,
        clip,
        mode,
        output_mode,
        idea,
        style,
        fixed_elements,
        shot_count,
        seed,
        product_brief_override="",
        shot_beats_override="",
        product_image=None,
        product_image_mode="design reference only",
    ):
        output_mode = output_mode if output_mode in {"fast", "standard", "full"} else "standard"
        product_image_mode = _product_image_mode(product_image_mode)
        product_rules = _product_interpretation_rules(product_image_mode, product_image is not None)
        effective_shot_count = int(shot_count)
        product_brief = product_brief_override.strip()
        if not product_brief:
            if product_image is not None:
                product_brief = _generate_text(
                    clip,
                    _brief_prompt_for_mode(mode, product_image_mode, idea, style, fixed_elements),
                    max_length=512,
                    seed=seed,
                    image=product_image,
                ).strip()
            else:
                product_brief = _generate_text(
                    clip,
                    _text_brief_prompt(mode, idea, style, fixed_elements),
                    max_length=512,
                    seed=seed,
                ).strip()

        shot_beats = shot_beats_override.strip()
        if shot_beats:
            shot_beat_lines = _prompt_lines(shot_beats)
            override_line_count = len([line for line in shot_beat_lines if line])
            if override_line_count:
                effective_shot_count = override_line_count
            shot_beats = _lines_to_text(shot_beat_lines)
        else:
            shot_beats_prompt = _format_template(
                SHOT_BEATS_TEMPLATE,
                SHOT_COUNT=effective_shot_count,
                MODE_LABEL=_mode_label(mode),
                BRIEF=product_brief,
                IDEA=idea,
                STYLE=style,
                FIXED=fixed_elements,
                PRODUCT_RULES=product_rules,
            )
            shot_beats_raw = _generate_text(clip, shot_beats_prompt, max_length=512, seed=seed + 1).strip()
            shot_beat_lines = _prompt_lines(shot_beats_raw, expected_count=effective_shot_count)
            shot_beats = _lines_to_text(shot_beat_lines)

        anchor_prompt = _format_template(
            ANCHOR_TEMPLATE,
            BRIEF=product_brief,
            IDEA=idea,
            STYLE=style,
            FIXED=fixed_elements,
            PRODUCT_RULES=product_rules,
        )
        anchor = _generate_text(clip, anchor_prompt, max_length=384, seed=seed + 2).strip()

        keyframe_prompt = _format_template(
            KEYFRAME_PROMPTS_TEMPLATE,
            SHOT_COUNT=effective_shot_count,
            BEATS=shot_beats,
            BRIEF=product_brief,
            ANCHOR=anchor,
            STYLE=style,
            FIXED=fixed_elements,
            PRODUCT_RULES=product_rules,
        )
        keyframe_prompts_raw = _generate_text(
            clip,
            keyframe_prompt,
            max_length=_keyframe_max_length(effective_shot_count, output_mode),
            seed=seed + 3,
        ).strip()
        keyframe_prompt_lines = _prompt_lines(keyframe_prompts_raw, expected_count=effective_shot_count)
        keyframe_prompts = _lines_to_text(keyframe_prompt_lines)

        transition_count = max(0, effective_shot_count - 1)
        transition_lines = []
        if output_mode in {"standard", "full"} and transition_count:
            transition_prompt = _format_template(
                TRANSITION_PROMPTS_TEMPLATE,
                TRANSITION_COUNT=transition_count,
                BEATS=shot_beats,
                BRIEF=product_brief,
                ANCHOR=anchor,
                STYLE=style,
                FIXED=fixed_elements,
                PRODUCT_RULES=product_rules,
            )
            transition_prompts_raw = _generate_text(
                clip,
                transition_prompt,
                max_length=_transition_max_length(effective_shot_count),
                seed=seed + 4,
            ).strip()
            transition_lines = _prompt_lines(transition_prompts_raw, expected_count=transition_count)
        transition_prompts = _lines_to_text(transition_lines)

        prompt_relay_block = _prompt_relay_block(keyframe_prompt_lines)
        shot_table_json = _shot_table_json(shot_beat_lines, keyframe_prompt_lines, transition_lines)
        validation_report = _validation_report(
            output_mode,
            effective_shot_count,
            shot_beat_lines,
            keyframe_prompt_lines,
            transition_lines,
            _product_conflict_warnings(
                idea,
                fixed_elements,
                product_brief,
                product_image_mode,
                product_image is not None,
            ),
        )

        korean_story = ""
        if output_mode == "full":
            korean_story_prompt = _format_template(
                KOREAN_STORY_TEMPLATE,
                MODE_LABEL=_mode_label(mode),
                BRIEF=product_brief,
                IDEA=idea,
                STYLE=style,
                BEATS=shot_beats,
                ANCHOR=anchor,
                FINAL_PROMPTS=keyframe_prompts,
                TRANSITION_PROMPTS=transition_prompts,
                CUT_LIST=_cut_list(effective_shot_count),
            )
            korean_story = _generate_text(
                clip,
                korean_story_prompt,
                max_length=_story_max_length(effective_shot_count),
                seed=seed + 5,
            ).strip()

        return {
            "ui": {
                "text": [
                    "Reference brief:",
                    product_brief,
                    "Shot beats:",
                    shot_beats,
                    "Continuity anchors / story arc:",
                    anchor,
                    "Keyframe image prompts:",
                    keyframe_prompts,
                    "Transition motion prompts:",
                    transition_prompts,
                    "PromptRelay block:",
                    prompt_relay_block,
                    "Shot table JSON:",
                    shot_table_json,
                    "Korean story:",
                    korean_story,
                    "Validation report:",
                    validation_report,
                ]
            },
            "result": (
                product_brief,
                shot_beats,
                anchor,
                keyframe_prompts,
                keyframe_prompt_lines,
                korean_story,
                transition_prompts,
                prompt_relay_block,
                shot_table_json,
                validation_report,
            ),
        }


NODE_CLASS_MAPPINGS = {
    "ToobusyKeyframeMaker": ToobusyKeyframeMaker,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ToobusyKeyframeMaker": "toobusy Keyframe Maker",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
