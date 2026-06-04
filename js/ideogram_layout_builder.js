import { app } from "/scripts/app.js";

const NODE_CLASS = "IdeogramLayoutBuilder";
const CANVAS_SIZE = 1000;

function getWidget(node, name) {
    return node.widgets?.find((widget) => widget.name === name);
}

function parseElements(value) {
    try {
        const parsed = JSON.parse(value || "[]");
        if (Array.isArray(parsed)) {
            return parsed;
        }
        if (Array.isArray(parsed.elements)) {
            return parsed.elements;
        }
    } catch (error) {
        console.warn("[drawings] Failed to parse elements_json", error);
    }
    return [];
}

function normalizeElement(element, index) {
    const bbox = Array.isArray(element.bbox) && element.bbox.length === 4
        ? element.bbox.map((value) => Math.max(0, Math.min(CANVAS_SIZE, Math.round(Number(value) || 0))))
        : [120 + index * 30, 120 + index * 30, 520 + index * 30, 360 + index * 30];

    if (bbox[2] <= bbox[0]) {
        bbox[2] = Math.min(CANVAS_SIZE, bbox[0] + 20);
    }
    if (bbox[3] <= bbox[1]) {
        bbox[3] = Math.min(CANVAS_SIZE, bbox[1] + 20);
    }

    return {
        type: "obj",
        bbox,
        text: element.text || "",
        desc: element.desc || "layout element",
        color_palette: Array.isArray(element.color_palette) ? element.color_palette : ["#FFFFFF", "#111111"],
    };
}

function createButton(label, title, onClick) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = label;
    button.title = title;
    button.addEventListener("click", onClick);
    return button;
}

function createInput(label, value, onInput) {
    const wrap = document.createElement("label");
    const title = document.createElement("span");
    const input = document.createElement("input");
    title.textContent = label;
    input.value = value || "";
    input.addEventListener("input", () => onInput(input.value));
    wrap.append(title, input);
    return { wrap, input };
}

function createTextarea(label, value, onInput) {
    const wrap = document.createElement("label");
    const title = document.createElement("span");
    const textarea = document.createElement("textarea");
    title.textContent = label;
    textarea.value = value || "";
    textarea.rows = 3;
    textarea.addEventListener("input", () => onInput(textarea.value));
    wrap.append(title, textarea);
    return { wrap, textarea };
}

function attachLayoutEditor(node) {
    if (node.__ideogramLayoutEditorAttached) {
        return;
    }
    node.__ideogramLayoutEditorAttached = true;

    const jsonWidget = getWidget(node, "elements_json");
    if (!jsonWidget) {
        return;
    }

    jsonWidget.computeSize = () => [0, 0];

    let elements = parseElements(jsonWidget.value).map(normalizeElement);
    let selectedIndex = elements.length ? 0 : -1;
    let drag = null;

    const root = document.createElement("div");
    root.className = "drawings-ideogram";

    const style = document.createElement("style");
    style.textContent = `
        .drawings-ideogram {
            box-sizing: border-box;
            width: 100%;
            min-width: 420px;
            color: #e9edf1;
            font: 12px/1.4 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            user-select: none;
        }
        .drawings-ideogram * { box-sizing: border-box; }
        .drawings-ideogram .toolbar {
            display: flex;
            gap: 6px;
            align-items: center;
            margin-bottom: 8px;
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
        .drawings-ideogram .panel {
            display: grid;
            grid-template-columns: minmax(260px, 1fr) 190px;
            gap: 10px;
        }
        .drawings-ideogram canvas {
            width: 100%;
            aspect-ratio: 1 / 1;
            display: block;
            border: 1px solid #4d5662;
            border-radius: 6px;
            background: #111418;
            cursor: crosshair;
        }
        .drawings-ideogram .fields {
            display: flex;
            flex-direction: column;
            gap: 8px;
            min-width: 0;
        }
        .drawings-ideogram label {
            display: flex;
            flex-direction: column;
            gap: 3px;
            color: #aeb8c4;
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
        .drawings-ideogram .bbox {
            color: #cbd5df;
            min-height: 18px;
            overflow-wrap: anywhere;
        }
    `;
    root.appendChild(style);

    const toolbar = document.createElement("div");
    toolbar.className = "toolbar";
    root.appendChild(toolbar);

    const panel = document.createElement("div");
    panel.className = "panel";
    root.appendChild(panel);

    const canvas = document.createElement("canvas");
    canvas.width = CANVAS_SIZE;
    canvas.height = CANVAS_SIZE;
    panel.appendChild(canvas);

    const fields = document.createElement("div");
    fields.className = "fields";
    panel.appendChild(fields);

    const bboxReadout = document.createElement("div");
    bboxReadout.className = "bbox";

    function syncWidget() {
        jsonWidget.value = JSON.stringify(elements, null, 2);
        jsonWidget.callback?.(jsonWidget.value);
        node.setDirtyCanvas(true, true);
    }

    function selected() {
        return selectedIndex >= 0 ? elements[selectedIndex] : null;
    }

    function canvasPoint(event) {
        const rect = canvas.getBoundingClientRect();
        return {
            x: Math.round(((event.clientX - rect.left) / rect.width) * CANVAS_SIZE),
            y: Math.round(((event.clientY - rect.top) / rect.height) * CANVAS_SIZE),
        };
    }

    function hitTest(point) {
        for (let i = elements.length - 1; i >= 0; i--) {
            const [x1, y1, x2, y2] = elements[i].bbox;
            const nearRight = Math.abs(point.x - x2) < 24;
            const nearBottom = Math.abs(point.y - y2) < 24;
            if (point.x >= x1 && point.x <= x2 && point.y >= y1 && point.y <= y2) {
                return { index: i, mode: nearRight && nearBottom ? "resize" : "move" };
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

        elements.forEach((element, index) => {
            const [x1, y1, x2, y2] = element.bbox;
            const isSelected = index === selectedIndex;
            const palette = element.color_palette?.[0] || "#8AB4F8";
            ctx.fillStyle = `${palette}33`;
            ctx.strokeStyle = isSelected ? "#FFFFFF" : palette;
            ctx.lineWidth = isSelected ? 5 : 3;
            ctx.fillRect(x1, y1, x2 - x1, y2 - y1);
            ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);
            ctx.fillStyle = "#FFFFFF";
            ctx.font = "24px system-ui, sans-serif";
            const label = element.text || element.desc || `Element ${index + 1}`;
            ctx.fillText(label.slice(0, 28), x1 + 12, y1 + 34);
            if (isSelected) {
                ctx.fillStyle = "#FFFFFF";
                ctx.fillRect(x2 - 18, y2 - 18, 18, 18);
            }
        });
    }

    function renderFields() {
        fields.replaceChildren();
        const element = selected();
        if (!element) {
            const empty = document.createElement("div");
            empty.textContent = "Add an element to start.";
            fields.appendChild(empty);
            bboxReadout.textContent = "";
            draw();
            return;
        }

        const textField = createInput("Text", element.text, (value) => {
            element.text = value;
            syncWidget();
            draw();
        });
        const descField = createTextarea("Description", element.desc, (value) => {
            element.desc = value;
            syncWidget();
            draw();
        });
        const paletteField = createInput("Palette", element.color_palette.join(", "), (value) => {
            element.color_palette = value.split(/[,\s]+/).filter(Boolean);
            syncWidget();
            draw();
        });

        bboxReadout.textContent = `bbox: [${element.bbox.join(", ")}]`;
        fields.append(textField.wrap, descField.wrap, paletteField.wrap, bboxReadout);
        draw();
    }

    function addElement() {
        const offset = elements.length * 35;
        elements.push(normalizeElement({
            bbox: [150 + offset, 150 + offset, 550 + offset, 380 + offset],
            text: "",
            desc: "new layout element",
            color_palette: ["#8AB4F8", "#FFFFFF"],
        }, elements.length));
        selectedIndex = elements.length - 1;
        syncWidget();
        renderFields();
    }

    function deleteElement() {
        if (selectedIndex < 0) {
            return;
        }
        elements.splice(selectedIndex, 1);
        selectedIndex = Math.min(selectedIndex, elements.length - 1);
        syncWidget();
        renderFields();
    }

    function duplicateElement() {
        const element = selected();
        if (!element) {
            return;
        }
        const copy = JSON.parse(JSON.stringify(element));
        copy.bbox = [
            Math.min(980, copy.bbox[0] + 40),
            Math.min(980, copy.bbox[1] + 40),
            Math.min(1000, copy.bbox[2] + 40),
            Math.min(1000, copy.bbox[3] + 40),
        ];
        elements.push(copy);
        selectedIndex = elements.length - 1;
        syncWidget();
        renderFields();
    }

    toolbar.append(
        createButton("+", "Add element", addElement),
        createButton("Copy", "Duplicate selected element", duplicateElement),
        createButton("Del", "Delete selected element", deleteElement),
    );

    canvas.addEventListener("pointerdown", (event) => {
        const point = canvasPoint(event);
        const hit = hitTest(point);
        if (hit.index < 0) {
            selectedIndex = -1;
            renderFields();
            return;
        }
        selectedIndex = hit.index;
        const element = selected();
        drag = {
            mode: hit.mode,
            start: point,
            bbox: [...element.bbox],
        };
        canvas.setPointerCapture(event.pointerId);
        renderFields();
    });

    canvas.addEventListener("pointermove", (event) => {
        if (!drag || selectedIndex < 0) {
            return;
        }
        const point = canvasPoint(event);
        const dx = point.x - drag.start.x;
        const dy = point.y - drag.start.y;
        const element = selected();
        const bbox = [...drag.bbox];
        if (drag.mode === "resize") {
            bbox[2] = Math.max(bbox[0] + 20, Math.min(CANVAS_SIZE, bbox[2] + dx));
            bbox[3] = Math.max(bbox[1] + 20, Math.min(CANVAS_SIZE, bbox[3] + dy));
        } else {
            const width = bbox[2] - bbox[0];
            const height = bbox[3] - bbox[1];
            bbox[0] = Math.max(0, Math.min(CANVAS_SIZE - width, bbox[0] + dx));
            bbox[1] = Math.max(0, Math.min(CANVAS_SIZE - height, bbox[1] + dy));
            bbox[2] = bbox[0] + width;
            bbox[3] = bbox[1] + height;
        }
        element.bbox = bbox.map(Math.round);
        bboxReadout.textContent = `bbox: [${element.bbox.join(", ")}]`;
        syncWidget();
        draw();
    });

    canvas.addEventListener("pointerup", (event) => {
        drag = null;
        canvas.releasePointerCapture(event.pointerId);
    });

    if (!elements.length) {
        addElement();
    } else {
        syncWidget();
        renderFields();
    }

    node.addDOMWidget("layout_editor", "drawings_ideogram_layout", root, {
        getMinHeight: () => 520,
        getMaxHeight: () => 820,
        getHeight: () => 560,
    });

    const originalComputeSize = node.computeSize;
    node.computeSize = function computeSize(out) {
        const size = originalComputeSize?.call(this, out) || [520, 720];
        return [Math.max(size[0], 560), Math.max(size[1], 740)];
    };
}

app.registerExtension({
    name: "drawings.ideogram.layout_builder",
    async nodeCreated(node) {
        if (node.comfyClass === NODE_CLASS) {
            attachLayoutEditor(node);
        }
    },
});
