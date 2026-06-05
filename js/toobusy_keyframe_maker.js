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

function setWidget(node, name, value) {
    const widget = findWidget(node, name);
    if (widget) {
        widget.value = value;
    }
}

function refreshSummary(node) {
    const idea = widgetText(node, "idea");
    const style = widgetText(node, "style");
    const fixed = widgetText(node, "fixed_elements");
    const productBrief = widgetText(node, "product_brief_override");
    const shotBeats = widgetText(node, "shot_beats_override");

    setWidget(node, "toobusy_idea_summary", `idea: ${shorten(idea)}`);
    setWidget(node, "toobusy_style_summary", `style: ${shorten(style)}`);
    setWidget(node, "toobusy_fixed_summary", `fixed: ${shorten(fixed)}`);

    const overrideState = [
        productBrief ? "product brief override on" : "product brief auto",
        shotBeats ? "shot beats override on" : "shot beats auto",
    ].join(" | ");
    setWidget(node, "toobusy_override_summary", overrideState);

    node.setDirtyCanvas?.(true, true);
    app.graph?.setDirtyCanvas?.(true, true);
}

function addReadOnlyText(node, name, value) {
    const widget = node.addWidget("text", name, value, () => {}, { serialize: false });
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

            addReadOnlyText(this, "toobusy_keyframe_guide", "Guide: idea=what happens | style=look/tone | fixed=keep consistent");
            addReadOnlyText(this, "toobusy_idea_summary", "idea: (empty)");
            addReadOnlyText(this, "toobusy_style_summary", "style: (empty)");
            addReadOnlyText(this, "toobusy_fixed_summary", "fixed: (empty)");
            addReadOnlyText(this, "toobusy_override_summary", "product brief auto | shot beats auto");

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
