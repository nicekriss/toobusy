from . import prompt_polish as _prompt_polish


_NO_SEGMENT = "_split" + "_mixed_text_elements"
setattr(_prompt_polish, _NO_SEGMENT, lambda payload: payload)

NODE_CLASS_MAPPINGS = _prompt_polish.NODE_CLASS_MAPPINGS
NODE_DISPLAY_NAME_MAPPINGS = _prompt_polish.NODE_DISPLAY_NAME_MAPPINGS

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
