"""Regression tests for toobusy Z-Image Turbo resolution + img2img inputs.

Covers the optional ``width``/``height`` direct-resolution fields and the
optional ``image`` input that auto-switches the node to img2img:

  * explicit width/height feed EmptyLatentImage (rounded to divisible_by);
  * a connected image switches to img2img -> VAEEncode, never EmptyLatentImage;
  * with no explicit size, img2img output size follows the source image;
  * with explicit size, the source is ImageScale'd to it.

Standalone- and pytest-runnable, no ComfyUI runtime (see test_model_overrides).
"""

import importlib.util
import os
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# (node_type, kwargs) of every _call_node invocation in the last generate().
_CALLS = []


def _install_stubs():
    folder_paths = types.ModuleType("folder_paths")
    folder_paths.get_filename_list = lambda kind: []
    sys.modules["folder_paths"] = folder_paths

    def fake_call_node(node_type, **kwargs):
        _CALLS.append((node_type, kwargs))
        if node_type == "LoraLoader":
            return [f"<{node_type}-model>", f"<{node_type}-clip>"]
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
_zit = _load(
    "toobusy.z_image_turbo_node.z_image_turbo",
    os.path.join("z_image_turbo_node", "z_image_turbo.py"),
)


class _FakeImage:
    """Stand-in for a ComfyUI IMAGE tensor: shape [batch, height, width, ch]."""

    def __init__(self, height, width, batch=1, channels=3):
        self.shape = (batch, height, width, channels)


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


def _generate_wh(**overrides):
    """width/height-first view of generate(): the node now appends
    model/model_clean/clip/vae/positive/negative passthrough outputs after
    the original image/latent/width/height slots."""
    return _generate(**overrides)[2:]


def _called(node_type):
    return [kw for nt, kw in _CALLS if nt == node_type]


# --- passthrough outputs ----------------------------------------------------

def test_passthrough_outputs_expose_loaded_objects():
    result = _generate()
    assert len(result) == 10
    image, latent, w, h, model, model_clean, clip, vae, positive, negative = result
    # `model` is the final sampled model (shift applied here; no LoRA/controlnet
    # in this run); `model_clean` is the as-loaded model before any patching.
    assert model == "<ModelSamplingAuraFlow-out>"
    assert model_clean == "<UNETLoader-out>"
    assert clip == "<CLIPLoader-out>"
    assert vae == "<VAELoader-out>"
    assert positive == "<CLIPTextEncode-out>" and negative == "<CLIPTextEncode-out>"


def test_output_slot_order_is_backward_compatible():
    types = _zit.ToobusyZImageTurbo.RETURN_TYPES
    assert types[:4] == ("IMAGE", "LATENT", "INT", "INT"), "existing slots must not move"
    assert types[4:] == ("MODEL", "MODEL", "CLIP", "VAE", "CONDITIONING", "CONDITIONING")
    names = _zit.ToobusyZImageTurbo.RETURN_NAMES
    assert names[4:6] == ("model", "model_clean")


# --- conditioning / latent overrides -----------------------------------------

class _FakeLatent(dict):
    """Stand-in for a LATENT dict: {"samples": tensor [B, C, H/8, W/8]}."""

    def __init__(self, height_px, width_px):
        samples = types.SimpleNamespace(shape=(1, 16, height_px // 8, width_px // 8))
        super().__init__(samples=samples)


def test_positive_override_skips_its_text_encode():
    result = _generate(positive_override="ext-pos")
    encodes = _called("CLIPTextEncode")
    assert len(encodes) == 1 and encodes[0]["text"] == "n", "only the negative is encoded"
    assert result[8] == "ext-pos", "positive passthrough echoes the override"


def test_both_overrides_without_lora_skip_clip_loader():
    result = _generate(positive_override="ext-pos", negative_override="ext-neg")
    assert not _called("CLIPLoader"), "no prompt to encode and no LoRA -> no CLIP load"
    assert not _called("CLIPTextEncode")
    assert result[6] is None, "clip passthrough is None when the loader is skipped"
    assert result[8] == "ext-pos" and result[9] == "ext-neg"


def test_lora_still_loads_clip_with_both_overrides():
    _generate(
        positive_override="ext-pos", negative_override="ext-neg",
        lora_slots=1, lora_1_enable=True, lora_1_name="some.safetensors", lora_1_strength=1.0,
    )
    assert _called("CLIPLoader"), "LoRA application needs CLIP even with conditioning overrides"


def test_latent_override_wins_and_sets_size():
    latent = _FakeLatent(height_px=1280, width_px=768)
    result = _generate(latent_override=latent, image=_FakeImage(height=512, width=512))
    assert not _called("EmptyLatentImage") and not _called("VAEEncode"), "external latent bypasses both latent sources"
    assert _called("KSampler")[0]["latent_image"] is latent
    assert (result[2], result[3]) == (768, 1280), "width/height follow the latent dims"


# --- model auto-detection ----------------------------------------------------

def test_scan_picks_zimage_model_regardless_of_naming():
    names = ["aaa_first.safetensors", "z_image_bf16.safetensors", "wan21_14B.safetensors"]
    picked = _zit._scan_for(names, [("zimage", "turbo"), ("zimage",)])
    assert picked == "z_image_bf16.safetensors"


def test_scan_prefers_turbo_variant_over_plain():
    names = ["z_image_bf16.safetensors", "ZIT\\Z-Image-Turbo_fp8.safetensors"]
    picked = _zit._scan_for(names, [("zimage", "turbo"), ("zimage",)])
    assert picked == "ZIT\\Z-Image-Turbo_fp8.safetensors"


def test_scan_finds_text_encoder_and_vae_in_subfolders():
    clips = ["qwen3_4b.safetensors", "ZIT\\zImage_textEncoder.safetensors"]
    assert _zit._scan_for(clips, [("zimage", "textencoder"), ("zimage",)]) == "ZIT\\zImage_textEncoder.safetensors"
    vaes = ["sdxl_vae.safetensors", "ZIT\\zImage_vae.safetensors"]
    assert _zit._scan_for(vaes, [("zimage", "vae"), ("zimage",)]) == "ZIT\\zImage_vae.safetensors"


def test_scan_falls_back_to_first_when_nothing_matches():
    names = ["unrelated_a.safetensors", "unrelated_b.safetensors"]
    assert _zit._scan_for(names, [("zimage",)]) == "unrelated_a.safetensors"


# --- INPUT_TYPES exposure --------------------------------------------------

def test_exposes_image_width_height_inputs():
    optional = _zit.ToobusyZImageTurbo.INPUT_TYPES()["optional"]
    assert optional.get("image") == ("IMAGE",) or optional["image"][0] == "IMAGE"
    assert optional["width"][0] == "INT"
    assert optional["height"][0] == "INT"


def test_no_lora_auto_enabled_by_default():
    required = _zit.ToobusyZImageTurbo.INPUT_TYPES()["required"]
    assert required["lora_slots"][1]["default"] == 0
    assert required["lora_1_enable"][1]["default"] is False


# --- text-to-image (no image) ---------------------------------------------

def test_t2i_default_uses_empty_latent_from_ratio():
    w, h, *_ = _generate_wh()
    assert _called("EmptyLatentImage"), "t2i should build an EmptyLatentImage"
    assert not _called("VAEEncode"), "t2i must not VAE-encode"
    # 1:1 @ 1.0MP -> sqrt(1e6)=1000 -> round(1000/32)*32 = 992.
    assert (w, h) == (992, 992)


def test_t2i_explicit_width_height_override_ratio():
    w, h, *_ = _generate_wh(width=768, height=1280)
    empties = _called("EmptyLatentImage")
    assert empties and empties[0]["width"] == 768 and empties[0]["height"] == 1280
    assert (w, h) == (768, 1280)


def test_t2i_explicit_size_is_rounded_to_divisible_by():
    # 700 -> nearest multiple of 32 = 704; 1290 -> 1280.
    w, h, *_ = _generate_wh(width=700, height=1290, divisible_by=32)
    assert (w, h) == (704, 1280)


def test_t2i_single_dimension_falls_back_to_ratio():
    # Only width set (height 0) is not a complete manual size -> ratio path.
    w, h, *_ = _generate_wh(width=512, height=0)
    assert (w, h) == (992, 992)


# --- img2img (image connected) --------------------------------------------

def test_i2i_image_switches_to_vae_encode():
    img = _FakeImage(height=512, width=768)
    _generate(image=img)
    assert _called("VAEEncode"), "img2img should VAE-encode the source"
    assert not _called("EmptyLatentImage"), "img2img must not build an empty latent"


def test_i2i_native_size_follows_source_image():
    img = _FakeImage(height=512, width=768)
    w, h, *_ = _generate_wh(image=img)
    # source 768x512 already multiples of 8 -> reported as-is
    assert (w, h) == (768, 512)


def test_i2i_native_size_cropped_to_multiple_of_8():
    img = _FakeImage(height=510, width=770)  # not multiples of 8
    w, h, *_ = _generate_wh(image=img)
    assert (w, h) == (768, 504)  # 770//8*8=768, 510//8*8=504


def test_i2i_explicit_size_scales_source():
    img = _FakeImage(height=512, width=768)
    w, h, *_ = _generate_wh(image=img, width=1024, height=1024)
    scales = _called("ImageScale")
    assert scales and scales[0]["width"] == 1024 and scales[0]["height"] == 1024
    assert _called("VAEEncode")
    assert (w, h) == (1024, 1024)


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
