import { app } from "../../scripts/app.js";

function findWidget(node, name) {
    return node.widgets?.find((widget) => widget.name === name);
}

function widgetText(node, name) {
    return String(findWidget(node, name)?.value ?? "").trim();
}

function shorten(value, maxLength = 84) {
    const oneLine = String(value || "").replace(/\s+/g, " ").trim();
    if (!oneLine) {
        return "(empty)";
    }
    return oneLine.length > maxLength ? `${oneLine.slice(0, maxLength - 1)}...` : oneLine;
}

function refreshSummary(node) {
    const idea = widgetText(node, "idea");
    const style = widgetText(node, "style");
    const fixed = widgetText(node, "fixed_elements");
    const productBrief = widgetText(node, "product_brief_override");
    const shotBeats = widgetText(node, "shot_beats_override");

    node.toobusySummaryLines = [
        ["Idea", shorten(idea, 78)],
        ["Style", shorten(style, 78)],
        ["Fixed", shorten(fixed, 78)],
        [
            "Mode",
            [
                productBrief ? "product brief override" : "product brief auto",
                shotBeats ? "shot beats override" : "shot beats auto",
            ].join(" | "),
        ],
    ];

    node.setDirtyCanvas?.(true, true);
    app.graph?.setDirtyCanvas?.(true, true);
}

function drawSummaryPanel(node, ctx) {
    const lines = node.toobusySummaryLines;
    if (!lines?.length) {
        return;
    }

    const margin = 16;
    const panelHeight = 124;
    const panelY = node.size[1] - panelHeight - 12;
    const panelWidth = node.size[0] - margin * 2;

    ctx.save();
    ctx.fillStyle = "rgba(24, 26, 28, 0.92)";
    ctx.strokeStyle = "rgba(120, 150, 170, 0.38)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.roundRect(margin, panelY, panelWidth, panelHeight, 8);
    ctx.fill();
    ctx.stroke();

    ctx.fillStyle = "rgba(230, 236, 240, 0.92)";
    ctx.font = "13px sans-serif";
    ctx.fillText("Input summary", margin + 12, panelY + 22);

    ctx.font = "12px sans-serif";
    lines.forEach(([label, value], index) => {
        const y = panelY + 44 + index * 22;
        ctx.fillStyle = "rgba(135, 180, 210, 0.92)";
        ctx.fillText(label, margin + 12, y);
        ctx.fillStyle = "rgba(225, 225, 225, 0.88)";
        ctx.fillText(value, margin + 72, y);
    });

    ctx.restore();
}

app.registerExtension({
    name: "toobusy.keyframeMaker",
    beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== "ToobusyKeyframeMaker") {
            return;
        }

        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            onNodeCreated?.apply(this, arguments);

            this.toobusySummaryLines = [];

            this.addWidget("button", "Refresh input summary", "refresh", () => {
                refreshSummary(this);
            }, { serialize: false });

            this.size[1] = Math.max(this.size[1], 820);
            refreshSummary(this);
        };

        const onExecuted = nodeType.prototype.onExecuted;
        nodeType.prototype.onExecuted = function (message) {
            onExecuted?.apply(this, arguments);
            refreshSummary(this);
        };

        const onDrawForeground = nodeType.prototype.onDrawForeground;
        nodeType.prototype.onDrawForeground = function (ctx) {
            onDrawForeground?.apply(this, arguments);
            drawSummaryPanel(this, ctx);
        };
    },
});
