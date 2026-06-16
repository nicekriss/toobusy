import { app } from "../../scripts/app.js";

// toobusy Layout Text Overlay — a WYSIWYG editor: real text laid over the source
// image, dragged / inline-edited / restyled live. State (items in 0..1 normalized
// coords) is saved to the `overlay_data` widget; the Python node renders the same
// with Pillow. The backdrop image + seed items arrive via onExecuted after a run.

const NODE_CLASS = "ToobusyLayoutTextOverlay";
const ACCENT = "#7fc8ff";

function injectStyle() {
    if (document.getElementById("toobusy-overlay-style")) return;
    const style = document.createElement("style");
    style.id = "toobusy-overlay-style";
    style.textContent = `
    .tb-overlay { display:flex; flex-direction:column; gap:6px; width:100%; font-family:sans-serif; }
    .tb-overlay-bar { display:flex; flex-wrap:wrap; gap:6px; align-items:center; }
    .tb-overlay-bar button { background:#2a2f37; color:#cfd6de; border:1px solid #3a414b; border-radius:5px; padding:3px 8px; cursor:pointer; font-size:11px; }
    .tb-overlay-bar button:hover { border-color:${ACCENT}; }
    .tb-overlay-bar label { color:#9aa4b0; font-size:11px; display:flex; gap:4px; align-items:center; }
    .tb-overlay-stage { position:relative; width:100%; background:#15191e center/contain no-repeat; border:1px solid #2d3642; border-radius:6px; overflow:hidden; user-select:none; }
    .tb-overlay-hint { position:absolute; inset:0; display:flex; align-items:center; justify-content:center; color:#6b7785; font-size:12px; text-align:center; padding:12px; }
    .tb-text { position:absolute; box-sizing:border-box; cursor:move; outline:1px dashed transparent; line-height:1.1; white-space:pre-wrap; word-break:break-word; }
    .tb-text.sel { outline:1px dashed ${ACCENT}; }
    .tb-text[contenteditable="true"] { cursor:text; }
    .tb-handle { position:absolute; right:-6px; bottom:-6px; width:12px; height:12px; background:${ACCENT}; border:2px solid #15191e; border-radius:50%; cursor:nwse-resize; }
    `;
    document.head.appendChild(style);
}

function clamp(v, lo, hi) {
    return Math.max(lo, Math.min(hi, v));
}

function install(node) {
    injectStyle();
    const overlayWidget = node.widgets?.find((w) => w.name === "overlay_data");

    let items = [];
    let selected = -1;
    let backdropAspect = 16 / 9;

    function loadItems() {
        try {
            const data = JSON.parse(overlayWidget?.value || "{}");
            items = Array.isArray(data.items) ? data.items : [];
        } catch {
            items = [];
        }
    }

    function persist() {
        if (overlayWidget) {
            overlayWidget.value = JSON.stringify({ items });
            overlayWidget.callback?.(overlayWidget.value);
        }
    }

    const root = document.createElement("div");
    root.className = "tb-overlay";

    const bar = document.createElement("div");
    bar.className = "tb-overlay-bar";

    const stage = document.createElement("div");
    stage.className = "tb-overlay-stage";
    const hint = document.createElement("div");
    hint.className = "tb-overlay-hint";
    hint.textContent = "Connect image (+ layout_json) and Queue once — the image and its text appear here to drag & edit.";
    stage.appendChild(hint);

    root.append(bar, stage);

    function stageSize() {
        const w = stage.clientWidth || 320;
        return { w, h: w / backdropAspect };
    }

    function applyStageHeight() {
        const { h } = stageSize();
        stage.style.height = `${Math.max(80, Math.round(h))}px`;
    }

    function renderItems() {
        // Remove old text nodes (keep hint).
        stage.querySelectorAll(".tb-text").forEach((el) => el.remove());
        const { w, h } = stageSize();
        hint.style.display = items.length ? "none" : "flex";

        items.forEach((item, index) => {
            const el = document.createElement("div");
            el.className = "tb-text" + (index === selected ? " sel" : "");
            el.style.left = `${clamp(item.x ?? 0, 0, 1) * 100}%`;
            el.style.top = `${clamp(item.y ?? 0, 0, 1) * 100}%`;
            el.style.width = `${clamp(item.w ?? 0.5, 0.02, 1) * 100}%`;
            el.style.fontSize = `${(item.fontSize ?? 0.08) * h}px`;
            el.style.color = item.color || "#FFFFFF";
            el.style.textAlign = item.align || "center";
            el.style.fontWeight = "700";
            el.style.textShadow = `0 0 ${Math.max(1, (item.strokeWidth ?? 3))}px ${item.stroke || "#000"}, 0 1px 2px ${item.stroke || "#000"}`;
            el.textContent = item.text || "";

            el.addEventListener("pointerdown", (e) => startDrag(e, index, el));
            el.addEventListener("dblclick", () => beginEdit(el, index));
            el.addEventListener("blur", () => {
                el.contentEditable = "false";
                item.text = el.textContent;
                persist();
            });

            const handle = document.createElement("div");
            handle.className = "tb-handle";
            handle.addEventListener("pointerdown", (e) => startResize(e, index));
            el.appendChild(handle);

            stage.appendChild(el);
        });
        syncToolbar();
    }

    function beginEdit(el, index) {
        selected = index;
        el.contentEditable = "true";
        el.focus();
        renderItems();
    }

    function startDrag(event, index, el) {
        if (el.isContentEditable) return;
        event.preventDefault();
        event.stopPropagation();
        selected = index;
        const { w, h } = stageSize();
        const startX = event.clientX;
        const startY = event.clientY;
        const item = items[index];
        const ox = item.x ?? 0;
        const oy = item.y ?? 0;
        const move = (e) => {
            item.x = clamp(ox + (e.clientX - startX) / w, 0, 1);
            item.y = clamp(oy + (e.clientY - startY) / h, 0, 1);
            renderItems();
        };
        const up = () => {
            window.removeEventListener("pointermove", move);
            window.removeEventListener("pointerup", up);
            persist();
        };
        window.addEventListener("pointermove", move);
        window.addEventListener("pointerup", up);
        renderItems();
    }

    function startResize(event, index) {
        event.preventDefault();
        event.stopPropagation();
        selected = index;
        const { h } = stageSize();
        const startY = event.clientY;
        const item = items[index];
        const base = item.fontSize ?? 0.08;
        const move = (e) => {
            item.fontSize = clamp(base + (e.clientY - startY) / h, 0.01, 0.6);
            renderItems();
        };
        const up = () => {
            window.removeEventListener("pointermove", move);
            window.removeEventListener("pointerup", up);
            persist();
        };
        window.addEventListener("pointermove", move);
        window.addEventListener("pointerup", up);
    }

    // ----- toolbar -----
    const addBtn = document.createElement("button");
    addBtn.textContent = "＋ Text";
    addBtn.onclick = () => {
        items.push({ text: "텍스트", x: 0.3, y: 0.45, w: 0.4, h: 0.1, fontSize: 0.07, color: "#FFFFFF", stroke: "#000000", strokeWidth: 3, align: "center" });
        selected = items.length - 1;
        persist();
        renderItems();
    };

    const delBtn = document.createElement("button");
    delBtn.textContent = "✕ Delete";
    delBtn.onclick = () => {
        if (selected < 0) return;
        items.splice(selected, 1);
        selected = -1;
        persist();
        renderItems();
    };

    const sizeLabel = document.createElement("label");
    sizeLabel.textContent = "size";
    const sizeInput = document.createElement("input");
    sizeInput.type = "range";
    sizeInput.min = "1";
    sizeInput.max = "40";
    sizeInput.step = "0.5";
    sizeInput.oninput = () => {
        if (selected < 0) return;
        items[selected].fontSize = Number(sizeInput.value) / 100;
        renderItems();
    };
    sizeInput.onchange = persist;
    sizeLabel.appendChild(sizeInput);

    const colorLabel = document.createElement("label");
    colorLabel.textContent = "color";
    const colorInput = document.createElement("input");
    colorInput.type = "color";
    colorInput.value = "#ffffff";
    colorInput.oninput = () => {
        if (selected < 0) return;
        items[selected].color = colorInput.value;
        renderItems();
    };
    colorInput.onchange = persist;
    colorLabel.appendChild(colorInput);

    const alignBtn = document.createElement("button");
    alignBtn.textContent = "align: center";
    alignBtn.onclick = () => {
        if (selected < 0) return;
        const order = ["left", "center", "right"];
        const cur = items[selected].align || "center";
        items[selected].align = order[(order.indexOf(cur) + 1) % 3];
        alignBtn.textContent = `align: ${items[selected].align}`;
        persist();
        renderItems();
    };

    bar.append(addBtn, delBtn, sizeLabel, colorLabel, alignBtn);

    function syncToolbar() {
        const item = selected >= 0 ? items[selected] : null;
        const has = !!item;
        delBtn.disabled = !has;
        sizeInput.disabled = !has;
        colorInput.disabled = !has;
        alignBtn.disabled = !has;
        if (item) {
            sizeInput.value = String((item.fontSize ?? 0.08) * 100);
            colorInput.value = item.color || "#ffffff";
            alignBtn.textContent = `align: ${item.align || "center"}`;
        }
    }

    // Click empty stage to deselect.
    stage.addEventListener("pointerdown", (e) => {
        if (e.target === stage || e.target === hint) {
            selected = -1;
            renderItems();
        }
    });

    if (node.addDOMWidget) {
        node.addDOMWidget("overlay_editor", "toobusy_overlay", root, { serialize: false });
    }

    // Receive backdrop image + seed items after a run.
    const prevOnExecuted = node.onExecuted;
    node.onExecuted = function (message) {
        prevOnExecuted?.apply(this, arguments);
        const bg = message?.toobusy_overlay_bg?.[0];
        if (bg) {
            stage.style.backgroundImage = `url(${bg})`;
            const probe = new Image();
            probe.onload = () => {
                if (probe.naturalWidth && probe.naturalHeight) {
                    backdropAspect = probe.naturalWidth / probe.naturalHeight;
                    applyStageHeight();
                    renderItems();
                }
            };
            probe.src = bg;
        }
        // Seed only when the editor is still empty, so manual edits aren't clobbered.
        if (!items.length) {
            try {
                const seeded = JSON.parse(message?.toobusy_overlay_items?.[0] || "[]");
                if (Array.isArray(seeded) && seeded.length) {
                    items = seeded;
                    persist();
                }
            } catch {}
        }
        renderItems();
    };

    loadItems();
    applyStageHeight();
    renderItems();
    requestAnimationFrame(() => {
        applyStageHeight();
        renderItems();
    });
}

app.registerExtension({
    name: "toobusy.layoutTextOverlay",
    async nodeCreated(node) {
        if (node.comfyClass === NODE_CLASS) install(node);
    },
});
