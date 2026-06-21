"""Regression tests for toobusy Flux2 Klein Prompt Director.

Standalone-runnable, no ComfyUI runtime. The node calls the shared text
generator, but tests replace it with a deterministic fake.

Director inputs are now bundle-driven: intent comes from Reference Board text
cards (category "goal") and structure comes from the button panel selection.
There is no task_mode / goal_ko / style_mode node input anymore.
"""

import importlib.util
import json
import os
import sys
import types


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CALLS = []


def _install_stubs():
    pkg = types.ModuleType("toobusy")
    pkg.__path__ = [ROOT]
    sys.modules["toobusy"] = pkg

    km_pkg = types.ModuleType("toobusy.keyframe_maker_node")
    km_pkg.__path__ = [os.path.join(ROOT, "keyframe_maker_node")]
    sys.modules["toobusy.keyframe_maker_node"] = km_pkg

    km = types.ModuleType("toobusy.keyframe_maker_node.keyframe_maker")
    km._generate_text = lambda clip, prompt, max_length, seed, image=None: ""
    sys.modules["toobusy.keyframe_maker_node.keyframe_maker"] = km


def _load():
    path = os.path.join(ROOT, "flux2_klein_prompt_director_node", "prompt_director.py")
    spec = importlib.util.spec_from_file_location("toobusy.flux2_klein_prompt_director_node.prompt_director", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_install_stubs()
_mod = _load()


class _FakeImage:
    def __init__(self, height=768, width=512):
        self.shape = (1, height, width, 3)


def _fake_generate_text(clip, prompt, max_length, seed, image=None):
    del clip
    _CALLS.append({"prompt": prompt, "max_length": max_length, "seed": seed, "image": image})
    if "final_prompt_en:" in prompt:
        return (
            "final_prompt_en:\n"
            "A cinematic scene centered on the woman from the main character reference, "
            "speaking face to face with the man from the secondary reference, using the "
            "two-person pose reference, wearing the elegant black dress, in a warm palace interior.\n"
            "final_prompt_ko:\n"
            "[한글 요약]\n인물 A 중심, 인물 B와 대화, 포즈/의상/배경 레퍼런스를 역할별로 반영한다."
        )
    if "Main Character Reference" in prompt:
        return "young woman, long black hair, calm expression"
    if "Secondary Character Reference" in prompt:
        return "young man, brown jacket, side-facing pose"
    if "Pose Reference" in prompt:
        return "two-person medium shot, facing each other, slight low angle"
    if "Outfit Reference" in prompt:
        return "elegant black dress with gold details; visible person wearing the outfit"
    if "Background Reference" in prompt:
        return "warm palace-like interior with golden lighting"
    return ""


def _default_bundle():
    return {
        "cards": [
            {"role": "character_a", "image": _FakeImage()},
            {"role": "character_b", "image": _FakeImage()},
            {"role": "pose_a", "image": _FakeImage()},
            {"role": "outfit_a", "image": _FakeImage()},
            {"role": "background_a", "image": _FakeImage()},
        ],
    }


def _direct(**overrides):
    _CALLS.clear()
    _mod._generate_text = _fake_generate_text
    kwargs = dict(
        clip="clip",
        analysis_mode="balanced",
        seed=1,
        toobusy_bundle=_default_bundle(),
    )
    kwargs.update(overrides)
    return _mod.ToobusyFlux2KleinPromptDirector().direct(**kwargs)


def _final_request_prompt():
    for call in _CALLS:
        if "final_prompt_en:" in call["prompt"]:
            return call["prompt"]
    return ""


def _selection(blocks):
    return json.dumps({"version": 1, "blocks": blocks})


def test_input_output_contract():
    inputs = _mod.ToobusyFlux2KleinPromptDirector.INPUT_TYPES()
    assert "clip" in inputs["required"]
    assert inputs["required"]["analysis_mode"][1]["default"] == "balanced"
    assert "seed" in inputs["required"]
    # Removed manual fields.
    assert "task_mode" not in inputs["required"]
    assert "goal_ko" not in inputs["required"]
    assert "style_mode" not in inputs["required"]
    # Bundle-driven inputs.
    assert inputs["optional"]["toobusy_bundle"][0] == "TOOBUSY_BUNDLE"
    assert inputs["optional"]["director_selection_json"][0] == "STRING"
    assert _mod.ToobusyFlux2KleinPromptDirector.RETURN_NAMES == (
        "toobusy_bundle",
        "resolved_prompt",
        "selected_blocks_json",
        "validation_report",
    )


def test_goal_text_card_drives_llm_goal():
    bundle = _default_bundle()
    bundle["text_blocks"] = [
        {"category": "goal", "text": "둘이 마주보며 대화하는 영화 같은 장면"},
    ]
    bundle_out, final_en, _selected_json, _validation = _direct(toobusy_bundle=bundle)
    request = _final_request_prompt()
    assert "둘이 마주보며 대화하는 영화 같은 장면" in request
    assert bundle_out["resolved_prompt"] == final_en


def test_text_cards_fold_style_negative_custom():
    bundle = _default_bundle()
    bundle["text_blocks"] = [
        {"category": "goal", "text": "cozy interview shot"},
        {"category": "style", "text": "warm film tone"},
        {"category": "negative", "text": "blurry, watermark"},
        {"category": "custom", "text": "holding a coffee cup"},
    ]
    bundle_out, _final_en, selected_json, _validation = _direct(toobusy_bundle=bundle)
    categories = [b["category"] for b in bundle_out["prompt_blocks"]]
    assert categories == ["style", "custom"]
    assert bundle_out["negative_prompt"] == "blurry, watermark"
    assert "warm film tone" in selected_json
    assert "holding a coffee cup" in selected_json
    request = _final_request_prompt()
    assert "[style] warm film tone" in request
    assert "[custom] holding a coffee cup" in request


def test_button_selection_with_text_cards_compose_in_order():
    bundle = _default_bundle()
    bundle["text_blocks"] = [
        {"category": "goal", "text": "movie poster"},
        {"category": "style", "text": "teal and orange grade"},
        {"category": "negative", "text": "extra fingers"},
    ]
    selection = _selection([
        {"kind": "reference", "role": "character_a", "category": "character", "label": "Character A"},
        {"kind": "flag", "flag": "face_swap", "label": "FaceSwap"},
        {"kind": "modifier", "category": "camera", "text": "low angle"},
        {"kind": "negative", "text": "blurry"},
    ])
    bundle_out, _final_en, _selected_json, _validation = _direct(
        toobusy_bundle=bundle,
        director_selection_json=selection,
    )
    categories = [b["category"] for b in bundle_out["prompt_blocks"]]
    # Button blocks first (character, camera), then text-card blocks (style).
    assert categories == ["character", "camera", "style"]
    assert bundle_out["prompt_blocks"][0]["role"] == "character_a"
    assert bundle_out["flags"]["face_swap"] is True
    # Button negative merged with negative text card.
    assert bundle_out["negative_prompt"] == "blurry, extra fingers"


def test_expanded_reference_roles_compose():
    # Director must handle the full board role set: character_d + pose + background.
    bundle = _default_bundle()
    bundle["cards"].append({"role": "character_d", "image": _FakeImage()})
    bundle["text_blocks"] = [{"category": "goal", "text": "group scene"}]
    selection = _selection([
        {"kind": "reference", "role": "character_d", "category": "character", "label": "Character D"},
        {"kind": "reference", "role": "pose_a", "category": "pose", "label": "Pose"},
        {"kind": "reference", "role": "background_a", "category": "location", "label": "Background"},
    ])
    bundle_out, _final_en, _selected_json, _validation = _direct(
        toobusy_bundle=bundle,
        director_selection_json=selection,
    )
    blocks = bundle_out["prompt_blocks"]
    roles = [b["role"] for b in blocks]
    categories = [b["category"] for b in blocks]
    assert "character_d" in roles
    assert "pose_a" in roles
    assert "background_a" in roles
    assert categories[0] == "character"  # character_d
    assert "pose" in categories
    assert "location" in categories


def test_face_swap_suppresses_body_face_in_request():
    bundle = _default_bundle()
    bundle["cards"].append({"role": "face_a", "image": _FakeImage()})
    bundle["text_blocks"] = [{"category": "goal", "text": "portrait swap"}]
    selection = _selection([
        {"kind": "reference", "role": "character_a", "category": "character", "label": "Character A"},
        {"kind": "reference", "role": "face_a", "category": "face", "label": "Face A"},
        {"kind": "flag", "flag": "face_swap", "label": "FaceSwap"},
    ])
    bundle_out, _final_en, _selected_json, _validation = _direct(
        toobusy_bundle=bundle,
        director_selection_json=selection,
    )
    request = _final_request_prompt()
    # Strong global face-swap rule injected.
    assert "FACE SWAP (face only) is active" in request
    # Body reference annotated as body-only; face reference as identity source.
    assert "BODY ONLY" in request
    assert "FACE IDENTITY" in request
    assert bundle_out["flags"]["face_swap"] is True
    assert bundle_out["flags"]["reference_order"] == "body_first_face_second"


def test_product_swap_keeps_scene_and_swaps_product():
    bundle = _default_bundle()
    bundle["cards"].append({"role": "prop_a", "image": _FakeImage()})
    bundle["text_blocks"] = [{"category": "goal", "text": "Character A 의 제품을 Prop으로 교체"}]
    selection = _selection([
        {"kind": "reference", "role": "character_a", "category": "character", "label": "Character A"},
        {"kind": "reference", "role": "prop_a", "category": "prop", "label": "Prop"},
        {"kind": "flag", "flag": "product_swap", "label": "Product Swap"},
    ])
    bundle_out, _final_en, _selected_json, _validation = _direct(
        toobusy_bundle=bundle,
        director_selection_json=selection,
    )
    request = _final_request_prompt()
    assert "PRODUCT SWAP is active" in request
    # Character block becomes scene-only; prop block becomes new-product-only.
    assert "SCENE" in request
    assert "NEW PRODUCT" in request
    assert bundle_out["flags"]["product_swap"] is True
    assert bundle_out["flags"]["reference_order"] == "product_swap"


def test_character_swap_keeps_scene_swaps_person():
    bundle = _default_bundle()  # has character_a + character_b
    bundle["text_blocks"] = [{"category": "goal", "text": "A 장면에 B를 넣기"}]
    selection = _selection([
        {"kind": "reference", "role": "character_a", "category": "character", "label": "Character A"},
        {"kind": "reference", "role": "character_b", "category": "character", "label": "Character B"},
        {"kind": "flag", "flag": "character_swap", "label": "Character Swap"},
    ])
    bundle_out, _final_en, _selected_json, _validation = _direct(
        toobusy_bundle=bundle,
        director_selection_json=selection,
    )
    request = _final_request_prompt()
    assert "CHARACTER SWAP is active" in request
    assert "SCENE & POSE" in request  # Character A annotated as scene
    assert "NEW PERSON" in request  # Character B annotated as new identity
    # Multi-person aware: respects a target in the goal, keeps others unchanged.
    assert "keep every other person in the scene unchanged" in request
    assert bundle_out["flags"]["character_swap"] is True
    assert bundle_out["flags"]["reference_order"] == "character_swap"


def test_empty_inputs_fall_back_to_auto_compose():
    # No selection, no text cards -> legacy auto-compose from reference summaries.
    bundle_out, _final_en, selected_json, _validation = _direct()
    roles = {b["role"] for b in bundle_out["prompt_blocks"]}
    assert "character_a" in roles
    assert "face_swap" not in bundle_out["flags"]
    assert "User-selected ordered composition blocks" not in _final_request_prompt()
    assert "character_a" in selected_json


def test_text_cards_from_cards_fallback():
    # Older bundles may carry text cards only in `cards`, not `text_blocks`.
    bundle = _default_bundle()
    bundle["cards"].append({"type": "text", "category": "goal", "text": "sunset rooftop scene"})
    _bundle_out, _final_en, _selected_json, _validation = _direct(toobusy_bundle=bundle)
    assert "sunset rooftop scene" in _final_request_prompt()


def test_reference_leak_warnings_still_fire():
    bundle = _default_bundle()
    bundle["text_blocks"] = [{"category": "goal", "text": "scene"}]
    _bundle_out, _final_en, _selected_json, validation = _direct(toobusy_bundle=bundle)
    assert "Pose reference appears to be a two-person composition." in validation
    assert "Outfit reference appears to contain a visible person" in validation
    assert "reference_sizes:" in validation


def test_reference_resize_policy_downscales_only():
    assert _mod._resize_size_to_total_pixels(512, 768) == (512, 768, False)
    width, height, resized = _mod._resize_size_to_total_pixels(4000, 3000)
    assert resized is True
    assert width * height <= 1_010_000
    assert abs((width / height) - (4000 / 3000)) < 0.01


def test_malformed_selection_with_no_text_falls_back_to_auto():
    bundle_out, _final_en, _selected_json, _validation = _direct(director_selection_json="{not json")
    roles = {b["role"] for b in bundle_out["prompt_blocks"]}
    assert "character_a" in roles


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
            except Exception as exc:  # noqa: BLE001
                failures += 1
                print(f"ERROR {name}: {type(exc).__name__}: {exc}")
    if failures:
        print(f"\n{failures} test(s) failed")
        sys.exit(1)
    print("\nall tests passed")
