"""Regression tests for toobusy Wan SCAIL Extend Sampler.

Covers the pure fold logic that must never drift:

  * the chunk plan (base + N extend segments, per-chunk seeds);
  * kept-frame math (extends drop the re-rendered overlap);
  * INPUT_TYPES exposing the dynamic extend_segments counter + slots;
  * generate() wiring: per-chunk WanSCAILToVideo -> SamplerCustom ->
    VAEDecode calls, offset chaining, fresh text conditioning;
  * the clear error when the installed core's WanSCAILToVideo predates
    the SCAIL-2 extend inputs.

Standalone- and pytest-runnable, no ComfyUI runtime (see test_model_overrides).
Tests that need torch are skipped when torch is not installed.
"""

import importlib.util
import os
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_CALLS = []


def _install_stubs():
    pkg = types.ModuleType("toobusy")
    pkg.__path__ = [ROOT]
    sys.modules["toobusy"] = pkg

    sub = types.ModuleType("toobusy.ltx23_compact_sampler_node")
    sub.__path__ = [os.path.join(ROOT, "ltx23_compact_sampler_node")]
    sys.modules["toobusy.ltx23_compact_sampler_node"] = sub

    samp = types.ModuleType("toobusy.ltx23_compact_sampler_node.ltx23_compact_sampler")
    samp._sampler_names = lambda: ["euler", "res_multistep"]
    sys.modules["toobusy.ltx23_compact_sampler_node.ltx23_compact_sampler"] = samp


def _load(modname, relpath):
    path = os.path.join(ROOT, relpath)
    spec = importlib.util.spec_from_file_location(modname, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[modname] = module
    spec.loader.exec_module(module)
    return module


_install_stubs()
_mod = _load(
    "toobusy.wan_scail_extend_sampler_node.wan_scail_extend_sampler",
    os.path.join("wan_scail_extend_sampler_node", "wan_scail_extend_sampler.py"),
)

try:
    import torch  # noqa: F401

    _HAS_TORCH = True
except ImportError:
    _HAS_TORCH = False


class _FakeFrames:
    """Stand-in for an IMAGE tensor [T, H, W, C] supporting the slicing the
    node does (drop overlap, take last frame)."""

    def __init__(self, count):
        self.count = count

    @property
    def shape(self):
        return (self.count, 8, 8, 3)

    def __getitem__(self, item):
        if isinstance(item, slice):
            return _FakeFrames(len(range(*item.indices(self.count))))
        raise TypeError(item)


def _fake_call_core(class_name, hint="", **kwargs):
    _CALLS.append((class_name, kwargs))
    if class_name == "WanSCAILToVideo":
        offset = kwargs["video_frame_offset"]
        prev = kwargs["previous_frames"]
        if prev is not None:
            offset = max(0, offset - kwargs["previous_frame_count"])
        return ("pos+", "neg+", {"samples": f"latent{kwargs['length']}"}, offset + kwargs["length"])
    if class_name == "SamplerCustom":
        return ("output-latent", "denoised-latent")
    if class_name == "VAEDecode":
        # Find the matching chunk length from the last SCAIL call.
        length = next(kw["length"] for name, kw in reversed(_CALLS) if name == "WanSCAILToVideo")
        return (_FakeFrames(length),)
    return (f"<{class_name}-out>",)


def _generate(**overrides):
    _CALLS.clear()
    _mod._call_core = _fake_call_core
    _mod._scail_missing_params = lambda: []

    # generate() only needs torch.cat; feed it a fake so these wiring tests run
    # on _FakeFrames with or without a real torch install.
    fake_torch = types.ModuleType("torch")

    def fake_cat(chunks, dim=0):
        assert dim == 0
        return _FakeFrames(sum(chunk.count for chunk in chunks))

    fake_torch.cat = fake_cat

    kwargs = dict(
        model="m", clip="c", vae="v", reference_image="ref", pose_video="pose",
        positive="p", negative="n", width=512, height=896,
        base_frames=65, extend_segments=0, seed=7, steps=6, cfg=1.0,
        sampler_name="euler", scheduler="simple", shift=5.0,
        previous_frame_count=5, color_match=False, replacement_mode=False,
        pose_strength=1.0, pose_start=0.0, pose_end=1.0, clip_vision_crop="none",
    )
    kwargs.update(overrides)

    real_torch = sys.modules.get("torch")
    sys.modules["torch"] = fake_torch
    try:
        return _mod.ToobusyWanSCAILExtendSampler().generate(**kwargs)
    finally:
        if real_torch is not None:
            sys.modules["torch"] = real_torch
        else:
            del sys.modules["torch"]


def _called(node_type):
    return [kw for nt, kw in _CALLS if nt == node_type]


# --- pure helpers ------------------------------------------------------------

def test_chunk_plan_base_only():
    assert _mod._chunk_plan(65, 0, [81] * 8, 7) == [(65, 7)]


def test_chunk_plan_with_segments_steps_seed():
    plan = _mod._chunk_plan(65, 2, [81, 49] + [81] * 6, 7)
    assert plan == [(65, 7), (81, 8), (49, 9)]


def test_chunk_plan_clamps_segment_count():
    assert len(_mod._chunk_plan(65, 99, [81] * 8, 0)) == 1 + _mod.MAX_EXTEND_SEGMENTS


def test_kept_frame_counts_trims_overlap_on_extends_only():
    plan = [(65, 0), (81, 1), (81, 2)]
    assert _mod._kept_frame_counts(plan, 5) == [65, 76, 76]


# --- INPUT_TYPES -------------------------------------------------------------

def test_exposes_dynamic_segment_widgets():
    required = _mod.ToobusyWanSCAILExtendSampler.INPUT_TYPES()["required"]
    assert required["extend_segments"][1]["default"] == 0
    assert required["extend_segments"][1]["max"] == _mod.MAX_EXTEND_SEGMENTS
    for slot in range(1, _mod.MAX_EXTEND_SEGMENTS + 1):
        assert required[f"extend_{slot}_frames"][0] == "INT"


def test_masks_and_clip_vision_are_optional_inputs():
    optional = _mod.ToobusyWanSCAILExtendSampler.INPUT_TYPES()["optional"]
    assert optional["pose_video_mask"][0] == "IMAGE"
    assert optional["reference_image_mask"][0] == "IMAGE"
    assert optional["clip_vision"][0] == "CLIP_VISION"


# --- generate() wiring -------------------------------------------------------

def test_base_only_runs_one_chunk():
    images, frame_count = _generate()
    assert len(_called("WanSCAILToVideo")) == 1
    assert len(_called("SamplerCustom")) == 1
    assert len(_called("VAEDecode")) == 1
    assert frame_count == 65 and images.count == 65


def test_two_extends_chain_offset_and_previous_frames():
    images, frame_count = _generate(extend_segments=2, extend_1_frames=81, extend_2_frames=81)
    scail = _called("WanSCAILToVideo")
    assert len(scail) == 3
    # base: no previous frames, offset 0
    assert scail[0]["previous_frames"] is None and scail[0]["video_frame_offset"] == 0
    # ext1: offset = base length, previous frames provided
    assert scail[1]["video_frame_offset"] == 65 and scail[1]["previous_frames"] is not None
    # ext2: offset = (65-5) + 81 = 141 per the core node's adjusted-offset output
    assert scail[2]["video_frame_offset"] == 141
    # output: 65 + 76 + 76
    assert frame_count == 65 + 76 + 76 == images.count


def test_each_chunk_gets_fresh_text_conditioning_and_own_seed():
    _generate(extend_segments=1, extend_1_frames=81, seed=10)
    # Text encoded once per prompt, reused for every chunk (fresh, not chained).
    assert len(_called("CLIPTextEncode")) == 2
    scail = _called("WanSCAILToVideo")
    assert all(kw["positive"] == "<CLIPTextEncode-out>" for kw in scail)
    seeds = [kw["noise_seed"] for kw in _called("SamplerCustom")]
    assert seeds == [10, 11]


def test_clip_vision_encoded_only_when_connected():
    _generate()
    assert not _called("CLIPVisionEncode")
    _generate(clip_vision="cv")
    encodes = _called("CLIPVisionEncode")
    assert encodes and encodes[0]["image"] == "ref" and encodes[0]["crop"] == "none"


def test_shift_zero_skips_model_patch():
    _generate(shift=0.0)
    assert not _called("ModelSamplingSD3")
    _generate(shift=5.0)
    assert _called("ModelSamplingSD3")


def test_segment_not_longer_than_overlap_is_rejected():
    try:
        _generate(extend_segments=1, extend_1_frames=5, previous_frame_count=5)
    except ValueError as exc:
        assert "extend_1_frames" in str(exc)
    else:
        raise AssertionError("expected ValueError for segment <= overlap")


def test_old_core_without_scail2_inputs_fails_clearly():
    _CALLS.clear()
    _mod._call_core = _fake_call_core
    _mod._scail_missing_params = lambda: ["previous_frames"]
    try:
        _mod.ToobusyWanSCAILExtendSampler().generate(
            model="m", clip="c", vae="v", reference_image="r", pose_video="p",
            positive="", negative="", width=512, height=896, base_frames=65,
            extend_segments=0, seed=1, steps=6, cfg=1.0, sampler_name="euler",
            scheduler="simple", shift=5.0, previous_frame_count=5,
            color_match=False, replacement_mode=False, pose_strength=1.0,
            pose_start=0.0, pose_end=1.0, clip_vision_crop="none",
        )
    except RuntimeError as exc:
        assert "previous_frames" in str(exc) and "Update ComfyUI" in str(exc)
    else:
        raise AssertionError("expected RuntimeError on old core")


# --- color transfer (torch only) ---------------------------------------------

def test_color_match_identity_when_stats_match():
    if not _HAS_TORCH:
        print("SKIP test_color_match_identity_when_stats_match (no torch)")
        return
    import torch

    frames = torch.rand(3, 16, 16, 3)
    reference = frames[-1:]
    matched = _mod._match_color_to_reference(frames[-1:], reference)
    assert torch.allclose(matched, reference, atol=0.02), "self-transfer should be near-identity"


def test_color_match_moves_toward_reference_stats():
    if not _HAS_TORCH:
        print("SKIP test_color_match_moves_toward_reference_stats (no torch)")
        return
    import torch

    dark = torch.rand(2, 16, 16, 3) * 0.3
    bright = torch.rand(1, 16, 16, 3) * 0.3 + 0.7
    matched = _mod._match_color_to_reference(dark, bright)
    assert matched.mean() > dark.mean() + 0.2, "transfer should pull means toward the reference"
    assert matched.min() >= 0.0 and matched.max() <= 1.0


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
