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


def _fit_image(image, width, height, fill=(245, 245, 245)):
    width = max(1, int(width))
    height = max(1, int(height))
    source_w, source_h = image.size
    scale = min(width / source_w, height / source_h)
    new_w = max(1, int(source_w * scale))
    new_h = max(1, int(source_h * scale))
    resized = image.resize((new_w, new_h), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (width, height), fill)
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


def _font(size, family="system", weight=400):
    # Keep frontend text styling and exported board renders aligned. The first
    # choices are Windows-friendly so Korean scene notes keep real glyphs.
    family = str(family or "system").lower()
    is_bold = int(weight or 400) >= 700
    families = {
        "malgun": ("malgunbd.ttf", "malgun.ttf") if is_bold else ("malgun.ttf", "malgunbd.ttf"),
        "gulim": ("gulim.ttc", "gulim.ttf", "malgun.ttf"),
        "newgulim": ("NGULIM.TTF", "gulim.ttc", "malgun.ttf"),
        "batang": ("batang.ttc", "batang.ttf", "malgun.ttf"),
        "gungsuh": (("batang.ttc", 2), "batang.ttc", "malgun.ttf"),
        "serif": ("georgiab.ttf", "timesbd.ttf", "Georgia.ttf", "times.ttf") if is_bold else ("Georgia.ttf", "times.ttf"),
        "mono": ("consolab.ttf", "DejaVuSansMono-Bold.ttf", "consola.ttf", "DejaVuSansMono.ttf") if is_bold else ("consola.ttf", "DejaVuSansMono.ttf"),
        "hand": ("segoeprb.ttf", "comicbd.ttf", "segoepr.ttf", "comic.ttf") if is_bold else ("segoepr.ttf", "comic.ttf"),
        "rounded": ("ARLRDBD.TTF", "trebucbd.ttf", "malgunbd.ttf") if is_bold else ("ARLRDBD.TTF", "trebuc.ttf", "malgun.ttf"),
        "impact": ("impact.ttf", "arialbd.ttf", "malgunbd.ttf"),
        "system": ("malgunbd.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf", "malgun.ttf", "arial.ttf", "DejaVuSans.ttf")
        if is_bold
        else ("malgun.ttf", "arial.ttf", "DejaVuSans.ttf"),
    }
    for candidate in families.get(family, families["system"]):
        try:
            name, index = candidate if isinstance(candidate, tuple) else (candidate, 0)
            return ImageFont.truetype(name, max(8, int(size)), index=index)
        except Exception:
            continue
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


def _pressure_points(points):
    result = []
    for point in points or []:
        if isinstance(point, dict):
            try:
                pressure = max(0.0, min(1.0, float(point.get("p", 0.65))))
            except (TypeError, ValueError):
                pressure = 0.65
            result.append((float(point.get("x", 0)), float(point.get("y", 0)), pressure))
    return result


def _draw_pressure_stroke(draw, points, color, base_width, pressure_enabled=True, opacity=1.0, softness=0.0):
    """Render a round, pressure-sensitive freehand stroke for final IMAGE output."""
    if not points:
        return

    def width_for(pressure):
        if not pressure_enabled:
            return max(1, int(round(base_width)))
        return max(1, int(round(float(base_width) * (0.16 + pressure * 0.84))))

    rgb = tuple(color[:3])
    source_alpha = color[3] if len(color) > 3 else 255
    opacity = max(0.04, min(1.0, float(opacity or 1.0)))
    softness = max(0.0, min(1.0, float(softness or 0.0)))
    layers = [(1.0, 1.0)]
    if softness >= 0.2:
        layers = [(1.0 + softness * 1.8, 0.12), (1.0 + softness * 0.8, 0.22), (1.0, 0.66)]

    for width_scale, alpha_scale in layers:
        layer_color = (*rgb, max(1, int(source_alpha * opacity * alpha_scale)))
        x0, y0, p0 = points[0]
        r0 = width_for(p0) * width_scale / 2
        draw.ellipse((x0 - r0, y0 - r0, x0 + r0, y0 + r0), fill=layer_color)
        for x1, y1, p1 in points[1:]:
            distance = math.hypot(x1 - x0, y1 - y0)
            steps = max(1, min(24, int(math.ceil(distance / 2.0))))
            prev_x, prev_y = x0, y0
            for step in range(1, steps + 1):
                t = step / steps
                x = x0 + (x1 - x0) * t
                y = y0 + (y1 - y0) * t
                pressure = p0 + (p1 - p0) * t
                width = max(1, int(round(width_for(pressure) * width_scale)))
                draw.line((prev_x, prev_y, x, y), fill=layer_color, width=width)
                radius = width / 2
                draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=layer_color)
                prev_x, prev_y = x, y
            x0, y0, p0 = x1, y1, p1


def _rounded_rect(draw, box, radius, **kwargs):
    try:
        draw.rounded_rectangle(box, radius=radius, **kwargs)
    except Exception:
        draw.rectangle(box, **kwargs)


def _cover_image(image, width, height):
    """Scale to fill width x height, center-cropping the overflow."""
    width = max(1, int(width))
    height = max(1, int(height))
    source_w, source_h = image.size
    scale = max(width / source_w, height / source_h)
    new_w = max(1, int(round(source_w * scale)))
    new_h = max(1, int(round(source_h * scale)))
    resized = image.resize((new_w, new_h), Image.Resampling.LANCZOS)
    left = (new_w - width) // 2
    top = (new_h - height) // 2
    return resized.crop((left, top, left + width, top + height))


def _keyframe_items(board):
    """Image items marked as keyframes, in their marked order."""
    items = [
        item
        for item in board.get("items", [])
        if isinstance(item, dict)
        and item.get("type") == "image"
        and int(item.get("keyframe") or 0) > 0
    ]
    return sorted(items, key=lambda item: int(item.get("keyframe") or 0))


def _render_artboard(board, artboard, fallback_width, fallback_height, background):
    width = max(16, int(artboard.get("w", fallback_width))) if artboard else int(fallback_width)
    height = max(16, int(artboard.get("h", fallback_height))) if artboard else int(fallback_height)
    offset_x = float(artboard.get("x", 0)) if artboard else 0.0
    offset_y = float(artboard.get("y", 0)) if artboard else 0.0
    canvas = Image.new("RGB", (width, height), _hex_to_rgba(background)[:3])
    draw = ImageDraw.Draw(canvas, "RGBA")
    for item in board.get("items", []):
        if not isinstance(item, dict) or item.get("type") == "frame" or item.get("hidden"):
            continue
        item_type = item.get("type")
        x = float(item.get("x", 0)) - offset_x
        y = float(item.get("y", 0)) - offset_y
        w = float(item.get("w", 160))
        h = float(item.get("h", 120))
        color = _hex_to_rgba(item.get("color", "#111111"), item.get("alpha", 1))
        fill = _hex_to_rgba(item.get("fill", "#ffffff"), item.get("fillAlpha", 0.6))
        stroke_width = max(1, int(item.get("strokeWidth", 3)))
        if item_type == "image":
            image = _data_url_to_pil(item.get("src"))
            if image is not None:
                canvas.paste(_fit_image(image, w, h), (int(x), int(y)))
        elif item_type == "rect":
            radius = max(0, min(12, w / 4, h / 4))
            _rounded_rect(draw, (x, y, x + w, y + h), radius, fill=fill, outline=color, width=stroke_width)
        elif item_type == "ellipse":
            draw.ellipse((x, y, x + w, y + h), fill=fill, outline=color, width=stroke_width)
        elif item_type == "line":
            x2 = float(item.get("x2", x + offset_x + w)) - offset_x
            y2 = float(item.get("y2", y + offset_y + h)) - offset_y
            draw.line((x, y, x2, y2), fill=color, width=stroke_width)
            if item.get("arrow", False):
                angle = math.atan2(y2 - y, x2 - x)
                length = 18 + stroke_width * 2
                left = (x2 - length * math.cos(angle - 0.45), y2 - length * math.sin(angle - 0.45))
                right = (x2 - length * math.cos(angle + 0.45), y2 - length * math.sin(angle + 0.45))
                draw.polygon([(x2, y2), left, right], fill=color)
        elif item_type == "pen":
            points = [(px - offset_x, py - offset_y, pressure) for px, py, pressure in _pressure_points(item.get("points"))]
            _draw_pressure_stroke(draw, points, color, stroke_width, item.get("pressure", True) is not False, item.get("opacity", 1.0), item.get("softness", 0.0))
        elif item_type == "text":
            font = _font(item.get("fontSize", 24), item.get("fontFamily", "system"), item.get("fontWeight", 400))
            line_y = y
            for line in _wrap_text(draw, item.get("text", ""), font, max(20, int(w))):
                draw.text((x, line_y), line, fill=color, font=font)
                bbox = draw.textbbox((x, line_y), line, font=font)
                line_y += bbox[3] - bbox[1] + 6
                if line_y > y + h:
                    break
    return canvas


class ToobusyStoryboardBoard:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "board_data": ("STRING", {"default": json.dumps(DEFAULT_BOARD), "multiline": True}),
                "width": ("INT", {"default": 1280, "min": 256, "max": 4096, "step": 8}),
                "height": ("INT", {"default": 720, "min": 256, "max": 4096, "step": 8}),
                "background": ("STRING", {"default": "#f8f9fa"}),
                "keyframe_fit": (
                    ["crop", "pad", "stretch"],
                    {
                        "default": "crop",
                        "tooltip": "How keyframe images are fitted to width x height: crop = fill and center-crop, pad = letterbox on the background color, stretch = ignore aspect.",
                    },
                ),
            },
        }

    # keyframes/keyframe_count are appended after the original outputs so
    # existing workflows keep their link slot indices.
    RETURN_TYPES = ("IMAGE", "STRING", "IMAGE", "INT", "IMAGE", "INT")
    RETURN_NAMES = ("image", "board_data", "keyframes", "keyframe_count", "artboards", "artboard_count")
    # Match Prompt Line semantics: downstream nodes are mapped over one
    # single-image tensor at a time instead of receiving one VRAM-heavy batch.
    OUTPUT_IS_LIST = (False, False, False, False, True, False)
    FUNCTION = "render"
    CATEGORY = "toobusy/Plan"

    def render(self, board_data, width, height, background, keyframe_fit="crop"):
        width = int(width)
        height = int(height)
        board = _parse_board(board_data)
        frames = [
            item for item in board.get("items", [])
            if isinstance(item, dict) and item.get("type") == "frame"
        ]
        active_frame = next(
            (item for item in frames if item.get("id") == board.get("activeArtboardId")),
            frames[0] if frames else None,
        )
        offset_x = float(active_frame.get("x", 0)) if active_frame else 0.0
        offset_y = float(active_frame.get("y", 0)) if active_frame else 0.0
        if active_frame:
            width = max(16, int(active_frame.get("w", width)))
            height = max(16, int(active_frame.get("h", height)))
        canvas = Image.new("RGB", (width, height), _hex_to_rgba(background)[:3])
        draw = ImageDraw.Draw(canvas, "RGBA")

        for item in board.get("items", []):
            if not isinstance(item, dict):
                continue
            item_type = item.get("type")
            if item_type == "frame" or item.get("hidden"):
                continue
            x = float(item.get("x", 0)) - offset_x
            y = float(item.get("y", 0)) - offset_y
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
                radius = max(0, min(12, w / 4, h / 4))
                _rounded_rect(draw, (x, y, x + w, y + h), radius, fill=fill, outline=color, width=stroke_width)

            elif item_type == "ellipse":
                draw.ellipse((x, y, x + w, y + h), fill=fill, outline=color, width=stroke_width)

            elif item_type == "line":
                x2 = float(item.get("x2", x + offset_x + w)) - offset_x
                y2 = float(item.get("y2", y + offset_y + h)) - offset_y
                draw.line((x, y, x2, y2), fill=color, width=stroke_width)
                if item.get("arrow", False):
                    angle = math.atan2(y2 - y, x2 - x)
                    length = 18 + stroke_width * 2
                    left = (x2 - length * math.cos(angle - 0.45), y2 - length * math.sin(angle - 0.45))
                    right = (x2 - length * math.cos(angle + 0.45), y2 - length * math.sin(angle + 0.45))
                    draw.polygon([(x2, y2), left, right], fill=color)

            elif item_type == "pen":
                pts = [(px - offset_x, py - offset_y, pressure) for px, py, pressure in _pressure_points(item.get("points"))]
                _draw_pressure_stroke(
                    draw,
                    pts,
                    color,
                    stroke_width,
                    item.get("pressure", True) is not False,
                    item.get("opacity", 1.0),
                    item.get("softness", 0.0),
                )

            elif item_type == "text":
                font = _font(item.get("fontSize", 24), item.get("fontFamily", "system"), item.get("fontWeight", 400))
                line_y = y
                for line in _wrap_text(draw, item.get("text", ""), font, max(20, int(w))):
                    draw.text((x, line_y), line, fill=color, font=font)
                    bbox = draw.textbbox((x, line_y), line, font=font)
                    line_y += bbox[3] - bbox[1] + 6
                    if line_y > y + h:
                        break

        array = np.asarray(canvas).astype(np.float32) / 255.0
        board_image = torch.from_numpy(array)[None,]

        # Keyframe batch: image cards marked with a keyframe order, fitted to
        # the output size, ready for keyframe/video nodes downstream. With no
        # marked keyframes the batch falls back to the board render (count 0).
        keyframe_frames = []
        background_rgb = _hex_to_rgba(background)[:3]
        for item in _keyframe_items(board):
            image = _data_url_to_pil(item.get("src"))
            if image is None:
                continue
            if keyframe_fit == "pad":
                fitted = _fit_image(image, width, height, fill=background_rgb)
            elif keyframe_fit == "stretch":
                fitted = image.resize((width, height), Image.Resampling.LANCZOS)
            else:
                fitted = _cover_image(image, width, height)
            frame = np.asarray(fitted.convert("RGB")).astype(np.float32) / 255.0
            keyframe_frames.append(torch.from_numpy(frame))

        if keyframe_frames:
            keyframes = torch.stack(keyframe_frames, dim=0)
            keyframe_count = len(keyframe_frames)
        else:
            keyframes = board_image
            keyframe_count = 0

        ordered_frames = sorted(
            frames,
            key=lambda item: (
                int(item.get("order", 10_000)),
                float(item.get("y", 0)),
                float(item.get("x", 0)),
            ),
        )
        artboard_tensors = []
        for artboard in ordered_frames:
            rendered = _render_artboard(board, artboard, width, height, background)
            if rendered.size != (width, height):
                rendered = _fit_image(rendered, width, height, fill=background_rgb)
            artboard_tensors.append(torch.from_numpy(np.asarray(rendered).astype(np.float32) / 255.0)[None,])
        if artboard_tensors:
            artboards = artboard_tensors
            artboard_count = len(artboard_tensors)
        else:
            artboards = [board_image]
            artboard_count = 1

        return (board_image, json.dumps(board, ensure_ascii=False), keyframes, keyframe_count, artboards, artboard_count)


NODE_CLASS_MAPPINGS = {
    "ToobusyStoryboardBoard": ToobusyStoryboardBoard,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ToobusyStoryboardBoard": "toobusy Whiteboard",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
