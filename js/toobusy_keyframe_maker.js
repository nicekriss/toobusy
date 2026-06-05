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

function lineCount(value) {
    return String(value || "").split(/\r?\n/).filter((line) => line.trim()).length;
}

function roundedRect(ctx, x, y, width, height, radius) {
    if (ctx.roundRect) {
        ctx.roundRect(x, y, width, height, radius);
        return;
    }

    ctx.moveTo(x + radius, y);
    ctx.lineTo(x + width - radius, y);
    ctx.quadraticCurveTo(x + width, y, x + width, y + radius);
    ctx.lineTo(x + width, y + height - radius);
    ctx.quadraticCurveTo(x + width, y + height, x + width - radius, y + height);
    ctx.lineTo(x + radius, y + height);
    ctx.quadraticCurveTo(x, y + height, x, y + height - radius);
    ctx.lineTo(x, y + radius);
    ctx.quadraticCurveTo(x, y, x + radius, y);
}

function refreshSummary(node) {
    const idea = widgetText(node, "idea");
    const style = widgetText(node, "style");
    const fixed = widgetText(node, "fixed_elements");
    const productBrief = widgetText(node, "product_brief_override");
    const shotBeats = widgetText(node, "shot_beats_override");
    const shotCount = String(findWidget(node, "shot_count")?.value ?? "").trim();
    const beatOverrideCount = lineCount(shotBeats);

    node.toobusyOverrideStates = {
        productBrief: Boolean(productBrief),
        shotBeats: Boolean(shotBeats),
    };

    node.toobusySummaryLines = [
        ["Idea", shorten(idea, 70)],
        ["Style", shorten(style, 70)],
        ["Fixed", shorten(fixed, 70)],
        [
            "Product brief",
            productBrief ? "OVERRIDE ON - image analysis skipped" : "AUTO - generated from product_image",
        ],
        [
            "Shot beats",
            shotBeats
                ? `OVERRIDE ON - beat generation skipped, using ${beatOverrideCount || "?"} override lines`
                : `AUTO - generating ${shotCount || "?"} beats from brief/idea/style/fixed`,
        ],
        [
            "Flow",
            [
                "brief",
                "beats",
                "keyframes",
                "korean story",
            ].join(" | "),
        ],
    ];

    node.setDirtyCanvas?.(true, true);
    app.graph?.setDirtyCanvas?.(true, true);
}

function drawBadge(ctx, x, y, title, hint, active = false) {
    const text = hint ? `${title} - ${hint}` : title;
    ctx.save();
    ctx.font = "11px sans-serif";
    const width = Math.min(ctx.measureText(text).width + 16, 430);
    const height = 18;

    ctx.fillStyle = active ? "rgba(164, 92, 35, 0.95)" : "rgba(30, 42, 52, 0.96)";
    ctx.strokeStyle = active ? "rgba(255, 182, 96, 0.88)" : "rgba(116, 166, 202, 0.62)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    roundedRect(ctx, x, y, width, height, 6);
    ctx.fill();
    ctx.stroke();

    ctx.fillStyle = "rgba(246, 248, 250, 0.96)";
    ctx.fillText(text, x + 8, y + 13);
    ctx.restore();
}

function drawInputBadges(node, ctx) {
    const states = node.toobusyOverrideStates || {};
    const badges = [
        ["idea", "Idea", "광고 핵심 사건/변화"],
        ["style", "Style", "룩, 톤, 촬영감"],
        ["fixed_elements", "Fixed", "모든 컷에 유지할 요소"],
        ["product_brief_override", "Brief Override", "입력하면 제품 이미지 분석 무시", states.productBrief],
        ["shot_beats_override", "Beats Override", "입력하면 샷비트 생성 무시", states.shotBeats],
    ];

    for (const [widgetName, title, hint, active] of badges) {
        const widget = findWidget(node, widgetName);
        if (!widget || typeof widget.last_y !== "number") {
            continue;
        }
        drawBadge(ctx, 18, widget.last_y + 2, title, hint, active);
    }
}

function drawSummaryPanel(node, ctx) {
    const lines = node.toobusySummaryLines;
    if (!lines?.length) {
        return;
    }

    const margin = 16;
    const panelHeight = 168;
    const panelY = node.size[1] - panelHeight - 12;
    const panelWidth = node.size[0] - margin * 2;

    ctx.save();
    ctx.fillStyle = "rgba(14, 17, 20, 0.96)";
    ctx.strokeStyle = "rgba(118, 178, 214, 0.62)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    roundedRect(ctx, margin, panelY, panelWidth, panelHeight, 8);
    ctx.fill();
    ctx.stroke();

    ctx.fillStyle = "rgba(230, 236, 240, 0.92)";
    ctx.font = "13px sans-serif";
    ctx.fillText("Input summary", margin + 12, panelY + 22);

    ctx.font = "12px sans-serif";
    lines.forEach(([label, value], index) => {
        const y = panelY + 44 + index * 22;
        const isOverrideWarning = String(value).startsWith("OVERRIDE ON");
        ctx.fillStyle = isOverrideWarning ? "rgba(255, 184, 108, 0.95)" : "rgba(135, 190, 224, 0.95)";
        ctx.fillText(label, margin + 12, y);
        ctx.fillStyle = isOverrideWarning ? "rgba(255, 220, 174, 0.96)" : "rgba(232, 236, 238, 0.92)";
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

            this.addWidget("button", "Refresh labels / summary", "refresh", () => {
                refreshSummary(this);
            }, { serialize: false });

            this.size[1] = Math.max(this.size[1], 875);
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
            drawInputBadges(this, ctx);
            drawSummaryPanel(this, ctx);
        };
    },
});
