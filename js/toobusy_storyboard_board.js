import { app } from "../../scripts/app.js";

const DEFAULT_BOARD = {
    version: 1,
    items: [
        { type: "text", x: 64, y: 48, w: 420, h: 80, text: "Storyboard / mood board", fontSize: 36, color: "#111111" },
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

function setBoard(node, board) {
    const widget = boardWidget(node);
    if (widget) {
        widget.value = JSON.stringify(board);
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
    node.setDirtyCanvas?.(true, true);
}

function canvasPoint(canvas, event) {
    const rect = canvas.getBoundingClientRect();
    return {
        x: (event.clientX - rect.left) * (canvas.width / rect.width),
        y: (event.clientY - rect.top) * (canvas.height / rect.height),
    };
}

function colorFor(item, fallback = "#111111") {
    return item.color || fallback;
}

function drawBoard(ctx, board, selectedId) {
    ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height);
    ctx.fillStyle = "#f4f1e8";
    ctx.fillRect(0, 0, ctx.canvas.width, ctx.canvas.height);
    ctx.save();
    ctx.strokeStyle = "rgba(0,0,0,0.08)";
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
        ctx.strokeStyle = colorFor(item);
        ctx.fillStyle = item.fill || "rgba(255,255,255,0.55)";

        if (item.type === "rect") {
            ctx.fillRect(item.x, item.y, item.w, item.h);
            ctx.strokeRect(item.x, item.y, item.w, item.h);
        } else if (item.type === "ellipse") {
            ctx.beginPath();
            ctx.ellipse(item.x + item.w / 2, item.y + item.h / 2, Math.abs(item.w / 2), Math.abs(item.h / 2), 0, 0, Math.PI * 2);
            ctx.fill();
            ctx.stroke();
        } else if (item.type === "image") {
            ctx.fillStyle = "#e8e8e8";
            ctx.fillRect(item.x, item.y, item.w, item.h);
            ctx.strokeRect(item.x, item.y, item.w, item.h);
            ctx.fillStyle = colorFor(item);
            ctx.font = "20px sans-serif";
            ctx.fillText(`image_${item.slot || 1}`, item.x + 14, item.y + 30);
        } else if (item.type === "text") {
            ctx.fillStyle = colorFor(item);
            ctx.font = `${item.fontSize || 24}px sans-serif`;
            const lines = String(item.text || "").split("\n");
            lines.forEach((line, index) => ctx.fillText(line, item.x, item.y + (item.fontSize || 24) * (index + 1)));
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
        }

        if (item.id === selectedId) {
            const x = Math.min(item.x, item.x2 ?? item.x + (item.w || 0));
            const y = Math.min(item.y, item.y2 ?? item.y + (item.h || 0));
            const w = Math.abs((item.x2 ?? item.x + (item.w || 0)) - item.x) || item.w || 80;
            const h = Math.abs((item.y2 ?? item.y + (item.h || 0)) - item.y) || item.h || 60;
            ctx.strokeStyle = "#2d7ff9";
            ctx.lineWidth = 2;
            ctx.setLineDash([6, 4]);
            ctx.strokeRect(x - 4, y - 4, w + 8, h + 8);
        }
        ctx.restore();
    }
}

function itemAt(board, point) {
    for (let index = board.items.length - 1; index >= 0; index -= 1) {
        const item = board.items[index];
        const x2 = item.x2 ?? item.x + (item.w || 0);
        const y2 = item.y2 ?? item.y + (item.h || 0);
        const minX = Math.min(item.x, x2) - 8;
        const maxX = Math.max(item.x, x2) + 8;
        const minY = Math.min(item.y, y2) - 8;
        const maxY = Math.max(item.y, y2) + 8;
        if (point.x >= minX && point.x <= maxX && point.y >= minY && point.y <= maxY) {
            return item;
        }
    }
    return null;
}

function addItem(board, type) {
    const base = { id: crypto.randomUUID(), type, x: 120, y: 120, w: 260, h: 160, color: "#111111", strokeWidth: 3 };
    if (type === "text") {
        Object.assign(base, { w: 420, h: 90, text: "Scene note", fontSize: 28 });
    } else if (type === "image") {
        Object.assign(base, { slot: 1 });
    } else if (type === "line") {
        Object.assign(base, { x2: 380, y2: 220, arrow: true });
    } else if (type === "ellipse") {
        Object.assign(base, { fill: "rgba(255,255,255,0.45)" });
    } else if (type === "rect") {
        Object.assign(base, { fill: "rgba(255,255,255,0.45)" });
    }
    board.items.push(base);
    return base;
}

function openEditor(node) {
    const board = parseBoard(node);
    let selected = null;
    let dragging = false;
    let dragOffset = { x: 0, y: 0 };
    let penItem = null;
    let tool = "select";

    const overlay = document.createElement("div");
    overlay.style.cssText = "position:fixed;inset:0;background:rgba(0,0,0,.72);z-index:10000;display:flex;align-items:center;justify-content:center;";
    const panel = document.createElement("div");
    panel.style.cssText = "width:min(1320px,96vw);height:min(860px,94vh);background:#151915;color:#eee;border:1px solid #5f7f61;display:grid;grid-template-rows:auto 1fr auto;box-shadow:0 18px 80px rgba(0,0,0,.45);";
    overlay.appendChild(panel);

    const toolbar = document.createElement("div");
    toolbar.style.cssText = "display:flex;gap:8px;align-items:center;padding:10px;border-bottom:1px solid #344235;flex-wrap:wrap;";
    panel.appendChild(toolbar);

    const canvas = document.createElement("canvas");
    canvas.width = Number(findWidget(node, "width")?.value || 1280);
    canvas.height = Number(findWidget(node, "height")?.value || 720);
    canvas.style.cssText = "width:100%;height:100%;object-fit:contain;background:#f4f1e8;cursor:crosshair;";
    const canvasWrap = document.createElement("div");
    canvasWrap.style.cssText = "overflow:hidden;display:flex;align-items:center;justify-content:center;padding:12px;";
    canvasWrap.appendChild(canvas);
    panel.appendChild(canvasWrap);

    const inspector = document.createElement("div");
    inspector.style.cssText = "display:flex;gap:8px;align-items:center;padding:10px;border-top:1px solid #344235;flex-wrap:wrap;";
    panel.appendChild(inspector);

    const button = (label, action) => {
        const el = document.createElement("button");
        el.textContent = label;
        el.style.cssText = "background:#253126;color:#f0f6ef;border:1px solid #638266;padding:7px 10px;cursor:pointer;";
        el.onclick = action;
        toolbar.appendChild(el);
        return el;
    };

    const refreshInspector = () => {
        inspector.innerHTML = "";
        const hint = document.createElement("span");
        hint.textContent = selected ? `Selected: ${selected.type}` : "Select an item, or draw/place a new one.";
        inspector.appendChild(hint);
        if (!selected) {
            return;
        }
        if (selected.type === "text") {
            const input = document.createElement("input");
            input.value = selected.text || "";
            input.style.cssText = "flex:1;min-width:260px;background:#0f120f;color:#fff;border:1px solid #536b55;padding:6px;";
            input.oninput = () => {
                selected.text = input.value;
                drawBoard(canvas.getContext("2d"), board, selected?.id);
            };
            inspector.appendChild(input);
        }
        if (selected.type === "image") {
            const slot = document.createElement("input");
            slot.type = "number";
            slot.min = "1";
            slot.max = "6";
            slot.value = selected.slot || 1;
            slot.oninput = () => {
                selected.slot = Math.max(1, Math.min(6, Number(slot.value || 1)));
                drawBoard(canvas.getContext("2d"), board, selected?.id);
            };
            inspector.appendChild(document.createTextNode("slot"));
            inspector.appendChild(slot);
        }
        const color = document.createElement("input");
        color.type = "color";
        color.value = selected.color || "#111111";
        color.oninput = () => {
            selected.color = color.value;
            drawBoard(canvas.getContext("2d"), board, selected?.id);
        };
        inspector.appendChild(color);
    };

    const selectItem = (item) => {
        selected = item;
        refreshInspector();
        drawBoard(canvas.getContext("2d"), board, selected?.id);
    };

    button("Select", () => { tool = "select"; });
    button("Pen", () => { tool = "pen"; });
    button("Text", () => selectItem(addItem(board, "text")));
    button("Image slot", () => selectItem(addItem(board, "image")));
    button("Rect", () => selectItem(addItem(board, "rect")));
    button("Ellipse", () => selectItem(addItem(board, "ellipse")));
    button("Arrow", () => selectItem(addItem(board, "line")));
    button("Delete", () => {
        if (selected) {
            board.items = board.items.filter((item) => item.id !== selected.id);
            selectItem(null);
        }
    });

    const apply = document.createElement("button");
    apply.textContent = "Apply";
    apply.style.cssText = "margin-left:auto;background:#4d7d48;color:#fff;border:1px solid #91c48b;padding:7px 14px;cursor:pointer;";
    apply.onclick = () => {
        setBoard(node, board);
        overlay.remove();
    };
    toolbar.appendChild(apply);

    const close = document.createElement("button");
    close.textContent = "Close";
    close.style.cssText = "background:#2b2f2b;color:#fff;border:1px solid #666;padding:7px 14px;cursor:pointer;";
    close.onclick = () => overlay.remove();
    toolbar.appendChild(close);

    canvas.onpointerdown = (event) => {
        const point = canvasPoint(canvas, event);
        if (tool === "pen") {
            penItem = { id: crypto.randomUUID(), type: "pen", points: [point], color: "#111111", strokeWidth: 4 };
            board.items.push(penItem);
            selectItem(penItem);
            dragging = true;
            return;
        }
        const hit = itemAt(board, point);
        selectItem(hit);
        if (hit) {
            dragging = true;
            dragOffset = { x: point.x - hit.x, y: point.y - hit.y };
        }
    };
    canvas.onpointermove = (event) => {
        if (!dragging) {
            return;
        }
        const point = canvasPoint(canvas, event);
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
        drawBoard(canvas.getContext("2d"), board, selected?.id);
    };
    canvas.onpointerup = () => {
        dragging = false;
        penItem = null;
    };

    document.body.appendChild(overlay);
    refreshInspector();
    drawBoard(canvas.getContext("2d"), board, selected?.id);
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
            this.addWidget("button", "Open board editor", "open", () => openEditor(this), { serialize: false });
        };
    },
});
