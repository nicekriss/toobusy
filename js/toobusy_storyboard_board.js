import { app } from "../../scripts/app.js";

const DEFAULT_BOARD = {
    version: 2,
    items: [
        { type: "text", id: "title", x: 38, y: 34, w: 420, h: 70, text: "Storyboard / mood board", fontSize: 34, color: "#111111" },
    ],
};

const HANDLE = 10; // resize handle size in canvas pixels
const MIN_SIZE = 20;

function findWidget(node, name) {
    return node.widgets?.find((widget) => widget.name === name);
}

function boardWidget(node) {
    return findWidget(node, "board_data");
}

function parseBoard(node) {
    try {
        const parsed = JSON.parse(boardWidget(node)?.value || "");
        if (parsed && Array.isArray(parsed.items)) {
            return parsed;
        }
    } catch {}
    return structuredClone(DEFAULT_BOARD);
}

function serializeBoard(board) {
    // Skip the back-reference to the ComfyNode, otherwise JSON.stringify hits a
    // circular structure (node -> widgets -> DOMWidget._node).
    return JSON.stringify(board, (key, value) => (key === "_node" ? undefined : value));
}

function saveBoard(node, board) {
    const widget = boardWidget(node);
    if (widget) {
        widget.value = serializeBoard(board);
    }
    node.setDirtyCanvas?.(true, true);
    app.graph?.setDirtyCanvas?.(true, true);
}

function hideWidget(node, widget) {
    if (!widget) {
        return;
    }
    if (!widget._toobusyOriginalType) {
        widget._toobusyOriginalType = widget.type;
        widget._toobusyOriginalComputeSize = widget.computeSize;
    }
    widget.type = "hidden";
    widget.computeSize = () => [0, -4];
    widget.hidden = true;
}

function pointFor(canvas, event) {
    const rect = canvas.getBoundingClientRect();
    return {
        x: (event.clientX - rect.left) * (canvas.width / rect.width),
        y: (event.clientY - rect.top) * (canvas.height / rect.height),
    };
}

function itemBounds(item) {
    const x2 = item.x2 ?? item.x + (item.w || 0);
    const y2 = item.y2 ?? item.y + (item.h || 0);
    return {
        x: Math.min(item.x, x2),
        y: Math.min(item.y, y2),
        w: Math.abs(x2 - item.x) || item.w || 80,
        h: Math.abs(y2 - item.y) || item.h || 60,
    };
}

function hitItem(board, point) {
    for (let index = board.items.length - 1; index >= 0; index -= 1) {
        const item = board.items[index];
        const bounds = itemBounds(item);
        if (
            point.x >= bounds.x - 8 &&
            point.x <= bounds.x + bounds.w + 8 &&
            point.y >= bounds.y - 8 &&
            point.y <= bounds.y + bounds.h + 8
        ) {
            return item;
        }
    }
    return null;
}

function near(point, x, y) {
    return Math.abs(point.x - x) <= HANDLE && Math.abs(point.y - y) <= HANDLE;
}

// Returns a drag descriptor if the point grabs a handle of the selected item.
function handleAt(item, point) {
    if (!item) return null;
    if (item.type === "line") {
        if (near(point, item.x, item.y)) return { mode: "line-end", end: "start" };
        if (near(point, item.x2, item.y2)) return { mode: "line-end", end: "end" };
        return null;
    }
    if (item.type === "pen") return null; // freehand strokes are not resized
    const b = itemBounds(item);
    if (near(point, b.x + b.w, b.y + b.h)) return { mode: "resize" };
    return null;
}

function addItem(board, type, point = { x: 120, y: 120 }) {
    const item = {
        id: crypto.randomUUID(),
        type,
        x: point.x,
        y: point.y,
        w: 240,
        h: 140,
        color: "#111111",
        strokeWidth: 3,
    };
    if (type === "text") {
        Object.assign(item, { w: 360, h: 90, text: "Scene note", fontSize: 28 });
    } else if (type === "line") {
        Object.assign(item, { x2: point.x + 240, y2: point.y + 90, arrow: true });
    } else if (type === "rect" || type === "ellipse") {
        Object.assign(item, { fill: "rgba(255,255,255,0.55)" });
    }
    board.items.push(item);
    return item;
}

function imageFromSrc(src, cache, onload) {
    if (!src) {
        return null;
    }
    if (cache.has(src)) {
        return cache.get(src);
    }
    const img = new Image();
    img.onload = onload;
    img.src = src;
    cache.set(src, img);
    return img;
}

// Word-wrap to mirror storyboard_board.py _wrap_text: split on whitespace
// (explicit newlines collapse to spaces, like Python's str.split()), keep a word
// on the line while the measured width stays within `width`.
function wrapTextLines(ctx, text, fontPx, width) {
    ctx.font = `${fontPx}px sans-serif`;
    const words = String(text || "").split(/\s+/).filter(Boolean);
    if (!words.length) {
        return [""];
    }
    const lines = [];
    let current = words[0];
    for (let i = 1; i < words.length; i += 1) {
        const test = `${current} ${words[i]}`;
        if (ctx.measureText(test).width <= width) {
            current = test;
        } else {
            lines.push(current);
            current = words[i];
        }
    }
    lines.push(current);
    return lines;
}

function drawBoard(ctx, board, selected, imageCache) {
    const background = findWidget(board._node, "background")?.value || "#f4f1e8";
    ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height);
    ctx.fillStyle = background;
    ctx.fillRect(0, 0, ctx.canvas.width, ctx.canvas.height);

    ctx.save();
    ctx.strokeStyle = "rgba(0,0,0,0.08)";
    ctx.lineWidth = 1;
    for (let x = 0; x < ctx.canvas.width; x += 40) {
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, ctx.canvas.height);
        ctx.stroke();
    }
    for (let y = 0; y < ctx.canvas.height; y += 40) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(ctx.canvas.width, y);
        ctx.stroke();
    }
    ctx.restore();

    for (const item of board.items) {
        ctx.save();
        ctx.lineWidth = item.strokeWidth || 3;
        ctx.strokeStyle = item.color || "#111111";
        ctx.fillStyle = item.fill || "rgba(255,255,255,0.55)";

        if (item.type === "image") {
            const img = imageFromSrc(item.src, imageCache, () => drawBoard(ctx, board, selected, imageCache));
            if (img?.complete && img.naturalWidth) {
                ctx.drawImage(img, item.x, item.y, item.w, item.h);
            } else {
                ctx.fillStyle = "#e8e8e8";
                ctx.fillRect(item.x, item.y, item.w, item.h);
                ctx.strokeRect(item.x, item.y, item.w, item.h);
                ctx.fillStyle = item.color || "#111111";
                ctx.font = "18px sans-serif";
                ctx.fillText("drop image", item.x + 12, item.y + 28);
            }
        } else if (item.type === "rect") {
            ctx.fillRect(item.x, item.y, item.w, item.h);
            ctx.strokeRect(item.x, item.y, item.w, item.h);
        } else if (item.type === "ellipse") {
            ctx.beginPath();
            ctx.ellipse(item.x + item.w / 2, item.y + item.h / 2, Math.abs(item.w / 2), Math.abs(item.h / 2), 0, 0, Math.PI * 2);
            ctx.fill();
            ctx.stroke();
        } else if (item.type === "line") {
            ctx.beginPath();
            ctx.moveTo(item.x, item.y);
            ctx.lineTo(item.x2, item.y2);
            ctx.stroke();
        } else if (item.type === "pen" && Array.isArray(item.points)) {
            ctx.beginPath();
            item.points.forEach((point, index) => {
                if (index === 0) {
                    ctx.moveTo(point.x, point.y);
                } else {
                    ctx.lineTo(point.x, point.y);
                }
            });
            ctx.stroke();
        } else if (item.type === "text") {
            ctx.fillStyle = item.color || "#111111";
            const fs = item.fontSize || 24;
            ctx.textBaseline = "top";
            const lines = wrapTextLines(ctx, item.text, fs, Math.max(MIN_SIZE, item.w || MIN_SIZE));
            let lineY = item.y;
            for (const line of lines) {
                ctx.fillText(line, item.x, lineY);
                lineY += fs + 6; // mirror Python's per-line advance (~bbox height + 6)
                if (lineY > item.y + (item.h || 0)) {
                    break;
                }
            }
        }

        if (selected?.id === item.id) {
            const bounds = itemBounds(item);
            ctx.strokeStyle = "#2d7ff9";
            ctx.lineWidth = 2;
            ctx.setLineDash([6, 4]);
            ctx.strokeRect(bounds.x - 4, bounds.y - 4, bounds.w + 8, bounds.h + 8);

            // Resize handles.
            ctx.setLineDash([]);
            ctx.fillStyle = "#2d7ff9";
            if (item.type === "line") {
                for (const [hx, hy] of [[item.x, item.y], [item.x2, item.y2]]) {
                    ctx.fillRect(hx - HANDLE / 2, hy - HANDLE / 2, HANDLE, HANDLE);
                }
            } else if (item.type !== "pen") {
                ctx.fillRect(bounds.x + bounds.w - HANDLE / 2, bounds.y + bounds.h - HANDLE / 2, HANDLE, HANDLE);
            }
        }
        ctx.restore();
    }
}

function fileToDataUrl(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result || ""));
        reader.onerror = reject;
        reader.readAsDataURL(file);
    });
}

function rgbToHex(value) {
    const match = String(value || "").match(/\d+(\.\d+)?/g);
    if (!match || match.length < 3) {
        return /^#[0-9a-f]{6}$/i.test(value) ? value : "#ffffff";
    }
    const [r, g, b] = match.map((n) => Math.max(0, Math.min(255, Math.round(parseFloat(n)))));
    return `#${[r, g, b].map((n) => n.toString(16).padStart(2, "0")).join("")}`;
}

function makeInlineBoard(node) {
    const board = parseBoard(node);
    board._node = node;
    let selected = null;
    let tool = "select";
    let dragging = false;
    let dragMode = "move"; // move | resize | line-end | pen
    let dragEnd = null; // for line-end: "start" | "end"
    let penItem = null;
    let dragOffset = { x: 0, y: 0 };
    const imageCache = new Map();

    const undoStack = [];
    const redoStack = [];

    const root = document.createElement("div");
    root.style.cssText = "width:640px;background:#151915;color:#edf4ed;border:1px solid #3d543f;padding:6px;box-sizing:border-box;";

    const toolbar = document.createElement("div");
    toolbar.style.cssText = "display:flex;gap:4px;align-items:center;margin-bottom:6px;flex-wrap:wrap;";
    root.appendChild(toolbar);

    const propBar = document.createElement("div");
    propBar.style.cssText = "display:flex;gap:6px;align-items:center;margin-bottom:6px;flex-wrap:wrap;min-height:24px;";
    root.appendChild(propBar);

    const canvas = document.createElement("canvas");
    canvas.width = 640;
    canvas.height = 360;
    canvas.tabIndex = 0;
    canvas.style.cssText = "display:block;width:100%;height:auto;background:#f4f1e8;cursor:crosshair;border:1px solid #384338;box-sizing:border-box;outline:none;";
    root.appendChild(canvas);

    const status = document.createElement("div");
    status.textContent = "Drop images directly on the board. Double-click text to edit.";
    status.style.cssText = "font-size:11px;color:#b8c7b8;margin-top:5px;";
    root.appendChild(status);

    const ctx = canvas.getContext("2d");
    const redraw = () => {
        drawBoard(ctx, board, selected, imageCache);
        saveBoard(node, board);
    };

    // ----- history -----
    const snapshot = () => serializeBoard(board);
    const pushHistory = () => {
        undoStack.push(snapshot());
        if (undoStack.length > 60) undoStack.shift();
        redoStack.length = 0;
    };
    const restore = (snap) => {
        try {
            const data = JSON.parse(snap);
            if (Array.isArray(data.items)) {
                board.items = data.items;
                selected = null;
            }
        } catch {}
    };
    const undo = () => {
        if (!undoStack.length) return;
        redoStack.push(snapshot());
        restore(undoStack.pop());
        renderProps();
        redraw();
    };
    const redo = () => {
        if (!redoStack.length) return;
        undoStack.push(snapshot());
        restore(redoStack.pop());
        renderProps();
        redraw();
    };

    const button = (label, action, parent = toolbar) => {
        const el = document.createElement("button");
        el.textContent = label;
        el.style.cssText = "background:#253126;color:#f0f6ef;border:1px solid #638266;padding:4px 7px;font-size:11px;cursor:pointer;";
        el.onclick = action;
        parent.appendChild(el);
        return el;
    };

    const labelText = (text) => {
        const el = document.createElement("span");
        el.textContent = text;
        el.style.cssText = "font-size:11px;color:#b8c7b8;";
        return el;
    };

    const select = (item) => {
        selected = item;
        status.textContent = item
            ? `Selected: ${item.type}`
            : "Drop images directly on the board. Double-click text to edit.";
        renderProps();
        redraw();
    };

    // ----- selected-item property controls -----
    function renderProps() {
        propBar.replaceChildren();
        if (!selected) {
            propBar.appendChild(labelText("No selection · pick a tool or click an item"));
            return;
        }
        const item = selected;

        // Stroke / text color (all items).
        const colorInput = document.createElement("input");
        colorInput.type = "color";
        colorInput.value = rgbToHex(item.color || "#111111");
        colorInput.title = "Color";
        colorInput.style.cssText = "width:28px;height:22px;padding:0;border:1px solid #638266;background:none;cursor:pointer;";
        colorInput.onchange = () => {
            pushHistory();
            item.color = colorInput.value;
            redraw();
        };
        propBar.append(labelText("color"), colorInput);

        // Fill (rect / ellipse).
        if (item.type === "rect" || item.type === "ellipse") {
            const fillInput = document.createElement("input");
            fillInput.type = "color";
            fillInput.value = rgbToHex(item.fill || "#ffffff");
            fillInput.title = "Fill";
            fillInput.style.cssText = colorInput.style.cssText;
            fillInput.onchange = () => {
                pushHistory();
                item.fill = fillInput.value;
                redraw();
            };
            const noFill = button("no fill", () => {
                pushHistory();
                item.fill = "rgba(0,0,0,0)";
                redraw();
            }, propBar);
            noFill.style.padding = "3px 6px";
            propBar.append(labelText("fill"), fillInput, noFill);
        }

        // Stroke width (everything except text).
        if (item.type !== "text") {
            const strokeInput = document.createElement("input");
            strokeInput.type = "number";
            strokeInput.min = "1";
            strokeInput.max = "60";
            strokeInput.value = String(item.strokeWidth || 3);
            strokeInput.style.cssText = "width:48px;font-size:11px;";
            strokeInput.onchange = () => {
                pushHistory();
                item.strokeWidth = Math.max(1, Math.min(60, Math.round(Number(strokeInput.value) || 1)));
                strokeInput.value = String(item.strokeWidth);
                redraw();
            };
            propBar.append(labelText("stroke"), strokeInput);
        }

        // Font size + edit (text).
        if (item.type === "text") {
            const fontInput = document.createElement("input");
            fontInput.type = "number";
            fontInput.min = "8";
            fontInput.max = "200";
            fontInput.value = String(item.fontSize || 24);
            fontInput.style.cssText = "width:54px;font-size:11px;";
            fontInput.onchange = () => {
                pushHistory();
                item.fontSize = Math.max(8, Math.min(200, Math.round(Number(fontInput.value) || 8)));
                fontInput.value = String(item.fontSize);
                redraw();
            };
            const editBtn = button("Edit text", () => editText(item), propBar);
            editBtn.style.padding = "3px 6px";
            propBar.append(labelText("size"), fontInput, editBtn);
        }

        // z-order + duplicate (all items).
        const front = button("Front", () => reorder(item, 1), propBar);
        const back = button("Back", () => reorder(item, -1), propBar);
        const dup = button("Duplicate", () => duplicate(item), propBar);
        for (const b of [front, back, dup]) b.style.padding = "3px 6px";
    }

    function editText(item) {
        const next = prompt("Text", item.text || "");
        if (next === null) return;
        pushHistory();
        item.text = next;
        redraw();
    }

    function reorder(item, direction) {
        const index = board.items.indexOf(item);
        if (index < 0) return;
        const target = direction > 0 ? board.items.length - 1 : 0;
        if (index === target) return;
        pushHistory();
        board.items.splice(index, 1);
        if (direction > 0) {
            board.items.push(item);
        } else {
            board.items.unshift(item);
        }
        redraw();
    }

    function duplicate(item) {
        pushHistory();
        const copy = structuredClone({ ...item, _node: undefined });
        copy.id = crypto.randomUUID();
        copy.x = (copy.x || 0) + 24;
        copy.y = (copy.y || 0) + 24;
        if (copy.type === "line") {
            copy.x2 = (copy.x2 || 0) + 24;
            copy.y2 = (copy.y2 || 0) + 24;
        }
        if (Array.isArray(copy.points)) {
            copy.points = copy.points.map((p) => ({ x: p.x + 24, y: p.y + 24 }));
        }
        board.items.push(copy);
        select(copy);
    }

    function deleteSelected() {
        if (!selected) return;
        pushHistory();
        board.items = board.items.filter((item) => item.id !== selected.id);
        select(null);
    }

    // ----- toolbar -----
    button("Select", () => { tool = "select"; });
    button("Pen", () => { tool = "pen"; });
    button("Text", () => {
        const text = prompt("Text", "Scene note");
        if (text === null) return;
        pushHistory();
        const item = addItem(board, "text", { x: 44, y: 48 });
        item.text = text;
        select(item);
    });
    button("Rect", () => { pushHistory(); select(addItem(board, "rect", { x: 80, y: 90 })); });
    button("Ellipse", () => { pushHistory(); select(addItem(board, "ellipse", { x: 100, y: 110 })); });
    button("Arrow", () => { pushHistory(); select(addItem(board, "line", { x: 120, y: 140 })); });
    button("Delete", deleteSelected);
    button("Undo", undo);
    button("Redo", redo);

    // ----- canvas interaction -----
    canvas.onpointerdown = (event) => {
        canvas.focus();
        const point = pointFor(canvas, event);

        if (tool === "pen") {
            pushHistory();
            penItem = { id: crypto.randomUUID(), type: "pen", points: [point], color: "#111111", strokeWidth: 4 };
            board.items.push(penItem);
            selected = penItem;
            dragging = true;
            dragMode = "pen";
            renderProps();
            redraw();
            return;
        }

        // Grab a resize/endpoint handle of the already-selected item first.
        const handle = handleAt(selected, point);
        if (handle) {
            pushHistory();
            dragging = true;
            dragMode = handle.mode;
            dragEnd = handle.end || null;
            return;
        }

        const hit = hitItem(board, point);
        select(hit);
        if (hit) {
            pushHistory();
            dragging = true;
            dragMode = "move";
            dragOffset = { x: point.x - hit.x, y: point.y - hit.y };
        }
    };

    canvas.onpointermove = (event) => {
        if (!dragging) {
            return;
        }
        const point = pointFor(canvas, event);

        if (dragMode === "pen" && penItem) {
            penItem.points.push(point);
        } else if (dragMode === "resize" && selected) {
            if (selected.type === "line") {
                // handled by line-end
            } else {
                selected.w = Math.max(MIN_SIZE, point.x - selected.x);
                selected.h = Math.max(MIN_SIZE, point.y - selected.y);
            }
        } else if (dragMode === "line-end" && selected) {
            if (dragEnd === "start") {
                selected.x = point.x;
                selected.y = point.y;
            } else {
                selected.x2 = point.x;
                selected.y2 = point.y;
            }
        } else if (dragMode === "move" && selected) {
            const oldX = selected.x;
            const oldY = selected.y;
            selected.x = point.x - dragOffset.x;
            selected.y = point.y - dragOffset.y;
            if (selected.type === "line") {
                selected.x2 += selected.x - oldX;
                selected.y2 += selected.y - oldY;
            } else if (Array.isArray(selected.points)) {
                const dx = selected.x - oldX;
                const dy = selected.y - oldY;
                selected.points = selected.points.map((p) => ({ x: p.x + dx, y: p.y + dy }));
            }
        }
        redraw();
    };

    canvas.onpointerup = () => {
        dragging = false;
        penItem = null;
        dragMode = "move";
        dragEnd = null;
    };

    canvas.ondblclick = (event) => {
        const point = pointFor(canvas, event);
        const hit = hitItem(board, point);
        if (hit && hit.type === "text") {
            select(hit);
            editText(hit);
        }
    };

    canvas.onkeydown = (event) => {
        if (event.key === "Delete" || event.key === "Backspace") {
            if (selected) {
                event.preventDefault();
                deleteSelected();
            }
            return;
        }
        const ctrlLike = event.ctrlKey || event.metaKey;
        if (ctrlLike && event.key.toLowerCase() === "z") {
            event.preventDefault();
            if (event.shiftKey) redo(); else undo();
        } else if (ctrlLike && event.key.toLowerCase() === "y") {
            event.preventDefault();
            redo();
        }
    };

    canvas.ondragover = (event) => {
        event.preventDefault();
        status.textContent = "Drop to place image.";
    };

    canvas.ondrop = async (event) => {
        event.preventDefault();
        const file = [...(event.dataTransfer?.files || [])].find((candidate) => candidate.type.startsWith("image/"));
        if (!file) {
            status.textContent = "Drop image files only.";
            return;
        }
        const point = pointFor(canvas, event);
        const src = await fileToDataUrl(file);
        pushHistory();
        const item = {
            id: crypto.randomUUID(),
            type: "image",
            x: point.x,
            y: point.y,
            w: 220,
            h: 150,
            src,
            color: "#111111",
            strokeWidth: 2,
        };
        board.items.push(item);
        select(item);
    };

    renderProps();
    redraw();
    return root;
}

app.registerExtension({
    name: "toobusy.storyboardBoard",
    beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== "ToobusyStoryboardBoard") {
            return;
        }

        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            onNodeCreated?.apply(this, arguments);
            hideWidget(this, boardWidget(this));

            const board = makeInlineBoard(this);
            if (this.addDOMWidget) {
                this.addDOMWidget("storyboard_board", "div", board, { serialize: false });
            } else {
                this.addWidget("button", "Inline board unsupported", "open", () => {}, { serialize: false });
            }
            this.size = [680, 560];
        };
    },
});
