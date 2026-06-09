"""Regression tests for the external MODEL/CLIP/VAE override inputs on the
folded samplers (Ideogram4 T2I, Z-Image Turbo).

These nodes normally load UNET/CLIP/VAE internally. The override inputs let an
advanced user feed pre-built MODEL/CLIP/VAE objects from any compatible loader;
when an override is connected the matching internal loader must be skipped.

The test loads the node modules standalone (no running ComfyUI) by stubbing
``folder_paths`` and the shared ``_call_node`` helper, then asserts:
  1. the override keys are exposed in ``INPUT_TYPES()["optional"]`` with the
     right socket type, and
  2. ``generate()`` skips the internal loader for each connected override and
     still runs every internal loader when no override is connected.

Runs under pytest (``test_*`` functions) and standalone
(``python tests/test_model_overrides.py``) so it works in this repo's
compile-only CI without adding a pytest dependency.
"""

import importlib.util
import os
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Internal loader node types that an override must bypass.
LOADER_NODES = ("UNETLoader", "CLIPLoader", "VAELoader")

# Shared call log populated by the stubbed _call_node.
_CALLS = []


def _install_stubs():
    """Stub the ComfyUI runtime so the node modules import standalone."""
    folder_paths = types.ModuleType("folder_paths")
    folder_paths.get_filename_list = lambda kind: []
    sys.modules["folder_paths"] = folder_paths

    def fake_call_node(node_type, **kwargs):
        _CALLS.append(node_type)
        return [f"<{node_type}-out>"]

    pkg = types.ModuleType("toobusy")
    pkg.__path__ = [ROOT]
    sys.modules["toobusy"] = pkg

    sub = types.ModuleType("toobusy.ltx23_compact_sampler_node")
    sub.__path__ = [os.path.join(ROOT, "ltx23_compact_sampler_node")]
    sys.modules["toobusy.ltx23_compact_sampler_node"] = sub

    samp = types.ModuleType("toobusy.ltx23_compact_sampler_node.ltx23_compact_sampler")
    samp._call_node = fake_call_node
    samp._sampler_names = lambda: ["res_multistep", "euler"]
    samp._default_sampler_name = lambda names: names[0]
    sys.modules["toobusy.ltx23_compact_sampler_node.ltx23_compact_sampler"] = samp


def _load(modname, relpath):
    path = os.path.join(ROOT, relpath)
    spec = importlib.util.spec_from_file_location(modname, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[modname] = module
    spec.loader.exec_module(module)
    return module


_install_stubs()
_ideo = _load(
    "toobusy.ideogram4_t2i_node.ideogram4_t2i",
    os.path.join("ideogram4_t2i_node", "ideogram4_t2i.py"),
)
_zit = _load(
    "toobusy.z_image_turbo_node.z_image_turbo",
    os.path.join("z_image_turbo_node", "z_image_turbo.py"),
)


def _loaders_called():
    return [c for c in _CALLS if c in LOADER_NODES]


# --- INPUT_TYPES exposure -------------------------------------------------

def test_zimage_exposes_override_inputs():
    optional = _zit.ToobusyZImageTurbo.INPUT_TYPES()["optional"]
    assert optional.get("model_override") == ("MODEL",)
    assert optional.get("clip_override") == ("CLIP",)
    assert optional.get("vae_override") == ("VAE",)


def test_ideogram4_exposes_override_inputs():
    optional = _ideo.ToobusyIdeogram4T2I.INPUT_TYPES()["optional"]
    assert optional.get("model_override") == ("MODEL",)
    assert optional.get("uncond_model_override") == ("MODEL",)
    assert optional.get("clip_override") == ("CLIP",)
    assert optional.get("vae_override") == ("VAE",)


# --- loader-skip behaviour ------------------------------------------------

def _run_zimage(**overrides):
    _CALLS.clear()
    _zit.ToobusyZImageTurbo().generate(
        model_name="m", clip_name="c", vae_name="v", positive="p", negative="n",
        ratio_preset="1:1", megapixels=1.0, divisible_by=32, batch_size=1, seed=1,
        steps=8, cfg=1.0, sampler_name="res_multistep", scheduler="simple",
        denoise=1.0, aura_shift=3.0, lora_slots=0, **overrides,
    )


def _run_ideogram4(**overrides):
    _CALLS.clear()
    _ideo.ToobusyIdeogram4T2I().generate(
        model_name="m", unconditional_model_name="um", clip_name="c", vae_name="v",
        prompt="{}", quality="Turbo", steps=0, ratio_preset="1:1", megapixels=1.0,
        seed=0, sampler_name="res_multistep", cfg=7.0, lora_slots=0, **overrides,
    )


def test_zimage_overrides_skip_internal_loaders():
    _run_zimage(
        model_override="EXT_M", clip_override="EXT_C", vae_override="EXT_V",
    )
    assert _loaders_called() == [], "override connected but internal loaders ran"


def test_zimage_no_override_runs_all_loaders():
    _run_zimage()
    assert sorted(_loaders_called()) == sorted(LOADER_NODES)


def test_ideogram4_overrides_skip_internal_loaders():
    _run_ideogram4(
        model_override="EXT_M", uncond_model_override="EXT_UM",
        clip_override="EXT_C", vae_override="EXT_V",
    )
    assert _loaders_called() == [], "override connected but internal loaders ran"


def test_ideogram4_no_override_runs_all_loaders():
    _run_ideogram4()
    # Ideogram4 loads two UNETs (conditional + unconditional) plus CLIP + VAE.
    called = _loaders_called()
    assert called.count("UNETLoader") == 2
    assert called.count("CLIPLoader") == 1
    assert called.count("VAELoader") == 1


def test_ideogram4_partial_override_skips_only_connected():
    # Only the conditional model is overridden; the other three loaders run.
    _run_ideogram4(model_override="EXT_M")
    called = _loaders_called()
    assert called.count("UNETLoader") == 1  # only the unconditional UNET loads
    assert called.count("CLIPLoader") == 1
    assert called.count("VAELoader") == 1


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
