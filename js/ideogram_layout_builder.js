import { app } from "../../scripts/app.js";

const NODE_CLASS = "IdeogramLayoutBuilder";
const CANVAS_SIZE = 1000;
const MIN_BOX_SIZE = 40;

const RESOLUTION_PRESETS = [
    ["square_2048", "Square 2K", 2048, 2048],
    ["square_1024", "Square 1K", 1024, 1024],
    ["portrait_9_16", "Portrait 9:16", 1024, 1792],
    ["portrait_3_4", "Portrait 3:4", 1024, 1365],
    ["portrait_2_3", "Portrait 2:3", 1024, 1536],
    ["landscape_16_9", "Landscape 16:9", 1792, 1024],
    ["landscape_4_3", "Landscape 4:3", 1365, 1024],
    ["landscape_3_2", "Landscape 3:2", 1536, 1024],
    ["wide_21_9", "Wide 21:9", 2048, 878],
    ["custom", "Custom", 2048, 2048],
];

const STYLE_PRESETS = [
    ["Clean ad", "clean commercial design, sharp focus, balanced negative space"],
    ["Premium product", "premium product advertising, polished materials, restrained luxury layout"],
    ["Editorial poster", "editorial poster design, strong hierarchy, refined typography"],
    ["Cinematic", "cinematic composition, dramatic mood, high contrast, filmic color"],
    ["Minimal", "minimal modern design, lots of negative space, simple geometric layout"],
    ["Playful graphic", "playful graphic design, bold shapes, energetic composition"],
];

const LIGHTING_PRESETS = [
    ["Soft studio", "soft studio lighting with gentle shadows"],
    ["Natural window", "soft natural window light from the side"],
    ["Cinematic contrast", "dramatic cinematic key light with subtle rim light"],
    ["Bright commercial", "bright even commercial lighting, clean highlights"],
    ["Golden hour", "warm golden hour light with long soft shadows"],
    ["Neon", "colored neon lighting with glowing accents"],
];

const CAMERA_PRESETS = [
    ["Product photo", "professional product photography, 85mm lens"],
    ["Portrait photo", "professional portrait photography, 50mm lens, shallow depth of field"],
    ["Wide editorial", "editorial photography, 35mm lens, natural perspective"],
    ["Macro detail", "macro photography, crisp fine detail, shallow depth of field"],
    ["None", ""],
];

const MEDIUM_PRESETS = [
    ["Photography", "photography"],
    ["Digital illustration", "digital illustration"],
    ["3D render", "3D render"],
    ["Vector poster", "vector illustration"],
    ["Typography poster", "graphic design poster"],
    ["Oil painting", "oil painting"],
    ["Watercolor", "watercolor"],
];

const PALETTE_PRESETS = [
    ["Neutral", ["#111111", "#FFFFFF", "#D8C7A3", "#8A8F98", "#4A5562"]],
    ["Warm editorial", ["#2B1A12", "#F2D8B3", "#C96F3D", "#7A3324", "#FFF8ED"]],
    ["Cool tech", ["#07111F", "#EAF4FF", "#46A3FF", "#7DE2D1", "#94A3B8"]],
    ["Luxury", ["#090909", "#F7F1DF", "#C8A95D", "#6D1F2A", "#FFFFFF"]],
    ["Pastel", ["#F8C7D8", "#B8D8FF", "#FFF0B8", "#CFF2D0", "#FFFFFF"]],
    ["High contrast", ["#000000", "#FFFFFF", "#FF3B30", "#FFD60A", "#0A84FF"]],
];

// Keep these defaults in sync with ideogram_layout_builder/nodes.py so Reset
// matches the state of a freshly-created node.
const DEFAULT_LAYOUT_STATE = {
    high_level_description: "A clean editorial poster with deliberate layout.",
    aesthetics: "clean commercial design, sharp focus, balanced negative space",
    lighting: "soft studio lighting with gentle shadows",
    photo: "professional product photography, 85mm lens",
    medium: "photography",
    global_palette: "#111111, #FFFFFF, #D8C7A3",
    background: "minimal studio background with subtle depth and a clean surface",
    include_global_palette: true,
    strict_text: true,
    reinforce_text: true,
    elements: [],
    resolution: {
        preset: "square_2048",
        width: 2048,
        height: 2048,
    },
};

// Text element roles. Value is sent as `role` on each element; the Python node
// expands it into a description hint (keep keys in sync with ROLE_HINTS).
const ROLE_PRESETS = [
    ["None", ""],
    ["Headline", "headline"],
    ["Subtitle", "subtitle"],
    ["Body", "body"],
    ["Footer", "footer"],
    ["Product label", "product label"],
    ["Sign", "sign"],
    ["UI label", "ui label"],
    ["Logo / wordmark", "logo"],
];

// One-click starting layouts. bbox is [x_min, y_min, x_max, y_max] on the
// 0-1000 canvas; text + role + desc seed each region (desc left blank so the
// user fills the specifics).
const LAYOUT_TEMPLATES = [
    ["(template…)", null],
    ["Poster", [
        { bbox: [120, 90, 880, 240], text: "HEADLINE", role: "headline" },
        { bbox: [120, 250, 880, 340], text: "Subtitle goes here", role: "subtitle" },
        { bbox: [200, 380, 800, 820], text: "", role: "", desc: "hero subject" },
        { bbox: [120, 900, 880, 960], text: "footer / website", role: "footer" },
    ]],
    ["Product ad", [
        { bbox: [300, 120, 700, 620], text: "", role: "", desc: "hero product" },
        { bbox: [100, 660, 900, 780], text: "HEADLINE", role: "headline" },
        { bbox: [150, 790, 850, 860], text: "supporting claim", role: "subtitle" },
        { bbox: [410, 890, 590, 960], text: "LOGO", role: "logo" },
    ]],
    ["Packaging label", [
        { bbox: [380, 80, 620, 200], text: "LOGO", role: "logo" },
        { bbox: [120, 240, 880, 380], text: "PRODUCT TITLE", role: "headline" },
        { bbox: [160, 410, 840, 520], text: "descriptor", role: "subtitle" },
        { bbox: [380, 820, 620, 920], text: "500ml", role: "product label" },
    ]],
    ["UI screenshot", [
        { bbox: [40, 40, 240, 960], text: "", role: "", desc: "sidebar navigation" },
        { bbox: [280, 40, 960, 130], text: "Dashboard", role: "ui label" },
        { bbox: [280, 160, 470, 360], text: "", role: "", desc: "KPI card" },
        { bbox: [500, 160, 690, 360], text: "", role: "", desc: "KPI card" },
        { bbox: [720, 160, 960, 360], text: "", role: "", desc: "KPI card" },
        { bbox: [280, 390, 960, 760], text: "", role: "", desc: "main graph" },
        { bbox: [280, 790, 960, 960], text: "", role: "", desc: "activity panel" },
    ]],
    ["Infographic", [
        { bbox: [120, 70, 880, 190], text: "TITLE", role: "headline" },
        { bbox: [60, 260, 250, 520], text: "Step 1", role: "subtitle" },
        { bbox: [280, 260, 470, 520], text: "Step 2", role: "subtitle" },
        { bbox: [500, 260, 690, 520], text: "Step 3", role: "subtitle" },
        { bbox: [720, 260, 940, 520], text: "Step 4", role: "subtitle" },
        { bbox: [120, 600, 880, 920], text: "", role: "", desc: "summary / chart" },
    ]],
];

const COLOR_CHOICES = [
    "#000000",
    "#111111",
    "#FFFFFF",
    "#F7F1DF",
    "#D8C7A3",
    "#8A8F98",
    "#4A5562",
    "#07111F",
    "#0A84FF",
    "#46A3FF",
    "#7DE2D1",
    "#FF3B30",
    "#FFD60A",
    "#C96F3D",
    "#6D1F2A",
    "#F8C7D8",
];

function widget(node, name) {
    return node.widgets?.find((item) => item.name === name);
}

function hideNativeWidgets(node) {
    for (const item of node.widgets || []) {
        item.hidden = true;
        item.computeSize = () => [0, -4];
    }
}

function clamp(value, min = 0, max = CANVAS_SIZE) {
    return Math.max(min, Math.min(max, Math.round(Number(value) || 0)));
}

function parseElements(value) {
    try {
        const parsed = JSON.parse(value || "[]");
        if (Array.isArray(parsed)) return parsed;
        if (parsed && Array.isArray(parsed.elements)) return parsed.elements;
        // Full Ideogram payload (e.g. piped from Prompt Polish): pull elements
        // out of compositional_deconstruction and swap bbox from Ideogram order
        // [y,x,y,x] back to canvas order [x,y,x,y].
        const comp = parsed && parsed.compositional_deconstruction;
        if (comp && Array.isArray(comp.elements)) {
            return comp.elements.map((el) => {
                if (el && Array.isArray(el.bbox) && el.bbox.length === 4) {
                    const [y1, x1, y2, x2] = el.bbox;
                    return { ...el, bbox: [x1, y1, x2, y2] };
                }
                return el;
            });
        }
        return [];
    } catch {
        return [];
    }
}

function normalizeElement(element = {}, index = 0) {
    const fallback = [130 + index * 30, 130 + index * 30, 560 + index * 30, 380 + index * 30];
    // NOTE: use an arrow wrapper — passing `clamp` straight to map would feed
    // map's (value, index, array) args into clamp's (value, min, max) and yield NaN.
    const bbox = Array.isArray(element.bbox) && element.bbox.length === 4
        ? element.bbox.map((value) => clamp(value))
        : fallback;
    if (bbox[2] - bbox[0] < MIN_BOX_SIZE) bbox[2] = Math.min(CANVAS_SIZE, bbox[0] + MIN_BOX_SIZE);
    if (bbox[3] - bbox[1] < MIN_BOX_SIZE) bbox[3] = Math.min(CANVAS_SIZE, bbox[1] + MIN_BOX_SIZE);
    if (bbox[2] - bbox[0] < MIN_BOX_SIZE) bbox[0] = Math.max(0, bbox[2] - MIN_BOX_SIZE);
    if (bbox[3] - bbox[1] < MIN_BOX_SIZE) bbox[1] = Math.max(0, bbox[3] - MIN_BOX_SIZE);
    return {
        type: "obj",
        bbox,
        text: element.text || "",
        desc: element.desc || "",
        role: typeof element.role === "string" ? element.role : "",
        color_palette: Array.isArray(element.color_palette) ? element.color_palette : [],
    };
}

function makeButton(text, title, onClick) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = text;
    button.title = title;

    // Run the action on pointerup and stop the event from reaching LiteGraph.
    // Some ComfyUI (Nodes 2.0) builds swallow the synthetic "click" on DOM
    // widgets overlapping the canvas, so we don't rely on it.
    let armed = false;
    button.addEventListener("pointerdown", (event) => {
        event.preventDefault();
        event.stopPropagation();
        armed = true;
    });
    button.addEventListener("pointerup", (event) => {
        event.preventDefault();
        event.stopPropagation();
        if (!armed) return;
        armed = false;
        try {
            onClick();
        } catch (err) {
            console.error(`[toobusy ideogram] "${text}" button failed:`, err);
        }
    });
    button.addEventListener("pointerleave", () => { armed = false; });
    button.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
    });
    return button;
}

let __uidCounter = 0;
function uid(prefix) {
    __uidCounter += 1;
    return `toobusy-ig-${prefix}-${__uidCounter}`;
}

function makeField(labelText, value, multiline, onInput, placeholder = "") {
    const label = document.createElement("label");
    const span = document.createElement("span");
    const input = multiline ? document.createElement("textarea") : document.createElement("input");
    span.textContent = labelText;
    input.id = uid("field");
    input.name = input.id;
    span.htmlFor = input.id;
    input.value = value || "";
    if (placeholder) input.placeholder = placeholder;
    if (multiline) input.rows = 4;
    input.addEventListener("input", () => onInput(input.value));
    label.append(span, input);
    return label;
}

function makeSelectField(labelText, options, currentValue, onInput) {
    const label = document.createElement("label");
    const span = document.createElement("span");
    const select = document.createElement("select");
    span.textContent = labelText;
    select.id = uid("select");
    select.name = select.id;

    let matched = false;
    for (const [name, value] of options) {
        const option = document.createElement("option");
        option.textContent = name;
        option.value = value;
        if (value === currentValue) matched = true;
        select.appendChild(option);
    }

    if (!matched && currentValue) {
        const option = document.createElement("option");
        option.textContent = "Current custom value";
        option.value = currentValue;
        select.appendChild(option);
    }

    select.value = currentValue || options[0][1];
    select.addEventListener("change", () => onInput(select.value));
    label.append(span, select);
    return label;
}

function makeCheckboxField(labelText, checked, onInput, title = "") {
    const label = document.createElement("label");
    label.className = "checkbox-field";
    if (title) label.title = title;
    const input = document.createElement("input");
    input.type = "checkbox";
    input.id = uid("check");
    input.name = input.id;
    input.checked = !!checked;
    const span = document.createElement("span");
    span.textContent = labelText;
    span.htmlFor = input.id;
    input.addEventListener("change", () => onInput(input.checked));
    label.append(input, span);
    return label;
}

function makeNumberInput(value, onInput) {
    const input = document.createElement("input");
    input.type = "number";
    input.id = uid("num");
    input.name = input.id;
    input.min = "256";
    input.max = "2048";
    input.step = "1";
    input.value = String(value);
    // Clamp on commit (blur / Enter), not on every keystroke: clamping mid-typing
    // turns a partial "1" into 256, flips the preset to custom, and triggers a
    // canvas redraw on each character. On commit, also write the clamped value
    // back so the field never shows an out-of-range number.
    const commit = () => {
        const clamped = clamp(input.value, 256, 2048);
        input.value = String(clamped);
        onInput(clamped);
    };
    input.addEventListener("change", commit);
    input.addEventListener("keydown", (event) => {
        if (event.key === "Enter") {
            event.preventDefault();
            input.blur();
        }
    });
    return input;
}

function parseColors(value, fallback) {
    if (Array.isArray(value)) return value;
    const colors = String(value || "")
        .split(/[,\s]+/)
        .map((color) => color.trim().toUpperCase())
        .filter((color) => /^#[0-9A-F]{6}$/.test(color));
    return colors.length ? colors : fallback;
}

function makePaletteEditor(labelText, colors, onInput, count = 5) {
    // Use a div (not a label) so clicking empty space or the title does not
    // trigger the first color input.
    const root = document.createElement("div");
    root.className = "palette-editor";
    const title = document.createElement("span");
    title.className = "palette-title";
    const row = document.createElement("div");
    const swatches = [];
    title.textContent = labelText;
    row.className = "palette-row";

    function emit() {
        onInput(swatches.map((swatch) => swatch.dataset.color));
    }

    for (let index = 0; index < count; index++) {
        const swatch = document.createElement("input");
        swatch.type = "color";
        swatch.id = uid("color");
        swatch.name = swatch.id;
        swatch.className = "color-swatch";
        const initial = (colors[index] || colors[colors.length - 1] || "#FFFFFF").toUpperCase();
        swatch.value = initial;
        swatch.dataset.color = initial;
        swatch.title = "Pick color";
        swatch.addEventListener("input", () => {
            swatch.dataset.color = swatch.value.toUpperCase();
            emit();
        });
        swatches.push(swatch);
        row.appendChild(swatch);
    }

    root.append(title, row);
    return { root, swatches };
}

function installEditor(node) {
    if (node.__toobusyIdeogramInstalled) return;
    node.__toobusyIdeogramInstalled = true;

    const jsonWidget = widget(node, "elements_json");
    if (!jsonWidget) return;

    hideNativeWidgets(node);

    let elements = parseElements(jsonWidget.value).map(normalizeElement);
    let selectedIndex = elements.length ? 0 : -1;
    let drag = null;
    node.properties = node.properties || {};
    const storedResolution = node.properties.ideogram_layout_resolution || {};
    const widthWidget = widget(node, "width");
    const heightWidget = widget(node, "height");
    let resolution = {
        preset: storedResolution.preset || "square_2048",
        width: clamp(storedResolution.width || widthWidget?.value || 2048, 256, 2048),
        height: clamp(storedResolution.height || heightWidget?.value || 2048, 256, 2048),
    };

    const root = document.createElement("div");
    root.className = "toobusy-ideogram";
    root.innerHTML = `
        <style>
            .toobusy-ideogram {
                box-sizing: border-box;
                width: 100%;
                min-width: 900px;
                color: #e9edf1;
                font: 12px/1.35 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
                user-select: none;
            }
            .toobusy-ideogram * { box-sizing: border-box; }
            .toobusy-ideogram .preset-bar {
                display: flex;
                gap: 6px;
                align-items: center;
                margin-bottom: 10px;
            }
            .toobusy-ideogram .preset-bar .preset-bar-title { color: #aeb8c4; }
            .toobusy-ideogram .preset-bar select { flex: 1; min-width: 0; }
            .toobusy-ideogram .editor {
                display: grid;
                grid-template-columns: minmax(0, 0.62fr) minmax(420px, 1.35fr) minmax(150px, 0.36fr);
                gap: 14px;
                align-items: start;
            }
            .toobusy-ideogram .section-title {
                font-size: 10px;
                text-transform: uppercase;
                letter-spacing: 0.05em;
                color: #7f8b99;
                border-bottom: 1px solid #2a323b;
                padding-bottom: 3px;
                margin: 2px 0 4px;
            }
            .toobusy-ideogram .panel-empty { color: #7f8b99; font-size: 11px; }
            .toobusy-ideogram .side-info { display: flex; flex-direction: column; gap: 4px; }
            .toobusy-ideogram .icon-btn {
                width: 32px;
                height: 30px;
                padding: 0;
                font-size: 15px;
                display: flex;
                align-items: center;
                justify-content: center;
            }
            .toobusy-ideogram .col-left,
            .toobusy-ideogram .col-right {
                display: flex;
                flex-direction: column;
                gap: 8px;
                min-width: 0;
            }
            .toobusy-ideogram .col-center {
                display: flex;
                flex-direction: column;
                gap: 8px;
                min-width: 0;
            }
            .toobusy-ideogram .scene {
                display: flex;
                flex-direction: column;
                gap: 8px;
            }
            .toobusy-ideogram .scene .full { width: 100%; }
            .toobusy-ideogram .resolution {
                display: grid;
                grid-template-columns: minmax(0, 2fr) minmax(0, 1fr) minmax(0, 1fr) auto;
                gap: 7px;
                align-items: end;
                margin-bottom: 8px;
            }
            .toobusy-ideogram .toolbar {
                display: flex;
                gap: 6px;
                margin-bottom: 7px;
                align-items: center;
            }
            .toobusy-ideogram .count-readout {
                color: #9fb0c0;
                font-size: 11px;
            }
            .toobusy-ideogram .layer-list {
                display: flex;
                flex-direction: column;
                gap: 3px;
                max-height: 220px;
                overflow-y: auto;
            }
            .toobusy-ideogram .layer-row {
                display: flex;
                gap: 2px;
                align-items: center;
            }
            .toobusy-ideogram .layer-row.active .layer-name {
                border-color: #6f93c8;
                background: #1d2733;
                color: #ffffff;
            }
            .toobusy-ideogram .layer-name {
                flex: 1 1 auto;
                min-width: 0;
                text-align: left;
                padding: 3px 6px;
                font-size: 11px;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
            }
            .toobusy-ideogram .layer-btn {
                flex: 0 0 auto;
                width: 22px;
                height: 24px;
                padding: 0;
                font-size: 10px;
                line-height: 1;
            }
            .toobusy-ideogram .layer-btn:disabled { opacity: 0.35; cursor: default; }
            .toobusy-ideogram .canvas-frame {
                width: 100%;
                aspect-ratio: 1 / 1;
                max-height: 620px;
                min-height: 320px;
                border: 1px solid #58616d;
                border-radius: 6px;
                background: #0e1319;
                display: flex;
                align-items: center;
                justify-content: center;
                overflow: hidden;
            }
            .toobusy-ideogram canvas {
                width: auto;
                height: auto;
                max-width: 100%;
                max-height: 100%;
                display: block;
                background: #111418;
                cursor: crosshair;
            }
            .toobusy-ideogram label {
                display: flex;
                flex-direction: column;
                gap: 3px;
                color: #aeb8c4;
                min-width: 0;
            }
            .toobusy-ideogram label.checkbox-field {
                flex-direction: row;
                align-items: center;
                gap: 7px;
                cursor: pointer;
            }
            .toobusy-ideogram label.checkbox-field input {
                width: auto;
                flex: 0 0 auto;
                margin: 0;
                cursor: pointer;
            }
            .toobusy-ideogram .output-options {
                display: flex;
                flex-direction: column;
                gap: 6px;
            }
            .toobusy-ideogram input,
            .toobusy-ideogram select,
            .toobusy-ideogram textarea {
                width: 100%;
                border: 1px solid #4d5662;
                border-radius: 6px;
                background: #151a20;
                color: #edf2f7;
                padding: 6px;
                font: inherit;
                resize: vertical;
            }
            .toobusy-ideogram textarea {
                min-height: 72px;
                line-height: 1.4;
            }
            /* Free-text fields: warm neutral accent */
            .toobusy-ideogram textarea,
            .toobusy-ideogram input:not([type="color"]) {
                border-left: 3px solid #8a8170;
                background: #14181d;
            }
            /* Dropdowns: blue accent + custom chevron, clearly different from text */
            .toobusy-ideogram select {
                border-left: 3px solid #4a90e2;
                background-color: #15212c;
                cursor: pointer;
                -webkit-appearance: none;
                appearance: none;
                padding-right: 26px;
                background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6' viewBox='0 0 10 6'%3E%3Cpath d='M1 1l4 4 4-4' stroke='%237fb2e8' stroke-width='1.5' fill='none'/%3E%3C/svg%3E");
                background-repeat: no-repeat;
                background-position: right 9px center;
            }
            /* Preset system dropdown: stronger (green) accent */
            .toobusy-ideogram .preset-bar select {
                border-left: 3px solid #5bc88a;
                background-color: #16241d;
                background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6' viewBox='0 0 10 6'%3E%3Cpath d='M1 1l4 4 4-4' stroke='%238fe0b3' stroke-width='1.5' fill='none'/%3E%3C/svg%3E");
            }
            .toobusy-ideogram button {
                border: 1px solid #4d5662;
                border-radius: 6px;
                background: #252b33;
                color: #edf2f7;
                padding: 5px 9px;
                cursor: pointer;
            }
            .toobusy-ideogram button:hover { background: #303844; }
            .toobusy-ideogram button:disabled {
                opacity: 0.45;
                cursor: default;
            }
            .toobusy-ideogram button:disabled:hover { background: #252b33; }
            .toobusy-ideogram .import-modal-backdrop {
                position: fixed;
                inset: 0;
                z-index: 9999;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 24px;
                background: rgba(3, 6, 10, 0.66);
            }
            .toobusy-ideogram .import-modal-backdrop[hidden] { display: none; }
            .toobusy-ideogram .import-modal {
                width: min(720px, 92vw);
                max-height: 86vh;
                overflow: auto;
                border: 1px solid #596574;
                border-radius: 8px;
                background: #11171f;
                box-shadow: 0 18px 48px rgba(0, 0, 0, 0.45);
                padding: 14px;
                user-select: text;
            }
            .toobusy-ideogram .import-modal-head,
            .toobusy-ideogram .import-modal-actions {
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 10px;
            }
            .toobusy-ideogram .import-modal-title {
                font-size: 13px;
                font-weight: 700;
                color: #edf2f7;
            }
            .toobusy-ideogram .import-modal-subtitle {
                margin: 4px 0 10px;
                color: #9fb0c0;
                font-size: 11px;
            }
            .toobusy-ideogram .import-modal textarea {
                min-height: 260px;
                resize: vertical;
                font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace;
                font-size: 11px;
                line-height: 1.45;
            }
            .toobusy-ideogram .import-modal-status {
                min-height: 52px;
                margin: 10px 0;
                padding: 9px;
                border: 1px solid #35404b;
                border-radius: 6px;
                background: #0d1218;
                color: #cbd5df;
                white-space: pre-wrap;
                overflow-wrap: anywhere;
            }
            .toobusy-ideogram .import-modal-status.error {
                border-color: #7d3d44;
                color: #ffb8c1;
                background: #1a1013;
            }
            .toobusy-ideogram .import-modal-actions {
                justify-content: flex-end;
            }
            .toobusy-ideogram .import-file {
                display: none;
            }
            .toobusy-ideogram .element {
                display: flex;
                flex-direction: column;
                gap: 8px;
                min-width: 0;
            }
            .toobusy-ideogram .bbox {
                color: #cbd5df;
                min-height: 18px;
                overflow-wrap: anywhere;
            }
            .toobusy-ideogram .resolution-readout {
                color: #cbd5df;
                min-height: 27px;
                display: flex;
                align-items: center;
            }
            .toobusy-ideogram .palette-editor {
                display: flex;
                flex-direction: column;
                gap: 3px;
                min-width: 0;
            }
            .toobusy-ideogram .palette-title { color: #aeb8c4; }
            .toobusy-ideogram .clear-colors {
                margin-top: 4px;
                align-self: flex-start;
                font-size: 11px;
                padding: 3px 8px;
            }
            .toobusy-ideogram .clear-colors:disabled { opacity: 0.45; cursor: default; }
            .toobusy-ideogram .palette-row {
                display: flex;
                gap: 5px;
                flex-wrap: wrap;
            }
            .toobusy-ideogram .color-swatch {
                width: 34px;
                height: 26px;
                padding: 0;
                border: 1px solid #6d7784;
                border-radius: 5px;
                cursor: pointer;
                background: none;
                -webkit-appearance: none;
                appearance: none;
            }
            .toobusy-ideogram .color-swatch::-webkit-color-swatch-wrapper { padding: 2px; }
            .toobusy-ideogram .color-swatch::-webkit-color-swatch { border: none; border-radius: 3px; }
            .toobusy-ideogram .palette-preset {
                display: grid;
                grid-template-columns: 150px minmax(0, 1fr);
                gap: 7px;
                align-items: end;
                grid-column: 1 / -1;
            }
        </style>
        <div class="editor">
            <div class="col-left">
                <div class="scene"></div>
            </div>
            <div class="col-center">
                <div class="canvas-frame">
                    <canvas width="1000" height="1000"></canvas>
                </div>
                <div class="resolution"></div>
                <div class="element"></div>
            </div>
            <div class="col-right">
                <div class="toolbar"></div>
                <div class="side-info"></div>
            </div>
        </div>
    `;

    const scene = root.querySelector(".scene");
    const resolutionBar = root.querySelector(".resolution");
    const toolbar = root.querySelector(".toolbar");
    const sideInfo = root.querySelector(".side-info");
    const canvas = root.querySelector("canvas");
    const elementPanel = root.querySelector(".element");
    const bboxReadout = document.createElement("div");
    bboxReadout.className = "bbox";
    const resolutionReadout = document.createElement("div");
    resolutionReadout.className = "resolution-readout";

    let updateCount = () => {};

    function syncElements() {
        jsonWidget.value = JSON.stringify(elements, null, 2);
        jsonWidget.callback?.(jsonWidget.value);
        updateCount();
        node.setDirtyCanvas(true, true);
    }

    function syncScene(name, value) {
        const item = widget(node, name);
        if (!item) return;
        item.value = value;
        item.callback?.(value);
        node.setDirtyCanvas(true, true);
    }

    function selected() {
        return selectedIndex >= 0 ? elements[selectedIndex] : null;
    }

    function selectedOrLast() {
        if (selectedIndex >= 0 && selectedIndex < elements.length) return elements[selectedIndex];
        if (elements.length) {
            selectedIndex = elements.length - 1;
            return elements[selectedIndex];
        }
        return null;
    }

    function persistResolution() {
        node.properties.ideogram_layout_resolution = { ...resolution };
        if (widthWidget) {
            widthWidget.value = resolution.width;
            widthWidget.callback?.(resolution.width);
        }
        if (heightWidget) {
            heightWidget.value = resolution.height;
            heightWidget.callback?.(resolution.height);
        }
        node.setDirtyCanvas(true, true);
    }

    function applyResolution() {
        const frame = canvas.parentElement;
        const frameWidth = frame.clientWidth || 560;
        const frameHeight = frame.clientHeight || 560;
        const scale = Math.min(frameWidth / resolution.width, frameHeight / resolution.height);
        const pixelWidth = Math.max(1, Math.round(resolution.width * scale));
        const pixelHeight = Math.max(1, Math.round(resolution.height * scale));
        // Match the drawing buffer to the real aspect ratio so nothing gets stretched.
        canvas.width = pixelWidth;
        canvas.height = pixelHeight;
        canvas.style.width = `${pixelWidth}px`;
        canvas.style.height = `${pixelHeight}px`;
        resolutionReadout.textContent = `${resolution.width} x ${resolution.height}`;
        persistResolution();
        draw();
    }

    function point(event) {
        const rect = canvas.getBoundingClientRect();
        return {
            x: clamp(((event.clientX - rect.left) / rect.width) * CANVAS_SIZE),
            y: clamp(((event.clientY - rect.top) / rect.height) * CANVAS_SIZE),
        };
    }

    const HANDLE_HIT = 28; // normalized distance to grab a corner handle

    function cornerAt(pos, bbox) {
        const [x1, y1, x2, y2] = bbox;
        const near = (a, b) => Math.abs(pos.x - a) < HANDLE_HIT && Math.abs(pos.y - b) < HANDLE_HIT;
        if (near(x1, y1)) return "nw";
        if (near(x2, y1)) return "ne";
        if (near(x1, y2)) return "sw";
        if (near(x2, y2)) return "se";
        return null;
    }

    function hitTest(pos) {
        for (let i = elements.length - 1; i >= 0; i--) {
            const bbox = elements[i].bbox;
            const [x1, y1, x2, y2] = bbox;
            const corner = cornerAt(pos, bbox);
            if (corner) {
                return { index: i, mode: "resize", handle: corner };
            }
            if (pos.x >= x1 && pos.x <= x2 && pos.y >= y1 && pos.y <= y2) {
                return { index: i, mode: "move" };
            }
        }
        return { index: -1, mode: "none" };
    }

    function drawLabel(ctx, label, x, y, width) {
        const fontSize = 13;
        ctx.font = `${fontSize}px system-ui, sans-serif`;
        let text = label || "";
        while (text.length > 1 && ctx.measureText(text).width > width - 12) {
            text = text.slice(0, -2);
        }
        if (text !== label && text.length > 1) text = `${text}...`;
        ctx.fillText(text, x + 6, y + fontSize + 6);
    }

    function draw() {
        const ctx = canvas.getContext("2d");
        const W = canvas.width;
        const H = canvas.height;
        const fx = W / CANVAS_SIZE;
        const fy = H / CANVAS_SIZE;

        ctx.clearRect(0, 0, W, H);
        ctx.fillStyle = "#151a20";
        ctx.fillRect(0, 0, W, H);

        ctx.strokeStyle = "#2d3642";
        ctx.lineWidth = 1;
        for (let line = 100; line < CANVAS_SIZE; line += 100) {
            ctx.beginPath();
            ctx.moveTo(line * fx, 0);
            ctx.lineTo(line * fx, H);
            ctx.moveTo(0, line * fy);
            ctx.lineTo(W, line * fy);
            ctx.stroke();
        }

        for (const [index, element] of elements.entries()) {
            const [x1, y1, x2, y2] = element.bbox;
            const px = x1 * fx;
            const py = y1 * fy;
            const pw = (x2 - x1) * fx;
            const ph = (y2 - y1) * fy;
            const active = index === selectedIndex;
            const color = element.color_palette?.[0] || "#8AB4F8";
            ctx.fillStyle = `${color}33`;
            ctx.strokeStyle = active ? "#FFFFFF" : color;
            ctx.lineWidth = active ? 3 : 2;
            ctx.fillRect(px, py, pw, ph);
            ctx.strokeRect(px, py, pw, ph);
            ctx.fillStyle = "#FFFFFF";
            drawLabel(ctx, element.text || element.desc || `Element ${index + 1}`, px, py, pw);
            if (active) {
                const hs = 9;
                for (const [cx, cy] of [[px, py], [px + pw, py], [px, py + ph], [px + pw, py + ph]]) {
                    ctx.fillRect(cx - hs / 2, cy - hs / 2, hs, hs);
                }
            }
        }
    }

    function renderElementPanel() {
        elementPanel.replaceChildren();
        renderLayerList();
        const heading = document.createElement("div");
        heading.className = "section-title";
        heading.textContent = "Selected element";
        elementPanel.appendChild(heading);

        const element = selected();
        if (!element) {
            const empty = document.createElement("div");
            empty.className = "panel-empty";
            empty.textContent = "Drag on the canvas to draw a box, or click an existing one.";
            elementPanel.appendChild(empty);
            bboxReadout.textContent = "bbox: —";
            draw();
            return;
        }

        const hasColors = Array.isArray(element.color_palette) && element.color_palette.length > 0;
        const elementPalette = makePaletteEditor(
            hasColors ? "Element colors" : "Element colors (optional, unset)",
            parseColors(element.color_palette, ["#8AB4F8", "#FFFFFF", "#111111"]),
            (colors) => {
                element.color_palette = colors;
                syncElements();
                draw();
            },
            3,
        );

        // Reset this element's palette to "unset" (omitted from the output JSON).
        const clearColors = makeButton("Clear colors", "Reset this element's colors to unset", () => {
            element.color_palette = [];
            syncElements();
            renderElementPanel();
            draw();
        });
        clearColors.classList.add("clear-colors");
        if (!hasColors) clearColors.disabled = true;
        elementPalette.root.appendChild(clearColors);

        elementPanel.append(
            makeField(
                "Text",
                element.text,
                false,
                (value) => {
                    element.text = value;
                    syncElements();
                    draw();
                },
                "Type to render this box as text. Leave blank for an object.",
            ),
            makeSelectField(
                "Role (text hint)",
                ROLE_PRESETS,
                element.role || "",
                (value) => {
                    element.role = value;
                    syncElements();
                    draw();
                },
            ),
            makeField(
                "Description",
                element.desc,
                true,
                (value) => {
                    element.desc = value;
                    syncElements();
                    draw();
                },
                "What this region shows (e.g. 'a woman in a red top').",
            ),
            elementPalette.root,
        );
        bboxReadout.textContent = `bbox: [${element.bbox.join(", ")}]`;
        draw();
    }

    function addElement() {
        elements.push(normalizeElement({}, elements.length));
        selectedIndex = elements.length - 1;
        syncElements();
        renderElementPanel();
    }

    function duplicateElement() {
        const element = selectedOrLast();
        if (!element) {
            addElement();
            return;
        }
        const copy = JSON.parse(JSON.stringify(element));
        const [x1, y1, x2, y2] = copy.bbox;
        const width = Math.max(MIN_BOX_SIZE, x2 - x1);
        const height = Math.max(MIN_BOX_SIZE, y2 - y1);
        const offset = 160;
        let nextX = x1 + offset;
        let nextY = y1 + offset;

        if (nextX + width > CANVAS_SIZE) nextX = Math.max(0, x1 - offset);
        if (nextY + height > CANVAS_SIZE) nextY = Math.max(0, y1 - offset);

        const clampedX = clamp(nextX, 0, Math.max(0, CANVAS_SIZE - width));
        const clampedY = clamp(nextY, 0, Math.max(0, CANVAS_SIZE - height));
        copy.bbox = [
            clampedX,
            clampedY,
            Math.min(CANVAS_SIZE, clampedX + width),
            Math.min(CANVAS_SIZE, clampedY + height),
        ];
        copy.desc = copy.desc || "duplicated layout element";
        elements.push(normalizeElement(copy, elements.length));
        selectedIndex = elements.length - 1;
        syncElements();
        renderElementPanel();
        draw();
    }

    function deleteElement() {
        if (selectedIndex < 0) return;
        elements.splice(selectedIndex, 1);
        selectedIndex = Math.min(selectedIndex, elements.length - 1);
        syncElements();
        renderElementPanel();
    }

    const sceneField = makeField(
        "Scene · whole image",
        widget(node, "high_level_description")?.value,
        true,
        (value) => syncScene("high_level_description", value),
        "One-line summary of the entire image: subject, mood, setting.",
    );
    const backgroundField = makeField(
        "Background · behind subject",
        widget(node, "background")?.value,
        true,
        (value) => syncScene("background", value),
        "Only the environment behind/around the subjects (not the boxes).",
    );
    const styleField = makeSelectField("Style", STYLE_PRESETS, widget(node, "aesthetics")?.value, (value) => syncScene("aesthetics", value));
    const outputField = makeSelectField("Output type", MEDIUM_PRESETS, widget(node, "medium")?.value, (value) => syncScene("medium", value));
    const lightingField = makeSelectField("Lighting", LIGHTING_PRESETS, widget(node, "lighting")?.value, (value) => syncScene("lighting", value));
    const cameraField = makeSelectField("Camera", CAMERA_PRESETS, widget(node, "photo")?.value, (value) => syncScene("photo", value));

    // Map scene widget names to their DOM input so presets can refresh the view.
    const sceneInputs = {
        high_level_description: sceneField.querySelector("textarea, input"),
        background: backgroundField.querySelector("textarea, input"),
        aesthetics: styleField.querySelector("select"),
        medium: outputField.querySelector("select"),
        lighting: lightingField.querySelector("select"),
        photo: cameraField.querySelector("select"),
    };

    // Scene + Background grouped together, then the look/style dropdowns.
    const describeTitle = document.createElement("div");
    describeTitle.className = "section-title";
    describeTitle.textContent = "Describe";
    const styleTitle = document.createElement("div");
    styleTitle.className = "section-title";
    styleTitle.textContent = "Look";
    scene.append(describeTitle, sceneField, backgroundField, styleTitle, styleField, outputField, lightingField, cameraField);

    const palettePresetWrap = document.createElement("div");
    palettePresetWrap.className = "palette-preset";
    const palettePresetLabel = document.createElement("label");
    const palettePresetTitle = document.createElement("span");
    const palettePresetSelect = document.createElement("select");
    palettePresetSelect.id = uid("select");
    palettePresetSelect.name = palettePresetSelect.id;
    palettePresetTitle.textContent = "Palette preset";
    for (const [name] of PALETTE_PRESETS) {
        const option = document.createElement("option");
        option.value = name;
        option.textContent = name;
        palettePresetSelect.appendChild(option);
    }
    palettePresetLabel.append(palettePresetTitle, palettePresetSelect);

    let globalColors = parseColors(widget(node, "global_palette")?.value, PALETTE_PRESETS[0][1]);
    const globalPalette = makePaletteEditor("Global colors", globalColors, (colors) => {
        globalColors = colors;
        syncScene("global_palette", colors.join(", "));
    });
    palettePresetSelect.addEventListener("change", () => {
        const preset = PALETTE_PRESETS.find(([name]) => name === palettePresetSelect.value);
        if (!preset) return;
        globalColors = [...preset[1]];
        globalPalette.swatches.forEach((swatch, index) => {
            const color = (globalColors[index] || "#FFFFFF").toUpperCase();
            swatch.value = color;
            swatch.dataset.color = color;
        });
        syncScene("global_palette", globalColors.join(", "));
    });
    palettePresetWrap.append(palettePresetLabel, globalPalette.root);
    scene.appendChild(palettePresetWrap);

    // ----- Output / text options (drive the hidden BOOLEAN widgets) -----
    const outputTitle = document.createElement("div");
    outputTitle.className = "section-title";
    outputTitle.textContent = "Text & output";
    const outputOptions = document.createElement("div");
    outputOptions.className = "output-options";
    const includePaletteField = makeCheckboxField(
        "Include global palette",
        widget(node, "include_global_palette")?.value ?? true,
        (checked) => syncScene("include_global_palette", checked),
        "When off, the global color_palette is omitted so color is left open.",
    );
    const strictTextField = makeCheckboxField(
        "Strict text rendering",
        widget(node, "strict_text")?.value ?? true,
        (checked) => syncScene("strict_text", checked),
        "Adds 'spelled exactly, sharp, preserve caps/punctuation' to text elements.",
    );
    const reinforceTextField = makeCheckboxField(
        "Reinforce text (“reads ...”)",
        widget(node, "reinforce_text")?.value ?? true,
        (checked) => syncScene("reinforce_text", checked),
        "Off = compact JSON: rely on the text field without repeating it in desc.",
    );
    // Map each toggle widget to its checkbox so presets can refresh the view.
    const toggleInputs = {
        include_global_palette: includePaletteField.querySelector("input"),
        strict_text: strictTextField.querySelector("input"),
        reinforce_text: reinforceTextField.querySelector("input"),
    };
    outputOptions.append(includePaletteField, strictTextField, reinforceTextField);
    scene.append(outputTitle, outputOptions);

    // ----- Layout templates (seed a starting set of boxes) -----
    function applyTemplate(elementSeeds) {
        elements = elementSeeds.map((seed, index) => normalizeElement(seed, index));
        selectedIndex = elements.length ? 0 : -1;
        syncElements();
        renderElementPanel();
        draw();
    }
    const templateField = makeSelectField(
        "Layout template",
        LAYOUT_TEMPLATES.map(([name]) => [name, name]),
        LAYOUT_TEMPLATES[0][0],
        (name) => {
            const tpl = LAYOUT_TEMPLATES.find(([n]) => n === name);
            if (!tpl || !tpl[1]) return;
            const ok = !elements.length || window.confirm("Replace the current boxes with this template?");
            if (ok) applyTemplate(tpl[1]);
            // Reset back to the placeholder option so re-picking the same template works.
            templateField.querySelector("select").value = LAYOUT_TEMPLATES[0][0];
        },
    );
    const templateTitle = document.createElement("div");
    templateTitle.className = "section-title";
    templateTitle.textContent = "Start";
    scene.prepend(templateTitle, templateField);

    const presetLabel = document.createElement("label");
    const presetTitle = document.createElement("span");
    const presetSelect = document.createElement("select");
    presetSelect.id = uid("select");
    presetSelect.name = presetSelect.id;
    presetTitle.textContent = "Canvas preset";
    for (const [id, label] of RESOLUTION_PRESETS) {
        const option = document.createElement("option");
        option.value = id;
        option.textContent = label;
        presetSelect.appendChild(option);
    }
    presetSelect.value = resolution.preset;
    presetLabel.append(presetTitle, presetSelect);

    const widthLabel = document.createElement("label");
    const widthTitle = document.createElement("span");
    const widthInput = makeNumberInput(resolution.width, (value) => {
        resolution = { ...resolution, preset: "custom", width: value };
        presetSelect.value = "custom";
        applyResolution();
    });
    widthTitle.textContent = "Width";
    widthLabel.append(widthTitle, widthInput);

    const heightLabel = document.createElement("label");
    const heightTitle = document.createElement("span");
    const heightInput = makeNumberInput(resolution.height, (value) => {
        resolution = { ...resolution, preset: "custom", height: value };
        presetSelect.value = "custom";
        applyResolution();
    });
    heightTitle.textContent = "Height";
    heightLabel.append(heightTitle, heightInput);

    presetSelect.addEventListener("change", () => {
        const preset = RESOLUTION_PRESETS.find(([id]) => id === presetSelect.value);
        if (!preset) return;
        const [id, , width, height] = preset;
        resolution = { preset: id, width, height };
        widthInput.value = String(width);
        heightInput.value = String(height);
        applyResolution();
    });

    resolutionBar.append(presetLabel, widthLabel, heightLabel, resolutionReadout);

    // Compact icon buttons in the narrow right column.
    const iconAdd = makeButton("＋", "Add element", addElement);
    const iconDup = makeButton("⧉", "Duplicate selected element", duplicateElement);
    const iconDel = makeButton("🗑", "Delete selected element", deleteElement);
    for (const b of [iconAdd, iconDup, iconDel]) b.classList.add("icon-btn");
    toolbar.append(iconAdd, iconDup, iconDel);

    // Small info block (count + bbox) lives in the right column.
    const sideTitle = document.createElement("div");
    sideTitle.className = "section-title";
    sideTitle.textContent = "Info";
    const countReadout = document.createElement("div");
    countReadout.className = "count-readout";
    const layerTitle = document.createElement("div");
    layerTitle.className = "section-title";
    layerTitle.textContent = "Layers";
    const layerList = document.createElement("div");
    layerList.className = "layer-list";
    sideInfo.append(sideTitle, countReadout, bboxReadout, layerTitle, layerList);
    updateCount = () => {
        countReadout.textContent = `${elements.length} box(es)`;
    };
    updateCount();

    // Top-most box is drawn last (highest index); show the list top-to-bottom in
    // that visual stacking order so clicking a row picks even an occluded box.
    function renderLayerList() {
        if (!layerList) return;
        layerList.replaceChildren();
        if (!elements.length) {
            const empty = document.createElement("div");
            empty.className = "panel-empty";
            empty.textContent = "No boxes yet.";
            layerList.appendChild(empty);
            return;
        }
        for (let i = elements.length - 1; i >= 0; i--) {
            const el = elements[i];
            const row = document.createElement("div");
            row.className = "layer-row" + (i === selectedIndex ? " active" : "");

            const isText = !!(el.text && el.text.trim());
            const label = `${isText ? "T" : "□"} ${el.text || el.desc || `Element ${i + 1}`}`;
            const name = makeButton(label, "Select this box", () => {
                selectedIndex = i;
                renderElementPanel();
            });
            name.classList.add("layer-name");

            const raise = makeButton("▲", "Bring forward", () => raiseElement(i));
            const lower = makeButton("▼", "Send backward", () => lowerElement(i));
            const del = makeButton("✕", "Delete this box", () => {
                selectedIndex = i;
                deleteElement();
            });
            for (const b of [raise, lower, del]) b.classList.add("layer-btn");
            if (i === elements.length - 1) raise.disabled = true;
            if (i === 0) lower.disabled = true;

            row.append(name, raise, lower, del);
            layerList.appendChild(row);
        }
    }

    // z-order helpers: swapping array position changes draw/hit-test stacking.
    function swapElements(a, b) {
        if (a < 0 || b < 0 || a >= elements.length || b >= elements.length) return;
        [elements[a], elements[b]] = [elements[b], elements[a]];
        if (selectedIndex === a) selectedIndex = b;
        else if (selectedIndex === b) selectedIndex = a;
        syncElements();
        renderElementPanel();
        draw();
    }
    function raiseElement(i) { swapElements(i, i + 1); }
    function lowerElement(i) { swapElements(i, i - 1); }

    // Nudge the selected box by (dx, dy), keeping its size and staying in bounds.
    function nudgeSelected(dx, dy) {
        const el = selected();
        if (!el) return;
        const w = el.bbox[2] - el.bbox[0];
        const h = el.bbox[3] - el.bbox[1];
        el.bbox[0] = clamp(el.bbox[0] + dx, 0, CANVAS_SIZE - w);
        el.bbox[1] = clamp(el.bbox[1] + dy, 0, CANVAS_SIZE - h);
        el.bbox[2] = el.bbox[0] + w;
        el.bbox[3] = el.bbox[1] + h;
        bboxReadout.textContent = `bbox: [${el.bbox.join(", ")}]`;
        syncElements();
        draw();
    }

    // ----- Presets (saved in the browser via localStorage) -----
    const PRESET_STORE_KEY = "toobusy.ideogram.presets";
    const loadPresets = () => {
        try { return JSON.parse(localStorage.getItem(PRESET_STORE_KEY)) || {}; } catch { return {}; }
    };
    const savePresets = (obj) => {
        try { localStorage.setItem(PRESET_STORE_KEY, JSON.stringify(obj)); } catch {}
    };

    const presetBar = document.createElement("div");
    presetBar.className = "preset-bar";
    const presetBarTitle = document.createElement("span");
    presetBarTitle.className = "preset-bar-title";
    presetBarTitle.textContent = "Preset";
    const presetSelectEl = document.createElement("select");
    presetSelectEl.id = uid("preset");
    presetSelectEl.name = presetSelectEl.id;

    const refreshPresetSelect = (selected) => {
        const presets = loadPresets();
        const names = Object.keys(presets).sort();
        presetSelectEl.replaceChildren();
        if (!names.length) {
            const opt = document.createElement("option");
            opt.value = "";
            opt.textContent = "(no presets)";
            presetSelectEl.appendChild(opt);
        } else {
            for (const name of names) {
                const opt = document.createElement("option");
                opt.value = name;
                opt.textContent = name;
                presetSelectEl.appendChild(opt);
            }
        }
        if (selected) presetSelectEl.value = selected;
    };

    function captureState() {
        return {
            high_level_description: widget(node, "high_level_description")?.value || "",
            aesthetics: widget(node, "aesthetics")?.value || "",
            lighting: widget(node, "lighting")?.value || "",
            photo: widget(node, "photo")?.value || "",
            medium: widget(node, "medium")?.value || "",
            global_palette: widget(node, "global_palette")?.value || "",
            background: widget(node, "background")?.value || "",
            include_global_palette: widget(node, "include_global_palette")?.value ?? true,
            strict_text: widget(node, "strict_text")?.value ?? true,
            reinforce_text: widget(node, "reinforce_text")?.value ?? true,
            elements: JSON.parse(JSON.stringify(elements)),
            resolution: { ...resolution },
        };
    }

    function captureWidgetState() {
        const stored = node.properties?.ideogram_layout_resolution || {};
        return {
            high_level_description: widget(node, "high_level_description")?.value || "",
            aesthetics: widget(node, "aesthetics")?.value || "",
            lighting: widget(node, "lighting")?.value || "",
            photo: widget(node, "photo")?.value || "",
            medium: widget(node, "medium")?.value || "",
            global_palette: widget(node, "global_palette")?.value || "",
            background: widget(node, "background")?.value || "",
            include_global_palette: widget(node, "include_global_palette")?.value ?? true,
            strict_text: widget(node, "strict_text")?.value ?? true,
            reinforce_text: widget(node, "reinforce_text")?.value ?? true,
            elements: parseElements(jsonWidget.value || "[]"),
            resolution: {
                preset: stored.preset || "custom",
                width: stored.width || widthWidget?.value || DEFAULT_LAYOUT_STATE.resolution.width,
                height: stored.height || heightWidget?.value || DEFAULT_LAYOUT_STATE.resolution.height,
            },
        };
    }

    function applyState(state) {
        if (!state) return;
        const setScene = (name, value) => {
            if (value === undefined) return;
            syncScene(name, value);
            const input = sceneInputs[name];
            if (input) input.value = value;
        };
        setScene("high_level_description", state.high_level_description);
        setScene("aesthetics", state.aesthetics);
        setScene("lighting", state.lighting);
        setScene("photo", state.photo);
        setScene("medium", state.medium);
        setScene("background", state.background);

        if (state.global_palette !== undefined) {
            syncScene("global_palette", state.global_palette);
            globalColors = parseColors(state.global_palette, PALETTE_PRESETS[0][1]);
            globalPalette.swatches.forEach((sw, i) => {
                const c = (globalColors[i] || "#FFFFFF").toUpperCase();
                sw.value = c;
                sw.dataset.color = c;
            });
        }

        const setToggle = (name, value) => {
            if (value === undefined) return;
            syncScene(name, !!value);
            const input = toggleInputs[name];
            if (input) input.checked = !!value;
        };
        setToggle("include_global_palette", state.include_global_palette);
        setToggle("strict_text", state.strict_text);
        setToggle("reinforce_text", state.reinforce_text);

        if (Array.isArray(state.elements)) {
            elements = state.elements.map(normalizeElement);
            selectedIndex = elements.length ? 0 : -1;
        }

        if (state.resolution && state.resolution.width && state.resolution.height) {
            resolution = {
                preset: state.resolution.preset || "custom",
                width: clamp(state.resolution.width, 256, 2048),
                height: clamp(state.resolution.height, 256, 2048),
            };
            widthInput.value = String(resolution.width);
            heightInput.value = String(resolution.height);
            presetSelect.value = RESOLUTION_PRESETS.some(([id]) => id === resolution.preset) ? resolution.preset : "custom";
        }

        syncElements();
        renderElementPanel();
        applyResolution();
    }

    function reloadFromWidgets() {
        applyState(captureWidgetState());
    }

    node.__toobusyIdeogramReloadFromWidgets = reloadFromWidgets;

    // Convert a full Ideogram payload (e.g. Prompt Polish output) into the
    // builder's internal state so it can be applied. bbox is swapped from
    // Ideogram order [y,x,y,x] back to canvas order [x,y,x,y]. Returns null if
    // the JSON is not a recognizable payload.
    function payloadToState(payload) {
        if (!payload || typeof payload !== "object" || Array.isArray(payload)) return null;
        const style = payload.style_description && typeof payload.style_description === "object" ? payload.style_description : {};
        const comp = payload.compositional_deconstruction && typeof payload.compositional_deconstruction === "object" ? payload.compositional_deconstruction : null;
        if (!("high_level_description" in payload) && !comp) return null;
        const rawElements = comp && Array.isArray(comp.elements) ? comp.elements : [];
        const elements = rawElements.map((el) => {
            if (el && Array.isArray(el.bbox) && el.bbox.length === 4) {
                const [y1, x1, y2, x2] = el.bbox;
                return { ...el, bbox: [x1, y1, x2, y2] };
            }
            return el;
        });
        return {
            high_level_description: payload.high_level_description || "",
            aesthetics: style.aesthetics || "",
            lighting: style.lighting || "",
            photo: style.photo || "",
            medium: style.medium || "",
            global_palette: Array.isArray(style.color_palette) ? style.color_palette.join(", ") : "",
            background: (comp && comp.background) || "",
            elements,
            resolution: payload.resolution || (payload.width && payload.height ? {
                preset: payload.resolution_preset || "custom",
                width: payload.width,
                height: payload.height,
            } : undefined),
        };
    }

    function stateFromBuilderInputs(inputs = {}) {
        return {
            high_level_description: inputs.high_level_description || "",
            aesthetics: inputs.aesthetics || "",
            lighting: inputs.lighting || "",
            photo: inputs.photo || "",
            medium: inputs.medium || "",
            global_palette: inputs.global_palette || "",
            background: inputs.background || "",
            include_global_palette: inputs.include_global_palette ?? true,
            strict_text: inputs.strict_text ?? true,
            reinforce_text: inputs.reinforce_text ?? true,
            elements: parseElements(inputs.elements_json || "[]"),
            resolution: {
                preset: "custom",
                width: inputs.width || DEFAULT_LAYOUT_STATE.resolution.width,
                height: inputs.height || DEFAULT_LAYOUT_STATE.resolution.height,
            },
        };
    }

    function stateToIdeogramPayload(state) {
        const elements = Array.isArray(state.elements) ? state.elements.map((el) => {
            const normalized = normalizeElement(el);
            const [x1, y1, x2, y2] = normalized.bbox;
            return { ...normalized, bbox: [y1, x1, y2, x2] };
        }) : [];
        return {
            high_level_description: state.high_level_description || "",
            style_description: {
                aesthetics: state.aesthetics || "",
                lighting: state.lighting || "",
                photo: state.photo || "",
                medium: state.medium || "",
                color_palette: parseColors(state.global_palette || "", []),
            },
            compositional_deconstruction: {
                background: state.background || "",
                elements,
            },
            resolution: state.resolution || undefined,
        };
    }

    function decodeBytes(bytes, encoding = "utf-8") {
        try {
            return new TextDecoder(encoding).decode(bytes);
        } catch {
            return String.fromCharCode(...bytes);
        }
    }

    function readPngMetadata(arrayBuffer) {
        const bytes = new Uint8Array(arrayBuffer);
        const signature = [137, 80, 78, 71, 13, 10, 26, 10];
        if (bytes.length < 8 || !signature.every((value, index) => bytes[index] === value)) {
            throw new Error("PNG metadata import only supports PNG files.");
        }

        const view = new DataView(arrayBuffer);
        const fields = [];
        let offset = 8;
        while (offset + 12 <= bytes.length) {
            const length = view.getUint32(offset);
            offset += 4;
            const type = decodeBytes(bytes.slice(offset, offset + 4), "latin1");
            offset += 4;
            if (offset + length + 4 > bytes.length) break;
            const data = bytes.slice(offset, offset + length);
            offset += length + 4; // Skip CRC.

            if (type === "tEXt") {
                const sep = data.indexOf(0);
                if (sep > 0) {
                    fields.push({
                        key: decodeBytes(data.slice(0, sep), "latin1"),
                        value: decodeBytes(data.slice(sep + 1), "latin1"),
                    });
                }
            } else if (type === "iTXt") {
                let pos = data.indexOf(0);
                if (pos > 0 && data[pos + 1] === 0) {
                    const key = decodeBytes(data.slice(0, pos), "utf-8");
                    pos += 3; // null + compression flag + compression method
                    const languageEnd = data.indexOf(0, pos);
                    if (languageEnd >= 0) {
                        const translatedEnd = data.indexOf(0, languageEnd + 1);
                        if (translatedEnd >= 0) {
                            fields.push({
                                key,
                                value: decodeBytes(data.slice(translatedEnd + 1), "utf-8"),
                            });
                        }
                    }
                }
            }
        }
        return fields;
    }

    function stateFromComfyPrompt(prompt) {
        if (!prompt || typeof prompt !== "object" || Array.isArray(prompt)) return null;
        const nodeById = prompt;
        const builderFromInput = (input) => {
            if (!Array.isArray(input) || input.length < 1) return null;
            const linkedNode = nodeById[String(input[0])];
            if (linkedNode && linkedNode.class_type === NODE_CLASS) {
                return {
                    state: stateFromBuilderInputs(linkedNode.inputs || {}),
                    source: `prompt:${NODE_CLASS}#${input[0]}`,
                };
            }
            return null;
        };

        for (const [nodeId, node] of Object.entries(nodeById)) {
            if (node && node.class_type === "ToobusyIdeogram4T2I") {
                const fromPrompt = builderFromInput(node.inputs && node.inputs.prompt);
                if (fromPrompt) return fromPrompt;
            }
        }

        const builders = Object.entries(nodeById)
            .filter(([, node]) => node && node.class_type === NODE_CLASS);
        if (builders.length === 1) {
            const [nodeId, node] = builders[0];
            return {
                state: stateFromBuilderInputs(node.inputs || {}),
                source: `prompt:${NODE_CLASS}#${nodeId}`,
            };
        }
        return null;
    }

    function stateFromWorkflowBuilderNode(node) {
        const values = Array.isArray(node.widgets_values) ? node.widgets_values : [];
        const resolutionState = node.properties && node.properties.ideogram_layout_resolution;
        return {
            high_level_description: values[1] || "",
            aesthetics: values[2] || "",
            lighting: values[3] || "",
            photo: values[4] || "",
            medium: values[5] || "",
            global_palette: values[6] || "",
            include_global_palette: values[7] ?? true,
            strict_text: values[8] ?? true,
            reinforce_text: values[9] ?? true,
            background: values[10] || "",
            elements: parseElements(values[11] || "[]"),
            resolution: {
                preset: resolutionState?.preset || "custom",
                width: values[12] || resolutionState?.width || DEFAULT_LAYOUT_STATE.resolution.width,
                height: values[13] || resolutionState?.height || DEFAULT_LAYOUT_STATE.resolution.height,
            },
        };
    }

    function stateFromComfyWorkflow(workflow) {
        if (!workflow || typeof workflow !== "object" || Array.isArray(workflow)) return null;
        const nodes = Array.isArray(workflow.nodes) ? workflow.nodes : [];
        const nodeById = Object.fromEntries(nodes.map((node) => [String(node.id), node]));
        const links = Array.isArray(workflow.links) ? workflow.links : [];
        const linkById = Object.fromEntries(links.map((link) => [String(link[0]), link]));
        const builderFromInput = (input) => {
            const link = input && input.link != null ? linkById[String(input.link)] : null;
            const linkedNode = link ? nodeById[String(link[1])] : null;
            if (linkedNode && linkedNode.type === NODE_CLASS) {
                return {
                    state: stateFromWorkflowBuilderNode(linkedNode),
                    source: `workflow:${NODE_CLASS}#${linkedNode.id}`,
                };
            }
            return null;
        };

        for (const node of nodes) {
            if (node && node.type === "ToobusyIdeogram4T2I") {
                const promptInput = (node.inputs || []).find((input) => input.name === "prompt");
                const fromPrompt = builderFromInput(promptInput);
                if (fromPrompt) return fromPrompt;
            }
        }

        const builders = nodes.filter((node) => node && node.type === NODE_CLASS);
        if (builders.length === 1) {
            const node = builders[0];
            return {
                state: stateFromWorkflowBuilderNode(node),
                source: `workflow:${NODE_CLASS}#${node.id}`,
            };
        }
        return null;
    }

    function findPayloadInMetadata(value, seen = new WeakSet()) {
        if (value && typeof value === "object") {
            if (seen.has(value)) return null;
            seen.add(value);
            if (payloadToState(value)) return value;
            const entries = Array.isArray(value) ? value : Object.values(value);
            for (const item of entries) {
                const found = findPayloadInMetadata(item, seen);
                if (found) return found;
            }
            return null;
        }

        if (typeof value !== "string") return null;
        const trimmed = value.trim();
        if (!trimmed) return null;
        const candidates = [trimmed];
        const firstBrace = trimmed.indexOf("{");
        const lastBrace = trimmed.lastIndexOf("}");
        if (firstBrace >= 0 && lastBrace > firstBrace) {
            candidates.push(trimmed.slice(firstBrace, lastBrace + 1));
        }

        for (const candidate of candidates) {
            try {
                const parsed = JSON.parse(candidate);
                const found = findPayloadInMetadata(parsed, seen);
                if (found) return found;
            } catch {}
        }
        return null;
    }

    function payloadFromPngMetadata(fields) {
        for (const field of fields.filter((item) => item.key === "prompt")) {
            try {
                const prompt = JSON.parse(field.value);
                const found = stateFromComfyPrompt(prompt);
                if (found) {
                    return {
                        payload: stateToIdeogramPayload(found.state),
                        source: found.source,
                    };
                }
            } catch {}
        }

        for (const field of fields.filter((item) => item.key === "workflow")) {
            try {
                const workflow = JSON.parse(field.value);
                const found = stateFromComfyWorkflow(workflow);
                if (found) {
                    return {
                        payload: stateToIdeogramPayload(found.state),
                        source: found.source,
                    };
                }
            } catch {}
        }

        const preferred = ["ideogram_json", "prompt", "workflow", "parameters"];
        const ordered = [
            ...preferred.flatMap((key) => fields.filter((field) => field.key === key)),
            ...fields.filter((field) => !preferred.includes(field.key)),
        ];
        for (const field of ordered) {
            const payload = findPayloadInMetadata(field.value);
            if (payload) return { payload, source: field.key };
        }
        return null;
    }

    function resetLayout() {
        const ok = window.confirm("Reset this Layout Builder to the default empty layout?");
        if (!ok) return;
        applyState(JSON.parse(JSON.stringify(DEFAULT_LAYOUT_STATE)));
    }

    let importDialog = null;
    function openImportPolishedDialog() {
        if (!importDialog) {
            const backdrop = document.createElement("div");
            backdrop.className = "import-modal-backdrop";
            backdrop.hidden = true;

            const modal = document.createElement("div");
            modal.className = "import-modal";
            modal.addEventListener("pointerdown", (event) => event.stopPropagation());
            modal.addEventListener("pointerup", (event) => event.stopPropagation());

            const head = document.createElement("div");
            head.className = "import-modal-head";
            const title = document.createElement("div");
            title.className = "import-modal-title";
            title.textContent = "Import polished";
            const closeButton = makeButton("Close", "Close without changing the layout", () => close());
            head.append(title, closeButton);

            const subtitle = document.createElement("div");
            subtitle.className = "import-modal-subtitle";
            subtitle.textContent = "Paste Prompt Polish ideogram_json, or load a PNG with ComfyUI metadata. Nothing changes until Apply.";

            const textarea = document.createElement("textarea");
            textarea.spellcheck = false;
            textarea.placeholder = "{\n  \"high_level_description\": \"...\",\n  \"compositional_deconstruction\": { \"elements\": [...] }\n}";

            const status = document.createElement("div");
            status.className = "import-modal-status";

            const actions = document.createElement("div");
            actions.className = "import-modal-actions";
            const fileInput = document.createElement("input");
            fileInput.type = "file";
            fileInput.accept = "image/png";
            fileInput.className = "import-file";
            const imageButton = makeButton("Load PNG", "Read Ideogram JSON from PNG metadata", () => fileInput.click());
            const cancelButton = makeButton("Cancel", "Close without changing the layout", () => close());
            const applyButton = makeButton("Apply", "Replace the current layout with this parsed payload", () => {
                if (!importDialog.state) return;
                applyState(importDialog.state);
                close();
            });
            applyButton.disabled = true;
            actions.append(imageButton, cancelButton, applyButton);

            modal.append(head, subtitle, textarea, status, fileInput, actions);
            backdrop.appendChild(modal);
            root.appendChild(backdrop);

            const setStatus = (message, isError = false) => {
                status.textContent = message;
                status.classList.toggle("error", isError);
            };
            const validate = () => {
                const raw = textarea.value.trim();
                importDialog.state = null;
                applyButton.disabled = true;
                if (!raw) {
                    setStatus("Paste ideogram_json to preview the scene and element count.", false);
                    return;
                }
                let parsed;
                try {
                    parsed = JSON.parse(raw);
                } catch (err) {
                    setStatus(`JSON parse error: ${err.message}`, true);
                    return;
                }
                const state = payloadToState(parsed);
                if (!state) {
                    setStatus("Ideogram payload shape not recognized. Expected high_level_description and/or compositional_deconstruction.elements.", true);
                    return;
                }
                importDialog.state = state;
                applyButton.disabled = false;
                const scenePreview = state.high_level_description || "(no scene)";
                const fields = [
                    `Elements: ${state.elements.length}`,
                    `Scene: ${scenePreview}`,
                    state.background ? `Background: ${state.background}` : "",
                    state.global_palette ? `Palette: ${state.global_palette}` : "",
                ].filter(Boolean);
                setStatus(`${fields.join("\n")}\n\nApply will replace the current canvas boxes and scene/style fields.`, false);
            };
            textarea.addEventListener("input", validate);
            fileInput.addEventListener("change", async () => {
                const file = fileInput.files && fileInput.files[0];
                fileInput.value = "";
                if (!file) return;
                try {
                    const fields = readPngMetadata(await file.arrayBuffer());
                    const found = payloadFromPngMetadata(fields);
                    if (!found) {
                        setStatus("No Prompt Polish / Ideogram JSON payload found in this PNG metadata.", true);
                        return;
                    }
                    textarea.value = JSON.stringify(found.payload, null, 2);
                    validate();
                    if (importDialog.state) {
                        setStatus(`${status.textContent}\n\nLoaded from PNG metadata field: ${found.source}`, false);
                    }
                } catch (err) {
                    setStatus(`Image metadata import error: ${err.message}`, true);
                }
            });

            const close = () => {
                backdrop.hidden = true;
                importDialog.state = null;
            };
            const open = () => {
                textarea.value = "";
                validate();
                backdrop.hidden = false;
                setTimeout(() => textarea.focus(), 0);
            };
            backdrop.addEventListener("pointerdown", (event) => {
                if (event.target === backdrop) close();
            });
            root.addEventListener("keydown", (event) => {
                if (!backdrop.hidden && event.key === "Escape") {
                    event.preventDefault();
                    close();
                }
            });
            importDialog = { open, state: null };
        }
        importDialog.open();
    }

    presetBar.append(
        presetBarTitle,
        presetSelectEl,
        makeButton("Import polished", "Paste a Prompt Polish / Ideogram JSON to load it (preview before it replaces the layout)", openImportPolishedDialog),
        makeButton("Reset", "Reset this builder to a fresh empty layout", resetLayout),
        makeButton("Save", "Save current layout as a named preset", () => {
            const name = (window.prompt("Preset name:") || "").trim();
            if (!name) return;
            const presets = loadPresets();
            presets[name] = captureState();
            savePresets(presets);
            refreshPresetSelect(name);
        }),
        makeButton("Load", "Load the selected preset", () => {
            const name = presetSelectEl.value;
            if (!name) return;
            applyState(loadPresets()[name]);
        }),
        makeButton("Delete", "Delete the selected preset", () => {
            const name = presetSelectEl.value;
            if (!name) return;
            const presets = loadPresets();
            delete presets[name];
            savePresets(presets);
            refreshPresetSelect();
        }),
    );
    refreshPresetSelect();
    root.insertBefore(presetBar, root.querySelector(".editor"));

    const DRAG_THRESHOLD = 28; // normalized units before an empty-canvas drag becomes a new box

    // Make the canvas focusable so it can receive keyboard shortcuts.
    canvas.tabIndex = 0;
    canvas.style.outline = "none";

    canvas.addEventListener("pointerdown", (event) => {
        canvas.focus();
        const pos = point(event);
        const hit = hitTest(pos);
        if (hit.index >= 0) {
            selectedIndex = hit.index;
            drag = { mode: hit.mode, handle: hit.handle, start: pos, bbox: [...selected().bbox] };
            canvas.setPointerCapture(event.pointerId);
            renderElementPanel();
            return;
        }

        // Empty canvas: wait for an actual drag before creating a box (a plain
        // click should just deselect, not spawn a tiny box).
        drag = { mode: "pending", start: pos };
        canvas.setPointerCapture(event.pointerId);
    });

    const CURSOR_FOR_HANDLE = { nw: "nwse-resize", se: "nwse-resize", ne: "nesw-resize", sw: "nesw-resize" };

    canvas.addEventListener("pointermove", (event) => {
        const pos = point(event);

        if (!drag) {
            // Hover feedback: resize cursor on corners, move cursor inside a box.
            const hit = hitTest(pos);
            canvas.style.cursor = hit.mode === "resize"
                ? CURSOR_FOR_HANDLE[hit.handle] || "crosshair"
                : hit.mode === "move" ? "move" : "crosshair";
            return;
        }

        if (drag.mode === "pending") {
            if (Math.abs(pos.x - drag.start.x) < DRAG_THRESHOLD && Math.abs(pos.y - drag.start.y) < DRAG_THRESHOLD) {
                return;
            }
            // Threshold crossed: materialize the new box and switch to create mode.
            const fresh = normalizeElement({ bbox: [drag.start.x, drag.start.y, drag.start.x + MIN_BOX_SIZE, drag.start.y + MIN_BOX_SIZE] }, elements.length);
            fresh.desc = "";
            elements.push(fresh);
            selectedIndex = elements.length - 1;
            drag = { mode: "create", start: drag.start, bbox: [...fresh.bbox] };
            renderElementPanel();
        }

        if (selectedIndex < 0) return;
        const dx = pos.x - drag.start.x;
        const dy = pos.y - drag.start.y;
        const element = selected();
        const bbox = [...drag.bbox];
        if (drag.mode === "create") {
            bbox[0] = clamp(Math.min(drag.start.x, pos.x));
            bbox[1] = clamp(Math.min(drag.start.y, pos.y));
            bbox[2] = Math.max(bbox[0] + MIN_BOX_SIZE, clamp(Math.max(drag.start.x, pos.x)));
            bbox[3] = Math.max(bbox[1] + MIN_BOX_SIZE, clamp(Math.max(drag.start.y, pos.y)));
        } else if (drag.mode === "resize") {
            const handle = drag.handle || "se";
            let [a, b, c, d] = drag.bbox; // x1, y1, x2, y2
            if (handle.includes("w")) a = clamp(a + dx);
            if (handle.includes("e")) c = clamp(c + dx);
            if (handle.includes("n")) b = clamp(b + dy);
            if (handle.includes("s")) d = clamp(d + dy);
            // Normalize ordering and enforce a minimum size.
            let x1 = Math.min(a, c);
            let x2 = Math.max(a, c);
            let y1 = Math.min(b, d);
            let y2 = Math.max(b, d);
            if (x2 - x1 < MIN_BOX_SIZE) {
                if (handle.includes("w")) x1 = x2 - MIN_BOX_SIZE; else x2 = x1 + MIN_BOX_SIZE;
            }
            if (y2 - y1 < MIN_BOX_SIZE) {
                if (handle.includes("n")) y1 = y2 - MIN_BOX_SIZE; else y2 = y1 + MIN_BOX_SIZE;
            }
            bbox[0] = clamp(x1);
            bbox[1] = clamp(y1);
            bbox[2] = clamp(x2);
            bbox[3] = clamp(y2);
        } else {
            const width = bbox[2] - bbox[0];
            const height = bbox[3] - bbox[1];
            bbox[0] = clamp(bbox[0] + dx, 0, CANVAS_SIZE - width);
            bbox[1] = clamp(bbox[1] + dy, 0, CANVAS_SIZE - height);
            bbox[2] = bbox[0] + width;
            bbox[3] = bbox[1] + height;
        }
        element.bbox = bbox;
        bboxReadout.textContent = `bbox: [${element.bbox.join(", ")}]`;
        syncElements();
        draw();
    });

    canvas.addEventListener("pointerup", (event) => {
        const mode = drag?.mode;
        drag = null;
        try {
            canvas.releasePointerCapture(event.pointerId);
        } catch {}
        if (mode === "pending") {
            // Plain click on empty canvas -> deselect, don't create anything.
            selectedIndex = -1;
            renderElementPanel();
        } else if (mode === "create") {
            syncElements();
            renderElementPanel();
        }
    });

    // Keyboard shortcuts while the canvas is focused: Delete/Backspace removes
    // the selected box, arrows nudge it (Shift = larger step), Esc deselects.
    canvas.addEventListener("keydown", (event) => {
        if (event.key === "Delete" || event.key === "Backspace") {
            if (selectedIndex < 0) return;
            event.preventDefault();
            deleteElement();
            return;
        }
        if (event.key === "Escape") {
            if (selectedIndex < 0) return;
            event.preventDefault();
            selectedIndex = -1;
            renderElementPanel();
            return;
        }
        const step = event.shiftKey ? 20 : 5;
        const nudges = {
            ArrowUp: [0, -step], ArrowDown: [0, step],
            ArrowLeft: [-step, 0], ArrowRight: [step, 0],
        };
        if (nudges[event.key]) {
            if (selectedIndex < 0) return;
            event.preventDefault();
            nudgeSelected(nudges[event.key][0], nudges[event.key][1]);
        }
    });

    if (!elements.length) addElement();
    syncElements();
    renderElementPanel();
    applyResolution();

    const PREFERRED_WIDTH = 980;
    const MIN_WIDTH = 900;
    root.style.overflowY = "visible";

    // Height tracks the actual content so the node fits snugly (no empty gap or
    // inner scrollbar).
    const measuredHeight = () => Math.max(300, Math.ceil(root.scrollHeight) + 8);

    const domWidget = node.addDOMWidget("layout_editor", "toobusy_ideogram_layout", root, {
        getMinHeight: measuredHeight,
        getMaxHeight: () => 1600,
        getHeight: measuredHeight,
    });

    if (domWidget && node.widgets?.includes(domWidget)) {
        node.widgets = [domWidget, ...node.widgets.filter((item) => item !== domWidget)];
    }

    const originalComputeSize = node.computeSize;
    node.computeSize = function computeSize(out) {
        const size = originalComputeSize?.call(this, out) || [MIN_WIDTH, measuredHeight()];
        return [Math.max(size[0], MIN_WIDTH), size[1]];
    };

    // Keep the canvas pixel buffer matched to its (fixed-height) frame.
    new ResizeObserver(applyResolution).observe(canvas.parentElement);

    const ensurePreferredSize = () => {
        const w = Math.max(node.size?.[0] || 0, PREFERRED_WIDTH);
        node.setSize([w, node.computeSize()[1]]);
        node.setDirtyCanvas(true, true);
    };

    requestAnimationFrame(() => { applyResolution(); ensurePreferredSize(); });
    setTimeout(ensurePreferredSize, 50);

    const originalOnConfigure = node.onConfigure;
    node.onConfigure = function onConfigure() {
        const result = originalOnConfigure?.apply(this, arguments);
        requestAnimationFrame(() => {
            reloadFromWidgets();
            ensurePreferredSize();
        });
        return result;
    };

    setTimeout(reloadFromWidgets, 0);
}

app.registerExtension({
    name: "toobusy.ideogram.layout_builder",
    async nodeCreated(node) {
        if (node.comfyClass === NODE_CLASS) installEditor(node);
    },
});
