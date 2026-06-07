import { app } from "../../scripts/app.js";

function findWidget(node, name) {
    return node.widgets?.find((widget) => widget.name === name);
}

function widgetText(node, name) {
    return String(findWidget(node, name)?.value ?? "").trim();
}

function shorten(value, maxLength = 90) {
    const oneLine = String(value || "").replace(/\s+/g, " ").trim();
    if (!oneLine) {
        return "(empty)";
    }
    return oneLine.length > maxLength ? `${oneLine.slice(0, maxLength - 1)}...` : oneLine;
}

function lineCount(value) {
    return String(value || "").split(/\r?\n/).filter((line) => line.trim()).length;
}

function setSummary(node) {
    const idea = widgetText(node, "idea");
    const mode = String(findWidget(node, "mode")?.value ?? "Product Commercial").trim();
    const style = widgetText(node, "style");
    const fixed = widgetText(node, "fixed_elements");
    const productBrief = widgetText(node, "product_brief_override");
    const shotBeats = widgetText(node, "shot_beats_override");
    const shotCount = String(findWidget(node, "shot_count")?.value ?? "").trim();
    const beatOverrideCount = lineCount(shotBeats);

    const briefName = mode === "Product Commercial" ? "product brief" : "reference brief";
    const productBriefMode = productBrief
        ? `OVERRIDE ON: ${briefName} auto analysis is skipped.`
        : `AUTO: ${briefName} is generated from product_image if connected, otherwise from text inputs.`;
    const shotBeatsMode = shotBeats
        ? `OVERRIDE ON: shot beat generation is skipped. Effective shot count = ${beatOverrideCount || "?"}.`
        : `AUTO: generating ${shotCount || "?"} shot beats from brief + idea + style + fixed.`;

    const summary = [
        "INPUT GUIDE",
        `Mode: ${mode}`,
        "Idea: commercial event, transformation, or story hook.",
        "Style: look, tone, camera feeling, lighting, genre.",
        "Fixed: product/character/color/background rules to keep consistent.",
        "",
        "CURRENT INPUTS",
        `Idea: ${shorten(idea)}`,
        `Style: ${shorten(style)}`,
        `Fixed: ${shorten(fixed)}`,
        "",
        "OVERRIDE STATUS",
        `Product brief: ${productBriefMode}`,
        `Shot beats: ${shotBeatsMode}`,
        "",
        "toobusy · brief -> beats -> keyframes -> story",
    ].join("\n");

    const widget = findWidget(node, "input_guide_summary");
    if (widget) {
        widget.value = summary;
    }

    node.setDirtyCanvas?.(true, true);
    app.graph?.setDirtyCanvas?.(true, true);
}

function copyGeneratedToOverride(node, captureKey, overrideName) {
    const value = node[captureKey];
    if (typeof value !== "string" || !value.trim()) {
        return; // nothing generated yet — run the node once first.
    }
    const widget = findWidget(node, overrideName);
    if (!widget) return;
    widget.value = value;
    widget.callback?.(widget.value, node, widget);
    setSummary(node);
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

            this.color = "#263228";
            this.bgcolor = "#171d18";

            const summaryWidget = this.addWidget(
                "customtext",
                "input_guide_summary",
                "",
                () => {},
                { serialize: false }
            );
            if (summaryWidget.inputEl) {
                summaryWidget.inputEl.readOnly = true;
                summaryWidget.inputEl.style.opacity = "0.95";
                summaryWidget.inputEl.style.fontSize = "12px";
                summaryWidget.inputEl.style.lineHeight = "1.35";
                summaryWidget.inputEl.style.minHeight = "230px";
                summaryWidget.inputEl.style.border = "1px solid rgba(124, 180, 135, 0.38)";
                summaryWidget.inputEl.style.background = "rgba(15, 18, 16, 0.96)";
                summaryWidget.inputEl.style.color = "rgba(232, 240, 232, 0.96)";
            }

            this.addWidget("button", "Refresh guide / summary", "refresh", () => {
                setSummary(this);
            }, { serialize: false });

            // Lock an expensive generated stage into its override so later runs
            // reuse it and only the downstream stages regenerate.
            this.addWidget("button", "Use generated brief as override", "use_brief", () => {
                copyGeneratedToOverride(this, "_toobusyGeneratedBrief", "product_brief_override");
            }, { serialize: false });

            this.addWidget("button", "Use generated shot beats as override", "use_beats", () => {
                copyGeneratedToOverride(this, "_toobusyGeneratedBeats", "shot_beats_override");
            }, { serialize: false });

            setSummary(this);
        };

        const onExecuted = nodeType.prototype.onExecuted;
        nodeType.prototype.onExecuted = function (message) {
            onExecuted?.apply(this, arguments);
            // ui.text is [label, value, label, value, ...] from keyframe_maker.py:
            // index 1 = reference/product brief, index 3 = shot beats.
            const text = message?.text;
            if (Array.isArray(text)) {
                if (typeof text[1] === "string") this._toobusyGeneratedBrief = text[1];
                if (typeof text[3] === "string") this._toobusyGeneratedBeats = text[3];
            }
            setSummary(this);
        };
    },
});
