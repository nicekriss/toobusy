"""Regression tests for toobusy Load CLIP.

Locks in the vocab-fit behavior: when a fine-tuned LLM text encoder ships
more tokens than the core model expects (Dolphin: 128258 vs 128256), the
node grows the model's embedding to the file's size — keeping every token —
instead of trimming. Loading is delegated to the standard loaders (GGUF pack
for .gguf, core CLIPLoader otherwise) and the resizing hook is always
restored.

Standalone- and pytest-runnable, no ComfyUI runtime.
"""

import importlib.util
import os
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_CALLS = []
_NODE_REGISTRY = {}


def _install_stubs():
    nodes_mod = types.ModuleType("nodes")
    nodes_mod.NODE_CLASS_MAPPINGS = _NODE_REGISTRY
    sys.modules["nodes"] = nodes_mod

    folder_paths = types.ModuleType("folder_paths")
    folder_paths.get_filename_list = lambda kind: []
    sys.modules["folder_paths"] = folder_paths

    def fake_call_node(node_type, **kwargs):
        _CALLS.append((node_type, kwargs))
        return [f"<{node_type}-clip>"]

    pkg = types.ModuleType("toobusy")
    pkg.__path__ = [ROOT]
    sys.modules["toobusy"] = pkg

    sub = types.ModuleType("toobusy.ltx23_compact_sampler_node")
    sub.__path__ = [os.path.join(ROOT, "ltx23_compact_sampler_node")]
    sys.modules["toobusy.ltx23_compact_sampler_node"] = sub

    samp = types.ModuleType("toobusy.ltx23_compact_sampler_node.ltx23_compact_sampler")
    samp._call_node = fake_call_node
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
    "toobusy.load_clip_node.load_clip",
    os.path.join("load_clip_node", "load_clip.py"),
)

try:
    import torch  # noqa: F401

    _HAS_TORCH = True
except ImportError:
    _HAS_TORCH = False


# --- pure resize decision ----------------------------------------------------

def test_resize_grows_to_checkpoint_when_bigger():
    # Dolphin case: checkpoint 128258 vs model 128256 -> grow to 128258.
    assert _mod._resize_target((128258, 4096), (128256, 4096)) == (128258, 4096)


def test_resize_none_when_equal():
    assert _mod._resize_target((128256, 4096), (128256, 4096)) is None


def test_resize_none_when_smaller_or_rank_differs():
    # Smaller checkpoint isn't a grow case (let the normal loader decide).
    assert _mod._resize_target((128000, 4096), (128256, 4096)) is None
    # Mixed (one bigger, one smaller) is not a clean grow.
    assert _mod._resize_target((128258, 2048), (128256, 4096)) is None
    # Different rank -> leave alone.
    assert _mod._resize_target((128258,), (128256, 4096)) is None


# --- dispatch ---------------------------------------------------------------

def _run(clip_name, **overrides):
    _CALLS.clear()
    kwargs = dict(type="lumina2", fit_model_to_file=False, device="default")
    kwargs.update(overrides)
    return _mod.ToobusyLoadClip().load(clip_name, **kwargs)


def test_safetensors_routes_to_core_cliploader():
    _NODE_REGISTRY.clear()
    _NODE_REGISTRY["CLIPLoader"] = object
    result = _run("ZIT/zImage_textEncoder.safetensors")
    assert _CALLS and _CALLS[0][0] == "CLIPLoader"
    assert result[0] == "<CLIPLoader-clip>"


def test_gguf_routes_to_gguf_pack():
    _NODE_REGISTRY.clear()
    _NODE_REGISTRY["ClipLoaderGGUF"] = object
    _run("Dolphin3.0-Llama3.1-8B-Q8_0.gguf")
    assert _CALLS and _CALLS[0][0] == "ClipLoaderGGUF"


def test_gguf_without_pack_errors_clearly():
    _NODE_REGISTRY.clear()  # no GGUF loader installed
    try:
        _run("something.gguf")
    except RuntimeError as exc:
        assert "GGUF" in str(exc) and "ComfyUI-GGUF" in str(exc)
    else:
        raise AssertionError("expected RuntimeError when no GGUF loader is present")


# --- resizing hook (torch only) ---------------------------------------------

def test_resizing_hook_grows_param_and_loads(capsys=None):
    if not _HAS_TORCH:
        print("SKIP test_resizing_hook_grows_param_and_loads (no torch)")
        return
    import torch

    # A model whose embedding is the core size (128256-ish, scaled down).
    class _Model(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.embed = torch.nn.Embedding(10, 4)

    model = _Model()
    loaded = {}

    # Stub the delegate to mimic the core loader: build the (too small) model,
    # then load an oversized checkpoint into it via load_state_dict.
    def fake_delegate(self, clip_name, type, device):
        checkpoint = {"embed.weight": torch.ones(12, 4)}  # 12 > 10: added tokens
        missing_unexpected = model.load_state_dict(checkpoint, strict=False)
        loaded["weight_rows"] = model.embed.weight.shape[0]
        return "clip-ok"

    original_delegate = _mod.ToobusyLoadClip._delegate
    _mod.ToobusyLoadClip._delegate = fake_delegate
    try:
        result = _mod.ToobusyLoadClip().load("custom.safetensors", type="lumina2", fit_model_to_file=True)
    finally:
        _mod.ToobusyLoadClip._delegate = original_delegate

    assert result == ("clip-ok",)
    assert loaded["weight_rows"] == 12, "embedding should have grown to the checkpoint size (all tokens kept)"
    # The global torch method must be restored after the call.
    assert torch.nn.Module.load_state_dict.__name__ == "load_state_dict"


def test_hook_restored_even_on_error():
    if not _HAS_TORCH:
        print("SKIP test_hook_restored_even_on_error (no torch)")
        return
    import torch

    before = torch.nn.Module.load_state_dict

    def boom(self, clip_name, type, device):
        raise RuntimeError("loader blew up")

    original_delegate = _mod.ToobusyLoadClip._delegate
    _mod.ToobusyLoadClip._delegate = boom
    try:
        _mod.ToobusyLoadClip().load("x.safetensors", type="lumina2", fit_model_to_file=True)
    except RuntimeError:
        pass
    finally:
        _mod.ToobusyLoadClip._delegate = original_delegate

    assert torch.nn.Module.load_state_dict is before, "hook must be restored after an error"


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
