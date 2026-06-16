"""toobusy Image -> Ideogram Layout.

Analyzes a single image with Florence-2 and emits an Ideogram4 structured-JSON
*draft* (high_level_description + style_description + compositional_deconstruction
with bbox'd text/obj elements). The draft is meant to be loaded into the existing
`toobusy Ideogram Layout Builder` and hand-edited — not a finished caption.

Wiring: connect this node's `ideogram_json` output into the Layout Builder's
`elements_json` input (the builder already ingests a full Ideogram payload and
draws the boxes on its canvas), and the `high_level_description` / `background` /
`color_palette` outputs into the builder's matching inputs. The manual builder is
untouched — this only adds an "image -> draft" front door.

Florence-2 inference is delegated to an installed Florence-2 node
(kijai/ComfyUI-Florence2 `Florence2Run`, fed an `FL2MODEL` from
`DownloadAndLoadFlorence2Model`). Nothing is bundled or downloaded here, so this
adds no heavy dependency to toobusy. If that node is missing the node loads fine
and fails at run time with a clear "install ComfyUI-Florence2" message.

v1 implements the `Full Setup` analysis mode. `Composition Only` / `Style Only`
are scaffolded as TODO and currently fall back to Full Setup.
"""

import json

from ..ltx23_compact_sampler_node.ltx23_compact_sampler import _call_node
from ..ideogram_layout_builder.nodes import (
    ELEMENT_PALETTE_MAX,
    MIN_BOX_SIZE,
    STYLE_PALETTE_MAX,
    _clamp_int,
    _to_ideogram_bbox,
)

_FLORENCE_NODE = "Florence2Run"
_FLORENCE_HINT = (
    "Install kijai/ComfyUI-Florence2 (provides 'Florence2Run' + "
    "'DownloadAndLoadFlorence2Model') and feed an FL2MODEL into florence2_model."
)


def _first_image_size(image):
    """(width, height) of the first frame of an IMAGE tensor [B,H,W,C]."""
    try:
        shape = image.shape
        return int(shape[2]), int(shape[1])
    except Exception:
        return 1000, 1000


def _norm_coord(value, extent):
    """A single bbox coordinate -> 0..1000. Florence region tasks return either
    pixel coords (dense_region_caption / od) or already-normalized 0..1 coords
    (ocr_with_region); detect which and scale accordingly."""
    try:
        value = float(value)
    except (TypeError, ValueError):
        return 0
    if 0.0 <= value <= 1.0:
        scaled = value * 1000.0
    else:
        scaled = value / float(extent) * 1000.0 if extent else value
    return _clamp_int(scaled)


def _norm_box(box, width, height):
    """A 4-number box [x1,y1,x2,y2] -> canvas-order [x_min,y_min,x_max,y_max] in
    0..1000, sorted and clamped but NOT grown (so small-text filtering can see
    the real size before MIN_BOX_SIZE growth kicks in)."""
    if not isinstance(box, (list, tuple)) or len(box) < 4:
        return None
    x1 = _norm_coord(box[0], width)
    y1 = _norm_coord(box[1], height)
    x2 = _norm_coord(box[2], width)
    y2 = _norm_coord(box[3], height)
    x_min, x_max = sorted((x1, x2))
    y_min, y_max = sorted((y1, y2))
    return [x_min, y_min, x_max, y_max]


def _grow_box(bbox):
    """Grow a canvas-order bbox to MIN_BOX_SIZE so the builder keeps it."""
    x_min, y_min, x_max, y_max = bbox
    if x_max - x_min < MIN_BOX_SIZE:
        x_max = min(1000, x_min + MIN_BOX_SIZE)
    if y_max - y_min < MIN_BOX_SIZE:
        y_max = min(1000, y_min + MIN_BOX_SIZE)
    return [x_min, y_min, x_max, y_max]


_SPECIAL_TOKENS = ("</s>", "<s>", "<pad>", "<unk>")


def _clean_text(value):
    """Strip Florence's special tokens (</s>, <s>, <pad>, ...) that leak into
    region labels — kijai only cleans the final caption string, not the labels."""
    text = str(value)
    for token in _SPECIAL_TOKENS:
        text = text.replace(token, "")
    return text.strip()


def _box_extent(box):
    """Reduce an 8-number quad polygon to an [x1,y1,x2,y2] extent; pass other
    boxes through."""
    if isinstance(box, (list, tuple)) and len(box) == 8:
        xs = box[0::2]
        ys = box[1::2]
        return [min(xs), min(ys), max(xs), max(ys)]
    return box


def _is_number_box(value):
    return (
        isinstance(value, (list, tuple))
        and len(value) >= 4
        and all(isinstance(n, (int, float)) for n in value[:8])
    )


def _iter_regions(data):
    """Yield (box, clean_label) from Florence2Run's `data` output, defensively
    across the shapes different tasks produce:
      * {'bboxes':[...], 'labels':[...]}           (caption_to_phrase_grounding)
      * a bare list of [x1,y1,x2,y2] boxes         (dense_region_caption)
      * [{'box'|'bbox':[...], 'label'|'text':str}] (ocr_with_region)
      * any of the above wrapped in a one-item per-image list
      * a dict keyed by the task token: {'<TASK>': {bboxes, labels}}"""
    # Unwrap a one-item per-image list around a dict container or a box list.
    if isinstance(data, list) and len(data) == 1 and isinstance(data[0], (dict, list)):
        inner = data[0]
        if isinstance(inner, dict) and any(k in inner for k in ("bboxes", "labels", "quad_boxes")):
            data = inner
        elif isinstance(inner, list):
            data = inner  # [[box, box, ...]] -> [box, box, ...]

    # Dig through a task-token-keyed wrapper: {'<DENSE_REGION_CAPTION>': {...}}.
    if isinstance(data, dict) and not any(
        k in data for k in ("bboxes", "labels", "quad_boxes", "box", "bbox")
    ):
        for value in data.values():
            if isinstance(value, dict) and any(k in value for k in ("bboxes", "labels", "quad_boxes")):
                data = value
                break

    if isinstance(data, dict) and any(k in data for k in ("bboxes", "labels", "quad_boxes")):
        boxes = data.get("bboxes") or data.get("quad_boxes") or []
        labels = data.get("labels") or []
        for index, box in enumerate(boxes):
            label = labels[index] if index < len(labels) else ""
            yield _box_extent(box), _clean_text(label)
        return

    if isinstance(data, list):
        for entry in data:
            if isinstance(entry, dict):
                box = entry.get("box") or entry.get("bbox") or entry.get("quad_boxes")
                label = entry.get("label") or entry.get("text") or ""
                if box is not None:
                    yield _box_extent(box), _clean_text(label)
            elif _is_number_box(entry):
                # Bare box from dense_region_caption (no label in this output).
                yield _box_extent(entry), ""


def _extract_palette(image, limit):
    """Dominant colors of the first frame as #RRGGBB, coarse-quantized so a few
    big regions win. Returns [] when torch/numpy aren't available."""
    try:
        import numpy as np

        frame = image[0].detach().cpu().numpy()
        pixels = (frame[..., :3].reshape(-1, 3) * 255.0).clip(0, 255).astype("uint8")
        if pixels.size == 0:
            return []
        # Quantize to a 32-step grid per channel and count the populous buckets.
        # Cast to int32 first: uint8 * 256 overflows and numpy now raises on it.
        buckets = ((pixels // 32) * 32 + 16).astype("int32")
        keys = buckets[:, 0] * 65536 + buckets[:, 1] * 256 + buckets[:, 2]
        values, counts = np.unique(keys, return_counts=True)
        order = counts.argsort()[::-1][:limit]
        hexes = []
        for key in values[order]:
            r = (int(key) >> 16) & 255
            g = (int(key) >> 8) & 255
            b = int(key) & 255
            hexes.append(f"#{r:02X}{g:02X}{b:02X}")
        return hexes
    except Exception:
        return []


def _florence(image, model, task, text_input="", max_new_tokens=512):
    """Call Florence2Run for one task -> (caption_string, data). Re-raises a
    missing-node error with a clear install hint (the shared _call_node only
    says the node is unavailable). `text_input` feeds grounding tasks like
    caption_to_phrase_grounding (the phrases to locate)."""
    try:
        out = _call_node(
            _FLORENCE_NODE,
            image=image,
            florence2_model=model,
            text_input=str(text_input),
            task=task,
            fill_mask=False,
            keep_model_loaded=True,
            max_new_tokens=int(max_new_tokens),
        )
    except Exception as exc:  # noqa: BLE001 - surface a clear install hint
        message = str(exc)
        if "not available" in message or _FLORENCE_NODE in message:
            raise RuntimeError(
                f"Required node '{_FLORENCE_NODE}' is not available. {_FLORENCE_HINT}"
            ) from exc
        raise
    out = tuple(out)
    caption = out[2] if len(out) > 2 else ""
    data = out[3] if len(out) > 3 else None
    if isinstance(caption, (list, tuple)):
        caption = caption[0] if caption else ""
    return str(caption).strip(), data


class ToobusyImageToIdeogramLayout:
    """Florence-2 image -> Ideogram4 structured-JSON draft for the Layout Builder."""

    CAPTION_TASKS = ["more_detailed_caption", "detailed_caption", "caption"]

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "florence2_model": (
                    "FL2MODEL",
                    {
                        "tooltip": (
                            "From a Florence-2 loader (kijai/ComfyUI-Florence2 "
                            "'DownloadAndLoadFlorence2Model'). Recommended: "
                            "Florence-2-large-ft (best object/region/OCR boxes) or "
                            "Florence-2-base-ft (lighter/faster). Avoid caption-only "
                            "community fine-tunes (CogFlorence / PromptGen): they weaken "
                            "the region & OCR tasks this node relies on for boxes."
                        ),
                    },
                ),
                "analysis_mode": (
                    ["Full Setup", "Composition Only (TODO)", "Style Only (TODO)"],
                    {
                        "default": "Full Setup",
                        "tooltip": "Full Setup rebuilds description + style + elements. Composition/Style are scaffolded TODOs and currently behave as Full Setup.",
                    },
                ),
                "caption_detail": (
                    cls.CAPTION_TASKS,
                    {"default": "more_detailed_caption"},
                ),
                "medium": (
                    ["photograph", "graphic_design", "illustration"],
                    {
                        "default": "photograph",
                        "tooltip": "What kind of image this is, written into style_description.medium. Photos -> photograph; thumbnails/posters -> graphic_design.",
                    },
                ),
                "max_elements": ("INT", {"default": 12, "min": 1, "max": 64}),
                "include_ocr_text": ("BOOLEAN", {"default": True, "label_on": "OCR text boxes", "label_off": "objects only"}),
                "include_color_palette": ("BOOLEAN", {"default": True, "label_on": "extract palette", "label_off": "no palette"}),
                "simplify_small_text": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "label_on": "drop tiny text",
                        "label_off": "keep tiny text",
                        "tooltip": "Drop OCR boxes smaller than ~2.5% of the frame on a side (watermarks, fine print).",
                    },
                ),
            }
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING", "INT", "INT")
    RETURN_NAMES = ("ideogram_json", "high_level_description", "background", "color_palette", "width", "height")
    FUNCTION = "analyze"
    CATEGORY = "toobusy/Plan"

    def analyze(
        self,
        image,
        florence2_model,
        analysis_mode="Full Setup",
        caption_detail="more_detailed_caption",
        medium="photograph",
        max_elements=12,
        include_ocr_text=True,
        include_color_palette=True,
        simplify_small_text=True,
    ):
        width, height = _first_image_size(image)

        # TODO(v2): Composition Only (keep existing builder content, only reuse
        # bbox positions) and Style Only (only push palette/lighting). For now
        # every mode produces a Full Setup draft.
        caption, _ = _florence(image, florence2_model, caption_detail)
        high_level_description = caption or "An image to lay out."

        elements = []
        # Objects: ground the caption's phrases to boxes. caption_to_phrase_grounding
        # returns {bboxes, labels} (boxes WITH descriptions) — unlike
        # dense_region_caption, whose data output is a bare box list with no labels.
        _, obj_data = _florence(
            image, florence2_model, "caption_to_phrase_grounding", text_input=caption
        )
        for box, label in _iter_regions(obj_data):
            norm = _norm_box(box, width, height)
            if norm is None:
                continue
            bbox = _grow_box(norm)
            elements.append({"type": "obj", "bbox": bbox, "desc": label or "object", "_area": _area(bbox)})

        # Text: OCR-with-region becomes text elements (text = recognized string).
        if include_ocr_text:
            _, ocr_data = _florence(image, florence2_model, "ocr_with_region")
            min_side = 25 if simplify_small_text else 0  # ~2.5% of 1000
            for box, label in _iter_regions(ocr_data):
                norm = _norm_box(box, width, height)
                if norm is None:
                    continue
                # Filter on the real (pre-growth) size so watermarks/fine print drop.
                if simplify_small_text and (norm[2] - norm[0] < min_side and norm[3] - norm[1] < min_side):
                    continue
                bbox = _grow_box(norm)
                elements.append(
                    {
                        "type": "text",
                        "bbox": bbox,
                        "text": label,
                        "desc": "rendered text integrated into the composition",
                        "_area": _area(bbox),
                    }
                )

        # Keep the most prominent elements, then order top-to-bottom / left-right.
        elements.sort(key=lambda el: el["_area"], reverse=True)
        elements = elements[: max(1, int(max_elements))]
        for el in elements:
            el.pop("_area", None)
        elements.sort(key=lambda el: (el["bbox"][1], el["bbox"][0]))  # y_min, x_min (canvas order)

        palette = _extract_palette(image, STYLE_PALETTE_MAX) if include_color_palette else []

        ideogram_elements = []
        for el in elements:
            ideogram = {"type": el["type"], "bbox": _to_ideogram_bbox(el["bbox"])}
            if el["type"] == "text":
                ideogram["text"] = el.get("text", "")
            ideogram["desc"] = el.get("desc", "")
            ideogram_elements.append(ideogram)

        if not ideogram_elements:
            ideogram_elements.append(
                {"type": "obj", "bbox": [250, 250, 750, 750], "desc": high_level_description}
            )

        # photo vs graphic: keep the two mutually exclusive (Ideogram convention).
        is_photo = medium == "photograph"
        style_description = {
            # v1: light, editable defaults — Florence captions don't give a
            # structured style breakdown, so the user refines these in the builder.
            "aesthetics": "draft from image analysis; refine in the builder",
            "lighting": "",
            "photo": "photograph, refine in the builder" if is_photo else "",
            "medium": str(medium),
        }
        if palette:
            style_description["color_palette"] = palette[:STYLE_PALETTE_MAX]

        background = "background extracted from the source image; refine as needed"

        payload = {
            "high_level_description": high_level_description,
            "style_description": style_description,
            "compositional_deconstruction": {
                "background": background,
                "elements": ideogram_elements,
            },
        }

        palette_string = ", ".join(palette[:ELEMENT_PALETTE_MAX]) if palette else ""
        return (
            json.dumps(payload, ensure_ascii=False, indent=2),
            high_level_description,
            background,
            palette_string,
            int(width),
            int(height),
        )


def _area(bbox):
    return max(0, bbox[2] - bbox[0]) * max(0, bbox[3] - bbox[1])


NODE_CLASS_MAPPINGS = {
    "ToobusyImageToIdeogramLayout": ToobusyImageToIdeogramLayout,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ToobusyImageToIdeogramLayout": "toobusy Image → Ideogram Layout",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
