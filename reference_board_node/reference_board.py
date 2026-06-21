import base64
import hashlib
import json
import os
import re
import uuid
import wave
from io import BytesIO

import numpy as np
import torch
from PIL import Image


REFERENCE_TARGET_PIXELS = 1_000_000

DEFAULT_REFERENCE_BOARD = {
    "version": 1,
    "global_note": "",
    "items": [],
}

REFERENCE_CACHE_SUBDIR = "toobusy_reference_board"
REFERENCE_IMAGE_SUBDIR = f"{REFERENCE_CACHE_SUBDIR}/images"
REFERENCE_AUDIO_SUBDIR = f"{REFERENCE_CACHE_SUBDIR}/audio"
REFERENCE_PRESET_SUBDIR = f"{REFERENCE_CACHE_SUBDIR}/presets"

IMAGE_ROLE_DEFS = (
    ("character_a", "Character A"),
    ("character_b", "Character B"),
    ("character_c", "Character C"),
    ("character_d", "Character D"),
    ("face_a", "Face A"),
    ("face_b", "Face B"),
    ("outfit_a", "Outfit A"),
    ("outfit_b", "Outfit B"),
    ("background_a", "Background A"),
    ("pose_a", "Pose A"),
    ("style_a", "Style A"),
    ("prop_a", "Prop A"),
    ("main_character", "Main Character A"),
    ("secondary_character", "Character B"),
    ("pose", "Pose"),
    ("outfit", "Outfit"),
    ("background", "Background"),
    ("style", "Style"),
    ("product", "Product"),
)

AUDIO_ROLE_DEFS = (
    ("audio_a", "Audio A"),
    ("audio_b", "Audio B"),
    ("audio_1", "Selected Audio 1"),
    ("audio_2", "Selected Audio 2"),
)

LEGACY_IMAGE_ROLES = (
    ("main_character", "Main Character A"),
    ("secondary_character", "Character B"),
    ("pose", "Pose"),
    ("outfit", "Outfit"),
    ("background", "Background"),
    ("style", "Style"),
    ("product", "Product"),
)

ROLE_DEFS = LEGACY_IMAGE_ROLES

LEGACY_ROLE_MAP = {
    "character_a": "main_character",
    "character_b": "secondary_character",
    "pose_a": "pose",
    "outfit_a": "outfit",
    "background_a": "background",
    "style_a": "style",
}

LEGACY_AUDIO_ROLE_MAP = {
    "audio_a": "audio_1",
    "audio_b": "audio_2",
}

CARD_TYPE_BY_ROLE = {
    "character_a": "character",
    "character_b": "character",
    "character_c": "character",
    "character_d": "character",
    "face_a": "face",
    "face_b": "face",
    "outfit_a": "outfit",
    "outfit_b": "outfit",
    "background_a": "background",
    "pose_a": "pose",
    "style_a": "style",
    "prop_a": "prop",
    "main_character": "character",
    "secondary_character": "character",
    "pose": "pose",
    "outfit": "outfit",
    "background": "background",
    "style": "style",
    "product": "prop",
    "audio_a": "audio",
    "audio_b": "audio",
    "audio_1": "audio",
    "audio_2": "audio",
}

ROLE_ALIASES = {
    "main": "main_character",
    "main_a": "main_character",
    "main character": "main_character",
    "main character a": "main_character",
    "character a": "character_a",
    "character_a": "character_a",
    "a": "character_a",
    "secondary": "secondary_character",
    "secondary_character": "secondary_character",
    "character b": "secondary_character",
    "character_b": "character_b",
    "b": "character_b",
    "pose": "pose",
    "outfit": "outfit",
    "background": "background",
    "style": "style",
    "product": "product",
    "face_a": "face_a",
    "face a": "face_a",
    "face_b": "face_b",
    "face b": "face_b",
    "outfit_a": "outfit_a",
    "outfit a": "outfit_a",
    "outfit_b": "outfit_b",
    "outfit b": "outfit_b",
    "character_c": "character_c",
    "character c": "character_c",
    "character_d": "character_d",
    "character d": "character_d",
    "background_a": "background_a",
    "background a": "background_a",
    "pose_a": "pose_a",
    "pose a": "pose_a",
    "style_a": "style_a",
    "style a": "style_a",
    "prop_a": "prop_a",
    "prop a": "prop_a",
    "audio_a": "audio_a",
    "audio a": "audio_a",
    "voice_a": "audio_a",
    "voice a": "audio_a",
    "audio_b": "audio_b",
    "audio b": "audio_b",
    "voice_b": "audio_b",
    "voice b": "audio_b",
    "audio_1": "audio_1",
    "audio 1": "audio_1",
    "selected_audio_1": "audio_1",
    "selected audio 1": "audio_1",
    "person1_audio": "audio_1",
    "person 1 audio": "audio_1",
    "audio_2": "audio_2",
    "audio 2": "audio_2",
    "selected_audio_2": "audio_2",
    "selected audio 2": "audio_2",
    "person2_audio": "audio_2",
    "person 2 audio": "audio_2",
    "extra": "extra",
    "ignore": "ignore",
    "extra / ignore": "ignore",
}


def _parse_board(board_json):
    try:
        data = json.loads(board_json or "")
        if isinstance(data, dict) and isinstance(data.get("items"), list):
            return data
    except Exception:
        pass
    return dict(DEFAULT_REFERENCE_BOARD)


def _normalize_role(role):
    text = str(role or "").strip().lower().replace("-", "_")
    valid = {key for key, _label in IMAGE_ROLE_DEFS} | {key for key, _label in AUDIO_ROLE_DEFS}
    return ROLE_ALIASES.get(text, text if text in valid else "ignore")


def _resize_size_to_total_pixels(width, height, target_pixels=REFERENCE_TARGET_PIXELS):
    width = max(1, int(width))
    height = max(1, int(height))
    pixels = width * height
    if pixels <= int(target_pixels):
        return width, height, False
    scale = (float(target_pixels) / float(pixels)) ** 0.5
    return max(1, int(round(width * scale))), max(1, int(round(height * scale))), True


def _data_url_to_pil(data_url):
    if not isinstance(data_url, str) or not data_url.startswith("data:image/"):
        return None
    try:
        _prefix, payload = data_url.split(",", 1)
        return Image.open(BytesIO(base64.b64decode(payload))).convert("RGB")
    except Exception:
        return None


def _data_url_to_bytes(data_url, expected_prefix=None):
    if not isinstance(data_url, str) or not data_url.startswith("data:"):
        return None, ""
    try:
        prefix, payload = data_url.split(",", 1)
        if expected_prefix and not prefix.startswith(expected_prefix):
            return None, ""
        return base64.b64decode(payload), prefix
    except Exception:
        return None, ""


def _input_directory():
    try:
        import folder_paths

        return folder_paths.get_input_directory()
    except Exception:
        return os.path.join(os.getcwd(), "input")


def _safe_reference_path(filename):
    text = str(filename or "").replace("\\", "/").lstrip("/")
    if not text:
        return None
    parts = [part for part in text.split("/") if part not in ("", ".", "..")]
    if not parts:
        return None
    base = os.path.abspath(_input_directory())
    path = os.path.abspath(os.path.join(base, *parts))
    try:
        common = os.path.commonpath([base, path])
    except Exception:
        return None
    if common != base:
        return None
    return path


def _safe_name(value, fallback="reference"):
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or fallback)).strip("._")[:60]
    return safe or fallback


def _filename_to_pil(filename):
    path = _safe_reference_path(filename)
    if not path or not os.path.isfile(path):
        return None
    try:
        return Image.open(path).convert("RGB")
    except Exception:
        return None


def _pil_to_image_tensor(image):
    array = np.asarray(image.convert("RGB"), dtype=np.float32) / 255.0
    return torch.from_numpy(array)[None,]


def _blank_image():
    return torch.zeros((1, 1, 1, 3), dtype=torch.float32)


def _blank_audio(sample_rate=44100):
    return {"waveform": torch.zeros((1, 1, 0), dtype=torch.float32), "sample_rate": int(sample_rate)}


def _prepare_image(image, item=None):
    if image is None:
        return None, None
    item = item or {}
    original_w, original_h = image.size
    resized_w, resized_h, resized = _resize_size_to_total_pixels(original_w, original_h)
    if resized:
        image = image.resize((resized_w, resized_h), Image.Resampling.LANCZOS)
        resize_note = "lanczos downscale"
    else:
        resize_note = "unchanged"
    reported_original_w = int(item.get("original_width") or item.get("originalWidth") or original_w)
    reported_original_h = int(item.get("original_height") or item.get("originalHeight") or original_h)
    return _pil_to_image_tensor(image), {
        "original_width": reported_original_w,
        "original_height": reported_original_h,
        "width": resized_w,
        "height": resized_h,
        "resize": resize_note,
    }


def _manifest_item(item, role, size_meta, item_type="image"):
    result = {
        "id": str(item.get("id") or ""),
        "name": str(item.get("name") or ""),
        "role": role,
        "type": item_type,
        "note": str(item.get("note") or ""),
        "source": str(item.get("source") or ""),
        "x": round(float(item.get("x", 0)), 2),
        "y": round(float(item.get("y", 0)), 2),
        **(size_meta or {}),
    }
    if item.get("filename"):
        result["filename"] = str(item.get("filename"))
    return result


def _audio_duration(audio):
    try:
        waveform = audio.get("waveform")
        sample_rate = int(audio.get("sample_rate") or 44100)
        samples = int(waveform.shape[-1])
        return float(samples) / float(sample_rate) if sample_rate > 0 else 0.0
    except Exception:
        return 0.0


def _wave_handle_to_audio(handle):
    channels = int(handle.getnchannels())
    sample_rate = int(handle.getframerate())
    sample_width = int(handle.getsampwidth())
    frame_count = int(handle.getnframes())
    raw = handle.readframes(frame_count)

    if sample_width == 1:
        array = np.frombuffer(raw, dtype=np.uint8).astype(np.float32)
        array = (array - 128.0) / 128.0
    elif sample_width == 2:
        array = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    elif sample_width == 4:
        array = np.frombuffer(raw, dtype="<i4").astype(np.float32) / 2147483648.0
    else:
        raise ValueError(f"unsupported WAV sample width: {sample_width}")

    if channels <= 0:
        raise ValueError("invalid WAV channel count")
    try:
        array = array.reshape(-1, channels).T
    except Exception:
        raise ValueError("invalid WAV frame data")
    waveform = torch.from_numpy(array.copy())[None,]
    audio = {"waveform": waveform, "sample_rate": sample_rate}
    return audio, {
        "sample_rate": sample_rate,
        "channels": channels,
        "samples": int(waveform.shape[-1]),
        "source_duration_seconds": round(_audio_duration(audio), 4),
    }


def _filename_to_audio(filename):
    path = _safe_reference_path(filename)
    if not path or not os.path.isfile(path):
        return None, None
    if os.path.splitext(path)[1].lower() != ".wav":
        return None, {"error": "unsupported audio format; WAV/PCM is required for AUDIO output"}
    try:
        with wave.open(path, "rb") as handle:
            return _wave_handle_to_audio(handle)
    except Exception as exc:
        return None, {"error": f"could not decode wav: {exc}"}


def _data_url_to_audio(data_url):
    payload, prefix = _data_url_to_bytes(data_url, "data:audio/")
    if payload is None:
        return None, None
    mime = prefix.split(";", 1)[0].split(":", 1)[-1].lower()
    if mime not in {"audio/wav", "audio/x-wav", "audio/wave"}:
        return None, {"error": "unsupported embedded audio format; WAV/PCM is required for AUDIO output"}
    try:
        with wave.open(BytesIO(payload), "rb") as handle:
            return _wave_handle_to_audio(handle)
    except Exception as exc:
        return None, {"error": f"could not decode embedded wav: {exc}"}


def _process_audio(audio, item):
    if audio is None:
        return None, 0.0, {}
    waveform = audio.get("waveform")
    sample_rate = int(audio.get("sample_rate") or 44100)
    if waveform is None or sample_rate <= 0:
        return None, 0.0, {"error": "invalid AUDIO object"}
    total_samples = int(waveform.shape[-1])
    source_duration = float(total_samples) / float(sample_rate) if sample_rate > 0 else 0.0
    start_seconds = max(0.0, float(item.get("start_offset_seconds") or 0.0))
    duration_value = item.get("duration_seconds")
    if duration_value in (None, ""):
        duration_seconds = max(0.0, source_duration - start_seconds)
    else:
        duration_seconds = max(0.0, float(duration_value))
    end_mode = str(item.get("end_mode") or "trim")
    if end_mode not in {"trim", "pad_silence", "loop"}:
        end_mode = "trim"

    start_sample = min(total_samples, int(round(start_seconds * sample_rate)))
    target_samples = int(round(duration_seconds * sample_rate))
    segment = waveform[..., start_sample : start_sample + target_samples]
    if target_samples <= 0:
        segment = waveform[..., 0:0]
    current_samples = int(segment.shape[-1])
    if current_samples < target_samples and end_mode == "pad_silence":
        pad = torch.zeros((*segment.shape[:-1], target_samples - current_samples), dtype=segment.dtype, device=segment.device)
        segment = torch.cat([segment, pad], dim=-1)
    elif current_samples < target_samples and end_mode == "loop" and current_samples > 0:
        repeats = (target_samples + current_samples - 1) // current_samples
        segment = segment.repeat(*([1] * (segment.ndim - 1)), repeats)[..., :target_samples]
    processed = {"waveform": segment, "sample_rate": sample_rate}
    actual_duration = _audio_duration(processed)
    return processed, actual_duration, {
        "sample_rate": sample_rate,
        "source_duration_seconds": round(source_duration, 4),
        "start_offset_seconds": round(start_seconds, 4),
        "duration_seconds": round(duration_seconds, 4),
        "actual_duration_seconds": round(actual_duration, 4),
        "end_mode": end_mode,
        "start_sample": start_sample,
        "samples": int(segment.shape[-1]),
    }


def _save_reference_image_from_data_url(data_url, source_name="reference"):
    image = _data_url_to_pil(data_url)
    if image is None:
        raise ValueError("invalid image data")
    original_w, original_h = image.size
    resized_w, resized_h, resized = _resize_size_to_total_pixels(original_w, original_h)
    if resized:
        image = image.resize((resized_w, resized_h), Image.Resampling.LANCZOS)
    safe_name = _safe_name(source_name, "reference")[:40]
    filename = f"{safe_name}_{uuid.uuid4().hex[:12]}.jpg"
    rel_path = f"{REFERENCE_IMAGE_SUBDIR}/{filename}"
    out_dir = os.path.join(_input_directory(), REFERENCE_IMAGE_SUBDIR)
    os.makedirs(out_dir, exist_ok=True)
    image.save(os.path.join(out_dir, filename), format="JPEG", quality=92)
    return {
        "filename": rel_path,
        "subfolder": REFERENCE_IMAGE_SUBDIR,
        "name": filename,
        "width": resized_w,
        "height": resized_h,
        "original_width": original_w,
        "original_height": original_h,
        "resize": "lanczos downscale" if resized else "unchanged",
    }


def _save_reference_audio_from_data_url(data_url, source_name="audio"):
    payload, prefix = _data_url_to_bytes(data_url, "data:audio/")
    if payload is None:
        raise ValueError("invalid audio data")
    mime = prefix.split(";", 1)[0].split(":", 1)[-1].lower()
    ext = {
        "audio/wav": ".wav",
        "audio/x-wav": ".wav",
        "audio/wave": ".wav",
        "audio/mpeg": ".mp3",
        "audio/mp3": ".mp3",
        "audio/ogg": ".ogg",
        "audio/webm": ".webm",
        "audio/mp4": ".m4a",
    }.get(mime, ".audio")
    safe_name = _safe_name(source_name, "audio")[:40]
    filename = f"{safe_name}_{uuid.uuid4().hex[:12]}{ext}"
    rel_path = f"{REFERENCE_AUDIO_SUBDIR}/{filename}"
    out_dir = os.path.join(_input_directory(), REFERENCE_AUDIO_SUBDIR)
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, filename)
    with open(path, "wb") as handle:
        handle.write(payload)
    audio, meta = _filename_to_audio(rel_path)
    meta = meta or {}
    return {
        "filename": rel_path,
        "subfolder": REFERENCE_AUDIO_SUBDIR,
        "name": filename,
        "mime": mime,
        "bytes": len(payload),
        "duration_seconds": meta.get("source_duration_seconds"),
        "sample_rate": meta.get("sample_rate"),
        "channels": meta.get("channels"),
        "decode": "wav/pcm" if audio is not None else meta.get("error", "stored only"),
    }


def _preset_directory():
    path = os.path.join(_input_directory(), REFERENCE_PRESET_SUBDIR)
    os.makedirs(path, exist_ok=True)
    return path


def _preset_path(preset_id):
    safe = _safe_name(preset_id, "reference_board")
    if not safe.endswith(".json"):
        safe += ".json"
    return os.path.join(_preset_directory(), safe)


def _strip_item_for_preset(item):
    cleaned = dict(item)
    cleaned.pop("src", None)
    cleaned.pop("data_url", None)
    cleaned.pop("preview_src", None)
    return cleaned


def _prepare_items_for_preset(items):
    prepared = []
    for item in items:
        if not isinstance(item, dict):
            continue
        working = dict(item)
        if not working.get("filename") and (working.get("src") or working.get("data_url")):
            try:
                saved = _save_reference_image_from_data_url(
                    working.get("src") or working.get("data_url"),
                    working.get("name") or working.get("id") or "reference",
                )
                working["filename"] = saved["filename"]
                working["width"] = saved["width"]
                working["height"] = saved["height"]
                working["original_width"] = working.get("original_width") or saved["original_width"]
                working["original_height"] = working.get("original_height") or saved["original_height"]
                working["resize"] = saved["resize"]
            except Exception:
                pass
        prepared.append(_strip_item_for_preset(working))
    return prepared


def _card_label(item):
    return str(item.get("name") or item.get("id") or item.get("role") or "card")


def _card_face_mask(tensor, item, mode):
    """Apply a face mask to the card image. mode = 'erase_face' (remove the face
    region) or 'keep_face' (keep only the face). Returns (tensor, warning_or_None)."""
    label = _card_label(item)
    action = "Erase Face" if mode == "erase_face" else "Keep Face Only"
    try:
        import numpy as np
        import cv2
        from ..face_mask_node.face_mask import _face_oval_mask, _apply_face_mask, _fill_rgb
    except Exception as exc:  # noqa: BLE001 - optional dependency
        msg = f"{action} on '{label}' skipped: opencv not installed. Run: pip install -r custom_nodes/toobusy/requirements_facemask.txt"
        print(f"[toobusy Reference Board] {msg} [{exc}]")
        return tensor, msg
    try:
        frame = tensor[0]
        rgb = frame[..., :3].clamp(0.0, 1.0).cpu().numpy().astype("float32")
        frame_uint8 = (rgb * 255.0).astype("uint8")
        expand = int(item.get("face_erase_expand", 8))
        feather = int(item.get("face_erase_feather", 6))
        mask = _face_oval_mask(frame_uint8, expand, feather, np, cv2)
        if mask is None:
            return tensor, f"{action} on '{label}': no face detected."
        fill = _fill_rgb(str(item.get("face_erase_fill", "gray")))
        out = _apply_face_mask(rgb, mask, fill, mode, np)
        return torch.from_numpy(out).unsqueeze(0).to(device=tensor.device, dtype=tensor.dtype), None
    except Exception as exc:  # noqa: BLE001
        msg = f"{action} on '{label}' failed: {exc}"
        print(f"[toobusy Reference Board] {msg}")
        return tensor, msg


def _card_bg_remove(tensor, item):
    """Remove the card's background. Returns (tensor, warning_or_None)."""
    label = _card_label(item)
    try:
        import numpy as np
        from PIL import Image as PILImage
        from rembg import new_session, remove
        from ..background_remove_node.background_remove import _background_rgb, _composite_frame
    except Exception as exc:  # noqa: BLE001 - optional dependency
        msg = f"Remove Background on '{label}' skipped: rembg/onnxruntime not installed. Run: pip install -r custom_nodes/toobusy/requirements_rembg.txt"
        print(f"[toobusy Reference Board] {msg} [{exc}]")
        return tensor, msg
    try:
        frame = tensor[0]
        rgb_uint8 = (frame[..., :3].clamp(0.0, 1.0).cpu().numpy() * 255.0).astype("uint8")
        pil = PILImage.fromarray(rgb_uint8, mode="RGB")
        session = new_session(str(item.get("bg_remove_model", "u2net")))
        cut = remove(pil, session=session).convert("RGBA")
        rgba = np.asarray(cut).astype("float32") / 255.0
        bg = _background_rgb(str(item.get("bg_remove_background", "white")))
        comp, _alpha = _composite_frame(rgba, bg, np)
        return torch.from_numpy(comp).unsqueeze(0).to(device=tensor.device, dtype=tensor.dtype), None
    except Exception as exc:  # noqa: BLE001
        msg = f"Remove Background on '{label}' failed: {exc}"
        print(f"[toobusy Reference Board] {msg}")
        return tensor, msg


def _apply_card_processors(tensor, item):
    """Apply per-card modules in order. Returns (tensor, [warnings])."""
    warnings = []
    out = tensor
    if item.get("face_erase_enabled"):
        out, warn = _card_face_mask(out, item, "erase_face")
        if warn:
            warnings.append(warn)
    elif item.get("face_keep_enabled"):
        out, warn = _card_face_mask(out, item, "keep_face")
        if warn:
            warnings.append(warn)
    if item.get("bg_remove_enabled"):
        out, warn = _card_bg_remove(out, item)
        if warn:
            warnings.append(warn)
    return out, warnings


def _roles_summary(items):
    labels = []
    seen = set()
    for item in items:
        role = _normalize_role(item.get("role"))
        if role in ("ignore", "extra") or role in seen:
            continue
        seen.add(role)
        labels.append(role)
    return labels


def _preset_id_for_name(name):
    """Stable, collision-free preset id derived from the full (unicode) name.

    `_safe_name` alone collapses non-ASCII names (e.g. all-Korean) to the same
    fallback, so distinct presets would overwrite each other. Appending a short
    hash of the original name keeps same-name saves overwriting (intended) while
    guaranteeing different names get different files. The hash is hex, so it
    survives `_preset_path`'s re-sanitization unchanged.
    """
    sanitized = _safe_name(name, "preset")
    digest = hashlib.sha1(str(name or "").encode("utf-8")).hexdigest()[:8]
    return f"{sanitized}-{digest}"


def _save_board_preset(name, board):
    import datetime

    preset_name = str(name or "").strip() or "Reference Board"
    preset_id = _preset_id_for_name(preset_name)
    now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()
    old = {}
    path = _preset_path(preset_id)
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as handle:
                old = json.load(handle)
        except Exception:
            old = {}
    items = _prepare_items_for_preset(board.get("items", []))
    preset = {
        "version": 1,
        "id": preset_id,
        "name": preset_name,
        "created_at": old.get("created_at") or now,
        "updated_at": now,
        "global_note": str(board.get("global_note") or ""),
        "items": items,
    }
    # Atomic write: write to a temp file then replace, so a crash mid-write can
    # never truncate/lose an existing preset.
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as handle:
        json.dump(preset, handle, ensure_ascii=False, indent=2)
    os.replace(tmp_path, path)
    return _preset_summary(preset)


def _preset_summary(preset):
    items = preset.get("items") if isinstance(preset.get("items"), list) else []
    return {
        "id": str(preset.get("id") or ""),
        "name": str(preset.get("name") or preset.get("id") or ""),
        "updated_at": str(preset.get("updated_at") or ""),
        "image_count": len(items),
        "roles": _roles_summary(items),
    }


def _list_board_presets():
    presets = []
    for filename in os.listdir(_preset_directory()):
        if not filename.endswith(".json"):
            continue
        try:
            with open(os.path.join(_preset_directory(), filename), "r", encoding="utf-8") as handle:
                preset = json.load(handle)
            if not preset.get("id"):
                preset["id"] = filename[:-5]
            presets.append(_preset_summary(preset))
        except Exception:
            continue
    return sorted(presets, key=lambda item: item.get("updated_at", ""), reverse=True)


def _load_board_preset(preset_id):
    path = _preset_path(preset_id)
    if not os.path.isfile(path):
        raise FileNotFoundError(preset_id)
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _delete_board_preset(preset_id):
    path = _preset_path(preset_id)
    if os.path.isfile(path):
        os.remove(path)
        return True
    return False


def _validation_report(assignments, duplicate_roles, ignored_count, decode_errors, module_warnings=None):
    lines = ["status: OK"]
    warnings = []
    if assignments.get("main_character") is None:
        warnings.append("Main Character A is empty.")
    for role in duplicate_roles:
        warnings.append(f"{role} has multiple cards; using the first one.")
    if decode_errors:
        warnings.append(f"{decode_errors} card(s) could not be decoded.")
    for module_warning in module_warnings or []:
        warnings.append(module_warning)
    if warnings:
        lines[0] = "status: CHECK"
    lines.append("roles:")
    for key, label in IMAGE_ROLE_DEFS:
        lines.append(f"- {label}: {'assigned' if assignments.get(key) is not None else 'empty'}")
    for key, label in AUDIO_ROLE_DEFS:
        lines.append(f"- {label}: {'assigned' if assignments.get(key) is not None else 'empty'}")
    lines.append(f"- Extra / Ignore: {ignored_count}")
    if warnings:
        lines.append("warnings:")
        lines += [f"- {warning}" for warning in warnings]
    return "\n".join(lines)


class ToobusyReferenceBoard:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "board_json": (
                    "STRING",
                    {
                        "default": json.dumps(DEFAULT_REFERENCE_BOARD, ensure_ascii=False),
                        "multiline": True,
                        "tooltip": "Serialized Reference Board state. The custom UI edits this field.",
                    },
                ),
            },
        }

    RETURN_TYPES = (
        "TOOBUSY_BUNDLE",
        "STRING",
        "STRING",
        "STRING",
    )
    RETURN_NAMES = (
        "toobusy_bundle",
        "global_note",
        "reference_manifest_json",
        "validation_report",
    )
    FUNCTION = "collect"
    CATEGORY = "toobusy/Plan"

    def collect(self, board_json):
        board = _parse_board(board_json)
        assignments = {key: None for key, _label in IMAGE_ROLE_DEFS}
        legacy_assignments = {key: None for key, _label in LEGACY_IMAGE_ROLES}
        audio_assignments = {key: None for key, _label in AUDIO_ROLE_DEFS}
        legacy_audio_assignments = {key: None for key, _label in (("audio_1", "Audio 1"), ("audio_2", "Audio 2"))}
        audio_durations = {key: 0.0 for key, _label in AUDIO_ROLE_DEFS}
        legacy_audio_durations = {"audio_1": 0.0, "audio_2": 0.0}
        bundle_roles = {key: None for key, _label in LEGACY_IMAGE_ROLES}
        manifest_items = []
        selected_card_items = []
        bundle_cards = []
        text_blocks = []
        selections = {}
        duplicate_roles = []
        ignored_count = 0
        decode_errors = 0
        module_warnings = []

        for item in board.get("items", []):
            if not isinstance(item, dict):
                continue
            if str(item.get("type") or "").strip().lower() == "text":
                # Text card: carries prompt intent/style/negative/custom text.
                text_value = str(item.get("text") or "").strip()
                if not text_value:
                    ignored_count += 1
                    continue
                category = str(item.get("text_category") or "goal").strip().lower()
                if category not in ("goal", "style", "negative", "custom"):
                    category = "custom"
                text_blocks.append({"category": category, "text": text_value})
                bundle_cards.append({
                    "id": str(item.get("id") or ""),
                    "type": "text",
                    "role": f"text_{category}",
                    "label": str(item.get("name") or category),
                    "category": category,
                    "text": text_value,
                    "prompt": text_value,
                })
                continue
            if str(item.get("type") or "").strip().lower() == "lora":
                # Independent LoRA card: no media, emit a Bundle LoRA card only
                # when it is enabled and names a file (mirrors face-LoRA logic;
                # downstream consumers do not check `enabled`).
                lora_name = str(item.get("lora_name") or "").strip()
                if not lora_name or not bool(item.get("lora_enabled", True)):
                    ignored_count += 1
                    continue
                try:
                    lora_strength = float(item.get("lora_strength", 1.0))
                except Exception:
                    lora_strength = 1.0
                card_id = str(item.get("id") or "")
                raw_role = str(item.get("role") or "lora").strip() or "lora"
                lora_role = raw_role if "lora" in raw_role else f"{raw_role}_lora"
                bundle_cards.append({
                    "id": card_id,
                    "type": "lora",
                    "role": lora_role,
                    "label": str(item.get("name") or lora_name),
                    "lora_name": lora_name,
                    "strength": lora_strength,
                    "enabled": True,
                    "metadata": {
                        "id": card_id,
                        "role": lora_role,
                        "type": "lora",
                        "lora_name": lora_name,
                        "strength": lora_strength,
                    },
                })
                continue
            role = _normalize_role(item.get("role"))
            if role in ("ignore", "extra"):
                ignored_count += 1
                continue
            if role in audio_assignments:
                audio, audio_meta = _filename_to_audio(item.get("filename"))
                if audio is None:
                    audio, audio_meta = _data_url_to_audio(item.get("src") or item.get("data_url"))
                if audio is None:
                    decode_errors += 1
                    manifest_items.append(_manifest_item(item, role, audio_meta or {}, "audio"))
                    continue
                processed_audio, actual_duration, processed_meta = _process_audio(audio, item)
                if processed_audio is None:
                    decode_errors += 1
                    manifest_items.append(_manifest_item(item, role, processed_meta or audio_meta or {}, "audio"))
                    continue
                merged_meta = {**(audio_meta or {}), **processed_meta}
                manifest = _manifest_item(item, role, merged_meta, "audio")
                manifest_items.append(manifest)
                if audio_assignments[role] is None:
                    audio_assignments[role] = processed_audio
                    audio_durations[role] = actual_duration
                    selected_card_items.append(manifest)
                    selections[role] = str(item.get("id") or "")
                    bundle_cards.append({
                        "id": str(item.get("id") or ""),
                        "type": "audio",
                        "role": role,
                        "label": str(item.get("name") or role),
                        "audio": processed_audio,
                        "audio_settings": {
                            "start_offset_seconds": merged_meta.get("start_offset_seconds", 0.0),
                            "duration_seconds": merged_meta.get("duration_seconds", actual_duration),
                            "actual_duration_seconds": merged_meta.get("actual_duration_seconds", actual_duration),
                            "end_mode": merged_meta.get("end_mode", "trim"),
                        },
                        "metadata": manifest,
                    })
                    legacy_audio_role = LEGACY_AUDIO_ROLE_MAP.get(role, role if role in legacy_audio_assignments else None)
                    if legacy_audio_role and legacy_audio_assignments.get(legacy_audio_role) is None:
                        legacy_audio_assignments[legacy_audio_role] = processed_audio
                        legacy_audio_durations[legacy_audio_role] = actual_duration
                elif role not in duplicate_roles:
                    duplicate_roles.append(role)
                continue
            if role not in assignments:
                ignored_count += 1
                continue

            image = _filename_to_pil(item.get("filename")) or _data_url_to_pil(item.get("src") or item.get("data_url"))
            tensor, size_meta = _prepare_image(image, item)
            if tensor is None:
                decode_errors += 1
                continue
            tensor, _module_warnings = _apply_card_processors(tensor, item)
            module_warnings.extend(_module_warnings)
            manifest = _manifest_item(item, role, size_meta, "image")
            manifest_items.append(manifest)
            if assignments[role] is None:
                assignments[role] = tensor
                selected_card_items.append(manifest)
                selections[role] = str(item.get("id") or "")
                role_payload = {
                    "image": tensor,
                    "id": str(item.get("id") or ""),
                    "name": str(item.get("name") or ""),
                    "note": str(item.get("note") or ""),
                    "width": size_meta.get("width") if size_meta else None,
                    "height": size_meta.get("height") if size_meta else None,
                    "filename": str(item.get("filename") or ""),
                }
                card_type = str(item.get("type") or CARD_TYPE_BY_ROLE.get(role) or "custom")
                bundle_cards.append({
                    "id": role_payload["id"],
                    "type": card_type,
                    "role": role,
                    "label": role_payload["name"] or role,
                    "image": tensor,
                    "prompt": str(item.get("note") or ""),
                    "metadata": manifest,
                })
                if card_type == "face" and item.get("face_lora_enabled") and str(item.get("face_lora_name") or "").strip():
                    try:
                        face_lora_strength = float(item.get("face_lora_strength", 1.0))
                    except Exception:
                        face_lora_strength = 1.0
                    lora_role = f"{role}_faceswap_lora"
                    bundle_cards.append({
                        "id": f"{role_payload['id']}_faceswap_lora",
                        "type": "lora",
                        "role": lora_role,
                        "label": f"{role_payload['name'] or role} FaceSwap LoRA",
                        "lora_name": str(item.get("face_lora_name") or "").strip(),
                        "strength": face_lora_strength,
                        "source_card_id": role_payload["id"],
                        "enabled": True,
                        "metadata": {
                            "role": lora_role,
                            "type": "lora",
                            "source_card_id": role_payload["id"],
                        },
                    })
                legacy_role = LEGACY_ROLE_MAP.get(role, role if role in legacy_assignments else None)
                if legacy_role and legacy_assignments.get(legacy_role) is None:
                    legacy_assignments[legacy_role] = tensor
                    bundle_roles[legacy_role] = dict(role_payload)
                if role in bundle_roles and bundle_roles.get(role) is None:
                    bundle_roles[role] = dict(role_payload)
            elif role not in duplicate_roles:
                duplicate_roles.append(role)

        global_note = str(board.get("global_note") or "")
        manifest = {
            "version": 1,
            "target_pixels": REFERENCE_TARGET_PIXELS,
            "resize_policy": "downscale only, preserve aspect ratio, lanczos, no upscale",
            "global_note": global_note,
            "items": manifest_items,
        }
        toobusy_bundle = {
            **bundle_roles,
            "version": 1,
            "bundle_type": "TOOBUSY_BUNDLE",
            "global_note": global_note,
            "cards": bundle_cards,
            "text_blocks": text_blocks,
            "selections": selections,
            "prompt_blocks": [],
            "resolved_prompt": "",
            "negative_prompt": "",
            "flags": {},
            "manifest": manifest,
        }
        validation_assignments = {**legacy_assignments, **legacy_audio_assignments}
        validation = _validation_report(validation_assignments, duplicate_roles, ignored_count, decode_errors, module_warnings)
        return (
            toobusy_bundle,
            global_note,
            json.dumps(manifest, ensure_ascii=False, indent=2),
            validation,
        )


NODE_CLASS_MAPPINGS = {
    "ToobusyReferenceBoard": ToobusyReferenceBoard,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ToobusyReferenceBoard": "toobusy Reference Board",
}

try:
    from aiohttp import web
    from server import PromptServer

    @PromptServer.instance.routes.post("/toobusy/reference_board/save_image")
    async def _toobusy_reference_board_save_image(request):
        payload = await request.json()
        saved = _save_reference_image_from_data_url(
            payload.get("src") or payload.get("data_url"),
            payload.get("name") or payload.get("source") or "reference",
        )
        if payload.get("original_width"):
            saved["original_width"] = int(payload.get("original_width"))
        if payload.get("original_height"):
            saved["original_height"] = int(payload.get("original_height"))
        saved["url"] = (
            f"/view?filename={saved['name']}"
            f"&subfolder={REFERENCE_IMAGE_SUBDIR}"
            "&type=input"
        )
        return web.json_response(saved)

    @PromptServer.instance.routes.post("/toobusy/reference_board/save_audio")
    async def _toobusy_reference_board_save_audio(request):
        payload = await request.json()
        saved = _save_reference_audio_from_data_url(
            payload.get("src") or payload.get("data_url"),
            payload.get("name") or payload.get("source") or "audio",
        )
        saved["url"] = (
            f"/view?filename={saved['name']}"
            f"&subfolder={REFERENCE_AUDIO_SUBDIR}"
            "&type=input"
        )
        return web.json_response(saved)

    @PromptServer.instance.routes.post("/toobusy/reference_board/save_preset")
    async def _toobusy_reference_board_save_preset(request):
        payload = await request.json()
        board = payload.get("board") if isinstance(payload.get("board"), dict) else {}
        summary = _save_board_preset(payload.get("name"), board)
        return web.json_response(summary)

    @PromptServer.instance.routes.get("/toobusy/reference_board/list_presets")
    async def _toobusy_reference_board_list_presets(_request):
        return web.json_response({"presets": _list_board_presets()})

    @PromptServer.instance.routes.get("/toobusy/reference_board/load_preset")
    async def _toobusy_reference_board_load_preset(request):
        preset = _load_board_preset(request.query.get("id", ""))
        return web.json_response(preset)

    @PromptServer.instance.routes.post("/toobusy/reference_board/delete_preset")
    async def _toobusy_reference_board_delete_preset(request):
        payload = await request.json()
        deleted = _delete_board_preset(payload.get("id", ""))
        return web.json_response({"deleted": deleted})
except Exception:
    pass

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
