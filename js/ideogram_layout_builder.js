import { app } from "../../scripts/app.js";

const NODE_CLASS = "IdeogramLayoutBuilder";
const CANVAS_SIZE = 1000;
const MIN_BOX_SIZE = 40;

const RESOLUTION_PRESETS = [
    ["square_1024", "Square 1:1", 1024, 1024],
    ["portrait_9_16", "Portrait 9:16", 1024, 1792],
    ["portrait_3_4", "Portrait 3:4", 1024, 1365],
    ["portrait_2_3", "Portrait 2:3", 1024, 1536],
    ["landscape_16_9", "Landscape 16:9", 1792, 1024],
    ["landscape_4_3", "Landscape 4:3", 1365, 1024],
    ["landscape_3_2", "Landscape 3:2", 1536, 1024],
    ["wide_21_9", "Wide 21:9", 2048, 878],
    ["custom", "Custom", 1024, 1024],
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
        const elements = Array.isArray(parsed) ? parsed : parsed.elements;
        return Array.isArray(elements) ? elements : [];
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

function makeNumberInput(value, onInput) {
    const input = document.createElement("input");
    input.type = "number";
    input.id = uid("num");
    input.name = input.id;
    input.min = "256";
    input.max = "2048";
    input.step = "1";
    input.value = String(value);
    input.addEventListener("input", () => onInput(clamp(input.value, 256, 2048)));
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
        preset: storedResolution.preset || "square_1024",
        width: clamp(storedResolution.width || widthWidget?.value || 1024, 256, 2048),
        height: clamp(storedResolution.height || heightWidget?.value || 1024, 256, 2048),
    };

    const root = document.createElement("div");
    root.className = "toobusy-ideogram";
    root.innerHTML = `
        <style>
            .toobusy-ideogram {
                box-sizing: border-box;
                width: 100%;
                min-width: 340px;
                color: #e9edf1;
                font: 12px/1.35 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
                user-select: none;
            }
            .toobusy-ideogram * { box-sizing: border-box; }
            .toobusy-ideogram .scene {
                display: grid;
                grid-template-columns: repeat(2, minmax(0, 1fr));
                gap: 8px 10px;
                margin-bottom: 10px;
            }
            .toobusy-ideogram .scene .full { grid-column: 1 / -1; }
            .toobusy-ideogram .workspace {
                display: flex;
                flex-direction: column;
                gap: 10px;
            }
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
                margin-left: auto;
                color: #9fb0c0;
                font-size: 11px;
            }
            .toobusy-ideogram .canvas-frame {
                width: 100%;
                height: 360px;
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
            .toobusy-ideogram button {
                border: 1px solid #4d5662;
                border-radius: 6px;
                background: #252b33;
                color: #edf2f7;
                padding: 5px 9px;
                cursor: pointer;
            }
            .toobusy-ideogram button:hover { background: #303844; }
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
        <div class="scene"></div>
        <div class="resolution"></div>
        <div class="toolbar"></div>
        <div class="workspace">
            <div class="canvas-frame">
                <canvas width="1000" height="1000"></canvas>
            </div>
            <div class="element"></div>
        </div>
    `;

    const scene = root.querySelector(".scene");
    const resolutionBar = root.querySelector(".resolution");
    const toolbar = root.querySelector(".toolbar");
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

    function hitTest(pos) {
        for (let i = elements.length - 1; i >= 0; i--) {
            const [x1, y1, x2, y2] = elements[i].bbox;
            if (pos.x >= x1 && pos.x <= x2 && pos.y >= y1 && pos.y <= y2) {
                const resize = Math.abs(pos.x - x2) < 26 && Math.abs(pos.y - y2) < 26;
                return { index: i, mode: resize ? "resize" : "move" };
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
            if (active) ctx.fillRect(px + pw - 10, py + ph - 10, 10, 10);
        }
    }

    function renderElementPanel() {
        elementPanel.replaceChildren();
        const element = selected();
        if (!element) {
            const empty = document.createElement("div");
            empty.textContent = "Drag on the canvas to draw a box, or click an existing one.";
            elementPanel.appendChild(empty);
            draw();
            return;
        }

        const elementPalette = makePaletteEditor(
            "Element colors (optional)",
            parseColors(element.color_palette, ["#8AB4F8", "#FFFFFF", "#111111"]),
            (colors) => {
                element.color_palette = colors;
                syncElements();
                draw();
            },
            3,
        );

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
            bboxReadout,
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

    const sceneField = makeField("Scene", widget(node, "high_level_description")?.value, true, (value) => syncScene("high_level_description", value));
    const backgroundField = makeField("Background", widget(node, "background")?.value, true, (value) => syncScene("background", value));
    sceneField.classList.add("full");
    backgroundField.classList.add("full");

    // Full-width text areas, then the four preset selects in a tidy 2x2 grid.
    scene.append(
        sceneField,
        makeSelectField("Style", STYLE_PRESETS, widget(node, "aesthetics")?.value, (value) => syncScene("aesthetics", value)),
        makeSelectField("Output type", MEDIUM_PRESETS, widget(node, "medium")?.value, (value) => syncScene("medium", value)),
        makeSelectField("Lighting", LIGHTING_PRESETS, widget(node, "lighting")?.value, (value) => syncScene("lighting", value)),
        makeSelectField("Camera", CAMERA_PRESETS, widget(node, "photo")?.value, (value) => syncScene("photo", value)),
        backgroundField,
    );

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

    toolbar.append(
        makeButton("+ Element", "Add element", addElement),
        makeButton("Duplicate", "Duplicate selected element", duplicateElement),
        makeButton("Delete", "Delete selected element", deleteElement),
    );

    const countReadout = document.createElement("span");
    countReadout.className = "count-readout";
    toolbar.appendChild(countReadout);
    updateCount = () => {
        countReadout.textContent = `${elements.length} element(s)`;
    };
    updateCount();

    const DRAG_THRESHOLD = 10; // normalized units before an empty-canvas drag becomes a new box

    canvas.addEventListener("pointerdown", (event) => {
        const pos = point(event);
        const hit = hitTest(pos);
        if (hit.index >= 0) {
            selectedIndex = hit.index;
            drag = { mode: hit.mode, start: pos, bbox: [...selected().bbox] };
            canvas.setPointerCapture(event.pointerId);
            renderElementPanel();
            return;
        }

        // Empty canvas: wait for an actual drag before creating a box (a plain
        // click should just deselect, not spawn a tiny box).
        drag = { mode: "pending", start: pos };
        canvas.setPointerCapture(event.pointerId);
    });

    canvas.addEventListener("pointermove", (event) => {
        if (!drag) return;
        const pos = point(event);

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
            bbox[2] = Math.max(bbox[0] + 20, clamp(bbox[2] + dx));
            bbox[3] = Math.max(bbox[1] + 20, clamp(bbox[3] + dy));
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

    if (!elements.length) addElement();
    syncElements();
    renderElementPanel();
    applyResolution();

    // Preferred height fits the whole editor; the root scrolls internally so the
    // user can freely shrink the node (getMinHeight stays small) without clipping.
    const PREFERRED_HEIGHT = 900;
    root.style.overflowY = "auto";

    const domWidget = node.addDOMWidget("layout_editor", "toobusy_ideogram_layout", root, {
        getMinHeight: () => 320,
        getMaxHeight: () => 1600,
        getHeight: () => PREFERRED_HEIGHT,
    });

    if (domWidget && node.widgets?.includes(domWidget)) {
        node.widgets = [domWidget, ...node.widgets.filter((item) => item !== domWidget)];
    }

    const MIN_WIDTH = 420;
    // Keep computeSize's minimum small so the user can still shrink the node
    // (the root scrolls internally); we set the preferred size explicitly below.
    const originalComputeSize = node.computeSize;
    node.computeSize = function computeSize(out) {
        const size = originalComputeSize?.call(this, out) || [MIN_WIDTH, 320];
        return [Math.max(size[0], MIN_WIDTH), size[1]];
    };

    // Keep the canvas pixel buffer matched to its (fixed-height) frame.
    new ResizeObserver(applyResolution).observe(canvas.parentElement);

    const ensurePreferredSize = () => {
        const w = Math.max(node.size?.[0] || 0, MIN_WIDTH);
        const h = Math.max(node.size?.[1] || 0, PREFERRED_HEIGHT);
        node.setSize([w, h]);
        node.setDirtyCanvas(true, true);
    };

    // Apply the preferred size on first mount and again after ComfyUI restores a
    // saved (possibly too-short) size when loading a workflow.
    requestAnimationFrame(() => { applyResolution(); ensurePreferredSize(); });
    setTimeout(ensurePreferredSize, 50);

    const originalOnConfigure = node.onConfigure;
    node.onConfigure = function onConfigure() {
        const result = originalOnConfigure?.apply(this, arguments);
        requestAnimationFrame(ensurePreferredSize);
        return result;
    };
}

app.registerExtension({
    name: "toobusy.ideogram.layout_builder",
    async nodeCreated(node) {
        if (node.comfyClass === NODE_CLASS) installEditor(node);
    },
});
