"""Regression tests for the optional toobusy Face Mask node.

Lightweight at import (no mediapipe/cv2/torch at module load). Deps are checked
only when the node runs.
"""

import importlib.util
import os
import sys
import types


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load():
    path = os.path.join(ROOT, "face_mask_node", "face_mask.py")
    spec = importlib.util.spec_from_file_location("toobusy.face_mask_node.face_mask", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_mod = _load()


def _try_numpy():
    try:
        import numpy as np

        return np
    except ImportError:
        return None


def test_missing_dependencies_message():
    def missing(_name):
        raise ImportError(_name)

    missing_names = _mod._missing_optional_dependencies(missing)
    # opencv is the hard requirement; mediapipe is optional (auto-falls back).
    assert "opencv-python" in missing_names
    try:
        _mod._ensure_facemask(missing)
    except RuntimeError as exc:
        text = str(exc)
        assert "Face Mask optional dependencies are missing." in text
        assert "requirements_facemask.txt" in text
    else:
        raise AssertionError("missing optional dependencies should raise")


def test_contract():
    inputs = _mod.ToobusyFaceMask.INPUT_TYPES()
    assert inputs["required"]["image"][0] == "IMAGE"
    assert inputs["required"]["mode"][0] == _mod.FACE_MODES
    assert inputs["required"]["mode"][1]["default"] == "erase_face"
    assert "gray" in inputs["required"]["fill"][0]
    assert inputs["optional"]["expand"][0] == "INT"
    assert _mod.ToobusyFaceMask.RETURN_TYPES == ("IMAGE", "MASK")
    assert _mod.ToobusyFaceMask.RETURN_NAMES == ("image", "mask")


def test_fill_rgb_mapping():
    assert _mod._fill_rgb("gray") == (0.5, 0.5, 0.5)
    assert _mod._fill_rgb("black") == (0.0, 0.0, 0.0)
    assert _mod._fill_rgb("unknown") == (0.5, 0.5, 0.5)


def test_apply_face_mask_modes():
    np = _try_numpy()
    if np is None:
        print("SKIP test_apply_face_mask_modes (no numpy)")
        return "SKIP"
    # 2x1 image: pixel0 = white face, pixel1 = white non-face. mask = [1, 0].
    rgb = np.ones((1, 2, 3), dtype="float32")
    mask = np.array([[1.0, 0.0]], dtype="float32")
    # erase_face: face pixel (mask=1) becomes fill(black); non-face stays.
    erased = _mod._apply_face_mask(rgb, mask, (0.0, 0.0, 0.0), "erase_face", np)
    assert float(erased[0, 0, 0]) == 0.0  # face erased
    assert float(erased[0, 1, 0]) == 1.0  # rest kept
    # keep_face: face pixel stays; non-face becomes fill.
    kept = _mod._apply_face_mask(rgb, mask, (0.0, 0.0, 0.0), "keep_face", np)
    assert float(kept[0, 0, 0]) == 1.0  # face kept
    assert float(kept[0, 1, 0]) == 0.0  # rest removed


def test_yolo_loader_does_not_retain_model_instances():
    calls = []

    class FakeYOLO:
        def __init__(self, path):
            calls.append(path)

    ultralytics = types.ModuleType("ultralytics")
    ultralytics.YOLO = FakeYOLO
    old = sys.modules.get("ultralytics")
    sys.modules["ultralytics"] = ultralytics
    try:
        first = _mod._load_yolo("face.pt")
        second = _mod._load_yolo("face.pt")
    finally:
        if old is None:
            sys.modules.pop("ultralytics", None)
        else:
            sys.modules["ultralytics"] = old

    assert calls == ["face.pt", "face.pt"]
    assert first is not second


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
