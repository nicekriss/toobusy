import re


class ToobusyMiniMaxH3SemanticReference:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "enabled": ("BOOLEAN", {"default": True, "label_on": "사용", "label_off": "사용 안 함"}),
                "routing": (["auto", "semantic_only", "visual_reference"], {"default": "auto"}),
                "role_label": ("STRING", {"default": "", "multiline": False}),
            },
            "optional": {
                "analysis": ("STRING", {"lazy": True}),
                "image": ("IMAGE", {"lazy": True}),
            },
        }

    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("visual_reference", "semantic_role")
    FUNCTION = "select"
    CATEGORY = "toobusy/Make"
    DESCRIPTION = "Uses Gemma analysis to forward only safe visual references while always preserving semantic role text."

    @staticmethod
    def _parse_analysis(analysis):
        text = (analysis or "").strip()
        match = re.search(r"VISUAL_REFERENCE\s*:\s*(YES|NO)", text, flags=re.IGNORECASE)
        visual_safe = bool(match and match.group(1).upper() == "YES")
        description_match = re.search(r"SEMANTIC_DESCRIPTION\s*:\s*(.+)", text, flags=re.IGNORECASE | re.DOTALL)
        if description_match:
            description = description_match.group(1).strip()
        else:
            description = re.sub(r"^\s*VISUAL_REFERENCE\s*:\s*(?:YES|NO)\s*$", "", text, flags=re.IGNORECASE | re.MULTILINE).strip()
        return visual_safe, description

    @classmethod
    def check_lazy_status(cls, enabled, routing, role_label, analysis=None, image=None):
        if not enabled:
            return []
        if analysis is None:
            return ["analysis"]
        visual_safe, _description = cls._parse_analysis(analysis)
        use_image = routing == "visual_reference" or (routing == "auto" and visual_safe)
        if use_image and image is None:
            return ["image"]
        return []

    def select(self, enabled, routing, role_label, analysis=None, image=None):
        if not enabled or analysis is None:
            return (None, "")
        visual_safe, description = self._parse_analysis(analysis)
        use_image = routing == "visual_reference" or (routing == "auto" and visual_safe)
        label = role_label.strip()
        semantic_role = f"{label}: {description}" if label and description else description
        return (image if use_image else None, semantic_role)


class ToobusyMiniMaxH3ReferenceManifest:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "optional_4_enabled": ("BOOLEAN", {"default": False}),
                "optional_5_enabled": ("BOOLEAN", {"default": False}),
                "optional_6_enabled": ("BOOLEAN", {"default": False}),
            },
            "optional": {
                "outfit_analysis": ("STRING", {"lazy": True}),
                "pose_analysis": ("STRING", {"lazy": True}),
                "optional_4_analysis": ("STRING", {"lazy": True}),
                "optional_5_analysis": ("STRING", {"lazy": True}),
                "optional_6_analysis": ("STRING", {"lazy": True}),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("reference_manifest",)
    FUNCTION = "build"
    CATEGORY = "toobusy/Make"
    DESCRIPTION = "Builds semantic roles and compact <Picture N> bindings for the visual references that passed the Gemma safety gate."

    @classmethod
    def check_lazy_status(
        cls,
        optional_4_enabled,
        optional_5_enabled,
        optional_6_enabled,
        outfit_analysis=None,
        pose_analysis=None,
        optional_4_analysis=None,
        optional_5_analysis=None,
        optional_6_analysis=None,
    ):
        needed = []
        if outfit_analysis is None:
            needed.append("outfit_analysis")
        if pose_analysis is None:
            needed.append("pose_analysis")
        if optional_4_enabled and optional_4_analysis is None:
            needed.append("optional_4_analysis")
        if optional_5_enabled and optional_5_analysis is None:
            needed.append("optional_5_analysis")
        if optional_6_enabled and optional_6_analysis is None:
            needed.append("optional_6_analysis")
        return needed

    @staticmethod
    def _append_role(lines, label, analysis, picture_number, allow_visual):
        visual_safe, description = ToobusyMiniMaxH3SemanticReference._parse_analysis(analysis)
        if description:
            lines.append(f"{label}: {description}")
        if allow_visual and visual_safe:
            lines.append(
                f"VISUAL REFERENCE BINDING: <Picture {picture_number}> supplies only the {label.lower()} geometry, "
                "construction, colors, and materials. Ignore its source person, pose, background, composition, and rendering style."
            )
            return picture_number + 1
        return picture_number

    def build(
        self,
        optional_4_enabled,
        optional_5_enabled,
        optional_6_enabled,
        outfit_analysis=None,
        pose_analysis=None,
        optional_4_analysis=None,
        optional_5_analysis=None,
        optional_6_analysis=None,
    ):
        lines = [
            "FACE IDENTITY DIRECTION: <Picture 1> supplies facial identity only; ignore its cap, clothing, background, lighting, and composition."
        ]
        picture_number = self._append_role(lines, "OUTFIT SEMANTIC DESCRIPTION", outfit_analysis, 2, True)
        self._append_role(lines, "POSE SEMANTIC DESCRIPTION", pose_analysis, picture_number, False)
        for enabled, label, analysis in (
            (optional_4_enabled, "OPTIONAL REFERENCE ROLE 4", optional_4_analysis),
            (optional_5_enabled, "OPTIONAL REFERENCE ROLE 5", optional_5_analysis),
            (optional_6_enabled, "OPTIONAL REFERENCE ROLE 6", optional_6_analysis),
        ):
            if enabled:
                picture_number = self._append_role(lines, label, analysis, picture_number, True)
        return ("\n".join(lines),)


NODE_CLASS_MAPPINGS = {
    "ToobusyMiniMaxH3SemanticReference": ToobusyMiniMaxH3SemanticReference,
    "ToobusyMiniMaxH3ReferenceManifest": ToobusyMiniMaxH3ReferenceManifest,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ToobusyMiniMaxH3SemanticReference": "toobusy MiniMax H3 Semantic Reference",
    "ToobusyMiniMaxH3ReferenceManifest": "toobusy MiniMax H3 Reference Manifest",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
