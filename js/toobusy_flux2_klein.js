import { app } from "../../scripts/app.js";

const MAX_LORA_SLOTS = 5;
const MAX_REFERENCE_SLOTS = 3;
const ACCENT = "#7fc8ff";

const ADVANCED_WIDGETS = [
    "megapixels",
    "divisible_by",
    "batch_size",
    "sampler_name",
    "width",
    "height",
];

const OVERRIDE_INPUT_SPECS = [
    ["model_override", "MODEL"],
    ["clip_override", "CLIP"],
    ["vae_override", "VAE"],
];

const INFO_TITLE = "toobusy · Flux2 Klein";
const INFO_TEXT = [
    "Prompt guide:",
    "1) Say the final product/scene first.",
    "2) Add material, color, camera, background, and 'no human' when making product/detail shots.",
    "3) Reference #1 anchors the main image and default size; #2 and #3 add extra visual references in order.",
    "",
    "Template:",
    "product detail shot, [item], [material/color], studio lighting, clean background, [composition], no human",
].join(" ");
const INFO_SIGNATURE = "fold the graph — 너무바쁜베짱이";

function findWidget(node, name) {
    return node.widgets?.find((widget) => widget.name === name);
}

function setWidgetVisible(node, widget, visible) {
    if (!widget) return;
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
    const maxTextW = 300;
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

function makeReadoutWidget() {
    return {
        type: "toobusy_klein_readout",
        name: "klein_reference_readout",
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

function activeSlotCount(node, widgetName, maxSlots) {
    const widget = findWidget(node, widgetName);
    const value = Number(widget?.value ?? 0);
    return Math.max(0, Math.min(maxSlots, Number.isFinite(value) ? Math.round(value) : 0));
}

function setActiveSlotCount(node, widgetName, count, maxSlots, updater) {
    const widget = findWidget(node, widgetName);
    if (widget) widget.value = Math.max(0, Math.min(maxSlots, count));
    updater(node);
}

function loraSlotWidgets(node, slot) {
    return [
        findWidget(node, `lora_${slot}_enable`),
        findWidget(node, `lora_${slot}_name`),
        findWidget(node, `lora_${slot}_strength`),
        node[`_toobusyRemoveLora${slot}`],
    ];
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

function removeLoraSlot(node, slot) {
    const count = activeSlotCount(node, "lora_slots", MAX_LORA_SLOTS);
    if (slot < 1 || slot > count) return;
    for (let k = slot; k < count; k += 1) copyLoraSlot(node, k + 1, k);
    clearLoraSlot(node, count);
    setActiveSlotCount(node, "lora_slots", count - 1, MAX_LORA_SLOTS, updateLoraSlots);
}

function updateLoraSlots(node) {
    const advanced = isAdvanced(node);
    const count = activeSlotCount(node, "lora_slots", MAX_LORA_SLOTS);
    for (let slot = 1; slot <= MAX_LORA_SLOTS; slot += 1) {
        const visible = advanced && slot <= count;
        for (const widget of loraSlotWidgets(node, slot)) setWidgetVisible(node, widget, visible);
    }
    setWidgetVisible(node, node._toobusyAddLoraBtn, advanced);
    if (node._toobusyAddLoraBtn) {
        node._toobusyAddLoraBtn.name = count >= MAX_LORA_SLOTS ? "LoRA slots full" : "Add LoRA slot";
    }
}

function referenceSlotWidgets(node, slot) {
    return [
        findWidget(node, `reference_${slot}_enable`),
        node[`_toobusyRemoveReference${slot}`],
    ];
}

function setInputVisible(node, name, type, visible) {
    const idx = node.inputs ? node.inputs.findIndex((i) => i.name === name) : -1;
    const exists = idx >= 0;
    if (visible) {
        if (!exists) node.addInput(name, type);
    } else if (exists && node.inputs[idx].link == null) {
        node.removeInput(idx);
    }
}

function setOverrideInputsVisible(node, visible) {
    for (const [name, type] of OVERRIDE_INPUT_SPECS) {
        setInputVisible(node, name, type, visible);
    }
}

function updateReferenceReadout(node) {
    const readout = findWidget(node, "klein_reference_readout");
    if (!readout) return;
    const count = activeSlotCount(node, "reference_slots", MAX_REFERENCE_SLOTS);
    readout.value = `Klein references: #1 -> #2 -> #3 (${count}/${MAX_REFERENCE_SLOTS} visible)`;
    node.setDirtyCanvas?.(true, true);
}

function updateReferenceSlots(node) {
    const count = activeSlotCount(node, "reference_slots", MAX_REFERENCE_SLOTS);
    for (let slot = 1; slot <= MAX_REFERENCE_SLOTS; slot += 1) {
        const visible = slot <= count;
        setInputVisible(node, `reference_${slot}_image`, "IMAGE", visible);
        for (const widget of referenceSlotWidgets(node, slot)) setWidgetVisible(node, widget, visible);
    }
    setWidgetVisible(node, node._toobusyAddReferenceBtn, true);
    if (node._toobusyAddReferenceBtn) {
        node._toobusyAddReferenceBtn.name = count >= MAX_REFERENCE_SLOTS ? "Reference slots full" : "Add reference slot";
    }
    updateReferenceReadout(node);
}

function removeReferenceSlot(node, slot) {
    const widget = findWidget(node, `reference_${slot}_enable`);
    if (widget) {
        widget.value = false;
        widget.callback?.(false);
    }
    updateReferenceSlots(node);
}

function applyAdvanced(node) {
    const advanced = isAdvanced(node);
    for (const name of ADVANCED_WIDGETS) setWidgetVisible(node, findWidget(node, name), advanced);
    setOverrideInputsVisible(node, advanced);
    if (node._toobusyAdvButton) {
        node._toobusyAdvButton.name = advanced ? "Hide advanced settings" : "Show advanced settings";
    }
    updateLoraSlots(node);
    updateReferenceSlots(node);
}

app.registerExtension({
    name: "toobusy.flux2Klein",
    beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== "ToobusyFlux2Klein") return;

        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            onNodeCreated?.apply(this, arguments);

            const readout = makeReadoutWidget();
            if (this.addCustomWidget) this.addCustomWidget(readout);
            else (this.widgets = this.widgets || []).push(readout);

            const referenceSlotWidget = findWidget(this, "reference_slots");
            if (referenceSlotWidget) {
                setWidgetVisible(this, referenceSlotWidget, false);
                const callback = referenceSlotWidget.callback;
                referenceSlotWidget.callback = (...args) => {
                    callback?.apply(referenceSlotWidget, args);
                    updateReferenceSlots(this);
                };
            }

            for (let slot = 1; slot <= MAX_REFERENCE_SLOTS; slot += 1) {
                const button = this.addWidget("button", `Disable reference ${slot}`, "disable", () => {
                    removeReferenceSlot(this, slot);
                }, { serialize: false });
                this[`_toobusyRemoveReference${slot}`] = button;
                const widgets = this.widgets;
                const fromIndex = widgets.indexOf(button);
                if (fromIndex >= 0) widgets.splice(fromIndex, 1);
                const enable = findWidget(this, `reference_${slot}_enable`);
                const insertAt = enable ? widgets.indexOf(enable) + 1 : widgets.length;
                widgets.splice(insertAt, 0, button);
            }

            this._toobusyAddReferenceBtn = this.addWidget("button", "Add reference slot", "add", () => {
                const count = activeSlotCount(this, "reference_slots", MAX_REFERENCE_SLOTS);
                if (count >= MAX_REFERENCE_SLOTS) return;
                setActiveSlotCount(this, "reference_slots", count + 1, MAX_REFERENCE_SLOTS, updateReferenceSlots);
            }, { serialize: false });

            const loraSlotWidget = findWidget(this, "lora_slots");
            if (loraSlotWidget) {
                setWidgetVisible(this, loraSlotWidget, false);
                const callback = loraSlotWidget.callback;
                loraSlotWidget.callback = (...args) => {
                    callback?.apply(loraSlotWidget, args);
                    updateLoraSlots(this);
                };
            }

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

            this._toobusyAddLoraBtn = this.addWidget("button", "Add LoRA slot", "add", () => {
                const count = activeSlotCount(this, "lora_slots", MAX_LORA_SLOTS);
                if (count >= MAX_LORA_SLOTS) return;
                setActiveSlotCount(this, "lora_slots", count + 1, MAX_LORA_SLOTS, updateLoraSlots);
            }, { serialize: false });

            this._toobusyAdvButton = this.addWidget("button", "Show advanced settings", "advanced", () => {
                this.properties = this.properties || {};
                this.properties.toobusy_advanced = !isAdvanced(this);
                applyAdvanced(this);
            }, { serialize: false });

            applyAdvanced(this);
        };

        const onConfigure = nodeType.prototype.onConfigure;
        nodeType.prototype.onConfigure = function () {
            onConfigure?.apply(this, arguments);
            applyAdvanced(this);
        };

        const onDrawForeground = nodeType.prototype.onDrawForeground;
        nodeType.prototype.onDrawForeground = function (ctx) {
            onDrawForeground?.apply(this, arguments);
            try {
                drawInfoBadge(this, ctx);
            } catch (err) {
                // A tooltip draw issue should never break the node canvas.
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
