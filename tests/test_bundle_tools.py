"""Regression tests for toobusy Bundle utility nodes."""

import importlib.util
import os
import sys


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load():
    path = os.path.join(ROOT, "bundle_tools_node", "bundle_tools.py")
    spec = importlib.util.spec_from_file_location("toobusy.bundle_tools_node.bundle_tools", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_mod = _load()


class _FakeImage:
    def __init__(self, name):
        self.name = name

    def __bool__(self):
        # Mimic a multi-element torch tensor: truthiness is ambiguous and raises.
        # This guards against `payload or blank` regressions in Bundle Unpack.
        raise RuntimeError("Boolean value of Tensor with more than one element is ambiguous")


class _FakeWaveform:
    shape = (1, 1, 16000)


def test_unpack_extracts_images_audio_prompt_and_lora():
    image_a = _FakeImage("a")
    face_a = _FakeImage("face")
    audio = {"waveform": _FakeWaveform(), "sample_rate": 16000}
    bundle = {
        "version": 1,
        "resolved_prompt": "resolved",
        "negative_prompt": "negative",
        "cards": [
            {"role": "character_a", "image": image_a},
            {"role": "face_a", "image": face_a},
            {"role": "audio_a", "audio": audio},
            {"type": "lora", "role": "face_a_faceswap_lora", "lora_name": "headswap.safetensors", "strength": 0.8},
        ],
    }
    out = _mod.ToobusyBundleUnpack().unpack(bundle)
    assert out[0] is image_a
    assert out[2] is face_a
    assert out[8] is audio
    assert out[10] == 1.0
    assert out[12] == "resolved"
    assert out[13] == "negative"
    assert out[14] == "headswap.safetensors"
    assert out[15] == 0.8
    assert "headswap.safetensors" in out[16]


def test_independent_lora_card_is_picked_up():
    # An independent LoRA card (role "lora_a", type "lora") must flow through
    # the Bundle LoRA extraction just like a face-attached LoRA card.
    bundle = {
        "cards": [
            {"role": "character_a", "image": _FakeImage("a")},
            {"type": "lora", "role": "lora_a", "lora_name": "style_pop.safetensors", "strength": 0.65},
        ],
    }
    name, strength = _mod._first_lora(bundle)
    assert name == "style_pop.safetensors"
    assert strength == 0.65
    out = _mod.ToobusyBundleUnpack().unpack(bundle)
    assert out[14] == "style_pop.safetensors"
    assert out[15] == 0.65


def test_bundle_get_pulls_role_image_and_note():
    img_a = _FakeImage("a")
    img_c = _FakeImage("c")
    bundle = {
        "character_a": {"image": img_a, "note": "hero note"},
        "cards": [
            {"role": "character_a", "image": img_a, "prompt": "hero note"},
            {"role": "character_c", "image": img_c, "prompt": "third"},
        ],
    }
    out = _mod.ToobusyBundleGet().get(bundle, "character_a")
    assert out[0] is img_a
    assert out[1] == "character_a"
    assert out[2] == "hero note"
    # character_c lives only in cards (no legacy alias) — still found.
    out_c = _mod.ToobusyBundleGet().get(bundle, "character_c")
    assert out_c[0] is img_c
    assert out_c[2] == "third"


def test_bundle_get_contract():
    inputs = _mod.ToobusyBundleGet.INPUT_TYPES()
    assert inputs["required"]["toobusy_bundle"][0] == "TOOBUSY_BUNDLE"
    assert inputs["required"]["role"][0] == _mod.BUNDLE_GET_ROLES
    assert _mod.ToobusyBundleGet.RETURN_NAMES == ("image", "role", "note")


def test_unpack_contract():
    assert _mod.ToobusyBundleUnpack.INPUT_TYPES()["required"]["toobusy_bundle"][0] == "TOOBUSY_BUNDLE"
    assert _mod.ToobusyBundleUnpack.RETURN_NAMES[:4] == (
        "character_a_image",
        "character_b_image",
        "face_a_image",
        "outfit_a_image",
    )


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
