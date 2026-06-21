"""toobusy Face Mask (optional mediapipe-based node).

For the masked face-swap workflow:
  - mode "erase_face": remove the face region from the BODY image (the face the
    Klein model should NOT keep), so it gets re-filled from the face reference.
  - mode "keep_face": keep ONLY the face region of the SOURCE face image and
    remove everything else (the inverted mask), so only the face is contributed.

Lightweight at import; heavy deps (torch, numpy, cv2, mediapipe) load lazily on
run. Outputs the processed IMAGE plus the face-region MASK.
"""

import importlib
import os


FACEMASK_INSTALL_MESSAGE = """Face Mask optional dependencies are missing.

Install only if you want to use toobusy Face Mask:

pip install -r custom_nodes/toobusy/requirements_facemask.txt
"""

# opencv is the only hard requirement (its Haar cascade is the reliable face
# detector fallback). mediapipe is optional — it gives a more precise face oval
# when it imports cleanly, but it is brittle across Python versions.
OPTIONAL_DEPENDENCIES = (
    ("cv2", "opencv-python"),
)

FACE_MODES = ["erase_face", "keep_face"]

# RGB fill (0-1) for removed regions in the output IMAGE.
FILL_COLORS = {
    "gray": (0.5, 0.5, 0.5),
    "black": (0.0, 0.0, 0.0),
    "white": (1.0, 1.0, 1.0),
}


def _missing_optional_dependencies(importer=importlib.import_module):
    missing = []
    for module_name, package_name in OPTIONAL_DEPENDENCIES:
        try:
            importer(module_name)
        except Exception:
            missing.append(package_name)
    return missing


def _ensure_facemask(importer=importlib.import_module):
    missing = _missing_optional_dependencies(importer)
    if missing:
        details = "\nMissing: " + ", ".join(missing)
        raise RuntimeError(FACEMASK_INSTALL_MESSAGE + details)


def _fill_rgb(name):
    return FILL_COLORS.get(name, FILL_COLORS["gray"])


def _apply_face_mask(rgb, mask, fill_rgb, mode, np):
    """Composite per mode.

    rgb: HxWx3 float32 (0-1). mask: HxW float32 (0-1, 1 = face region).
    erase_face -> remove the face region (fill where mask=1).
    keep_face  -> keep only the face region (fill where mask=0).
    Returns HxWx3 float32.
    """
    bg = np.array(fill_rgb, dtype="float32").reshape(1, 1, 3)
    if mode == "keep_face":
        alpha = mask[..., None]  # keep face, fill the rest
    else:  # erase_face
        alpha = 1.0 - mask[..., None]  # keep everything except the face
    return (rgb * alpha + bg * (1.0 - alpha)).astype("float32")


def _finalize_mask(mask_uint8, expand, feather, np, cv2):
    """Dilate + feather a binary uint8 mask into a soft float32 mask (0-1)."""
    if expand and expand > 0:
        k = int(expand) * 2 + 1
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
        mask_uint8 = cv2.dilate(mask_uint8, kernel)
    soft = mask_uint8.astype("float32") / 255.0
    if feather and feather > 0:
        k = int(feather) * 2 + 1
        soft = cv2.GaussianBlur(soft, (k, k), 0)
    return np.clip(soft, 0.0, 1.0).astype("float32")


_YOLO_CACHE = {}


def _find_face_yolo_model():
    """Locate a face YOLO model the user already has (e.g. from Face Detailer /
    ComfyUI-Impact-Pack). Prefers a segmentation model (gives a mask). Returns
    (path, kind) where kind is 'segm' or 'bbox', or (None, None)."""
    try:
        import folder_paths
    except Exception:
        return None, None
    candidates = []
    for ftype, kind in (("ultralytics_segm", "segm"), ("ultralytics_bbox", "bbox")):
        try:
            for name in folder_paths.get_filename_list(ftype):
                if "face" in name.lower():
                    path = folder_paths.get_full_path(ftype, name)
                    if path:
                        candidates.append((path, kind))
        except Exception:
            pass
    if not candidates:
        base = os.path.join(getattr(folder_paths, "models_dir", "") or "", "ultralytics")
        for sub, kind in (("segm", "segm"), ("bbox", "bbox")):
            directory = os.path.join(base, sub)
            if os.path.isdir(directory):
                for name in sorted(os.listdir(directory)):
                    if "face" in name.lower() and name.lower().endswith((".pt", ".pth")):
                        candidates.append((os.path.join(directory, name), kind))
    return candidates[0] if candidates else (None, None)


def _load_yolo(path):
    model = _YOLO_CACHE.get(path)
    if model is None:
        from ultralytics import YOLO

        model = YOLO(path)
        _YOLO_CACHE[path] = model
    return model


def _detect_face_yolo(frame_rgb_uint8, np, cv2):
    """Face mask via a YOLO face model (reuses the user's Face Detailer model).

    Quietly returns None when ultralytics or a face model is unavailable, so the
    detector chain falls through to mediapipe/opencv without noise.
    """
    path, kind = _find_face_yolo_model()
    if not path:
        return None
    try:
        model = _load_yolo(path)
    except Exception:
        return None
    height, width = frame_rgb_uint8.shape[:2]
    bgr = cv2.cvtColor(frame_rgb_uint8, cv2.COLOR_RGB2BGR)
    results = model.predict(bgr, verbose=False)
    mask = np.zeros((height, width), dtype="uint8")
    found = False
    for result in results:
        masks = getattr(result, "masks", None)
        if kind == "segm" and masks is not None and getattr(masks, "data", None) is not None:
            for seg_tensor in masks.data:
                seg = (seg_tensor.detach().cpu().numpy() * 255.0).astype("uint8")
                if seg.shape[:2] != (height, width):
                    seg = cv2.resize(seg, (width, height), interpolation=cv2.INTER_NEAREST)
                mask = np.maximum(mask, seg)
                found = True
        if found:
            continue
        boxes = getattr(result, "boxes", None)
        if boxes is not None and getattr(boxes, "xyxy", None) is not None:
            xyxy = boxes.xyxy.detach().cpu().numpy()
            if len(xyxy):
                areas = (xyxy[:, 2] - xyxy[:, 0]) * (xyxy[:, 3] - xyxy[:, 1])
                x1, y1, x2, y2 = xyxy[int(areas.argmax())][:4]
                center = (int((x1 + x2) / 2), int((y1 + y2) / 2))
                axes = (int((x2 - x1) * 0.55), int((y2 - y1) * 0.62))
                cv2.ellipse(mask, center, axes, 0, 0, 360, 255, -1)
                found = True
    return mask if found else None


def _detect_face_mediapipe(frame_rgb_uint8, np, cv2):
    """Precise face-oval mask via mediapipe FaceMesh; returns uint8 mask or None.

    Imports the solutions submodule directly (`mediapipe.python.solutions`) so it
    still works when `mediapipe.solutions` is not exposed on the top-level module
    (the "module 'mediapipe' has no attribute 'solutions'" case).
    """
    from mediapipe.python.solutions import face_mesh as mp_face_mesh

    height, width = frame_rgb_uint8.shape[:2]
    mesh = mp_face_mesh.FaceMesh(
        static_image_mode=True,
        max_num_faces=5,
        refine_landmarks=False,
        min_detection_confidence=0.5,
    )
    try:
        result = mesh.process(frame_rgb_uint8)
    finally:
        mesh.close()
    if not result.multi_face_landmarks:
        return None
    oval_idx = sorted({i for connection in mp_face_mesh.FACEMESH_FACE_OVAL for i in connection})
    best_mask = None
    best_area = -1.0
    for landmarks in result.multi_face_landmarks:
        points = np.array(
            [[landmarks.landmark[i].x * width, landmarks.landmark[i].y * height] for i in oval_idx],
            dtype="float32",
        )
        hull = cv2.convexHull(points.astype("int32"))
        mask = np.zeros((height, width), dtype="uint8")
        cv2.fillConvexPoly(mask, hull, 255)
        area = float(cv2.contourArea(hull))
        if area > best_area:
            best_area = area
            best_mask = mask
    return best_mask


def _detect_face_cv2(frame_rgb_uint8, np, cv2):
    """Fallback face mask via OpenCV Haar cascade (ships with opencv). bbox -> ellipse."""
    height, width = frame_rgb_uint8.shape[:2]
    gray = cv2.cvtColor(frame_rgb_uint8, cv2.COLOR_RGB2GRAY)
    cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    min_side = max(40, int(min(height, width) * 0.08))
    faces = cascade.detectMultiScale(
        gray,
        scaleFactor=1.1,
        minNeighbors=7,
        minSize=(min_side, min_side),
    )
    if len(faces) == 0:
        return None
    x, y, w, h = max(faces, key=lambda f: int(f[2]) * int(f[3]))
    mask = np.zeros((height, width), dtype="uint8")
    # The Haar box roughly bounds the face; inscribe a slightly-tall ellipse and
    # bias the center up a touch (forehead-to-chin sits above the box center).
    center = (int(x + w / 2), int(y + h * 0.46))
    axes = (int(w * 0.5), int(h * 0.62))
    cv2.ellipse(mask, center, axes, 0, 0, 360, 255, -1)
    return mask


def _face_oval_mask(frame_rgb_uint8, expand, feather, np, cv2, mp=None):
    """Face-region soft mask (0-1) for the largest face, or None.

    Detector chain, best first: a YOLO face model (reuses the user's Face
    Detailer model — accurate, no false positives), then mediapipe FaceMesh
    (precise oval), then OpenCV Haar (always available). `mp` is accepted for
    call-site compatibility but no longer required.
    """
    mask = None
    for detector in (_detect_face_yolo, _detect_face_mediapipe, _detect_face_cv2):
        try:
            mask = detector(frame_rgb_uint8, np, cv2)
        except Exception as exc:  # noqa: BLE001 - try the next detector
            print(f"[toobusy Face Mask] {detector.__name__} failed, trying next: {exc}")
            mask = None
        if mask is not None:
            break
    if mask is None:
        return None
    return _finalize_mask(mask, expand, feather, np, cv2)


class ToobusyFaceMask:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "mode": (FACE_MODES, {"default": "erase_face"}),
                "fill": (list(FILL_COLORS.keys()), {"default": "gray"}),
            },
            "optional": {
                "expand": ("INT", {"default": 8, "min": 0, "max": 256, "tooltip": "Grow the face mask outward (px)."}),
                "feather": ("INT", {"default": 6, "min": 0, "max": 128, "tooltip": "Soften the mask edges (px)."}),
            },
        }

    RETURN_TYPES = ("IMAGE", "MASK")
    RETURN_NAMES = ("image", "mask")
    FUNCTION = "process"
    CATEGORY = "toobusy/Image"

    def process(self, image, mode, fill, expand=8, feather=6):
        _ensure_facemask()
        import numpy as np
        import torch
        import cv2

        mode = mode if mode in FACE_MODES else "erase_face"
        fill_rgb = _fill_rgb(fill)

        out_images = []
        out_masks = []
        for frame in image:
            rgb = frame[..., :3].clamp(0.0, 1.0).cpu().numpy().astype("float32")
            frame_uint8 = (rgb * 255.0).astype("uint8")
            mask = _face_oval_mask(frame_uint8, expand, feather, np, cv2)
            if mask is None:
                # No face found: pass image through, empty mask.
                out_images.append(torch.from_numpy(rgb))
                out_masks.append(torch.zeros(rgb.shape[:2], dtype=torch.float32))
                continue
            composited = _apply_face_mask(rgb, mask, fill_rgb, mode, np)
            out_images.append(torch.from_numpy(composited))
            out_masks.append(torch.from_numpy(mask))

        image_out = torch.stack(out_images, dim=0)
        mask_out = torch.stack(out_masks, dim=0)
        return (image_out, mask_out)


NODE_CLASS_MAPPINGS = {
    "ToobusyFaceMask": ToobusyFaceMask,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ToobusyFaceMask": "toobusy Face Mask",
}
