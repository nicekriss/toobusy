import { app } from "../../scripts/app.js";

const MAX_EXTEND_SEGMENTS = 8;
// Auto mode plans internally, not from slots — mirror the Python sanity cap.
const MAX_AUTO_SEGMENTS = 64;

// ----- Auto ("target total") planning — mirrors _auto_plan in Python so the
// on-canvas readout shows exactly the chunk breakdown that will run. -----

function roundToGrid(value, minimum) {
    value = Math.round(Number(value) || 0);
    if (value < minimum) value = minimum;
    const remainder = (value - 1) % 4;
    let grid;
    if (remainder === 0) grid = value;
    else if (remainder <= 2) grid = value - remainder;
    else grid = value + (4 - remainder);
    while (grid < minimum) grid += 4;
    return grid;
}

function autoPlanLengths(target, chunkFrames, overlap, maxSegments) {
    overlap = Math.max(0, Math.round(Number(overlap) || 0));
    const chunk = roundToGrid(chunkFrames, 9);
    const goal = Math.max(1, Math.round(Number(target) || 0));
    const base = roundToGrid(Math.min(chunk, goal), 5);
    const lengths = [base];
    const perExtend = chunk - overlap;
    if (perExtend <= 0) return lengths;

    let remaining = goal - base;
    const minLast = Math.max(9, overlap + 4);
    let index = 1;
    while (remaining > 0 && index <= maxSegments) {
        if (remaining >= perExtend) {
            lengths.push(chunk);
            remaining -= perExtend;
            index += 1;
            continue;
        }
        const lastLength = roundToGrid(remaining + overlap, minLast);
        const contributed = lastLength - overlap;
        if (Math.abs(remaining - contributed) < remaining) lengths.push(lastLength);
        break;
    }
    return lengths;
}

function frameMode(node) {
    return findWidget(node, "frame_mode")?.value || "manual segments";
}

function isAuto(node) {
    return frameMode(node) === "target total";
}

// Expert tuning hidden by default (Basic view). The extend segment controls
// are NOT here — growing the video is the whole point of this node, so the
// +/- segment surface always shows. replacement_mode is deliberately NOT here
// either: animation vs replacement changes what the node fundamentally does
// (whose scene, whose character), so it stays on the Basic surface.
const ADVANCED_WIDGETS = [
    "sampler_name",
    "scheduler",
    "shift",
    "previous_frame_count",
    "color_match",
    "color_anchor",
    "pose_strength",
    "pose_start",
    "pose_end",
    "clip_vision_crop",
];

// toobusy signature accent — same calm blue as the other toobusy nodes.
const ACCENT = "#7fc8ff";

const INFO_TITLE = "toobusy · Wan SCAIL Extend Sampler";
const INFO_TEXT =
    "Folds the SCAIL-2 generate + extend graph into one node: CLIPTextEncode x2 " +
    "+ CLIPVisionEncode + ModelSamplingSD3 + KSamplerSelect + BasicScheduler, then " +
    "WanSCAILToVideo -> SamplerCustom -> VAEDecode per chunk with overlap trim and " +
    "Reinhard LAB seam color match. Every '+ Add extend' replaces an 18-node block.";
const INFO_SIGNATURE = "fold the graph — 너무바쁜베짱이";

function findWidget(node, name) {
    return node.widgets?.find((widget) => widget.name === name);
}

// Read-only status line drawn on the canvas (same custom widget pattern as the
// Z-Image readout): total output frames and rough seconds at 16 fps.
function makeReadoutWidget() {
    return {
        type: "toobusy_readout",
        name: "frames_readout",
        value: "",
        options: { serialize: false },
        serialize: false,
        draw(ctx, node, widgetWidth, widgetY, height) {
            ctx.save();
            ctx.textAlign = "center";
            ctx.textBaseline = "middle";
            ctx.font = "600 12px sans-serif";
            ctx.fillStyle = ACCENT;
            ctx.fillText(String(this.value || ""), widgetWidth * 0.5, widgetY + height * 0.5);
            ctx.restore();
        },
        computeSize(width) {
            return [width || 0, 22];
        },
    };
}

function titleHeight() {
    return (typeof LiteGraph !== "undefined" && LiteGraph.NODE_TITLE_HEIGHT) || 30;
}

function wrapText(ctx, text, maxWidth) {
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

// Top-right "i" badge + hover tooltip floated outside the node (same pattern
// as toobusy Z-Image Turbo). Guarded so a draw error never breaks the node.
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

    if (!node._toobusyInfoHover) {
        return;
    }

    ctx.save();
    const pad = 9;
    const maxTextW = 250;
    const lineH = 15;
    const titleH = 17;
    const dividerGap = 9;
    const footerH = 15;

    ctx.font = "11px sans-serif";
    const lines = wrapText(ctx, INFO_TEXT, maxTextW);
    const boxW = maxTextW + pad * 2;
    const boxH = pad + titleH + lines.length * lineH + dividerGap + footerH + pad;
    const bx = node.size[0] + 12;
    const by = cy;

    ctx.fillStyle = "rgba(20, 26, 32, 0.96)";
    ctx.strokeStyle = "#2d3642";
    ctx.lineWidth = 1;
    ctx.beginPath();
    if (ctx.roundRect) {
        ctx.roundRect(bx, by, boxW, boxH, 6);
    } else {
        ctx.rect(bx, by, boxW, boxH);
    }
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

function setWidgetVisible(node, widget, visible) {
    if (!widget) {
        return;
    }
    if (!widget._toobusyOriginalType) {
        widget._toobusyOriginalType = widget.type;
        widget._toobusyOriginalComputeSize = widget.computeSize;
    }
    widget.hidden = !visible;
    widget.disabled = !visible;
    widget.type = visible ? widget._toobusyOriginalType : "hidden";
    widget.computeSize = visible ? widget._toobusyOriginalComputeSize : () => [0, -4];
    node.setDirtyCanvas?.(true, true);
}

function isAdvanced(node) {
    return !!(node.properties && node.properties.toobusy_advanced);
}

// ----- Extend segments (same +/- slot pattern as the toobusy LoRA slots) ----

function activeSegmentCount(node) {
    const widget = findWidget(node, "extend_segments");
    const value = Number(widget?.value ?? 0);
    return Math.max(0, Math.min(MAX_EXTEND_SEGMENTS, Number.isFinite(value) ? Math.round(value) : 0));
}

function setActiveSegmentCount(node, count) {
    const clamped = Math.max(0, Math.min(MAX_EXTEND_SEGMENTS, count));
    const widget = findWidget(node, "extend_segments");
    if (widget) {
        widget.value = clamped;
        widget.callback?.(clamped);
    }
    updateSegments(node);
}

function copySegment(node, from, to) {
    const src = findWidget(node, `extend_${from}_frames`);
    const dst = findWidget(node, `extend_${to}_frames`);
    if (src && dst) {
        dst.value = src.value;
        dst.callback?.(dst.value);
    }
}

function clearSegment(node, slot) {
    const widget = findWidget(node, `extend_${slot}_frames`);
    if (widget) {
        widget.value = 81;
        widget.callback?.(81);
    }
}

// Remove one segment: segments below shift up, the freed last slot resets.
function removeSegment(node, slot) {
    const count = activeSegmentCount(node);
    if (slot < 1 || slot > count) return;
    for (let k = slot; k < count; k += 1) {
        copySegment(node, k + 1, k);
    }
    clearSegment(node, count);
    setActiveSegmentCount(node, count - 1);
}

function updateSegments(node) {
    const count = activeSegmentCount(node);
    for (let slot = 1; slot <= MAX_EXTEND_SEGMENTS; slot += 1) {
        const visible = slot <= count;
        setWidgetVisible(node, findWidget(node, `extend_${slot}_frames`), visible);
        setWidgetVisible(node, node[`_toobusyRemoveSegment${slot}`], visible);
    }
    if (node._toobusyAddBtn) {
        node._toobusyAddBtn.name = count >= MAX_EXTEND_SEGMENTS
            ? "Extend segments full"
            : "＋ Add extend segment";
    }
    updateFramesReadout(node);
    node.setDirtyCanvas?.(true, true);
    app.graph?.setDirtyCanvas?.(true, true);
}

function updateFramesReadout(node) {
    const readout = findWidget(node, "frames_readout");
    if (!readout) return;
    const overlap = Math.max(0, Number(findWidget(node, "previous_frame_count")?.value ?? 5));
    const mode = findWidget(node, "replacement_mode")?.value ? "Replacement" : "Animation";

    let parts;
    let extendCount;
    if (isAuto(node)) {
        const target = Math.max(0, Number(findWidget(node, "target_total_frames")?.value ?? 0));
        const chunk = Math.max(0, Number(findWidget(node, "base_frames")?.value ?? 81));
        const lengths = autoPlanLengths(target, chunk, overlap, MAX_AUTO_SEGMENTS);
        parts = lengths.map((len, i) => (i === 0 ? len : Math.max(0, len - overlap)));
        extendCount = lengths.length - 1;
    } else {
        const base = Math.max(0, Number(findWidget(node, "base_frames")?.value ?? 0));
        const count = activeSegmentCount(node);
        parts = [base];
        for (let slot = 1; slot <= count; slot += 1) {
            const frames = Math.max(0, Number(findWidget(node, `extend_${slot}_frames`)?.value ?? 0));
            parts.push(Math.max(0, frames - overlap));
        }
        extendCount = count;
    }

    const total = parts.reduce((sum, value) => sum + value, 0);
    const seconds = (total / 16).toFixed(1);
    const sum = parts.length > 1 ? `${parts.join(" + ")} = ` : "";
    const segLabel = isAuto(node) ? ` · ${extendCount} extend${extendCount === 1 ? "" : "s"}` : "";
    readout.value = `${sum}${total} frames · ~${seconds}s @ 16fps${segLabel} · ${mode}`;
    node.setDirtyCanvas?.(true, true);
}

function hookReadout(node, name) {
    const widget = findWidget(node, name);
    if (!widget) return;
    const original = widget.callback;
    widget.callback = (...args) => {
        original?.apply(widget, args);
        updateFramesReadout(node);
    };
}

// Show the extend surface (slots + Add) only in manual mode; show
// target_total_frames only in auto mode. base_frames stays in both (it's the
// per-chunk size auto mode extends with).
function applyMode(node) {
    const auto = isAuto(node);
    setWidgetVisible(node, findWidget(node, "target_total_frames"), auto);
    if (auto) {
        for (let slot = 1; slot <= MAX_EXTEND_SEGMENTS; slot += 1) {
            setWidgetVisible(node, findWidget(node, `extend_${slot}_frames`), false);
            setWidgetVisible(node, node[`_toobusyRemoveSegment${slot}`], false);
        }
        if (node._toobusyAddBtn) setWidgetVisible(node, node._toobusyAddBtn, false);
        updateFramesReadout(node);
        node.setDirtyCanvas?.(true, true);
        app.graph?.setDirtyCanvas?.(true, true);
    } else {
        if (node._toobusyAddBtn) setWidgetVisible(node, node._toobusyAddBtn, true);
        updateSegments(node);
    }
}

function applyAdvanced(node) {
    const advanced = isAdvanced(node);
    for (const name of ADVANCED_WIDGETS) {
        setWidgetVisible(node, findWidget(node, name), advanced);
    }
    if (node._toobusyAdvButton) {
        node._toobusyAdvButton.name = advanced ? "Hide advanced settings" : "Show advanced settings";
    }
    applyMode(node);
}

app.registerExtension({
    name: "toobusy.wanScailExtendSampler",
    beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== "ToobusyWanSCAILExtendSampler") {
            return;
        }

        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            onNodeCreated?.apply(this, arguments);

            // Hidden counter: the +/- buttons drive it, like lora_slots.
            const segmentsWidget = findWidget(this, "extend_segments");
            if (segmentsWidget) {
                setWidgetVisible(this, segmentsWidget, false);
                const callback = segmentsWidget.callback;
                segmentsWidget.callback = (...args) => {
                    callback?.apply(segmentsWidget, args);
                    updateSegments(this);
                };
            }

            // frame_mode + target_total_frames are appended last in INPUT_TYPES
            // (to keep saved widget order stable); move them right under
            // base_frames so the "how long" controls read as one group.
            {
                const widgets = this.widgets;
                const baseFrames = findWidget(this, "base_frames");
                let anchor = baseFrames ? widgets.indexOf(baseFrames) + 1 : widgets.length;
                for (const name of ["frame_mode", "target_total_frames"]) {
                    const widget = findWidget(this, name);
                    if (!widget) continue;
                    const from = widgets.indexOf(widget);
                    if (from >= 0) {
                        widgets.splice(from, 1);
                        if (from < anchor) anchor -= 1;
                    }
                    widgets.splice(anchor, 0, widget);
                    anchor += 1;
                }
            }
            const modeWidget = findWidget(this, "frame_mode");
            if (modeWidget) {
                const callback = modeWidget.callback;
                modeWidget.callback = (...args) => {
                    callback?.apply(modeWidget, args);
                    applyMode(this);
                };
            }

            // Per-segment remove button placed right under its frames widget.
            for (let slot = 1; slot <= MAX_EXTEND_SEGMENTS; slot += 1) {
                const button = this.addWidget("button", `✕ Remove extend ${slot}`, "remove", () => {
                    removeSegment(this, slot);
                }, { serialize: false });
                this[`_toobusyRemoveSegment${slot}`] = button;
                const widgets = this.widgets;
                const fromIndex = widgets.indexOf(button);
                if (fromIndex >= 0) widgets.splice(fromIndex, 1);
                const frames = findWidget(this, `extend_${slot}_frames`);
                const insertAt = frames ? widgets.indexOf(frames) + 1 : widgets.length;
                widgets.splice(insertAt, 0, button);
            }

            this._toobusyAddBtn = this.addWidget("button", "＋ Add extend segment", "add", () => {
                if (activeSegmentCount(this) >= MAX_EXTEND_SEGMENTS) return;
                setActiveSegmentCount(this, activeSegmentCount(this) + 1);
            }, { serialize: false });

            // Move the Add button right after the last segment row so the
            // whole extend surface reads as one block above seed/steps.
            {
                const widgets = this.widgets;
                const fromIndex = widgets.indexOf(this._toobusyAddBtn);
                if (fromIndex >= 0) widgets.splice(fromIndex, 1);
                const lastRemove = this[`_toobusyRemoveSegment${MAX_EXTEND_SEGMENTS}`];
                const anchor = lastRemove ? widgets.indexOf(lastRemove) + 1 : widgets.length;
                widgets.splice(anchor, 0, this._toobusyAddBtn);
            }

            // Total-frames readout right under the extend block.
            const readout = makeReadoutWidget();
            if (this.addCustomWidget) {
                this.addCustomWidget(readout);
            } else {
                (this.widgets = this.widgets || []).push(readout);
            }
            {
                const widgets = this.widgets;
                const fromIndex = widgets.indexOf(readout);
                if (fromIndex >= 0) widgets.splice(fromIndex, 1);
                const anchor = widgets.indexOf(this._toobusyAddBtn) + 1;
                widgets.splice(anchor, 0, readout);
            }
            hookReadout(this, "base_frames");
            hookReadout(this, "target_total_frames");
            hookReadout(this, "previous_frame_count");
            hookReadout(this, "replacement_mode");
            for (let slot = 1; slot <= MAX_EXTEND_SEGMENTS; slot += 1) {
                hookReadout(this, `extend_${slot}_frames`);
            }

            this._toobusyAdvButton = this.addWidget("button", "Show advanced settings", "advanced", () => {
                this.properties = this.properties || {};
                this.properties.toobusy_advanced = !isAdvanced(this);
                applyAdvanced(this);
            }, { serialize: false });

            applyAdvanced(this);
            updateFramesReadout(this);
        };

        const onConfigure = nodeType.prototype.onConfigure;
        nodeType.prototype.onConfigure = function () {
            onConfigure?.apply(this, arguments);
            applyAdvanced(this);
            updateFramesReadout(this);
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
