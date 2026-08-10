import { app } from "../../scripts/app.js";

const ACCENT = "#7fc8ff";
const MAX_CHUNKS = 64;

function findWidget(node, name) {
    return node.widgets?.find((widget) => widget.name === name);
}

function roundToGrid(value, minimum = 5) {
    value = Math.max(minimum, Math.round(Number(value) || 0));
    const remainder = (value - 1) % 4;
    if (remainder === 0) return value;
    if (remainder <= 2) return value - remainder;
    return value + 4 - remainder;
}

function planChunks(total, perSampler) {
    const target = Math.max(1, Math.round(Number(total) || 1));
    const chunk = roundToGrid(perSampler);
    const lengths = [];
    let remaining = target;
    const base = roundToGrid(Math.min(chunk, remaining));
    lengths.push(base);
    remaining -= base;
    while (remaining > 0 && lengths.length < MAX_CHUNKS) {
        const length = remaining >= chunk - 1 ? chunk : roundToGrid(remaining + 1);
        lengths.push(length);
        remaining -= length - 1;
    }
    const produced = lengths.reduce((sum, length, index) => sum + length - (index ? 1 : 0), 0);
    return { target, chunk, lengths, crop: Math.max(0, produced - target) };
}

function makeReadout() {
    return {
        type: "toobusy_animate2_readout",
        name: "chunk_plan_readout",
        value: "",
        options: { serialize: false },
        serialize: false,
        draw(ctx, node, width, y, height) {
            ctx.save();
            ctx.textAlign = "center";
            ctx.textBaseline = "middle";
            ctx.font = "600 12px sans-serif";
            ctx.fillStyle = ACCENT;
            ctx.fillText(this.value, width * 0.5, y + height * 0.5);
            ctx.restore();
        },
        computeSize(width) {
            return [width || 0, 24];
        },
    };
}

function updateReadout(node) {
    const readout = findWidget(node, "chunk_plan_readout");
    if (!readout) return;
    const linkedTarget = node.inputs?.some(
        (input) => (input.name === "total_frames" || input.name === "total_frames_input") && input.link != null,
    );
    if (linkedTarget) {
        readout.value = "total resolved at run time · 1-frame overlap per chunk";
    } else {
        const plan = planChunks(
            findWidget(node, "total_frames")?.value,
            findWidget(node, "frames_per_sampler")?.value,
        );
        const crop = plan.crop ? ` · last crop ${plan.crop}` : "";
        readout.value = `${plan.target} frames · ${plan.lengths.length} samplers × up to ${plan.chunk}${crop}`;
    }
    node.setDirtyCanvas?.(true, true);
}

function hook(node, name) {
    const widget = findWidget(node, name);
    if (!widget) return;
    const callback = widget.callback;
    widget.callback = (...args) => {
        callback?.apply(widget, args);
        updateReadout(node);
    };
}

app.registerExtension({
    name: "toobusy.WanAnimate2LongSampler",
    beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== "ToobusyWanAnimate2LongSampler") return;

        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            onNodeCreated?.apply(this, arguments);
            const readout = makeReadout();
            if (this.addCustomWidget) this.addCustomWidget(readout);
            else (this.widgets = this.widgets || []).push(readout);
            hook(this, "total_frames");
            hook(this, "frames_per_sampler");
            updateReadout(this);
        };

        const onConfigure = nodeType.prototype.onConfigure;
        nodeType.prototype.onConfigure = function () {
            onConfigure?.apply(this, arguments);
            updateReadout(this);
        };

        const onConnectionsChange = nodeType.prototype.onConnectionsChange;
        nodeType.prototype.onConnectionsChange = function () {
            onConnectionsChange?.apply(this, arguments);
            updateReadout(this);
        };
    },
});
