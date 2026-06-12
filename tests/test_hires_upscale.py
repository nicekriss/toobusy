"""Regression tests for toobusy Hires Upscale.

Covers the fold's call chain (UpscaleModelLoader -> ImageUpscaleWithModel ->
ImageScaleBy -> VAEEncode), the scale_by=1.0 resample skip, the
upscale_model override loader skip, and the INPUT_TYPES surface.

Standalone- and pytest-runnable, no ComfyUI runtime (see test_model_overrides).
"""

import importlib.util
import os
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_CALLS = []


def _install_stubs():
    folder_paths = types.ModuleType("folder_paths")
    folder_paths.get_filename_list = lambda kind: []
    sys.modules["folder_paths"] = folder_paths

    def fake_call_node(node_type, **kwargs):
        _CALLS.append((node_type, kwargs))
        if node_type == "ImageUpscaleWithModel":
            return [_FakeImage(2048, 4096)]  # 4x of the 512x1024 input
        if node_type == "ImageScaleBy":
            scale = kwargs["scale_by"]
            source = kwargs["image"]
            return [_FakeImage(int(source.shape[1] * scale), int(source.shape[2] * scale))]
        return [f"<{node_type}-out>"]

    pkg = types.ModuleType("toobusy")
    pkg.__path__ = [ROOT]
    sys.modules["toobusy"] = pkg

    sub = types.ModuleType("toobusy.ltx23_compact_sampler_node")
    sub.__path__ = [os.path.join(ROOT, "ltx23_compact_sampler_node")]
    sys.modules["toobusy.ltx23_compact_sampler_node"] = sub

    samp = types.ModuleType("toobusy.ltx23_compact_sampler_node.ltx23_compact_sampler")
    samp._call_node = fake_call_node
    sys.modules["toobusy.ltx23_compact_sampler_node.ltx23_compact_sampler"] = samp


class _FakeImage:
    """Stand-in for an IMAGE tensor: shape [batch, height, width, ch]."""

    def __init__(self, height, width):
        self.shape = (1, height, width, 3)


def _load(modname, relpath):
    path = os.path.join(ROOT, relpath)
    spec = importlib.util.spec_from_file_location(modname, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[modname] = module
    spec.loader.exec_module(module)
    return module


_install_stubs()
_mod = _load(
    "toobusy.hires_upscale_node.hires_upscale",
    os.path.join("hires_upscale_node", "hires_upscale.py"),
)


def _upscale(**overrides):
    _CALLS.clear()
    kwargs = dict(
        image=_FakeImage(512, 1024),
        vae="v",
        upscale_model_name="ESRGAN/4x_foolhardy_Remacri.pth",
        downscale_method="lanczos",
        scale_by=0.5,
    )
    kwargs.update(overrides)
    return _mod.ToobusyHiresUpscale().upscale(**kwargs)


def _called(node_type):
    return [kw for nt, kw in _CALLS if nt == node_type]


def test_full_chain_order_and_sizes():
    image, latent, width, height = _upscale()
    assert [nt for nt, _ in _CALLS] == [
        "UpscaleModelLoader",
        "ImageUpscaleWithModel",
        "ImageScaleBy",
        "VAEEncode",
    ]
    # 512x1024 -> 4x model -> 2048x4096 -> 0.5 -> 1024x2048
    assert (height, width) == (1024, 2048)
    assert image.shape[1] == 1024 and image.shape[2] == 2048
    assert latent == "<VAEEncode-out>"
    scaled = _called("ImageScaleBy")[0]
    assert scaled["upscale_method"] == "lanczos" and scaled["scale_by"] == 0.5


def test_scale_by_one_skips_resample():
    _, _, width, height = _upscale(scale_by=1.0)
    assert not _called("ImageScaleBy"), "scale_by=1.0 must skip the pointless resample"
    assert (height, width) == (2048, 4096)


def test_override_skips_internal_loader():
    _upscale(upscale_model="external-model")
    assert not _called("UpscaleModelLoader")
    assert _called("ImageUpscaleWithModel")[0]["upscale_model"] == "external-model"


def test_vae_encode_receives_final_pixels():
    _upscale()
    encode = _called("VAEEncode")[0]
    assert encode["vae"] == "v"
    assert encode["pixels"].shape[1] == 1024, "VAEEncode must get the post-resample pixels"


def test_input_types_surface():
    spec = _mod.ToobusyHiresUpscale.INPUT_TYPES()
    required = spec["required"]
    assert required["scale_by"][1]["default"] == 0.5
    assert "lanczos" in required["downscale_method"][0]
    assert spec["optional"]["upscale_model"][0] == "UPSCALE_MODEL"


def test_default_model_prefers_remacri():
    names = ["other_model.pth", "ESRGAN/4x_foolhardy_Remacri.pth", "another.pth"]
    assert _mod._default_model_name(names) == "ESRGAN/4x_foolhardy_Remacri.pth"
    assert _mod._default_model_name(["x.pth", "My_Remacri_v2.safetensors"]) == "My_Remacri_v2.safetensors"
    assert _mod._default_model_name(["only.pth"]) == "only.pth"


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
