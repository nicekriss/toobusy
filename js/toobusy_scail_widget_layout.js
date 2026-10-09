// Saved-workflow repair for toobusy Wan SCAIL Extend Sampler.
//
// ComfyUI saves widget values by POSITION, in the order the widgets sit on the
// node — and this node's JS reorders widgets (frame_mode under base_frames,
// color_sample next to color_anchor, a "✕ Remove" button after every extend
// slot). So every widget added since v0.2.9 shifted the positions of a graph
// saved by an older version, and the hidden extend slots ended up holding
// "remove" / "fixed" / null ("Value remove cannot be converted to INT").
//
// parseScailWidgetValues() reads the raw widgets_values of ANY known layout by
// value type and returns { widgetName: value }, so onConfigure can put every
// value back on the widget it belongs to. Pure module (no ComfyUI imports) so
// tests/js can run it under plain node.

export const MAX_EXTEND_SEGMENTS = 8;

// Every value widget the node has today. A name an older layout did not save
// gets its default back instead of whatever the positional restore left there.
export const SCAIL_VALUE_WIDGETS = [
    "positive", "negative", "width", "height", "base_frames", "frame_mode", "target_total_frames",
    "extend_segments", "seed", "control_after_generate", "steps", "cfg", "sampler_name", "scheduler",
    "shift", "previous_frame_count", "color_match", "color_anchor", "color_sample", "color_match_strength",
    "replacement_mode", "pose_strength", "pose_start", "pose_end", "clip_vision_crop",
    ...Array.from({ length: MAX_EXTEND_SEGMENTS }, (_, k) => `extend_${k + 1}_frames`),
];

const FRAME_MODES = ["target total", "manual segments"];
const SEED_CONTROLS = ["fixed", "increment", "decrement", "randomize"];
const COLOR_ANCHORS = ["first chunk", "previous chunk"];
const COLOR_SAMPLES = ["whole chunk", "last frame"];
const CLIP_VISION_CROPS = ["none", "center"];

const isNum = (v) => typeof v === "number" && Number.isFinite(v);
const isStr = (v) => typeof v === "string";
const isBool = (v) => typeof v === "boolean";
const oneOf = (choices) => (v) => isStr(v) && choices.includes(v);

// Returns { name: value } or null when the array matches no known layout (the
// caller then leaves the frontend's positional restore alone).
export function parseScailWidgetValues(values) {
    if (!Array.isArray(values)) return null;
    const out = {};
    let i = 0;
    const take = (name, check) => {
        if (i >= values.length || !check(values[i])) return false;
        out[name] = values[i];
        i += 1;
        return true;
    };
    const takeOptional = (name, check) => (i < values.length && check(values[i]) ? take(name, check) : false);

    if (!take("positive", isStr) || !take("negative", isStr)) return null;
    if (!take("width", isNum) || !take("height", isNum) || !take("base_frames", isNum)) return null;

    // v0.2.11+: frame_mode + target_total_frames sit right under base_frames.
    const hasFrameMode = takeOptional("frame_mode", oneOf(FRAME_MODES));
    if (hasFrameMode && !take("target_total_frames", isNum)) return null;

    if (!take("extend_segments", isNum) || !take("seed", isNum)) return null;
    takeOptional("control_after_generate", oneOf(SEED_CONTROLS));

    if (!take("steps", isNum) || !take("cfg", isNum)) return null;
    if (!take("sampler_name", isStr) || !take("scheduler", isStr)) return null;
    if (!take("shift", isNum) || !take("previous_frame_count", isNum)) return null;
    if (!take("color_match", isBool)) return null;

    // v0.2.10+: color_anchor; v0.2.11+: color_sample + color_match_strength.
    takeOptional("color_anchor", oneOf(COLOR_ANCHORS));
    if (takeOptional("color_sample", oneOf(COLOR_SAMPLES)) && !take("color_match_strength", isNum)) return null;

    if (!take("replacement_mode", isBool)) return null;
    if (!take("pose_strength", isNum) || !take("pose_start", isNum) || !take("pose_end", isNum)) return null;
    if (!take("clip_vision_crop", oneOf(CLIP_VISION_CROPS))) return null;

    // Tail: extend_N_frames, each optionally followed by its "✕ Remove" button
    // value ("remove"), then "＋ Add" ("add") and non-serialized leftovers
    // (null). Only the numbers are slot values, in slot order.
    let slot = 1;
    for (; i < values.length && slot <= MAX_EXTEND_SEGMENTS; i += 1) {
        if (isNum(values[i])) {
            out[`extend_${slot}_frames`] = values[i];
            slot += 1;
        }
    }

    // Graphs saved before frame_mode existed always ran the manual extend
    // slots — keep that instead of silently switching them to the new
    // "target total" default (which would ignore their extend count).
    if (!hasFrameMode) out.frame_mode = "manual segments";
    return out;
}
