"""toobusy Load CLIP.

One text-encoder loader for everything — safetensors and .gguf — that
adapts the model to the file instead of demanding an exact-size checkpoint.

The core CLIPLoader (and the GGUF loader) build a fixed-architecture text
encoder — e.g. Llama 3.1 with a 128256-token embedding — then load the
checkpoint into it. A fine-tuned LLM that added special tokens (Dolphin's
ChatML pair -> 128258) trips `load_state_dict` with a size mismatch and
refuses to load. This node grows the model's affected tensors to the
checkpoint's size for the duration of the load, so **every token is kept**
(no trimming) and the encoder takes whatever vocab the file ships.

Loading itself is delegated to the standard loaders through their normal
interface — `.gguf` files go through ComfyUI-GGUF when installed, everything
else through the core CLIPLoader — so toobusy adds no GGUF code or
dependency of its own. The size-reconciling hook wraps PyTorch's
`load_state_dict` only while this node runs and is always restored, so no
other node or model is permanently affected.
"""

GGUF_NODE_CANDIDATES = ("CLIPLoaderGGUF", "ClipLoaderGGUF")

_FALLBACK_TYPES = [
    "stable_diffusion", "sd3", "flux2", "lumina2", "qwen_image", "wan",
    "hidream", "cosmos", "ltxv", "ace", "ideogram4",
]


def _node_class(class_name):
    try:
        import nodes

        return nodes.NODE_CLASS_MAPPINGS.get(class_name)
    except Exception:
        return None


def _gguf_node_name():
    for name in GGUF_NODE_CANDIDATES:
        if _node_class(name) is not None:
            return name
    return None


def _clip_type_options():
    """The CLIP `type` list straight from the installed core CLIPLoader, so a
    newer core's types are always present."""
    cls = _node_class("CLIPLoader")
    if cls is not None:
        try:
            options = cls.INPUT_TYPES()["required"]["type"][0]
            if isinstance(options, (list, tuple)) and options:
                return list(options)
        except Exception:
            pass
    return list(_FALLBACK_TYPES)


def _clip_name_options():
    """Union of the core text_encoders list and the GGUF loader's list, so both
    safetensors and .gguf text encoders show up in one dropdown."""
    names = []
    try:
        import folder_paths

        names.extend(folder_paths.get_filename_list("text_encoders"))
    except Exception:
        pass
    gguf = _gguf_node_name()
    if gguf is not None:
        try:
            options = _node_class(gguf).INPUT_TYPES()["required"]["clip_name"][0]
            for name in options:
                if name not in names:
                    names.append(name)
        except Exception:
            pass
    return names or ["(no text encoders found)"]


def _resize_target(checkpoint_shape, model_shape):
    """When the checkpoint tensor is the same rank as the model's, differs, and
    is never smaller in any dim, return the shape the model param should grow
    to (the checkpoint's). Otherwise None — let the normal loader handle it."""
    if len(checkpoint_shape) != len(model_shape):
        return None
    if tuple(checkpoint_shape) == tuple(model_shape):
        return None
    if all(c >= m for c, m in zip(checkpoint_shape, model_shape)):
        return tuple(checkpoint_shape)
    return None


def _grow_module_param(module, key, new_shape):
    """Replace the parameter/buffer at dotted `key` on `module` with a zero
    tensor of `new_shape` (same dtype/device), so the subsequent
    load_state_dict copies the full checkpoint tensor in. Returns True on
    success."""
    import torch

    *path, leaf = key.split(".")
    target = module
    for part in path:
        if not hasattr(target, part):
            return False
        target = getattr(target, part)
    current = getattr(target, leaf, None)
    if current is None:
        return False
    grown = torch.zeros(new_shape, dtype=current.dtype, device=current.device)
    if isinstance(current, torch.nn.Parameter):
        setattr(target, leaf, torch.nn.Parameter(grown, requires_grad=current.requires_grad))
    else:
        # Registered buffer (or plain attribute tensor).
        if leaf in getattr(target, "_buffers", {}):
            target._buffers[leaf] = grown
        else:
            setattr(target, leaf, grown)
    # Keep nn.Embedding / nn.Linear metadata consistent with the new weight.
    if leaf == "weight":
        if hasattr(target, "num_embeddings"):
            target.num_embeddings = new_shape[0]
        if hasattr(target, "out_features"):
            target.out_features = new_shape[0]
        if hasattr(target, "in_features") and len(new_shape) > 1:
            target.in_features = new_shape[-1]
    return True


def _install_resizing_load(report):
    """Monkeypatch torch.nn.Module.load_state_dict so that, before each load,
    any of the module's own params that are smaller than the matching
    checkpoint tensor are grown to fit (keeping all tokens). Returns restore();
    the patch is global for the synchronous load and must be removed in a
    finally block."""
    import torch

    original = torch.nn.Module.load_state_dict

    def resizing_load_state_dict(self, state_dict, strict=True, assign=False):
        own = self.state_dict()
        for key, value in state_dict.items():
            target = own.get(key)
            if target is None or not hasattr(value, "shape"):
                continue
            new_shape = _resize_target(tuple(value.shape), tuple(target.shape))
            if new_shape is not None and _grow_module_param(self, key, new_shape):
                report.append((key, tuple(target.shape), new_shape))
        return original(self, state_dict, strict=strict, assign=assign)

    torch.nn.Module.load_state_dict = resizing_load_state_dict

    def restore():
        torch.nn.Module.load_state_dict = original

    return restore


class ToobusyLoadClip:
    """A text-encoder loader that grows the model to fit the file, so custom /
    added-token LLM encoders (safetensors or GGUF) load with every token kept."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "clip_name": (_clip_name_options(), {"tooltip": "Text encoder file (safetensors or .gguf). Both folders are merged here."}),
                "type": (_clip_type_options(), {"default": "lumina2", "tooltip": "Text-encoder architecture (same list as the core CLIPLoader)."}),
            },
            "optional": {
                "fit_model_to_file": (
                    "BOOLEAN",
                    {"default": True, "label_on": "fit model to file", "label_off": "strict load",
                     "tooltip": "Grow the model's embedding to the checkpoint's vocab so an added-token LLM (e.g. Dolphin: 128258 vs 128256) loads with every token kept. Off = behave like the normal loader."},
                ),
                "device": (["default", "cpu"], {"advanced": True}),
            },
        }

    RETURN_TYPES = ("CLIP",)
    RETURN_NAMES = ("clip",)
    FUNCTION = "load"
    CATEGORY = "toobusy/Make"

    def _delegate(self, clip_name, type, device):
        """Load through the standard loader (GGUF pack for .gguf, core
        CLIPLoader otherwise) via its normal interface."""
        from ..ltx23_compact_sampler_node.ltx23_compact_sampler import _call_node

        is_gguf = str(clip_name).lower().endswith(".gguf")
        if is_gguf:
            gguf_node = _gguf_node_name()
            if gguf_node is None:
                raise RuntimeError(
                    f"'{clip_name}' is a GGUF text encoder but no GGUF loader node is installed. "
                    "Install ComfyUI-GGUF, or use a safetensors text encoder."
                )
            result = _call_node(gguf_node, clip_name=clip_name, type=type, device=device)
        else:
            result = _call_node("CLIPLoader", clip_name=clip_name, type=type, device=device)
        return result[0]

    def load(self, clip_name, type, fit_model_to_file=True, device="default"):
        if not fit_model_to_file:
            return (self._delegate(clip_name, type, device),)

        report = []
        restore = _install_resizing_load(report)
        try:
            clip = self._delegate(clip_name, type, device)
        finally:
            restore()

        if report:
            for key, was, now in report:
                print(f"[toobusy Load CLIP] Grew '{key}' {was} -> {now} to match the file.")
            print(f"[toobusy Load CLIP] Loaded '{clip_name}' with {len(report)} tensor(s) resized (all tokens kept).")
        else:
            print(f"[toobusy Load CLIP] Loaded '{clip_name}' (model already fit the file).")
        return (clip,)


NODE_CLASS_MAPPINGS = {
    "ToobusyLoadClip": ToobusyLoadClip,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ToobusyLoadClip": "toobusy Load CLIP",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
