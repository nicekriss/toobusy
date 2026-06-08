import { app } from "../../scripts/app.js";

const MAX_LORA_SLOTS = 5;

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
        };

        const onConfigure = nodeType.prototype.onConfigure;
        nodeType.prototype.onConfigure = function () {
            onConfigure?.apply(this, arguments);
            updateLoraSlots(this);
        };
    },
});
