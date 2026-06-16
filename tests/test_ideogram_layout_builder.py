"""Regression tests for the Ideogram Layout Builder's Pull-from-input bridge.

The builder gained optional `imported_json` / `image` inputs and OUTPUT_NODE so
the frontend "⟳ Pull from input" button can load an upstream Ideogram draft onto
the canvas. These tests lock the contract that must not drift:

  * the bridge inputs are exposed (imported_json forceInput + image);
  * imported_json is echoed to the `ui` payload, NOT merged into the output;
  * without bridge inputs the node still returns a plain tuple;
  * OUTPUT_NODE is set.

Standalone- and pytest-runnable, no ComfyUI runtime (nodes.py is self-contained).
"""

import importlib.util
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load():
    path = os.path.join(ROOT, "ideogram_layout_builder", "nodes.py")
    spec = importlib.util.spec_from_file_location("toobusy_ilb_nodes", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_mod = _load()
_Builder = _mod.IdeogramLayoutBuilder


def _build(**overrides):
    kwargs = dict(
        high_level_description="A poster.",
        aesthetics="clean",
        lighting="soft",
        photo="",
        medium="graphic_design",
        global_palette="#111111, #FFFFFF",
        background="studio",
        elements_json="[]",
        width=2048,
        height=2048,
    )
    kwargs.update(overrides)
    return _Builder().build(**kwargs)


def test_output_node_and_bridge_inputs_exposed():
    assert _Builder.OUTPUT_NODE is True
    optional = _Builder.INPUT_TYPES()["optional"]
    assert optional["imported_json"][0] == "STRING"
    assert optional["imported_json"][1]["forceInput"] is True
    assert optional["image"][0] == "IMAGE"


def test_no_bridge_returns_plain_tuple():
    result = _build()
    assert isinstance(result, tuple)
    assert isinstance(result[0], str)  # ideogram_json


def test_text_json_output_exposed():
    assert _Builder.RETURN_NAMES == ("ideogram_json", "width", "height", "text_json")
    required = _Builder.INPUT_TYPES()["required"]
    assert required["text_overlay_mode"][0] == "BOOLEAN"


_MIXED = json.dumps([
    {"bbox": [100, 100, 900, 220], "text": "제목", "desc": "title"},
    {"bbox": [100, 300, 900, 700], "desc": "a photo"},
])


def test_text_overlay_mode_splits_text_out():
    out = _build(elements_json=_MIXED, text_overlay_mode=True)
    gen = json.loads(out[0])["compositional_deconstruction"]["elements"]
    text = json.loads(out[3])["compositional_deconstruction"]["elements"]
    assert "text" not in [e["type"] for e in gen]  # generation art has no text
    assert text and all(e["type"] == "text" for e in text)  # text_json is text-only


def test_text_overlay_off_keeps_text_in_generation():
    out = _build(elements_json=_MIXED, text_overlay_mode=False)
    gen = json.loads(out[0])["compositional_deconstruction"]["elements"]
    assert "text" in [e["type"] for e in gen]  # text stays in the image
    # text_json is still produced (text-only) regardless of the toggle.
    text = json.loads(out[3])["compositional_deconstruction"]["elements"]
    assert text and all(e["type"] == "text" for e in text)


def test_split_with_only_text_gets_fallback_obj():
    only_text = json.dumps([{"bbox": [100, 100, 900, 220], "text": "제목", "desc": "title"}])
    out = _build(elements_json=only_text, text_overlay_mode=True)
    gen = json.loads(out[0])["compositional_deconstruction"]["elements"]
    assert gen and all(e["type"] == "obj" for e in gen)  # fallback subject so art isn't empty


def test_imported_json_goes_to_ui_not_output():
    bridge = '{"compositional_deconstruction": {"elements": [{"type": "obj", "bbox": [0, 0, 100, 100], "desc": "imported thing"}]}}'
    out = _build(imported_json=bridge)
    assert isinstance(out, dict) and "ui" in out and "result" in out
    assert out["ui"]["toobusy_import"] == [bridge]
    # The node's own output must come from elements_json (empty -> default
    # centered subject), NOT from the imported bridge json.
    payload = json.loads(out["result"][0])
    descs = [el.get("desc", "") for el in payload["compositional_deconstruction"]["elements"]]
    assert "imported thing" not in " ".join(descs)


def test_empty_imported_json_stays_plain_tuple():
    assert isinstance(_build(imported_json="   "), tuple)


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
