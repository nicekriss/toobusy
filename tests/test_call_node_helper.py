"""Regression tests for the shared `_call_node` helper (ltx23 module).

The operator hit this in the field: a core update gave ImageScaleToTotalPixels
a new required `resolution_steps` input, and calling the V3 node class
directly raised TypeError because V3 `execute` methods carry no Python
defaults — the graph executor fills them from the node schema. `_call_node`
must do the same: fill INPUT_TYPES defaults for missing inputs, resolve the
real signature behind the V3 *args/**kwargs normalizer, and still filter
unknown kwargs.

Standalone- and pytest-runnable, no ComfyUI runtime.
"""

import importlib.util
import os
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_NODE_REGISTRY = {}


def _install_stubs():
    nodes_mod = types.ModuleType("nodes")
    nodes_mod.NODE_CLASS_MAPPINGS = _NODE_REGISTRY
    sys.modules["nodes"] = nodes_mod


def _load(modname, relpath):
    path = os.path.join(ROOT, relpath)
    spec = importlib.util.spec_from_file_location(modname, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[modname] = module
    spec.loader.exec_module(module)
    return module


_install_stubs()
_mod = _load(
    "toobusy.ltx23_compact_sampler_node.ltx23_compact_sampler",
    os.path.join("ltx23_compact_sampler_node", "ltx23_compact_sampler.py"),
)


class _ClassicNode:
    """V1-style node: FUNCTION names a plain method with Python defaults."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "method": (["lanczos", "bilinear"],),
                "new_widget": ("INT", {"default": 7}),
            },
        }

    FUNCTION = "run"

    def run(self, image, method, new_widget=0):
        return (image, method, new_widget)


class _V3Node:
    """V3-style node: FUNCTION resolves to a *args/**kwargs normalizer and
    `execute` has required params whose defaults only exist in the schema —
    the exact shape that broke ImageScaleToTotalPixels."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "upscale_method": (["lanczos", "bilinear"],),
                "megapixels": ("FLOAT", {"default": 1.0}),
                "resolution_steps": ("INT", {"default": 8}),
            },
        }

    FUNCTION = "EXECUTE_NORMALIZED"

    @classmethod
    def EXECUTE_NORMALIZED(cls, *args, **kwargs):
        return cls.execute(*args, **kwargs)

    @classmethod
    def execute(cls, image, upscale_method, megapixels, resolution_steps):
        return (image, upscale_method, megapixels, resolution_steps)


def test_classic_node_gets_schema_default_for_missing_widget():
    _NODE_REGISTRY["Classic"] = _ClassicNode
    image, method, new_widget = _mod._call_node("Classic", image="img", method="lanczos")
    assert (image, method, new_widget) == ("img", "lanczos", 7)


def test_classic_node_filters_unknown_kwargs():
    _NODE_REGISTRY["Classic"] = _ClassicNode
    result = _mod._call_node("Classic", image="img", method="lanczos", bogus=123)
    assert result[0] == "img"


def test_v3_node_missing_required_schema_default_is_filled():
    _NODE_REGISTRY["V3"] = _V3Node
    # The field crash: caller predates resolution_steps entirely.
    image, method, mp, steps = _mod._call_node(
        "V3", image="img", upscale_method="lanczos", megapixels=1.0
    )
    assert steps == 8, "schema default must be filled like the graph executor does"


def test_v3_node_combo_without_default_uses_first_option():
    _NODE_REGISTRY["V3"] = _V3Node
    _, method, _, _ = _mod._call_node("V3", image="img", megapixels=2.0)
    assert method == "lanczos"


def test_v3_node_explicit_kwargs_win_over_defaults():
    _NODE_REGISTRY["V3"] = _V3Node
    *_, steps = _mod._call_node(
        "V3", image="img", upscale_method="bilinear", megapixels=2.0, resolution_steps=3
    )
    assert steps == 3


def test_v3_node_unknown_kwargs_filtered():
    _NODE_REGISTRY["V3"] = _V3Node
    result = _mod._call_node("V3", image="img", upscale_method="lanczos", megapixels=1.0, bogus=1)
    assert result[0] == "img"


class _PreviewNode:
    """A node with a preview UI returns {"ui": ..., "result": (...)} instead of
    a bare tuple — the shape that crashed ZIT ControlNet's DWPose call with
    KeyError: 0 when the caller did result[0]."""

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"image": ("IMAGE",)}}

    FUNCTION = "run"

    def run(self, image):
        return {"ui": {"images": ["preview.png"]}, "result": (f"processed-{image}",)}


def test_dict_result_with_ui_is_unwrapped():
    _NODE_REGISTRY["Preview"] = _PreviewNode
    result = _mod._call_node("Preview", image="img")
    # Must be the result tuple, so result[0] works (not the dict -> KeyError: 0).
    assert result[0] == "processed-img"


def test_plain_tuple_return_is_unchanged():
    _NODE_REGISTRY["Classic"] = _ClassicNode
    result = _mod._call_node("Classic", image="img", method="lanczos")
    assert isinstance(result, tuple) and result[0] == "img"


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
            except Exception as exc:  # noqa: BLE001 - regression visibility
                failures += 1
                print(f"ERROR {name}: {type(exc).__name__}: {exc}")
    if failures:
        print(f"\n{failures} test(s) failed")
        sys.exit(1)
    print("\nall tests passed")
