import { app } from "../../scripts/app.js";

const MAX_LORA_SLOTS = 5;

// Expert tuning hidden by default (Basic view). The model-load slots
// (model_name / clip_name / vae_name) are intentionally NOT here: they stay
// visible so a beginner can see and fix which model is loaded instead of
// wiring the wrong file and wondering why nothing works. Everything not listed
// here — model/clip/vae names, positive, negative, ratio_preset, megapixels,
// width, height, batch_size, seed, steps — plus the LoRA controls (handled
// separately) make up the Basic surface.
const ADVANCED_WIDGETS = [
    "divisible_by",
    "cfg",
    "sampler_name",
    "scheduler",
    "denoise",
    "aura_shift",
];

// toobusy signature accent — one calm blue tying the readout, the info badge,
// and the tooltip title together so the node reads as one family.
const ACCENT = "#7fc8ff";

// Hover tooltip behind the top-right info badge (replaces the old always-on
// "folds" text row): a title, the fold description, then a quiet signature.
const INFO_TITLE = "toobusy · Z-Image Turbo";
const INFO_TEXT =
    "Folds ~10 nodes into one: UNET + CLIP + VAE loaders + (LoRA) -> " +
    "ModelSamplingAuraFlow -> CLIPTextEncode x2 -> EmptyLatentImage " +
    "(or VAEEncode when an image is connected, i.e. img2img) -> KSampler -> VAEDecode.";
const INFO_SIGNATURE = "fold the graph — 너무바쁜베짱이";

// Mirror of z_image_turbo.py RATIO_PRESETS / _resolution_from_megapixels so the
// node can show the dimensions it will generate before the graph is queued.
const RATIO_PRESETS = {
    "1:1": [1, 1], "16:9": [16, 9], "9:16": [9, 16], "4:3": [4, 3], "3:4": [3, 4],
    "3:2": [3, 2], "2:3": [2, 3], "21:9": [21, 9], "9:21": [9, 21],
};

function roundToMultiple(value, divisor) {
    const d = Math.max(1, Math.round(divisor) || 1);
    return Math.max(d, Math.round(value / d) * d);
}

function resolutionFromMegapixels(ratioPreset, megapixels, divisibleBy) {
    const [rw, rh] = RATIO_PRESETS[ratioPreset] || RATIO_PRESETS["1:1"];
    const pixels = Math.max(0.01, Number(megapixels) || 0) * 1_000_000;
    const scale = Math.sqrt(pixels / (rw * rh));
    return [roundToMultiple(rw * scale, divisibleBy), roundToMultiple(rh * scale, divisibleBy)];
}

function findWidget(node, name) {
    return node.widgets?.find((widget) => widget.name === name);
}

function titleHeight() {
    return (typeof LiteGraph !== "undefined" && LiteGraph.NODE_TITLE_HEIGHT) || 30;
}

// Greedy word-wrap of `text` into lines no wider than `maxWidth` for `ctx`'s
// current font.
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

// Draw a small "i" badge in the node's top-right title corner, and — while
// hovered — a tooltip box with INFO_TEXT. Stores the badge's hit-circle on the
// node so onMouseMove can detect hover. Guarded so a draw error can never break
// the rest of the node.
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

    // Float the tooltip OUTSIDE the node — to the right of its right edge —
    // so it never covers the node's own inputs/widgets. onDrawForeground is
    // not clipped to the node body, so out-of-bounds coords render fine.
    const bx = node.size[0] + 12;
    const by = cy;                   // align the box top with the badge, extend down

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

    // Title (accent) — the node's name as a small header.
    ctx.fillStyle = ACCENT;
    ctx.font = "bold 11px sans-serif";
    ctx.fillText(INFO_TITLE, bx + pad, y);
    y += titleH;

    // Body — what the one node folds.
    ctx.fillStyle = "#cfd6de";
    ctx.font = "11px sans-serif";
    lines.forEach((ln, i) => ctx.fillText(ln, bx + pad, y + i * lineH));
    y += lines.length * lineH + dividerGap * 0.5;

    // Thin divider.
    ctx.strokeStyle = "#2d3642";
    ctx.beginPath();
    ctx.moveTo(bx + pad, y);
    ctx.lineTo(bx + boxW - pad, y);
    ctx.stroke();
    y += dividerGap * 0.5;

    // Quiet signature — the toobusy identity, one line, dim.
    ctx.fillStyle = "#6b7785";
    ctx.font = "italic 10px sans-serif";
    ctx.fillText(INFO_SIGNATURE, bx + pad, y);
    ctx.restore();
}

function imageInputConnected(node) {
    const input = node.inputs?.find((i) => i.name === "image");
    return !!(input && input.link != null);
}

function updateResolutionReadout(node) {
    const readout = findWidget(node, "resolution_readout");
    if (!readout) return;
    const div = Number(findWidget(node, "divisible_by")?.value ?? 32);
    const wv = Number(findWidget(node, "width")?.value ?? 0);
    const hv = Number(findWidget(node, "height")?.value ?? 0);
    const manual = wv > 0 && hv > 0;

    let w;
    let h;
    let source;
    if (manual) {
        w = roundToMultiple(wv, div);
        h = roundToMultiple(hv, div);
        source = "manual";
    } else {
        const ratio = String(findWidget(node, "ratio_preset")?.value ?? "1:1");
        const mp = Number(findWidget(node, "megapixels")?.value ?? 1);
        [w, h] = resolutionFromMegapixels(ratio, mp, div);
        source = `${ratio} @ ${mp.toFixed(2)}MP`;
    }

    if (imageInputConnected(node)) {
        // img2img: a connected image drives the size unless width/height are set.
        readout.value = manual
            ? `img2img -> ${w} x ${h} (source scaled)`
            : `img2img -> source image size`;
    } else {
        readout.value = `${source} -> ${w} x ${h}`;
    }
    node.setDirtyCanvas?.(true, true);
}

// Wrap a widget's callback so changing it also refreshes the readout.
function hookReadout(node, name) {
    const widget = findWidget(node, name);
    if (!widget) return;
    const original = widget.callback;
    widget.callback = (...args) => {
        original?.apply(widget, args);
        updateResolutionReadout(node);
    };
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

function loraSlotWidgets(node, slot) {
    return [
        findWidget(node, `lora_${slot}_enable`),
        findWidget(node, `lora_${slot}_name`),
        findWidget(node, `lora_${slot}_strength`),
        node[`_toobusyRemoveLora${slot}`],
    ];
}

// Copy one slot's three values into another (compact slots upward on remove).
function copyLoraSlot(node, from, to) {
    for (const field of ["enable", "name", "strength"]) {
        const src = findWidget(node, `lora_${from}_${field}`);
        const dst = findWidget(node, `lora_${to}_${field}`);
        if (src && dst) {
            dst.value = src.value;
            dst.callback?.(dst.value);
        }
    }
}

function clearLoraSlot(node, slot) {
    const defaults = { enable: false, name: "None", strength: 1.0 };
    for (const [field, value] of Object.entries(defaults)) {
        const widget = findWidget(node, `lora_${slot}_${field}`);
        if (widget) {
            widget.value = value;
            widget.callback?.(value);
        }
    }
}

// Remove a specific slot: slots below shift up, the freed last slot is reset,
// and the active count drops by one.
function removeLoraSlot(node, slot) {
    const count = activeSlotCount(node);
    if (slot < 1 || slot > count) return;
    for (let k = slot; k < count; k += 1) {
        copyLoraSlot(node, k + 1, k);
    }
    clearLoraSlot(node, count);
    setActiveSlotCount(node, count - 1);
}

function activeSlotCount(node) {
    const widget = findWidget(node, "lora_slots");
    const value = Number(widget?.value ?? 1);
    return Math.max(0, Math.min(MAX_LORA_SLOTS, Number.isFinite(value) ? Math.round(value) : 1));
}

function setActiveSlotCount(node, count) {
    const clamped = Math.max(0, Math.min(MAX_LORA_SLOTS, count));
    const widget = findWidget(node, "lora_slots");
    if (widget) {
        widget.value = clamped;
    }
    updateLoraSlots(node);
}

function updateLoraSlots(node) {
    const advanced = isAdvanced(node);
    const count = activeSlotCount(node);
    for (let slot = 1; slot <= MAX_LORA_SLOTS; slot += 1) {
        // LoRA is an advanced surface: slots only show in the Advanced view, and
        // then only up to the active slot count.
        const visible = advanced && slot <= count;
        for (const widget of loraSlotWidgets(node, slot)) {
            setWidgetVisible(node, widget, visible);
        }
    }

    // The Add LoRA button belongs to the Advanced view too. Per-slot remove
    // buttons are gated via loraSlotWidgets above (advanced && slot <= count).
    setWidgetVisible(node, node._toobusyAddBtn, advanced);
    if (node._toobusyAddBtn) {
        node._toobusyAddBtn.name = count >= MAX_LORA_SLOTS ? "LoRA slots full" : "Add LoRA slot";
    }

    node.setDirtyCanvas?.(true, true);
    app.graph?.setDirtyCanvas?.(true, true);
}

function applyAdvanced(node) {
    const advanced = isAdvanced(node);
    for (const name of ADVANCED_WIDGETS) {
        setWidgetVisible(node, findWidget(node, name), advanced);
    }
    if (node._toobusyAdvButton) {
        node._toobusyAdvButton.name = advanced ? "Hide advanced settings" : "Show advanced settings";
    }
    // updateLoraSlots handles the LoRA widgets/buttons and the canvas redraw.
    updateLoraSlots(node);
}

app.registerExtension({
    name: "toobusy.zImageTurbo",
    beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== "ToobusyZImageTurbo") {
            return;
        }

        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            onNodeCreated?.apply(this, arguments);

            // Transparency lives in the top-right "i" badge (hover for what this
            // node folds) — see drawInfoBadge — instead of an always-on text row.

            // Always-visible resolution readout (sits right after the inputs,
            // above the LoRA/advanced buttons).
            // Read-only resolution status line. Uses a customtext (DOM) widget
            // with readOnly so clicking it does nothing — a plain "text" widget
            // pops an edit prompt, which felt unfinished. Coloured to stand out
            // as a status readout rather than an input.
            const readout = this.addWidget("customtext", "resolution_readout", "", () => {}, { serialize: false });
            if (readout.inputEl) {
                const el = readout.inputEl;
                el.readOnly = true;
                el.style.fontSize = "12px";
                el.style.fontWeight = "600";
                el.style.color = ACCENT;
                el.style.textAlign = "center";
                el.style.background = "transparent";
                el.style.border = "none";
                el.style.boxShadow = "none";
                el.style.resize = "none";
                el.style.overflow = "hidden";
                el.style.cursor = "default";
                el.style.minHeight = "0px";
                el.style.height = "20px";
                el.rows = 1;
            }
            for (const name of ["ratio_preset", "megapixels", "divisible_by", "width", "height"]) {
                hookReadout(this, name);
            }

            const slotWidget = findWidget(this, "lora_slots");
            if (slotWidget) {
                setWidgetVisible(this, slotWidget, false);
                const callback = slotWidget.callback;
                slotWidget.callback = (...args) => {
                    callback?.apply(slotWidget, args);
                    updateLoraSlots(this);
                };
            }

            // Per-slot remove button under each slot, so you remove the LoRA you
            // see (not just the last one). Slots below shift up on remove.
            for (let slot = 1; slot <= MAX_LORA_SLOTS; slot += 1) {
                const button = this.addWidget("button", `✕ Remove LoRA ${slot}`, "remove", () => {
                    removeLoraSlot(this, slot);
                }, { serialize: false });
                this[`_toobusyRemoveLora${slot}`] = button;
                const widgets = this.widgets;
                const fromIndex = widgets.indexOf(button);
                if (fromIndex >= 0) widgets.splice(fromIndex, 1);
                const strength = findWidget(this, `lora_${slot}_strength`);
                const insertAt = strength ? widgets.indexOf(strength) + 1 : widgets.length;
                widgets.splice(insertAt, 0, button);
            }

            this._toobusyAddBtn = this.addWidget("button", "Add LoRA slot", "add", () => {
                if (activeSlotCount(this) >= MAX_LORA_SLOTS) return;
                setActiveSlotCount(this, activeSlotCount(this) + 1);
            }, { serialize: false });

            this._toobusyAdvButton = this.addWidget("button", "Show advanced settings", "advanced", () => {
                this.properties = this.properties || {};
                this.properties.toobusy_advanced = !isAdvanced(this);
                applyAdvanced(this);
            }, { serialize: false });

            applyAdvanced(this);
            updateResolutionReadout(this);
        };

        const onConfigure = nodeType.prototype.onConfigure;
        nodeType.prototype.onConfigure = function () {
            onConfigure?.apply(this, arguments);
            applyAdvanced(this);
            updateResolutionReadout(this);
        };

        // Connecting/disconnecting the image input flips the t2i/img2img readout.
        const onConnectionsChange = nodeType.prototype.onConnectionsChange;
        nodeType.prototype.onConnectionsChange = function () {
            const result = onConnectionsChange?.apply(this, arguments);
            updateResolutionReadout(this);
            return result;
        };

        // Top-right info badge + hover tooltip.
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
