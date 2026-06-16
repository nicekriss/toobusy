"""Regression tests for toobusy Layout Text Overlay.

  * INPUT_TYPES exposes image + overlay_data + optional layout_json;
  * seeding overlay items from an Ideogram layout JSON (text elements only,
    bbox [y,x,y,x] 0-1000 -> normalized 0..1);
  * render() composites onto the image and returns a same-size IMAGE tensor
    (torch only).

Standalone- and pytest-runnable, no ComfyUI runtime (module is json-only at top).
"""

import importlib.util
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load():
    path = os.path.join(ROOT, "layout_text_overlay_node", "layout_text_overlay.py")
    spec = importlib.util.spec_from_file_location("toobusy_layout_text_overlay", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_mod = _load()

LAYOUT = """
{
  "compositional_deconstruction": {
    "elements": [
      {"type": "text", "bbox": [65, 248, 179, 752], "text": "LTX2.3 두두등장!", "desc": "title"},
      {"type": "obj",  "bbox": [385, 37, 665, 337], "desc": "a panel"},
      {"type": "text", "bbox": [229, 37, 352, 962], "text": "미들프레임 넣기", "desc": "subtitle"}
    ]
  }
}
"""


def test_input_types():
    required = _mod.ToobusyLayoutTextOverlay.INPUT_TYPES()["required"]
    optional = _mod.ToobusyLayoutTextOverlay.INPUT_TYPES()["optional"]
    assert required["image"][0] == "IMAGE"
    assert required["overlay_data"][0] == "STRING"
    assert optional["layout_json"][1]["forceInput"] is True


def test_seed_only_text_elements_and_normalize():
    items = _mod.seed_items_from_layout(LAYOUT)
    assert [it["text"] for it in items] == ["LTX2.3 두두등장!", "미들프레임 넣기"]  # obj skipped
    title = items[0]
    # bbox [65,248,179,752] -> x=248/1000, y=65/1000, w=(752-248)/1000, h=(179-65)/1000
    assert abs(title["x"] - 0.248) < 1e-6 and abs(title["y"] - 0.065) < 1e-6
    assert abs(title["w"] - 0.504) < 1e-6 and abs(title["h"] - 0.114) < 1e-6
    # fontSize is a fraction of image height (~0.8 * box height) so the seed fills the box.
    assert abs(title["fontSize"] - round(0.114 * 0.8, 4)) < 1e-6


def test_seed_handles_garbage_json():
    assert _mod.seed_items_from_layout("not json") == []
    assert _mod.seed_items_from_layout("") == []
    assert _mod.seed_items_from_layout('{"compositional_deconstruction": {}}') == []


def test_render_composites_same_size(_torch_required=True):
    try:
        import torch
    except ImportError:
        print("SKIP test_render_composites_same_size (no torch)")
        return
    try:
        import PIL  # noqa: F401
    except ImportError:
        print("SKIP test_render_composites_same_size (no PIL)")
        return

    image = torch.zeros(1, 128, 256, 3)
    # Empty overlay -> seeds from layout_json; output must match input size.
    out = _mod.render_overlay(image, "", LAYOUT, font_scale=1.0)
    assert tuple(out.shape) == (1, 128, 256, 3)
    # Something was drawn (white-ish text on black) -> max pixel raised.
    assert float(out.max()) > 0.5


def test_render_with_explicit_items():
    try:
        import torch  # noqa: F401
        import PIL  # noqa: F401
    except ImportError:
        print("SKIP test_render_with_explicit_items (no torch/PIL)")
        return
    import json as _json
    import torch

    image = torch.zeros(1, 100, 100, 3)
    overlay = _json.dumps({"items": [
        {"text": "HI", "x": 0.1, "y": 0.1, "w": 0.8, "h": 0.3, "fontSize": 0.2, "color": "#FF0000", "align": "center"},
    ]})
    out = _mod.render_overlay(image, overlay, "", font_scale=1.0)
    assert tuple(out.shape) == (1, 100, 100, 3)
    assert float(out[..., 0].max()) > 0.5  # red channel lit by the red text


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
