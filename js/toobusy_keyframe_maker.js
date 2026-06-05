import { app } from "../../scripts/app.js";

function findWidget(node, name) {
    return node.widgets?.find((widget) => widget.name === name);
}

function findToobusyWidget(node, id) {
    return node.widgets?.find((widget) => widget.toobusyId === id);
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

function setDisplay(node, id, label) {
    const widget = findToobusyWidget(node, id);
    if (widget) {
        widget.name = label;
        widget.value = "";
    }
}

function refreshSummary(node) {
    const idea = widgetText(node, "idea");
    const style = widgetText(node, "style");
    const fixed = widgetText(node, "fixed_elements");
    const productBrief = widgetText(node, "product_brief_override");
    const shotBeats = widgetText(node, "shot_beats_override");

    setDisplay(node, "idea_summary", `Idea - ${shorten(idea)}`);
    setDisplay(node, "style_summary", `Style - ${shorten(style)}`);
    setDisplay(node, "fixed_summary", `Fixed - ${shorten(fixed)}`);

    const overrideState = [
        productBrief ? "product brief override on" : "product brief auto",
        shotBeats ? "shot beats override on" : "shot beats auto",
    ].join(" | ");
    setDisplay(node, "override_summary", `Mode - ${overrideState}`);

    node.setDirtyCanvas?.(true, true);
    app.graph?.setDirtyCanvas?.(true, true);
}

function addReadOnlyText(node, id, label) {
    const widget = node.addWidget("text", label, "", () => {}, { serialize: false });
    widget.toobusyId = id;
    widget.disabled = true;
    return widget;
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

            addReadOnlyText(this, "guide", "Guide - idea: event/story | style: look/tone | fixed: must stay consistent");
            addReadOnlyText(this, "idea_summary", "Idea - (empty)");
            addReadOnlyText(this, "style_summary", "Style - (empty)");
            addReadOnlyText(this, "fixed_summary", "Fixed - (empty)");
            addReadOnlyText(this, "override_summary", "Mode - product brief auto | shot beats auto");

            this.addWidget("button", "Refresh input summary", "refresh", () => {
                refreshSummary(this);
            }, { serialize: false });

            refreshSummary(this);
        };

        const onExecuted = nodeType.prototype.onExecuted;
        nodeType.prototype.onExecuted = function (message) {
            onExecuted?.apply(this, arguments);
            refreshSummary(this);
        };
    },
});
