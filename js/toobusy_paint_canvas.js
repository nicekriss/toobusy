import { app } from "../../scripts/app.js";

// toobusy Paint Canvas — an openCanvas-style painting surface inside the
// node: pressure brush / eraser / eyedropper, layers, zoom-pan, undo, and an
// auto-save toggle (off = commit to the workflow only via the Save button).
// Layers live as offscreen bitmaps at document resolution; the view canvas
// only displays them. The Python node composites the saved layer PNGs.

const ACCENT = "#7fc8ff";
const INFO_TITLE = "toobusy · Paint Canvas";
const INFO_TEXT =
    "Paint right in the graph: pressure brush, eraser, eyedropper, layers, " +
    "zoom/pan, undo. Every queued run takes the current painting as input — " +
    "sketch here, let ZIT ControlNet / img2img finish it. Auto-save commits " +
    "after each stroke; switch it off to commit only with the Save button.";
const INFO_SIGNATURE = "fold the graph — 너무바쁜베짱이";

const MAX_EDGE = 2048;
const MAX_STROKE_UNDO = 15;

function findWidget(node, name) {
    return node.widgets?.find((widget) => widget.name === name);
}

function canvasWidget(node) {
    return findWidget(node, "canvas_data");
}

function hideWidget(node, widget) {
    if (!widget) return;
    widget.type = "hidden";
    widget.computeSize = () => [0, -4];
    widget.hidden = true;
}

function makeLayerCanvas(width, height) {
    const canvas = document.createElement("canvas");
    canvas.width = Math.max(1, width);
    canvas.height = Math.max(1, height);
    return canvas;
}

let __layerCounter = 0;
function newLayer(width, height, name) {
    __layerCounter += 1;
    return {
        id: `layer_${Date.now().toString(36)}_${__layerCounter}`,
        name: name || `Layer ${__layerCounter}`,
        visible: true,
        opacity: 1.0,
        canvas: makeLayerCanvas(width, height),
    };
}

function makePaintEditor(node) {
    // ----- document state ----------------------------------------------------
    const widthWidget = findWidget(node, "width");
    const heightWidget = findWidget(node, "height");
    const backgroundWidget = findWidget(node, "background");
    const doc = {
        width: Math.min(MAX_EDGE, Number(widthWidget?.value) || 1024),
        height: Math.min(MAX_EDGE, Number(heightWidget?.value) || 1024),
    };
    let layers = [];
    let activeIndex = 0;
    let tool = "brush"; // brush | eraser | eyedropper | hand
    let spaceHeld = false;
    let altHeld = false;
    let dirty = false;
    const brush = { size: 24, hardness: 70, opacity: 100, color: "#1b1f24" };
    const history = [];
    const redoHistory = [];

    node.properties = node.properties || {};
    let autoSave = node.properties.toobusy_paint_autosave !== false; // default on

    const storedView = node.properties.toobusy_paint_view;
    const view = {
        x: Number(storedView?.x) || 40,
        y: Number(storedView?.y) || 40,
        scale: Number(storedView?.scale) || 0.5,
    };

    // ----- DOM ----------------------------------------------------------------
    const root = document.createElement("div");
    root.className = "toobusy-paint";
    root.innerHTML = `
        <style>
            .toobusy-paint {
                position: relative;
                width: 100%;
                height: 620px; /* runtime: follows node height */
                box-sizing: border-box;
                border-radius: 10px;
                overflow: hidden;
                background: #11151a;
                border: 1px solid #2d3642;
                font: 12px/1.4 system-ui, -apple-system, "Segoe UI", sans-serif;
                user-select: none;
                color: #e9edf1;
            }
            .toobusy-paint * { box-sizing: border-box; }
            .toobusy-paint canvas.paint-surface {
                position: absolute;
                inset: 0;
                width: 100%;
                height: 100%;
                display: block;
                outline: none;
                touch-action: none;
                cursor: none;
            }
            .toobusy-paint .island {
                position: absolute;
                display: flex;
                gap: 3px;
                align-items: center;
                padding: 4px;
                border-radius: 10px;
                background: rgba(23, 28, 34, 0.92);
                border: 1px solid #2d3642;
                box-shadow: 0 8px 24px rgba(0, 0, 0, 0.38);
                backdrop-filter: blur(8px);
            }
            .toobusy-paint .island.toolbar { top: 10px; left: 50%; transform: translateX(-50%); }
            .toobusy-paint .island.brushbox {
                top: 56px; left: 10px;
                flex-direction: column; align-items: stretch; gap: 7px;
                padding: 9px; width: 168px;
            }
            .toobusy-paint .island.layerbox {
                top: 56px; right: 10px;
                flex-direction: column; align-items: stretch; gap: 5px;
                padding: 9px; width: 188px;
                max-height: calc(100% - 120px);
                overflow-y: auto;
            }
            .toobusy-paint .island.zoom { left: 10px; bottom: 10px; }
            .toobusy-paint .tb-btn {
                width: 32px; height: 32px;
                display: flex; align-items: center; justify-content: center;
                border: none; border-radius: 8px;
                background: transparent; color: #c8d2dc;
                cursor: pointer; padding: 0; font-size: 14px;
            }
            .toobusy-paint .tb-btn svg { width: 16px; height: 16px; }
            .toobusy-paint .tb-btn:hover { background: #2a323c; color: #ffffff; }
            .toobusy-paint .tb-btn.active { background: rgba(127, 200, 255, 0.18); color: ${ACCENT}; }
            .toobusy-paint .tb-btn:disabled { opacity: 0.35; cursor: default; }
            .toobusy-paint .tb-sep { width: 1px; height: 20px; background: #2d3642; margin: 0 3px; }
            .toobusy-paint .save-btn {
                border: 1px solid #3a4450; border-radius: 8px;
                background: #1f262e; color: #d6dde4;
                font-size: 11px; padding: 6px 10px; cursor: pointer;
                white-space: nowrap;
            }
            .toobusy-paint .save-btn:hover { background: #2a323c; }
            .toobusy-paint .save-btn.dirty { border-color: #c8a13e; color: #ffd97a; }
            .toobusy-paint .row-label {
                font-size: 10px; text-transform: uppercase; letter-spacing: 0.05em;
                color: #7f8b99; margin-bottom: -3px;
                display: flex; justify-content: space-between;
            }
            .toobusy-paint .row-label .value { color: #aeb8c4; text-transform: none; }
            .toobusy-paint input[type="range"] {
                width: 100%; margin: 0; padding: 0;
                background: transparent; cursor: pointer;
            }
            .toobusy-paint input[type="color"] {
                width: 100%; height: 28px; padding: 0;
                border: 1px solid #3a4450; border-radius: 7px;
                background: none; cursor: pointer;
            }
            .toobusy-paint .swatch-row { display: flex; gap: 4px; }
            .toobusy-paint .swatch {
                width: 20px; height: 20px; border-radius: 5px;
                border: 1px solid #3a4450; cursor: pointer; padding: 0;
            }
            .toobusy-paint .layer-row {
                display: flex; gap: 3px; align-items: center;
                padding: 3px; border-radius: 7px; border: 1px solid transparent;
            }
            .toobusy-paint .layer-row.active { border-color: ${ACCENT}; background: rgba(127, 200, 255, 0.08); }
            .toobusy-paint .layer-row .eye {
                width: 22px; height: 22px; padding: 0;
                border: none; border-radius: 5px; background: transparent;
                color: #c8d2dc; cursor: pointer; font-size: 11px;
            }
            .toobusy-paint .layer-row .eye.off { color: #555f6a; }
            .toobusy-paint .layer-row .lname {
                flex: 1 1 auto; min-width: 0; text-align: left;
                background: transparent; border: none; color: #d6dde4;
                font-size: 11px; padding: 3px 4px; cursor: pointer;
                white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
            }
            .toobusy-paint .layer-row .mini {
                width: 20px; height: 22px; padding: 0;
                border: 1px solid #3a4450; border-radius: 5px;
                background: #1f262e; color: #c8d2dc; cursor: pointer; font-size: 10px;
            }
            .toobusy-paint .mini:disabled { opacity: 0.3; cursor: default; }
            .toobusy-paint .layer-actions { display: flex; gap: 4px; }
            .toobusy-paint .layer-actions .chip {
                flex: 1; border: 1px solid #3a4450; border-radius: 7px;
                background: #1f262e; color: #d6dde4; font-size: 11px;
                padding: 4px 0; cursor: pointer;
            }
            .toobusy-paint .layer-actions .chip:hover { background: #2a323c; }
            .toobusy-paint .zoom-label {
                min-width: 44px; text-align: center; font-size: 11px;
                color: #c8d2dc; cursor: pointer; border-radius: 6px; padding: 4px 2px;
            }
            .toobusy-paint .zoom-label:hover { background: #2a323c; }
            .toobusy-paint .hint {
                position: absolute; right: 12px; bottom: 10px;
                font-size: 10.5px; color: rgba(127, 139, 153, 0.85);
                text-align: right; pointer-events: none;
            }
            .toobusy-paint .autosave-label {
                display: flex; align-items: center; gap: 4px;
                font-size: 11px; color: #aeb8c4; cursor: pointer;
                padding: 0 6px; white-space: nowrap;
            }
            .toobusy-paint .autosave-label input { margin: 0; cursor: pointer; }
        </style>
        <canvas class="paint-surface" tabindex="0"></canvas>
        <div class="island toolbar"></div>
        <div class="island brushbox"></div>
        <div class="island layerbox"></div>
        <div class="island zoom"></div>
        <div class="hint">B brush · E eraser · I picker · Space pan · wheel zoom · [ ] size</div>
    `;

    const surface = root.querySelector("canvas.paint-surface");
    const toolbarEl = root.querySelector(".island.toolbar");
    const brushBox = root.querySelector(".island.brushbox");
    const layerBox = root.querySelector(".island.layerbox");
    const zoomEl = root.querySelector(".island.zoom");
    const ctx = surface.getContext("2d");

    for (const type of ["pointerdown", "pointerup", "dblclick", "contextmenu"]) {
        root.addEventListener(type, (event) => event.stopPropagation());
    }
    root.addEventListener("keydown", (event) => event.stopPropagation());

    // ----- coordinates (graph-zoom corrected, same fix as the whiteboard) -----
    const toLocal = (clientX, clientY) => {
        const rect = surface.getBoundingClientRect();
        const ratioX = rect.width > 0 ? surface.clientWidth / rect.width : 1;
        const ratioY = rect.height > 0 ? surface.clientHeight / rect.height : 1;
        return { x: (clientX - rect.left) * ratioX, y: (clientY - rect.top) * ratioY };
    };
    const toDoc = (clientX, clientY) => {
        const local = toLocal(clientX, clientY);
        return { x: (local.x - view.x) / view.scale, y: (local.y - view.y) / view.scale };
    };
    const persistView = () => {
        node.properties.toobusy_paint_view = { x: view.x, y: view.y, scale: view.scale };
    };

    // ----- serialization / save ------------------------------------------------
    function serializeDocument() {
        return JSON.stringify({
            version: 1,
            width: doc.width,
            height: doc.height,
            layers: layers.map((layer) => ({
                id: layer.id,
                name: layer.name,
                visible: layer.visible,
                opacity: layer.opacity,
                src: layer.canvas.toDataURL("image/png"),
            })),
        });
    }

    function commitToWidget() {
        const widget = canvasWidget(node);
        if (!widget) return;
        widget.value = serializeDocument();
        widget.callback?.(widget.value);
        dirty = false;
        syncSaveButton();
        node.setDirtyCanvas?.(true, true);
    }

    let saveTimer = null;
    function markDirty() {
        dirty = true;
        syncSaveButton();
        if (autoSave) {
            clearTimeout(saveTimer);
            saveTimer = setTimeout(commitToWidget, 350);
        }
    }

    // ----- history ---------------------------------------------------------------
    // Small documents snapshot raw ImageData (fast undo); large ones snapshot a
    // PNG data URL instead so 15 undo steps can't eat hundreds of MB.
    const BIG_DOC_PIXELS = 1024 * 1024;

    function layerSnapshot(layer) {
        if (layer.canvas.width * layer.canvas.height > BIG_DOC_PIXELS) {
            return { type: "stroke", layerId: layer.id, src: layer.canvas.toDataURL("image/png") };
        }
        const lctx = layer.canvas.getContext("2d");
        return {
            type: "stroke",
            layerId: layer.id,
            image: lctx.getImageData(0, 0, layer.canvas.width, layer.canvas.height),
        };
    }

    function pushStrokeHistory(layer) {
        try {
            history.push(layerSnapshot(layer));
        } catch {
            return;
        }
        while (history.length > MAX_STROKE_UNDO) history.shift();
        redoHistory.length = 0;
    }

    function pushStructureHistory() {
        history.push({ type: "structure", state: serializeDocument(), active: activeIndex });
        while (history.length > MAX_STROKE_UNDO) history.shift();
        redoHistory.length = 0;
    }

    function snapshotForRedo(entry) {
        if (entry.type === "stroke") {
            const layer = layers.find((candidate) => candidate.id === entry.layerId);
            if (!layer) return null;
            try {
                return layerSnapshot(layer);
            } catch {
                return null;
            }
        }
        return { type: "structure", state: serializeDocument(), active: activeIndex };
    }

    function applyHistoryEntry(entry) {
        if (entry.type === "stroke") {
            const layer = layers.find((candidate) => candidate.id === entry.layerId);
            if (!layer) return;
            const lctx = layer.canvas.getContext("2d");
            if (entry.image) {
                lctx.putImageData(entry.image, 0, 0);
                markDirty();
                draw();
            } else if (entry.src) {
                const img = new Image();
                img.onload = () => {
                    lctx.clearRect(0, 0, layer.canvas.width, layer.canvas.height);
                    lctx.drawImage(img, 0, 0);
                    markDirty();
                    draw();
                };
                img.src = entry.src;
            }
            return;
        }
        loadDocument(entry.state, entry.active);
        markDirty();
    }

    function undo() {
        const entry = history.pop();
        if (!entry) return;
        const redoEntry = snapshotForRedo(entry);
        if (redoEntry) redoHistory.push(redoEntry);
        applyHistoryEntry(entry);
    }

    function redo() {
        const entry = redoHistory.pop();
        if (!entry) return;
        const undoEntry = snapshotForRedo(entry);
        if (undoEntry) history.push(undoEntry);
        applyHistoryEntry(entry);
    }

    // ----- document load / resize -------------------------------------------------
    function loadDocument(json, nextActive = 0) {
        let parsed = null;
        try {
            parsed = JSON.parse(json || "");
        } catch {}
        const sourceLayers = Array.isArray(parsed?.layers) ? parsed.layers : [];
        layers = [];
        for (const source of sourceLayers) {
            const layer = newLayer(doc.width, doc.height, source.name);
            layer.id = source.id || layer.id;
            layer.visible = source.visible !== false;
            layer.opacity = Number.isFinite(Number(source.opacity)) ? Number(source.opacity) : 1.0;
            layers.push(layer);
            if (typeof source.src === "string" && source.src.startsWith("data:image/")) {
                const img = new Image();
                const target = layer;
                img.onload = () => {
                    const lctx = target.canvas.getContext("2d");
                    lctx.clearRect(0, 0, target.canvas.width, target.canvas.height);
                    lctx.drawImage(img, 0, 0);
                    draw();
                };
                img.src = source.src;
            }
        }
        if (!layers.length) {
            layers.push(newLayer(doc.width, doc.height, "Layer 1"));
        }
        activeIndex = Math.max(0, Math.min(layers.length - 1, nextActive));
        renderLayerPanel();
        draw();
    }

    function resizeDocument(width, height) {
        width = Math.max(1, Math.min(MAX_EDGE, Math.round(width)));
        height = Math.max(1, Math.min(MAX_EDGE, Math.round(height)));
        if (width === doc.width && height === doc.height) return;
        doc.width = width;
        doc.height = height;
        for (const layer of layers) {
            const next = makeLayerCanvas(width, height);
            next.getContext("2d").drawImage(layer.canvas, 0, 0);
            layer.canvas = next;
        }
        markDirty();
        draw();
    }

    // ----- rendering -----------------------------------------------------------------
    let checkerPattern = null;
    function getCheckerPattern() {
        if (checkerPattern) return checkerPattern;
        const tile = document.createElement("canvas");
        tile.width = 16;
        tile.height = 16;
        const tctx = tile.getContext("2d");
        tctx.fillStyle = "#272d34";
        tctx.fillRect(0, 0, 16, 16);
        tctx.fillStyle = "#2f3640";
        tctx.fillRect(0, 0, 8, 8);
        tctx.fillRect(8, 8, 8, 8);
        checkerPattern = ctx.createPattern(tile, "repeat");
        return checkerPattern;
    }

    let stroke = null; // { layer, temp, lastX, lastY, erase }
    let pointer = { x: -1, y: -1, inside: false };

    function draw() {
        const dpr = window.devicePixelRatio || 1;
        const wantW = Math.max(1, Math.round(surface.clientWidth * dpr));
        const wantH = Math.max(1, Math.round(surface.clientHeight * dpr));
        if (surface.width !== wantW || surface.height !== wantH) {
            surface.width = wantW;
            surface.height = wantH;
        }

        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        ctx.fillStyle = "#171c22";
        ctx.fillRect(0, 0, surface.clientWidth, surface.clientHeight);

        ctx.setTransform(dpr * view.scale, 0, 0, dpr * view.scale, dpr * view.x, dpr * view.y);

        // Document backdrop: checkerboard (transparency) + background color.
        ctx.save();
        ctx.fillStyle = getCheckerPattern();
        ctx.fillRect(0, 0, doc.width, doc.height);
        const background = String(backgroundWidget?.value || "#ffffff");
        ctx.fillStyle = background;
        ctx.fillRect(0, 0, doc.width, doc.height);
        ctx.restore();

        ctx.save();
        ctx.beginPath();
        ctx.rect(0, 0, doc.width, doc.height);
        ctx.clip();
        for (const layer of layers) {
            if (!layer.visible || layer.opacity <= 0) continue;
            ctx.globalAlpha = layer.opacity;
            ctx.drawImage(layer.canvas, 0, 0);
            // Live stroke preview rides on top of its layer.
            if (stroke && !stroke.erase && stroke.layer === layer) {
                ctx.globalAlpha = layer.opacity * (brush.opacity / 100);
                ctx.drawImage(stroke.temp, 0, 0);
            }
        }
        ctx.globalAlpha = 1;
        ctx.restore();

        // Document border.
        ctx.strokeStyle = "rgba(127, 200, 255, 0.45)";
        ctx.lineWidth = 1.5 / view.scale;
        ctx.strokeRect(0, 0, doc.width, doc.height);

        // Brush cursor outline.
        if (pointer.inside && (tool === "brush" || tool === "eraser") && !spaceHeld) {
            ctx.beginPath();
            ctx.arc(pointer.x, pointer.y, Math.max(0.5, brush.size / 2), 0, Math.PI * 2);
            ctx.strokeStyle = tool === "eraser" ? "rgba(255,255,255,0.85)" : "rgba(127,200,255,0.9)";
            ctx.lineWidth = 1 / view.scale;
            ctx.stroke();
        }
    }

    // ----- brush engine ----------------------------------------------------------------
    function stampAt(target, x, y, radius) {
        const tctx = target.getContext("2d");
        const hardness = Math.max(0, Math.min(1, brush.hardness / 100));
        if (hardness >= 0.99 || radius <= 1) {
            tctx.fillStyle = brush.color;
            tctx.beginPath();
            tctx.arc(x, y, radius, 0, Math.PI * 2);
            tctx.fill();
            return;
        }
        const gradient = tctx.createRadialGradient(x, y, radius * hardness, x, y, radius);
        gradient.addColorStop(0, brush.color);
        gradient.addColorStop(1, `${brush.color}00`);
        tctx.fillStyle = gradient;
        tctx.beginPath();
        tctx.arc(x, y, radius, 0, Math.PI * 2);
        tctx.fill();
    }

    function eraseStampAt(layer, x, y, radius) {
        const lctx = layer.canvas.getContext("2d");
        lctx.save();
        lctx.globalCompositeOperation = "destination-out";
        const hardness = Math.max(0, Math.min(1, brush.hardness / 100));
        const alpha = brush.opacity / 100;
        if (hardness >= 0.99) {
            lctx.globalAlpha = alpha;
            lctx.fillStyle = "#000000";
            lctx.beginPath();
            lctx.arc(x, y, radius, 0, Math.PI * 2);
            lctx.fill();
        } else {
            const gradient = lctx.createRadialGradient(x, y, radius * hardness, x, y, radius);
            gradient.addColorStop(0, `rgba(0,0,0,${alpha})`);
            gradient.addColorStop(1, "rgba(0,0,0,0)");
            lctx.fillStyle = gradient;
            lctx.beginPath();
            lctx.arc(x, y, radius, 0, Math.PI * 2);
            lctx.fill();
        }
        lctx.restore();
    }

    function strokeSegment(fromX, fromY, toX, toY, pressure) {
        const radius = Math.max(0.5, (brush.size / 2) * (stroke.pen ? Math.max(0.05, pressure) : 1));
        const distance = Math.hypot(toX - fromX, toY - fromY);
        const spacing = Math.max(0.6, radius * 0.25);
        const steps = Math.max(1, Math.ceil(distance / spacing));
        for (let i = 1; i <= steps; i += 1) {
            const t = i / steps;
            const x = fromX + (toX - fromX) * t;
            const y = fromY + (toY - fromY) * t;
            if (stroke.erase) {
                eraseStampAt(stroke.layer, x, y, radius);
            } else {
                stampAt(stroke.temp, x, y, radius);
            }
        }
    }

    function beginStroke(point, event) {
        const layer = layers[activeIndex];
        if (!layer) return;
        if (!layer.visible) {
            console.warn("[toobusy Paint Canvas] active layer is hidden — stroke skipped.");
            return;
        }
        pushStrokeHistory(layer);
        stroke = {
            layer,
            erase: tool === "eraser",
            temp: makeLayerCanvas(doc.width, doc.height),
            lastX: point.x,
            lastY: point.y,
            pen: event.pointerType === "pen",
        };
        strokeSegment(point.x, point.y, point.x, point.y, event.pressure || 1);
        draw();
    }

    function endStroke() {
        if (!stroke) return;
        if (!stroke.erase) {
            const lctx = stroke.layer.canvas.getContext("2d");
            lctx.save();
            lctx.globalAlpha = brush.opacity / 100;
            lctx.drawImage(stroke.temp, 0, 0);
            lctx.restore();
        }
        stroke = null;
        markDirty();
        draw();
    }

    function pickColor(point) {
        const probe = makeLayerCanvas(1, 1);
        const pctx = probe.getContext("2d");
        const background = String(backgroundWidget?.value || "#ffffff");
        pctx.fillStyle = background;
        pctx.fillRect(0, 0, 1, 1);
        for (const layer of layers) {
            if (!layer.visible || layer.opacity <= 0) continue;
            pctx.globalAlpha = layer.opacity;
            pctx.drawImage(layer.canvas, point.x, point.y, 1, 1, 0, 0, 1, 1);
        }
        const [r, g, b] = pctx.getImageData(0, 0, 1, 1).data;
        brush.color = `#${[r, g, b].map((v) => v.toString(16).padStart(2, "0")).join("")}`;
        renderBrushPanel();
    }

    // ----- pointer interaction ------------------------------------------------------------
    let panning = null;
    surface.addEventListener("pointerdown", (event) => {
        surface.focus();
        const isPan = event.button === 1 || spaceHeld || tool === "hand";
        if (isPan) {
            const local = toLocal(event.clientX, event.clientY);
            panning = { startX: local.x, startY: local.y, viewX: view.x, viewY: view.y };
            surface.setPointerCapture(event.pointerId);
            return;
        }
        if (event.button !== 0) return;
        const point = toDoc(event.clientX, event.clientY);
        if (tool === "eyedropper" || altHeld) {
            pickColor(point);
            return;
        }
        if (tool === "brush" || tool === "eraser") {
            surface.setPointerCapture(event.pointerId);
            beginStroke(point, event);
        }
    });

    surface.addEventListener("pointermove", (event) => {
        const point = toDoc(event.clientX, event.clientY);
        pointer = { x: point.x, y: point.y, inside: true };

        if (panning) {
            const local = toLocal(event.clientX, event.clientY);
            view.x = panning.viewX + (local.x - panning.startX);
            view.y = panning.viewY + (local.y - panning.startY);
            draw();
            return;
        }
        if (stroke) {
            // Use coalesced events for smooth fast strokes when available.
            const events = event.getCoalescedEvents?.() || [event];
            for (const sample of events) {
                const sub = toDoc(sample.clientX, sample.clientY);
                strokeSegment(stroke.lastX, stroke.lastY, sub.x, sub.y, sample.pressure || 1);
                stroke.lastX = sub.x;
                stroke.lastY = sub.y;
            }
            draw();
            return;
        }
        draw();
    });

    surface.addEventListener("pointerup", (event) => {
        try {
            surface.releasePointerCapture(event.pointerId);
        } catch {}
        if (panning) {
            panning = null;
            persistView();
            return;
        }
        endStroke();
    });

    surface.addEventListener("pointerleave", () => {
        pointer.inside = false;
        draw();
    });

    surface.addEventListener("wheel", (event) => {
        event.preventDefault();
        event.stopPropagation();
        const local = toLocal(event.clientX, event.clientY);
        const wx = (local.x - view.x) / view.scale;
        const wy = (local.y - view.y) / view.scale;
        const speed = event.ctrlKey || event.metaKey ? 0.0012 : 0.0018;
        view.scale = Math.max(0.05, Math.min(8, view.scale * Math.exp(-event.deltaY * speed)));
        view.x = local.x - wx * view.scale;
        view.y = local.y - wy * view.scale;
        persistView();
        syncZoomLabel();
        draw();
    }, { passive: false });

    // ----- keyboard --------------------------------------------------------------------------
    surface.addEventListener("keydown", (event) => {
        const ctrlLike = event.ctrlKey || event.metaKey;
        if (event.key === " " && !spaceHeld) {
            spaceHeld = true;
            event.preventDefault();
            draw();
            return;
        }
        if (event.key === "Alt") {
            altHeld = true;
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
        if (ctrlLike && event.key.toLowerCase() === "s") {
            event.preventDefault();
            commitToWidget();
            return;
        }
        if (ctrlLike) return;
        const key = event.key.toLowerCase();
        if (key === "[") {
            brush.size = Math.max(1, Math.round(brush.size / 1.15));
            renderBrushPanel();
            draw();
            return;
        }
        if (key === "]") {
            brush.size = Math.min(256, Math.max(brush.size + 1, Math.round(brush.size * 1.15)));
            renderBrushPanel();
            draw();
            return;
        }
        const tools = { b: "brush", e: "eraser", i: "eyedropper", h: "hand" };
        if (tools[key]) setTool(tools[key]);
    });

    surface.addEventListener("keyup", (event) => {
        if (event.key === " ") {
            spaceHeld = false;
            draw();
        }
        if (event.key === "Alt") altHeld = false;
    });

    // ----- toolbar ------------------------------------------------------------------------------
    const toolButtons = new Map();
    function toolbarButton(label, title, action, toggles = null) {
        const el = document.createElement("button");
        el.className = "tb-btn";
        el.textContent = label;
        el.title = title;
        el.addEventListener("pointerdown", (event) => event.preventDefault());
        el.addEventListener("click", action);
        toolbarEl.appendChild(el);
        if (toggles) toolButtons.set(toggles, el);
        return el;
    }
    function setTool(next) {
        tool = next;
        for (const [name, el] of toolButtons) {
            el.classList.toggle("active", name === tool);
        }
        surface.style.cursor = tool === "hand" ? "grab" : "none";
        surface.focus();
        draw();
    }

    toolbarButton("🖌", "Brush (B)", () => setTool("brush"), "brush");
    toolbarButton("◫", "Eraser (E)", () => setTool("eraser"), "eraser");
    toolbarButton("💧", "Eyedropper (I, or hold Alt)", () => setTool("eyedropper"), "eyedropper");
    toolbarButton("✋", "Pan (H or Space)", () => setTool("hand"), "hand");
    const sep1 = document.createElement("div");
    sep1.className = "tb-sep";
    toolbarEl.appendChild(sep1);
    toolbarButton("↶", "Undo (Ctrl+Z)", undo);
    toolbarButton("↷", "Redo (Ctrl+Shift+Z)", redo);
    const sep2 = document.createElement("div");
    sep2.className = "tb-sep";
    toolbarEl.appendChild(sep2);

    const saveButton = document.createElement("button");
    saveButton.className = "save-btn";
    saveButton.title = "Commit the painting to the node (Ctrl+S). Queued runs use the last committed state.";
    saveButton.addEventListener("click", commitToWidget);
    toolbarEl.appendChild(saveButton);

    const autosaveLabel = document.createElement("label");
    autosaveLabel.className = "autosave-label";
    const autosaveInput = document.createElement("input");
    autosaveInput.type = "checkbox";
    autosaveInput.checked = autoSave;
    autosaveLabel.append(autosaveInput, document.createTextNode("auto"));
    autosaveLabel.title = "Auto-save: commit to the node after every stroke. Off = only the Save button commits.";
    autosaveInput.addEventListener("change", () => {
        autoSave = autosaveInput.checked;
        node.properties.toobusy_paint_autosave = autoSave;
        if (autoSave && dirty) commitToWidget();
    });
    toolbarEl.appendChild(autosaveLabel);

    function syncSaveButton() {
        saveButton.textContent = dirty ? "Save ●" : "Saved";
        saveButton.classList.toggle("dirty", dirty);
    }
    syncSaveButton();
    setTool("brush");

    // ----- brush panel -----------------------------------------------------------------------
    function labeledSlider(parent, label, min, max, value, format, onInput) {
        const head = document.createElement("div");
        head.className = "row-label";
        const title = document.createElement("span");
        title.textContent = label;
        const display = document.createElement("span");
        display.className = "value";
        display.textContent = format(value);
        head.append(title, display);
        const input = document.createElement("input");
        input.type = "range";
        input.min = String(min);
        input.max = String(max);
        input.value = String(value);
        input.addEventListener("pointerdown", (event) => event.stopPropagation());
        input.addEventListener("input", () => {
            const next = Number(input.value);
            display.textContent = format(next);
            onInput(next);
        });
        parent.append(head, input);
        return input;
    }

    const RECENT_COLORS = ["#1b1f24", "#e03131", "#f08c00", "#2f9e44", "#1971c2", "#ffffff"];
    function renderBrushPanel() {
        brushBox.replaceChildren();

        const colorLabel = document.createElement("div");
        colorLabel.className = "row-label";
        colorLabel.textContent = "Color";
        const colorInput = document.createElement("input");
        colorInput.type = "color";
        colorInput.value = brush.color;
        colorInput.addEventListener("input", () => {
            brush.color = colorInput.value;
        });
        const swatchRow = document.createElement("div");
        swatchRow.className = "swatch-row";
        for (const color of RECENT_COLORS) {
            const swatch = document.createElement("button");
            swatch.className = "swatch";
            swatch.style.background = color;
            swatch.title = color;
            swatch.addEventListener("click", () => {
                brush.color = color;
                renderBrushPanel();
            });
            swatchRow.appendChild(swatch);
        }
        brushBox.append(colorLabel, colorInput, swatchRow);

        labeledSlider(brushBox, "Size", 1, 256, brush.size, (v) => `${Math.round(v)}px`, (v) => {
            brush.size = v;
            draw();
        });
        labeledSlider(brushBox, "Hardness", 0, 100, brush.hardness, (v) => `${Math.round(v)}%`, (v) => {
            brush.hardness = v;
        });
        labeledSlider(brushBox, "Opacity", 1, 100, brush.opacity, (v) => `${Math.round(v)}%`, (v) => {
            brush.opacity = v;
        });
    }
    renderBrushPanel();

    // ----- layer panel ------------------------------------------------------------------------
    function renderLayerPanel() {
        layerBox.replaceChildren();
        const head = document.createElement("div");
        head.className = "row-label";
        head.textContent = "Layers";
        layerBox.appendChild(head);

        // Top layer first in the list.
        for (let index = layers.length - 1; index >= 0; index -= 1) {
            const layer = layers[index];
            const row = document.createElement("div");
            row.className = `layer-row${index === activeIndex ? " active" : ""}`;

            const eye = document.createElement("button");
            eye.className = `eye${layer.visible ? "" : " off"}`;
            eye.textContent = layer.visible ? "👁" : "—";
            eye.title = "Toggle visibility";
            eye.addEventListener("click", () => {
                pushStructureHistory();
                layer.visible = !layer.visible;
                markDirty();
                renderLayerPanel();
                draw();
            });

            const name = document.createElement("button");
            name.className = "lname";
            name.textContent = layer.name;
            name.title = "Select layer";
            name.addEventListener("click", () => {
                activeIndex = index;
                renderLayerPanel();
            });

            const up = document.createElement("button");
            up.className = "mini";
            up.textContent = "▲";
            up.title = "Move up";
            up.disabled = index === layers.length - 1;
            up.addEventListener("click", () => {
                pushStructureHistory();
                [layers[index], layers[index + 1]] = [layers[index + 1], layers[index]];
                if (activeIndex === index) activeIndex = index + 1;
                else if (activeIndex === index + 1) activeIndex = index;
                markDirty();
                renderLayerPanel();
                draw();
            });

            const down = document.createElement("button");
            down.className = "mini";
            down.textContent = "▼";
            down.title = "Move down";
            down.disabled = index === 0;
            down.addEventListener("click", () => {
                pushStructureHistory();
                [layers[index], layers[index - 1]] = [layers[index - 1], layers[index]];
                if (activeIndex === index) activeIndex = index - 1;
                else if (activeIndex === index - 1) activeIndex = index;
                markDirty();
                renderLayerPanel();
                draw();
            });

            const del = document.createElement("button");
            del.className = "mini";
            del.textContent = "✕";
            del.title = "Delete layer";
            del.disabled = layers.length <= 1;
            del.addEventListener("click", () => {
                pushStructureHistory();
                layers.splice(index, 1);
                activeIndex = Math.max(0, Math.min(layers.length - 1, activeIndex));
                markDirty();
                renderLayerPanel();
                draw();
            });

            row.append(eye, name, up, down, del);
            layerBox.appendChild(row);
        }

        // Active layer opacity.
        const active = layers[activeIndex];
        if (active) {
            labeledSlider(layerBox, "Layer opacity", 0, 100, Math.round(active.opacity * 100), (v) => `${Math.round(v)}%`, (v) => {
                active.opacity = v / 100;
                markDirty();
                draw();
            });
        }

        const actions = document.createElement("div");
        actions.className = "layer-actions";
        const add = document.createElement("button");
        add.className = "chip";
        add.textContent = "＋ Layer";
        add.addEventListener("click", () => {
            pushStructureHistory();
            const layer = newLayer(doc.width, doc.height);
            layers.splice(activeIndex + 1, 0, layer);
            activeIndex += 1;
            markDirty();
            renderLayerPanel();
            draw();
        });
        const merge = document.createElement("button");
        merge.className = "chip";
        merge.textContent = "Merge ↓";
        merge.title = "Merge the active layer into the one below";
        merge.disabled = activeIndex === 0;
        merge.addEventListener("click", () => {
            if (activeIndex === 0) return;
            pushStructureHistory();
            const top = layers[activeIndex];
            const bottom = layers[activeIndex - 1];
            const bctx = bottom.canvas.getContext("2d");
            bctx.save();
            bctx.globalAlpha = top.opacity;
            if (top.visible) bctx.drawImage(top.canvas, 0, 0);
            bctx.restore();
            layers.splice(activeIndex, 1);
            activeIndex -= 1;
            markDirty();
            renderLayerPanel();
            draw();
        });
        actions.append(add, merge);
        layerBox.appendChild(actions);
    }

    // ----- zoom island ---------------------------------------------------------------------------
    const zoomOut = document.createElement("button");
    zoomOut.className = "tb-btn";
    zoomOut.textContent = "−";
    const zoomLabel = document.createElement("div");
    zoomLabel.className = "zoom-label";
    zoomLabel.title = "Reset zoom to 100%";
    const zoomIn = document.createElement("button");
    zoomIn.className = "tb-btn";
    zoomIn.textContent = "+";
    const zoomFit = document.createElement("button");
    zoomFit.className = "tb-btn";
    zoomFit.textContent = "⛶";
    zoomFit.title = "Fit the canvas";
    zoomEl.append(zoomOut, zoomLabel, zoomIn, zoomFit);
    const syncZoomLabel = () => {
        zoomLabel.textContent = `${Math.round(view.scale * 100)}%`;
    };
    function zoomBy(factor) {
        const cx = surface.clientWidth / 2;
        const cy = surface.clientHeight / 2;
        const wx = (cx - view.x) / view.scale;
        const wy = (cy - view.y) / view.scale;
        view.scale = Math.max(0.05, Math.min(8, view.scale * factor));
        view.x = cx - wx * view.scale;
        view.y = cy - wy * view.scale;
        persistView();
        syncZoomLabel();
        draw();
    }
    function fitCanvas() {
        const pad = 40;
        const scale = Math.min(
            (surface.clientWidth - pad * 2) / doc.width,
            (surface.clientHeight - pad * 2) / doc.height,
        );
        view.scale = Math.max(0.05, Math.min(8, scale));
        view.x = (surface.clientWidth - doc.width * view.scale) / 2;
        view.y = (surface.clientHeight - doc.height * view.scale) / 2;
        persistView();
        syncZoomLabel();
        draw();
    }
    zoomOut.addEventListener("click", () => zoomBy(1 / 1.2));
    zoomIn.addEventListener("click", () => zoomBy(1.2));
    zoomLabel.addEventListener("click", () => zoomBy(1 / view.scale));
    zoomFit.addEventListener("click", fitCanvas);
    syncZoomLabel();

    // ----- lifecycle -------------------------------------------------------------------------------
    new ResizeObserver(() => draw()).observe(root);
    for (const widget of [widthWidget, heightWidget]) {
        if (!widget) continue;
        const original = widget.callback;
        widget.callback = (...args) => {
            original?.apply(widget, args);
            resizeDocument(Number(widthWidget?.value) || doc.width, Number(heightWidget?.value) || doc.height);
        };
    }
    if (backgroundWidget) {
        const original = backgroundWidget.callback;
        backgroundWidget.callback = (...args) => {
            original?.apply(backgroundWidget, args);
            draw();
        };
    }

    loadDocument(canvasWidget(node)?.value);
    requestAnimationFrame(() => {
        if (!storedView) fitCanvas();
        else draw();
    });

    return root;
}

// ----- node-frame info badge (shared toobusy pattern) ---------------------------

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
    name: "toobusy.paintCanvas",
    beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== "ToobusyPaintCanvas") {
            return;
        }

        const RESERVED = 150; // title + width/height/background widgets
        const syncHeight = (node) => {
            const editor = node._toobusyPaintEl;
            if (!editor) return;
            editor.style.height = `${Math.max(380, Math.round((node.size?.[1] || 780) - RESERVED))}px`;
        };

        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            onNodeCreated?.apply(this, arguments);
            hideWidget(this, canvasWidget(this));

            const editor = makePaintEditor(this);
            this._toobusyPaintEl = editor;
            if (this.addDOMWidget) {
                this.addDOMWidget("paint_canvas", "div", editor, { serialize: false });
            } else {
                this.addWidget("button", "Inline canvas unsupported", "open", () => {}, { serialize: false });
            }
            this.size = [980, 800];
            syncHeight(this);
        };

        const onResize = nodeType.prototype.onResize;
        nodeType.prototype.onResize = function () {
            const result = onResize?.apply(this, arguments);
            syncHeight(this);
            return result;
        };

        const onConfigure = nodeType.prototype.onConfigure;
        nodeType.prototype.onConfigure = function () {
            const result = onConfigure?.apply(this, arguments);
            syncHeight(this);
            return result;
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
