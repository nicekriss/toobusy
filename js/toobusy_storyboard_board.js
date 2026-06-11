import { app } from "../../scripts/app.js";

// toobusy Storyboard Board — an Excalidraw-style whiteboard living inside the
// node: infinite pan/zoom canvas, floating tool islands, in-place text
// editing, image paste/drop, and keyframe marking for the image -> keyframes
// -> video flow. Board items live in world coordinates; the Python render
// captures the (0,0)-(width,height) output frame.

const ACCENT = "#7fc8ff";
const INFO_TITLE = "toobusy · Storyboard Board";
const INFO_TEXT =
    "An in-graph whiteboard: sketch, write, paste images, arrange them freely " +
    "on an infinite canvas, then mark image cards as keyframes (K). Outputs the " +
    "framed board as an image plus the marked keyframes as an IMAGE batch for " +
    "video nodes downstream.";
const INFO_SIGNATURE = "fold the graph — 너무바쁜베짱이";

const MIN_SIZE = 16;
const GRID_STEP = 28;
const MAX_IMAGE_EDGE = 1536;

const COLOR_PRESETS = ["#1b1f24", "#e03131", "#f08c00", "#2f9e44", "#1971c2", "#ae3ec9", "#ffffff"];
const FILL_PRESETS = ["rgba(0,0,0,0)", "rgba(255,255,255,0.85)", "rgba(224,49,49,0.16)", "rgba(240,140,0,0.16)", "rgba(47,158,68,0.16)", "rgba(25,113,194,0.16)"];
const STROKE_PRESETS = [2, 4, 8];
const FONT_PRESETS = [20, 32, 48];

const DEFAULT_BOARD = {
    version: 3,
    items: [
        { type: "text", id: "title", x: 48, y: 40, w: 480, h: 52, text: "Storyboard / mood board", fontSize: 36, color: "#1b1f24" },
    ],
};

// Minimal inline SVG icon set (16x16 viewBox, stroke = currentColor).
const ICONS = {
    select: '<svg viewBox="0 0 16 16" fill="none"><path d="M4 2l8 6.5-3.6.7 2 3.8-1.8 1-2-3.9L4 12.5z" stroke="currentColor" stroke-width="1.3" stroke-linejoin="round"/></svg>',
    hand: '<svg viewBox="0 0 16 16" fill="none"><path d="M5 7.5V3.8a1 1 0 012 0V7m0-3.9a1 1 0 012 0V7m0-2.6a1 1 0 012 0V8.7c0 2.9-1.6 4.8-4.1 4.8-1.9 0-2.8-.8-3.9-2.6L2 9.1c-.5-.8.6-1.7 1.3-1L5 9.7" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    pen: '<svg viewBox="0 0 16 16" fill="none"><path d="M3 13l.8-3L11 2.8a1.2 1.2 0 011.7 0l.5.5a1.2 1.2 0 010 1.7L6 12.2z" stroke="currentColor" stroke-width="1.3" stroke-linejoin="round"/></svg>',
    text: '<svg viewBox="0 0 16 16" fill="none"><path d="M3 4V2.8h10V4M8 2.8V13m-2 0h4" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/></svg>',
    rect: '<svg viewBox="0 0 16 16" fill="none"><rect x="2.6" y="3.6" width="10.8" height="8.8" rx="1.6" stroke="currentColor" stroke-width="1.3"/></svg>',
    ellipse: '<svg viewBox="0 0 16 16" fill="none"><ellipse cx="8" cy="8" rx="5.6" ry="4.4" stroke="currentColor" stroke-width="1.3"/></svg>',
    arrow: '<svg viewBox="0 0 16 16" fill="none"><path d="M3 13L12.4 3.6M12.8 8V3.2H8" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    image: '<svg viewBox="0 0 16 16" fill="none"><rect x="2.4" y="3" width="11.2" height="10" rx="1.4" stroke="currentColor" stroke-width="1.2"/><circle cx="6" cy="6.6" r="1.1" fill="currentColor"/><path d="M3.4 11.6l3-3 2.3 2.3 2-2 2.5 2.7" stroke="currentColor" stroke-width="1.2" stroke-linejoin="round"/></svg>',
    undo: '<svg viewBox="0 0 16 16" fill="none"><path d="M5.5 3.5L3 6l2.5 2.5M3 6h6a4 4 0 010 8H7" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    redo: '<svg viewBox="0 0 16 16" fill="none"><path d="M10.5 3.5L13 6l-2.5 2.5M13 6H7a4 4 0 000 8h2" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    fit: '<svg viewBox="0 0 16 16" fill="none"><path d="M2.5 5.5v-3h3m5 0h3v3m0 5v3h-3m-5 0h-3v-3" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/></svg>',
};

function findWidget(node, name) {
    return node.widgets?.find((widget) => widget.name === name);
}

function boardWidget(node) {
    return findWidget(node, "board_data");
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

function serializeBoard(board) {
    return JSON.stringify(board, (key, value) => (key === "_node" ? undefined : value));
}

function hideWidget(node, widget) {
    if (!widget) return;
    widget.type = "hidden";
    widget.computeSize = () => [0, -4];
    widget.hidden = true;
}

function itemBounds(item) {
    const x2 = item.x2 ?? item.x + (item.w || 0);
    const y2 = item.y2 ?? item.y + (item.h || 0);
    if (item.type === "pen" && Array.isArray(item.points) && item.points.length) {
        const xs = item.points.map((p) => p.x);
        const ys = item.points.map((p) => p.y);
        const minX = Math.min(...xs);
        const minY = Math.min(...ys);
        return { x: minX, y: minY, w: Math.max(...xs) - minX, h: Math.max(...ys) - minY };
    }
    return {
        x: Math.min(item.x, x2),
        y: Math.min(item.y, y2),
        w: Math.abs(x2 - item.x) || item.w || 0,
        h: Math.abs(y2 - item.y) || item.h || 0,
    };
}

function rgbToHex(value) {
    const match = String(value || "").match(/\d+(\.\d+)?/g);
    if (!match || match.length < 3) {
        return /^#[0-9a-f]{6}$/i.test(value) ? value : "#1b1f24";
    }
    const [r, g, b] = match.map((n) => Math.max(0, Math.min(255, Math.round(parseFloat(n)))));
    return `#${[r, g, b].map((n) => n.toString(16).padStart(2, "0")).join("")}`;
}

// Downscale + re-encode dropped/pasted images so board_data (and the workflow
// file it serializes into) stays reasonably small.
function encodeImageBlob(blob) {
    return new Promise((resolve, reject) => {
        const url = URL.createObjectURL(blob);
        const img = new Image();
        img.onload = () => {
            URL.revokeObjectURL(url);
            const scale = Math.min(1, MAX_IMAGE_EDGE / Math.max(img.naturalWidth, img.naturalHeight));
            const buffer = document.createElement("canvas");
            buffer.width = Math.max(1, Math.round(img.naturalWidth * scale));
            buffer.height = Math.max(1, Math.round(img.naturalHeight * scale));
            buffer.getContext("2d").drawImage(img, 0, 0, buffer.width, buffer.height);
            const usePng = String(blob.type).includes("png") && blob.size < 1_500_000;
            resolve({
                src: usePng ? buffer.toDataURL("image/png") : buffer.toDataURL("image/jpeg", 0.87),
                width: buffer.width,
                height: buffer.height,
            });
        };
        img.onerror = () => {
            URL.revokeObjectURL(url);
            reject(new Error("not an image"));
        };
        img.src = url;
    });
}

function makeBoardEditor(node) {
    const board = parseBoard(node);
    let selected = null;
    let editing = null; // item currently in the inline text editor
    let tool = "select";
    let spaceHeld = false;
    let drag = null; // {mode, ...}
    let hoverCursor = "default";
    const imageCache = new Map();
    const undoStack = [];
    const redoStack = [];

    const storedView = node.properties?.toobusy_board_view;
    const view = {
        x: Number(storedView?.x) || 60,
        y: Number(storedView?.y) || 60,
        scale: Number(storedView?.scale) || 0.5,
    };

    // ----- DOM scaffold ------------------------------------------------------
    const root = document.createElement("div");
    root.className = "toobusy-board";
    root.innerHTML = `
        <style>
            .toobusy-board {
                position: relative;
                width: 100%;
                height: 600px;
                box-sizing: border-box;
                border-radius: 10px;
                overflow: hidden;
                background: #11151a;
                border: 1px solid #2d3642;
                font: 12px/1.4 system-ui, -apple-system, "Segoe UI", sans-serif;
                user-select: none;
                color: #e9edf1;
            }
            .toobusy-board * { box-sizing: border-box; }
            .toobusy-board canvas.board-surface {
                position: absolute;
                inset: 0;
                width: 100%;
                height: 100%;
                display: block;
                outline: none;
                touch-action: none;
            }
            .toobusy-board .island {
                position: absolute;
                display: flex;
                gap: 2px;
                align-items: center;
                padding: 4px;
                border-radius: 10px;
                background: rgba(23, 28, 34, 0.92);
                border: 1px solid #2d3642;
                box-shadow: 0 8px 24px rgba(0, 0, 0, 0.38);
                backdrop-filter: blur(8px);
            }
            .toobusy-board .island.toolbar {
                top: 10px;
                left: 50%;
                transform: translateX(-50%);
            }
            .toobusy-board .island.props {
                top: 56px;
                left: 10px;
                flex-direction: column;
                align-items: stretch;
                gap: 7px;
                padding: 9px;
                width: 168px;
            }
            .toobusy-board .island.zoom {
                left: 10px;
                bottom: 10px;
            }
            .toobusy-board .tb-btn {
                width: 32px;
                height: 32px;
                display: flex;
                align-items: center;
                justify-content: center;
                border: none;
                border-radius: 8px;
                background: transparent;
                color: #c8d2dc;
                cursor: pointer;
                padding: 0;
            }
            .toobusy-board .tb-btn svg { width: 16px; height: 16px; }
            .toobusy-board .tb-btn:hover { background: #2a323c; color: #ffffff; }
            .toobusy-board .tb-btn.active {
                background: rgba(127, 200, 255, 0.18);
                color: ${ACCENT};
            }
            .toobusy-board .tb-btn:disabled { opacity: 0.35; cursor: default; }
            .toobusy-board .tb-sep {
                width: 1px;
                height: 20px;
                background: #2d3642;
                margin: 0 3px;
            }
            .toobusy-board .props .row-label {
                font-size: 10px;
                text-transform: uppercase;
                letter-spacing: 0.05em;
                color: #7f8b99;
                margin-bottom: -3px;
            }
            .toobusy-board .props .row {
                display: flex;
                gap: 4px;
                flex-wrap: wrap;
                align-items: center;
            }
            .toobusy-board .swatch {
                width: 22px;
                height: 22px;
                border-radius: 6px;
                border: 1px solid #3a4450;
                cursor: pointer;
                padding: 0;
                background: transparent;
            }
            .toobusy-board .swatch.active { outline: 2px solid ${ACCENT}; outline-offset: 1px; }
            .toobusy-board .swatch.none {
                background:
                    linear-gradient(to top right, transparent 46%, #e03131 46%, #e03131 54%, transparent 54%),
                    #1f262e;
            }
            .toobusy-board input.swatch-custom {
                width: 22px;
                height: 22px;
                padding: 0;
                border: 1px solid #3a4450;
                border-radius: 6px;
                background: none;
                cursor: pointer;
            }
            .toobusy-board .chip-btn {
                border: 1px solid #3a4450;
                border-radius: 7px;
                background: #1f262e;
                color: #d6dde4;
                font-size: 11px;
                padding: 4px 8px;
                cursor: pointer;
            }
            .toobusy-board .chip-btn:hover { background: #2a323c; }
            .toobusy-board .chip-btn.active {
                border-color: ${ACCENT};
                color: ${ACCENT};
                background: rgba(127, 200, 255, 0.12);
            }
            .toobusy-board .chip-btn.danger:hover { border-color: #b04a52; color: #ffb8c1; }
            .toobusy-board .zoom-label {
                min-width: 44px;
                text-align: center;
                font-size: 11px;
                color: #c8d2dc;
                cursor: pointer;
                border-radius: 6px;
                padding: 4px 2px;
            }
            .toobusy-board .zoom-label:hover { background: #2a323c; }
            .toobusy-board .hint {
                position: absolute;
                right: 12px;
                bottom: 10px;
                font-size: 10.5px;
                color: rgba(127, 139, 153, 0.85);
                text-align: right;
                pointer-events: none;
            }
            .toobusy-board textarea.inline-editor {
                position: absolute;
                display: none;
                background: transparent;
                border: 1.5px dashed ${ACCENT};
                border-radius: 4px;
                outline: none;
                resize: none;
                overflow: hidden;
                padding: 0 2px;
                margin: 0;
                line-height: 1.25;
                font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
                white-space: pre-wrap;
                word-break: break-word;
            }
            .toobusy-board input.image-file { display: none; }
        </style>
        <canvas class="board-surface" tabindex="0"></canvas>
        <div class="island toolbar"></div>
        <div class="island props" hidden></div>
        <div class="island zoom"></div>
        <div class="hint">Space-drag pan · Ctrl+wheel zoom · Ctrl+V paste image · double-click text · K keyframe</div>
        <textarea class="inline-editor" spellcheck="false"></textarea>
        <input class="image-file" type="file" accept="image/*" multiple />
    `;

    const canvas = root.querySelector("canvas.board-surface");
    const toolbarEl = root.querySelector(".island.toolbar");
    const propsEl = root.querySelector(".island.props");
    const zoomEl = root.querySelector(".island.zoom");
    const editorEl = root.querySelector("textarea.inline-editor");
    const fileInput = root.querySelector("input.image-file");
    const ctx = canvas.getContext("2d");

    // Keep board interactions inside the board: LiteGraph must not also pan
    // the graph or steal keystrokes while the cursor works the whiteboard.
    for (const type of ["pointerdown", "pointerup", "dblclick", "contextmenu"]) {
        root.addEventListener(type, (event) => event.stopPropagation());
    }
    root.addEventListener("keydown", (event) => event.stopPropagation());

    // ----- view + coordinate helpers ----------------------------------------
    const toWorld = (event) => {
        const rect = canvas.getBoundingClientRect();
        return {
            x: (event.clientX - rect.left - view.x) / view.scale,
            y: (event.clientY - rect.top - view.y) / view.scale,
        };
    };
    const persistView = () => {
        node.properties = node.properties || {};
        node.properties.toobusy_board_view = { x: view.x, y: view.y, scale: view.scale };
    };
    const zoomAt = (clientX, clientY, factor) => {
        const rect = canvas.getBoundingClientRect();
        const sx = clientX - rect.left;
        const sy = clientY - rect.top;
        const wx = (sx - view.x) / view.scale;
        const wy = (sy - view.y) / view.scale;
        view.scale = Math.max(0.08, Math.min(4, view.scale * factor));
        view.x = sx - wx * view.scale;
        view.y = sy - wy * view.scale;
        persistView();
        syncZoomLabel();
        closeTextEditor();
        draw();
    };
    const outputFrame = () => ({
        w: Number(findWidget(node, "width")?.value) || 1280,
        h: Number(findWidget(node, "height")?.value) || 720,
    });
    const fitOutputFrame = () => {
        const frame = outputFrame();
        const pad = 48;
        const scale = Math.min(
            (canvas.clientWidth - pad * 2) / frame.w,
            (canvas.clientHeight - pad * 2) / frame.h,
        );
        view.scale = Math.max(0.08, Math.min(4, scale));
        view.x = (canvas.clientWidth - frame.w * view.scale) / 2;
        view.y = (canvas.clientHeight - frame.h * view.scale) / 2;
        persistView();
        syncZoomLabel();
        closeTextEditor();
        draw();
    };

    // ----- persistence + history ---------------------------------------------
    const commit = () => {
        const widget = boardWidget(node);
        if (widget) {
            widget.value = serializeBoard(board);
            widget.callback?.(widget.value);
        }
        node.setDirtyCanvas?.(true, true);
        draw();
    };
    const snapshot = () => serializeBoard(board);
    const pushHistory = () => {
        undoStack.push(snapshot());
        if (undoStack.length > 80) undoStack.shift();
        redoStack.length = 0;
    };
    const restore = (snap) => {
        try {
            const data = JSON.parse(snap);
            if (Array.isArray(data.items)) {
                board.items = data.items;
                selected = null;
            }
        } catch {}
    };
    const undo = () => {
        if (!undoStack.length) return;
        closeTextEditor();
        redoStack.push(snapshot());
        restore(undoStack.pop());
        renderProps();
        commit();
    };
    const redo = () => {
        if (!redoStack.length) return;
        closeTextEditor();
        undoStack.push(snapshot());
        restore(redoStack.pop());
        renderProps();
        commit();
    };

    // ----- keyframe order ------------------------------------------------------
    const keyframeItems = () =>
        board.items
            .filter((item) => item.type === "image" && Number(item.keyframe) > 0)
            .sort((a, b) => Number(a.keyframe) - Number(b.keyframe));
    const renumberKeyframes = () => {
        keyframeItems().forEach((item, index) => {
            item.keyframe = index + 1;
        });
    };
    const toggleKeyframe = (item) => {
        if (!item || item.type !== "image") return;
        pushHistory();
        if (Number(item.keyframe) > 0) {
            delete item.keyframe;
        } else {
            item.keyframe = keyframeItems().length + 1;
        }
        renumberKeyframes();
        renderProps();
        commit();
    };

    // ----- drawing -------------------------------------------------------------
    function imageFromSrc(src) {
        if (!src) return null;
        if (imageCache.has(src)) return imageCache.get(src);
        const img = new Image();
        img.onload = () => draw();
        img.src = src;
        imageCache.set(src, img);
        return img;
    }

    function roundedPath(c, x, y, w, h, r) {
        const radius = Math.max(0, Math.min(r, Math.abs(w) / 2, Math.abs(h) / 2));
        c.beginPath();
        if (c.roundRect) {
            c.roundRect(x, y, w, h, radius);
        } else {
            c.rect(x, y, w, h);
        }
    }

    function drawPen(c, points) {
        if (!Array.isArray(points) || points.length < 2) return;
        c.beginPath();
        c.moveTo(points[0].x, points[0].y);
        for (let i = 1; i < points.length - 1; i += 1) {
            const midX = (points[i].x + points[i + 1].x) / 2;
            const midY = (points[i].y + points[i + 1].y) / 2;
            c.quadraticCurveTo(points[i].x, points[i].y, midX, midY);
        }
        const last = points[points.length - 1];
        c.lineTo(last.x, last.y);
        c.lineJoin = "round";
        c.lineCap = "round";
        c.stroke();
    }

    function wrapTextLines(c, text, fontPx, width) {
        c.font = `${fontPx}px system-ui, -apple-system, "Segoe UI", sans-serif`;
        const lines = [];
        for (const raw of String(text || "").split("\n")) {
            const words = raw.split(/\s+/).filter(Boolean);
            if (!words.length) {
                lines.push("");
                continue;
            }
            let current = words[0];
            for (let i = 1; i < words.length; i += 1) {
                const test = `${current} ${words[i]}`;
                if (c.measureText(test).width <= width) {
                    current = test;
                } else {
                    lines.push(current);
                    current = words[i];
                }
            }
            lines.push(current);
        }
        return lines.length ? lines : [""];
    }

    function drawItem(c, item) {
        c.save();
        c.lineWidth = item.strokeWidth || 3;
        c.strokeStyle = item.color || "#1b1f24";
        c.fillStyle = item.fill || "rgba(0,0,0,0)";

        if (item.type === "image") {
            const img = imageFromSrc(item.src);
            const radius = 10;
            c.save();
            c.shadowColor = "rgba(15, 20, 26, 0.28)";
            c.shadowBlur = 14 * view.scale;
            c.shadowOffsetY = 4 * view.scale;
            roundedPath(c, item.x, item.y, item.w, item.h, radius);
            c.fillStyle = "#ffffff";
            c.fill();
            c.restore();
            roundedPath(c, item.x, item.y, item.w, item.h, radius);
            c.save();
            c.clip();
            if (img?.complete && img.naturalWidth) {
                c.drawImage(img, item.x, item.y, item.w, item.h);
            } else {
                c.fillStyle = "#e7ebef";
                c.fillRect(item.x, item.y, item.w, item.h);
                c.fillStyle = "#7f8b99";
                c.font = `${14 / view.scale}px system-ui, sans-serif`;
                c.fillText("loading…", item.x + 10, item.y + 24);
            }
            c.restore();
            roundedPath(c, item.x, item.y, item.w, item.h, radius);
            c.lineWidth = 1 / view.scale;
            c.strokeStyle = "rgba(15, 20, 26, 0.22)";
            c.stroke();

            if (Number(item.keyframe) > 0) {
                const r = 13 / view.scale;
                const bx = item.x + r + 6 / view.scale;
                const by = item.y + r + 6 / view.scale;
                c.beginPath();
                c.arc(bx, by, r, 0, Math.PI * 2);
                c.fillStyle = ACCENT;
                c.fill();
                c.fillStyle = "#0d1218";
                c.font = `700 ${15 / view.scale}px system-ui, sans-serif`;
                c.textAlign = "center";
                c.textBaseline = "middle";
                c.fillText(String(item.keyframe), bx, by + 0.5 / view.scale);
            }
        } else if (item.type === "rect") {
            roundedPath(c, item.x, item.y, item.w, item.h, 12);
            c.fill();
            c.stroke();
        } else if (item.type === "ellipse") {
            c.beginPath();
            c.ellipse(item.x + item.w / 2, item.y + item.h / 2, Math.abs(item.w / 2), Math.abs(item.h / 2), 0, 0, Math.PI * 2);
            c.fill();
            c.stroke();
        } else if (item.type === "line") {
            c.beginPath();
            c.moveTo(item.x, item.y);
            c.lineTo(item.x2, item.y2);
            c.lineCap = "round";
            c.stroke();
            if (item.arrow) {
                const angle = Math.atan2(item.y2 - item.y, item.x2 - item.x);
                const length = 14 + (item.strokeWidth || 3) * 2;
                c.beginPath();
                c.moveTo(item.x2, item.y2);
                c.lineTo(item.x2 - length * Math.cos(angle - 0.45), item.y2 - length * Math.sin(angle - 0.45));
                c.lineTo(item.x2 - length * Math.cos(angle + 0.45), item.y2 - length * Math.sin(angle + 0.45));
                c.closePath();
                c.fillStyle = item.color || "#1b1f24";
                c.fill();
            }
        } else if (item.type === "pen") {
            drawPen(c, item.points);
        } else if (item.type === "text" && item !== editing) {
            c.fillStyle = item.color || "#1b1f24";
            c.textBaseline = "top";
            const fs = item.fontSize || 24;
            const lines = wrapTextLines(c, item.text, fs, Math.max(MIN_SIZE, item.w || MIN_SIZE));
            let lineY = item.y;
            for (const line of lines) {
                c.fillText(line, item.x, lineY);
                lineY += fs * 1.25;
            }
            // Text height follows its content so selection hugs the words.
            item.h = Math.max(fs * 1.25, lines.length * fs * 1.25);
        }
        c.restore();
    }

    function selectionHandles(item) {
        const b = itemBounds(item);
        if (item.type === "line") {
            return [
                { id: "start", x: item.x, y: item.y },
                { id: "end", x: item.x2, y: item.y2 },
            ];
        }
        if (item.type === "pen") return [];
        return [
            { id: "nw", x: b.x, y: b.y },
            { id: "ne", x: b.x + b.w, y: b.y },
            { id: "sw", x: b.x, y: b.y + b.h },
            { id: "se", x: b.x + b.w, y: b.y + b.h },
        ];
    }

    function draw() {
        const dpr = window.devicePixelRatio || 1;
        const wantW = Math.max(1, Math.round(canvas.clientWidth * dpr));
        const wantH = Math.max(1, Math.round(canvas.clientHeight * dpr));
        if (canvas.width !== wantW || canvas.height !== wantH) {
            canvas.width = wantW;
            canvas.height = wantH;
        }

        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        const background = findWidget(node, "background")?.value || "#f8f9fa";
        ctx.fillStyle = background;
        ctx.fillRect(0, 0, canvas.clientWidth, canvas.clientHeight);

        // Dot grid (screen-space culled, fades out when zoomed far away).
        const step = GRID_STEP * view.scale;
        if (step >= 9) {
            const alpha = Math.min(0.5, (step - 8) / 60 + 0.18);
            ctx.fillStyle = `rgba(110, 122, 136, ${alpha})`;
            const startX = ((view.x % step) + step) % step;
            const startY = ((view.y % step) + step) % step;
            const r = Math.min(1.4, 0.8 + view.scale * 0.4);
            for (let x = startX; x < canvas.clientWidth; x += step) {
                for (let y = startY; y < canvas.clientHeight; y += step) {
                    ctx.beginPath();
                    ctx.arc(x, y, r, 0, Math.PI * 2);
                    ctx.fill();
                }
            }
        }

        ctx.setTransform(dpr * view.scale, 0, 0, dpr * view.scale, dpr * view.x, dpr * view.y);

        // Output frame: the region the Python render captures.
        const frame = outputFrame();
        ctx.save();
        ctx.strokeStyle = "rgba(127, 200, 255, 0.55)";
        ctx.lineWidth = 1.5 / view.scale;
        roundedPath(ctx, 0, 0, frame.w, frame.h, 4 / view.scale);
        ctx.stroke();
        ctx.fillStyle = "rgba(127, 200, 255, 0.75)";
        ctx.font = `600 ${11 / view.scale}px system-ui, sans-serif`;
        ctx.textBaseline = "bottom";
        ctx.fillText(`output ${frame.w} × ${frame.h}`, 2 / view.scale, -6 / view.scale);
        ctx.restore();

        for (const item of board.items) {
            drawItem(ctx, item);
        }

        if (selected && board.items.includes(selected)) {
            const b = itemBounds(selected);
            const pad = 5 / view.scale;
            ctx.save();
            ctx.strokeStyle = ACCENT;
            ctx.lineWidth = 1.5 / view.scale;
            ctx.setLineDash([5 / view.scale, 4 / view.scale]);
            ctx.strokeRect(b.x - pad, b.y - pad, b.w + pad * 2, b.h + pad * 2);
            ctx.setLineDash([]);
            const hs = 8 / view.scale;
            for (const handle of selectionHandles(selected)) {
                ctx.beginPath();
                ctx.arc(handle.x, handle.y, hs / 2 + 1 / view.scale, 0, Math.PI * 2);
                ctx.fillStyle = "#ffffff";
                ctx.fill();
                ctx.lineWidth = 1.5 / view.scale;
                ctx.strokeStyle = ACCENT;
                ctx.stroke();
            }
            ctx.restore();
        } else if (selected) {
            selected = null;
        }
    }

    // ----- selection / hit testing ----------------------------------------------
    function hitItem(point) {
        const tolerance = 6 / view.scale;
        for (let index = board.items.length - 1; index >= 0; index -= 1) {
            const item = board.items[index];
            const b = itemBounds(item);
            if (
                point.x >= b.x - tolerance &&
                point.x <= b.x + b.w + tolerance &&
                point.y >= b.y - tolerance &&
                point.y <= b.y + b.h + tolerance
            ) {
                return item;
            }
        }
        return null;
    }

    function handleAt(item, point) {
        if (!item) return null;
        const reach = 9 / view.scale;
        for (const handle of selectionHandles(item)) {
            if (Math.abs(point.x - handle.x) <= reach && Math.abs(point.y - handle.y) <= reach) {
                return handle;
            }
        }
        return null;
    }

    const select = (item) => {
        if (selected === item) {
            renderProps();
            draw();
            return;
        }
        selected = item;
        renderProps();
        draw();
    };

    // ----- inline text editor ------------------------------------------------------
    function openTextEditor(item) {
        if (!item || item.type !== "text") return;
        pushHistory();
        editing = item;
        const fs = (item.fontSize || 24) * view.scale;
        editorEl.style.display = "block";
        editorEl.style.left = `${item.x * view.scale + view.x - 3}px`;
        editorEl.style.top = `${item.y * view.scale + view.y - 3}px`;
        editorEl.style.width = `${Math.max(120, (item.w || 200) * view.scale + 12)}px`;
        editorEl.style.fontSize = `${fs}px`;
        editorEl.style.color = item.color || "#1b1f24";
        editorEl.value = item.text || "";
        const grow = () => {
            editorEl.style.height = "auto";
            editorEl.style.height = `${editorEl.scrollHeight + 4}px`;
        };
        editorEl.oninput = () => {
            item.text = editorEl.value;
            grow();
            draw();
        };
        grow();
        draw();
        setTimeout(() => {
            editorEl.focus();
            editorEl.select();
        }, 0);
    }

    function closeTextEditor(cancel = false) {
        if (!editing) return;
        const item = editing;
        editing = null;
        editorEl.style.display = "none";
        if (cancel) {
            undo();
            return;
        }
        item.text = editorEl.value;
        if (!String(item.text).trim()) {
            board.items = board.items.filter((candidate) => candidate !== item);
            if (selected === item) selected = null;
            renderProps();
        }
        commit();
    }

    editorEl.addEventListener("blur", () => closeTextEditor());
    editorEl.addEventListener("keydown", (event) => {
        event.stopPropagation();
        if (event.key === "Escape") {
            event.preventDefault();
            closeTextEditor();
            canvas.focus();
        }
    });

    // ----- item creation -------------------------------------------------------------
    function createItem(type, point) {
        const item = {
            id: crypto.randomUUID(),
            type,
            x: point.x,
            y: point.y,
            w: 0,
            h: 0,
            color: "#1b1f24",
            strokeWidth: 4,
        };
        if (type === "rect" || type === "ellipse") {
            item.fill = "rgba(0,0,0,0)";
        } else if (type === "line") {
            item.x2 = point.x;
            item.y2 = point.y;
            item.arrow = true;
        } else if (type === "text") {
            item.w = 320;
            item.h = 40;
            item.text = "";
            item.fontSize = 32;
        }
        board.items.push(item);
        return item;
    }

    async function placeImageBlobs(blobs, point) {
        let offset = 0;
        let lastItem = null;
        for (const blob of blobs) {
            try {
                const encoded = await encodeImageBlob(blob);
                const worldW = Math.min(440, encoded.width);
                const worldH = worldW * (encoded.height / encoded.width);
                pushHistory();
                lastItem = {
                    id: crypto.randomUUID(),
                    type: "image",
                    x: point.x + offset - worldW / 2,
                    y: point.y + offset - worldH / 2,
                    w: worldW,
                    h: worldH,
                    src: encoded.src,
                };
                board.items.push(lastItem);
                offset += 28;
            } catch {}
        }
        if (lastItem) {
            select(lastItem);
            commit();
        }
    }

    const viewCenterWorld = () => ({
        x: (canvas.clientWidth / 2 - view.x) / view.scale,
        y: (canvas.clientHeight / 2 - view.y) / view.scale,
    });

    // ----- toolbar ----------------------------------------------------------------------
    const toolButtons = new Map();
    const toolbarButton = (icon, title, action, { toggles = null } = {}) => {
        const el = document.createElement("button");
        el.className = "tb-btn";
        el.innerHTML = ICONS[icon];
        el.title = title;
        el.addEventListener("pointerdown", (event) => event.preventDefault());
        el.addEventListener("click", action);
        toolbarEl.appendChild(el);
        if (toggles) toolButtons.set(toggles, el);
        return el;
    };
    const setTool = (next) => {
        tool = next;
        for (const [name, el] of toolButtons) {
            el.classList.toggle("active", name === tool);
        }
        canvas.style.cursor = tool === "hand" ? "grab" : tool === "select" ? "default" : "crosshair";
        canvas.focus();
    };

    toolbarButton("select", "Select / move (V)", () => setTool("select"), { toggles: "select" });
    toolbarButton("hand", "Pan (H or Space)", () => setTool("hand"), { toggles: "hand" });
    const sep1 = document.createElement("div");
    sep1.className = "tb-sep";
    toolbarEl.appendChild(sep1);
    toolbarButton("pen", "Draw (P)", () => setTool("pen"), { toggles: "pen" });
    toolbarButton("text", "Text (T) — or double-click the canvas", () => setTool("text"), { toggles: "text" });
    toolbarButton("rect", "Rectangle (R)", () => setTool("rect"), { toggles: "rect" });
    toolbarButton("ellipse", "Ellipse (O)", () => setTool("ellipse"), { toggles: "ellipse" });
    toolbarButton("arrow", "Arrow (A)", () => setTool("arrow"), { toggles: "arrow" });
    toolbarButton("image", "Insert image (or drop / Ctrl+V)", () => fileInput.click());
    const sep2 = document.createElement("div");
    sep2.className = "tb-sep";
    toolbarEl.appendChild(sep2);
    toolbarButton("undo", "Undo (Ctrl+Z)", undo);
    toolbarButton("redo", "Redo (Ctrl+Shift+Z)", redo);
    setTool("select");

    fileInput.addEventListener("change", () => {
        const files = [...(fileInput.files || [])].filter((file) => file.type.startsWith("image/"));
        fileInput.value = "";
        if (files.length) placeImageBlobs(files, viewCenterWorld());
    });

    // ----- zoom island --------------------------------------------------------------------
    const zoomOut = document.createElement("button");
    zoomOut.className = "tb-btn";
    zoomOut.textContent = "−";
    zoomOut.title = "Zoom out";
    const zoomLabel = document.createElement("div");
    zoomLabel.className = "zoom-label";
    zoomLabel.title = "Reset zoom to 100%";
    const zoomIn = document.createElement("button");
    zoomIn.className = "tb-btn";
    zoomIn.textContent = "+";
    zoomIn.title = "Zoom in";
    const zoomFit = document.createElement("button");
    zoomFit.className = "tb-btn";
    zoomFit.innerHTML = ICONS.fit;
    zoomFit.title = "Fit the output frame (F)";
    zoomEl.append(zoomOut, zoomLabel, zoomIn, zoomFit);
    const syncZoomLabel = () => {
        zoomLabel.textContent = `${Math.round(view.scale * 100)}%`;
    };
    const centerClient = () => {
        const rect = canvas.getBoundingClientRect();
        return { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 };
    };
    zoomOut.addEventListener("click", () => {
        const c = centerClient();
        zoomAt(c.x, c.y, 1 / 1.2);
    });
    zoomIn.addEventListener("click", () => {
        const c = centerClient();
        zoomAt(c.x, c.y, 1.2);
    });
    zoomLabel.addEventListener("click", () => {
        const c = centerClient();
        zoomAt(c.x, c.y, 1 / view.scale);
    });
    zoomFit.addEventListener("click", fitOutputFrame);
    syncZoomLabel();

    // ----- properties island -----------------------------------------------------------------
    function swatchRow(values, current, apply, { fillStyleSwatch = false } = {}) {
        const row = document.createElement("div");
        row.className = "row";
        for (const value of values) {
            const el = document.createElement("button");
            const isNone = value === "rgba(0,0,0,0)";
            el.className = `swatch${isNone ? " none" : ""}`;
            if (!isNone) el.style.background = value;
            if (value === "#ffffff") el.style.borderColor = "#5a6572";
            if (current === value) el.classList.add("active");
            el.title = isNone ? "No fill" : value;
            el.addEventListener("click", () => apply(value));
            row.appendChild(el);
        }
        const custom = document.createElement("input");
        custom.type = "color";
        custom.className = "swatch-custom";
        custom.title = "Custom color";
        custom.value = rgbToHex(current);
        custom.addEventListener("change", () => apply(fillStyleSwatch ? `${custom.value}cc` : custom.value));
        row.appendChild(custom);
        return row;
    }

    function chipRow(entries) {
        const row = document.createElement("div");
        row.className = "row";
        for (const { label, title, active, danger, action } of entries) {
            const el = document.createElement("button");
            el.className = `chip-btn${active ? " active" : ""}${danger ? " danger" : ""}`;
            el.textContent = label;
            if (title) el.title = title;
            el.addEventListener("click", action);
            row.appendChild(el);
        }
        return row;
    }

    function rowLabel(text) {
        const el = document.createElement("div");
        el.className = "row-label";
        el.textContent = text;
        return el;
    }

    function renderProps() {
        if (!selected) {
            propsEl.hidden = true;
            propsEl.replaceChildren();
            return;
        }
        const item = selected;
        propsEl.hidden = false;
        propsEl.replaceChildren();

        if (item.type !== "image") {
            propsEl.append(
                rowLabel(item.type === "text" ? "Text color" : "Stroke"),
                swatchRow(COLOR_PRESETS, item.color || "#1b1f24", (value) => {
                    pushHistory();
                    item.color = value;
                    renderProps();
                    commit();
                }),
            );
        }

        if (item.type === "rect" || item.type === "ellipse") {
            propsEl.append(
                rowLabel("Fill"),
                swatchRow(FILL_PRESETS, item.fill || "rgba(0,0,0,0)", (value) => {
                    pushHistory();
                    item.fill = value;
                    renderProps();
                    commit();
                }, { fillStyleSwatch: true }),
            );
        }

        if (item.type !== "text" && item.type !== "image") {
            propsEl.append(
                rowLabel("Stroke width"),
                chipRow(STROKE_PRESETS.map((value, index) => ({
                    label: ["S", "M", "L"][index],
                    title: `${value}px`,
                    active: (item.strokeWidth || 3) === value,
                    action: () => {
                        pushHistory();
                        item.strokeWidth = value;
                        renderProps();
                        commit();
                    },
                }))),
            );
        }

        if (item.type === "text") {
            propsEl.append(
                rowLabel("Font size"),
                chipRow(FONT_PRESETS.map((value, index) => ({
                    label: ["S", "M", "L"][index],
                    title: `${value}px`,
                    active: (item.fontSize || 24) === value,
                    action: () => {
                        pushHistory();
                        item.fontSize = value;
                        renderProps();
                        commit();
                    },
                }))),
            );
        }

        if (item.type === "image") {
            const order = Number(item.keyframe) > 0 ? ` ${item.keyframe}` : "";
            propsEl.append(
                rowLabel("Keyframe"),
                chipRow([{
                    label: Number(item.keyframe) > 0 ? `★ Keyframe${order}` : "☆ Mark keyframe",
                    title: "Include this image in the keyframes output, in marked order (K)",
                    active: Number(item.keyframe) > 0,
                    action: () => toggleKeyframe(item),
                }]),
            );
        }

        propsEl.append(
            rowLabel("Arrange"),
            chipRow([
                {
                    label: "Front",
                    action: () => reorder(item, 1),
                },
                {
                    label: "Back",
                    action: () => reorder(item, -1),
                },
                {
                    label: "Copy",
                    title: "Duplicate (Ctrl+D)",
                    action: () => duplicate(item),
                },
                {
                    label: "✕",
                    title: "Delete (Del)",
                    danger: true,
                    action: deleteSelected,
                },
            ]),
        );
    }

    function reorder(item, direction) {
        const index = board.items.indexOf(item);
        if (index < 0) return;
        const target = direction > 0 ? board.items.length - 1 : 0;
        if (index === target) return;
        pushHistory();
        board.items.splice(index, 1);
        if (direction > 0) board.items.push(item);
        else board.items.unshift(item);
        commit();
    }

    function duplicate(item) {
        pushHistory();
        const copy = structuredClone({ ...item, _node: undefined });
        copy.id = crypto.randomUUID();
        copy.x = (copy.x || 0) + 24;
        copy.y = (copy.y || 0) + 24;
        if (copy.type === "line") {
            copy.x2 = (copy.x2 || 0) + 24;
            copy.y2 = (copy.y2 || 0) + 24;
        }
        if (Array.isArray(copy.points)) {
            copy.points = copy.points.map((p) => ({ x: p.x + 24, y: p.y + 24 }));
        }
        delete copy.keyframe;
        board.items.push(copy);
        select(copy);
        commit();
    }

    function deleteSelected() {
        if (!selected) return;
        pushHistory();
        board.items = board.items.filter((item) => item.id !== selected.id);
        selected = null;
        renumberKeyframes();
        renderProps();
        commit();
    }

    // ----- pointer interaction ------------------------------------------------------------------
    canvas.addEventListener("pointerdown", (event) => {
        canvas.focus();
        closeTextEditor();
        const point = toWorld(event);
        const panning = event.button === 1 || spaceHeld || tool === "hand";

        if (panning) {
            drag = { mode: "pan", startX: event.clientX, startY: event.clientY, viewX: view.x, viewY: view.y };
            canvas.style.cursor = "grabbing";
            canvas.setPointerCapture(event.pointerId);
            return;
        }
        if (event.button !== 0) return;

        if (tool === "pen") {
            pushHistory();
            const item = { id: crypto.randomUUID(), type: "pen", points: [point], color: "#1b1f24", strokeWidth: 4 };
            board.items.push(item);
            selected = item;
            drag = { mode: "pen", item };
            renderProps();
            canvas.setPointerCapture(event.pointerId);
            draw();
            return;
        }

        if (tool === "rect" || tool === "ellipse" || tool === "arrow") {
            pushHistory();
            const item = createItem(tool === "arrow" ? "line" : tool, point);
            selected = item;
            drag = { mode: "create", item, origin: point };
            renderProps();
            canvas.setPointerCapture(event.pointerId);
            draw();
            return;
        }

        if (tool === "text") {
            pushHistory();
            const item = createItem("text", point);
            select(item);
            setTool("select");
            openTextEditor(item);
            return;
        }

        // select tool
        const handle = handleAt(selected, point);
        if (handle) {
            pushHistory();
            if (selected.type === "line") {
                drag = { mode: "line-end", end: handle.id };
            } else {
                const b = itemBounds(selected);
                const anchor = {
                    nw: { x: b.x + b.w, y: b.y + b.h },
                    ne: { x: b.x, y: b.y + b.h },
                    sw: { x: b.x + b.w, y: b.y },
                    se: { x: b.x, y: b.y },
                }[handle.id];
                drag = {
                    mode: "resize",
                    anchor,
                    aspect: selected.type === "image" && b.h > 0 ? b.w / b.h : null,
                };
            }
            canvas.setPointerCapture(event.pointerId);
            return;
        }

        const hit = hitItem(point);
        select(hit);
        if (hit) {
            pushHistory();
            drag = { mode: "move", offsetX: point.x - hit.x, offsetY: point.y - hit.y, lastX: hit.x, lastY: hit.y };
            canvas.setPointerCapture(event.pointerId);
        }
    });

    canvas.addEventListener("pointermove", (event) => {
        if (!drag) {
            // Hover cursor feedback for handles.
            if (tool === "select" && selected) {
                const handle = handleAt(selected, toWorld(event));
                const next = handle
                    ? (handle.id === "nw" || handle.id === "se" ? "nwse-resize"
                        : handle.id === "ne" || handle.id === "sw" ? "nesw-resize" : "move")
                    : "default";
                if (next !== hoverCursor) {
                    hoverCursor = next;
                    canvas.style.cursor = next;
                }
            }
            return;
        }
        const point = toWorld(event);

        if (drag.mode === "pan") {
            view.x = drag.viewX + (event.clientX - drag.startX);
            view.y = drag.viewY + (event.clientY - drag.startY);
            draw();
            return;
        }
        if (drag.mode === "pen") {
            drag.item.points.push(point);
            draw();
            return;
        }
        if (drag.mode === "create") {
            const item = drag.item;
            if (item.type === "line") {
                item.x2 = point.x;
                item.y2 = point.y;
            } else {
                item.x = Math.min(drag.origin.x, point.x);
                item.y = Math.min(drag.origin.y, point.y);
                item.w = Math.abs(point.x - drag.origin.x);
                item.h = Math.abs(point.y - drag.origin.y);
            }
            draw();
            return;
        }
        if (drag.mode === "line-end" && selected) {
            if (drag.end === "start") {
                selected.x = point.x;
                selected.y = point.y;
            } else {
                selected.x2 = point.x;
                selected.y2 = point.y;
            }
            draw();
            return;
        }
        if (drag.mode === "resize" && selected) {
            let w = point.x - drag.anchor.x;
            let h = point.y - drag.anchor.y;
            if (drag.aspect && !event.altKey) {
                if (Math.abs(w) / drag.aspect > Math.abs(h)) {
                    h = (Math.abs(w) / drag.aspect) * Math.sign(h || 1);
                } else {
                    w = Math.abs(h) * drag.aspect * Math.sign(w || 1);
                }
            }
            selected.x = Math.min(drag.anchor.x, drag.anchor.x + w);
            selected.y = Math.min(drag.anchor.y, drag.anchor.y + h);
            selected.w = Math.max(MIN_SIZE, Math.abs(w));
            selected.h = Math.max(MIN_SIZE, Math.abs(h));
            draw();
            return;
        }
        if (drag.mode === "move" && selected) {
            const nextX = point.x - drag.offsetX;
            const nextY = point.y - drag.offsetY;
            const dx = nextX - drag.lastX;
            const dy = nextY - drag.lastY;
            drag.lastX = nextX;
            drag.lastY = nextY;
            selected.x += dx;
            selected.y += dy;
            if (selected.type === "line") {
                selected.x2 += dx;
                selected.y2 += dy;
            }
            if (Array.isArray(selected.points)) {
                selected.points = selected.points.map((p) => ({ x: p.x + dx, y: p.y + dy }));
            }
            draw();
        }
    });

    canvas.addEventListener("pointerup", (event) => {
        if (!drag) return;
        const finished = drag;
        drag = null;
        try {
            canvas.releasePointerCapture(event.pointerId);
        } catch {}

        if (finished.mode === "pan") {
            persistView();
            canvas.style.cursor = tool === "hand" ? "grab" : "default";
            return;
        }
        if (finished.mode === "create") {
            const item = finished.item;
            if (item.type !== "line" && (item.w < MIN_SIZE || item.h < MIN_SIZE)) {
                // A plain click: give the shape a comfortable default size.
                item.w = Math.max(item.w, 220);
                item.h = Math.max(item.h, 140);
            }
            if (item.type === "line") {
                const length = Math.hypot(item.x2 - item.x, item.y2 - item.y);
                if (length < MIN_SIZE) {
                    item.x2 = item.x + 200;
                    item.y2 = item.y + 70;
                }
            }
            setTool("select");
        }
        commit();
    });

    canvas.addEventListener("dblclick", (event) => {
        const point = toWorld(event);
        const hit = hitItem(point);
        if (hit?.type === "text") {
            select(hit);
            openTextEditor(hit);
            return;
        }
        if (hit?.type === "image") {
            toggleKeyframe(hit);
            select(hit);
            return;
        }
        if (!hit) {
            pushHistory();
            const item = createItem("text", point);
            select(item);
            openTextEditor(item);
        }
    });

    // Wheel: pan; Ctrl/Cmd+wheel: zoom to cursor. Never reaches LiteGraph.
    canvas.addEventListener("wheel", (event) => {
        event.preventDefault();
        event.stopPropagation();
        if (event.ctrlKey || event.metaKey) {
            zoomAt(event.clientX, event.clientY, Math.exp(-event.deltaY * 0.0012));
            return;
        }
        const dx = event.shiftKey ? event.deltaY : event.deltaX;
        const dy = event.shiftKey ? 0 : event.deltaY;
        view.x -= dx;
        view.y -= dy;
        persistView();
        closeTextEditor();
        draw();
    }, { passive: false });

    // ----- keyboard -----------------------------------------------------------------------------
    canvas.addEventListener("keydown", (event) => {
        const ctrlLike = event.ctrlKey || event.metaKey;
        if (event.key === " " && !spaceHeld) {
            spaceHeld = true;
            canvas.style.cursor = "grab";
            event.preventDefault();
            return;
        }
        if (ctrlLike && event.key.toLowerCase() === "z") {
            event.preventDefault();
            if (event.shiftKey) redo();
            else undo();
            return;
        }
        if (ctrlLike && event.key.toLowerCase() === "y") {
            event.preventDefault();
            redo();
            return;
        }
        if (ctrlLike && event.key.toLowerCase() === "d") {
            event.preventDefault();
            if (selected) duplicate(selected);
            return;
        }
        if (event.key === "Delete" || event.key === "Backspace") {
            if (selected) {
                event.preventDefault();
                deleteSelected();
            }
            return;
        }
        if (event.key === "Escape") {
            select(null);
            return;
        }
        const nudges = { ArrowUp: [0, -1], ArrowDown: [0, 1], ArrowLeft: [-1, 0], ArrowRight: [1, 0] };
        if (nudges[event.key] && selected) {
            event.preventDefault();
            const step = (event.shiftKey ? 10 : 1) / view.scale;
            const [dx, dy] = nudges[event.key];
            selected.x += dx * step;
            selected.y += dy * step;
            if (selected.type === "line") {
                selected.x2 += dx * step;
                selected.y2 += dy * step;
            }
            if (Array.isArray(selected.points)) {
                selected.points = selected.points.map((p) => ({ x: p.x + dx * step, y: p.y + dy * step }));
            }
            commit();
            return;
        }
        if (ctrlLike) return;
        const shortcuts = { v: "select", h: "hand", p: "pen", t: "text", r: "rect", o: "ellipse", a: "arrow" };
        const key = event.key.toLowerCase();
        if (shortcuts[key]) {
            setTool(shortcuts[key]);
            return;
        }
        if (key === "k" && selected?.type === "image") {
            toggleKeyframe(selected);
            return;
        }
        if (key === "f") {
            fitOutputFrame();
        }
    });

    canvas.addEventListener("keyup", (event) => {
        if (event.key === " ") {
            spaceHeld = false;
            canvas.style.cursor = tool === "hand" ? "grab" : "default";
        }
    });

    // ----- clipboard + drag-drop ----------------------------------------------------------------
    root.addEventListener("paste", (event) => {
        const blobs = [...(event.clipboardData?.items || [])]
            .filter((item) => item.type.startsWith("image/"))
            .map((item) => item.getAsFile())
            .filter(Boolean);
        if (blobs.length) {
            event.preventDefault();
            event.stopPropagation();
            placeImageBlobs(blobs, viewCenterWorld());
        }
    });

    canvas.addEventListener("dragover", (event) => {
        event.preventDefault();
        event.stopPropagation();
    });
    canvas.addEventListener("drop", (event) => {
        event.preventDefault();
        event.stopPropagation();
        const files = [...(event.dataTransfer?.files || [])].filter((file) => file.type.startsWith("image/"));
        if (files.length) placeImageBlobs(files, toWorld(event));
    });

    // ----- lifecycle ------------------------------------------------------------------------------
    new ResizeObserver(() => draw()).observe(root);
    const widthWidget = findWidget(node, "width");
    const heightWidget = findWidget(node, "height");
    const backgroundWidget = findWidget(node, "background");
    for (const widget of [widthWidget, heightWidget, backgroundWidget]) {
        if (!widget) continue;
        const original = widget.callback;
        widget.callback = (...args) => {
            original?.apply(widget, args);
            draw();
        };
    }

    renderProps();
    requestAnimationFrame(() => {
        if (!storedView) fitOutputFrame();
        else draw();
        syncZoomLabel();
    });
    return root;
}

// ----- node-frame info badge (shared toobusy pattern) -------------------------

function titleHeight() {
    return (typeof LiteGraph !== "undefined" && LiteGraph.NODE_TITLE_HEIGHT) || 30;
}

function wrapBadgeText(ctx, text, maxWidth) {
    const lines = [];
    let line = "";
    for (const word of String(text).split(/\s+/)) {
        const test = line ? `${line} ${word}` : word;
        if (line && ctx.measureText(test).width > maxWidth) {
            lines.push(line);
            line = word;
        } else {
            line = test;
        }
    }
    if (line) lines.push(line);
    return lines;
}

function drawInfoBadge(node, ctx) {
    if (node.flags && node.flags.collapsed) {
        node._toobusyInfoRect = null;
        return;
    }
    const r = 7;
    const cx = node.size[0] - 15;
    const cy = -titleHeight() * 0.5;
    node._toobusyInfoRect = { cx, cy, r };

    ctx.save();
    ctx.beginPath();
    ctx.arc(cx, cy, r, 0, Math.PI * 2);
    ctx.fillStyle = node._toobusyInfoHover ? ACCENT : "#6b7785";
    ctx.fill();
    ctx.fillStyle = "#ffffff";
    ctx.font = "bold 10px sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText("i", cx, cy + 0.5);
    ctx.restore();

    if (!node._toobusyInfoHover) return;

    ctx.save();
    const pad = 9;
    const maxTextW = 250;
    const lineH = 15;
    const titleH = 17;
    const dividerGap = 9;
    const footerH = 15;
    ctx.font = "11px sans-serif";
    const lines = wrapBadgeText(ctx, INFO_TEXT, maxTextW);
    const boxW = maxTextW + pad * 2;
    const boxH = pad + titleH + lines.length * lineH + dividerGap + footerH + pad;
    const bx = node.size[0] + 12;
    const by = cy;

    ctx.fillStyle = "rgba(20, 26, 32, 0.96)";
    ctx.strokeStyle = "#2d3642";
    ctx.lineWidth = 1;
    ctx.beginPath();
    if (ctx.roundRect) ctx.roundRect(bx, by, boxW, boxH, 6);
    else ctx.rect(bx, by, boxW, boxH);
    ctx.fill();
    ctx.stroke();

    ctx.textAlign = "left";
    ctx.textBaseline = "top";
    let y = by + pad;
    ctx.fillStyle = ACCENT;
    ctx.font = "bold 11px sans-serif";
    ctx.fillText(INFO_TITLE, bx + pad, y);
    y += titleH;
    ctx.fillStyle = "#cfd6de";
    ctx.font = "11px sans-serif";
    lines.forEach((ln, i) => ctx.fillText(ln, bx + pad, y + i * lineH));
    y += lines.length * lineH + dividerGap * 0.5;
    ctx.strokeStyle = "#2d3642";
    ctx.beginPath();
    ctx.moveTo(bx + pad, y);
    ctx.lineTo(bx + boxW - pad, y);
    ctx.stroke();
    y += dividerGap * 0.5;
    ctx.fillStyle = "#6b7785";
    ctx.font = "italic 10px sans-serif";
    ctx.fillText(INFO_SIGNATURE, bx + pad, y);
    ctx.restore();
}

app.registerExtension({
    name: "toobusy.storyboardBoard",
    beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== "ToobusyStoryboardBoard") {
            return;
        }

        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            onNodeCreated?.apply(this, arguments);
            hideWidget(this, boardWidget(this));

            const editor = makeBoardEditor(this);
            if (this.addDOMWidget) {
                this.addDOMWidget("storyboard_board", "div", editor, { serialize: false });
            } else {
                this.addWidget("button", "Inline board unsupported", "open", () => {}, { serialize: false });
            }
            this.size = [960, 760];
        };

        const onDrawForeground = nodeType.prototype.onDrawForeground;
        nodeType.prototype.onDrawForeground = function (ctx) {
            onDrawForeground?.apply(this, arguments);
            try {
                drawInfoBadge(this, ctx);
            } catch (err) {
                // Never let a draw glitch break the node.
            }
        };

        const onMouseMove = nodeType.prototype.onMouseMove;
        nodeType.prototype.onMouseMove = function (event, pos) {
            const rect = this._toobusyInfoRect;
            let hover = false;
            if (rect && Array.isArray(pos)) {
                const dx = pos[0] - rect.cx;
                const dy = pos[1] - rect.cy;
                hover = dx * dx + dy * dy <= (rect.r + 4) * (rect.r + 4);
            }
            if (hover !== !!this._toobusyInfoHover) {
                this._toobusyInfoHover = hover;
                this.setDirtyCanvas?.(true, true);
            }
            return onMouseMove?.apply(this, arguments);
        };
    },
});
