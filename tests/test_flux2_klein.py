"""Regression tests for toobusy Flux2 Klein (post-review fixes).

Locks in the review fixes on the folded Flux2 Klein node:

  * references are applied through REAL core nodes
    (ImageScaleToTotalPixels 1MP lanczos -> VAEEncode -> ReferenceLatent),
    chained on the conditioning — not the unreachable subgraph-UUID classes
    the first prototype called;
  * the internal CLIP loader uses type="flux2" (not lumina2);
  * disabled / unconnected reference slots are skipped;
  * default sizing follows the first active reference image;
  * passthrough outputs (model / model_clean / clip / vae / positive) follow
    the toobusy convention with backward-compatible slot order.

Standalone- and pytest-runnable, no ComfyUI runtime.
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
        return [f"<{node_type}-out>"]

    pkg = types.ModuleType("toobusy")
    pkg.__path__ = [ROOT]
    sys.modules["toobusy"] = pkg

    sub = types.ModuleType("toobusy.ltx23_compact_sampler_node")
    sub.__path__ = [os.path.join(ROOT, "ltx23_compact_sampler_node")]
    sys.modules["toobusy.ltx23_compact_sampler_node"] = sub

    ltx_path = os.path.join(ROOT, "ltx23_compact_sampler_node", "ltx23_compact_sampler.py")
    spec = importlib.util.spec_from_file_location(
        "toobusy.ltx23_compact_sampler_node.ltx23_compact_sampler", ltx_path
    )
    samp = importlib.util.module_from_spec(spec)
    sys.modules["toobusy.ltx23_compact_sampler_node.ltx23_compact_sampler"] = samp
    spec.loader.exec_module(samp)
    samp._call_node = fake_call_node
    samp._sampler_names = lambda: ["euler", "res_multistep"]
    samp._default_sampler_name = lambda names: names[0]


def _load(modname, relpath):
    path = os.path.join(ROOT, relpath)
    spec = importlib.util.spec_from_file_location(modname, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[modname] = module
    spec.loader.exec_module(module)
    return module


_install_stubs()
_mod = _load(
    "toobusy.flux2_klein_node.flux2_klein",
    os.path.join("flux2_klein_node", "flux2_klein.py"),
)


class _FakeImage:
    def __init__(self, height, width):
        self.shape = (1, height, width, 3)


def _generate(**overrides):
    _CALLS.clear()
    kwargs = dict(
        model_name="m", clip_name="c", vae_name="v", positive="p",
        ratio_preset="1:1", megapixels=1.0, divisible_by=32, batch_size=1,
        seed=1, steps=4, sampler_name="euler", lora_slots=0, reference_slots=3,
        reference_1_enable=True, reference_2_enable=True, reference_3_enable=True,
    )
    kwargs.update(overrides)
    return _mod.ToobusyFlux2Klein().generate(**kwargs)


def _called(node_type):
    return [kw for nt, kw in _CALLS if nt == node_type]


def test_references_use_real_core_chain():
    _generate(reference_1_image=_FakeImage(512, 768), reference_2_image=_FakeImage(256, 256))
    scales = _called("ImageScaleToTotalPixels")
    assert len(scales) == 2
    assert all(kw["upscale_method"] == "lanczos" and kw["megapixels"] == 1.0 for kw in scales)
    assert len(_called("VAEEncode")) == 2
    refs = _called("ReferenceLatent")
    assert len(refs) == 2
    # The second ReferenceLatent chains on the first one's conditioning output.
    assert refs[0]["conditioning"] == "<CLIPTextEncode-out>"
    assert refs[1]["conditioning"] == "<ReferenceLatent-out>"
    # No UUID-typed calls anywhere (the prototype's unreachable subgraph ids).
    assert all("-" not in nt or nt.count("-") < 4 for nt, _ in _CALLS)


def test_disabled_or_missing_references_are_skipped():
    _generate(reference_1_image=_FakeImage(512, 512), reference_1_enable=False)
    assert not _called("ReferenceLatent")


def test_internal_clip_loader_uses_flux2_type():
    _generate()
    clips = _called("CLIPLoader")
    assert clips and clips[0]["type"] == "flux2"


def test_size_follows_first_active_reference():
    _generate(reference_1_image=_FakeImage(510, 770))
    latents = _called("EmptyFlux2LatentImage")
    assert latents and (latents[0]["width"], latents[0]["height"]) == (768, 504)


def test_manual_size_wins_over_reference():
    _generate(reference_1_image=_FakeImage(512, 512), width=768, height=1280)
    latents = _called("EmptyFlux2LatentImage")
    assert latents and (latents[0]["width"], latents[0]["height"]) == (768, 1280)


def test_passthrough_outputs_and_slot_order():
    result = _generate()
    assert len(result) == 9
    image, latent, w, h, model, model_clean, clip, vae, positive = result
    assert model == "<FluxKVCache-out>", "final model includes the KV cache patch"
    assert model_clean == "<UNETLoader-out>", "clean model predates LoRA/KV"
    assert clip == "<CLIPLoader-out>" and vae == "<VAELoader-out>"
    types_ = _mod.ToobusyFlux2Klein.RETURN_TYPES
    assert types_[:4] == ("IMAGE", "LATENT", "INT", "INT"), "existing slots must not move"


def test_default_scan_keywords_find_operator_files():
    scan = sys.modules["toobusy.ltx23_compact_sampler_node.ltx23_compact_sampler"]._scan_for
    models = ["wan21_14B.safetensors", "FLUX2\\flux-2-klein-9b-fp8.safetensors"]
    assert scan(models, [("flux2", "klein"), ("klein",)]) == "FLUX2\\flux-2-klein-9b-fp8.safetensors"
    clips = ["ZIT\\zImage_textEncoder.safetensors", "flux2\\qwen38BFluxKlein9BTE_38b.safetensors"]
    assert scan(clips, [("qwen", "klein"), ("qwen",)]) == "flux2\\qwen38BFluxKlein9BTE_38b.safetensors"
    vaes = ["sdxl_vae.safetensors", "flux2\\flux2-vae.safetensors"]
    assert scan(vaes, [("flux2", "vae"), ("flux2",)]) == "flux2\\flux2-vae.safetensors"


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
