"""toobusy Paint Canvas.

An openCanvas-style painting node at the very front of the graph: brush
(pen pressure), eraser, color picker, layers, zoom/pan, undo — drawn right
inside the node. Every queued run takes the current painting as input, so a
rough sketch can flow straight into ZIT ControlNet / img2img and come back
finished.

The frontend serializes the document into `canvas_data` (JSON with one PNG
data URL per layer); this node composites the visible layers over the
background color and also outputs the painted-area alpha as a MASK.
"""

import base64
import json
from io import BytesIO

import numpy as np
import torch
from PIL import Image


MAX_CANVAS_EDGE = 2048

DEFAULT_CANVAS = {
    "version": 1,
    "layers": [],
}


def _parse_canvas(canvas_data):
    try:
        data = json.loads(canvas_data or "")
        if isinstance(data, dict) and isinstance(data.get("layers"), list):
            return data
    except Exception:
        pass
    return DEFAULT_CANVAS


def _hex_to_rgb(value):
    text = str(value or "#ffffff").strip().lstrip("#")
    if len(text) == 3:
        text = "".join(ch * 2 for ch in text)
    if len(text) != 6:
        text = "ffffff"
    try:
        return tuple(int(text[index : index + 2], 16) for index in (0, 2, 4))
    except Exception:
        return (255, 255, 255)


def _data_url_to_rgba(data_url):
    if not isinstance(data_url, str) or not data_url.startswith("data:image/"):
        return None
    try:
        _, payload = data_url.split(",", 1)
        return Image.open(BytesIO(base64.b64decode(payload))).convert("RGBA")
    except Exception:
        return None


class ToobusyPaintCanvas:
    """Folds an external painting app + export + Load Image round-trip into
    one in-graph painting surface with layers."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "canvas_data": ("STRING", {"default": json.dumps(DEFAULT_CANVAS), "multiline": True}),
                "width": ("INT", {"default": 1024, "min": 64, "max": MAX_CANVAS_EDGE, "step": 8}),
                "height": ("INT", {"default": 1024, "min": 64, "max": MAX_CANVAS_EDGE, "step": 8}),
                "background": ("STRING", {"default": "#ffffff"}),
            },
        }

    RETURN_TYPES = ("IMAGE", "MASK", "STRING")
    RETURN_NAMES = ("image", "painted_mask", "canvas_data")
    FUNCTION = "render"
    CATEGORY = "toobusy/Plan"

    def render(self, canvas_data, width, height, background):
        width = max(1, min(MAX_CANVAS_EDGE, int(width)))
        height = max(1, min(MAX_CANVAS_EDGE, int(height)))
        document = _parse_canvas(canvas_data)

        base = Image.new("RGBA", (width, height), (*_hex_to_rgb(background), 255))
        painted_alpha = np.zeros((height, width), dtype=np.float32)

        for layer in document.get("layers", []):
            if not isinstance(layer, dict) or not layer.get("visible", True):
                continue
            pixels = _data_url_to_rgba(layer.get("src"))
            if pixels is None:
                continue
            if pixels.size != (width, height):
                pixels = pixels.resize((width, height), Image.Resampling.LANCZOS)
            opacity = float(layer.get("opacity", 1.0))
            opacity = max(0.0, min(1.0, opacity))
            if opacity <= 0.0:
                continue
            if opacity < 1.0:
                alpha = pixels.getchannel("A").point(lambda value: int(value * opacity))
                pixels.putalpha(alpha)
            base = Image.alpha_composite(base, pixels)
            layer_alpha = np.asarray(pixels.getchannel("A"), dtype=np.float32) / 255.0
            painted_alpha = np.maximum(painted_alpha, layer_alpha)

        rgb = np.asarray(base.convert("RGB"), dtype=np.float32) / 255.0
        image = torch.from_numpy(rgb)[None,]
        mask = torch.from_numpy(painted_alpha)[None,]
        return (image, mask, json.dumps(document, ensure_ascii=False))


NODE_CLASS_MAPPINGS = {
    "ToobusyPaintCanvas": ToobusyPaintCanvas,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ToobusyPaintCanvas": "toobusy Paint Canvas",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
