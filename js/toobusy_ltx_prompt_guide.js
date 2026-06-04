import { app } from "../../scripts/app.js";

function findWidget(node, name) {
    return node.widgets?.find((widget) => widget.name === name);
}

function widgetNumber(node, name, fallback) {
    const value = Number(findWidget(node, name)?.value);
    return Number.isFinite(value) ? value : fallback;
}

function extractQuotedDialogue(text) {
    const pairs = [
        ["'", "'"],
        ['"', '"'],
        ["“", "”"],
        ["‘", "’"],
        ["「", "」"],
        ["『", "』"],
    ];
    const parts = [];

    for (const [openQuote, closeQuote] of pairs) {
        let start = 0;
        while (start < text.length) {
            const left = text.indexOf(openQuote, start);
            if (left < 0) {
                break;
            }
            const right = text.indexOf(closeQuote, left + openQuote.length);
            if (right < 0) {
                break;
            }
            const value = text.slice(left + openQuote.length, right).trim();
            if (value) {
                parts.push(value);
            }
            start = right + closeQuote.length;
        }
    }

    return parts.join("\n");
}

function containsHangul(text) {
    return /[\uac00-\ud7a3]/.test(text);
}

function estimateDuration(node) {
    const prompt = String(findWidget(node, "prompt")?.value ?? "");
    const fallbackDuration = widgetNumber(node, "duration_seconds", 4.0);
    const language = String(findWidget(node, "language")?.value ?? "Auto");
    const dialogue = extractQuotedDialogue(prompt);

    if (!dialogue) {
        return fallbackDuration;
    }

    let mode = language;
    if (mode === "Auto") {
        mode = containsHangul(dialogue) ? "Korean" : "English";
    }

    let speechSeconds;
    if (mode === "Korean") {
        const count = Array.from(dialogue).filter((char) => !/\s/.test(char)).length;
        speechSeconds = count / 5.5;
    } else {
        const count = dialogue.split(/\s+/).filter(Boolean).length;
        speechSeconds = count / 2.4;
    }

    return Math.max(fallbackDuration, Math.round((speechSeconds + 1.0) * 10) / 10);
}

function ltxLength(durationSeconds, frameRate) {
    return Math.max(1, Math.round(durationSeconds * frameRate) + 1);
}

function updateRecommendationDisplay(node, durationSeconds, length, frameRate) {
    node.toobusyRecommendedDuration = Number(durationSeconds);
    node.toobusyRecommendedLength = Number(length);

    const displayWidget = findWidget(node, "toobusy_recommended");
    if (displayWidget) {
        displayWidget.value = `Recommended: ${Number(durationSeconds).toFixed(1)}s | length ${length} @ ${Number(frameRate).toFixed(2)}fps`;
    }

    node.setDirtyCanvas(true, true);
}

function refreshRecommendation(node) {
    const durationSeconds = estimateDuration(node);
    const frameRate = widgetNumber(node, "frame_rate", 24.0);
    const length = ltxLength(durationSeconds, frameRate);
    updateRecommendationDisplay(node, durationSeconds, length, frameRate);
}

app.registerExtension({
    name: "toobusy.ltxPromptGuide",
    beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== "LTX23PromptGuide") {
            return;
        }

        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            onNodeCreated?.apply(this, arguments);

            this.toobusyRecommendedDuration = null;
            this.toobusyRecommendedLength = null;

            this.addWidget(
                "text",
                "toobusy_recommended",
                "Run prompt guide to estimate duration",
                () => {},
                { serialize: false }
            );

            this.addWidget("button", "Suggest duration", "suggest", () => {
                refreshRecommendation(this);
            });

            this.addWidget("button", "Apply recommended duration", "apply", () => {
                if (this.toobusyRecommendedDuration == null) {
                    refreshRecommendation(this);
                }

                if (this.toobusyRecommendedDuration == null) {
                    return;
                }

                const durationWidget = findWidget(this, "duration_seconds");
                if (durationWidget) {
                    durationWidget.value = this.toobusyRecommendedDuration;
                    durationWidget.callback?.(durationWidget.value, this, durationWidget);
                }

                this.setDirtyCanvas(true, true);
            });
        };

        const onExecuted = nodeType.prototype.onExecuted;
        nodeType.prototype.onExecuted = function (message) {
            onExecuted?.apply(this, arguments);

            const recommended = message?.recommended_duration_seconds?.[0];
            const length = message?.length?.[0];
            const frameRate = message?.frame_rate_float?.[0] ?? message?.frame_rate?.[0];

            if (recommended == null || length == null || frameRate == null) {
                return;
            }

            updateRecommendationDisplay(this, Number(recommended), Number(length), Number(frameRate));
        };
    },
});
