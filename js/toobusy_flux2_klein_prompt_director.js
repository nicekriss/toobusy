import { app } from "../../scripts/app.js";

// toobusy Flux2 Klein Prompt Director - button composer panel.
//
// The Python node owns the prompt logic; this panel only serializes an ordered
// list of "blocks" into the hidden `director_selection_json` widget. The node
// treats those blocks as authoritative and lets the LLM assemble them in order.

const NODE_SIZE = [380, 560];
const WIDGET_HEIGHT = 432;
const SELECTION_WIDGET = "director_selection_json";

// All reference roles the board can produce -> {label, category}. The panel
// only shows buttons for roles actually registered in the connected board.
const REFERENCE_ROLE_INFO = {
    character_a: { label: "Character A", category: "character" },
    character_b: { label: "Character B", category: "character" },
    character_c: { label: "Character C", category: "character" },
    character_d: { label: "Character D", category: "character" },
    main_character: { label: "Character A", category: "character" },
    secondary_character: { label: "Character B", category: "character" },
    face_a: { label: "Face A", category: "face" },
    face_b: { label: "Face B", category: "face" },
    outfit_a: { label: "Outfit A", category: "outfit" },
    outfit_b: { label: "Outfit B", category: "outfit" },
    outfit: { label: "Outfit", category: "outfit" },
    pose_a: { label: "Pose", category: "pose" },
    pose: { label: "Pose", category: "pose" },
    background_a: { label: "Background", category: "location" },
    background: { label: "Background", category: "location" },
    style_a: { label: "Style", category: "style" },
    style: { label: "Style", category: "style" },
    prop_a: { label: "Prop", category: "prop" },
    product: { label: "Prop", category: "prop" },
};

// Stable display order for the dynamically-shown reference buttons.
const REFERENCE_ORDER = [
    "character_a", "main_character", "character_b", "secondary_character",
    "character_c", "character_d", "face_a", "face_b",
    "outfit_a", "outfit", "outfit_b", "pose_a", "pose",
    "background_a", "background", "style_a", "style", "prop_a", "product",
];

function refRoleInfo(role) {
    return REFERENCE_ROLE_INFO[role] || { label: role, category: "character" };
}

// Walk up the bundle input chain to the connected Reference Board and read its
// registered card items from the hidden `board_json` widget.
function findBoardItems(node, depth = 0) {
    if (!node || depth > 6) return null;
    const boardWidget = node.widgets?.find((w) => w.name === "board_json");
    if (boardWidget) {
        try {
            const parsed = JSON.parse(boardWidget.value || "");
            if (parsed && Array.isArray(parsed.items)) return parsed.items;
        } catch {}
        return [];
    }
    const graph = node.graph;
    if (!graph || !node.inputs) return null;
    for (const input of node.inputs) {
        if (!input || input.link == null) continue;
        const isBundle = input.type === "TOOBUSY_BUNDLE" || /bundle/i.test(input.name || "");
        if (!isBundle) continue;
        const linkInfo = graph.links?.[input.link];
        if (!linkInfo) continue;
        const origin = graph.getNodeById?.(linkInfo.origin_id);
        const items = findBoardItems(origin, depth + 1);
        if (items) return items;
    }
    return null;
}

// Returns the ordered list of reference roles registered in the connected
// board, or null when no Reference Board is connected.
function availableReferenceRoles(node) {
    const items = findBoardItems(node);
    if (items == null) return null;
    const seen = new Set();
    const roles = [];
    for (const item of items) {
        const role = item?.role;
        if (!role || !REFERENCE_ROLE_INFO[role] || seen.has(role)) continue;
        seen.add(role);
        roles.push(role);
    }
    roles.sort((a, b) => {
        const ia = REFERENCE_ORDER.indexOf(a);
        const ib = REFERENCE_ORDER.indexOf(b);
        return (ia < 0 ? 999 : ia) - (ib < 0 ? 999 : ib);
    });
    return roles;
}

const MODIFIER_GROUPS = [
    ["camera", "Camera", ["low angle", "high angle", "eye level", "close-up", "medium shot", "wide shot", "over-the-shoulder", "dutch angle"]],
    ["lighting", "Lighting", ["soft light", "rim light", "golden hour", "studio light", "hard shadow", "backlight", "neon glow", "natural daylight"]],
    ["style", "Style", ["film grain", "editorial", "anime", "photoreal", "cinematic color", "high fashion"]],
];

const MODIFIER_LABEL = Object.fromEntries(MODIFIER_GROUPS.map(([key, label]) => [key, label]));

// Toggle flags rendered as chips in the Swap group.
const FLAG_BUTTONS = [
    ["face_swap", "FaceSwap"],
    ["product_swap", "Product Swap"],
    ["character_swap", "Character Swap"],
];
const FLAG_FIELD = { face_swap: "faceSwap", product_swap: "productSwap", character_swap: "characterSwap" };

function defaultState() {
    return {
        version: 1,
        order: [],
        refs: {},
        faceSwap: false,
        productSwap: false,
        characterSwap: false,
        camera: {},
        lighting: {},
        style: {},
        negative: "",
        custom: "",
    };
}

function findWidget(node, name) {
    return node.widgets?.find((widget) => widget.name === name);
}

function hideWidget(widget) {
    if (!widget) return;
    widget.type = "hidden";
    widget.computeSize = () => [0, -4];
    widget.hidden = true;
}

function selectedChips(state, group) {
    return MODIFIER_GROUPS.find(([key]) => key === group)[2].filter((chip) => state[group][chip]);
}

function serializeBlocks(state) {
    const blocks = [];
    for (const key of state.order) {
        if (key.startsWith("ref:")) {
            const role = key.slice(4);
            const info = refRoleInfo(role);
            blocks.push({ kind: "reference", role, category: info.category, label: info.label });
        } else if (key.startsWith("flag:")) {
            const flag = key.slice(5);
            const label = (FLAG_BUTTONS.find(([f]) => f === flag) || [flag, flag])[1];
            blocks.push({ kind: "flag", flag, label });
        } else if (key.startsWith("mod:")) {
            const group = key.slice(4);
            const text = selectedChips(state, group).join(", ");
            if (text) blocks.push({ kind: "modifier", category: group, text, label: MODIFIER_LABEL[group] });
        } else if (key === "neg") {
            const text = state.negative.trim();
            if (text) blocks.push({ kind: "negative", text, label: "Negative" });
        } else if (key === "custom") {
            const text = state.custom.trim();
            if (text) blocks.push({ kind: "custom", text, label: "Custom" });
        }
    }
    return blocks;
}

// Human-readable summary for the ordered "Selected blocks" strip.
function blockSummary(block) {
    if (block.kind === "reference") return block.label;
    if (block.kind === "flag") return block.label || block.flag;
    if (block.kind === "modifier") return `${block.label}: ${block.text}`;
    if (block.kind === "negative") return `Negative: ${block.text}`;
    if (block.kind === "custom") return `Custom: ${block.text}`;
    return "";
}

function stateFromBlocks(blocks) {
    const state = defaultState();
    if (!Array.isArray(blocks)) return state;
    for (const block of blocks) {
        if (!block || typeof block !== "object") continue;
        if (block.kind === "reference" && block.role) {
            state.refs[block.role] = true;
            state.order.push(`ref:${block.role}`);
        } else if (block.kind === "flag" && FLAG_FIELD[block.flag]) {
            state[FLAG_FIELD[block.flag]] = true;
            state.order.push(`flag:${block.flag}`);
        } else if (block.kind === "modifier" && block.category && state[block.category]) {
            for (const chip of String(block.text || "").split(",").map((part) => part.trim()).filter(Boolean)) {
                state[block.category][chip] = true;
            }
            state.order.push(`mod:${block.category}`);
        } else if (block.kind === "negative") {
            state.negative = String(block.text || "");
            state.order.push("neg");
        } else if (block.kind === "custom") {
            state.custom = String(block.text || "");
            state.order.push("custom");
        }
    }
    return state;
}

function loadState(node) {
    try {
        const parsed = JSON.parse(findWidget(node, SELECTION_WIDGET)?.value || "");
        if (parsed && Array.isArray(parsed.blocks)) {
            return stateFromBlocks(parsed.blocks);
        }
    } catch {}
    return defaultState();
}

function syncState(node, state) {
    const widget = findWidget(node, SELECTION_WIDGET);
    if (widget) {
        widget.value = JSON.stringify({ version: 1, blocks: serializeBlocks(state) });
    }
    node.setDirtyCanvas?.(true, true);
}

function orderAdd(state, key) {
    if (!state.order.includes(key)) state.order.push(key);
}

function orderRemove(state, key) {
    state.order = state.order.filter((item) => item !== key);
}

function toggleReference(state, role) {
    if (state.refs[role]) {
        delete state.refs[role];
        orderRemove(state, `ref:${role}`);
    } else {
        state.refs[role] = true;
        orderAdd(state, `ref:${role}`);
    }
}

function toggleFlag(state, flag) {
    const field = FLAG_FIELD[flag];
    if (!field) return;
    state[field] = !state[field];
    const key = `flag:${flag}`;
    if (state[field]) orderAdd(state, key);
    else orderRemove(state, key);
}

function toggleChip(state, group, chip) {
    if (state[group][chip]) delete state[group][chip];
    else state[group][chip] = true;
    if (selectedChips(state, group).length > 0) orderAdd(state, `mod:${group}`);
    else orderRemove(state, `mod:${group}`);
}

function setText(state, field, key, value) {
    state[field] = value;
    if (value.trim()) orderAdd(state, key);
    else orderRemove(state, key);
}

function injectStyle() {
    if (document.getElementById("toobusy-director-style")) return;
    const style = document.createElement("style");
    style.id = "toobusy-director-style";
    style.textContent = `
        .toobusy-director {
            box-sizing: border-box;
            width: 100%;
            height: 100%;
            overflow-y: auto;
            overflow-x: hidden;
            padding: 8px;
            font-family: var(--font-family, sans-serif);
            font-size: 12px;
            color: var(--input-text, #e6e6e6);
            background: var(--comfy-menu-bg, #1c1c1c);
            border-radius: 6px;
        }
        .toobusy-director .grp { margin-bottom: 8px; }
        .toobusy-director .grp-title {
            font-size: 10px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            opacity: 0.7;
            margin-bottom: 4px;
        }
        .toobusy-director .ref-refresh {
            cursor: pointer;
            opacity: 0.8;
            margin-left: 4px;
            font-size: 11px;
        }
        .toobusy-director .ref-refresh:hover { color: #6aa9ff; opacity: 1; }
        .toobusy-director .ref-hint {
            font-size: 11px;
            opacity: 0.55;
            padding: 2px 0;
        }
        .toobusy-director .chips { display: flex; flex-wrap: wrap; gap: 4px; }
        .toobusy-director .chip {
            border: 1px solid var(--border-color, #444);
            background: var(--comfy-input-bg, #2a2a2a);
            color: var(--input-text, #e6e6e6);
            border-radius: 12px;
            padding: 3px 9px;
            font-size: 11px;
            cursor: pointer;
            user-select: none;
            white-space: nowrap;
        }
        .toobusy-director .chip:hover { border-color: #6aa9ff; }
        .toobusy-director .chip.on {
            background: #2f6df6;
            border-color: #2f6df6;
            color: #fff;
        }
        .toobusy-director .chip.flag.on { background: #c2410c; border-color: #c2410c; }
        .toobusy-director input.txt {
            box-sizing: border-box;
            width: 100%;
            background: var(--comfy-input-bg, #2a2a2a);
            color: var(--input-text, #e6e6e6);
            border: 1px solid var(--border-color, #444);
            border-radius: 4px;
            padding: 4px 6px;
            font-size: 11px;
        }
        .toobusy-director .selected {
            border-top: 1px solid var(--border-color, #444);
            margin-top: 8px;
            padding-top: 6px;
        }
        .toobusy-director .selrow { display: flex; align-items: center; justify-content: space-between; }
        .toobusy-director .selrow .clear {
            cursor: pointer; opacity: 0.7; font-size: 10px; text-decoration: underline;
        }
        .toobusy-director .sel-list { display: flex; flex-direction: column; gap: 3px; margin-top: 5px; }
        .toobusy-director .sel-item {
            display: flex; align-items: center; gap: 6px;
            background: var(--comfy-input-bg, #2a2a2a);
            border: 1px solid var(--border-color, #3a3a3a);
            border-radius: 4px;
            padding: 3px 6px;
            font-size: 11px;
        }
        .toobusy-director .sel-item .idx {
            background: #2f6df6; color: #fff; border-radius: 8px;
            min-width: 15px; height: 15px; line-height: 15px; text-align: center;
            font-size: 10px;
        }
        .toobusy-director .sel-item .txt { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .toobusy-director .sel-item .x { cursor: pointer; opacity: 0.6; }
        .toobusy-director .sel-item .x:hover { opacity: 1; color: #ff6b6b; }
        .toobusy-director .sel-empty { opacity: 0.5; font-size: 11px; padding: 3px 0; }
    `;
    document.head.appendChild(style);
}

function stopEvents(root) {
    const stop = (event) => event.stopPropagation();
    ["pointerdown", "pointerup", "pointermove", "mousedown", "mouseup", "click", "dblclick", "wheel", "keydown", "keyup", "input", "change"].forEach(
        (type) => root.addEventListener(type, stop),
    );
}

function removeBlockByKey(state, key) {
    if (key.startsWith("ref:")) {
        delete state.refs[key.slice(4)];
    } else if (key.startsWith("flag:")) {
        const field = FLAG_FIELD[key.slice(5)];
        if (field) state[field] = false;
    } else if (key.startsWith("mod:")) {
        state[key.slice(4)] = {};
    } else if (key === "neg") {
        state.negative = "";
    } else if (key === "custom") {
        state.custom = "";
    }
    orderRemove(state, key);
}

function keyForBlockIndex(state, index) {
    // Walk order, skipping entries that serialize to nothing, to map a rendered
    // block back to its order key.
    let visible = 0;
    for (const key of state.order) {
        if (key.startsWith("mod:") && selectedChips(state, key.slice(4)).length === 0) continue;
        if (key === "neg" && !state.negative.trim()) continue;
        if (key === "custom" && !state.custom.trim()) continue;
        if (visible === index) return key;
        visible += 1;
    }
    return null;
}

function buildPanel(node) {
    injectStyle();
    const state = loadState(node);
    const root = document.createElement("div");
    root.className = "toobusy-director";
    stopEvents(root);

    const render = () => {
        const blocks = serializeBlocks(state);
        const selList = blocks.length
            ? `<div class="sel-list">${blocks
                  .map(
                      (block, index) =>
                          `<div class="sel-item"><span class="idx">${index + 1}</span><span class="txt">${escapeHtml(blockSummary(block))}</span><span class="x" data-sel="${index}">✕</span></div>`,
                  )
                  .join("")}</div>`
            : `<div class="sel-empty">No blocks selected yet.</div>`;

        const roles = availableReferenceRoles(node);
        let refChips;
        if (roles === null) {
            refChips = `<div class="ref-hint">Connect a Reference Board to list its characters &amp; references.</div>`;
        } else if (roles.length === 0) {
            refChips = `<div class="ref-hint">No reference cards in the connected board yet.</div>`;
        } else {
            refChips = roles
                .map((role) => `<div class="chip${state.refs[role] ? " on" : ""}" data-ref="${role}">${escapeHtml(refRoleInfo(role).label)}</div>`)
                .join("");
        }

        root.innerHTML = `
            <div class="grp">
                <div class="grp-title">References <span class="ref-refresh" title="Re-read the connected board">↻</span></div>
                <div class="chips">${refChips}</div>
            </div>
            <div class="grp">
                <div class="grp-title">Swap</div>
                <div class="chips">
                    ${FLAG_BUTTONS.map(([flag, fl]) => `<div class="chip flag${state[FLAG_FIELD[flag]] ? " on" : ""}" data-flag="${flag}">${fl}</div>`).join("")}
                </div>
            </div>
            ${MODIFIER_GROUPS.map(
                ([group, label, chips]) => `
                <div class="grp">
                    <div class="grp-title">${label}</div>
                    <div class="chips">
                        ${chips.map((chip) => `<div class="chip${state[group][chip] ? " on" : ""}" data-grp="${group}" data-chip="${escapeAttr(chip)}">${chip}</div>`).join("")}
                    </div>
                </div>`,
            ).join("")}
            <div class="grp">
                <div class="grp-title">Negative</div>
                <input class="txt" data-text="negative" placeholder="things to avoid (free text)" value="${escapeAttr(state.negative)}">
            </div>
            <div class="grp">
                <div class="grp-title">Custom</div>
                <input class="txt" data-text="custom" placeholder="extra prompt detail (free text)" value="${escapeAttr(state.custom)}">
            </div>
            <div class="selected">
                <div class="selrow">
                    <div class="grp-title" style="margin:0;">Selected blocks (order kept)</div>
                    <span class="clear">clear all</span>
                </div>
                ${selList}
            </div>
        `;

        root.querySelectorAll("[data-ref]").forEach((el) =>
            el.addEventListener("click", () => {
                toggleReference(state, el.dataset.ref);
                commit();
            }),
        );
        root.querySelector(".ref-refresh")?.addEventListener("click", () => render());
        root.querySelectorAll("[data-flag]").forEach((el) =>
            el.addEventListener("click", () => {
                toggleFlag(state, el.dataset.flag);
                commit();
            }),
        );
        root.querySelectorAll("[data-grp]").forEach((el) =>
            el.addEventListener("click", () => {
                toggleChip(state, el.dataset.grp, el.dataset.chip);
                commit();
            }),
        );
        root.querySelectorAll("input[data-text]").forEach((el) =>
            el.addEventListener("input", () => {
                const field = el.dataset.text;
                setText(state, field, field === "negative" ? "neg" : "custom", el.value);
                // Light commit: no full re-render while typing, just resync + selected strip.
                syncState(node, state);
                refreshSelected();
            }),
        );
        root.querySelector(".clear").addEventListener("click", () => {
            const fresh = defaultState();
            Object.assign(state, fresh);
            commit();
        });
        root.querySelectorAll(".sel-item .x").forEach((el) =>
            el.addEventListener("click", () => {
                const key = keyForBlockIndex(state, Number(el.dataset.sel));
                if (key) removeBlockByKey(state, key);
                commit();
            }),
        );
    };

    const refreshSelected = () => {
        const blocks = serializeBlocks(state);
        const container = root.querySelector(".selected");
        if (!container) return;
        const selList = blocks.length
            ? `<div class="sel-list">${blocks
                  .map(
                      (block, index) =>
                          `<div class="sel-item"><span class="idx">${index + 1}</span><span class="txt">${escapeHtml(blockSummary(block))}</span><span class="x" data-sel="${index}">✕</span></div>`,
                  )
                  .join("")}</div>`
            : `<div class="sel-empty">No blocks selected yet.</div>`;
        const old = container.querySelector(".sel-list, .sel-empty");
        if (old) old.outerHTML = selList;
        container.querySelectorAll(".sel-item .x").forEach((el) =>
            el.addEventListener("click", () => {
                const key = keyForBlockIndex(state, Number(el.dataset.sel));
                if (key) removeBlockByKey(state, key);
                commit();
            }),
        );
    };

    const commit = () => {
        syncState(node, state);
        render();
    };

    function refreshFromWidget() {
        Object.assign(state, loadState(node));
        render();
    }

    render();
    syncState(node, state);
    return { root, refreshFromWidget, rerender: render };
}

function escapeHtml(value) {
    return String(value).replace(/[&<>]/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[ch]));
}

function escapeAttr(value) {
    return String(value).replace(/[&<>"]/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[ch]));
}

app.registerExtension({
    name: "toobusy.flux2KleinPromptDirector",
    beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== "ToobusyFlux2KleinPromptDirector") return;

        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            onNodeCreated?.apply(this, arguments);
            hideWidget(findWidget(this, SELECTION_WIDGET));
            const panel = buildPanel(this);
            this._toobusyDirectorPanel = panel;
            if (this.addDOMWidget) {
                const domWidget = this.addDOMWidget("director_panel", "div", panel.root, {
                    serialize: false,
                    getMinHeight: () => WIDGET_HEIGHT,
                    getHeight: () => WIDGET_HEIGHT,
                });
                if (domWidget) {
                    domWidget.computeSize = () => [NODE_SIZE[0] - 20, WIDGET_HEIGHT];
                }
            }
            if (!this.properties?.toobusy_director_sized) {
                this.properties = this.properties || {};
                this.properties.toobusy_director_sized = true;
                if (this.setSize) this.setSize(NODE_SIZE);
                else this.size = [...NODE_SIZE];
            }
        };

        const onConfigure = nodeType.prototype.onConfigure;
        nodeType.prototype.onConfigure = function () {
            onConfigure?.apply(this, arguments);
            // Restore the panel from the deserialized hidden widget value.
            this._toobusyDirectorPanel?.refreshFromWidget?.();
        };

        const onConnectionsChange = nodeType.prototype.onConnectionsChange;
        nodeType.prototype.onConnectionsChange = function () {
            const result = onConnectionsChange?.apply(this, arguments);
            // Re-read the connected board so reference buttons stay in sync.
            this._toobusyDirectorPanel?.rerender?.();
            return result;
        };

        const originalComputeSize = nodeType.prototype.computeSize;
        nodeType.prototype.computeSize = function (out) {
            const size = originalComputeSize?.call(this, out) || NODE_SIZE;
            return [Math.max(size[0], NODE_SIZE[0]), Math.max(size[1], NODE_SIZE[1])];
        };
    },
});
