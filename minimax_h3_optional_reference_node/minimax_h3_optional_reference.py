class ToobusyMiniMaxH3OptionalReference:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "enabled": ("BOOLEAN", {"default": False, "label_on": "사용", "label_off": "사용 안 함"}),
                "role": ("STRING", {"multiline": True, "default": ""}),
            },
            "optional": {
                "image": ("IMAGE", {"lazy": True}),
            },
        }

    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("optional_image", "active_role_line")
    FUNCTION = "select"
    CATEGORY = "toobusy/Make"
    DESCRIPTION = "Enables an optional MiniMax H3 reference image and its role without evaluating the image branch while disabled."

    @classmethod
    def check_lazy_status(cls, enabled, role, image=None):
        if enabled and image is None:
            return ["image"]
        return []

    def select(self, enabled, role, image=None):
        if not enabled or image is None:
            return (None, "")
        role = role.strip()
        return (image, f"OPTIONAL REFERENCE ROLE: {role}" if role else "")


NODE_CLASS_MAPPINGS = {
    "ToobusyMiniMaxH3OptionalReference": ToobusyMiniMaxH3OptionalReference,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ToobusyMiniMaxH3OptionalReference": "toobusy MiniMax H3 Optional Reference",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
