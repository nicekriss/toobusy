"""Regression tests for toobusy Reference Board backend."""

import base64
import importlib.util
import json
import os
import sys
from io import BytesIO


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

try:
    import torch  # noqa: F401
    from PIL import Image

    _HAS_DEPS = True
except ImportError:
    _HAS_DEPS = False

_mod = None
if _HAS_DEPS:
    spec = importlib.util.spec_from_file_location(
        "toobusy.reference_board_node.reference_board",
        os.path.join(ROOT, "reference_board_node", "reference_board.py"),
    )
    _mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = _mod
    spec.loader.exec_module(_mod)


def _skip(name):
    print(f"SKIP {name} (no torch/PIL)")
    return "SKIP"


def _data_url(width, height, color=(255, 0, 0)):
    image = Image.new("RGB", (width, height), color)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def test_reference_board_assigns_roles_and_manifest_without_payload():
    if not _mod:
        return _skip("test_reference_board_assigns_roles_and_manifest_without_payload")
    board = {
        "version": 1,
        "global_note": "keep face, borrow outfit",
        "items": [
            {"id": "ref_01", "name": "face", "role": "main_character", "note": "face only", "source": "paste", "src": _data_url(32, 48), "x": 12, "y": 24},
            {"id": "ref_02", "name": "dress", "role": "outfit", "note": "black dress", "source": "drop", "src": _data_url(64, 64), "x": 40, "y": 50},
        ],
    }
    out = _mod.ToobusyReferenceBoard().collect(json.dumps(board))
    toobusy_bundle = out[0]
    manifest = json.loads(out[2])
    validation = out[3]

    assert toobusy_bundle["main_character"]["image"].shape == (1, 48, 32, 3)
    assert toobusy_bundle["outfit"]["image"].shape == (1, 64, 64, 3)
    assert toobusy_bundle["main_character"]["id"] == "ref_01"
    assert toobusy_bundle["bundle_type"] == "TOOBUSY_BUNDLE"
    assert toobusy_bundle["cards"][0]["role"] == "main_character"
    assert toobusy_bundle["cards"][0]["type"] == "character"
    assert out[1] == "keep face, borrow outfit"
    assert manifest["items"][0]["role"] == "main_character"
    assert "src" not in json.dumps(manifest)
    assert "Main Character A: assigned" in validation
    assert "Character B: empty" in validation


def test_reference_board_downscales_large_images_only():
    if not _mod:
        return _skip("test_reference_board_downscales_large_images_only")
    width, height, resized = _mod._resize_size_to_total_pixels(4000, 3000)
    assert resized is True
    assert width * height <= 1_010_000
    assert abs((width / height) - (4000 / 3000)) < 0.01
    assert _mod._resize_size_to_total_pixels(800, 600) == (800, 600, False)


def test_reference_board_duplicate_role_warns_and_uses_first():
    if not _mod:
        return _skip("test_reference_board_duplicate_role_warns_and_uses_first")
    board = {
        "items": [
            {"id": "a", "role": "main_character", "src": _data_url(16, 16, (255, 0, 0))},
            {"id": "b", "role": "main_character", "src": _data_url(20, 20, (0, 255, 0))},
        ],
    }
    out = _mod.ToobusyReferenceBoard().collect(json.dumps(board))
    assert out[0]["main_character"]["image"].shape == (1, 16, 16, 3)
    assert "main_character has multiple cards" in out[3]


def test_reference_board_loads_cached_filename_without_payload():
    if not _mod:
        return _skip("test_reference_board_loads_cached_filename_without_payload")
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        cache_dir = os.path.join(tmp, "toobusy_reference_board")
        os.makedirs(cache_dir)
        Image.new("RGB", (24, 36), (0, 0, 255)).save(os.path.join(cache_dir, "ref.jpg"), format="JPEG")
        old_input_directory = _mod._input_directory
        _mod._input_directory = lambda: tmp
        try:
            board = {
                "items": [
                    {
                        "id": "cached",
                        "role": "main_character",
                        "filename": "toobusy_reference_board/ref.jpg",
                        "original_width": 240,
                        "original_height": 360,
                    }
                ]
            }
            out = _mod.ToobusyReferenceBoard().collect(json.dumps(board))
            manifest = json.loads(out[2])
            assert out[0]["main_character"]["image"].shape == (1, 36, 24, 3)
            assert manifest["items"][0]["filename"] == "toobusy_reference_board/ref.jpg"
            assert manifest["items"][0]["original_width"] == 240
        finally:
            _mod._input_directory = old_input_directory


def test_reference_board_modern_roles_map_to_legacy_outputs_and_bundle():
    if not _mod:
        return _skip("test_reference_board_modern_roles_map_to_legacy_outputs_and_bundle")
    board = {
        "items": [
            {"id": "char-a", "name": "A", "role": "character_a", "src": _data_url(32, 48), "note": "hero"},
            {"id": "outfit-a", "name": "Outfit", "role": "outfit_a", "src": _data_url(40, 50), "note": "jacket"},
        ],
    }
    out = _mod.ToobusyReferenceBoard().collect(json.dumps(board))
    toobusy_bundle = out[0]
    assert toobusy_bundle["main_character"]["image"].shape == (1, 48, 32, 3)
    assert toobusy_bundle["outfit"]["image"].shape == (1, 50, 40, 3)
    assert toobusy_bundle["cards"][0]["role"] == "character_a"
    assert toobusy_bundle["selections"]["character_a"] == "char-a"
    assert toobusy_bundle["main_character"]["id"] == "char-a"


def test_reference_board_face_card_can_attach_lora_card():
    if not _mod:
        return _skip("test_reference_board_face_card_can_attach_lora_card")
    board = {
        "items": [
            {
                "id": "face-a",
                "name": "Face A",
                "role": "face_a",
                "src": _data_url(32, 32),
                "face_lora_enabled": True,
                "face_lora_name": "headswap.safetensors",
                "face_lora_strength": 0.75,
            },
        ],
    }
    out = _mod.ToobusyReferenceBoard().collect(json.dumps(board))
    lora_cards = [card for card in out[0]["cards"] if card["type"] == "lora"]
    assert len(lora_cards) == 1
    assert lora_cards[0]["role"] == "face_a_faceswap_lora"
    assert lora_cards[0]["lora_name"] == "headswap.safetensors"
    assert lora_cards[0]["strength"] == 0.75


def test_reference_board_independent_lora_card_becomes_bundle_lora():
    if not _mod:
        return _skip("test_reference_board_independent_lora_card_becomes_bundle_lora")
    board = {
        "items": [
            {"id": "char-a", "name": "A", "role": "character_a", "src": _data_url(32, 48)},
            {
                "id": "lora-1",
                "name": "pop style",
                "type": "lora",
                "role": "lora_a",
                "lora_name": "style_pop.safetensors",
                "lora_strength": 0.65,
                "lora_enabled": True,
            },
            {
                "id": "lora-off",
                "type": "lora",
                "role": "lora_a",
                "lora_name": "disabled.safetensors",
                "lora_enabled": False,
            },
            {
                "id": "lora-empty",
                "type": "lora",
                "role": "lora_a",
                "lora_name": "",
                "lora_enabled": True,
            },
        ],
    }
    out = _mod.ToobusyReferenceBoard().collect(json.dumps(board))
    lora_cards = [card for card in out[0]["cards"] if card["type"] == "lora"]
    assert len(lora_cards) == 1
    assert lora_cards[0]["lora_name"] == "style_pop.safetensors"
    assert lora_cards[0]["strength"] == 0.65
    assert "lora" in lora_cards[0]["role"]
    # The character image card still flows through untouched.
    assert out[0]["main_character"]["image"].shape == (1, 48, 32, 3)


def test_reference_board_text_cards_become_text_blocks():
    if not _mod:
        return _skip("test_reference_board_text_cards_become_text_blocks")
    board = {
        "items": [
            {"id": "char-a", "role": "character_a", "src": _data_url(32, 48)},
            {"id": "t1", "type": "text", "text_category": "goal", "text": "둘이 대화하는 장면"},
            {"id": "t2", "type": "text", "text_category": "negative", "text": "blurry"},
            {"id": "t3", "type": "text", "text_category": "weird", "text": "fallback to custom"},
            {"id": "t4", "type": "text", "text_category": "goal", "text": ""},
        ],
    }
    out = _mod.ToobusyReferenceBoard().collect(json.dumps(board))
    bundle = out[0]
    text_blocks = bundle["text_blocks"]
    assert len(text_blocks) == 3
    assert text_blocks[0] == {"category": "goal", "text": "둘이 대화하는 장면"}
    assert text_blocks[1] == {"category": "negative", "text": "blurry"}
    assert text_blocks[2]["category"] == "custom"  # unknown category coerced
    text_cards = [card for card in bundle["cards"] if card["type"] == "text"]
    assert len(text_cards) == 3
    # The image card still flows through.
    assert bundle["main_character"]["image"].shape == (1, 48, 32, 3)


def test_preset_id_distinct_for_distinct_names():
    if not _mod:
        return _skip("test_preset_id_distinct_for_distinct_names")
    a = _mod._preset_id_for_name("야수")
    b = _mod._preset_id_for_name("베짱이")
    c = _mod._preset_id_for_name("장면A")
    d = _mod._preset_id_for_name("전사A")
    assert a != b  # two all-Korean names must NOT collide
    assert c != d  # same trailing ASCII must NOT collide
    assert a == _mod._preset_id_for_name("야수")  # same name stable (re-save overwrites)
    assert _mod._safe_name(a) == a  # id survives path re-sanitization unchanged


def test_two_korean_presets_coexist():
    if not _mod:
        return _skip("test_two_korean_presets_coexist")
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        old_input_directory = _mod._input_directory
        _mod._input_directory = lambda: tmp
        try:
            board1 = {"global_note": "first", "items": []}
            board2 = {"global_note": "second", "items": []}
            _mod._save_board_preset("야수", board1)
            _mod._save_board_preset("베짱이", board2)
            presets = _mod._list_board_presets()
            names = sorted(p["name"] for p in presets)
            assert names == ["베짱이", "야수"]  # both survived, no overwrite
            # Each loads back to its own content.
            ids = {p["name"]: p["id"] for p in presets}
            assert _mod._load_board_preset(ids["야수"])["global_note"] == "first"
            assert _mod._load_board_preset(ids["베짱이"])["global_note"] == "second"
        finally:
            _mod._input_directory = old_input_directory


def test_validation_report_surfaces_module_warnings():
    if not _mod:
        return _skip("test_validation_report_surfaces_module_warnings")
    report = _mod._validation_report(
        {"main_character": object()},
        [],
        0,
        0,
        ["Erase Face on 'hero' skipped: mediapipe/opencv not installed. Run: pip install -r custom_nodes/toobusy/requirements_facemask.txt"],
    )
    assert "status: CHECK" in report
    assert "Erase Face on 'hero' skipped" in report
    # Path is relative to the ComfyUI root so it is copy-paste runnable from the terminal.
    assert "pip install -r custom_nodes/toobusy/requirements_facemask.txt" in report


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                result = fn()
                if result != "SKIP":
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
