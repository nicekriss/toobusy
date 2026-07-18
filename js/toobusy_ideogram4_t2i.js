import { app } from "../../scripts/app.js";

const MAX_LORA_SLOTS = 5;
const QUALITY_PRESETS = {
    Quality: { steps: 48, mu: 0.0, std: 1.5 },
    Default: { steps: 20, mu: 0.0, std: 1.75 },
    Turbo: { steps: 12, mu: 0.5, std: 1.75 },
};

function findWidget(node, name) {
    return node.widgets?.find((widget) => widget.name === name);
}

function numericWidgetValue(node, name, fallback) {
    const value = Number(findWidget(node, name)?.value);
    return Number.isFinite(value) ? value : fallback;
}

function resolvedSettingsText(node) {
    const quality = String(findWidget(node, "quality")?.value ?? "Turbo");
    const preset = QUALITY_PRESETS[quality];
    const manualSteps = Math.round(numericWidgetValue(node, "steps", 0));
    const isCustom = quality === "Custom";
    const steps = isCustom ? (manualSteps > 0 ? manualSteps : 20) : preset.steps;
    const mu = quality === "Custom" ? numericWidgetValue(node, "mu", 0.5) : preset.mu;
    const std = quality === "Custom" ? numericWidgetValue(node, "std", 1.75) : preset.std;
    const sampler = isCustom ? String(findWidget(node, "sampler_name")?.value ?? "euler") : "euler";
    const cfg = isCustom ? numericWidgetValue(node, "cfg", 7.0) : 7.0;
    const tailCfg = isCustom ? numericWidgetValue(node, "cfg_override", 3.0) : 3.0;
    const tailStart = isCustom ? numericWidgetValue(node, "cfg_override_start", 0.7) : 0.7;
    const tailEnd = isCustom ? numericWidgetValue(node, "cfg_override_end", 1.0) : 1.0;
    const sage = Boolean(findWidget(node, "use_sage_attention")?.value);
    return `${quality}: ${steps} steps  ·  ${sampler}  ·  μ ${mu} / σ ${std}\nCFG ${cfg} → ${tailCfg} @ ${Math.round(tailStart * 100)}–${Math.round(tailEnd * 100)}%  ·  Sage ${sage ? "ON" : "OFF"}`;
}

function updateResolvedSettings(node) {
    if (!node._toobusyResolvedSettings) return;
    node._toobusyResolvedSettings.value = resolvedSettingsText(node);
    node.setDirtyCanvas?.(true, true);
}

function watchResolvedSetting(node, name) {
    const widget = findWidget(node, name);
    if (!widget || widget._toobusyResolvedWatched) return;
    widget._toobusyResolvedWatched = true;
    const callback = widget.callback;
    widget.callback = function () {
        const result = callback?.apply(this, arguments);
        if (name === "quality") updatePresetControls(node);
        else updateResolvedSettings(node);
        return result;
    };
}

function updatePresetControls(node) {
    const isCustom = String(findWidget(node, "quality")?.value ?? "Turbo") === "Custom";
    for (const name of [
        "steps", "sampler_name", "cfg", "mu", "std",
        "cfg_override", "cfg_override_start", "cfg_override_end",
    ]) {
        setWidgetVisible(node, findWidget(node, name), isCustom);
    }
    updateResolvedSettings(node);
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

function loraSlotWidgets(node, slot) {
    return [
        findWidget(node, `lora_${slot}_enable`),
        findWidget(node, `lora_${slot}_name`),
        findWidget(node, `lora_${slot}_strength`),
        node[`_toobusyRemoveLora${slot}`],
    ];
}

function activeSlotCount(node) {
    const widget = findWidget(node, "lora_slots");
    const value = Number(widget?.value ?? 0);
    return Math.max(0, Math.min(MAX_LORA_SLOTS, Number.isFinite(value) ? Math.round(value) : 0));
}

function setActiveSlotCount(node, count) {
    const clamped = Math.max(0, Math.min(MAX_LORA_SLOTS, count));
    const widget = findWidget(node, "lora_slots");
    if (widget) widget.value = clamped;
    updateLoraSlots(node);
}

// Copy one slot's three values into another (used to compact slots upward when
// a slot in the middle is removed).
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

// Remove a specific slot: slots below it shift up to fill the gap, the freed
// last slot is reset to defaults, and the active count drops by one. This makes
// removal intuitive — you remove the LoRA you actually see, not just the last.
function removeLoraSlot(node, slot) {
    const count = activeSlotCount(node);
    if (slot < 1 || slot > count) return;
    for (let k = slot; k < count; k += 1) {
        copyLoraSlot(node, k + 1, k);
    }
    clearLoraSlot(node, count);
    setActiveSlotCount(node, count - 1);
}

function updateLoraSlots(node) {
    const count = activeSlotCount(node);
    for (let slot = 1; slot <= MAX_LORA_SLOTS; slot += 1) {
        const visible = slot <= count;
        for (const widget of loraSlotWidgets(node, slot)) {
            setWidgetVisible(node, widget, visible);
        }
    }

    if (node._toobusyAddLoraBtn) {
        node._toobusyAddLoraBtn.name = count >= MAX_LORA_SLOTS ? "LoRA slots full" : "Add LoRA slot";
    }

    node.setDirtyCanvas?.(true, true);
    app.graph?.setDirtyCanvas?.(true, true);
}

app.registerExtension({
    name: "toobusy.ideogram4T2I",
    beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== "ToobusyIdeogram4T2I") return;

        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            onNodeCreated?.apply(this, arguments);

            const readout = this.addWidget(
                "customtext",
                "Resolved settings",
                "",
                () => {},
                { serialize: false },
            );
            readout.inputEl?.setAttribute?.("readonly", "readonly");
            this._toobusyResolvedSettings = readout;

            // Keep the applied values visible directly below the quality selector.
            const widgets = this.widgets;
            const readoutIndex = widgets.indexOf(readout);
            if (readoutIndex >= 0) widgets.splice(readoutIndex, 1);
            const qualityWidget = findWidget(this, "quality");
            const qualityIndex = qualityWidget ? widgets.indexOf(qualityWidget) : -1;
            widgets.splice(qualityIndex >= 0 ? qualityIndex + 1 : widgets.length, 0, readout);

            for (const name of [
                "quality", "steps", "mu", "std", "cfg", "cfg_override",
                "cfg_override_start", "cfg_override_end", "use_sage_attention",
            ]) {
                watchResolvedSetting(this, name);
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

            // A per-slot remove button placed directly under each slot, so you
            // remove the LoRA you can see (not just the highest-numbered one).
            for (let slot = 1; slot <= MAX_LORA_SLOTS; slot += 1) {
                const button = this.addWidget("button", `✕ Remove LoRA ${slot}`, "remove", () => {
                    removeLoraSlot(this, slot);
                }, { serialize: false });
                this[`_toobusyRemoveLora${slot}`] = button;
                // addWidget appends to the end; move the button right after this
                // slot's strength widget so it sits with its slot.
                const widgets = this.widgets;
                const fromIndex = widgets.indexOf(button);
                if (fromIndex >= 0) widgets.splice(fromIndex, 1);
                const strength = findWidget(this, `lora_${slot}_strength`);
                const insertAt = strength ? widgets.indexOf(strength) + 1 : widgets.length;
                widgets.splice(insertAt, 0, button);
            }

            // "Add LoRA slot" stays at the bottom of the LoRA stack.
            this._toobusyAddLoraBtn = this.addWidget("button", "Add LoRA slot", "add", () => {
                if (activeSlotCount(this) >= MAX_LORA_SLOTS) return;
                setActiveSlotCount(this, activeSlotCount(this) + 1);
            }, { serialize: false });

            updateLoraSlots(this);
            updatePresetControls(this);
        };

        const onConfigure = nodeType.prototype.onConfigure;
        nodeType.prototype.onConfigure = function () {
            onConfigure?.apply(this, arguments);
            updateLoraSlots(this);
            updatePresetControls(this);
        };
    },
});
