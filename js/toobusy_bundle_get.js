import { app } from "../../scripts/app.js";

// toobusy Bundle Get - narrow the `role` combo to the roles actually registered
// in the connected Reference Board (no socket wall; pick the card you want).

const ALL_ROLES = [
    "character_a", "character_b", "character_c", "character_d",
    "face_a", "face_b", "outfit_a", "outfit_b",
    "pose_a", "background_a", "style_a", "prop_a",
    "main_character", "secondary_character", "pose", "outfit", "background", "style", "product",
];

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

function registeredRoles(node) {
    const items = findBoardItems(node);
    if (items == null) return null;
    const seen = new Set();
    const roles = [];
    for (const item of items) {
        const role = item?.role;
        if (!role || seen.has(role) || !ALL_ROLES.includes(role)) continue;
        if ((item.type || "") === "text" || (item.type || "") === "lora") continue;
        seen.add(role);
        roles.push(role);
    }
    return roles;
}

function updateRoleCombo(node) {
    const widget = node.widgets?.find((w) => w.name === "role");
    if (!widget) return;
    const roles = registeredRoles(node);
    const list = roles && roles.length ? roles.slice() : ALL_ROLES.slice();
    if (widget.value && !list.includes(widget.value)) list.unshift(widget.value);
    widget.options = widget.options || {};
    widget.options.values = list;
    if (!list.includes(widget.value)) widget.value = list[0];
    node.setDirtyCanvas?.(true, true);
}

app.registerExtension({
    name: "toobusy.bundleGet",
    beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== "ToobusyBundleGet") return;

        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            onNodeCreated?.apply(this, arguments);
            setTimeout(() => updateRoleCombo(this), 0);
        };

        const onConnectionsChange = nodeType.prototype.onConnectionsChange;
        nodeType.prototype.onConnectionsChange = function () {
            const result = onConnectionsChange?.apply(this, arguments);
            updateRoleCombo(this);
            return result;
        };
    },
});
