class ToobusyPromptLines:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "source": ("STRING", {"default": "", "multiline": True}),
                "start_index": ("INT", {"default": 0, "min": 0, "max": 100000}),
                "max_rows": ("INT", {"default": 1000, "min": 1, "max": 100000}),
                "remove_empty_lines": ("BOOLEAN", {"default": True}),
                "strip_lines": ("BOOLEAN", {"default": True}),
            },
        }

    RETURN_TYPES = ("STRING", "STRING", "INT")
    RETURN_NAMES = ("line", "text", "count")
    OUTPUT_IS_LIST = (True, False, False)
    FUNCTION = "split"
    CATEGORY = "toobusy/Plan"

    def split(self, source, start_index, max_rows, remove_empty_lines, strip_lines):
        lines = str(source or "").splitlines()
        if strip_lines:
            lines = [line.strip() for line in lines]
        if remove_empty_lines:
            lines = [line for line in lines if line.strip()]

        start = max(0, int(start_index))
        end = start + max(1, int(max_rows))
        selected = lines[start:end]
        count = len(selected)

        # Comfy list outputs should not be empty; keep the graph executable.
        line_output = selected if selected else [""]
        text_output = "\n".join(selected)
        return (line_output, text_output, count)


NODE_CLASS_MAPPINGS = {
    "ToobusyPromptLines": ToobusyPromptLines,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ToobusyPromptLines": "toobusy Prompt Lines",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
