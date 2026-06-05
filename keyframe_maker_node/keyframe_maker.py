from ..ltx23_compact_sampler_node.ltx23_compact_sampler import _call_node


PRODUCT_BRIEF_PROMPT = """Analyze the product image and create a compact product brief for a beauty commercial storyboard.

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
key_beauty_appeal:
human_usage_needed:

Rules:
- Be literal and concise.
- Focus only on the visible product.
- Do not invent brand names.
- If text is unreadable, write "unreadable".
- If there is no label, write "none".
- Keep each field short.
- English only."""


SHOT_BEATS_TEMPLATE = """You are a storyboard planner.

Create exactly {SHOT_COUNT} short visual beats for a short commercial.

Product brief:
{PRODUCT_BRIEF}

Core idea:
{IDEA}

Style:
{STYLE}

Fixed elements:
{FIXED}

Rules:
- Output exactly {SHOT_COUNT} lines.
- Each line must describe one shot beat only.
- Each line must be short, under 12 words.
- Keep the sequence visually progressive.
- Keep the same product and same character identity.
- No numbering.
- No explanations.
- No blank lines.
- English only."""


KEYFRAME_PROMPTS_TEMPLATE = """You are writing image-generation prompts for storyboard keyframes.

Expand each shot beat into one cinematic image prompt.

Shot beats:
{BEATS}

Product brief:
{PRODUCT_BRIEF}

Global style:
{STYLE}

Fixed elements that must remain consistent in every shot:
{FIXED}

Rules:
- Output exactly {SHOT_COUNT} lines.
- One line = one final image prompt.
- Each line should be 25 to 40 words.
- Keep the same product and same character identity across all lines.
- Make each shot visually distinct and sequential.
- Include camera/composition cues naturally.
- No numbering.
- No explanations.
- No blank lines.
- English only."""


KOREAN_STORY_TEMPLATE = """You are a Korean storyboard interpreter for AI-generated commercial keyframes.

Your job is to read the generated keyframe prompts and explain what kind of commercial story they represent.

Input information:

Product brief:
{PRODUCT_BRIEF}

Original idea:
{IDEA}

Visual style:
{STYLE}

Shot beats:
{BEATS}

Final keyframe prompts:
{FINAL_PROMPTS}

Rules:
- Output in Korean only.
- Do not rewrite the prompts.
- Do not generate new prompts.
- Do not mention technical prompt words unless necessary.
- Explain the story in a way that a non-prompt user can understand.
- Focus on what happens in each keyframe, the emotional flow, and the advertising intention.
- If the sequence feels inconsistent, mention it briefly.
- If the product identity seems unclear or changes between shots, mention it briefly.
- Keep the answer concise and easy to read.
- Do not use markdown tables.
- Do not add extra unrelated suggestions.

Output format:

[광고 한 줄 요약]
한 문장으로 이 광고가 어떤 분위기와 메시지를 가진 광고인지 설명한다.

[전체 스토리 흐름]
2~4문장으로 키프레임들이 어떤 순서로 이어지는지 설명한다.

[컷별 해석]
1컷: ...
2컷: ...
3컷: ...
4컷: ...
5컷: ...
6컷: ...

[의도와 분위기]
이 키프레임들이 전달하려는 제품 이미지, 감정, 광고 톤을 간단히 설명한다.

[체크 포인트]
제품 일관성, 장면 흐름, 광고 전달력 관점에서 주의할 점이 있으면 1~3개만 적는다."""


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


class ToobusyKeyframeMaker:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "clip": ("CLIP",),
                "product_image": ("IMAGE",),
                "idea": (
                    "STRING",
                    {
                        "default": "한 여성이 집안에서 향수를 공중에 뿌리자, 집이 갑자기 궁전으로 변하며 여자의 모습도 화려한 공주로 변하게된다.",
                        "multiline": True,
                    },
                ),
                "style": (
                    "STRING",
                    {"default": "cinematic, 고급 향수 광고, elegant composition", "multiline": True},
                ),
                "fixed_elements": ("STRING", {"default": "금빛 조명,웜톤", "multiline": True}),
                "shot_count": ("INT", {"default": 6, "min": 1, "max": 24}),
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
                "product_brief_override": ("STRING", {"default": "", "multiline": True}),
                "shot_beats_override": ("STRING", {"default": "", "multiline": True}),
            },
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("product_brief", "shot_beats", "keyframe_prompts", "korean_story")
    FUNCTION = "make"
    CATEGORY = "toobusy/Keyframe"

    def make(
        self,
        clip,
        product_image,
        idea,
        style,
        fixed_elements,
        shot_count,
        seed,
        product_brief_override="",
        shot_beats_override="",
    ):
        product_brief = product_brief_override.strip()
        if not product_brief:
            product_brief = _generate_text(
                clip,
                PRODUCT_BRIEF_PROMPT,
                max_length=512,
                seed=seed,
                image=product_image,
            ).strip()

        shot_beats = shot_beats_override.strip()
        if not shot_beats:
            shot_beats_prompt = _format_template(
                SHOT_BEATS_TEMPLATE,
                SHOT_COUNT=shot_count,
                PRODUCT_BRIEF=product_brief,
                IDEA=idea,
                STYLE=style,
                FIXED=fixed_elements,
            )
            shot_beats = _generate_text(clip, shot_beats_prompt, max_length=512, seed=seed + 1).strip()

        keyframe_prompt = _format_template(
            KEYFRAME_PROMPTS_TEMPLATE,
            SHOT_COUNT=shot_count,
            BEATS=shot_beats,
            PRODUCT_BRIEF=product_brief,
            STYLE=style,
            FIXED=fixed_elements,
        )
        keyframe_prompts = _generate_text(clip, keyframe_prompt, max_length=2048, seed=seed + 2).strip()

        korean_story_prompt = _format_template(
            KOREAN_STORY_TEMPLATE,
            PRODUCT_BRIEF=product_brief,
            IDEA=idea,
            STYLE=style,
            BEATS=shot_beats,
            FINAL_PROMPTS=keyframe_prompts,
        )
        korean_story = _generate_text(clip, korean_story_prompt, max_length=2048, seed=seed + 3).strip()

        return {
            "ui": {
                "text": [
                    "Product brief:",
                    product_brief,
                    "Shot beats:",
                    shot_beats,
                    "Keyframe prompts:",
                    keyframe_prompts,
                    "Korean story:",
                    korean_story,
                ]
            },
            "result": (product_brief, shot_beats, keyframe_prompts, korean_story),
        }


NODE_CLASS_MAPPINGS = {
    "ToobusyKeyframeMaker": ToobusyKeyframeMaker,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ToobusyKeyframeMaker": "toobusy Keyframe Maker",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
