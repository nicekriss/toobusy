import os
from typing import List

import folder_paths


class HFModelAutoLoader:
    """
    Scan ComfyUI model folders for a requested model.

    If the file already exists, return its resolved path and found=True.
    If it is missing, optionally download it from Hugging Face (either a full
    file URL or a `repo_id` + filename) into the right ComfyUI model folder,
    then return the resolved path.
    """

    CATEGORY_FOLDERS = {
        "checkpoints": "checkpoints",
        "loras": "loras",
        "vae": "vae",
        "controlnet": "controlnet",
        "clip": "clip",
        "text_encoders": "text_encoders",
        "diffusion_models": "diffusion_models",
        "unet": "unet",
        "embeddings": "embeddings",
    }

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model_name": ("STRING", {"default": "example.safetensors"}),
                "model_category": (list(cls.CATEGORY_FOLDERS.keys()),),
                "download_if_missing": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "tooltip": (
                            "When on, a missing model is actually downloaded from "
                            "hf_source (a real network download on queue), not just "
                            "located. Off by default so the node only scans/reports."
                        ),
                    },
                ),
                "hf_source": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": False,
                        "tooltip": (
                            "Either a Hugging Face repo id (e.g. 'owner/repo') "
                            "or a full file URL (https://huggingface.co/owner/repo/resolve/main/file.safetensors)."
                        ),
                    },
                ),
                "hf_filename": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": False,
                        "tooltip": (
                            "Path of the file inside the repo. Leave blank to use model_name. "
                            "Ignored when hf_source is a full file URL."
                        ),
                    },
                ),
            }
        }

    RETURN_TYPES = ("STRING", "BOOLEAN", "STRING", "STRING")
    RETURN_NAMES = ("resolved_model_path", "found", "status", "download_url")
    FUNCTION = "scan_and_resolve"
    CATEGORY = "toobusy/Setup"

    @staticmethod
    def _list_model_files(category: str) -> List[str]:
        try:
            return folder_paths.get_filename_list(category)
        except Exception:
            return []

    @staticmethod
    def _resolve_full_path(category: str, filename: str) -> str:
        return folder_paths.get_full_path(category, filename) or ""

    @staticmethod
    def _target_dir(category: str) -> str:
        paths = folder_paths.get_folder_paths(category)
        if not paths:
            raise RuntimeError(f"No registered folder path for category '{category}'.")
        os.makedirs(paths[0], exist_ok=True)
        return paths[0]

    def _find(self, category: str, model_name: str):
        lower_name = model_name.lower()
        suffix = None
        for candidate in self._list_model_files(category):
            c_low = candidate.lower()
            if c_low == lower_name:
                return candidate
            if c_low.endswith(lower_name):
                suffix = candidate
        return suffix

    def _download(self, category, model_name, hf_source, hf_filename):
        source = hf_source.strip()
        if not source:
            raise RuntimeError(
                "download_if_missing is on but hf_source is empty. "
                "Provide a repo id or a full file URL."
            )

        target_dir = self._target_dir(category)

        # Full file URL path -> stream download with the requested model_name.
        if source.startswith("http://") or source.startswith("https://"):
            dest = os.path.join(target_dir, os.path.basename(model_name) or os.path.basename(source))
            self._download_url(source, dest)
            return dest

        # Otherwise treat source as a repo id and use huggingface_hub.
        repo_filename = (hf_filename.strip() or model_name).strip()
        try:
            from huggingface_hub import hf_hub_download
        except Exception as exc:
            raise RuntimeError(
                "huggingface_hub is not installed. Run 'pip install huggingface_hub' "
                "or use a full file URL in hf_source instead."
            ) from exc

        return hf_hub_download(
            repo_id=source,
            filename=repo_filename,
            local_dir=target_dir,
        )

    @staticmethod
    def _download_url(url: str, dest: str):
        import urllib.request

        tmp = dest + ".part"
        request = urllib.request.Request(url, headers={"User-Agent": "toobusy-hf-loader"})
        with urllib.request.urlopen(request) as response, open(tmp, "wb") as out:
            while True:
                chunk = response.read(1 << 20)
                if not chunk:
                    break
                out.write(chunk)
        os.replace(tmp, dest)

    def scan_and_resolve(
        self,
        model_name: str,
        model_category: str,
        download_if_missing: bool,
        hf_source: str,
        hf_filename: str,
    ):
        category = self.CATEGORY_FOLDERS[model_category]
        normalized = model_name.strip()

        chosen = self._find(category, normalized)
        if chosen:
            full_path = self._resolve_full_path(category, chosen)
            return (full_path, True, f"FOUND: {chosen}", hf_source)

        if not download_if_missing:
            status = (
                f"MISSING: '{normalized}' not found in '{category}'. "
                "Enable download_if_missing to fetch it."
            )
            return ("", False, status, hf_source)

        try:
            downloaded_path = self._download(category, normalized, hf_source, hf_filename)
        except Exception as exc:
            return ("", False, f"DOWNLOAD FAILED: {exc}", hf_source)

        # Refresh the cache so subsequent nodes can see the new file.
        try:
            folder_paths.get_filename_list.cache_clear()
        except Exception:
            pass

        return (downloaded_path, True, f"DOWNLOADED: {os.path.basename(downloaded_path)}", hf_source)


NODE_CLASS_MAPPINGS = {
    "HFModelAutoLoader": HFModelAutoLoader,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "HFModelAutoLoader": "toobusy HF Model Auto Loader",
}
