import { app } from "../../scripts/app.js";

const IMAGE_MODES = ["Analyze image literally", "Transform by scene text"];
const ANALYSIS_MODES = ["fast", "balanced", "detailed"];

function widget(node, name) {
    return node.widgets?.find((item) => item.name === name);
}

function migrateBrokenV038WidgetOrder(node) {
    const existing = widget(node, "existing_layout_json");
    const imageMode = widget(node, "image_instruction_mode");
    const analysis = widget(node, "analysis_mode");
    const debugRaw = widget(node, "debug_raw");
    const releaseClip = widget(node, "release_clip_after_run");
    if (!existing || !imageMode || !analysis || !debugRaw || !releaseClip) return;

    // v0.3.8 inserted release_clip_after_run before existing widgets. A graph
    // saved in that version has this positional shape when opened after the
    // field is moved to the safe final position:
    // existing <- release, image mode <- existing, analysis <- image mode,
    // debug <- analysis, release <- debug.
    const isBrokenV038 = typeof existing.value === "boolean"
        && IMAGE_MODES.includes(String(analysis.value))
        && ANALYSIS_MODES.includes(String(debugRaw.value));
    if (!isBrokenV038) return;

    const oldRelease = existing.value;
    const oldExisting = imageMode.value;
    const oldImageMode = analysis.value;
    const oldAnalysis = debugRaw.value;
    const oldDebug = releaseClip.value;

    existing.value = typeof oldExisting === "string" ? oldExisting : "";
    imageMode.value = IMAGE_MODES.includes(String(oldImageMode))
        ? oldImageMode : IMAGE_MODES[0];
    analysis.value = ANALYSIS_MODES.includes(String(oldAnalysis))
        ? oldAnalysis : "balanced";
    debugRaw.value = typeof oldDebug === "boolean" ? oldDebug : false;
    releaseClip.value = typeof oldRelease === "boolean" ? oldRelease : true;
    console.warn("[toobusy] Repaired Ideogram Prompt Polish widget order saved by v0.3.8.");
}

app.registerExtension({
    name: "toobusy.ideogramPromptPolishCompatibility",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== "ToobusyIdeogramPromptPolish") return;
        const original = nodeType.prototype.onConfigure;
        nodeType.prototype.onConfigure = function () {
            const result = original?.apply(this, arguments);
            migrateBrokenV038WidgetOrder(this);
            return result;
        };
    },
});
