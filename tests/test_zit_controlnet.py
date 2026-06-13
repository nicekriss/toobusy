"""Regression tests for toobusy ZIT ControlNet + the Z-Image Turbo hookup.

Module side: slot gating (enable/image), per-type preprocessing dispatch,
the core-Canny threshold fallback, and the ZIT_CONTROL bundle shape.
Z-Image side: the bundle patches the final model via ModelPatchLoader +
QwenImageDiffsynthControlnet with generation-size control maps, stacking
one patch per entry — and absolutely nothing happens when no module is
connected (the existing behavior stays byte-identical).

Standalone- and pytest-runnable, no ComfyUI runtime (see test_model_overrides).
"""

import importlib.util
import os
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_CALLS = []
_AVAILABLE_NODES = set()


def _install_stubs():
    folder_paths = types.ModuleType("folder_paths")
    folder_paths.get_filename_list = lambda kind: []
    sys.modules["folder_paths"] = folder_paths

    nodes_mod = types.ModuleType("nodes")

    class _Mappings(dict):
        def __contains__(self, key):
            return key in _AVAILABLE_NODES

    nodes_mod.NODE_CLASS_MAPPINGS = _Mappings()
    sys.modules["nodes"] = nodes_mod

    def fake_call_node(node_type, **kwargs):
        _CALLS.append((node_type, kwargs))
        return [f"<{node_type}-out>"]

    pkg = types.ModuleType("toobusy")
    pkg.__path__ = [ROOT]
    sys.modules["toobusy"] = pkg

    sub = types.ModuleType("toobusy.ltx23_compact_sampler_node")
    sub.__path__ = [os.path.join(ROOT, "ltx23_compact_sampler_node")]
    sys.modules["toobusy.ltx23_compact_sampler_node"] = sub

    # Load the REAL shared module (z_image imports _scan_for from it now),
    # then patch only the runtime-touching helpers.
    ltx_path = os.path.join(ROOT, "ltx23_compact_sampler_node", "ltx23_compact_sampler.py")
    spec = importlib.util.spec_from_file_location(
        "toobusy.ltx23_compact_sampler_node.ltx23_compact_sampler", ltx_path
    )
    samp = importlib.util.module_from_spec(spec)
    sys.modules["toobusy.ltx23_compact_sampler_node.ltx23_compact_sampler"] = samp
    spec.loader.exec_module(samp)
    samp._call_node = fake_call_node
    samp._sampler_names = lambda: ["res_multistep", "euler"]
    samp._default_sampler_name = lambda names: names[0]


def _load(modname, relpath):
    path = os.path.join(ROOT, relpath)
    spec = importlib.util.spec_from_file_location(modname, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[modname] = module
    spec.loader.exec_module(module)
    return module


_install_stubs()
_cn = _load(
    "toobusy.zit_controlnet_node.zit_controlnet",
    os.path.join("zit_controlnet_node", "zit_controlnet.py"),
)
_zit = _load(
    "toobusy.z_image_turbo_node.z_image_turbo",
    os.path.join("z_image_turbo_node", "z_image_turbo.py"),
)


def _build(**overrides):
    _CALLS.clear()
    kwargs = dict(
        patch_name="Z-Image-Turbo-Fun-Controlnet-Union.safetensors",
        depth_enable=True, depth_strength=0.4, depth_preprocess=True,
        canny_enable=True, canny_strength=1.0, canny_preprocess=True,
        pose_enable=True, pose_strength=1.0, pose_preprocess=True,
        preprocessor_resolution=512, canny_low=100, canny_high=200,
    )
    kwargs.update(overrides)
    return _cn.ToobusyZITControlNet().build(**kwargs)


def _called(node_type):
    return [kw for nt, kw in _CALLS if nt == node_type]


def _entries(result):
    return result["result"][0]["entries"]


# --- module: slot gating ------------------------------------------------------

def test_no_images_yields_empty_bundle():
    result = _build()
    assert _entries(result) == []
    assert result["result"][0]["patch_name"].endswith("Union.safetensors")


def test_disabled_slot_is_skipped():
    _AVAILABLE_NODES.update({"MiDaS-DepthMapPreprocessor"})
    result = _build(depth_image="img", depth_enable=False)
    assert _entries(result) == []


def test_each_slot_carries_own_image_and_strength():
    _AVAILABLE_NODES.update({"MiDaS-DepthMapPreprocessor", "CannyEdgePreprocessor", "DWPreprocessor"})
    result = _build(depth_image="A", canny_image="B", pose_image="C", depth_strength=0.4, canny_strength=0.7, pose_strength=1.0)
    entries = _entries(result)
    assert [(e["type"], e["strength"]) for e in entries] == [("depth", 0.4), ("canny", 0.7), ("pose", 1.0)]
    assert len(_called("MiDaS-DepthMapPreprocessor")) == 1
    assert len(_called("CannyEdgePreprocessor")) == 1
    assert len(_called("DWPreprocessor")) == 1


def test_preprocess_off_passes_image_through():
    result = _build(depth_image="ready-map", depth_preprocess=False)
    entries = _entries(result)
    assert entries[0]["image"] == "ready-map"
    assert not _called("MiDaS-DepthMapPreprocessor")
    assert not _called("ImageScaleToTotalPixels")


def test_canny_falls_back_to_core_node_with_float_thresholds():
    _AVAILABLE_NODES.clear()
    _AVAILABLE_NODES.add("Canny")
    _build(canny_image="B", canny_low=102, canny_high=204)
    core = _called("Canny")
    assert core, "core Canny fallback should be used when the aux pack is missing"
    assert abs(core[0]["low_threshold"] - 0.4) < 0.01
    assert abs(core[0]["high_threshold"] - 0.8) < 0.01


def test_missing_preprocessor_raises_helpful_error():
    _AVAILABLE_NODES.clear()
    try:
        _build(pose_image="C")
    except RuntimeError as exc:
        assert "DWPreprocessor" in str(exc) and "controlnet_aux" in str(exc)
    else:
        raise AssertionError("expected RuntimeError for missing pose preprocessor")


# --- Z-Image Turbo: bundle application ----------------------------------------

def _generate(**overrides):
    _CALLS.clear()
    kwargs = dict(
        model_name="m", clip_name="c", vae_name="v", positive="p", negative="n",
        ratio_preset="1:1", megapixels=1.0, divisible_by=32, batch_size=1, seed=1,
        steps=8, cfg=1.0, sampler_name="res_multistep", scheduler="simple",
        denoise=1.0, aura_shift=3.0, lora_slots=0,
    )
    kwargs.update(overrides)
    return _zit.ToobusyZImageTurbo().generate(**kwargs)


def test_zimage_without_module_applies_no_patch():
    _generate()
    assert not _called("ModelPatchLoader")
    assert not _called("QwenImageDiffsynthControlnet")


def test_zimage_applies_one_patch_per_entry_at_generation_size():
    control = {
        "patch_name": "union.safetensors",
        "entries": [
            {"type": "depth", "image": "map-A", "strength": 0.4},
            {"type": "pose", "image": "map-C", "strength": 1.0},
        ],
    }
    result = _generate(zit_control=control, width=768, height=1280)
    # Passthrough flavors: `model` carries the controlnet patches, `model_clean`
    # is the as-loaded model (slots 4 and 5).
    assert result[4] == "<QwenImageDiffsynthControlnet-out>"
    assert result[5] == "<UNETLoader-out>"
    loaders = _called("ModelPatchLoader")
    assert len(loaders) == 1 and loaders[0]["name"] == "union.safetensors"
    patches = _called("QwenImageDiffsynthControlnet")
    assert [p["strength"] for p in patches] == [0.4, 1.0]
    # control maps resized to the actual generation size
    scales = [kw for kw in _called("ImageScale") if kw.get("image") in ("map-A", "map-C")]
    assert all(kw["width"] == 768 and kw["height"] == 1280 for kw in scales)
    # patches chain: second patch receives the first patch's output model
    assert patches[1]["model"] == "<QwenImageDiffsynthControlnet-out>"
    # and the sampler runs on the patched model
    assert _called("KSampler")[0]["model"] == "<QwenImageDiffsynthControlnet-out>"


def test_zimage_empty_bundle_is_a_noop():
    _generate(zit_control={"patch_name": "union.safetensors", "entries": []})
    assert not _called("ModelPatchLoader")
    assert not _called("QwenImageDiffsynthControlnet")


def test_zimage_exposes_zit_control_input():
    optional = _zit.ToobusyZImageTurbo.INPUT_TYPES()["optional"]
    assert optional["zit_control"][0] == "ZIT_CONTROL"


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            _AVAILABLE_NODES.clear()
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
