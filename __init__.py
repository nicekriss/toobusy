"""ComfyUI custom node package entrypoint.

This repository is intended to be cloned into ComfyUI's `custom_nodes` folder
(e.g. `custom_nodes/toobusy`). ComfyUI imports that folder as a Python package,
so this top-level `__init__.py` must expose node mappings.
"""

from .ltx23_compact_sampler_node import (
    NODE_CLASS_MAPPINGS as LTX23_NODE_CLASS_MAPPINGS,
    NODE_DISPLAY_NAME_MAPPINGS as LTX23_NODE_DISPLAY_NAME_MAPPINGS,
)
from .keyframe_maker_node import (
    NODE_CLASS_MAPPINGS as KEYFRAME_NODE_CLASS_MAPPINGS,
    NODE_DISPLAY_NAME_MAPPINGS as KEYFRAME_NODE_DISPLAY_NAME_MAPPINGS,
)
from .z_image_turbo_node import (
    NODE_CLASS_MAPPINGS as Z_IMAGE_NODE_CLASS_MAPPINGS,
    NODE_DISPLAY_NAME_MAPPINGS as Z_IMAGE_NODE_DISPLAY_NAME_MAPPINGS,
)
from .prompt_lines_node import (
    NODE_CLASS_MAPPINGS as PROMPT_LINES_NODE_CLASS_MAPPINGS,
    NODE_DISPLAY_NAME_MAPPINGS as PROMPT_LINES_NODE_DISPLAY_NAME_MAPPINGS,
)

NODE_CLASS_MAPPINGS = {
    **LTX23_NODE_CLASS_MAPPINGS,
    **KEYFRAME_NODE_CLASS_MAPPINGS,
    **Z_IMAGE_NODE_CLASS_MAPPINGS,
    **PROMPT_LINES_NODE_CLASS_MAPPINGS,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    **LTX23_NODE_DISPLAY_NAME_MAPPINGS,
    **KEYFRAME_NODE_DISPLAY_NAME_MAPPINGS,
    **Z_IMAGE_NODE_DISPLAY_NAME_MAPPINGS,
    **PROMPT_LINES_NODE_DISPLAY_NAME_MAPPINGS,
}

WEB_DIRECTORY = "./js"
