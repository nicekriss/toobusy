import torch
from safetensors.torch import load_file

from .utils import init_weights_on_device
from .wan_video_dit import WanModel
from .wan_video_vae import WanVideoVAE


class ModelManager:
    """FlashVSR-only model loader matching the small pipeline contract."""

    def __init__(self, torch_dtype=torch.bfloat16, device="cpu"):
        self.torch_dtype = torch_dtype
        self.device = device
        self.models = {}

    def load_dit(self, path):
        state_dict = load_file(path, device="cpu")
        converter = WanModel.state_dict_converter()
        converted, config = converter.from_civitai(state_dict)
        if config:
            state_dict = converted
        else:
            state_dict, config = converter.from_diffusers(state_dict)
        if not config:
            raise ValueError("Unsupported FlashVSR DiT checkpoint format.")
        with init_weights_on_device():
            model = WanModel(**config)
        model.load_state_dict(state_dict, assign=True)
        model.to(device=self.device, dtype=self.torch_dtype)
        model.eval()
        self.models["wan_video_dit"] = model

    def load_vae(self, path):
        state_dict = torch.load(path, map_location="cpu", weights_only=True)
        state_dict = WanVideoVAE.state_dict_converter().from_civitai(state_dict)
        with init_weights_on_device():
            model = WanVideoVAE()
        model.load_state_dict(state_dict, assign=True)
        model.to(device=self.device, dtype=self.torch_dtype)
        model.eval()
        self.models["wan_video_vae"] = model

    def fetch_model(self, name):
        return self.models.get(name)
