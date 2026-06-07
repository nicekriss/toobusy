import { app } from "../../scripts/app.js";

function findWidget(node, name) {
    return node.widgets?.find((widget) => widget.name === name);
}

function setWidgetVisible(node, widget, visible) {
    if (!widget) return;
    if (!widget._toobusyOriginalType) {
        widget._toobusyOriginalType = widget.type;
        widget._toobusyOriginalComputeSize = widget.computeSize;
    }
    widget.hidden = !visible;
    widget.disabled = !visible;
    widget.type = visible ? widget._toobusyOriginalType : "hidden";
    widget.computeSize = visible ? widget._toobusyOriginalComputeSize : () => [0, -4];
    node.setDirtyCanvas?.(true, true);
}

function isAdvanced(node) {
    return !!(node.properties && node.properties.toobusy_advanced);
}

function sigmasConnected(node) {
    const input = node.inputs?.find((slot) => slot.name === "sigmas");
    return !!(input && input.link != null);
}

function apply(node) {
    const advanced = isAdvanced(node);
    const overridden = sigmasConnected(node);

    // manual_sigmas only matters when no SIGMAS input is connected, and is an
    // expert control, so it shows only in Advanced and only when not overridden.
    setWidgetVisible(node, findWidget(node, "manual_sigmas"), advanced && !overridden);

    const readout = findWidget(node, "sigma_source");
    if (readout) {
        readout.value = overridden
            ? "sigmas: connected SIGMAS input (overrides manual_sigmas)"
            : "sigmas: using manual_sigmas (default schedule)";
    }

    if (node._toobusyAdvButton) {
        node._toobusyAdvButton.name = advanced ? "Hide advanced settings" : "Show advanced settings";
    }

    node.setDirtyCanvas?.(true, true);
    app.graph?.setDirtyCanvas?.(true, true);
}

app.registerExtension({
    name: "toobusy.ltxCompactSampler",
    beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== "LTX23CompactAVSampler") {
            return;
        }

        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            onNodeCreated?.apply(this, arguments);

            this.addWidget("text", "sigma_source", "", () => {}, { serialize: false });

            this._toobusyAdvButton = this.addWidget("button", "Show advanced settings", "advanced", () => {
                this.properties = this.properties || {};
                this.properties.toobusy_advanced = !isAdvanced(this);
                apply(this);
            }, { serialize: false });

            apply(this);
        };

        const onConfigure = nodeType.prototype.onConfigure;
        nodeType.prototype.onConfigure = function () {
            onConfigure?.apply(this, arguments);
            apply(this);
        };

        const onConnectionsChange = nodeType.prototype.onConnectionsChange;
        nodeType.prototype.onConnectionsChange = function () {
            onConnectionsChange?.apply(this, arguments);
            apply(this);
        };
    },
});
