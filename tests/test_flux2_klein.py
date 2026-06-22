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
        if node_type == "LoraLoader":
            return ["<LoraLoader-model-out>", "<LoraLoader-clip-out>"]
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
    _ltx = sys.modules.get("toobusy.ltx23_compact_sampler_node.ltx23_compact_sampler")
    if _ltx is not None:
        _ltx._clear_loader_cache()  # test isolation: re-invoke loaders each run
    kwargs = dict(
        model_name="m", clip_name="c", vae_name="v", positive="p",
        size_mode="from reference",
        ratio_preset="1:1", megapixels=1.0, divisible_by=32, batch_size=1,
        seed=1, steps=4, sampler_name="euler", lora_slots=0, reference_slots=3,
        bundle_reference_order="standard",
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


def test_references_beyond_count_are_not_applied():
    # reference_slots=1 -> only slot 1 is applied even if more images are wired.
    _generate(reference_slots=1, reference_1_image=_FakeImage(512, 512), reference_2_image=_FakeImage(256, 256))
    assert len(_called("ReferenceLatent")) == 1


def test_unconnected_slots_are_skipped():
    # count covers 2 slots but only slot 2 has an image -> one reference applied.
    _generate(reference_slots=2, reference_2_image=_FakeImage(512, 512))
    assert len(_called("ReferenceLatent")) == 1


def test_supports_up_to_five_references():
    assert _mod.MAX_REFERENCE_SLOTS == 5
    images = {f"reference_{i}_image": _FakeImage(512, 512) for i in range(1, 6)}
    _generate(reference_slots=5, **images)
    assert len(_called("ReferenceLatent")) == 5
    # All five image sockets are exposed as optional inputs.
    optional = _mod.ToobusyFlux2Klein.INPUT_TYPES()["optional"]
    assert optional["toobusy_bundle"][0] == "TOOBUSY_BUNDLE"
    assert "reference_bundle" not in optional
    assert optional["use_bundle_prompt"][0] == "BOOLEAN"
    assert optional["use_bundle_loras"][0] == "BOOLEAN"
    order_spec = _mod.ToobusyFlux2Klein.INPUT_TYPES()["required"]["bundle_reference_order"]
    assert order_spec[0] == [
        "auto",
        "standard",
        "body_first_face_second",
        "face_first_body_second",
        "product_swap",
        "character_swap",
    ]
    assert order_spec[1]["default"] == "auto"
    for i in range(1, 6):
        assert optional[f"reference_{i}_image"][0] == "IMAGE"


def test_toobusy_bundle_fills_empty_reference_slots():
    bundle = {
        "main_character": {"image": _FakeImage(512, 512)},
        "pose": {"image": _FakeImage(384, 640)},
        "outfit": {"image": _FakeImage(256, 256)},
    }
    _generate(reference_slots=3, toobusy_bundle=bundle)
    assert len(_called("ReferenceLatent")) == 3
    scales = _called("ImageScaleToTotalPixels")
    assert [kw["image"] for kw in scales] == [
        bundle["main_character"]["image"],
        bundle["pose"]["image"],
        bundle["outfit"]["image"],
    ]


def test_individual_reference_overrides_bundle_slot():
    individual = _FakeImage(320, 640)
    bundle = {
        "main_character": {"image": _FakeImage(512, 512)},
        "pose": {"image": _FakeImage(384, 384)},
    }
    _generate(reference_slots=2, reference_1_image=individual, toobusy_bundle=bundle)
    scales = _called("ImageScaleToTotalPixels")
    assert len(scales) == 2
    assert scales[0]["image"] is individual
    assert scales[1]["image"] is bundle["pose"]["image"]


def test_universal_bundle_fills_reference_slots():
    char = _FakeImage(512, 512)
    pose = _FakeImage(384, 640)
    bundle = {
        "version": 1,
        "cards": [
            {"id": "char-a", "role": "character_a", "type": "character", "image": char},
            {"id": "pose-a", "role": "pose_a", "type": "pose", "image": pose},
        ],
    }
    _generate(reference_slots=2, toobusy_bundle=bundle)
    scales = _called("ImageScaleToTotalPixels")
    assert [kw["image"] for kw in scales] == [char, pose]


def test_bundle_reference_order_can_route_face_swap_inputs():
    body = _FakeImage(512, 512)
    face = _FakeImage(256, 256)
    outfit = _FakeImage(384, 384)
    bundle = {
        "cards": [
            {"role": "character_a", "type": "character", "image": body},
            {"role": "face_a", "type": "face", "image": face},
            {"role": "outfit_a", "type": "outfit", "image": outfit},
        ],
    }
    _generate(reference_slots=3, bundle_reference_order="body_first_face_second", toobusy_bundle=bundle)
    scales = _called("ImageScaleToTotalPixels")
    assert [kw["image"] for kw in scales] == [body, face, outfit]


def test_auto_order_follows_bundle_faceswap_flag():
    body = _FakeImage(512, 512)
    face = _FakeImage(256, 256)
    bundle = {
        "flags": {"face_swap": True, "reference_order": "body_first_face_second"},
        "cards": [
            {"role": "character_a", "type": "character", "image": body},
            {"role": "face_a", "type": "face", "image": face},
        ],
    }
    # auto (default) must follow flags.reference_order -> body then face.
    _generate(reference_slots=2, bundle_reference_order="auto", toobusy_bundle=bundle)
    scales = _called("ImageScaleToTotalPixels")
    assert [kw["image"] for kw in scales] == [body, face]


def test_resolve_reference_order_helper():
    assert _mod._resolve_reference_order("standard", {"flags": {"reference_order": "body_first_face_second"}}) == "standard"
    assert _mod._resolve_reference_order("auto", {"flags": {"reference_order": "body_first_face_second"}}) == "body_first_face_second"
    assert _mod._resolve_reference_order("auto", {}) == "standard"
    assert _mod._resolve_reference_order("auto", {"flags": {"reference_order": "bogus"}}) == "standard"
    assert _mod._resolve_reference_order("auto", {"flags": {"reference_order": "product_swap"}}) == "product_swap"


def test_product_swap_order_feeds_product_image():
    scene = _FakeImage(512, 512)
    product = _FakeImage(384, 384)
    bundle = {
        "flags": {"product_swap": True, "reference_order": "product_swap"},
        "cards": [
            {"role": "character_a", "type": "character", "image": scene},
            {"role": "prop_a", "type": "prop", "image": product},
        ],
    }
    # auto follows the flag -> main_character (scene) then product.
    _generate(reference_slots=2, bundle_reference_order="auto", toobusy_bundle=bundle)
    scales = _called("ImageScaleToTotalPixels")
    assert [kw["image"] for kw in scales] == [scene, product]


def test_character_swap_order_feeds_both_characters():
    a = _FakeImage(512, 512)
    b = _FakeImage(384, 384)
    bundle = {
        "flags": {"character_swap": True, "reference_order": "character_swap"},
        "cards": [
            {"role": "character_a", "type": "character", "image": a},
            {"role": "character_b", "type": "character", "image": b},
        ],
    }
    _generate(reference_slots=2, bundle_reference_order="auto", toobusy_bundle=bundle)
    scales = _called("ImageScaleToTotalPixels")
    assert [kw["image"] for kw in scales] == [a, b]


def test_bundle_prompt_overrides_positive_when_enabled():
    bundle = {"resolved_prompt": "bundle prompt text"}
    _generate(toobusy_bundle=bundle)
    encodes = _called("CLIPTextEncode")
    assert encodes and encodes[0]["text"] == "bundle prompt text"


def test_manual_positive_can_ignore_bundle_prompt():
    bundle = {"resolved_prompt": "bundle prompt text"}
    _generate(toobusy_bundle=bundle, use_bundle_prompt=False)
    encodes = _called("CLIPTextEncode")
    assert encodes and encodes[0]["text"] == "p"


def test_bundle_lora_applies_when_manual_loras_are_inactive():
    bundle = {"cards": [{"type": "lora", "role": "flux2_klein_faceswap_lora", "lora_name": "headswap.safetensors", "strength": 0.65}]}
    _generate(toobusy_bundle=bundle, use_bundle_loras=True, lora_slots=0)
    loras = _called("LoraLoader")
    assert len(loras) == 1
    assert loras[0]["lora_name"] == "headswap.safetensors"
    assert loras[0]["strength_model"] == 0.65


def test_manual_lora_overrides_bundle_loras():
    bundle = {"cards": [{"type": "lora", "lora_name": "bundle.safetensors", "strength": 0.65}]}
    _generate(
        toobusy_bundle=bundle,
        lora_slots=1,
        lora_1_enable=True,
        lora_1_name="manual.safetensors",
        lora_1_strength=0.9,
    )
    loras = _called("LoraLoader")
    assert len(loras) == 1
    assert loras[0]["lora_name"] == "manual.safetensors"


def test_internal_clip_loader_uses_flux2_type():
    _generate()
    clips = _called("CLIPLoader")
    assert clips and clips[0]["type"] == "flux2"


def test_from_reference_uses_reference_size():
    _generate(size_mode="from reference", reference_1_image=_FakeImage(510, 770))
    latents = _called("EmptyFlux2LatentImage")
    assert latents and (latents[0]["width"], latents[0]["height"]) == (768, 504)


def test_ratio_megapixels_mode_ignores_connected_reference():
    # The operator's case: 1:1 @ 1MP must win even with a reference connected.
    _generate(size_mode="ratio + megapixels", ratio_preset="1:1", megapixels=1.0,
              reference_1_image=_FakeImage(510, 770))
    latents = _called("EmptyFlux2LatentImage")
    # 1:1 @ 1MP, divisible_by 32 -> 992 x 992
    assert latents and (latents[0]["width"], latents[0]["height"]) == (992, 992)


def test_manual_mode_uses_width_height():
    _generate(size_mode="manual", reference_1_image=_FakeImage(512, 512), width=768, height=1280)
    latents = _called("EmptyFlux2LatentImage")
    assert latents and (latents[0]["width"], latents[0]["height"]) == (768, 1280)


def test_from_reference_without_reference_falls_back_to_ratio():
    _generate(size_mode="from reference", ratio_preset="1:1", megapixels=1.0)
    latents = _called("EmptyFlux2LatentImage")
    assert latents and (latents[0]["width"], latents[0]["height"]) == (992, 992)


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
