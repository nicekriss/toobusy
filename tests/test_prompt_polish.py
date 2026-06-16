"""Regression tests for Ideogram Prompt Polish, focused on the image-analysis
mode added so it doubles as an image -> Ideogram layout draft generator.

  * _build_prompt branches between scene-conversion and image-analysis;
  * both branches still request the exact Ideogram JSON schema;
  * the image input is exposed and forwarded to the text generator;
  * _extract_json still pulls JSON out of fenced/noisy LLM output.

Standalone- and pytest-runnable, no ComfyUI runtime (the module is json/re only).
"""

import importlib.util
import os
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _install_stubs():
    pkg = types.ModuleType("toobusy")
    pkg.__path__ = [ROOT]
    sys.modules["toobusy"] = pkg

    pp_pkg = types.ModuleType("toobusy.ideogram_prompt_polish_node")
    pp_pkg.__path__ = [os.path.join(ROOT, "ideogram_prompt_polish_node")]
    sys.modules["toobusy.ideogram_prompt_polish_node"] = pp_pkg

    # polish() lazily imports _generate_text from keyframe_maker; stub it so the
    # relative import resolves without ComfyUI (tests override it as needed).
    km_pkg = types.ModuleType("toobusy.keyframe_maker_node")
    km_pkg.__path__ = [os.path.join(ROOT, "keyframe_maker_node")]
    sys.modules["toobusy.keyframe_maker_node"] = km_pkg
    km = types.ModuleType("toobusy.keyframe_maker_node.keyframe_maker")
    km._generate_text = lambda clip, prompt, max_length, seed, image=None: '{"high_level_description": "stub"}'
    sys.modules["toobusy.keyframe_maker_node.keyframe_maker"] = km


def _load():
    path = os.path.join(ROOT, "ideogram_prompt_polish_node", "prompt_polish.py")
    spec = importlib.util.spec_from_file_location("toobusy.ideogram_prompt_polish_node.prompt_polish", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_install_stubs()
_mod = _load()


def _prompt(image_present):
    return _mod._build_prompt(
        scene="눈 오는 날 아이들",
        style_mode="Literal",
        language="Auto",
        preserve_intent=True,
        fill_missing=True,
        existing_layout_json="",
        image_present=image_present,
    )


SCHEMA_MARK = '"bbox" [y_min, x_min, y_max, x_max] in 0-1000'


def test_scene_mode_prompt():
    text = _prompt(image_present=False)
    assert "Convert the user's scene description" in text
    assert "Analyze the provided IMAGE" not in text
    assert SCHEMA_MARK in text


def test_image_mode_prompt():
    text = _prompt(image_present=True)
    assert "Analyze the provided IMAGE" in text
    assert "Korean stays Korean" in text
    assert "LTX2.3 두두등장!" in text
    assert "full-body vs upper-body" in text
    assert "visible feet" in text
    assert "never duplicate or near-identical boxes" in text
    assert SCHEMA_MARK in text  # same schema in both modes


def test_image_input_exposed_and_optional():
    optional = _mod.ToobusyIdeogramPromptPolish.INPUT_TYPES()["optional"]
    assert optional["image"][0] == "IMAGE"
    # image is optional, not required.
    assert "image" not in _mod.ToobusyIdeogramPromptPolish.INPUT_TYPES()["required"]


def test_extract_json_handles_fences_and_prose():
    raw = 'Sure! Here is the layout:\n```json\n{"high_level_description": "x", "a": 1,}\n```\nDone.'
    data = _mod._extract_json(raw)
    assert data == {"high_level_description": "x", "a": 1}


def test_image_is_forwarded_to_generator():
    # polish() should pass the image through to _generate_text. Override the
    # stubbed keyframe generator to capture the call.
    captured = {}

    def fake_generate_text(clip, prompt, max_length, seed, image=None):
        captured["image"] = image
        captured["prompt"] = prompt
        return '{"high_level_description": "from image"}'

    sys.modules["toobusy.keyframe_maker_node.keyframe_maker"]._generate_text = fake_generate_text

    sentinel = object()  # stands in for an IMAGE tensor
    out_json, _raw = _mod.ToobusyIdeogramPromptPolish().polish(
        clip="clip", scene="hint", style_mode="Literal", language="Auto",
        preserve_intent=True, fill_missing_fields=True, seed=1, image=sentinel,
    )
    assert captured["image"] is sentinel
    assert "Analyze the provided IMAGE" in captured["prompt"]
    assert "from image" in out_json


def test_enrich_palette_fills_empty_from_image():
    try:
        import torch
    except ImportError:
        print("SKIP test_enrich_palette_fills_empty_from_image (no torch)")
        return
    # Top half red, bottom half blue.
    image = torch.zeros(1, 100, 100, 3)
    image[:, :50, :, 0] = 1.0
    image[:, 50:, :, 2] = 1.0
    payload = {
        "style_description": {"color_palette": []},
        "compositional_deconstruction": {
            "elements": [
                {"type": "obj", "bbox": [0, 0, 400, 1000]},      # top region -> red
                {"type": "obj", "bbox": [600, 0, 1000, 1000], "color_palette": ["#ABCDEF"]},  # kept
            ]
        },
    }
    out = _mod._enrich_palette(payload, image)
    assert out["style_description"]["color_palette"], "style palette filled from image"
    elements = out["compositional_deconstruction"]["elements"]
    assert elements[0]["color_palette"][0] == "#F01010"  # red region (255->0xF0)
    assert elements[1]["color_palette"] == ["#ABCDEF"]   # existing palette untouched


def test_mixed_latin_hangul_text_is_split_before_builder():
    payload = {
        "compositional_deconstruction": {
            "elements": [
                {
                    "type": "text",
                    "bbox": [65, 248, 179, 752],
                    "desc": "Main title announcement",
                    "text": "LTX2.3 두두등장!",
                },
                {
                    "type": "obj",
                    "bbox": [385, 37, 665, 337],
                    "desc": "First Frame panel",
                    "text": "First Frame (시작 프레임)",
                },
            ]
        }
    }
    out = _mod._split_mixed_text_elements(payload)
    elements = out["compositional_deconstruction"]["elements"]
    texts = [element.get("text") for element in elements]
    assert texts == ["LTX2.3", "두두등장!", "First Frame", "시작 프레임"]
    assert all(element["type"] == "text" for element in elements)
    assert elements[0]["bbox"][1] < elements[1]["bbox"][1]
    assert elements[2]["bbox"][1] < elements[3]["bbox"][1]


def test_wide_title_split_uses_vertical_stack():
    payload = {
        "compositional_deconstruction": {
            "elements": [
                {
                    "type": "text",
                    "bbox": [40, 60, 340, 720],
                    "desc": "Stacked title",
                    "text": "SCAIL-2 캐릭터 교체 모션 트랜스퍼",
                },
            ]
        }
    }
    out = _mod._split_mixed_text_elements(payload)
    elements = out["compositional_deconstruction"]["elements"]
    assert [element["text"] for element in elements] == ["SCAIL-2", "캐릭터 교체 모션 트랜스퍼"]
    assert elements[0]["bbox"][0] < elements[1]["bbox"][0]
    assert elements[0]["bbox"][1] == elements[1]["bbox"][1]


def test_full_body_figure_desc_is_enriched():
    payload = {
        "compositional_deconstruction": {
            "elements": [
                {
                    "type": "obj",
                    "bbox": [100, 760, 940, 980],
                    "desc": "Male anime character in a black leather jacket",
                },
                {
                    "type": "obj",
                    "bbox": [440, 20, 890, 260],
                    "desc": "Source panel showing video frames",
                },
            ]
        }
    }
    out = _mod._enrich_element_descriptions(payload)
    elements = out["compositional_deconstruction"]["elements"]
    assert "Full-body head-to-toe" in elements[0]["desc"]
    assert "visible legs and feet" in elements[0]["desc"]
    assert "small UI cards" in elements[1]["desc"]


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
