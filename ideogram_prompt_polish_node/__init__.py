from . import prompt_polish as _prompt_polish
from ..keyframe_maker_node import keyframe_maker as _keyframe_maker


_NO_SEGMENT = "_split" + "_mixed_text_elements"
setattr(_prompt_polish, _NO_SEGMENT, lambda payload: payload)

_ORIGINAL_BUILD_PROMPT = _prompt_polish._build_prompt
_ORIGINAL_GENERATE_TEXT = _keyframe_maker._generate_text


def _build_prompt_compact(*args, **kwargs):
    prompt = _ORIGINAL_BUILD_PROMPT(*args, **kwargs)
    return prompt + "\n\nCompact JSON target: 5-8 major layout regions, one box per grouped label or visual block, skip minor details."


def _generate_text_capped(*args, **kwargs):
    if int(kwargs.get("max_length", 0) or 0) > 1024:
        kwargs["max_length"] = 1024
    return _ORIGINAL_GENERATE_TEXT(*args, **kwargs)


_prompt_polish._build_prompt = _build_prompt_compact
_keyframe_maker._generate_text = _generate_text_capped

NODE_CLASS_MAPPINGS = _prompt_polish.NODE_CLASS_MAPPINGS
NODE_DISPLAY_NAME_MAPPINGS = _prompt_polish.NODE_DISPLAY_NAME_MAPPINGS

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
