"""toobusy ZIT ControlNet.

A control module that snaps onto `toobusy Z-Image Turbo`: three control
slots (depth / canny / pose), each with its own image input, on/off switch,
and strength. The slot images are preprocessed in-node (MiDaS / Canny /
DWPose), shown as previews on the node, and bundled into a single
`ZIT_CONTROL` link. Z-Image Turbo applies the bundle as stacked
Fun-ControlNet-Union model patches (QwenImageDiffsynthControlnet) on its
final model — internal loader, override, and LoRA paths alike.

Folds, per active slot: ImageScaleToTotalPixels + preprocessor +
ModelPatchLoader + QwenImageDiffsynthControlnet + PreviewImage (the
operator's per-type bypass subgraphs become three toggles on one node).
"""

import os
import uuid

from ..ltx23_compact_sampler_node.ltx23_compact_sampler import _call_node

CONTROL_TYPES = ("depth", "canny", "pose")

PREFERRED_PATCHES = (
    "Z-Image-Turbo-Fun-Controlnet-Union.safetensors",
    "ZIT/Z-Image-Turbo-Fun-Controlnet-Union.safetensors",
)

_AUX_HINT = (
    "Install the 'comfyui_controlnet_aux' node pack for this preprocessor, "
    "or turn the slot's preprocess toggle off and feed a ready-made control map."
)


def _patch_names():
    try:
        import folder_paths

        names = list(folder_paths.get_filename_list("model_patches"))
        if names:
            return names
    except Exception:
        pass
    return ["Z-Image-Turbo-Fun-Controlnet-Union.safetensors"]


def _default_patch_name(names):
    for preferred in PREFERRED_PATCHES:
        if preferred in names:
            return preferred
    for name in names:
        lowered = name.lower()
        if "z-image" in lowered and "control" in lowered:
            return name
    return names[0]


def _node_exists(class_name):
    try:
        import nodes

        return class_name in nodes.NODE_CLASS_MAPPINGS
    except Exception:
        return False


def _save_previews(items):
    """Write the processed control maps to the temp dir and return PreviewImage
    style ui entries so they render on the node. Fully best-effort: preview
    failures must never break the control output."""
    results = []
    try:
        import numpy as np
        import folder_paths
        from PIL import Image as PILImage

        temp_dir = folder_paths.get_temp_directory()
        os.makedirs(temp_dir, exist_ok=True)
        prefix = f"toobusy_zitcn_{uuid.uuid4().hex[:8]}"
        for index, (control_type, tensor) in enumerate(items):
            try:
                array = tensor
                if hasattr(array, "detach"):
                    array = array.detach().cpu().numpy()
                frame = np.clip(array[0] * 255.0, 0, 255).astype("uint8")
                filename = f"{prefix}_{control_type}_{index}.png"
                PILImage.fromarray(frame).save(os.path.join(temp_dir, filename), compress_level=1)
                results.append({"filename": filename, "subfolder": "", "type": "temp"})
            except Exception:
                continue
    except Exception:
        return []
    return results


class ToobusyZITControlNet:
    """Depth / canny / pose control module for toobusy Z-Image Turbo."""

    @classmethod
    def INPUT_TYPES(cls):
        patch_names = _patch_names()
        return {
            "required": {
                "patch_name": (
                    patch_names,
                    {
                        "default": _default_patch_name(patch_names),
                        "tooltip": "Fun ControlNet Union model patch (models/model_patches). One union file drives all three control types.",
                    },
                ),
                "depth_enable": ("BOOLEAN", {"default": True, "label_on": "depth on", "label_off": "depth off"}),
                "depth_strength": ("FLOAT", {"default": 0.4, "min": -10.0, "max": 10.0, "step": 0.05}),
                "depth_preprocess": ("BOOLEAN", {"default": True, "label_on": "preprocess (MiDaS)", "label_off": "image is a depth map"}),
                "canny_enable": ("BOOLEAN", {"default": True, "label_on": "canny on", "label_off": "canny off"}),
                "canny_strength": ("FLOAT", {"default": 1.0, "min": -10.0, "max": 10.0, "step": 0.05}),
                "canny_preprocess": ("BOOLEAN", {"default": True, "label_on": "preprocess (Canny)", "label_off": "image is an edge map"}),
                "pose_enable": ("BOOLEAN", {"default": True, "label_on": "pose on", "label_off": "pose off"}),
                "pose_strength": ("FLOAT", {"default": 1.0, "min": -10.0, "max": 10.0, "step": 0.05}),
                "pose_preprocess": ("BOOLEAN", {"default": True, "label_on": "preprocess (DWPose)", "label_off": "image is a pose map"}),
                "preprocessor_resolution": ("INT", {"default": 512, "min": 128, "max": 2048, "step": 64}),
                "canny_low": ("INT", {"default": 100, "min": 0, "max": 255}),
                "canny_high": ("INT", {"default": 200, "min": 0, "max": 255}),
            },
            "optional": {
                "depth_image": ("IMAGE",),
                "canny_image": ("IMAGE",),
                "pose_image": ("IMAGE",),
            },
        }

    RETURN_TYPES = ("ZIT_CONTROL",)
    RETURN_NAMES = ("zit_control",)
    FUNCTION = "build"
    CATEGORY = "toobusy/Make"

    def _preprocess(self, control_type, image, resolution, canny_low, canny_high):
        image = _call_node(
            "ImageScaleToTotalPixels",
            image=image,
            upscale_method="lanczos",
            megapixels=1.0,
        )[0]

        if control_type == "depth":
            if not _node_exists("MiDaS-DepthMapPreprocessor"):
                raise RuntimeError(f"Depth preprocessing needs 'MiDaS-DepthMapPreprocessor'. {_AUX_HINT}")
            return _call_node(
                "MiDaS-DepthMapPreprocessor",
                image=image,
                a=6.283185307179586,
                bg_threshold=0.1,
                resolution=int(resolution),
            )[0]

        if control_type == "pose":
            if not _node_exists("DWPreprocessor"):
                raise RuntimeError(f"Pose preprocessing needs 'DWPreprocessor'. {_AUX_HINT}")
            return _call_node(
                "DWPreprocessor",
                image=image,
                detect_hand="enable",
                detect_body="enable",
                detect_face="enable",
                resolution=int(resolution),
            )[0]

        # canny: prefer the aux preprocessor, fall back to the core Canny node
        # (which takes 0..1 float thresholds instead of 0..255).
        if _node_exists("CannyEdgePreprocessor"):
            return _call_node(
                "CannyEdgePreprocessor",
                image=image,
                low_threshold=int(canny_low),
                high_threshold=int(canny_high),
                resolution=int(resolution),
            )[0]
        if _node_exists("Canny"):
            return _call_node(
                "Canny",
                image=image,
                low_threshold=max(0.0, min(1.0, int(canny_low) / 255.0)),
                high_threshold=max(0.0, min(1.0, int(canny_high) / 255.0)),
            )[0]
        raise RuntimeError(f"Canny preprocessing needs 'CannyEdgePreprocessor' or the core 'Canny' node. {_AUX_HINT}")

    def build(
        self,
        patch_name,
        depth_enable,
        depth_strength,
        depth_preprocess,
        canny_enable,
        canny_strength,
        canny_preprocess,
        pose_enable,
        pose_strength,
        pose_preprocess,
        preprocessor_resolution,
        canny_low,
        canny_high,
        depth_image=None,
        canny_image=None,
        pose_image=None,
    ):
        slots = (
            ("depth", depth_image, depth_enable, depth_strength, depth_preprocess),
            ("canny", canny_image, canny_enable, canny_strength, canny_preprocess),
            ("pose", pose_image, pose_enable, pose_strength, pose_preprocess),
        )

        entries = []
        previews = []
        for control_type, image, enabled, strength, preprocess in slots:
            if image is None:
                if enabled:
                    print(f"[toobusy ZIT ControlNet] {control_type} is on but has no image connected — skipped.")
                continue
            if not enabled:
                print(f"[toobusy ZIT ControlNet] {control_type} image connected but switched off — skipped.")
                continue
            processed = (
                self._preprocess(control_type, image, preprocessor_resolution, canny_low, canny_high)
                if preprocess
                else image
            )
            entries.append({"type": control_type, "image": processed, "strength": float(strength)})
            previews.append((control_type, processed))

        if not entries:
            print("[toobusy ZIT ControlNet] No active control slot — Z-Image Turbo will run unpatched.")

        control = {"patch_name": patch_name, "entries": entries}
        return {"ui": {"images": _save_previews(previews)}, "result": (control,)}


NODE_CLASS_MAPPINGS = {
    "ToobusyZITControlNet": ToobusyZITControlNet,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ToobusyZITControlNet": "toobusy ZIT ControlNet",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
