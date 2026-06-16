"""toobusy Layout Text Overlay.

Draws real text onto a generated image at chosen positions/sizes — so Korean (or
any) headlines stay crisp even when the image model (e.g. Ideogram4) can't render
them. The JS editor lets you drag/resize/restyle each text block live over the
image; this backend renders the same with Pillow so the output matches.

`overlay_data` is the editor's state (a list of text items in 0..1 normalized
coords). If it's empty, the node seeds items from a connected `layout_json`
(the Ideogram layout JSON's `type:"text"` elements) so it works without any
manual editing — connect image + layout_json and you already get the headlines
placed.
"""

import json


DEFAULT_OVERLAY = {"items": []}


def _parse_overlay(data):
    if isinstance(data, dict):
        return data
    if isinstance(data, str) and data.strip():
        try:
            parsed = json.loads(data)
            if isinstance(parsed, dict):
                return parsed
        except (ValueError, TypeError):
            pass
    return {"items": []}


def _hex_rgb(value, default=(255, 255, 255)):
    try:
        text = str(value).lstrip("#")
        if len(text) == 6:
            return (int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16))
    except (ValueError, TypeError):
        pass
    return default


def _font(size):
    """malgun first so Korean renders with real glyphs on Windows."""
    from PIL import ImageFont

    for name in ("malgun.ttf", "arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, max(8, int(size)))
        except Exception:
            continue
    return ImageFont.load_default()


def seed_items_from_layout(layout_json):
    """Ideogram layout JSON -> overlay text items (normalized 0..1). Each
    `type:"text"` element's bbox [y_min,x_min,y_max,x_max] in 0..1000 becomes a
    placed item; fontSize 0 means auto-fit to the box."""
    items = []
    try:
        data = json.loads(layout_json) if isinstance(layout_json, str) and layout_json.strip() else None
    except (ValueError, TypeError):
        data = None
    if not isinstance(data, dict):
        return items
    comp = data.get("compositional_deconstruction")
    elements = comp.get("elements") if isinstance(comp, dict) else None
    if not isinstance(elements, list):
        return items
    for element in elements:
        if not isinstance(element, dict) or element.get("type") != "text":
            continue
        text = str(element.get("text", "")).strip()
        if not text:
            continue
        bbox = element.get("bbox")
        if not (isinstance(bbox, list) and len(bbox) == 4):
            continue
        y0, x0, y1, x1 = bbox
        height_frac = max(0.02, min(1.0, (y1 - y0) / 1000.0))
        items.append({
            "text": text,
            "x": max(0.0, min(1.0, x0 / 1000.0)),
            "y": max(0.0, min(1.0, y0 / 1000.0)),
            "w": max(0.02, min(1.0, (x1 - x0) / 1000.0)),
            "h": height_frac,
            # fontSize is a fraction of image height; start ~one line filling the
            # box so the seed looks right, then the editor tweaks it.
            "fontSize": round(height_frac * 0.8, 4),
            "color": "#FFFFFF",
            "stroke": "#000000",
            "strokeWidth": 3,
            "align": "center",
        })
    return items


def _wrap(draw, text, font, max_width):
    """Wrap on spaces, then hard-break any single token wider than max_width
    (Korean has few spaces, so headlines need character wrapping too)."""
    out_lines = []
    for raw_line in str(text).replace("\r", "").split("\n"):
        words = raw_line.split(" ")
        line = ""
        for word in words:
            candidate = word if not line else f"{line} {word}"
            if draw.textlength(candidate, font=font) <= max_width or not line:
                line = candidate
            else:
                out_lines.append(line)
                line = word
        # hard-break overflowing lines character by character
        while line and draw.textlength(line, font=font) > max_width and len(line) > 1:
            cut = len(line)
            while cut > 1 and draw.textlength(line[:cut], font=font) > max_width:
                cut -= 1
            out_lines.append(line[:cut])
            line = line[cut:]
        out_lines.append(line)
    return out_lines or [""]


def _fit_font_size(draw, text, box_w, box_h, max_size):
    """Largest font size (<= max_size) whose wrapped text fits the box."""
    size = max(8, int(max_size))
    while size > 8:
        font = _font(size)
        lines = _wrap(draw, text, font, box_w)
        line_h = (draw.textbbox((0, 0), "Ag", font=font)[3]) * 1.15
        if len(lines) * line_h <= box_h and all(draw.textlength(l, font=font) <= box_w for l in lines):
            return size
        size -= 2
    return max(8, size)


def _draw_item(draw, item, width, height, font_scale):
    text = str(item.get("text", ""))
    if not text.strip():
        return
    box_x = float(item.get("x", 0.0)) * width
    box_y = float(item.get("y", 0.0)) * height
    box_w = max(1.0, float(item.get("w", 0.5)) * width)
    box_h = max(1.0, float(item.get("h", 0.1)) * height)

    # fontSize is a fraction of image height; 0 = auto-fit to the box.
    size_frac = float(item.get("fontSize") or 0)
    if size_frac <= 0:
        size = _fit_font_size(draw, text, box_w, box_h, max_size=box_h)
    else:
        size = int(size_frac * height)
    size = max(8, int(size * float(font_scale)))
    font = _font(size)

    color = _hex_rgb(item.get("color"), (255, 255, 255))
    stroke = _hex_rgb(item.get("stroke"), (0, 0, 0))
    stroke_width = max(0, int(item.get("strokeWidth", 3)))
    align = str(item.get("align", "center"))

    lines = _wrap(draw, text, font, box_w)
    line_h = (draw.textbbox((0, 0), "Ag", font=font)[3]) * 1.15
    cursor_y = box_y
    for line in lines:
        line_w = draw.textlength(line, font=font)
        if align == "center":
            line_x = box_x + (box_w - line_w) / 2.0
        elif align == "right":
            line_x = box_x + (box_w - line_w)
        else:
            line_x = box_x
        draw.text(
            (line_x, cursor_y),
            line,
            font=font,
            fill=color,
            stroke_width=stroke_width,
            stroke_fill=stroke,
        )
        cursor_y += line_h


def _image_to_data_url(image, max_edge=1280):
    """First IMAGE frame -> downscaled JPEG data URL for the editor backdrop."""
    try:
        import base64
        import io

        import numpy as np
        from PIL import Image as PILImage

        frame = image[0].detach().cpu().numpy()
        array = (frame[..., :3].clip(0.0, 1.0) * 255.0).astype("uint8")
        pil = PILImage.fromarray(array)
        w, h = pil.size
        scale = min(1.0, float(max_edge) / float(max(w, h)))
        if scale < 1.0:
            pil = pil.resize((max(1, int(w * scale)), max(1, int(h * scale))))
        buffer = io.BytesIO()
        pil.save(buffer, format="JPEG", quality=88)
        return "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")
    except Exception:
        return ""


def _resolved_items(overlay_data, layout_json):
    items = _parse_overlay(overlay_data).get("items")
    if not items:
        items = seed_items_from_layout(layout_json)
    return [item for item in items if isinstance(item, dict)]


def render_overlay(image, overlay_data, layout_json, font_scale):
    """Pure-ish core split out for testing: PIL IMAGE-tensor in, tensor out."""
    import numpy as np
    import torch
    from PIL import Image, ImageDraw

    frame = image[0].detach().cpu().numpy()
    array = (frame[..., :3].clip(0.0, 1.0) * 255.0).astype("uint8")
    pil = Image.fromarray(array).convert("RGB")
    width, height = pil.size
    draw = ImageDraw.Draw(pil)

    items = _parse_overlay(overlay_data).get("items")
    if not items:
        items = seed_items_from_layout(layout_json)
    for item in items:
        if isinstance(item, dict):
            _draw_item(draw, item, width, height, font_scale)

    out = np.asarray(pil).astype("float32") / 255.0
    return torch.from_numpy(out)[None, ...]


class ToobusyLayoutTextOverlay:
    """Render text from the layout JSON (or the editor) onto a generated image."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "overlay_data": ("STRING", {"default": json.dumps(DEFAULT_OVERLAY), "multiline": True}),
                "font_scale": (
                    "FLOAT",
                    {"default": 1.0, "min": 0.1, "max": 4.0, "step": 0.05, "tooltip": "Global multiplier on every text block's size."},
                ),
            },
            "optional": {
                "layout_json": (
                    "STRING",
                    {
                        "forceInput": True,
                        "tooltip": "Optional Ideogram layout JSON (e.g. from Prompt Polish). Its text elements seed the overlay when the editor is empty.",
                    },
                ),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "render"
    CATEGORY = "toobusy/Make"

    OUTPUT_NODE = True

    def render(self, image, overlay_data, font_scale=1.0, layout_json=""):
        rendered = render_overlay(image, overlay_data, layout_json, font_scale)
        # Hand the source image + resolved items to the JS editor so it can place
        # editable text over the real image (seeded from layout_json on first run).
        ui = {"toobusy_overlay_items": [json.dumps(_resolved_items(overlay_data, layout_json))]}
        backdrop = _image_to_data_url(image)
        if backdrop:
            ui["toobusy_overlay_bg"] = [backdrop]
        return {"ui": ui, "result": (rendered,)}


NODE_CLASS_MAPPINGS = {
    "ToobusyLayoutTextOverlay": ToobusyLayoutTextOverlay,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ToobusyLayoutTextOverlay": "toobusy Layout Text Overlay",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
