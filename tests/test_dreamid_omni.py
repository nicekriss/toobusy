"""Regression tests for the optional toobusy DreamID-Omni wrapper.

The wrapper delegates to the upstream benjiyaya/ComfyUI_Dreamid-Omni nodes
(resolved by name from ComfyUI's NODE_CLASS_MAPPINGS). Tests patch that single
seam (`_upstream_class`) with fakes so no real model/GPU is needed.
"""

import importlib.util
import os
import sys


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load():
    path = os.path.join(ROOT, "dreamid_omni_node", "dreamid_omni.py")
    spec = importlib.util.spec_from_file_location("toobusy.dreamid_omni_node.dreamid_omni", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_mod = _load()


class _FakeImage:
    def __init__(self, frames=2, height=64, width=64):
        self.shape = (frames, height, width, 3)
        self.sliced = False

    def __getitem__(self, item):
        assert item == slice(0, 1)
        out = _FakeImage(1, self.shape[1], self.shape[2])
        out.sliced = True
        return out


class _FakeSampler:
    calls = []

    def sample(self, **kwargs):
        _FakeSampler.calls.append(kwargs)
        return ({"frames": 1},)


class _FakeLoader:
    calls = []

    def load(self, **kwargs):
        _FakeLoader.calls.append(kwargs)
        return ({"engine": "E", "config": "C"},)


def _patch_upstream(loader=None, sampler=None, no_dep_check=True):
    """Patch the upstream-resolution seam; returns a restore callable."""
    original = _mod._upstream_class
    original_dep = _mod._ensure_optional_dependencies

    def fake(name):
        if name == _mod.UPSTREAM_LOADER_NAME:
            return loader
        if name == _mod.UPSTREAM_SAMPLER_NAME:
            return sampler
        return None

    _mod._upstream_class = fake
    if no_dep_check:
        _mod._ensure_optional_dependencies = lambda *a, **k: None

    def restore():
        _mod._upstream_class = original
        _mod._ensure_optional_dependencies = original_dep

    return restore


def test_loader_missing_dependencies_message():
    def missing(_name):
        raise ImportError(_name)

    missing_names = _mod._missing_optional_dependencies(missing)
    assert "diffusers" in missing_names
    try:
        _mod._ensure_optional_dependencies(missing)
    except RuntimeError as exc:
        text = str(exc)
        assert "DreamID-Omni optional dependencies are missing." in text
        assert "requirements_dreamid_omni.txt" in text
    else:
        raise AssertionError("missing optional dependencies should raise")


def test_loader_delegates_to_upstream():
    _FakeLoader.calls = []
    restore = _patch_upstream(loader=_FakeLoader)
    try:
        pipeline, info = _mod.ToobusyDreamIDOmniLoader().load(
            model_file="dreamid_omni_bf16.safetensors",
            precision="FP8",
            attention_backend="SDPA",
        )
        assert pipeline == {"engine": "E", "config": "C"}
        assert _FakeLoader.calls[0]["model_file"] == "dreamid_omni_bf16.safetensors"
        assert _FakeLoader.calls[0]["precision"] == "FP8"
        assert "delegated_to" in info
    finally:
        restore()


def test_talker_extracts_bundle_inputs_and_delegates():
    _FakeSampler.calls = []
    image_a = _FakeImage(frames=3)
    image_b = _FakeImage(frames=4)
    audio_a = {"waveform": "a", "sample_rate": 16000}
    audio_b = {"waveform": "b", "sample_rate": 16000}
    bundle = {
        "version": 1,
        "resolved_prompt": "bundle prompt wins",
        "cards": [
            {"role": "character_a", "image": image_a},
            {"role": "character_b", "image": image_b},
            {"role": "audio_a", "audio": audio_a},
            {"role": "audio_b", "audio": audio_b},
        ],
    }
    restore = _patch_upstream(sampler=_FakeSampler)
    try:
        video, out_bundle, prompt, selected_json = _mod.ToobusyDreamIDOmniTalker().talk(
            pipeline={"engine": "E", "config": "C"},
            toobusy_bundle=bundle,
            prompt="fallback",
            sample_steps=8,
            seed=11,
            width=512,
            height=768,
            solver_name="euler",
        )
    finally:
        restore()
    assert video == {"frames": 1}
    assert prompt == "bundle prompt wins"
    call = _FakeSampler.calls[0]
    assert call["ref_image"].shape[0] == 1
    assert call["ref_image2"].shape[0] == 1
    assert call["ref_audio"] is audio_a
    assert call["ref_audio2"] is audio_b
    assert call["pipeline"] == {"engine": "E", "config": "C"}
    assert out_bundle["flags"]["dreamid_talker_applied"] is True
    assert '"person2_audio": true' in selected_json
    assert '"two_person": true' in selected_json


def test_talker_drops_unpaired_second_person():
    _FakeSampler.calls = []
    bundle = {
        "resolved_prompt": "single",
        "cards": [
            {"role": "character_a", "image": _FakeImage(frames=1)},
            {"role": "character_b", "image": _FakeImage(frames=1)},
            {"role": "audio_a", "audio": {"waveform": "a", "sample_rate": 16000}},
            # No audio_b -> second person is unpaired and must be dropped.
        ],
    }
    restore = _patch_upstream(sampler=_FakeSampler)
    try:
        _video, _out, _prompt, selected_json = _mod.ToobusyDreamIDOmniTalker().talk(
            pipeline={}, toobusy_bundle=bundle, prompt="", sample_steps=8, seed=1,
            width=512, height=512, solver_name="unipc",
        )
    finally:
        restore()
    call = _FakeSampler.calls[0]
    assert call["ref_image2"] is None
    assert call["ref_audio2"] is None
    assert '"two_person": false' in selected_json


def test_talker_requires_character_a_and_audio_a():
    bundle = {"cards": [{"role": "character_a", "image": _FakeImage(frames=1)}]}  # no audio
    restore = _patch_upstream(sampler=_FakeSampler)
    try:
        raised = False
        try:
            _mod.ToobusyDreamIDOmniTalker().talk(
                pipeline={}, toobusy_bundle=bundle, prompt="", sample_steps=8, seed=1,
                width=512, height=512, solver_name="unipc",
            )
        except RuntimeError as exc:
            raised = True
            assert "Audio A" in str(exc)
        assert raised, "talker should require Character A image + Audio A"
    finally:
        restore()


def test_missing_upstream_raises_install_message():
    restore = _patch_upstream(loader=None, sampler=None)
    try:
        raised = False
        try:
            _mod.ToobusyDreamIDOmniTalker().talk(
                pipeline={}, toobusy_bundle={"resolved_prompt": "x"}, prompt="", sample_steps=8,
                seed=1, width=512, height=512, solver_name="unipc",
            )
        except RuntimeError as exc:
            raised = True
            assert "ComfyUI_Dreamid-Omni" in str(exc)
        assert raised, "missing upstream node should raise a clear install message"
    finally:
        restore()


def test_contracts_are_bundle_first():
    loader_inputs = _mod.ToobusyDreamIDOmniLoader.INPUT_TYPES()
    talker_inputs = _mod.ToobusyDreamIDOmniTalker.INPUT_TYPES()
    # Upstream not installed in tests -> loader uses the fallback widgets.
    assert loader_inputs["required"]["precision"][1]["default"] == "FP8"
    assert loader_inputs["required"]["attention_backend"][1]["default"] == "SDPA"
    assert talker_inputs["required"]["toobusy_bundle"][0] == "TOOBUSY_BUNDLE"
    assert _mod.ToobusyDreamIDOmniTalker.RETURN_TYPES == (
        "VIDEO",
        "TOOBUSY_BUNDLE",
        "STRING",
        "STRING",
    )


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
            except Exception as exc:  # noqa: BLE001
                failures += 1
                print(f"ERROR {name}: {type(exc).__name__}: {exc}")
    if failures:
        print(f"\n{failures} test(s) failed")
        sys.exit(1)
    print("\nall tests passed")
