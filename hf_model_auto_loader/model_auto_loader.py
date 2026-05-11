from typing import Dict, List, Tuple

import folder_paths
from nodes import CheckpointLoaderSimple


PRESETS: Dict[str, Dict[str, str]] = {
    "none": {"model_name": "", "model_category": "checkpoints", "huggingface_url": "https://huggingface.co/"},
    "sdxl_base_1.0": {
        "model_name": "sd_xl_base_1.0.safetensors",
        "model_category": "checkpoints",
        "huggingface_url": "https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0",
    },
    "flux1_dev": {
        "model_name": "flux1-dev.safetensors",
        "model_category": "checkpoints",
        "huggingface_url": "https://huggingface.co/black-forest-labs/FLUX.1-dev",
    },
    "ponydiffusion_v6xl": {
        "model_name": "ponyDiffusionV6XL_v6StartWithThisOne.safetensors",
        "model_category": "checkpoints",
        "huggingface_url": "https://huggingface.co/LyliaEngine/PonyDiffusion-V6-XL",
    },
}


class HFModelAutoLoader:
    CATEGORY_FOLDERS = {
        "checkpoints": "checkpoints",
        "loras": "loras",
        "vae": "vae",
        "controlnet": "controlnet",
        "clip": "clip",
        "unet": "unet",
        "embeddings": "embeddings",
    }

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "preset": (list(PRESETS.keys()),),
                "model_name": ("STRING", {"default": ""}),
                "model_category": (list(cls.CATEGORY_FOLDERS.keys()),),
                "huggingface_url": ("STRING", {"default": "https://huggingface.co/", "multiline": False}),
                "autoload_checkpoint": ("BOOLEAN", {"default": True}),
            }
        }

    RETURN_TYPES = ("STRING", "BOOLEAN", "STRING", "STRING", "MODEL", "CLIP", "VAE")
    RETURN_NAMES = (
        "resolved_model_path",
        "found",
        "status",
        "download_url",
        "model",
        "clip",
        "vae",
    )
    FUNCTION = "scan_and_resolve"
    CATEGORY = "loaders"

    @staticmethod
    def _list_model_files(category: str) -> List[str]:
        return folder_paths.get_filename_list(category)

    @staticmethod
    def _resolve_full_path(category: str, filename: str) -> str:
        return folder_paths.get_full_path(category, filename) or ""

    @staticmethod
    def _select_from_preset(
        preset: str, model_name: str, model_category: str, huggingface_url: str
    ) -> Tuple[str, str, str]:
        if preset == "none":
            return (model_name.strip(), model_category, huggingface_url.strip())

        item = PRESETS[preset]
        name = item["model_name"]
        category = item["model_category"]
        url = item["huggingface_url"]

        if model_name.strip():
            name = model_name.strip()
        if huggingface_url.strip():
            url = huggingface_url.strip()

        return (name, category, url)

    def scan_and_resolve(
        self,
        preset: str,
        model_name: str,
        model_category: str,
        huggingface_url: str,
        autoload_checkpoint: bool,
    ):
        name, category, url = self._select_from_preset(preset, model_name, model_category, huggingface_url)
        candidates = self._list_model_files(category)

        lower_name = name.lower()
        exact = None
        suffix = None

        for candidate in candidates:
            c_low = candidate.lower()
            if c_low == lower_name:
                exact = candidate
                break
            if c_low.endswith(lower_name):
                suffix = candidate

        chosen = exact or suffix
        if not chosen:
            status = f"MISSING: '{name}' not found in '{category}'."
            return ("", False, status, url, None, None, None)

        full_path = self._resolve_full_path(category, chosen)

        if category == "checkpoints" and autoload_checkpoint:
            model, clip, vae = CheckpointLoaderSimple().load_checkpoint(chosen)
            return (full_path, True, f"FOUND+LOADED: {chosen}", url, model, clip, vae)

        status = f"FOUND: {chosen} (autoload skipped: category={category})"
        return (full_path, True, status, url, None, None, None)


NODE_CLASS_MAPPINGS = {"HFModelAutoLoader": HFModelAutoLoader}
NODE_DISPLAY_NAME_MAPPINGS = {"HFModelAutoLoader": "HF Model Auto Loader + Preset"}
