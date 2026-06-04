"""ComfyUI custom node package entrypoint.

This repository is intended to be cloned into ComfyUI's `custom_nodes` folder
(e.g. `custom_nodes/drawings`). ComfyUI imports that folder as a Python package,
so this top-level `__init__.py` must expose node mappings.
"""

from .hf_model_auto_loader import (
    NODE_CLASS_MAPPINGS as HF_NODE_CLASS_MAPPINGS,
    NODE_DISPLAY_NAME_MAPPINGS as HF_NODE_DISPLAY_NAME_MAPPINGS,
)
from .ideogram_layout_builder import (
    NODE_CLASS_MAPPINGS as IDEOGRAM_NODE_CLASS_MAPPINGS,
    NODE_DISPLAY_NAME_MAPPINGS as IDEOGRAM_NODE_DISPLAY_NAME_MAPPINGS,
)

NODE_CLASS_MAPPINGS = {
    **HF_NODE_CLASS_MAPPINGS,
    **IDEOGRAM_NODE_CLASS_MAPPINGS,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    **HF_NODE_DISPLAY_NAME_MAPPINGS,
    **IDEOGRAM_NODE_DISPLAY_NAME_MAPPINGS,
}

WEB_DIRECTORY = "./js"
