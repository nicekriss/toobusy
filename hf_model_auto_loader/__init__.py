# NOTE: this subpackage's JS ships from the repo-root ./js folder, which the
# top-level package's WEB_DIRECTORY serves. A nested WEB_DIRECTORY here is never
# read by ComfyUI (only the top-level custom_node package's is), so it is
# intentionally omitted to avoid a dead, drifting duplicate.
from .model_auto_loader import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
