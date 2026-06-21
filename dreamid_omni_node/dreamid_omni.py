import importlib
import json


DREAMID_INSTALL_MESSAGE = """DreamID-Omni optional dependencies are missing.

Install only if you want to use toobusy DreamID-Omni:

pip install -r custom_nodes/toobusy/requirements_dreamid_omni.txt
"""

# Names the upstream benjiyaya/ComfyUI_Dreamid-Omni nodes register globally.
# toobusy DreamID-Omni delegates to these so we never duplicate the engine load,
# tensor->file glue, engine.generate signature, or video saving (the parts that
# drift). We only add Bundle integration on top.
UPSTREAM_LOADER_NAME = "ComfyUI DreamID-Omni Loader"
UPSTREAM_SAMPLER_NAME = "ComfyUI DreamID-Omni Sampler"

# Note: `dashscope` is intentionally excluded. Upstream lists it, but it is only
# used by dreamid_omni/utils/prompt_extend.py (an Alibaba Wan cloud prompt
# rewriter) which the ComfyUI nodes/engine never import. DreamID-Omni runs fully
# local without it, so requiring it would force an unused cloud SDK + API key.
OPTIONAL_DEPENDENCIES = (
    ("omegaconf", "omegaconf"),
    ("librosa", "librosa"),
    ("cv2", "opencv-python"),
    ("diffusers", "diffusers"),
    ("optimum", "optimum[quanto]"),
    ("open_clip", "open-clip-torch"),
    ("moviepy", "moviepy<2"),
    ("ftfy", "ftfy"),
    ("regex", "regex"),
    ("pydub", "pydub"),
    ("pandas", "pandas"),
)


def _missing_optional_dependencies(importer=importlib.import_module):
    missing = []
    for module_name, package_name in OPTIONAL_DEPENDENCIES:
        try:
            importer(module_name)
        except Exception:
            missing.append(package_name)
    return missing


def _ensure_optional_dependencies(importer=importlib.import_module):
    missing = _missing_optional_dependencies(importer)
    if missing:
        details = "\nMissing: " + ", ".join(missing)
        raise RuntimeError(DREAMID_INSTALL_MESSAGE + details)


# --- Upstream node resolution (single seam for tests to patch) -------------
def _comfy_node_mappings():
    try:
        import nodes as comfy_nodes  # ComfyUI's global node registry
    except Exception:
        return {}
    return getattr(comfy_nodes, "NODE_CLASS_MAPPINGS", {}) or {}


def _upstream_class(name):
    return _comfy_node_mappings().get(name)


def _require_upstream(name):
    cls = _upstream_class(name)
    if cls is None:
        raise RuntimeError(
            f"Upstream node '{name}' was not found.\n\n"
            "toobusy DreamID-Omni delegates to the benjiyaya/ComfyUI_Dreamid-Omni nodes.\n"
            "Install that custom node and its model (ComfyUI/models/DreamID-Omni/DreamID_Omni/*.safetensors), "
            "then restart ComfyUI."
        )
    return cls


# --- Bundle extraction helpers ---------------------------------------------
def _cards(bundle):
    if not isinstance(bundle, dict):
        return []
    cards = bundle.get("cards")
    return cards if isinstance(cards, list) else []


def _role_payload(bundle, role):
    if not isinstance(bundle, dict):
        return None
    data = bundle.get(role)
    return data if isinstance(data, dict) else None


def _first_from_roles(bundle, roles, key):
    if not isinstance(bundle, dict):
        return None
    for role in roles:
        data = _role_payload(bundle, role)
        if data is not None and data.get(key) is not None:
            return data.get(key)
    for card in _cards(bundle):
        if not isinstance(card, dict) or card.get("role") not in roles:
            continue
        if card.get(key) is not None:
            return card.get(key)
    return None


def _one_image(image):
    if image is None:
        return None
    shape = getattr(image, "shape", None)
    if shape is not None and len(shape) >= 1:
        try:
            if int(shape[0]) > 1:
                return image[0:1]
        except Exception:
            return image
    return image


def _select_person_inputs(bundle):
    image_1 = _one_image(_first_from_roles(bundle, ("character_a", "main_character"), "image"))
    image_2 = _one_image(_first_from_roles(bundle, ("character_b", "secondary_character"), "image"))
    audio_1 = _first_from_roles(bundle, ("audio_a", "audio_1"), "audio")
    audio_2 = _first_from_roles(bundle, ("audio_b", "audio_2"), "audio")
    return image_1, audio_1, image_2, audio_2


def _bundle_prompt(bundle, fallback):
    if isinstance(bundle, dict):
        prompt = str(bundle.get("resolved_prompt") or "").strip()
        if prompt:
            return prompt
    return str(fallback or "").strip()


def _bundle_debug(bundle, prompt, image_1, audio_1, image_2, audio_2):
    selected = {
        "prompt": prompt,
        "person1_image": image_1 is not None,
        "person1_audio": audio_1 is not None,
        "person2_image": image_2 is not None,
        "person2_audio": audio_2 is not None,
        "two_person": bool((image_2 is not None) and (audio_2 is not None)),
    }
    if isinstance(bundle, dict):
        selected["flags"] = bundle.get("flags") if isinstance(bundle.get("flags"), dict) else {}
    return json.dumps(selected, ensure_ascii=False, indent=2)


# Fallback widgets when the upstream node is not installed yet, so the toobusy
# node still loads and shows a sensible UI. Mirrors upstream defaults.
_LOADER_FALLBACK_INPUTS = {
    "required": {
        "model_file": ("STRING", {"default": "dreamid_omni_bf16.safetensors"}),
        "precision": (["FP32", "BF16", "FP8"], {"default": "FP8"}),
        "attention_backend": (["SDPA", "Sage Attention", "Flash Attention"], {"default": "SDPA"}),
    }
}


class ToobusyDreamIDOmniLoader:
    @classmethod
    def INPUT_TYPES(cls):
        upstream = _upstream_class(UPSTREAM_LOADER_NAME)
        if upstream is not None:
            try:
                return upstream.INPUT_TYPES()
            except Exception:
                pass
        return _LOADER_FALLBACK_INPUTS

    RETURN_TYPES = ("TOOBUSY_DREAMID_OMNI_PIPELINE", "STRING")
    RETURN_NAMES = ("pipeline", "loader_info")
    FUNCTION = "load"
    CATEGORY = "toobusy/DreamID"

    def load(self, model_file, precision, attention_backend, **kwargs):
        loader_cls = _require_upstream(UPSTREAM_LOADER_NAME)
        _ensure_optional_dependencies()
        result = loader_cls().load(
            precision=precision,
            attention_backend=attention_backend,
            model_file=model_file,
        )
        pipeline = result[0] if isinstance(result, (tuple, list)) and result else result
        info = {
            "status": "loaded",
            "delegated_to": UPSTREAM_LOADER_NAME,
            "model_file": str(model_file or ""),
            "precision": str(precision or ""),
            "attention_backend": str(attention_backend or ""),
        }
        return (pipeline, json.dumps(info, ensure_ascii=False, indent=2))


class ToobusyDreamIDOmniTalker:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "pipeline": ("TOOBUSY_DREAMID_OMNI_PIPELINE",),
                "toobusy_bundle": ("TOOBUSY_BUNDLE",),
                "prompt": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "",
                        "tooltip": "Fallback prompt. If the Bundle has resolved_prompt, the Bundle wins.",
                    },
                ),
                "sample_steps": ("INT", {"default": 20, "min": 1, "max": 100}),
                "seed": ("INT", {"default": 1, "min": 0, "max": 0xffffffffffffffff, "control_after_generate": True}),
                "width": ("INT", {"default": 992, "min": 64, "max": 2048, "step": 8}),
                "height": ("INT", {"default": 512, "min": 64, "max": 2048, "step": 8}),
                "solver_name": (["unipc", "dpm++", "euler"], {"default": "unipc"}),
                "text_encoder_offload": ("BOOLEAN", {"default": True}),
                "release_diffusion_after_run": ("BOOLEAN", {"default": False}),
            },
            "optional": {
                "ref_image": ("IMAGE", {"tooltip": "Advanced fallback. Overrides Bundle Character A."}),
                "ref_image2": ("IMAGE", {"tooltip": "Advanced fallback. Overrides Bundle Character B."}),
                "ref_audio": ("AUDIO", {"tooltip": "Advanced fallback. Overrides Bundle Audio A."}),
                "ref_audio2": ("AUDIO", {"tooltip": "Advanced fallback. Overrides Bundle Audio B."}),
            },
        }

    RETURN_TYPES = ("VIDEO", "TOOBUSY_BUNDLE", "STRING", "STRING")
    RETURN_NAMES = ("video", "toobusy_bundle", "resolved_prompt", "selected_json")
    FUNCTION = "talk"
    CATEGORY = "toobusy/DreamID"

    def talk(
        self,
        pipeline,
        toobusy_bundle,
        prompt,
        sample_steps,
        seed,
        width,
        height,
        solver_name,
        text_encoder_offload=True,
        release_diffusion_after_run=False,
        ref_image=None,
        ref_image2=None,
        ref_audio=None,
        ref_audio2=None,
    ):
        sampler_cls = _require_upstream(UPSTREAM_SAMPLER_NAME)

        bundle_image_1, bundle_audio_1, bundle_image_2, bundle_audio_2 = _select_person_inputs(toobusy_bundle)
        image_1 = _one_image(ref_image) if ref_image is not None else bundle_image_1
        image_2 = _one_image(ref_image2) if ref_image2 is not None else bundle_image_2
        audio_1 = ref_audio if ref_audio is not None else bundle_audio_1
        audio_2 = ref_audio2 if ref_audio2 is not None else bundle_audio_2

        if image_1 is None or audio_1 is None:
            raise RuntimeError(
                "DreamID-Omni needs Character A image + Audio A.\n"
                "Add them to the Reference Board (roles Character A and Audio A), or wire ref_image/ref_audio."
            )
        # Upstream requires the second person's image and audio to be paired.
        if (image_2 is None) != (audio_2 is None):
            image_2 = None
            audio_2 = None

        resolved_prompt = _bundle_prompt(toobusy_bundle, prompt)
        selected_json = _bundle_debug(toobusy_bundle, resolved_prompt, image_1, audio_1, image_2, audio_2)

        result = sampler_cls().sample(
            pipeline=pipeline,
            prompt=resolved_prompt,
            sample_steps=int(sample_steps),
            seed=int(seed),
            width=int(width),
            height=int(height),
            solver_name=str(solver_name),
            text_encoder_offload=bool(text_encoder_offload),
            release_diffusion_after_run=bool(release_diffusion_after_run),
            ref_image=image_1,
            ref_image2=image_2,
            ref_audio=audio_1,
            ref_audio2=audio_2,
        )
        video = result[0] if isinstance(result, (tuple, list)) and result else result

        out_bundle = dict(toobusy_bundle) if isinstance(toobusy_bundle, dict) else {"version": 1}
        flags = out_bundle.get("flags") if isinstance(out_bundle.get("flags"), dict) else {}
        out_bundle["flags"] = {**flags, "dreamid_talker_applied": True}
        return (video, out_bundle, resolved_prompt, selected_json)


NODE_CLASS_MAPPINGS = {
    "ToobusyDreamIDOmniLoader": ToobusyDreamIDOmniLoader,
    "ToobusyDreamIDOmniTalker": ToobusyDreamIDOmniTalker,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ToobusyDreamIDOmniLoader": "toobusy DreamID-Omni Loader",
    "ToobusyDreamIDOmniTalker": "toobusy DreamID-Omni Talker",
}
