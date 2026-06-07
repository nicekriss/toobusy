import { app } from "../../scripts/app.js";

// Mirror of ltx23_latent_prompt_nodes.py so the node can preview what it will
// produce (resolution, clip duration, audio state) before the graph is queued.
const RATIO_PRESETS = {
    "1:1": [1, 1], "16:9": [16, 9], "9:16": [9, 16], "4:3": [4, 3], "3:4": [3, 4],
    "3:2": [3, 2], "2:3": [2, 3], "21:9": [21, 9], "9:21": [9, 21],
};

function roundToMultiple(value, multiple) {
    const m = Math.max(1, Math.round(multiple) || 1);
    return Math.max(m, Math.round(value / m) * m);
}

function resolutionFromRatioMegapixels(ratioPreset, megapixels, divisibleBy) {
    const [rw, rh] = RATIO_PRESETS[ratioPreset] || RATIO_PRESETS["1:1"];
    const aspect = rw / rh;
    const area = Math.max(0.01, Number(megapixels) || 0) * 1_000_000;
    return [
        roundToMultiple(Math.sqrt(area * aspect), divisibleBy),
        roundToMultiple(Math.sqrt(area / aspect), divisibleBy),
    ];
}

function findWidget(node, name) {
    return node.widgets?.find((widget) => widget.name === name);
}

function audioConnected(node) {
    const input = node.inputs?.find((slot) => slot.name === "audio");
    return !!(input && input.link != null);
}

function buildReadout(node) {
    const ratio = String(findWidget(node, "ratio_preset")?.value ?? "16:9");
    const mp = Number(findWidget(node, "megapixels")?.value ?? 1);
    const div = Number(findWidget(node, "divisible_by")?.value ?? 32);
    const length = Number(findWidget(node, "length")?.value ?? 97);
    const fps = Number(findWidget(node, "frame_rate")?.value ?? 24);
    const useCustomAudio = !!findWidget(node, "use_custom_audio")?.value;

    const [w, h] = resolutionFromRatioMegapixels(ratio, mp, div);
    // Python length = round(duration * fps) + 1, so duration ~= (length - 1) / fps.
    const seconds = fps > 0 ? (length - 1) / fps : 0;

    let audioLine;
    if (!useCustomAudio) {
        audioLine = "custom audio: off (empty audio latent)";
    } else if (audioConnected(node)) {
        audioLine = "custom audio: ON (AUDIO connected)";
    } else {
        audioLine = "custom audio: ON — ⚠ connect an AUDIO input or turn it off";
    }

    return [
        `${ratio} @ ${mp.toFixed(2)}MP -> ${w} x ${h}`,
        `${length} frames @ ${fps} fps -> ~${seconds.toFixed(1)}s`,
        audioLine,
    ].join("\n");
}

function updateReadout(node) {
    const readout = findWidget(node, "av_readout");
    if (!readout) return;
    readout.value = buildReadout(node);
    node.setDirtyCanvas?.(true, true);
    app.graph?.setDirtyCanvas?.(true, true);
}

function hookWidget(node, name) {
    const widget = findWidget(node, name);
    if (!widget) return;
    const original = widget.callback;
    widget.callback = (...args) => {
        original?.apply(widget, args);
        updateReadout(node);
    };
}

app.registerExtension({
    name: "toobusy.ltxEmptyAVLatents",
    beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== "LTX23EmptyAVLatents") {
            return;
        }

        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            onNodeCreated?.apply(this, arguments);

            const readout = this.addWidget("customtext", "av_readout", "", () => {}, { serialize: false });
            if (readout.inputEl) {
                readout.inputEl.readOnly = true;
                readout.inputEl.style.fontSize = "12px";
                readout.inputEl.style.lineHeight = "1.35";
                readout.inputEl.style.minHeight = "60px";
                readout.inputEl.style.opacity = "0.95";
            }

            for (const name of ["ratio_preset", "megapixels", "divisible_by", "length", "frame_rate", "use_custom_audio"]) {
                hookWidget(this, name);
            }

            updateReadout(this);
        };

        const onConfigure = nodeType.prototype.onConfigure;
        nodeType.prototype.onConfigure = function () {
            onConfigure?.apply(this, arguments);
            updateReadout(this);
        };

        // Refresh the audio warning when the AUDIO input is (dis)connected.
        const onConnectionsChange = nodeType.prototype.onConnectionsChange;
        nodeType.prototype.onConnectionsChange = function () {
            onConnectionsChange?.apply(this, arguments);
            updateReadout(this);
        };
    },
});
