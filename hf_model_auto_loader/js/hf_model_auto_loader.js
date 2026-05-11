import { app } from "/scripts/app.js";

app.registerExtension({
  name: "hf.model.autoloader.ui",
  nodeCreated(node) {
    if (node.comfyClass !== "HFModelAutoLoader") return;

    const openDownload = () => {
      const widget = node.widgets?.find((w) => w.name === "huggingface_url");
      const url = widget?.value;
      if (typeof url === "string" && url.startsWith("http")) {
        window.open(url, "_blank", "noopener,noreferrer");
      }
    };

    node.addWidget("button", "Download (HF)", "", openDownload);
  },
});
