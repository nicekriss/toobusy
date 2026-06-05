import { app } from "../../scripts/app.js";

const DEFAULT_BOARD = {
    version: 2,
    items: [
        { type: "text", id: "title", x: 38, y: 34, w: 420, h: 70, text: "Storyboard / mood board", fontSize: 34, color: "#111111" },
    ],
};

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

function saveBoard(node, board) {
    const widget = boardWidget(node);
    if (widget) {
        // Skip the back-reference to the ComfyNode, otherwise JSON.stringify hits
        // a circular structure (node -> widgets -> DOMWidget._node).
        widget.value = JSON.stringify(board, (key, value) => (key === "_node" ? undefined : value));
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
            ctx.font = `${item.fontSize || 24}px sans-serif`;
            String(item.text || "").split("\n").forEach((line, index) => {
                ctx.fillText(line, item.x, item.y + (item.fontSize || 24) * (index + 1));
            });
        }

        if (selected?.id === item.id) {
            const bounds = itemBounds(item);
            ctx.strokeStyle = "#2d7ff9";
            ctx.lineWidth = 2;
            ctx.setLineDash([6, 4]);
            ctx.strokeRect(bounds.x - 4, bounds.y - 4, bounds.w + 8, bounds.h + 8);
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

function makeInlineBoard(node) {
    const board = parseBoard(node);
    board._node = node;
    let selected = null;
    let tool = "select";
    let dragging = false;
    let penItem = null;
    let dragOffset = { x: 0, y: 0 };
    const imageCache = new Map();

    const root = document.createElement("div");
    root.style.cssText = "width:640px;background:#151915;color:#edf4ed;border:1px solid #3d543f;padding:6px;box-sizing:border-box;";

    const toolbar = document.createElement("div");
    toolbar.style.cssText = "display:flex;gap:4px;align-items:center;margin-bottom:6px;flex-wrap:wrap;";
    root.appendChild(toolbar);

    const canvas = document.createElement("canvas");
    canvas.width = 640;
    canvas.height = 360;
    canvas.style.cssText = "display:block;width:100%;height:auto;background:#f4f1e8;cursor:crosshair;border:1px solid #384338;box-sizing:border-box;";
    root.appendChild(canvas);

    const status = document.createElement("div");
    status.textContent = "Drop images directly on the board.";
    status.style.cssText = "font-size:11px;color:#b8c7b8;margin-top:5px;";
    root.appendChild(status);

    const ctx = canvas.getContext("2d");
    const redraw = () => {
        drawBoard(ctx, board, selected, imageCache);
        saveBoard(node, board);
    };

    const button = (label, action) => {
        const el = document.createElement("button");
        el.textContent = label;
        el.style.cssText = "background:#253126;color:#f0f6ef;border:1px solid #638266;padding:4px 7px;font-size:11px;cursor:pointer;";
        el.onclick = action;
        toolbar.appendChild(el);
        return el;
    };

    const select = (item) => {
        selected = item;
        status.textContent = item ? `Selected: ${item.type}` : "Drop images directly on the board.";
        redraw();
    };

    button("Select", () => { tool = "select"; });
    button("Pen", () => { tool = "pen"; });
    button("Text", () => {
        const text = prompt("Text", "Scene note");
        if (text !== null) {
            select(addItem(board, "text", { x: 44, y: 48 }));
            selected.text = text;
            redraw();
        }
    });
    button("Rect", () => select(addItem(board, "rect", { x: 80, y: 90 })));
    button("Ellipse", () => select(addItem(board, "ellipse", { x: 100, y: 110 })));
    button("Arrow", () => select(addItem(board, "line", { x: 120, y: 140 })));
    button("Delete", () => {
        if (selected) {
            board.items = board.items.filter((item) => item.id !== selected.id);
            select(null);
        }
    });

    canvas.onpointerdown = (event) => {
        const point = pointFor(canvas, event);
        if (tool === "pen") {
            penItem = { id: crypto.randomUUID(), type: "pen", points: [point], color: "#111111", strokeWidth: 4 };
            board.items.push(penItem);
            selected = penItem;
            dragging = true;
            redraw();
            return;
        }

        const hit = hitItem(board, point);
        select(hit);
        if (hit) {
            dragging = true;
            dragOffset = { x: point.x - hit.x, y: point.y - hit.y };
        }
    };

    canvas.onpointermove = (event) => {
        if (!dragging) {
            return;
        }
        const point = pointFor(canvas, event);
        if (penItem) {
            penItem.points.push(point);
        } else if (selected) {
            const oldX = selected.x;
            const oldY = selected.y;
            selected.x = point.x - dragOffset.x;
            selected.y = point.y - dragOffset.y;
            if (selected.type === "line") {
                selected.x2 += selected.x - oldX;
                selected.y2 += selected.y - oldY;
            }
        }
        redraw();
    };

    canvas.onpointerup = () => {
        dragging = false;
        penItem = null;
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
            this.size = [680, 520];
        };
    },
});
