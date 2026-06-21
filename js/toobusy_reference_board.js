import { app } from "../../scripts/app.js";

const TARGET_PIXELS = 1_000_000;
const CACHE_PIXELS = 1_080_000;
const NODE_SIZE = [560, 390];
const WIDGET_SIZE = [530, 302];

const ROLES = [
    ["character_a", "Character A"],
    ["character_b", "Character B"],
    ["character_c", "Character C"],
    ["character_d", "Character D"],
    ["face_a", "Face A"],
    ["face_b", "Face B"],
    ["outfit_a", "Outfit A"],
    ["outfit_b", "Outfit B"],
    ["pose_a", "Pose A"],
    ["background_a", "Background A"],
    ["style_a", "Style A"],
    ["prop_a", "Prop A"],
    ["audio_a", "Audio A"],
    ["audio_b", "Audio B"],
    ["main_character", "Main A"],
    ["secondary_character", "Character B"],
    ["pose", "Pose"],
    ["outfit", "Outfit"],
    ["background", "Background"],
    ["style", "Style"],
    ["product", "Product"],
    ["audio_1", "Audio 1"],
    ["audio_2", "Audio 2"],
    ["ignore", "Extra / Ignore"],
];

const AUDIO_ROLES = new Set(["audio_a", "audio_b", "audio_1", "audio_2", "ignore"]);

// Human label for any role key (modern or legacy), used by the node preview.
const ROLE_LABEL = Object.fromEntries(ROLES.map(([key, label]) => [key, label]));

// The overlay editor saves modern role keys (character_a, background_a, ...)
// while counts/validation think in the legacy 7-role vocabulary. Collapse both
// onto a single canonical key so the preview, counts, and warnings agree.
const ROLE_CANONICAL = {
    character_a: "main_character",
    main_character: "main_character",
    character_b: "secondary_character",
    secondary_character: "secondary_character",
    outfit_a: "outfit",
    outfit: "outfit",
    pose_a: "pose",
    pose: "pose",
    background_a: "background",
    background: "background",
    style_a: "style",
    style: "style",
    prop_a: "product",
    product: "product",
    audio_a: "audio_1",
    audio_1: "audio_1",
    audio_b: "audio_2",
    audio_2: "audio_2",
};

function canonicalRole(role) {
    const key = role || "ignore";
    return ROLE_CANONICAL[key] || key;
}

// LoRA file list for independent LoRA cards, pulled from the core LoraLoader
// node's COMBO definition and cached for the session.
let LORA_LIST_CACHE = null;
async function fetchLoraList() {
    if (LORA_LIST_CACHE) return LORA_LIST_CACHE;
    try {
        const resp = await fetch("/object_info/LoraLoader");
        if (resp.ok) {
            const info = await resp.json();
            const names = info?.LoraLoader?.input?.required?.lora_name?.[0];
            if (Array.isArray(names)) {
                LORA_LIST_CACHE = names;
                return names;
            }
        }
    } catch (err) {
        console.warn("[toobusy Reference Board] lora list fetch failed", err);
    }
    LORA_LIST_CACHE = [];
    return [];
}

const DEFAULT_BOARD = { version: 1, global_note: "", items: [] };

function cloneBoard(board) {
    return JSON.parse(JSON.stringify(board || DEFAULT_BOARD));
}

function findWidget(node, name) {
    return node.widgets?.find((widget) => widget.name === name);
}

function boardWidget(node) {
    return findWidget(node, "board_json");
}

function hideWidget(widget) {
    if (!widget) return;
    widget.type = "hidden";
    widget.computeSize = () => [0, -4];
    widget.hidden = true;
}

function parseBoard(node) {
    try {
        const parsed = JSON.parse(boardWidget(node)?.value || "");
        if (parsed && Array.isArray(parsed.items)) {
            return parsed;
        }
    } catch {}
    return structuredClone(DEFAULT_BOARD);
}

function syncBoard(node, board) {
    const widget = boardWidget(node);
    if (widget) {
        widget.value = JSON.stringify(board);
    }
    node.setDirtyCanvas?.(true, true);
}

function referenceViewUrl(item) {
    if (item?.preview_src) return item.preview_src;
    if (item?.src) return item.src;
    if (!item?.filename) return "";
    const raw = String(item.filename).replace(/\\/g, "/");
    const parts = raw.split("/");
    const filename = parts.pop() || "";
    const subfolder = parts.join("/");
    const query = new URLSearchParams({ filename, type: "input" });
    if (subfolder) query.set("subfolder", subfolder);
    return `/view?${query.toString()}`;
}

function isAudioItem(item) {
    return (item?.type || "image") === "audio";
}

function typeForRole(role, fallback = "image") {
    if (["audio_a", "audio_b", "audio_1", "audio_2"].includes(role)) return "audio";
    if (["character_a", "character_b", "character_c", "character_d", "main_character", "secondary_character"].includes(role)) return "character";
    if (["face_a", "face_b"].includes(role)) return "face";
    if (["outfit_a", "outfit_b", "outfit"].includes(role)) return "outfit";
    if (["pose_a", "pose"].includes(role)) return "pose";
    if (["background_a", "background"].includes(role)) return "background";
    if (["style_a", "style"].includes(role)) return "style";
    if (["prop_a", "product"].includes(role)) return "prop";
    return fallback;
}

function boardCounts(board) {
    const counts = Object.fromEntries(ROLES.map(([key]) => [key, 0]));
    for (const item of board.items || []) {
        const role = item.role || "ignore";
        // Count under both the raw role and its canonical alias so legacy
        // checks (main_character, background, ...) see modern cards too.
        counts[role] = (counts[role] || 0) + 1;
        const canon = canonicalRole(role);
        if (canon !== role) counts[canon] = (counts[canon] || 0) + 1;
    }
    return counts;
}

function statusLines(board) {
    const counts = boardCounts(board);
    return [
        `cards: ${(board.items || []).length}`,
        `Main A: ${counts.main_character ? "assigned" : "empty"}`,
        `B/Pose/Outfit/BG: ${counts.secondary_character || 0}/${counts.pose || 0}/${counts.outfit || 0}/${counts.background || 0}`,
        `Style/Product: ${counts.style || 0}/${counts.product || 0}`,
        `Audio 1/2: ${counts.audio_1 || 0}/${counts.audio_2 || 0}`,
    ];
}

function validationSummary(board) {
    const counts = boardCounts(board);
    if (!counts.main_character) return "Warning: Main A empty";
    const duplicate = ["main_character", "outfit", "pose", "background", "style", "product"].find((role) => counts[role] > 1);
    if (duplicate) return `Warning: ${duplicate} assigned twice`;
    return "OK";
}

function resizeDimensions(width, height, targetPixels = TARGET_PIXELS) {
    const pixels = width * height;
    if (pixels <= targetPixels) {
        return { width, height, resized: false };
    }
    const scale = Math.sqrt(targetPixels / pixels);
    return {
        width: Math.max(1, Math.round(width * scale)),
        height: Math.max(1, Math.round(height * scale)),
        resized: true,
    };
}

function imageFromBlob(blob) {
    return new Promise((resolve, reject) => {
        const url = URL.createObjectURL(blob);
        const img = new Image();
        img.onload = () => {
            URL.revokeObjectURL(url);
            resolve(img);
        };
        img.onerror = () => {
            URL.revokeObjectURL(url);
            reject(new Error("not an image"));
        };
        img.src = url;
    });
}

async function encodeImageBlob(blob) {
    const img = await imageFromBlob(blob);
    const originalWidth = img.naturalWidth || img.width;
    const originalHeight = img.naturalHeight || img.height;
    const cached = resizeDimensions(originalWidth, originalHeight, CACHE_PIXELS);
    const finalSize = resizeDimensions(originalWidth, originalHeight, TARGET_PIXELS);
    const canvas = document.createElement("canvas");
    canvas.width = cached.width;
    canvas.height = cached.height;
    const ctx = canvas.getContext("2d");
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = "high";
    ctx.drawImage(img, 0, 0, cached.width, cached.height);
    const src = canvas.toDataURL("image/jpeg", 0.9);
    const meta = {
        src,
        original_width: originalWidth,
        original_height: originalHeight,
        cache_width: cached.width,
        cache_height: cached.height,
        width: finalSize.width,
        height: finalSize.height,
        resize: finalSize.resized ? "1MP target" : "unchanged",
    };
    try {
        const response = await fetch("/toobusy/reference_board/save_image", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                src,
                name: blob.name || "reference",
                source: blob.type || "image",
                original_width: originalWidth,
                original_height: originalHeight,
            }),
        });
        if (response.ok) {
            const saved = await response.json();
            return {
                filename: saved.filename,
                preview_src: saved.url,
                original_width: saved.original_width || originalWidth,
                original_height: saved.original_height || originalHeight,
                cache_width: saved.width || cached.width,
                cache_height: saved.height || cached.height,
                width: saved.width || finalSize.width,
                height: saved.height || finalSize.height,
                resize: saved.resize || meta.resize,
            };
        }
    } catch (err) {
        console.warn("[toobusy Reference Board] cache save failed, embedding image in workflow", err);
    }
    return meta;
}

function readBlobAsDataUrl(blob) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result || ""));
        reader.onerror = () => reject(reader.error || new Error("read failed"));
        reader.readAsDataURL(blob);
    });
}

function audioDurationFromSrc(src) {
    return new Promise((resolve) => {
        if (!src) {
            resolve(null);
            return;
        }
        const audio = new Audio();
        audio.preload = "metadata";
        audio.onloadedmetadata = () => {
            resolve(Number.isFinite(audio.duration) ? audio.duration : null);
        };
        audio.onerror = () => resolve(null);
        audio.src = src;
    });
}

async function encodeAudioBlob(blob) {
    const src = await readBlobAsDataUrl(blob);
    const browserDuration = await audioDurationFromSrc(src);
    const meta = {
        type: "audio",
        src,
        mime: blob.type || "audio",
        bytes: blob.size || 0,
        duration_seconds: browserDuration || 0,
        start_offset_seconds: 0,
        end_mode: "trim",
    };
    try {
        const response = await fetch("/toobusy/reference_board/save_audio", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                src,
                name: blob.name || "audio",
                source: blob.type || "audio",
            }),
        });
        if (response.ok) {
            const saved = await response.json();
            return {
                ...meta,
                src: "",
                filename: saved.filename,
                preview_src: saved.url,
                mime: saved.mime || meta.mime,
                bytes: saved.bytes || meta.bytes,
                duration_seconds: saved.duration_seconds || meta.duration_seconds || 0,
                sample_rate: saved.sample_rate || null,
                channels: saved.channels || null,
                decode: saved.decode || "stored",
            };
        }
    } catch (err) {
        console.warn("[toobusy Reference Board] audio cache save failed, embedding audio in workflow", err);
    }
    return meta;
}

function stopOverlayEvents(root) {
    const stop = (event) => {
        event.stopPropagation();
    };
    [
        "pointerdown",
        "pointerup",
        "pointermove",
        "mousedown",
        "mouseup",
        "mousemove",
        "click",
        "dblclick",
        "contextmenu",
        "wheel",
        "keydown",
        "keyup",
        "keypress",
        "input",
        "change",
        "dragover",
        "dragleave",
        "drop",
        "paste",
    ].forEach((type) => {
        root.addEventListener(type, stop);
    });
}

function injectOverlayStyle() {
    if (document.getElementById("toobusy-reference-board-style")) return;
    const style = document.createElement("style");
    style.id = "toobusy-reference-board-style";
    style.textContent = `
        .toobusy-ref-overlay {
            position: fixed;
            inset: 0;
            z-index: 100000;
            display: grid;
            place-items: center;
            background: rgba(0, 0, 0, 0.48);
            color: #edf3f8;
            font: 12px/1.35 system-ui, -apple-system, "Segoe UI", sans-serif;
        }
        .toobusy-ref-overlay * { box-sizing: border-box; }
        .toobusy-ref-modal {
            width: min(1200px, 90vw);
            height: min(850px, 85vh);
            display: grid;
            grid-template-rows: auto auto minmax(0, 1fr) auto auto;
            gap: 10px;
            padding: 14px;
            border: 1px solid #344254;
            border-radius: 12px;
            background: #101821;
            box-shadow: 0 20px 80px rgba(0,0,0,0.55);
            overflow: hidden;
        }
        .toobusy-ref-head,
        .toobusy-ref-toolbar,
        .toobusy-ref-footer {
            display: flex;
            gap: 8px;
            align-items: center;
        }
        .toobusy-ref-save-state {
            margin-left: auto;
            color: #9fb0c3;
        }
        .toobusy-ref-head { justify-content: space-between; }
        .toobusy-ref-title { font-weight: 750; font-size: 15px; }
        .toobusy-ref-toolbar { flex-wrap: wrap; }
        .toobusy-ref-toolbar .tb-group {
            display: flex;
            gap: 6px;
            align-items: center;
            padding-right: 10px;
            margin-right: 4px;
            border-right: 1px solid #2a3744;
            flex-wrap: wrap;
        }
        .toobusy-ref-toolbar .tb-group:last-child { border-right: 0; padding-right: 0; margin-right: 0; }
        .toobusy-ref-toolbar .tb-right { margin-left: auto; }
        .toobusy-ref-overlay button.tb-primary {
            background: #2f6df6;
            border-color: #2f6df6;
            color: #fff;
            font-weight: 650;
        }
        .toobusy-ref-overlay button.tb-primary:hover { background: #4b82ff; }
        .toobusy-ref-overlay button,
        .toobusy-ref-overlay input,
        .toobusy-ref-overlay select,
        .toobusy-ref-overlay textarea {
            border: 1px solid #43556a;
            border-radius: 7px;
            background: #172332;
            color: #f2f7fb;
            font: inherit;
        }
        .toobusy-ref-overlay button {
            min-height: 30px;
            padding: 0 11px;
            cursor: pointer;
            background: #21334b;
        }
        .toobusy-ref-overlay button:hover { border-color: #80c7ff; }
        .toobusy-ref-url {
            width: min(360px, 42vw);
            min-height: 30px;
            padding: 0 8px;
        }
        .toobusy-ref-preset-name-input {
            width: min(260px, 32vw);
            min-height: 30px;
            padding: 0 8px;
        }
        .toobusy-ref-board {
            position: relative;
            overflow: auto;
            min-height: 0;
            border: 1px solid #2d3948;
            border-radius: 10px;
            background:
                linear-gradient(rgba(255,255,255,0.045) 1px, transparent 1px),
                linear-gradient(90deg, rgba(255,255,255,0.045) 1px, transparent 1px),
                #0b1118;
            background-size: 32px 32px;
        }
        .toobusy-ref-board.is-drop {
            outline: 2px solid #80c7ff;
            outline-offset: -4px;
        }
        .toobusy-ref-hint {
            position: absolute;
            inset: 0;
            display: grid;
            place-items: center;
            color: #8493a4;
            pointer-events: none;
            text-align: center;
        }
        .toobusy-ref-card {
            position: absolute;
            width: 184px;
            min-height: 256px;
            border: 1px solid #43556a;
            border-radius: 10px;
            background: rgba(20, 29, 39, 0.98);
            box-shadow: 0 14px 32px rgba(0,0,0,0.42);
            overflow: hidden;
        }
        .toobusy-ref-card-lora {
            min-height: 0;
            border-color: #5b4a8a;
        }
        .toobusy-ref-card-lora .toobusy-ref-card-title {
            cursor: grab;
        }
        .toobusy-ref-card-lora label {
            display: grid;
            gap: 3px;
            color: #9eabba;
            font-size: 11px;
        }
        .toobusy-ref-card-lora label.inline {
            display: flex;
            align-items: center;
            gap: 6px;
        }
        .toobusy-ref-card-lora input[type="number"] {
            width: 100%;
            min-height: 24px;
            padding: 0 6px;
        }
        .toobusy-ref-card-text {
            min-height: 0;
            border-color: #3f6b57;
        }
        .toobusy-ref-card-text .toobusy-ref-card-title {
            cursor: grab;
        }
        .toobusy-ref-card-text label {
            display: grid;
            gap: 3px;
            color: #9eabba;
            font-size: 11px;
        }
        .toobusy-ref-card-text .text-content {
            width: 100%;
            height: 84px;
            padding: 6px;
            resize: vertical;
            user-select: text;
        }
        .text-insert-row {
            display: flex;
            flex-wrap: wrap;
            gap: 4px;
        }
        .text-insert-chip {
            cursor: pointer;
            border: 1px solid #3f6b57;
            background: rgba(63, 107, 87, 0.25);
            color: #cfe6da;
            border-radius: 10px;
            padding: 1px 7px;
            font-size: 10px;
            user-select: none;
            white-space: nowrap;
        }
        .text-insert-chip:hover { background: #3f6b57; color: #fff; }
        .text-insert-empty { font-size: 10px; color: #647386; }
        .toobusy-ref-thumb {
            width: 100%;
            height: 120px;
            display: block;
            object-fit: cover;
            background: #05080b;
            cursor: grab;
        }
        .toobusy-ref-card.toobusy-ref-card-drop {
            outline: 2px dashed #6aa9ff;
            outline-offset: -2px;
        }
        .toobusy-ref-audio-thumb {
            width: 100%;
            height: 120px;
            display: grid;
            align-content: center;
            gap: 8px;
            padding: 12px;
            background: linear-gradient(135deg, #0b1824, #172332);
            border-bottom: 1px solid #29394b;
            cursor: grab;
        }
        .toobusy-ref-audio-title {
            font-weight: 800;
            color: #9bd4ff;
        }
        .toobusy-ref-audio-wave {
            height: 30px;
            border-radius: 6px;
            background:
                linear-gradient(90deg, rgba(126,210,255,0.2), rgba(126,210,255,0.7), rgba(126,210,255,0.2)),
                repeating-linear-gradient(90deg, transparent 0 8px, rgba(255,255,255,0.16) 8px 10px);
        }
        .toobusy-ref-audio-options {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 6px;
        }
        .toobusy-ref-audio-options[hidden] {
            display: none !important;
        }
        .toobusy-ref-audio-options label {
            display: grid;
            gap: 3px;
            color: #9eabba;
            font-size: 11px;
        }
        .toobusy-ref-audio-options input,
        .toobusy-ref-audio-options select,
        .toobusy-ref-audio-player {
            width: 100%;
        }
        .toobusy-ref-face-lora-options {
            display: grid;
            gap: 6px;
            padding: 7px;
            border: 1px solid #2f4155;
            border-radius: 8px;
            background: rgba(10, 18, 26, 0.62);
        }
        .toobusy-ref-face-lora-options[hidden] {
            display: none !important;
        }
        .toobusy-ref-face-lora-options label {
            display: grid;
            gap: 3px;
            color: #9eabba;
            font-size: 11px;
        }
        .toobusy-ref-face-lora-options .inline {
            display: flex;
            align-items: center;
            gap: 6px;
        }
        .toobusy-ref-face-lora-options select,
        .toobusy-ref-face-lora-options input[type="text"],
        .toobusy-ref-face-lora-options input[type="number"] {
            width: 100%;
            min-height: 24px;
            padding: 0 6px;
        }
        .toobusy-ref-modules {
            display: grid;
            gap: 6px;
            padding: 7px;
            border: 1px solid #2f4155;
            border-radius: 8px;
            background: rgba(10, 18, 26, 0.62);
        }
        .toobusy-ref-modules[hidden] { display: none !important; }
        .toobusy-ref-modules-title {
            font-size: 10px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: #8fa1b3;
        }
        .toobusy-ref-module[hidden] { display: none !important; }
        .toobusy-ref-module {
            padding: 6px 7px;
            border-radius: 6px;
            background: rgba(255, 255, 255, 0.03);
        }
        .toobusy-ref-module + .toobusy-ref-module { margin-top: 6px; }
        .toobusy-ref-module .module-row {
            display: flex;
            flex-direction: column;
            gap: 5px;
        }
        .toobusy-ref-module .inline {
            display: flex;
            align-items: center;
            gap: 6px;
            color: #cfd9e5;
            font-size: 12px;
            white-space: nowrap;
            cursor: pointer;
        }
        .toobusy-ref-module .inline input { flex: 0 0 auto; }
        .toobusy-ref-module .module-body {
            display: grid;
            gap: 4px;
            margin-top: 4px;
            padding-left: 4px;
        }
        .toobusy-ref-module .module-body[hidden] { display: none !important; }
        .toobusy-ref-module .module-body label {
            display: grid;
            gap: 3px;
            color: #9eabba;
            font-size: 11px;
        }
        .toobusy-ref-module .module-body select,
        .toobusy-ref-module .module-body input[type="number"] {
            width: 100%;
            min-height: 24px;
            padding: 0 6px;
        }
        .toobusy-ref-audio-player {
            height: 30px;
            grid-column: 1 / -1;
        }
        .toobusy-ref-card-body {
            display: grid;
            gap: 6px;
            padding: 8px;
        }
        .toobusy-ref-card-title {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 8px;
            font-weight: 700;
            color: #cfd9e5;
        }
        .toobusy-ref-remove {
            min-height: 22px;
            padding: 0 7px;
            color: #ffd6d6;
            background: #43252b;
        }
        .toobusy-ref-card select,
        .toobusy-ref-card textarea {
            width: 100%;
        }
        .toobusy-ref-card select {
            min-height: 28px;
            padding: 0 6px;
        }
        .toobusy-ref-card textarea {
            height: 44px;
            padding: 6px;
            resize: none;
            user-select: text;
        }
        .toobusy-ref-meta {
            min-height: 30px;
            color: #8d9aaa;
            font-size: 11px;
        }
        .toobusy-ref-global {
            flex: 1 1 auto;
            min-height: 58px;
            padding: 7px;
            resize: none;
            user-select: text;
        }
        .toobusy-ref-status {
            width: 270px;
            min-height: 58px;
            padding: 7px;
            border: 1px solid #2f3b49;
            border-radius: 8px;
            background: #0c1219;
            color: #aebac7;
            white-space: pre-line;
        }
        .toobusy-ref-library {
            display: none;
            max-height: 190px;
            overflow: auto;
            border: 1px solid #2d3948;
            border-radius: 10px;
            background: #0b1118;
            padding: 8px;
        }
        .toobusy-ref-library.is-open { display: grid; gap: 7px; }
        .toobusy-ref-preset {
            display: grid;
            grid-template-columns: minmax(0, 1fr) auto auto;
            gap: 8px;
            align-items: center;
            padding: 7px;
            border: 1px solid #2f3b49;
            border-radius: 8px;
            background: #111b25;
        }
        .toobusy-ref-preset-name {
            font-weight: 700;
            color: #dce7f0;
            overflow: hidden;
            white-space: nowrap;
            text-overflow: ellipsis;
        }
        .toobusy-ref-preset-meta {
            color: #8e9cab;
            font-size: 11px;
        }
        .toobusy-ref-launcher {
            width: 100%;
            min-height: 292px;
            padding: 10px;
            display: grid;
            grid-template-rows: auto auto minmax(0, 1fr) auto auto;
            gap: 8px;
            border: 1px solid #303946;
            border-radius: 9px;
            background: #111820;
            color: #dbe5ee;
            font: 12px/1.35 system-ui, -apple-system, "Segoe UI", sans-serif;
            overflow: hidden;
        }
        .toobusy-ref-launcher button {
            min-height: 30px;
            border: 1px solid #43556a;
            border-radius: 7px;
            background: #21334b;
            color: #f2f7fb;
            cursor: pointer;
            font: inherit;
        }
        .toobusy-ref-launcher .topline {
            display: flex;
            gap: 8px;
            align-items: center;
        }
        .toobusy-ref-launcher .badge {
            padding: 3px 7px;
            border-radius: 999px;
            background: #0d253a;
            color: #9bd4ff;
            border: 1px solid #2c5570;
            white-space: nowrap;
        }
        .toobusy-ref-launcher .summary {
            color: #aeb9c6;
            white-space: pre-line;
        }
        .toobusy-ref-mini-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 6px;
        }
        .toobusy-ref-slot {
            min-width: 0;
            display: grid;
            grid-template-columns: 46px minmax(0, 1fr);
            gap: 6px;
            align-items: center;
            padding: 5px;
            border: 1px solid #2f3b49;
            border-radius: 8px;
            background: #0c1219;
        }
        .toobusy-ref-slot-placeholder {
            grid-column: 1 / -1;
            display: block;
            color: #647386;
            font-size: 11px;
            text-align: center;
            padding: 12px 6px;
        }
        .toobusy-ref-slot img,
        .toobusy-ref-empty-thumb {
            width: 46px;
            height: 46px;
            border-radius: 6px;
            object-fit: cover;
            background: #18212b;
            border: 1px solid #334153;
        }
        .toobusy-ref-empty-thumb {
            display: grid;
            place-items: center;
            color: #647386;
        }
        .toobusy-ref-slot-label {
            overflow: hidden;
            white-space: nowrap;
            text-overflow: ellipsis;
            color: #cfd9e5;
            font-weight: 650;
        }
        .toobusy-ref-slot-name {
            overflow: hidden;
            white-space: nowrap;
            text-overflow: ellipsis;
            color: #8e9cab;
            font-size: 11px;
        }
        .toobusy-ref-note-preview,
        .toobusy-ref-validation-preview {
            overflow: hidden;
            white-space: nowrap;
            text-overflow: ellipsis;
            color: #aeb9c6;
        }
        .toobusy-ref-slot { cursor: zoom-in; }
        .toobusy-ref-hover-preview {
            position: fixed;
            z-index: 100000;
            pointer-events: none;
            background: rgba(12, 18, 26, 0.97);
            border: 1px solid #3a4a5c;
            border-radius: 10px;
            padding: 6px;
            box-shadow: 0 18px 48px rgba(0, 0, 0, 0.55);
            max-width: 380px;
        }
        .toobusy-ref-hover-preview img {
            display: block;
            max-width: 360px;
            max-height: 360px;
            border-radius: 6px;
            object-fit: contain;
        }
        .toobusy-ref-hover-preview .hp-title {
            font-size: 11px;
            color: #9fb0c2;
            margin-bottom: 4px;
        }
        .toobusy-ref-hover-preview .hp-text {
            font-size: 12px;
            color: #e6edf5;
            white-space: pre-wrap;
            max-width: 360px;
        }
    `;
    document.head.appendChild(style);
}

function attachCardDrag(card, dragTarget, item, sync) {
    let drag = null;
    dragTarget.addEventListener("pointerdown", (event) => {
        if (event.target.closest("button, select, input, textarea")) return;
        drag = {
            startX: event.clientX,
            startY: event.clientY,
            originX: Number(item.x) || 0,
            originY: Number(item.y) || 0,
        };
        dragTarget.setPointerCapture?.(event.pointerId);
    });
    dragTarget.addEventListener("pointermove", (event) => {
        if (!drag) return;
        item.x = Math.max(0, drag.originX + event.clientX - drag.startX);
        item.y = Math.max(0, drag.originY + event.clientY - drag.startY);
        card.style.left = `${item.x}px`;
        card.style.top = `${item.y}px`;
        sync();
    });
    dragTarget.addEventListener("pointerup", () => {
        drag = null;
    });
}

function buildLoraCard(card, item, board, area, hint, sync) {
    card.classList.add("toobusy-ref-card-lora");
    card.innerHTML = `
        <div class="toobusy-ref-card-body">
            <div class="toobusy-ref-card-title"><span></span><button class="toobusy-ref-remove" title="Remove">x</button></div>
            <label class="inline"><input class="lora-enable" type="checkbox"> Enabled</label>
            <label>LoRA file
                <select class="lora-name"></select>
            </label>
            <label>Strength
                <input class="lora-strength" type="number" step="0.05" value="1">
            </label>
            <div class="toobusy-ref-meta">Independent LoRA card → added to the Bundle LoRA list.</div>
        </div>
    `;
    const titleSpan = card.querySelector(".toobusy-ref-card-title span");
    const enable = card.querySelector(".lora-enable");
    const select = card.querySelector(".lora-name");
    const strength = card.querySelector(".lora-strength");
    titleSpan.textContent = item.lora_name || item.name || "LoRA";
    enable.checked = item.lora_enabled !== false;
    strength.value = Number(item.lora_strength ?? 1);

    const ensureOption = (value) => {
        if (value && ![...select.options].some((opt) => opt.value === value)) {
            const opt = document.createElement("option");
            opt.value = value;
            opt.textContent = value;
            select.appendChild(opt);
        }
    };
    const placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.textContent = "(select LoRA)";
    select.appendChild(placeholder);
    ensureOption(item.lora_name || "");
    select.value = item.lora_name || "";
    fetchLoraList().then((names) => {
        for (const name of names) ensureOption(name);
        select.value = item.lora_name || "";
    });

    enable.addEventListener("change", () => {
        item.lora_enabled = enable.checked;
        sync();
    });
    select.addEventListener("change", () => {
        item.lora_name = select.value;
        titleSpan.textContent = item.lora_name || "LoRA";
        sync();
    });
    strength.addEventListener("input", () => {
        item.lora_strength = Number(strength.value || 1);
        sync();
    });
    card.querySelector(".toobusy-ref-remove").addEventListener("click", () => {
        const index = board.items.indexOf(item);
        if (index >= 0) board.items.splice(index, 1);
        card.remove();
        hint.style.display = board.items.length ? "none" : "";
        sync();
    });

    attachCardDrag(card, card.querySelector(".toobusy-ref-card-title"), item, sync);
    area.appendChild(card);
    hint.style.display = board.items.length ? "none" : "";
    return card;
}

const TEXT_CATEGORY_OPTIONS = [
    ["goal", "Goal (intent)"],
    ["style", "Style"],
    ["negative", "Negative"],
    ["custom", "Custom"],
];

// Canonical token a text card inserts for each reference role. Matches the
// Director button labels so the LLM correlates "Character A" in the text with
// the selected Character A reference.
const INSERT_TOKEN_LABEL = {
    character_a: "Character A",
    character_b: "Character B",
    character_c: "Character C",
    character_d: "Character D",
    main_character: "Character A",
    secondary_character: "Character B",
    face_a: "Face A",
    face_b: "Face B",
    outfit_a: "Outfit A",
    outfit_b: "Outfit B",
    outfit: "Outfit",
    pose_a: "Pose",
    pose: "Pose",
    background_a: "Background",
    background: "Background",
    style_a: "Style",
    style: "Style",
    prop_a: "Prop",
    product: "Prop",
};

function boardReferenceTokens(board) {
    const seenLabel = new Set();
    const tokens = [];
    for (const it of board.items || []) {
        const role = it?.role;
        if (!role) continue;
        if ((it.type || "") === "text" || (it.type || "") === "lora") continue;
        const label = INSERT_TOKEN_LABEL[role];
        if (!label || seenLabel.has(label)) continue;
        seenLabel.add(label);
        tokens.push(label);
    }
    return tokens;
}

function insertAtCursor(textarea, text) {
    const start = textarea.selectionStart ?? textarea.value.length;
    const end = textarea.selectionEnd ?? textarea.value.length;
    const before = textarea.value.slice(0, start);
    const after = textarea.value.slice(end);
    const needSpace = before && !/\s$/.test(before);
    const ins = (needSpace ? " " : "") + text + " ";
    textarea.value = before + ins + after;
    const pos = (before + ins).length;
    try {
        textarea.setSelectionRange(pos, pos);
    } catch {}
    textarea.focus();
}

function buildTextCard(card, item, board, area, hint, sync) {
    card.classList.add("toobusy-ref-card-text");
    card.innerHTML = `
        <div class="toobusy-ref-card-body">
            <div class="toobusy-ref-card-title"><span></span><button class="toobusy-ref-remove" title="Remove">x</button></div>
            <label>Category
                <select class="text-category">
                    ${TEXT_CATEGORY_OPTIONS.map(([value, label]) => `<option value="${value}">${label}</option>`).join("")}
                </select>
            </label>
            <div class="text-insert-row"></div>
            <textarea class="text-content" placeholder="prompt text (Goal = scene intent, Style/Negative/Custom feed those blocks)..."></textarea>
            <div class="toobusy-ref-meta">Text card → Director composes this by category. Click a chip to insert its name.</div>
        </div>
    `;
    const titleSpan = card.querySelector(".toobusy-ref-card-title span");
    const category = card.querySelector(".text-category");
    const content = card.querySelector(".text-content");
    const insertRow = card.querySelector(".text-insert-row");
    category.value = item.text_category || "goal";
    content.value = item.text || "";

    const renderInsertChips = () => {
        const tokens = boardReferenceTokens(board);
        if (!tokens.length) {
            insertRow.innerHTML = `<span class="text-insert-empty">Add reference cards to insert their names</span>`;
            return;
        }
        insertRow.innerHTML = tokens
            .map((token) => `<span class="text-insert-chip">${token}</span>`)
            .join("");
        insertRow.querySelectorAll(".text-insert-chip").forEach((chip) =>
            chip.addEventListener("click", () => {
                insertAtCursor(content, chip.textContent);
                item.text = content.value;
                sync();
            }),
        );
    };
    renderInsertChips();
    // Refresh chips when focusing the field so newly added cards show up.
    content.addEventListener("focus", renderInsertChips);
    const labelFor = (value) => (TEXT_CATEGORY_OPTIONS.find(([key]) => key === value) || ["", value])[1].split(" ")[0];
    const refreshTitle = () => {
        titleSpan.textContent = `Text · ${labelFor(category.value)}`;
    };
    refreshTitle();
    category.addEventListener("change", () => {
        item.text_category = category.value;
        refreshTitle();
        sync();
    });
    content.addEventListener("input", () => {
        item.text = content.value;
        sync();
    });
    card.querySelector(".toobusy-ref-remove").addEventListener("click", () => {
        const index = board.items.indexOf(item);
        if (index >= 0) board.items.splice(index, 1);
        card.remove();
        hint.style.display = board.items.length ? "none" : "";
        sync();
    });
    attachCardDrag(card, card.querySelector(".toobusy-ref-card-title"), item, sync);
    area.appendChild(card);
    hint.style.display = board.items.length ? "none" : "";
    return card;
}

function pickImageFile(onBlob) {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = "image/*";
    input.style.display = "none";
    input.addEventListener("change", () => {
        const file = input.files && input.files[0];
        if (file) onBlob(file);
        input.remove();
    });
    document.body.appendChild(input);
    input.click();
}

function createCardElement(item, board, area, hint, sync) {
    const card = document.createElement("div");
    card.className = "toobusy-ref-card";
    card.dataset.id = item.id;
    card.style.left = `${Number(item.x) || 24}px`;
    card.style.top = `${Number(item.y) || 24}px`;
    if ((item.type || "") === "lora") {
        return buildLoraCard(card, item, board, area, hint, sync);
    }
    if ((item.type || "") === "text") {
        return buildTextCard(card, item, board, area, hint, sync);
    }
    const isAudio = isAudioItem(item);
    card.innerHTML = `
        <div class="toobusy-ref-thumb-root"></div>
        <div class="toobusy-ref-card-body">
            <div class="toobusy-ref-card-title"><span></span><button class="toobusy-ref-remove" title="Remove">x</button></div>
            <select></select>
            <textarea placeholder="note..."></textarea>
            <div class="toobusy-ref-face-lora-options" hidden>
                <label class="inline">
                    <input class="face-lora-enable" type="checkbox">
                    Attach FaceSwap LoRA
                </label>
                <label>LoRA file
                    <select class="face-lora-name"></select>
                </label>
                <label>Strength
                    <input class="face-lora-strength" type="number" step="0.05" value="1">
                </label>
            </div>
            <div class="toobusy-ref-modules" ${isAudio ? "hidden" : ""}>
                <div class="toobusy-ref-modules-title">Modules</div>
                <div class="toobusy-ref-module module-face-erase" hidden>
                    <div class="module-row">
                        <label class="inline" title="For the BODY card: remove its face so a new face can be composited in.">
                            <input class="face-erase-enable" type="checkbox"> Erase Face
                        </label>
                        <label class="inline" title="For the FACE-SOURCE card: keep only the face, remove the rest.">
                            <input class="face-keep-enable" type="checkbox"> Keep Face Only
                        </label>
                    </div>
                    <div class="module-body face-mask-body" hidden>
                        <label>Fill
                            <select class="face-erase-fill">
                                <option value="gray">gray</option>
                                <option value="black">black</option>
                                <option value="white">white</option>
                            </select>
                        </label>
                        <label>Expand
                            <input class="face-erase-expand" type="number" min="0" step="1" value="8">
                        </label>
                        <label>Feather
                            <input class="face-erase-feather" type="number" min="0" step="1" value="6">
                        </label>
                    </div>
                </div>
                <div class="toobusy-ref-module module-bg-remove">
                    <label class="inline">
                        <input class="bg-remove-enable" type="checkbox">
                        Remove Background
                    </label>
                    <div class="module-body bg-remove-body" hidden>
                        <label>Model
                            <select class="bg-remove-model">
                                <option value="u2net">u2net</option>
                                <option value="u2netp">u2netp</option>
                                <option value="isnet-general-use">isnet-general-use</option>
                                <option value="isnet-anime">isnet-anime</option>
                                <option value="silueta">silueta</option>
                                <option value="birefnet-general">birefnet-general</option>
                            </select>
                        </label>
                        <label>Background
                            <select class="bg-remove-background">
                                <option value="white">white</option>
                                <option value="black">black</option>
                                <option value="green">green</option>
                                <option value="gray">gray</option>
                                <option value="magenta">magenta</option>
                            </select>
                        </label>
                    </div>
                </div>
            </div>
            <div class="toobusy-ref-audio-options" ${isAudio ? "" : "hidden"}>
                <label>Start
                    <input class="audio-start" type="number" min="0" step="0.1">
                </label>
                <label>Duration
                    <input class="audio-duration" type="number" min="0" step="0.1">
                </label>
                <label>End mode
                    <select class="audio-end-mode">
                        <option value="trim">trim</option>
                        <option value="pad_silence">pad_silence</option>
                        <option value="loop">loop</option>
                    </select>
                </label>
                <audio class="toobusy-ref-audio-player" controls preload="metadata"></audio>
            </div>
            <div class="toobusy-ref-meta"></div>
        </div>
    `;
    const thumbRoot = card.querySelector(".toobusy-ref-thumb-root");
    let dragTarget = null;
    if (isAudio) {
        thumbRoot.className = "toobusy-ref-audio-thumb";
        thumbRoot.innerHTML = `
            <div class="toobusy-ref-audio-title">AUDIO</div>
            <div class="toobusy-ref-audio-wave"></div>
            <div>${item.mime || item.source || "audio"}</div>
        `;
        dragTarget = thumbRoot;
        const player = card.querySelector(".toobusy-ref-audio-player");
        player.src = referenceViewUrl(item);
        const startInput = card.querySelector(".audio-start");
        const durationInput = card.querySelector(".audio-duration");
        const endMode = card.querySelector(".audio-end-mode");
        startInput.value = Number(item.start_offset_seconds || 0);
        durationInput.value = Number(item.duration_seconds || 0);
        endMode.value = item.end_mode || "trim";
        startInput.addEventListener("input", () => {
            item.start_offset_seconds = Number(startInput.value || 0);
            sync();
        });
        durationInput.addEventListener("input", () => {
            item.duration_seconds = Number(durationInput.value || 0);
            sync();
        });
        endMode.addEventListener("change", () => {
            item.end_mode = endMode.value;
            sync();
        });
    } else {
        const img = document.createElement("img");
        img.className = "toobusy-ref-thumb";
        img.draggable = false;
        img.src = referenceViewUrl(item);
        thumbRoot.replaceWith(img);
        dragTarget = img;
    }
    card.querySelector(".toobusy-ref-card-title span").textContent = item.name || item.id || "reference";

    const select = card.querySelector("select");
    for (const [value, label] of ROLES) {
        if (isAudio && !AUDIO_ROLES.has(value)) continue;
        if (!isAudio && AUDIO_ROLES.has(value) && value !== "ignore") continue;
        const opt = document.createElement("option");
        opt.value = value;
        opt.textContent = label;
        select.appendChild(opt);
    }
    select.value = item.role || "ignore";
    const faceLoraOptions = card.querySelector(".toobusy-ref-face-lora-options");
    const faceLoraEnable = card.querySelector(".face-lora-enable");
    const faceLoraName = card.querySelector(".face-lora-name");
    const faceLoraStrength = card.querySelector(".face-lora-strength");
    const updateFaceLoraVisibility = () => {
        faceLoraOptions.hidden = typeForRole(item.role, item.type || "image") !== "face";
    };
    faceLoraEnable.checked = Boolean(item.face_lora_enabled);
    faceLoraStrength.value = Number(item.face_lora_strength ?? 1);
    // Populate the LoRA file dropdown from the local lora list (same source as
    // the independent LoRA card), keeping the current value selectable.
    const ensureFaceLoraOption = (value) => {
        if (value && ![...faceLoraName.options].some((opt) => opt.value === value)) {
            const opt = document.createElement("option");
            opt.value = value;
            opt.textContent = value;
            faceLoraName.appendChild(opt);
        }
    };
    const faceLoraPlaceholder = document.createElement("option");
    faceLoraPlaceholder.value = "";
    faceLoraPlaceholder.textContent = "(select LoRA)";
    faceLoraName.appendChild(faceLoraPlaceholder);
    ensureFaceLoraOption(item.face_lora_name || "");
    faceLoraName.value = item.face_lora_name || "";
    fetchLoraList().then((names) => {
        for (const name of names) ensureFaceLoraOption(name);
        faceLoraName.value = item.face_lora_name || "";
    });
    faceLoraEnable.addEventListener("change", () => {
        item.face_lora_enabled = faceLoraEnable.checked;
        sync();
    });
    faceLoraName.addEventListener("change", () => {
        item.face_lora_name = faceLoraName.value;
        sync();
    });
    faceLoraStrength.addEventListener("input", () => {
        item.face_lora_strength = Number(faceLoraStrength.value || 1);
        sync();
    });

    // Attachable card modules: Erase Face / Keep Face Only (character/face) + Remove Background (any image).
    const faceEraseModule = card.querySelector(".module-face-erase");
    const faceEraseEnable = card.querySelector(".face-erase-enable");
    const faceKeepEnable = card.querySelector(".face-keep-enable");
    const faceMaskBody = card.querySelector(".face-mask-body");
    const faceEraseFill = card.querySelector(".face-erase-fill");
    const faceEraseExpand = card.querySelector(".face-erase-expand");
    const faceEraseFeather = card.querySelector(".face-erase-feather");
    const bgRemoveEnable = card.querySelector(".bg-remove-enable");
    const bgRemoveBody = card.querySelector(".bg-remove-body");
    const bgRemoveModel = card.querySelector(".bg-remove-model");
    const bgRemoveBackground = card.querySelector(".bg-remove-background");
    if (faceEraseModule) {
        faceEraseEnable.checked = Boolean(item.face_erase_enabled);
        faceKeepEnable.checked = Boolean(item.face_keep_enabled);
        faceEraseFill.value = item.face_erase_fill || "gray";
        faceEraseExpand.value = Number(item.face_erase_expand ?? 8);
        faceEraseFeather.value = Number(item.face_erase_feather ?? 6);
        const updateFaceMaskBody = () => {
            faceMaskBody.hidden = !(faceEraseEnable.checked || faceKeepEnable.checked);
        };
        updateFaceMaskBody();
        bgRemoveEnable.checked = Boolean(item.bg_remove_enabled);
        bgRemoveModel.value = item.bg_remove_model || "u2net";
        bgRemoveBackground.value = item.bg_remove_background || "white";
        bgRemoveBody.hidden = !bgRemoveEnable.checked;
        faceEraseEnable.addEventListener("change", () => {
            item.face_erase_enabled = faceEraseEnable.checked;
            if (faceEraseEnable.checked) {  // erase and keep are mutually exclusive
                faceKeepEnable.checked = false;
                item.face_keep_enabled = false;
            }
            updateFaceMaskBody();
            sync();
        });
        faceKeepEnable.addEventListener("change", () => {
            item.face_keep_enabled = faceKeepEnable.checked;
            if (faceKeepEnable.checked) {
                faceEraseEnable.checked = false;
                item.face_erase_enabled = false;
            }
            updateFaceMaskBody();
            sync();
        });
        faceEraseFill.addEventListener("change", () => { item.face_erase_fill = faceEraseFill.value; sync(); });
        faceEraseExpand.addEventListener("input", () => { item.face_erase_expand = Number(faceEraseExpand.value || 0); sync(); });
        faceEraseFeather.addEventListener("input", () => { item.face_erase_feather = Number(faceEraseFeather.value || 0); sync(); });
        bgRemoveEnable.addEventListener("change", () => {
            item.bg_remove_enabled = bgRemoveEnable.checked;
            bgRemoveBody.hidden = !bgRemoveEnable.checked;
            sync();
        });
        bgRemoveModel.addEventListener("change", () => { item.bg_remove_model = bgRemoveModel.value; sync(); });
        bgRemoveBackground.addEventListener("change", () => { item.bg_remove_background = bgRemoveBackground.value; sync(); });
    }
    const updateModuleVisibility = () => {
        if (!faceEraseModule) return;
        const t = typeForRole(item.role, item.type || "image");
        faceEraseModule.hidden = !(t === "character" || t === "face");
    };

    updateFaceLoraVisibility();
    updateModuleVisibility();
    select.addEventListener("change", () => {
        item.role = select.value;
        item.type = typeForRole(item.role, item.type || "image");
        updateFaceLoraVisibility();
        updateModuleVisibility();
        sync();
    });

    const note = card.querySelector("textarea");
    note.value = item.note || "";
    note.addEventListener("input", () => {
        item.note = note.value;
        sync();
    });

    card.querySelector(".toobusy-ref-remove").addEventListener("click", () => {
        const index = board.items.indexOf(item);
        if (index >= 0) board.items.splice(index, 1);
        card.remove();
        hint.style.display = board.items.length ? "none" : "";
        sync();
    });

    card.querySelector(".toobusy-ref-meta").textContent = isAudio
        ? `duration ${Number(item.duration_seconds || 0).toFixed(2)}s · start ${Number(item.start_offset_seconds || 0).toFixed(2)}s\n${item.decode || item.mime || item.source}`
        : `original ${item.original_width}x${item.original_height}\nresized ${item.width}x${item.height} · ${item.source}`;

    // Replace just this card's image while keeping all settings (role, note,
    // modules, lora). Click the thumbnail to pick a file, or drop an image on it.
    if (!isAudio) {
        const replaceCardImage = async (blob, source) => {
            try {
                const encoded = await encodeImageBlob(blob);
                for (const key of ["filename", "src", "data_url", "preview_src"]) delete item[key];
                Object.assign(item, encoded);
                item.source = source;
                const imgEl = card.querySelector(".toobusy-ref-thumb");
                if (imgEl) imgEl.src = referenceViewUrl(item);
                card.querySelector(".toobusy-ref-meta").textContent =
                    `original ${item.original_width}x${item.original_height}\nresized ${item.width}x${item.height} · ${item.source}`;
                sync();
            } catch (err) {
                console.warn("[toobusy Reference Board] image replace failed", err);
            }
        };
        const thumbImg = card.querySelector(".toobusy-ref-thumb");
        if (thumbImg) {
            thumbImg.style.cursor = "pointer";
            thumbImg.title = "Click to load a new image (keeps settings), or drop an image here";
            thumbImg.addEventListener("click", () => {
                if (card._toobusySuppressClick) {
                    card._toobusySuppressClick = false;
                    return;
                }
                pickImageFile((file) => replaceCardImage(file, "replace"));
            });
        }
        card.addEventListener("dragover", (event) => {
            if (!event.dataTransfer) return;
            event.preventDefault();
            event.stopPropagation();
            card.classList.add("toobusy-ref-card-drop");
        });
        card.addEventListener("dragleave", () => card.classList.remove("toobusy-ref-card-drop"));
        card.addEventListener("drop", async (event) => {
            event.preventDefault();
            event.stopPropagation(); // keep the board from adding a new card
            card.classList.remove("toobusy-ref-card-drop");
            const file = [...(event.dataTransfer?.files || [])].find((f) => f.type.startsWith("image/"));
            if (file) {
                await replaceCardImage(file, "drop");
                return;
            }
            const url = event.dataTransfer?.getData("text/uri-list") || event.dataTransfer?.getData("text/plain");
            if (url) {
                try {
                    const response = await fetch(url.split("\n")[0].trim());
                    await replaceCardImage(await response.blob(), "drop-url");
                } catch (err) {
                    console.warn("[toobusy Reference Board] URL image replace failed", err);
                }
            }
        });
    }

    let drag = null;
    dragTarget.addEventListener("pointerdown", (event) => {
        drag = {
            startX: event.clientX,
            startY: event.clientY,
            originX: Number(item.x) || 0,
            originY: Number(item.y) || 0,
            moved: false,
        };
        dragTarget.setPointerCapture?.(event.pointerId);
    });
    dragTarget.addEventListener("pointermove", (event) => {
        if (!drag) return;
        const dx = event.clientX - drag.startX;
        const dy = event.clientY - drag.startY;
        if (!drag.moved && Math.abs(dx) < 3 && Math.abs(dy) < 3) return; // ignore click jitter
        drag.moved = true;
        item.x = Math.max(0, drag.originX + dx);
        item.y = Math.max(0, drag.originY + dy);
        card.style.left = `${item.x}px`;
        card.style.top = `${item.y}px`;
        sync();
    });
    dragTarget.addEventListener("pointerup", () => {
        if (drag && drag.moved) card._toobusySuppressClick = true; // a drag, not a click
        drag = null;
    });

    area.appendChild(card);
    hint.style.display = board.items.length ? "none" : "";
    return card;
}

function refreshLauncher(launcher, node, stateText = "Applied") {
    const board = parseBoard(node);
    const summary = launcher.querySelector(".summary");
    const slots = launcher.querySelector(".toobusy-ref-mini-grid");
    const note = launcher.querySelector(".toobusy-ref-note-preview");
    const validation = launcher.querySelector(".toobusy-ref-validation-preview");
    const badge = launcher.querySelector(".badge");
    if (badge) badge.textContent = stateText;
    if (summary) summary.textContent = `cards: ${(board.items || []).length}`;
    if (note) note.textContent = `Global note: ${(board.global_note || "").trim() || "empty"}`;
    if (validation) validation.textContent = validationSummary(board);
    if (!slots) return;
    slots.innerHTML = "";
    const items = board.items || [];
    if (!items.length) {
        const empty = document.createElement("div");
        empty.className = "toobusy-ref-slot toobusy-ref-slot-placeholder";
        empty.textContent = "No cards yet. Open Reference Board to add references.";
        slots.appendChild(empty);
        return;
    }
    // Show only the cards the user actually registered, each under its own role
    // label. Empty roles are not drawn (no fixed slot grid).
    for (const item of items) {
        const role = item.role || "ignore";
        const isLora = (item.type || "") === "lora";
        const isText = (item.type || "") === "text";
        const audio = isAudioItem(item);
        const label = isText ? `Text · ${item.text_category || "goal"}` : (isLora ? "LoRA" : (ROLE_LABEL[role] || role));
        const name = isText
            ? ((item.text || "").trim().slice(0, 40) || "empty")
            : (isLora ? (item.lora_name || "no file") : (item.name || item.id || "ref"));
        const slot = document.createElement("div");
        slot.className = "toobusy-ref-slot";
        const mediaThumb = !audio && referenceViewUrl(item)
            ? `<img src="${referenceViewUrl(item)}" draggable="false">`
            : `<div class="toobusy-ref-empty-thumb">${audio ? "audio" : "img"}</div>`;
        const thumb = isText
            ? `<div class="toobusy-ref-empty-thumb">TXT</div>`
            : (isLora ? `<div class="toobusy-ref-empty-thumb">LoRA</div>` : mediaThumb);
        slot.innerHTML = `
            ${thumb}
            <div>
                <div class="toobusy-ref-slot-label">${label}</div>
                <div class="toobusy-ref-slot-name">${name}</div>
            </div>
        `;
        slot.addEventListener("mouseenter", (event) => showHoverPreview(item, event.clientX, event.clientY));
        slot.addEventListener("mousemove", (event) => positionHoverPreview(ensureHoverPreview(), event.clientX, event.clientY));
        slot.addEventListener("mouseleave", hideHoverPreview);
        makeSlotDraggable(slot, item, isText, isLora);
        slots.appendChild(slot);
    }
}

// Make a node-preview card draggable so it can be dropped into other apps
// (desktop, Photoshop, browser, etc.) — a real mood-board feel. Images drag as
// a file/URL; text cards drag their text.
function makeSlotDraggable(slot, item, isText, isLora) {
    const audio = isAudioItem(item);
    const img = slot.querySelector("img");
    if (img && !isText && !isLora && !audio) {
        img.draggable = true;
        img.addEventListener("dragstart", (event) => {
            const url = referenceViewUrl(item);
            if (!url) return;
            hideHoverPreview();
            let abs = url;
            try {
                abs = new URL(url, window.location.href).href;
            } catch {}
            const fname = `${item.name || item.role || "reference"}`.replace(/[^\w.-]+/g, "_") + ".png";
            try {
                event.dataTransfer.setData("text/uri-list", abs);
                event.dataTransfer.setData("text/plain", abs);
                // Chromium: enables drag-out to the OS as an image file.
                event.dataTransfer.setData("DownloadURL", `image/png:${fname}:${abs}`);
                event.dataTransfer.effectAllowed = "copy";
            } catch {}
        });
        return;
    }
    if (isText) {
        slot.draggable = true;
        slot.addEventListener("dragstart", (event) => {
            hideHoverPreview();
            try {
                event.dataTransfer.setData("text/plain", item.text || "");
                event.dataTransfer.effectAllowed = "copy";
            } catch {}
        });
    }
}

// --- Card thumbnail hover preview (large popup) -----------------------------
function ensureHoverPreview() {
    let el = document.getElementById("toobusy-ref-hover-preview");
    if (!el) {
        el = document.createElement("div");
        el.id = "toobusy-ref-hover-preview";
        el.className = "toobusy-ref-hover-preview";
        el.style.display = "none";
        document.body.appendChild(el);
    }
    return el;
}

function positionHoverPreview(el, x, y) {
    const pad = 16;
    const rect = el.getBoundingClientRect();
    let left = x + pad;
    let top = y + pad;
    if (left + rect.width + pad > window.innerWidth) left = x - rect.width - pad;
    if (top + rect.height + pad > window.innerHeight) top = window.innerHeight - rect.height - pad;
    el.style.left = `${Math.max(pad, left)}px`;
    el.style.top = `${Math.max(pad, top)}px`;
}

function showHoverPreview(item, x, y) {
    const el = ensureHoverPreview();
    el.innerHTML = "";
    const audio = isAudioItem(item);
    const isText = (item.type || "") === "text";
    const isLora = (item.type || "") === "lora";
    if (!isText && !isLora && !audio && referenceViewUrl(item)) {
        const img = document.createElement("img");
        img.src = referenceViewUrl(item);
        el.appendChild(img);
    } else {
        const title = document.createElement("div");
        title.className = "hp-title";
        title.textContent = isText
            ? `Text · ${item.text_category || "goal"}`
            : isLora
              ? "LoRA"
              : audio
                ? "Audio"
                : "Image";
        const body = document.createElement("div");
        body.className = "hp-text";
        body.textContent = isText
            ? item.text || "(empty)"
            : isLora
              ? `${item.lora_name || "(no file)"} · strength ${Number(item.lora_strength ?? 1)}`
              : item.name || item.id || "";
        el.appendChild(title);
        el.appendChild(body);
    }
    el.style.display = "block";
    positionHoverPreview(el, x, y);
}

function hideHoverPreview() {
    const el = document.getElementById("toobusy-ref-hover-preview");
    if (el) el.style.display = "none";
}

function openReferenceBoardOverlay(node, launcher) {
    injectOverlayStyle();
    const board = cloneBoard(parseBoard(node));
    const overlay = document.createElement("div");
    overlay.className = "toobusy-ref-overlay";
    overlay.innerHTML = `
        <div class="toobusy-ref-modal" role="dialog" aria-modal="true">
            <div class="toobusy-ref-head">
                <div class="toobusy-ref-title">toobusy Reference Board</div>
                <div class="toobusy-ref-save-state">Applied</div>
            </div>
            <div class="toobusy-ref-toolbar">
                <input class="file-input" type="file" accept="image/*,audio/*" multiple hidden>
                <div class="tb-group">
                    <button class="file-btn">Add files</button>
                    <input class="toobusy-ref-url" type="url" placeholder="Paste image/audio URL...">
                    <button class="url-btn">Add URL</button>
                    <button class="text-btn">Add Text</button>
                    <button class="lora-btn">Add LoRA</button>
                    <button class="clear-btn">Clear cards</button>
                </div>
                <div class="tb-group">
                    <input class="toobusy-ref-preset-name-input" type="text" placeholder="Preset name...">
                    <button class="save-preset-btn">Save as Preset</button>
                    <button class="load-preset-btn">Load Preset</button>
                </div>
                <div class="tb-group tb-right">
                    <button class="apply-close-btn tb-primary">Apply &amp; Close</button>
                    <button class="close-btn">Close</button>
                </div>
            </div>
            <div class="toobusy-ref-board" tabindex="0">
                <div class="toobusy-ref-hint">Drop, paste, or add reference images/audio</div>
            </div>
            <div class="toobusy-ref-library"></div>
            <div class="toobusy-ref-footer">
                <textarea class="toobusy-ref-global" placeholder="Global note for this reference set..."></textarea>
                <div class="toobusy-ref-status"></div>
            </div>
        </div>
    `;
    stopOverlayEvents(overlay);
    document.body.appendChild(overlay);

    const area = overlay.querySelector(".toobusy-ref-board");
    const hint = overlay.querySelector(".toobusy-ref-hint");
    const fileInput = overlay.querySelector(".file-input");
    const urlInput = overlay.querySelector(".toobusy-ref-url");
    const presetNameInput = overlay.querySelector(".toobusy-ref-preset-name-input");
    const globalNote = overlay.querySelector(".toobusy-ref-global");
    const status = overlay.querySelector(".toobusy-ref-status");
    const saveState = overlay.querySelector(".toobusy-ref-save-state");
    const library = overlay.querySelector(".toobusy-ref-library");
    let counter = board.items.length + 1;
    let dirty = false;

    function updateDraftState(markDirty = true) {
        board.global_note = globalNote.value;
        if (markDirty) dirty = true;
        status.textContent = statusLines(board).join("\n");
        saveState.textContent = dirty ? "Unsaved changes" : "Applied";
    }

    function applyToNode(stateText = "Applied") {
        board.global_note = globalNote.value;
        dirty = false;
        syncBoard(node, board);
        refreshLauncher(launcher, node, stateText);
        status.textContent = statusLines(board).join("\n");
        saveState.textContent = stateText;
    }

    function clearCardsDom() {
        area.querySelectorAll(".toobusy-ref-card").forEach((card) => card.remove());
        hint.style.display = "";
    }

    function redrawBoard() {
        clearCardsDom();
        counter = (board.items || []).length + 1;
        for (const item of board.items || []) {
            createCardElement(item, board, area, hint, updateDraftState);
        }
        hint.style.display = board.items?.length ? "none" : "";
        globalNote.value = board.global_note || "";
        updateDraftState();
    }

    function rolesText(roles) {
        return Array.isArray(roles) && roles.length ? roles.join(" / ") : "no roles";
    }

    async function refreshPresetLibrary() {
        library.classList.add("is-open");
        library.textContent = "Loading presets...";
        try {
            const response = await fetch("/toobusy/reference_board/list_presets");
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const data = await response.json();
            const presets = data.presets || [];
            library.innerHTML = "";
            if (!presets.length) {
                library.textContent = "No saved Reference Board presets yet. Type a preset name, then click Save as Preset.";
                return;
            }
            for (const preset of presets) {
                const row = document.createElement("div");
                row.className = "toobusy-ref-preset";
                row.innerHTML = `
                    <div>
                        <div class="toobusy-ref-preset-name"></div>
                        <div class="toobusy-ref-preset-meta"></div>
                    </div>
                    <button class="preset-load">Load</button>
                    <button class="preset-delete">Delete</button>
                `;
                row.querySelector(".toobusy-ref-preset-name").textContent = preset.name || preset.id;
                row.querySelector(".toobusy-ref-preset-meta").textContent =
                    `${preset.image_count || 0} images · ${rolesText(preset.roles)} · ${preset.updated_at || ""}`;
                row.querySelector(".preset-load").addEventListener("click", async () => {
                    const loadResponse = await fetch(`/toobusy/reference_board/load_preset?id=${encodeURIComponent(preset.id)}`);
                    if (!loadResponse.ok) throw new Error(`HTTP ${loadResponse.status}`);
                    const loaded = await loadResponse.json();
                    board.version = loaded.version || 1;
                    board.global_note = loaded.global_note || "";
                    board.items = Array.isArray(loaded.items) ? loaded.items : [];
                    redrawBoard();
                    saveState.textContent = `Loaded preset: ${loaded.name || preset.name || preset.id}`;
                    library.classList.remove("is-open");  // close the list after loading
                });
                row.querySelector(".preset-delete").addEventListener("click", async () => {
                    if (!confirm(`Delete preset "${preset.name || preset.id}"?`)) return;
                    await fetch("/toobusy/reference_board/delete_preset", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ id: preset.id }),
                    });
                    await refreshPresetLibrary();
                });
                library.appendChild(row);
            }
        } catch (err) {
            library.classList.add("is-open");
            library.textContent = "Preset library failed to load. Restart ComfyUI and hard-refresh the browser.";
            saveState.textContent = "Preset library route failed";
            console.warn("[toobusy Reference Board] preset list failed", err);
        }
    }

    async function saveAsPreset() {
        const name = presetNameInput.value.trim();
        if (!name) {
            saveState.textContent = "Enter a preset name first";
            presetNameInput.focus();
            return;
        }
        board.global_note = globalNote.value;
        try {
            const response = await fetch("/toobusy/reference_board/save_preset", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ name, board }),
            });
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const saved = await response.json();
            saveState.textContent = `Preset saved: ${saved.name || name}`;
            presetNameInput.value = saved.name || name;
            await refreshPresetLibrary();
        } catch (err) {
            saveState.textContent = "Preset save failed. Restart ComfyUI and hard-refresh.";
            library.classList.add("is-open");
            library.textContent = "Preset save failed. The backend route may not be registered until ComfyUI restarts.";
            console.warn("[toobusy Reference Board] preset save failed", err);
        }
    }

    function addCard(encoded, source, x = 24, y = 24) {
        const isAudio = encoded.type === "audio";
        const item = {
            id: `${isAudio ? "aud" : "ref"}_${Date.now().toString(36)}_${counter}`,
            name: `${isAudio ? "audio" : "ref"}_${String(counter).padStart(2, "0")}`,
            type: isAudio ? "audio" : "image",
            role: isAudio ? "audio_1" : "ignore",
            note: "",
            source,
            x,
            y,
            w: 184,
            h: isAudio ? 306 : 256,
            ...encoded,
        };
        if (isAudio && !item.duration_seconds) {
            item.duration_seconds = 0;
        }
        if (isAudio && item.start_offset_seconds == null) {
            item.start_offset_seconds = 0;
        }
        if (isAudio && !item.end_mode) {
            item.end_mode = "trim";
        }
        counter += 1;
        board.items.push(item);
        createCardElement(item, board, area, hint, updateDraftState);
        updateDraftState();
    }

    function addTextCard() {
        const item = {
            id: `text_${Date.now().toString(36)}_${counter}`,
            name: `text_${String(counter).padStart(2, "0")}`,
            type: "text",
            text_category: "goal",
            text: "",
            x: 24 + ((counter % 5) * 18),
            y: 24 + ((counter % 5) * 18),
        };
        counter += 1;
        board.items.push(item);
        createCardElement(item, board, area, hint, updateDraftState);
        updateDraftState();
    }

    function addLoraCard() {
        const item = {
            id: `lora_${Date.now().toString(36)}_${counter}`,
            name: `lora_${String(counter).padStart(2, "0")}`,
            type: "lora",
            role: "lora_a",
            lora_name: "",
            lora_strength: 1.0,
            lora_enabled: true,
            x: 24 + ((counter % 5) * 18),
            y: 24 + ((counter % 5) * 18),
        };
        counter += 1;
        board.items.push(item);
        createCardElement(item, board, area, hint, updateDraftState);
        updateDraftState();
    }

    async function addBlob(blob, source, x, y) {
        try {
            if (blob.type?.startsWith("audio/")) {
                addCard(await encodeAudioBlob(blob), source, x, y);
            } else {
                addCard(await encodeImageBlob(blob), source, x, y);
            }
        } catch (err) {
            console.warn("[toobusy Reference Board] media import failed", err);
        }
    }

    overlay.querySelector(".close-btn").addEventListener("click", () => {
        overlay.remove();
    });
    overlay.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
            overlay.remove();
        }
    });
    overlay.querySelector(".save-preset-btn").addEventListener("click", saveAsPreset);
    overlay.querySelector(".load-preset-btn").addEventListener("click", () => {
        // Toggle the preset library: click again to close it.
        if (library.classList.contains("is-open")) {
            library.classList.remove("is-open");
        } else {
            refreshPresetLibrary();
        }
    });
    overlay.querySelector(".apply-close-btn").addEventListener("click", () => {
        applyToNode("Applied");
        overlay.remove();
    });
    overlay.querySelector(".file-btn").addEventListener("click", () => fileInput.click());
    fileInput.addEventListener("change", async () => {
        const files = Array.from(fileInput.files || []);
        let x = 24;
        let y = 24;
        for (const file of files) {
            await addBlob(file, "file", x, y);
            x += 34;
            y += 34;
        }
        fileInput.value = "";
    });
    overlay.querySelector(".text-btn").addEventListener("click", addTextCard);
    overlay.querySelector(".lora-btn").addEventListener("click", addLoraCard);
    overlay.querySelector(".url-btn").addEventListener("click", async () => {
        const url = urlInput.value.trim();
        if (!url) return;
        try {
            const response = await fetch(url);
            await addBlob(await response.blob(), "url", 24, 24);
            urlInput.value = "";
        } catch (err) {
            console.warn("[toobusy Reference Board] URL import failed", err);
        }
    });
    overlay.querySelector(".clear-btn").addEventListener("click", () => {
        board.items = [];
        clearCardsDom();
        updateDraftState();
    });
    area.addEventListener("dragover", (event) => {
        event.preventDefault();
        area.classList.add("is-drop");
    });
    area.addEventListener("dragleave", () => area.classList.remove("is-drop"));
    area.addEventListener("drop", async (event) => {
        event.preventDefault();
        area.classList.remove("is-drop");
        const rect = area.getBoundingClientRect();
        const x = event.clientX - rect.left + area.scrollLeft;
        const y = event.clientY - rect.top + area.scrollTop;
        for (const file of Array.from(event.dataTransfer?.files || [])) {
            if (file.type.startsWith("image/") || file.type.startsWith("audio/")) {
                await addBlob(file, "drop", x, y);
            }
        }
    });
    overlay.addEventListener("paste", async (event) => {
        const items = Array.from(event.clipboardData?.items || []);
        for (const item of items) {
            if (item.type.startsWith("image/")) {
                event.preventDefault();
                const blob = item.getAsFile();
                if (blob) await addBlob(blob, "paste", 24, 24);
            }
        }
    });
    globalNote.value = board.global_note || "";
    globalNote.addEventListener("input", () => updateDraftState());

    for (const item of board.items || []) {
        createCardElement(item, board, area, hint, updateDraftState);
    }
    hint.style.display = board.items?.length ? "none" : "";
    updateDraftState(false);
    area.focus();
}

function makeLauncher(node) {
    injectOverlayStyle();
    const root = document.createElement("div");
    root.className = "toobusy-ref-launcher";
    root.innerHTML = `
        <div class="topline">
            <button>Open Reference Board</button>
            <span class="badge">Applied</span>
            <span class="summary"></span>
        </div>
        <div class="toobusy-ref-mini-grid"></div>
        <div class="toobusy-ref-note-preview"></div>
        <div class="toobusy-ref-validation-preview"></div>
    `;
    const button = root.querySelector("button");
    refreshLauncher(root, node, "Applied");
    button.addEventListener("pointerdown", (event) => event.stopPropagation());
    button.addEventListener("click", (event) => {
        event.stopPropagation();
        openReferenceBoardOverlay(node, root);
    });
    return root;
}

app.registerExtension({
    name: "toobusy.referenceBoard",
    beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== "ToobusyReferenceBoard") return;

        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            onNodeCreated?.apply(this, arguments);
            hideWidget(boardWidget(this));
            const launcher = makeLauncher(this);
            if (this.addDOMWidget) {
                const domWidget = this.addDOMWidget("reference_board_launcher", "div", launcher, {
                    serialize: false,
                    getMinHeight: () => WIDGET_SIZE[1],
                    getMaxHeight: () => WIDGET_SIZE[1],
                    getHeight: () => WIDGET_SIZE[1],
                });
                if (domWidget) {
                    domWidget.computeSize = () => [...WIDGET_SIZE];
                    if (this.widgets?.includes(domWidget)) {
                        this.widgets = [domWidget, ...this.widgets.filter((item) => item !== domWidget)];
                    }
                }
            } else {
                this.addWidget("button", "Open Reference Board", "open", () => openReferenceBoardOverlay(this, launcher), { serialize: false });
            }
            if (!this.properties?.toobusy_reference_board_sized) {
                this.properties = this.properties || {};
                this.properties.toobusy_reference_board_sized = true;
                this.setSize?.(NODE_SIZE);
                if (!this.setSize) {
                    this.size = [...NODE_SIZE];
                }
            }
        };

        const originalComputeSize = nodeType.prototype.computeSize;
        nodeType.prototype.computeSize = function (out) {
            const size = originalComputeSize?.call(this, out) || NODE_SIZE;
            return [Math.max(size[0], NODE_SIZE[0]), Math.max(size[1], NODE_SIZE[1])];
        };
    },
});
