import { app } from "../../scripts/app.js";

// toobusy ZIT ControlNet — Basic surface is just "image in, switch, strength"
// per control type. The preprocess toggles (treat the input as a ready-made
// control map instead of running MiDaS/Canny/DWPose), the preprocessor
// resolution, and the canny thresholds are expert options and live behind
// Show advanced settings.

const ACCENT = "#7fc8ff";
const INFO_TITLE = "toobusy · ZIT ControlNet";
const INFO_TEXT =
    "Depth / canny / pose control module for Z-Image Turbo: one image input, " +
    "switch, and strength per type. Inputs are preprocessed in-node (MiDaS / " +
    "Canny / DWPose) and previewed after each run; slots stack, so different " +
    "images can drive the model together. Advanced holds the raw-control-map " +
    "toggles, preprocessor resolution, and canny thresholds.";
const INFO_SIGNATURE = "fold the graph — 너무바쁜베짱이";

const ADVANCED_WIDGETS = [
    "depth_preprocess",
    "canny_preprocess",
    "pose_preprocess",
    "preprocessor_resolution",
    "canny_low",
    "canny_high",
];

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

function applyAdvanced(node) {
    const advanced = isAdvanced(node);
    for (const name of ADVANCED_WIDGETS) {
        setWidgetVisible(node, findWidget(node, name), advanced);
    }
    if (node._toobusyAdvButton) {
        node._toobusyAdvButton.name = advanced ? "Hide advanced settings" : "Show advanced settings";
    }
    node.setDirtyCanvas?.(true, true);
    app.graph?.setDirtyCanvas?.(true, true);
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

app.registerExtension({
    name: "toobusy.zitControlNet",
    beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== "ToobusyZITControlNet") {
            return;
        }

        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            onNodeCreated?.apply(this, arguments);

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
