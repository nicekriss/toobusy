"""Ideogram Layout Builder package entrypoint.

Hotfix: keep Korean/mixed text elements as a single original bbox when routing
text to the overlay node. The approximate Latin/Hangul sub-bbox split introduced
in v0.2.12 can misplace boxes on the canvas/output for some imported Ideogram
payloads, so disable only that runtime helper until the splitter can be rebuilt
with exact coordinate tests.
"""

from . import nodes as _nodes


def _keep_original_text_bbox_for_overlay(text, bbox):
    del text, bbox
    return []


_nodes._split_mixed_hangul_runs = _keep_original_text_bbox_for_overlay

NODE_CLASS_MAPPINGS = _nodes.NODE_CLASS_MAPPINGS
NODE_DISPLAY_NAME_MAPPINGS = _nodes.NODE_DISPLAY_NAME_MAPPINGS

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
