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
    if (node._toobusyRemoveLoraBtn) {
        node._toobusyRemoveLoraBtn.name = count <= 0 ? "No LoRA slots" : "Remove LoRA slot";
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

            this._toobusyAddLoraBtn = this.addWidget("button", "Add LoRA slot", "add", () => {
                if (activeSlotCount(this) >= MAX_LORA_SLOTS) return;
                setActiveSlotCount(this, activeSlotCount(this) + 1);
            }, { serialize: false });

            this._toobusyRemoveLoraBtn = this.addWidget("button", "No LoRA slots", "remove", () => {
                if (activeSlotCount(this) <= 0) return;
                setActiveSlotCount(this, activeSlotCount(this) - 1);
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
