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

function findWidget(node, name) {
    return node.widgets?.find((widget) => widget.name === name);
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
    ];
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

    // The Add/Remove LoRA buttons belong to the Advanced view too.
    setWidgetVisible(node, node._toobusyAddBtn, advanced);
    setWidgetVisible(node, node._toobusyRemoveBtn, advanced);
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

            const slotWidget = findWidget(this, "lora_slots");
            if (slotWidget) {
                setWidgetVisible(this, slotWidget, false);
                const callback = slotWidget.callback;
                slotWidget.callback = (...args) => {
                    callback?.apply(slotWidget, args);
                    updateLoraSlots(this);
                };
            }

            this._toobusyAddBtn = this.addWidget("button", "Add LoRA slot", "add", () => {
                setActiveSlotCount(this, activeSlotCount(this) + 1);
            }, { serialize: false });

            this._toobusyRemoveBtn = this.addWidget("button", "Remove LoRA slot", "remove", () => {
                setActiveSlotCount(this, activeSlotCount(this) - 1);
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
    },
});
