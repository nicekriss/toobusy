// Saved-workflow repair for toobusy Wan SCAIL Extend Sampler: every layout the
// node has ever saved must map back onto the right widget names.
// Run: node tests/js/scail_widget_layout.test.mjs
import assert from "node:assert/strict";
import { parseScailWidgetValues, SCAIL_VALUE_WIDGETS } from "../../js/toobusy_scail_widget_layout.js";

const slots = (frames) => frames.flatMap((f) => [f, "remove"]);

const tests = {
    "v0.2.9 graph (39 values) keeps its manual extends": () => {
        // widgets_values of the old docs/workflows/Wan21_SCAIL2_Testing_neobabae.json,
        // whose positional restore put "fixed" into extend_segments and
        // "remove" into extend_1..6_frames.
        const saved = [
            "a girl is dancing", "", 512, 896, 81, 3, 1, "fixed", 6, 1, "euler", "simple", 5, 5, true,
            false, 1, 0, 1, "none", ...slots([81, 81, 29, 81, 81, 81, 81, 81]), "add", null, null,
        ];
        assert.equal(saved.length, 39);
        const v = parseScailWidgetValues(saved);
        assert.equal(v.extend_segments, 3);
        assert.equal(v.seed, 1);
        assert.equal(v.control_after_generate, "fixed");
        assert.equal(v.steps, 6);
        assert.equal(v.sampler_name, "euler");
        assert.equal(v.color_match, true);
        assert.equal(v.replacement_mode, false);
        assert.equal(v.clip_vision_crop, "none");
        assert.equal(v.extend_3_frames, 29);
        assert.equal(v.extend_8_frames, 81);
        assert.equal(v.frame_mode, "manual segments");
        assert.ok(!("color_anchor" in v) && !("target_total_frames" in v));
    },

    "v0.2.10 graph (color_anchor, no frame_mode)": () => {
        const v = parseScailWidgetValues([
            "p", "n", 512, 896, 81, 2, 7, "randomize", 6, 1, "euler", "simple", 5, 5, true, "previous chunk",
            true, 1, 0, 1, "center", ...slots([45, 33, 81, 81, 81, 81, 81, 81]), "add", null, null,
        ]);
        assert.equal(v.color_anchor, "previous chunk");
        assert.equal(v.replacement_mode, true);
        assert.equal(v.clip_vision_crop, "center");
        assert.equal(v.extend_1_frames, 45);
        assert.equal(v.extend_2_frames, 33);
        assert.equal(v.frame_mode, "manual segments");
    },

    "current layout (44 values, docs/workflows/wan21_scail2.json) is an exact no-op": () => {
        const saved = [
            "the green hero", "", 512, 896, 81, "target total", 181, 0, 54177985180640, "randomize", 6, 1,
            "euler", "simple", 5, 5, true, "first chunk", "whole chunk", 1, false, 1, 0, 1, "none",
            ...slots([81, 81, 81, 81, 81, 81, 81, 81]), "add", null, null,
        ];
        assert.equal(saved.length, 44);
        const v = parseScailWidgetValues(saved);
        assert.equal(v.frame_mode, "target total");
        assert.equal(v.target_total_frames, 181);
        assert.equal(v.extend_segments, 0);
        assert.equal(v.seed, 54177985180640);
        assert.equal(v.color_sample, "whole chunk");
        assert.equal(v.color_match_strength, 1);
        assert.equal(v.replacement_mode, false);
        assert.equal(v.pose_strength, 1);
        assert.equal(v.pose_start, 0);
        assert.equal(v.pose_end, 1);
        // The current layout covers every value widget, so nothing falls back
        // to a default — and nothing outside the known list is produced.
        assert.deepEqual(Object.keys(v).sort(), [...SCAIL_VALUE_WIDGETS].sort());
    },

    "a frontend that skips button values still maps the slots": () => {
        const v = parseScailWidgetValues([
            "p", "", 512, 960, 49, "manual segments", 149, 2, 1, "fixed", 6, 1, "euler", "simple", 5, 5,
            true, "first chunk", "last frame", 0.5, false, 1, 0.5, 1, "none", 41, 37, 81, 81, 81, 81, 81, 81,
        ]);
        assert.equal(v.color_sample, "last frame");
        assert.equal(v.color_match_strength, 0.5);
        assert.equal(v.extend_1_frames, 41);
        assert.equal(v.extend_2_frames, 37);
        assert.equal(v.frame_mode, "manual segments");
    },

    "unknown shapes are left alone": () => {
        assert.equal(parseScailWidgetValues(undefined), null);
        assert.equal(parseScailWidgetValues([]), null);
        assert.equal(parseScailWidgetValues(["p", "n", "512", 896, 81]), null);
        // frame_mode present but its target missing.
        assert.equal(parseScailWidgetValues(["p", "n", 512, 896, 81, "target total", "x"]), null);
    },
};

let failed = 0;
for (const [name, fn] of Object.entries(tests)) {
    try {
        fn();
        console.log(`ok - ${name}`);
    } catch (err) {
        failed += 1;
        console.error(`FAIL - ${name}\n${err.stack}`);
    }
}
if (failed) process.exit(1);
