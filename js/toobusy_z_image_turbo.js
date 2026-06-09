import { app } from "../../scripts/app.js";

const MAX_LORA_SLOTS = 5;

// Expert controls hidden by default (Basic view). Everything not listed here —
// positive, negative, ratio_preset, megapixels, batch_size, seed, steps — plus
// the LoRA controls (handled separately) make up the Basic surface.
const ADVANCED_WIDGETS = [
    "model_name",
    "clip_name",
    "vae_name",
    "divisible_by",
    "cfg",
    "sampler_name",
    "scheduler",
    "denoise",
    "aura_shift",
];

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

            // Transparency: show what this one node folds, so intermediate users
            // can see inside the "black box" instead of distrusting it.
            this.addWidget(
                "text",
                "folds",
                "Folds ~10 nodes: UNET+CLIP+VAE +(LoRA) → AuraFlow → Encode×2 → EmptyLatent / VAEEncode(img2img) → KSampler → Decode",
                () => {},
                { serialize: false },
            );

            // Always-visible resolution readout (sits right after the inputs,
            // above the LoRA/advanced buttons).
            this.addWidget("text", "resolution_readout", "", () => {}, { serialize: false });
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
    },
});
