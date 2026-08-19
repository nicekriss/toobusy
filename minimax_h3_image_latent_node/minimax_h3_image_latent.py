import torch

import comfy.model_management
import comfy.nested_tensor


class ToobusyMiniMaxH3ImageLatent:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "width": ("INT", {"default": 1344, "min": 32, "max": 16384, "step": 32}),
                "height": ("INT", {"default": 768, "min": 32, "max": 16384, "step": 32}),
            },
        }

    RETURN_TYPES = ("LATENT",)
    FUNCTION = "create"
    CATEGORY = "toobusy/Make"
    DESCRIPTION = "Creates the one-frame video+audio latent required to run MiniMax H3 with a T=1 image VAE."

    def create(self, width, height):
        device = comfy.model_management.intermediate_device()
        video = torch.zeros([1, 24, 1, height // 16, width // 16], device=device)
        audio = torch.zeros([1, 32, 2, 2], device=device)
        return ({"samples": comfy.nested_tensor.NestedTensor((video, audio))},)


NODE_CLASS_MAPPINGS = {
    "ToobusyMiniMaxH3ImageLatent": ToobusyMiniMaxH3ImageLatent,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ToobusyMiniMaxH3ImageLatent": "toobusy MiniMax H3 Image Latent",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
