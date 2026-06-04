import { app } from "../../scripts/app.js";

const NODE_CLASS = "IdeogramLayoutBuilder";
const CANVAS_SIZE = 1000;

const SCENE_FIELDS = [
    ["high_level_description", "Scene", "textarea"],
    ["aesthetics", "Aesthetics", "textarea"],
    ["lighting", "Lighting", "textarea"],
    ["photo", "Photo", "input"],
    ["medium", "Medium", "input"],
    ["global_palette", "Global palette", "input"],
    ["background", "Background", "textarea"],
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
    const bbox = Array.isArray(element.bbox) && element.bbox.length === 4 ? element.bbox.map(clamp) : fallback;
    if (bbox[2] <= bbox[0]) bbox[2] = Math.min(CANVAS_SIZE, bbox[0] + 20);
    if (bbox[3] <= bbox[1]) bbox[3] = Math.min(CANVAS_SIZE, bbox[1] + 20);
    return {
        type: "obj",
        bbox,
        text: element.text || "",
        desc: element.desc || "new layout element",
        color_palette: Array.isArray(element.color_palette) ? element.color_palette : ["#8AB4F8", "#FFFFFF"],
    };
}

function makeButton(text, title, onClick) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = text;
    button.title = title;
    button.addEventListener("click", onClick);
    return button;
}

function makeField(labelText, value, multiline, onInput) {
    const label = document.createElement("label");
    const span = document.createElement("span");
    const input = multiline ? document.createElement("textarea") : document.createElement("input");
    span.textContent = labelText;
    input.value = value || "";
    if (multiline) input.rows = 2;
    input.addEventListener("input", () => onInput(input.value));
    label.append(span, input);
    return label;
}

function installEditor(node) {
    if (node.__drawingsIdeogramInstalled) return;
    node.__drawingsIdeogramInstalled = true;

    const jsonWidget = widget(node, "elements_json");
    if (!jsonWidget) return;

    hideNativeWidgets(node);

    let elements = parseElements(jsonWidget.value).map(normalizeElement);
    let selectedIndex = elements.length ? 0 : -1;
    let drag = null;

    const root = document.createElement("div");
    root.className = "drawings-ideogram";
    root.innerHTML = `
        <style>
            .drawings-ideogram {
                box-sizing: border-box;
                width: 100%;
                min-width: 620px;
                color: #e9edf1;
                font: 12px/1.35 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
                user-select: none;
            }
            .drawings-ideogram * { box-sizing: border-box; }
            .drawings-ideogram .scene {
                display: grid;
                grid-template-columns: repeat(2, minmax(0, 1fr));
                gap: 7px;
                margin-bottom: 8px;
            }
            .drawings-ideogram .workspace {
                display: grid;
                grid-template-columns: minmax(360px, 1fr) 230px;
                gap: 10px;
            }
            .drawings-ideogram .toolbar {
                display: flex;
                gap: 6px;
                margin-bottom: 7px;
            }
            .drawings-ideogram canvas {
                width: 100%;
                aspect-ratio: 1 / 1;
                display: block;
                border: 1px solid #58616d;
                border-radius: 6px;
                background: #111418;
                cursor: crosshair;
            }
            .drawings-ideogram label {
                display: flex;
                flex-direction: column;
                gap: 3px;
                color: #aeb8c4;
                min-width: 0;
            }
            .drawings-ideogram input,
            .drawings-ideogram textarea {
                width: 100%;
                border: 1px solid #4d5662;
                border-radius: 6px;
                background: #151a20;
                color: #edf2f7;
                padding: 6px;
                font: inherit;
                resize: vertical;
            }
            .drawings-ideogram button {
                border: 1px solid #4d5662;
                border-radius: 6px;
                background: #252b33;
                color: #edf2f7;
                padding: 5px 9px;
                cursor: pointer;
            }
            .drawings-ideogram button:hover { background: #303844; }
            .drawings-ideogram .element {
                display: flex;
                flex-direction: column;
                gap: 8px;
                min-width: 0;
            }
            .drawings-ideogram .bbox {
                color: #cbd5df;
                min-height: 18px;
                overflow-wrap: anywhere;
            }
        </style>
        <div class="scene"></div>
        <div class="toolbar"></div>
        <div class="workspace">
            <canvas width="1000" height="1000"></canvas>
            <div class="element"></div>
        </div>
    `;

    const scene = root.querySelector(".scene");
    const toolbar = root.querySelector(".toolbar");
    const canvas = root.querySelector("canvas");
    const elementPanel = root.querySelector(".element");
    const bboxReadout = document.createElement("div");
    bboxReadout.className = "bbox";

    function syncElements() {
        jsonWidget.value = JSON.stringify(elements, null, 2);
        jsonWidget.callback?.(jsonWidget.value);
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

    function draw() {
        const ctx = canvas.getContext("2d");
        ctx.clearRect(0, 0, CANVAS_SIZE, CANVAS_SIZE);
        ctx.fillStyle = "#151a20";
        ctx.fillRect(0, 0, CANVAS_SIZE, CANVAS_SIZE);

        ctx.strokeStyle = "#2d3642";
        ctx.lineWidth = 1;
        for (let line = 100; line < CANVAS_SIZE; line += 100) {
            ctx.beginPath();
            ctx.moveTo(line, 0);
            ctx.lineTo(line, CANVAS_SIZE);
            ctx.moveTo(0, line);
            ctx.lineTo(CANVAS_SIZE, line);
            ctx.stroke();
        }

        for (const [index, element] of elements.entries()) {
            const [x1, y1, x2, y2] = element.bbox;
            const active = index === selectedIndex;
            const color = element.color_palette?.[0] || "#8AB4F8";
            ctx.fillStyle = `${color}33`;
            ctx.strokeStyle = active ? "#FFFFFF" : color;
            ctx.lineWidth = active ? 5 : 3;
            ctx.fillRect(x1, y1, x2 - x1, y2 - y1);
            ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);
            ctx.fillStyle = "#FFFFFF";
            ctx.font = "24px system-ui, sans-serif";
            ctx.fillText((element.text || element.desc || `Element ${index + 1}`).slice(0, 28), x1 + 12, y1 + 34);
            if (active) ctx.fillRect(x2 - 18, y2 - 18, 18, 18);
        }
    }

    function renderElementPanel() {
        elementPanel.replaceChildren();
        const element = selected();
        if (!element) {
            const empty = document.createElement("div");
            empty.textContent = "Select or add an element.";
            elementPanel.appendChild(empty);
            draw();
            return;
        }

        elementPanel.append(
            makeField("Text", element.text, false, (value) => {
                element.text = value;
                syncElements();
                draw();
            }),
            makeField("Description", element.desc, true, (value) => {
                element.desc = value;
                syncElements();
                draw();
            }),
            makeField("Palette", element.color_palette.join(", "), false, (value) => {
                element.color_palette = value.split(/[,\s]+/).filter(Boolean);
                syncElements();
                draw();
            }),
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
        const element = selected();
        if (!element) return;
        const copy = JSON.parse(JSON.stringify(element));
        copy.bbox = [copy.bbox[0] + 35, copy.bbox[1] + 35, copy.bbox[2] + 35, copy.bbox[3] + 35].map(clamp);
        elements.push(normalizeElement(copy, elements.length));
        selectedIndex = elements.length - 1;
        syncElements();
        renderElementPanel();
    }

    function deleteElement() {
        if (selectedIndex < 0) return;
        elements.splice(selectedIndex, 1);
        selectedIndex = Math.min(selectedIndex, elements.length - 1);
        syncElements();
        renderElementPanel();
    }

    for (const [name, label, type] of SCENE_FIELDS) {
        const item = widget(node, name);
        scene.appendChild(makeField(label, item?.value, type === "textarea", (value) => syncScene(name, value)));
    }

    toolbar.append(
        makeButton("+ Element", "Add element", addElement),
        makeButton("Duplicate", "Duplicate selected element", duplicateElement),
        makeButton("Delete", "Delete selected element", deleteElement),
    );

    canvas.addEventListener("pointerdown", (event) => {
        const pos = point(event);
        const hit = hitTest(pos);
        selectedIndex = hit.index;
        if (selectedIndex >= 0) {
            drag = { mode: hit.mode, start: pos, bbox: [...selected().bbox] };
            canvas.setPointerCapture(event.pointerId);
        }
        renderElementPanel();
    });

    canvas.addEventListener("pointermove", (event) => {
        if (!drag || selectedIndex < 0) return;
        const pos = point(event);
        const dx = pos.x - drag.start.x;
        const dy = pos.y - drag.start.y;
        const element = selected();
        const bbox = [...drag.bbox];
        if (drag.mode === "resize") {
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
        drag = null;
        try {
            canvas.releasePointerCapture(event.pointerId);
        } catch {}
    });

    if (!elements.length) addElement();
    syncElements();
    renderElementPanel();

    const domWidget = node.addDOMWidget("layout_editor", "drawings_ideogram_layout", root, {
        getMinHeight: () => 760,
        getMaxHeight: () => 980,
        getHeight: () => 820,
    });

    if (domWidget && node.widgets?.includes(domWidget)) {
        node.widgets = [domWidget, ...node.widgets.filter((item) => item !== domWidget)];
    }

    const originalComputeSize = node.computeSize;
    node.computeSize = function computeSize(out) {
        const size = originalComputeSize?.call(this, out) || [680, 900];
        return [Math.max(size[0], 720), Math.max(size[1], 900)];
    };
}

app.registerExtension({
    name: "drawings.ideogram.layout_builder",
    async nodeCreated(node) {
        if (node.comfyClass === NODE_CLASS) installEditor(node);
    },
});
