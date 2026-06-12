"""Regression tests for toobusy Paint Canvas (Python composite side).

Covers layer compositing order, visibility/opacity handling, the painted-area
MASK, the empty/garbage canvas_data fallbacks, and the canvas size clamp.

The module needs torch/numpy/PIL (like the Storyboard Board), so the whole
suite is skipped on environments without them (CI compiles the module but
runs these only where torch exists, e.g. the operator venv).
"""

import importlib.util
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

try:
    import numpy as np
    import torch  # noqa: F401
    from PIL import Image

    _HAS_DEPS = True
except ImportError:
    _HAS_DEPS = False

_mod = None
if _HAS_DEPS:
    spec = importlib.util.spec_from_file_location(
        "toobusy.paint_canvas_node.paint_canvas",
        os.path.join(ROOT, "paint_canvas_node", "paint_canvas.py"),
    )
    _mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(_mod)


def _skip(name):
    print(f"SKIP {name} (no torch/PIL)")


def _layer_data_url(width, height, rgba_box=None):
    import base64
    from io import BytesIO

    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    if rgba_box:
        color, box = rgba_box
        for x in range(box[0], box[2]):
            for y in range(box[1], box[3]):
                image.putpixel((x, y), color)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()


def _render(layers, width=32, height=32, background="#ffffff"):
    import json

    node = _mod.ToobusyPaintCanvas()
    return node.render(json.dumps({"version": 1, "layers": layers}), width, height, background)


def test_empty_canvas_is_background_and_zero_mask():
    if not _mod:
        return _skip("test_empty_canvas_is_background_and_zero_mask")
    image, mask, _ = _render([], background="#ff0000")
    assert image.shape == (1, 32, 32, 3)
    assert mask.shape == (1, 32, 32)
    assert float(mask.max()) == 0.0
    assert abs(float(image[0, 0, 0, 0]) - 1.0) < 0.01 and float(image[0, 0, 0, 1]) < 0.01


def test_layer_composites_over_background_and_masks_painted_area():
    if not _mod:
        return _skip("test_layer_composites_over_background_and_masks_painted_area")
    layer = {
        "visible": True,
        "opacity": 1.0,
        "src": _layer_data_url(32, 32, ((0, 0, 255, 255), (0, 0, 16, 32))),
    }
    image, mask, _ = _render([layer], background="#ffffff")
    assert float(image[0, 16, 8, 2]) > 0.9 and float(image[0, 16, 8, 0]) < 0.1, "left half should be blue"
    assert float(image[0, 16, 24, 0]) > 0.9, "right half stays background white"
    assert float(mask[0, 16, 8]) == 1.0 and float(mask[0, 16, 24]) == 0.0


def test_hidden_and_zero_opacity_layers_are_skipped():
    if not _mod:
        return _skip("test_hidden_and_zero_opacity_layers_are_skipped")
    src = _layer_data_url(32, 32, ((0, 255, 0, 255), (0, 0, 32, 32)))
    image, mask, _ = _render(
        [
            {"visible": False, "opacity": 1.0, "src": src},
            {"visible": True, "opacity": 0.0, "src": src},
        ],
    )
    assert float(mask.max()) == 0.0
    assert float(image[0, 0, 0, 0]) > 0.9, "background stays untouched"


def test_layer_order_is_bottom_to_top():
    if not _mod:
        return _skip("test_layer_order_is_bottom_to_top")
    red = {"visible": True, "opacity": 1.0, "src": _layer_data_url(32, 32, ((255, 0, 0, 255), (0, 0, 32, 32)))}
    blue = {"visible": True, "opacity": 1.0, "src": _layer_data_url(32, 32, ((0, 0, 255, 255), (0, 0, 32, 32)))}
    image, _, _ = _render([red, blue])
    assert float(image[0, 16, 16, 2]) > 0.9, "the later (top) layer wins"


def test_garbage_canvas_data_falls_back():
    if not _mod:
        return _skip("test_garbage_canvas_data_falls_back")
    node = _mod.ToobusyPaintCanvas()
    image, mask, data = node.render("{not json", 64, 48, "#000000")
    assert image.shape == (1, 48, 64, 3) and float(mask.max()) == 0.0
    assert "layers" in data


def test_canvas_size_is_clamped():
    if not _mod:
        return _skip("test_canvas_size_is_clamped")
    image, _, _ = _render([], width=99999, height=16)
    assert image.shape[2] == _mod.MAX_CANVAS_EDGE


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except AssertionError as exc:
                failures += 1
                print(f"FAIL {name}: {exc}")
    if failures:
        print(f"\n{failures} test(s) failed")
        sys.exit(1)
    print("\nall tests passed")
