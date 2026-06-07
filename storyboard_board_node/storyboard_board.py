import base64
import json
import math
from io import BytesIO

import numpy as np
import torch
from PIL import Image, ImageDraw, ImageFont


DEFAULT_BOARD = {
    "version": 1,
    "items": [
        {
            "type": "text",
            "x": 64,
            "y": 48,
            "w": 420,
            "h": 80,
            "text": "Storyboard / mood board",
            "fontSize": 36,
            "color": "#111111",
        }
    ],
}


def _parse_board(board_data):
    try:
        data = json.loads(board_data or "")
        if isinstance(data, dict):
            items = data.get("items")
            if isinstance(items, list):
                return data
    except Exception:
        pass
    return DEFAULT_BOARD


def _hex_to_rgba(value, alpha=1.0):
    text = str(value or "#000000").strip()
    if text.startswith("rgba(") and text.endswith(")"):
        try:
            parts = [part.strip() for part in text[5:-1].split(",")]
            r = int(float(parts[0]))
            g = int(float(parts[1]))
            b = int(float(parts[2]))
            a = float(parts[3]) if len(parts) > 3 else 1.0
            return (r, g, b, max(0, min(255, int(a * 255))))
        except Exception:
            text = "#000000"
    elif text.startswith("rgb(") and text.endswith(")"):
        try:
            parts = [part.strip() for part in text[4:-1].split(",")]
            return (int(float(parts[0])), int(float(parts[1])), int(float(parts[2])), max(0, min(255, int(float(alpha) * 255))))
        except Exception:
            text = "#000000"
    if text.startswith("#"):
        text = text[1:]
    if len(text) == 3:
        text = "".join(ch * 2 for ch in text)
    if len(text) != 6:
        text = "000000"
    try:
        rgb = tuple(int(text[index : index + 2], 16) for index in (0, 2, 4))
    except Exception:
        rgb = (0, 0, 0)
    return (*rgb, max(0, min(255, int(float(alpha) * 255))))


def _tensor_to_pil(image_tensor):
    array = image_tensor
    if isinstance(array, torch.Tensor):
        array = array.detach().cpu().numpy()
    if array.ndim == 4:
        array = array[0]
    array = np.clip(array * 255.0, 0, 255).astype(np.uint8)
    return Image.fromarray(array, "RGB")


def _fit_image(image, width, height):
    width = max(1, int(width))
    height = max(1, int(height))
    source_w, source_h = image.size
    scale = min(width / source_w, height / source_h)
    new_w = max(1, int(source_w * scale))
    new_h = max(1, int(source_h * scale))
    resized = image.resize((new_w, new_h), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (width, height), (245, 245, 245))
    canvas.paste(resized, ((width - new_w) // 2, (height - new_h) // 2))
    return canvas


def _data_url_to_pil(data_url):
    if not isinstance(data_url, str) or not data_url.startswith("data:image/"):
        return None
    try:
        _, payload = data_url.split(",", 1)
        return Image.open(BytesIO(base64.b64decode(payload))).convert("RGB")
    except Exception:
        return None


def _font(size):
    try:
        return ImageFont.truetype("arial.ttf", max(8, int(size)))
    except Exception:
        return ImageFont.load_default()


def _wrap_text(draw, text, font, width):
    words = str(text or "").replace("\r", "").split()
    if not words:
        return [""]
    lines = []
    current = words[0]
    for word in words[1:]:
        test = f"{current} {word}"
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] <= width:
            current = test
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _points(points):
    result = []
    for point in points or []:
        if isinstance(point, dict):
            result.append((float(point.get("x", 0)), float(point.get("y", 0))))
    return result


class ToobusyStoryboardBoard:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "board_data": ("STRING", {"default": json.dumps(DEFAULT_BOARD), "multiline": True}),
                "width": ("INT", {"default": 1280, "min": 256, "max": 4096, "step": 8}),
                "height": ("INT", {"default": 720, "min": 256, "max": 4096, "step": 8}),
                "background": ("STRING", {"default": "#f4f1e8"}),
            },
        }

    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("image", "board_data")
    FUNCTION = "render"
    CATEGORY = "toobusy/Plan"

    def render(self, board_data, width, height, background):
        width = int(width)
        height = int(height)
        board = _parse_board(board_data)
        canvas = Image.new("RGB", (width, height), _hex_to_rgba(background)[:3])
        draw = ImageDraw.Draw(canvas, "RGBA")

        for item in board.get("items", []):
            if not isinstance(item, dict):
                continue
            item_type = item.get("type")
            x = float(item.get("x", 0))
            y = float(item.get("y", 0))
            w = float(item.get("w", 160))
            h = float(item.get("h", 120))
            color = _hex_to_rgba(item.get("color", "#111111"), item.get("alpha", 1))
            fill = _hex_to_rgba(item.get("fill", "#ffffff"), item.get("fillAlpha", 0.6))
            stroke_width = max(1, int(item.get("strokeWidth", 3)))

            if item_type == "image":
                image = _data_url_to_pil(item.get("src"))
                if image is not None:
                    image = _fit_image(image, w, h)
                    canvas.paste(image, (int(x), int(y)))
                else:
                    draw.rectangle((x, y, x + w, y + h), fill=(235, 235, 235, 255), outline=color, width=stroke_width)
                    draw.text((x + 12, y + 12), "drop image", fill=color, font=_font(18))

            elif item_type == "rect":
                draw.rectangle((x, y, x + w, y + h), fill=fill, outline=color, width=stroke_width)

            elif item_type == "ellipse":
                draw.ellipse((x, y, x + w, y + h), fill=fill, outline=color, width=stroke_width)

            elif item_type == "line":
                x2 = float(item.get("x2", x + w))
                y2 = float(item.get("y2", y + h))
                draw.line((x, y, x2, y2), fill=color, width=stroke_width)
                if item.get("arrow", False):
                    angle = math.atan2(y2 - y, x2 - x)
                    length = 18 + stroke_width * 2
                    left = (x2 - length * math.cos(angle - 0.45), y2 - length * math.sin(angle - 0.45))
                    right = (x2 - length * math.cos(angle + 0.45), y2 - length * math.sin(angle + 0.45))
                    draw.polygon([(x2, y2), left, right], fill=color)

            elif item_type == "pen":
                pts = _points(item.get("points"))
                if len(pts) > 1:
                    draw.line(pts, fill=color, width=stroke_width, joint="curve")

            elif item_type == "text":
                font = _font(item.get("fontSize", 24))
                line_y = y
                for line in _wrap_text(draw, item.get("text", ""), font, max(20, int(w))):
                    draw.text((x, line_y), line, fill=color, font=font)
                    bbox = draw.textbbox((x, line_y), line, font=font)
                    line_y += bbox[3] - bbox[1] + 6
                    if line_y > y + h:
                        break

        array = np.asarray(canvas).astype(np.float32) / 255.0
        return (torch.from_numpy(array)[None,], json.dumps(board, ensure_ascii=False))


NODE_CLASS_MAPPINGS = {
    "ToobusyStoryboardBoard": ToobusyStoryboardBoard,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ToobusyStoryboardBoard": "toobusy Storyboard Board",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
