import { app } from "/scripts/app.js";

app.registerExtension({
  name: "hf.model.autoloader.ui",
  nodeCreated(node) {
    if (node.comfyClass !== "HFModelAutoLoader") return;

    // The node's actual download happens on queue (download_if_missing). This
    // button is just a convenience link to the source on Hugging Face, built
    // from the `hf_source` widget (the old `huggingface_url` widget never
    // existed, so the button used to do nothing).
    const openOnHF = () => {
      const source = node.widgets?.find((w) => w.name === "hf_source")?.value;
      if (typeof source !== "string" || !source.trim()) return;
      const trimmed = source.trim();
      const url = /^https?:\/\//i.test(trimmed)
        ? trimmed
        : `https://huggingface.co/${trimmed.replace(/^\/+|\/+$/g, "")}`;
      window.open(url, "_blank", "noopener,noreferrer");
    };

    node.addWidget("button", "Open on Hugging Face", "", openOnHF);
  },
});
