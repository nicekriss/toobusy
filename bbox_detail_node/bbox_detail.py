"""Per-object crop list and feathered paste-back for detection-driven detail passes.

Pairs with core detection nodes (SAM3 Detect, RT-DETR Detect, Create Bounding Boxes):

    detect -> ToobusyBBoxCropList -> [any per-image sampler chain] -> ToobusyBBoxPasteBack

`ToobusyBBoxCropList` turns one frame's bounding boxes into a *list* of crops, each
resized to a target megapixel budget while keeping its own aspect ratio, so a model
such as Qwen-Image 2.1 can re-render every region at its native 2K budget.
`ToobusyBBoxPasteBack` shrinks each processed crop back to its box and blends it into
the original image with a feathered edge, so no coordinates are ever typed by hand.
"""

import json
import math

import torch

import comfy.utils


def _flatten_boxes(bboxes):
    """Accept per-frame lists (SAM3/RT-DETR), a flat list, one dict, or a JSON string.

    Returns the first frame's boxes as a list of dicts with x, y, width, height.
    """
    if bboxes is None:
        return []
    if isinstance(bboxes, str):
        text = bboxes.strip()
        bboxes = json.loads(text) if text else []
    if isinstance(bboxes, dict):
        bboxes = [bboxes]
    if not isinstance(bboxes, list) or len(bboxes) == 0:
        return []
    if isinstance(bboxes[0], list):
        bboxes = bboxes[0]
    out = []
    for box in bboxes:
        if not isinstance(box, dict):
            continue
        try:
            out.append({
                "x": float(box["x"]),
                "y": float(box["y"]),
                "width": float(box["width"]),
                "height": float(box["height"]),
            })
        except (KeyError, TypeError, ValueError):
            continue
    return out


def _round_mult(value, multiple):
    return max(int(multiple), int(round(float(value) / multiple)) * int(multiple))


def _resize(image_bhwc, width, height, method):
    chw = image_bhwc.movedim(-1, 1)
    out = comfy.utils.common_upscale(chw, int(width), int(height), method, "disabled")
    return out.movedim(1, -1)


class ToobusyBBoxCropList:
    """Crop every detected box into its own image (a list), padded and resized to a pixel budget."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "bboxes": ("BOUNDING_BOX", {"forceInput": True}),
                "padding_percent": ("FLOAT", {
                    "default": 6.0, "min": 0.0, "max": 100.0, "step": 0.5,
                    "tooltip": "Extra margin on every side, as a percent of the box's longer edge.",
                }),
                "target_megapixels": ("FLOAT", {
                    "default": 4.0, "min": 0.0, "max": 16.0, "step": 0.1,
                    "tooltip": "Each crop is resized (aspect kept) to about this many megapixels. 0 keeps the native crop size.",
                }),
                "multiple_of": ("INT", {
                    "default": 32, "min": 8, "max": 128, "step": 8,
                    "tooltip": "Crop width and height are rounded to this multiple.",
                }),
                "order": (["left_to_right", "top_to_bottom", "largest_first", "detection"], {
                    "default": "left_to_right",
                }),
                "max_items": ("INT", {
                    "default": 0, "min": 0, "max": 64,
                    "tooltip": "Keep at most this many boxes after ordering. 0 = all.",
                }),
                "resize_method": (["lanczos", "bicubic", "area", "bilinear"], {"default": "lanczos"}),
            }
        }

    RETURN_TYPES = ("IMAGE", "BOUNDING_BOX", "INT")
    RETURN_NAMES = ("crops", "used_bboxes", "count")
    OUTPUT_IS_LIST = (True, False, False)
    FUNCTION = "crop"
    CATEGORY = "toobusy/Detail"

    def crop(self, image, bboxes, padding_percent, target_megapixels, multiple_of, order, max_items, resize_method):
        frame = image[0:1]
        img_h, img_w = int(frame.shape[1]), int(frame.shape[2])
        boxes = _flatten_boxes(bboxes)

        if order == "left_to_right":
            boxes.sort(key=lambda b: (b["x"], b["y"]))
        elif order == "top_to_bottom":
            boxes.sort(key=lambda b: (b["y"], b["x"]))
        elif order == "largest_first":
            boxes.sort(key=lambda b: -(b["width"] * b["height"]))
        if max_items > 0:
            boxes = boxes[:max_items]

        used = []
        crops = []
        for box in boxes:
            pad = max(box["width"], box["height"]) * (padding_percent / 100.0)
            x1 = int(math.floor(max(0.0, box["x"] - pad)))
            y1 = int(math.floor(max(0.0, box["y"] - pad)))
            x2 = int(math.ceil(min(float(img_w), box["x"] + box["width"] + pad)))
            y2 = int(math.ceil(min(float(img_h), box["y"] + box["height"] + pad)))
            if x2 - x1 < 8 or y2 - y1 < 8:
                continue
            crop = frame[:, y1:y2, x1:x2, :]
            cw, ch = x2 - x1, y2 - y1
            if target_megapixels > 0:
                scale = math.sqrt(target_megapixels * 1e6 / float(cw * ch))
            else:
                scale = 1.0
            nw = _round_mult(cw * scale, multiple_of)
            nh = _round_mult(ch * scale, multiple_of)
            crops.append(_resize(crop, nw, nh, resize_method))
            used.append({"x": x1, "y": y1, "width": cw, "height": ch})

        if not crops:
            # Nothing detected: pass the whole frame through as a single item so the graph still runs.
            nw = _round_mult(img_w, multiple_of)
            nh = _round_mult(img_h, multiple_of)
            crops = [_resize(frame, nw, nh, resize_method)]
            used = [{"x": 0, "y": 0, "width": img_w, "height": img_h}]

        return (crops, [used], len(crops))


def _feather_mask(height, width, feather, edges, device, dtype):
    """Linear ramp 0->1 over `feather` pixels on the sides listed in `edges`."""
    mask = torch.ones((height, width), device=device, dtype=dtype)
    if feather <= 0:
        return mask
    ramp_h = torch.linspace(0.0, 1.0, steps=min(feather, height) + 1, device=device, dtype=dtype)[1:]
    ramp_w = torch.linspace(0.0, 1.0, steps=min(feather, width) + 1, device=device, dtype=dtype)[1:]
    if "top" in edges:
        mask[: ramp_h.shape[0], :] = torch.minimum(mask[: ramp_h.shape[0], :], ramp_h[:, None])
    if "bottom" in edges:
        mask[-ramp_h.shape[0]:, :] = torch.minimum(mask[-ramp_h.shape[0]:, :], ramp_h.flip(0)[:, None])
    if "left" in edges:
        mask[:, : ramp_w.shape[0]] = torch.minimum(mask[:, : ramp_w.shape[0]], ramp_w[None, :])
    if "right" in edges:
        mask[:, -ramp_w.shape[0]:] = torch.minimum(mask[:, -ramp_w.shape[0]:], ramp_w.flip(0)[None, :])
    return mask


class ToobusyBBoxPasteBack:
    """Shrink processed crops back to their boxes and blend them into the source image."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "crops": ("IMAGE",),
                "bboxes": ("BOUNDING_BOX", {"forceInput": True}),
                "feather_px": ("INT", {
                    "default": 24, "min": 0, "max": 512,
                    "tooltip": "Soft edge width in source pixels. Edges touching the image border stay hard.",
                }),
                "resize_method": (["lanczos", "bicubic", "area", "bilinear"], {"default": "lanczos"}),
                "tone": (["original_lowpass", "match_stats", "off"], {
                    "default": "original_lowpass",
                    "tooltip": "original_lowpass: keep the original's low-frequency tone and add only the crop's detail (seamless, recommended for full re-renders). match_stats: match per-channel mean/spread to the box. off: paste as is.",
                }),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    INPUT_IS_LIST = True
    FUNCTION = "paste"
    CATEGORY = "toobusy/Detail"

    @staticmethod
    def _match(crop, region):
        """Linear per-channel transfer: crop stats -> region stats (over the whole box)."""
        c_mean = crop.mean(dim=(0, 1, 2), keepdim=True)
        c_std = crop.std(dim=(0, 1, 2), keepdim=True).clamp_min(1e-4)
        r_mean = region.mean(dim=(0, 1, 2), keepdim=True)
        r_std = region.std(dim=(0, 1, 2), keepdim=True)
        return ((crop - c_mean) * (r_std / c_std) + r_mean).clamp(0.0, 1.0)

    @staticmethod
    def _lowpass(x_bhwc, cells=24):
        """Blurry copy: downsample so the short side is about `cells` pixels, then upsample."""
        h, w = int(x_bhwc.shape[1]), int(x_bhwc.shape[2])
        f = max(1, min(h, w) // cells)
        if f <= 1:
            return x_bhwc
        chw = x_bhwc.movedim(-1, 1)
        small = torch.nn.functional.interpolate(chw, size=(max(1, h // f), max(1, w // f)), mode="area")
        return torch.nn.functional.interpolate(small, size=(h, w), mode="bilinear", align_corners=False).movedim(1, -1)

    def paste(self, image, crops, bboxes, feather_px, resize_method, tone=None):
        base = image[0][0:1].clone()
        feather = int(feather_px[0])
        method = resize_method[0]
        mode = tone[0] if tone else "off"
        if isinstance(mode, bool):  # older graphs saved color_match as a boolean
            mode = "match_stats" if mode else "off"
        boxes = _flatten_boxes(bboxes[0])

        # Flatten any batched items into one crop per box.
        flat = []
        for item in crops:
            for i in range(item.shape[0]):
                flat.append(item[i:i + 1])

        img_h, img_w = int(base.shape[1]), int(base.shape[2])
        channels = int(base.shape[3])

        for crop, box in zip(flat, boxes):
            x1, y1 = int(round(box["x"])), int(round(box["y"]))
            w, h = int(round(box["width"])), int(round(box["height"]))
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(img_w, x1 + w), min(img_h, y1 + h)
            w, h = x2 - x1, y2 - y1
            if w <= 0 or h <= 0:
                continue
            crop = crop.to(base.device, base.dtype)
            if crop.shape[3] >= channels:
                crop = crop[..., :channels]
            else:
                pad = torch.ones((1, crop.shape[1], crop.shape[2], channels - crop.shape[3]), device=base.device, dtype=base.dtype)
                crop = torch.cat([crop, pad], dim=-1)
            resized = _resize(crop, w, h, method)
            region = base[:, y1:y2, x1:x2, :]
            if mode == "match_stats":
                resized = self._match(resized, region)
            elif mode == "original_lowpass":
                resized = (resized - self._lowpass(resized) + self._lowpass(region)).clamp(0.0, 1.0)
            edges = set()
            if x1 > 0:
                edges.add("left")
            if y1 > 0:
                edges.add("top")
            if x2 < img_w:
                edges.add("right")
            if y2 < img_h:
                edges.add("bottom")
            mask = _feather_mask(h, w, feather, edges, base.device, base.dtype)[None, :, :, None]
            region = base[:, y1:y2, x1:x2, :]
            base[:, y1:y2, x1:x2, :] = region * (1.0 - mask) + resized * mask

        return (base,)


NODE_CLASS_MAPPINGS = {
    "ToobusyBBoxCropList": ToobusyBBoxCropList,
    "ToobusyBBoxPasteBack": ToobusyBBoxPasteBack,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ToobusyBBoxCropList": "2BZ Crop Each BBox (list)",
    "ToobusyBBoxPasteBack": "2BZ Paste Crops Back",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
