"""Pick how large to work on an image from the size of the faces in it.

SeedVR2 retouch looks most natural when a face is about 200 px wide while it is
processed (2BZ test 2026-10-15, SAM3 "face" boxes: a 1 MP full-body shot enlarged x2
-> face 201 px looked best, x4 -> 397 px looked over-sharpened; close-ups whose faces
are already 500 px+ need no retouch at all). Character sheets work out of the box
because their faces already sit near that size.

`plan_face_scale` is pure Python so CI can test it without torch or ComfyUI.
"""

import json
import math


def _boxes(bboxes):
    """SAM3/RT-DETR per-frame lists, a flat list, one dict or a JSON string -> list of dicts."""
    if bboxes is None:
        return []
    if isinstance(bboxes, str):
        text = bboxes.strip()
        bboxes = json.loads(text) if text else []
    if isinstance(bboxes, dict):
        bboxes = [bboxes]
    if not isinstance(bboxes, list) or not bboxes:
        return []
    if isinstance(bboxes[0], list):
        bboxes = bboxes[0]
    out = []
    for b in bboxes:
        try:
            out.append({k: float(b[k]) for k in ("x", "y", "width", "height")})
        except (KeyError, TypeError, ValueError):
            continue
    return out


def _round_mult(value, multiple):
    return max(int(multiple), int(round(float(value) / multiple)) * int(multiple))


def plan_face_scale(width, height, bboxes, detect_width=None, target_face_px=200, pick="largest",
                    no_face_megapixels=4.0, max_scale=4.0, shrink_large_faces=False, multiple_of=16):
    """Return dict(scale, width, height, upscale, face_px, faces, reason).

    `bboxes` are in the coordinates of the image the detector saw (`detect_width` wide);
    they are mapped back to the input's `width`. `upscale` is the integer factor for an
    upscaler that only takes whole numbers (VOSR 2.0): at least 2, then resized to the
    exact plan.
    """
    k = float(width) / float(detect_width) if detect_width else 1.0
    widths = sorted((b["width"] * k for b in _boxes(bboxes) if b["width"] > 0), reverse=True)
    if widths:
        if pick == "smallest":
            face = widths[-1]
        elif pick == "median":
            face = widths[len(widths) // 2]
        else:
            face = widths[0]
        scale = float(target_face_px) / face
        if scale < 1.0 and not shrink_large_faces:
            reason = f"얼굴이 이미 {face:.0f}px — 목표 {target_face_px}px보다 커서 크기 그대로 (클로즈업은 리터치가 꼭 필요하지 않음)"
            scale = 1.0
        else:
            reason = f"가장 큰 얼굴 {face:.0f}px → {target_face_px}px" if pick == "largest" else f"얼굴({pick}) {face:.0f}px → {target_face_px}px"
    else:
        face = 0.0
        pixels = float(width * height)
        scale = max(1.0, math.sqrt(no_face_megapixels * 1e6 / pixels)) if no_face_megapixels > 0 else 1.0
        reason = f"얼굴을 못 찾음 → {no_face_megapixels:g}MP 근처로"
    scale = max(0.25, min(float(max_scale), scale))
    if abs(scale - 1.0) < 1e-6:  # keep the exact original size (no rounding to the multiple)
        w, h = int(width), int(height)
    else:
        w = _round_mult(width * scale, multiple_of)
        h = _round_mult(height * scale, multiple_of)
    # whole-number factor for VOSR 2.0; up to 10% short is finished by the exact resize (x2 for 2.04, not x3)
    upscale = max(2, min(4, math.ceil(scale / 1.1 - 1e-6)))
    return {"scale": round(scale, 4), "width": w, "height": h, "upscale": upscale, "needs_upscale": scale > 1.0 + 1e-6,
            "face_px": round(face), "faces": len(widths), "reason": reason}


class ToobusyFaceScalePlan:
    """Face boxes in -> working size out (and the whole-number factor for VOSR 2.0)."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE", {"tooltip": "원본 이미지(이 크기 기준으로 배율 계산)"}),
                "bboxes": ("BOUNDING_BOX", {"forceInput": True, "tooltip": "SAM3 Detect 'face' 박스"}),
                "target_face_px": ("INT", {
                    "default": 200, "min": 32, "max": 2048, "step": 8,
                    "tooltip": "처리할 때 얼굴(SAM3 face 박스) 폭. 200이 실측 적정선 — 올리면 더 쨍하고, 너무 크면 부자연스러움.",
                }),
                "pick": (["largest", "median", "smallest"], {
                    "default": "largest",
                    "tooltip": "얼굴이 여러 개일 때 기준. largest = 가장 큰 얼굴이 과해지지 않게(권장).",
                }),
                "no_face_megapixels": ("FLOAT", {
                    "default": 4.0, "min": 0.0, "max": 32.0, "step": 0.5,
                    "tooltip": "얼굴이 없을 때 이 MP 근처로 키움(이미 크면 그대로). 0 = 그대로.",
                }),
                "max_scale": ("FLOAT", {"default": 4.0, "min": 1.0, "max": 8.0, "step": 0.25,
                                        "tooltip": "한 변 최대 배율(4 = 면적 16배)"}),
                "shrink_large_faces": ("BOOLEAN", {"default": False,
                                                   "tooltip": "얼굴이 목표보다 크면 줄여서 처리(기본 끔 = 크기 그대로)"}),
                "multiple_of": ("INT", {"default": 16, "min": 8, "max": 64, "step": 8}),
            },
            "optional": {
                "detect_image": ("IMAGE", {"tooltip": "SAM3가 본 이미지(줄여서 검출했을 때). 박스 좌표를 원본 크기로 환산."}),
            },
        }

    RETURN_TYPES = ("INT", "INT", "INT", "FLOAT", "STRING", "BOOLEAN")
    RETURN_NAMES = ("vosr2_upscale", "width", "height", "scale", "info", "needs_upscale")
    FUNCTION = "plan"
    CATEGORY = "toobusy/retouch"
    DESCRIPTION = ("Measures the faces SAM3 found and plans the working size so a face is about 200 px wide "
                   "(the retouch sweet spot). Feed vosr2_upscale to VOSR 2.0 Upscale and width/height to an "
                   "Image Scale node, then retouch at that size.")

    def plan(self, image, bboxes, target_face_px, pick, no_face_megapixels, max_scale, shrink_large_faces,
             multiple_of, detect_image=None):
        h, w = int(image.shape[1]), int(image.shape[2])
        dw = int(detect_image.shape[2]) if detect_image is not None else None
        p = plan_face_scale(w, h, bboxes, dw, target_face_px, pick, no_face_megapixels, max_scale,
                            shrink_large_faces, multiple_of)
        mp_in, mp_out = w * h / 1e6, p["width"] * p["height"] / 1e6
        info = (f"입력 {w}×{h} ({mp_in:.1f}MP) · 얼굴 {p['faces']}개\n{p['reason']}\n"
                + (f"배율 ×{p['scale']:.2f} → 작업·결과 {p['width']}×{p['height']} ({mp_out:.1f}MP) · VOSR2 ×{p['upscale']} 후 맞춤"
                 if p["needs_upscale"] else f"작업·결과 {p['width']}×{p['height']} ({mp_out:.1f}MP) · VOSR2 건너뜀"))
        return (p["upscale"], p["width"], p["height"], p["scale"], info, p["needs_upscale"])


class ToobusyUseUpscaledIfNeeded:
    """Lazy pick: only the branch that is used gets computed, so VOSR 2.0 never runs when nothing needs enlarging."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "use_upscaled": ("BOOLEAN", {"forceInput": True, "tooltip": "Face-Size Scale Plan의 needs_upscale"}),
                "upscaled": ("IMAGE", {"lazy": True, "tooltip": "키운 이미지(VOSR 2.0) — 필요할 때만 계산"}),
                "original": ("IMAGE", {"lazy": True, "tooltip": "원본 — 키울 필요 없을 때"}),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "pick"
    CATEGORY = "toobusy/retouch"

    def check_lazy_status(self, use_upscaled, upscaled=None, original=None):
        if use_upscaled:
            return ["upscaled"] if upscaled is None else []
        return ["original"] if original is None else []

    def pick(self, use_upscaled, upscaled=None, original=None):
        return (upscaled if use_upscaled else original,)


NODE_CLASS_MAPPINGS = {"ToobusyFaceScalePlan": ToobusyFaceScalePlan, "ToobusyUseUpscaledIfNeeded": ToobusyUseUpscaledIfNeeded}
NODE_DISPLAY_NAME_MAPPINGS = {"ToobusyFaceScalePlan": "2BZ Face-Size Scale Plan", "ToobusyUseUpscaledIfNeeded": "2BZ Use Upscaled If Needed"}
