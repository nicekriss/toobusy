"""Regression tests for the optional toobusy Background Remove node.

The node must stay lightweight at import time (no rembg/torch/PIL at module
load). Dependencies are checked only when the node runs.
"""

import importlib.util
import os
import sys


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load():
    path = os.path.join(ROOT, "background_remove_node", "background_remove.py")
    spec = importlib.util.spec_from_file_location("toobusy.background_remove_node.background_remove", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_mod = _load()


def test_missing_dependencies_message():
    def missing(_name):
        raise ImportError(_name)

    missing_names = _mod._missing_optional_dependencies(missing)
    assert "rembg" in missing_names
    assert "onnxruntime" in missing_names
    try:
        _mod._ensure_rembg(missing)
    except RuntimeError as exc:
        text = str(exc)
        assert "Background Remove optional dependencies are missing." in text
        assert "requirements_rembg.txt" in text
    else:
        raise AssertionError("missing optional dependencies should raise")


def test_background_rgb_mapping():
    assert _mod._background_rgb("white") == (1.0, 1.0, 1.0)
    assert _mod._background_rgb("black") == (0.0, 0.0, 0.0)
    assert _mod._background_rgb("green") == (0.0, 1.0, 0.0)
    # Unknown name falls back to white.
    assert _mod._background_rgb("does-not-exist") == (1.0, 1.0, 1.0)


def test_contract():
    inputs = _mod.ToobusyBackgroundRemove.INPUT_TYPES()
    assert inputs["required"]["image"][0] == "IMAGE"
    assert inputs["required"]["model"][0] == _mod.REMBG_MODELS
    assert inputs["required"]["model"][1]["default"] == "u2net"
    assert "white" in inputs["required"]["background"][0]
    assert inputs["optional"]["alpha_matting"][0] == "BOOLEAN"
    assert _mod.ToobusyBackgroundRemove.RETURN_TYPES == ("IMAGE", "MASK")
    assert _mod.ToobusyBackgroundRemove.RETURN_NAMES == ("image", "mask")


def test_composite_frame_blends_over_background():
    np = _try_numpy()
    if np is None:
        print("SKIP test_composite_frame_blends_over_background (no numpy)")
        return "SKIP"
    # 1x1 pixel: full red foreground, half alpha, over white bg.
    rgba = np.array([[[1.0, 0.0, 0.0, 0.5]]], dtype="float32")
    rgb, alpha = _mod._composite_frame(rgba, (1.0, 1.0, 1.0), np)
    assert alpha.shape == (1, 1)
    assert abs(float(alpha[0, 0]) - 0.5) < 1e-6
    # red*0.5 + white*0.5 = (1.0, 0.5, 0.5)
    assert abs(float(rgb[0, 0, 0]) - 1.0) < 1e-6
    assert abs(float(rgb[0, 0, 1]) - 0.5) < 1e-6
    assert abs(float(rgb[0, 0, 2]) - 0.5) < 1e-6


def _try_numpy():
    try:
        import numpy as np

        return np
    except ImportError:
        return None


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
