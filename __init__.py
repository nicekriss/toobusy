"""ComfyUI custom node package entrypoint.

This repository is intended to be cloned into ComfyUI's `custom_nodes` folder
(e.g. `custom_nodes/toobusy`). ComfyUI imports that folder as a Python package,
so this top-level `__init__.py` must expose node mappings.

Each sub-package is imported in isolation. A package that cannot be imported --
usually because one of its optional dependencies is missing -- is skipped on its
own, and every other toobusy node still reaches ComfyUI. The skipped packages
are reported once at the end of this module so the reason shows up in the
ComfyUI startup log instead of silently removing the whole node set.
"""

import logging

logger = logging.getLogger(__name__)

NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}

# Sub-packages that imported cleanly, in registration order.
LOADED_NODE_PACKAGES = []
# Sub-package name -> the exception that stopped it from loading.
UNAVAILABLE_NODE_PACKAGES = {}


try:
    from .ltx23_compact_sampler_node import (
        NODE_CLASS_MAPPINGS as _CLASSES,
        NODE_DISPLAY_NAME_MAPPINGS as _NAMES,
    )
except Exception as exc:  # noqa: BLE001 - one broken package must not hide the rest
    UNAVAILABLE_NODE_PACKAGES["ltx23_compact_sampler_node"] = exc
else:
    NODE_CLASS_MAPPINGS.update(_CLASSES)
    NODE_DISPLAY_NAME_MAPPINGS.update(_NAMES)
    LOADED_NODE_PACKAGES.append("ltx23_compact_sampler_node")

try:
    from .keyframe_maker_node import (
        NODE_CLASS_MAPPINGS as _CLASSES,
        NODE_DISPLAY_NAME_MAPPINGS as _NAMES,
    )
except Exception as exc:  # noqa: BLE001 - one broken package must not hide the rest
    UNAVAILABLE_NODE_PACKAGES["keyframe_maker_node"] = exc
else:
    NODE_CLASS_MAPPINGS.update(_CLASSES)
    NODE_DISPLAY_NAME_MAPPINGS.update(_NAMES)
    LOADED_NODE_PACKAGES.append("keyframe_maker_node")

try:
    from .z_image_turbo_node import (
        NODE_CLASS_MAPPINGS as _CLASSES,
        NODE_DISPLAY_NAME_MAPPINGS as _NAMES,
    )
except Exception as exc:  # noqa: BLE001 - one broken package must not hide the rest
    UNAVAILABLE_NODE_PACKAGES["z_image_turbo_node"] = exc
else:
    NODE_CLASS_MAPPINGS.update(_CLASSES)
    NODE_DISPLAY_NAME_MAPPINGS.update(_NAMES)
    LOADED_NODE_PACKAGES.append("z_image_turbo_node")

try:
    from .storyboard_board_node import (
        NODE_CLASS_MAPPINGS as _CLASSES,
        NODE_DISPLAY_NAME_MAPPINGS as _NAMES,
    )
except Exception as exc:  # noqa: BLE001 - one broken package must not hide the rest
    UNAVAILABLE_NODE_PACKAGES["storyboard_board_node"] = exc
else:
    NODE_CLASS_MAPPINGS.update(_CLASSES)
    NODE_DISPLAY_NAME_MAPPINGS.update(_NAMES)
    LOADED_NODE_PACKAGES.append("storyboard_board_node")

try:
    from .ideogram_layout_builder import (
        NODE_CLASS_MAPPINGS as _CLASSES,
        NODE_DISPLAY_NAME_MAPPINGS as _NAMES,
    )
except Exception as exc:  # noqa: BLE001 - one broken package must not hide the rest
    UNAVAILABLE_NODE_PACKAGES["ideogram_layout_builder"] = exc
else:
    NODE_CLASS_MAPPINGS.update(_CLASSES)
    NODE_DISPLAY_NAME_MAPPINGS.update(_NAMES)
    LOADED_NODE_PACKAGES.append("ideogram_layout_builder")

try:
    from .ideogram4_t2i_node import (
        NODE_CLASS_MAPPINGS as _CLASSES,
        NODE_DISPLAY_NAME_MAPPINGS as _NAMES,
    )
except Exception as exc:  # noqa: BLE001 - one broken package must not hide the rest
    UNAVAILABLE_NODE_PACKAGES["ideogram4_t2i_node"] = exc
else:
    NODE_CLASS_MAPPINGS.update(_CLASSES)
    NODE_DISPLAY_NAME_MAPPINGS.update(_NAMES)
    LOADED_NODE_PACKAGES.append("ideogram4_t2i_node")

try:
    from .ideogram_prompt_polish_node import (
        NODE_CLASS_MAPPINGS as _CLASSES,
        NODE_DISPLAY_NAME_MAPPINGS as _NAMES,
    )
except Exception as exc:  # noqa: BLE001 - one broken package must not hide the rest
    UNAVAILABLE_NODE_PACKAGES["ideogram_prompt_polish_node"] = exc
else:
    NODE_CLASS_MAPPINGS.update(_CLASSES)
    NODE_DISPLAY_NAME_MAPPINGS.update(_NAMES)
    LOADED_NODE_PACKAGES.append("ideogram_prompt_polish_node")

try:
    from .wan_scail_extend_sampler_node import (
        NODE_CLASS_MAPPINGS as _CLASSES,
        NODE_DISPLAY_NAME_MAPPINGS as _NAMES,
    )
except Exception as exc:  # noqa: BLE001 - one broken package must not hide the rest
    UNAVAILABLE_NODE_PACKAGES["wan_scail_extend_sampler_node"] = exc
else:
    NODE_CLASS_MAPPINGS.update(_CLASSES)
    NODE_DISPLAY_NAME_MAPPINGS.update(_NAMES)
    LOADED_NODE_PACKAGES.append("wan_scail_extend_sampler_node")

try:
    from .wan_animate2_long_sampler_node import (
        NODE_CLASS_MAPPINGS as _CLASSES,
        NODE_DISPLAY_NAME_MAPPINGS as _NAMES,
    )
except Exception as exc:  # noqa: BLE001 - one broken package must not hide the rest
    UNAVAILABLE_NODE_PACKAGES["wan_animate2_long_sampler_node"] = exc
else:
    NODE_CLASS_MAPPINGS.update(_CLASSES)
    NODE_DISPLAY_NAME_MAPPINGS.update(_NAMES)
    LOADED_NODE_PACKAGES.append("wan_animate2_long_sampler_node")

try:
    from .hires_upscale_node import (
        NODE_CLASS_MAPPINGS as _CLASSES,
        NODE_DISPLAY_NAME_MAPPINGS as _NAMES,
    )
except Exception as exc:  # noqa: BLE001 - one broken package must not hide the rest
    UNAVAILABLE_NODE_PACKAGES["hires_upscale_node"] = exc
else:
    NODE_CLASS_MAPPINGS.update(_CLASSES)
    NODE_DISPLAY_NAME_MAPPINGS.update(_NAMES)
    LOADED_NODE_PACKAGES.append("hires_upscale_node")

try:
    from .zit_controlnet_node import (
        NODE_CLASS_MAPPINGS as _CLASSES,
        NODE_DISPLAY_NAME_MAPPINGS as _NAMES,
    )
except Exception as exc:  # noqa: BLE001 - one broken package must not hide the rest
    UNAVAILABLE_NODE_PACKAGES["zit_controlnet_node"] = exc
else:
    NODE_CLASS_MAPPINGS.update(_CLASSES)
    NODE_DISPLAY_NAME_MAPPINGS.update(_NAMES)
    LOADED_NODE_PACKAGES.append("zit_controlnet_node")

try:
    from .paint_canvas_node import (
        NODE_CLASS_MAPPINGS as _CLASSES,
        NODE_DISPLAY_NAME_MAPPINGS as _NAMES,
    )
except Exception as exc:  # noqa: BLE001 - one broken package must not hide the rest
    UNAVAILABLE_NODE_PACKAGES["paint_canvas_node"] = exc
else:
    NODE_CLASS_MAPPINGS.update(_CLASSES)
    NODE_DISPLAY_NAME_MAPPINGS.update(_NAMES)
    LOADED_NODE_PACKAGES.append("paint_canvas_node")

try:
    from .load_clip_node import (
        NODE_CLASS_MAPPINGS as _CLASSES,
        NODE_DISPLAY_NAME_MAPPINGS as _NAMES,
    )
except Exception as exc:  # noqa: BLE001 - one broken package must not hide the rest
    UNAVAILABLE_NODE_PACKAGES["load_clip_node"] = exc
else:
    NODE_CLASS_MAPPINGS.update(_CLASSES)
    NODE_DISPLAY_NAME_MAPPINGS.update(_NAMES)
    LOADED_NODE_PACKAGES.append("load_clip_node")

try:
    from .flux2_klein_node import (
        NODE_CLASS_MAPPINGS as _CLASSES,
        NODE_DISPLAY_NAME_MAPPINGS as _NAMES,
    )
except Exception as exc:  # noqa: BLE001 - one broken package must not hide the rest
    UNAVAILABLE_NODE_PACKAGES["flux2_klein_node"] = exc
else:
    NODE_CLASS_MAPPINGS.update(_CLASSES)
    NODE_DISPLAY_NAME_MAPPINGS.update(_NAMES)
    LOADED_NODE_PACKAGES.append("flux2_klein_node")

try:
    from .flux2_klein_prompt_director_node import (
        NODE_CLASS_MAPPINGS as _CLASSES,
        NODE_DISPLAY_NAME_MAPPINGS as _NAMES,
    )
except Exception as exc:  # noqa: BLE001 - one broken package must not hide the rest
    UNAVAILABLE_NODE_PACKAGES["flux2_klein_prompt_director_node"] = exc
else:
    NODE_CLASS_MAPPINGS.update(_CLASSES)
    NODE_DISPLAY_NAME_MAPPINGS.update(_NAMES)
    LOADED_NODE_PACKAGES.append("flux2_klein_prompt_director_node")

try:
    from .reference_board_node import (
        NODE_CLASS_MAPPINGS as _CLASSES,
        NODE_DISPLAY_NAME_MAPPINGS as _NAMES,
    )
except Exception as exc:  # noqa: BLE001 - one broken package must not hide the rest
    UNAVAILABLE_NODE_PACKAGES["reference_board_node"] = exc
else:
    NODE_CLASS_MAPPINGS.update(_CLASSES)
    NODE_DISPLAY_NAME_MAPPINGS.update(_NAMES)
    LOADED_NODE_PACKAGES.append("reference_board_node")

try:
    from .dreamid_omni_node import (
        NODE_CLASS_MAPPINGS as _CLASSES,
        NODE_DISPLAY_NAME_MAPPINGS as _NAMES,
    )
except Exception as exc:  # noqa: BLE001 - one broken package must not hide the rest
    UNAVAILABLE_NODE_PACKAGES["dreamid_omni_node"] = exc
else:
    NODE_CLASS_MAPPINGS.update(_CLASSES)
    NODE_DISPLAY_NAME_MAPPINGS.update(_NAMES)
    LOADED_NODE_PACKAGES.append("dreamid_omni_node")

try:
    from .bundle_tools_node import (
        NODE_CLASS_MAPPINGS as _CLASSES,
        NODE_DISPLAY_NAME_MAPPINGS as _NAMES,
    )
except Exception as exc:  # noqa: BLE001 - one broken package must not hide the rest
    UNAVAILABLE_NODE_PACKAGES["bundle_tools_node"] = exc
else:
    NODE_CLASS_MAPPINGS.update(_CLASSES)
    NODE_DISPLAY_NAME_MAPPINGS.update(_NAMES)
    LOADED_NODE_PACKAGES.append("bundle_tools_node")

try:
    from .layout_text_overlay_node import (
        NODE_CLASS_MAPPINGS as _CLASSES,
        NODE_DISPLAY_NAME_MAPPINGS as _NAMES,
    )
except Exception as exc:  # noqa: BLE001 - one broken package must not hide the rest
    UNAVAILABLE_NODE_PACKAGES["layout_text_overlay_node"] = exc
else:
    NODE_CLASS_MAPPINGS.update(_CLASSES)
    NODE_DISPLAY_NAME_MAPPINGS.update(_NAMES)
    LOADED_NODE_PACKAGES.append("layout_text_overlay_node")

try:
    from .background_remove_node import (
        NODE_CLASS_MAPPINGS as _CLASSES,
        NODE_DISPLAY_NAME_MAPPINGS as _NAMES,
    )
except Exception as exc:  # noqa: BLE001 - one broken package must not hide the rest
    UNAVAILABLE_NODE_PACKAGES["background_remove_node"] = exc
else:
    NODE_CLASS_MAPPINGS.update(_CLASSES)
    NODE_DISPLAY_NAME_MAPPINGS.update(_NAMES)
    LOADED_NODE_PACKAGES.append("background_remove_node")

try:
    from .face_mask_node import (
        NODE_CLASS_MAPPINGS as _CLASSES,
        NODE_DISPLAY_NAME_MAPPINGS as _NAMES,
    )
except Exception as exc:  # noqa: BLE001 - one broken package must not hide the rest
    UNAVAILABLE_NODE_PACKAGES["face_mask_node"] = exc
else:
    NODE_CLASS_MAPPINGS.update(_CLASSES)
    NODE_DISPLAY_NAME_MAPPINGS.update(_NAMES)
    LOADED_NODE_PACKAGES.append("face_mask_node")

try:
    from .flashvsr_node import (
        NODE_CLASS_MAPPINGS as _CLASSES,
        NODE_DISPLAY_NAME_MAPPINGS as _NAMES,
    )
except Exception as exc:  # noqa: BLE001 - one broken package must not hide the rest
    UNAVAILABLE_NODE_PACKAGES["flashvsr_node"] = exc
else:
    NODE_CLASS_MAPPINGS.update(_CLASSES)
    NODE_DISPLAY_NAME_MAPPINGS.update(_NAMES)
    LOADED_NODE_PACKAGES.append("flashvsr_node")

try:
    from .minimax_h3_image_latent_node import (
        NODE_CLASS_MAPPINGS as _CLASSES,
        NODE_DISPLAY_NAME_MAPPINGS as _NAMES,
    )
except Exception as exc:  # noqa: BLE001 - one broken package must not hide the rest
    UNAVAILABLE_NODE_PACKAGES["minimax_h3_image_latent_node"] = exc
else:
    NODE_CLASS_MAPPINGS.update(_CLASSES)
    NODE_DISPLAY_NAME_MAPPINGS.update(_NAMES)
    LOADED_NODE_PACKAGES.append("minimax_h3_image_latent_node")

try:
    from .minimax_h3_optional_reference_node import (
        NODE_CLASS_MAPPINGS as _CLASSES,
        NODE_DISPLAY_NAME_MAPPINGS as _NAMES,
    )
except Exception as exc:  # noqa: BLE001 - one broken package must not hide the rest
    UNAVAILABLE_NODE_PACKAGES["minimax_h3_optional_reference_node"] = exc
else:
    NODE_CLASS_MAPPINGS.update(_CLASSES)
    NODE_DISPLAY_NAME_MAPPINGS.update(_NAMES)
    LOADED_NODE_PACKAGES.append("minimax_h3_optional_reference_node")

try:
    from .minimax_h3_semantic_reference_node import (
        NODE_CLASS_MAPPINGS as _CLASSES,
        NODE_DISPLAY_NAME_MAPPINGS as _NAMES,
    )
except Exception as exc:  # noqa: BLE001 - one broken package must not hide the rest
    UNAVAILABLE_NODE_PACKAGES["minimax_h3_semantic_reference_node"] = exc
else:
    NODE_CLASS_MAPPINGS.update(_CLASSES)
    NODE_DISPLAY_NAME_MAPPINGS.update(_NAMES)
    LOADED_NODE_PACKAGES.append("minimax_h3_semantic_reference_node")

try:
    from .bbox_detail_node import (
        NODE_CLASS_MAPPINGS as _CLASSES,
        NODE_DISPLAY_NAME_MAPPINGS as _NAMES,
    )
except Exception as exc:  # noqa: BLE001 - one broken package must not hide the rest
    UNAVAILABLE_NODE_PACKAGES["bbox_detail_node"] = exc
else:
    NODE_CLASS_MAPPINGS.update(_CLASSES)
    NODE_DISPLAY_NAME_MAPPINGS.update(_NAMES)
    LOADED_NODE_PACKAGES.append("bbox_detail_node")

try:
    from .retouch_node import (
        NODE_CLASS_MAPPINGS as _CLASSES,
        NODE_DISPLAY_NAME_MAPPINGS as _NAMES,
    )
except Exception as exc:  # noqa: BLE001 - one broken package must not hide the rest
    UNAVAILABLE_NODE_PACKAGES["retouch_node"] = exc
else:
    NODE_CLASS_MAPPINGS.update(_CLASSES)
    NODE_DISPLAY_NAME_MAPPINGS.update(_NAMES)
    LOADED_NODE_PACKAGES.append("retouch_node")

if UNAVAILABLE_NODE_PACKAGES:
    for _package, _exc in sorted(UNAVAILABLE_NODE_PACKAGES.items()):
        logger.warning(
            "[toobusy] skipped node package %s (%s: %s). "
            "Its optional dependency is probably missing; see the matching "
            "requirements_*.txt in custom_nodes/toobusy.",
            _package,
            type(_exc).__name__,
            _exc,
        )
    logger.warning(
        "[toobusy] loaded %d node(s) from %d package(s); %d package(s) skipped.",
        len(NODE_CLASS_MAPPINGS),
        len(LOADED_NODE_PACKAGES),
        len(UNAVAILABLE_NODE_PACKAGES),
    )

WEB_DIRECTORY = "./js"

__all__ = [
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "LOADED_NODE_PACKAGES",
    "UNAVAILABLE_NODE_PACKAGES",
    "WEB_DIRECTORY",
]
