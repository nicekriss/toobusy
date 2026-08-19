import importlib.util
import os
import sys
import types


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class _FakeTensor:
    def __init__(self, shape, device):
        self.shape = tuple(shape)
        self.device = device


class _FakeNestedTensor:
    def __init__(self, tensors):
        self.tensors = tensors


def _load_module():
    torch = types.ModuleType("torch")
    torch.zeros = lambda shape, device=None: _FakeTensor(shape, device)
    sys.modules["torch"] = torch

    comfy = types.ModuleType("comfy")
    comfy.__path__ = []
    model_management = types.ModuleType("comfy.model_management")
    model_management.intermediate_device = lambda: "test-device"
    nested_tensor = types.ModuleType("comfy.nested_tensor")
    nested_tensor.NestedTensor = _FakeNestedTensor
    comfy.model_management = model_management
    comfy.nested_tensor = nested_tensor
    sys.modules["comfy"] = comfy
    sys.modules["comfy.model_management"] = model_management
    sys.modules["comfy.nested_tensor"] = nested_tensor

    path = os.path.join(ROOT, "minimax_h3_image_latent_node", "minimax_h3_image_latent.py")
    spec = importlib.util.spec_from_file_location("toobusy_minimax_h3_image_latent", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_module = _load_module()


def test_creates_native_one_frame_h3_nested_latent():
    latent = _module.ToobusyMiniMaxH3ImageLatent().create(1344, 768)[0]
    video, audio = latent["samples"].tensors
    assert video.shape == (1, 24, 1, 48, 84)
    assert audio.shape == (1, 32, 2, 2)
    assert video.device == audio.device == "test-device"


def test_node_contract_is_single_image_only():
    required = _module.ToobusyMiniMaxH3ImageLatent.INPUT_TYPES()["required"]
    assert tuple(required) == ("width", "height")
    assert required["width"][1]["step"] == 32
    assert required["height"][1]["step"] == 32
    assert _module.ToobusyMiniMaxH3ImageLatent.RETURN_TYPES == ("LATENT",)
    assert _module.ToobusyMiniMaxH3ImageLatent.CATEGORY == "toobusy/Make"


if __name__ == "__main__":
    test_creates_native_one_frame_h3_nested_latent()
    test_node_contract_is_single_image_only()
    print("all tests passed")
