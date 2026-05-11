from typing import List

import folder_paths


class HFModelAutoLoader:
    """
    Scan ComfyUI model folders for a requested model name.
    If found, returns the resolved model path and found=True.
    If missing, returns found=False with a status message and HF URL.
    """

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
                "model_name": ("STRING", {"default": "example.safetensors"}),
                "model_category": (list(cls.CATEGORY_FOLDERS.keys()),),
                "huggingface_url": (
                    "STRING",
                    {
                        "default": "https://huggingface.co/",
                        "multiline": False,
                    },
                ),
            }
        }

    RETURN_TYPES = ("STRING", "BOOLEAN", "STRING", "STRING")
    RETURN_NAMES = ("resolved_model_path", "found", "status", "download_url")
    FUNCTION = "scan_and_resolve"
    CATEGORY = "loaders"

    @staticmethod
    def _list_model_files(category: str) -> List[str]:
        return folder_paths.get_filename_list(category)

    @staticmethod
    def _resolve_full_path(category: str, filename: str) -> str:
        return folder_paths.get_full_path(category, filename) or ""

    def scan_and_resolve(self, model_name: str, model_category: str, huggingface_url: str):
        category = self.CATEGORY_FOLDERS[model_category]
        candidates = self._list_model_files(category)

        normalized = model_name.strip()
        lower_name = normalized.lower()

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

        if chosen:
            full_path = self._resolve_full_path(category, chosen)
            status = f"FOUND: {chosen}"
            return (full_path, True, status, huggingface_url)

        status = (
            f"MISSING: '{normalized}' not found in '{category}'. "
            "Use download_url to fetch it."
        )
        return ("", False, status, huggingface_url)


NODE_CLASS_MAPPINGS = {
    "HFModelAutoLoader": HFModelAutoLoader,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "HFModelAutoLoader": "HF Model Auto Loader",
}
