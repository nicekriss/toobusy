"""Regression tests for the compact Wan Animate 2 long sampler."""

import importlib.util
import os
import sys
import types


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CALLS = []


def _load(modname, relpath):
    path = os.path.join(ROOT, relpath)
    spec = importlib.util.spec_from_file_location(modname, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[modname] = module
    spec.loader.exec_module(module)
    return module


pkg = types.ModuleType("toobusy")
pkg.__path__ = [ROOT]
sys.modules["toobusy"] = pkg

ltx_pkg = types.ModuleType("toobusy.ltx23_compact_sampler_node")
ltx_pkg.__path__ = [os.path.join(ROOT, "ltx23_compact_sampler_node")]
sys.modules["toobusy.ltx23_compact_sampler_node"] = ltx_pkg
ltx = types.ModuleType("toobusy.ltx23_compact_sampler_node.ltx23_compact_sampler")
ltx._sampler_names = lambda: ["lcm"]
ltx._fill_input_defaults = lambda cls, kwargs, params, has_var_keyword: kwargs
sys.modules["toobusy.ltx23_compact_sampler_node.ltx23_compact_sampler"] = ltx

scail_pkg = types.ModuleType("toobusy.wan_scail_extend_sampler_node")
scail_pkg.__path__ = [os.path.join(ROOT, "wan_scail_extend_sampler_node")]
sys.modules["toobusy.wan_scail_extend_sampler_node"] = scail_pkg
_load(
    "toobusy.wan_scail_extend_sampler_node.wan_scail_extend_sampler",
    os.path.join("wan_scail_extend_sampler_node", "wan_scail_extend_sampler.py"),
)
_mod = _load(
    "toobusy.wan_animate2_long_sampler_node.wan_animate2_long_sampler",
    os.path.join("wan_animate2_long_sampler_node", "wan_animate2_long_sampler.py"),
)


class _FakeFrames:
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
    if class_name == "WanAnimate2ToVideo":
        offset = kwargs["video_frame_offset"]
        trim_image = 1 if kwargs["continue_motion"] is not None else 0
        if trim_image:
            offset = max(0, offset - 1)
        return ("p+", "n+", {"samples": "latent"}, 1, trim_image, offset + kwargs["length"])
    if class_name == "SamplerCustom":
        return ("sampled", "denoised")
    if class_name == "TrimVideoLatent":
        return ("trimmed",)
    if class_name == "VAEDecode":
        length = next(kw["length"] for name, kw in reversed(_CALLS) if name == "WanAnimate2ToVideo")
        return (_FakeFrames(length),)
    raise AssertionError(class_name)


def _generate(**overrides):
    _CALLS.clear()
    _mod._call_core = _fake_call_core
    _mod._animate_output_count = lambda: 6
    fake_torch = types.ModuleType("torch")
    fake_torch.cat = lambda chunks, dim=0: _FakeFrames(sum(chunk.count for chunk in chunks))
    kwargs = dict(
        model="patched-model",
        positive="positive-conditioning",
        negative="negative-conditioning",
        sampler="sampler",
        sigmas="sigmas",
        vae="vae",
        reference_image=_FakeFrames(1),
        pose_video=_FakeFrames(500),
        width=482,
        height=854,
        total_frames=241,
        frames_per_sampler=81,
        seed=10,
        cfg=1.0,
        reference_image_strength=1.0,
        pose_strength=1.0,
        pose_start_percent=0.0,
        pose_end_percent=1.0,
        color_match=False,
        color_match_strength=1.0,
    )
    kwargs.update(overrides)
    real_torch = sys.modules.get("torch")
    sys.modules["torch"] = fake_torch
    try:
        return _mod.ToobusyWanAnimate2LongSampler().generate(**kwargs)
    finally:
        if real_torch is not None:
            sys.modules["torch"] = real_torch
        else:
            del sys.modules["torch"]


def _called(name):
    return [kwargs for node_name, kwargs in _CALLS if node_name == name]


def test_plan_uses_one_frame_overlap():
    assert _mod._plan_chunks(241, 81, 10) == [(81, 10), (81, 11), (81, 12)]


def test_plan_builds_valid_last_chunk_then_output_crops_exactly():
    plan = _mod._plan_chunks(300, 81, 0)
    assert all((length - 1) % 4 == 0 for length, _seed in plan)
    images, frame_count, chunk_count = _generate(total_frames=300)
    assert images.count == frame_count == 300
    assert chunk_count == len(plan)


def test_551_frame_link_plan_finishes_at_exact_target():
    plan = _mod._plan_chunks(551, 81, 0)
    assert [length for length, _seed in plan] == [81, 81, 81, 81, 81, 81, 69, 5]
    images, frame_count, chunk_count = _generate(total_frames_input=551, pose_video=_FakeFrames(551))
    assert images.count == frame_count == 551
    assert chunk_count == 8


def test_final_core_sockets_are_exposed_directly():
    inputs = _mod.ToobusyWanAnimate2LongSampler.INPUT_TYPES()
    required = inputs["required"]
    assert required["model"][0] == "MODEL"
    assert required["positive"][0] == "CONDITIONING"
    assert required["negative"][0] == "CONDITIONING"
    assert required["sampler"][0] == "SAMPLER"
    assert required["sigmas"][0] == "SIGMAS"
    assert "clip" not in required and "sampler_name" not in required and "scheduler" not in required
    assert inputs["optional"]["positive_pose"][0] == "CONDITIONING"


def test_chunks_chain_motion_offset_and_seed():
    images, frame_count, chunk_count = _generate()
    animate = _called("WanAnimate2ToVideo")
    assert chunk_count == len(animate) == 3
    assert animate[0]["continue_motion"] is None and animate[0]["video_frame_offset"] == 0
    assert animate[1]["continue_motion"] is not None and animate[1]["video_frame_offset"] == 81
    assert animate[2]["video_frame_offset"] == 161
    assert [call["noise_seed"] for call in _called("SamplerCustom")] == [10, 11, 12]
    assert images.count == frame_count == 241


def test_conditioning_and_patched_model_pass_through_untouched():
    _generate(positive_pose="pose-conditioning")
    animate = _called("WanAnimate2ToVideo")
    assert all(call["positive"] == "positive-conditioning" for call in animate)
    assert all(call["positive_pose"] == "pose-conditioning" for call in animate)
    assert all(call["model"] == "patched-model" for call in _called("SamplerCustom"))


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except Exception as exc:
                failures += 1
                print(f"FAIL {name}: {exc}")
    if failures:
        raise SystemExit(1)
    print("all tests passed")
