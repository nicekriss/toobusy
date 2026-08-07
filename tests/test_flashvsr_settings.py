import ast
import importlib.util
import pathlib
import sys
import types


ROOT = pathlib.Path(__file__).resolve().parents[1]


folder_paths = types.ModuleType("folder_paths")
folder_paths.get_filename_list = lambda name: ["model.safetensors"]
folder_paths.get_full_path = lambda name, value: value
sys.modules["folder_paths"] = folder_paths

torch = types.ModuleType("torch")
sys.modules["torch"] = torch

comfy = types.ModuleType("comfy")
comfy_utils = types.ModuleType("comfy.utils")
comfy_utils.ProgressBar = object
comfy.utils = comfy_utils
sys.modules["comfy"] = comfy
sys.modules["comfy.utils"] = comfy_utils

package = types.ModuleType("flashvsr_node")
package.__path__ = [str(ROOT / "flashvsr_node")]
sys.modules["flashvsr_node"] = package

runtime = types.ModuleType("flashvsr_node.backend.runtime")


class FlashVSRModelHandle:
    def __init__(self, dit, projection, prompt, offload, aggressive_offload=False):
        self.offload = offload
        self.aggressive_offload = aggressive_offload


runtime.FlashVSRModelHandle = FlashVSRModelHandle
for name in (
    "chunk_starts",
    "decode_chunk",
    "load_dit_pipeline",
    "load_vae_pipeline",
    "merge_chunk",
    "release_pipeline",
    "resize_images",
    "sample_chunk",
    "validate_paths",
):
    setattr(runtime, name, lambda *args, **kwargs: None)
sys.modules["flashvsr_node.backend.runtime"] = runtime

spec = importlib.util.spec_from_file_location("flashvsr_node.nodes", ROOT / "flashvsr_node" / "nodes.py")
nodes = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = nodes
spec.loader.exec_module(nodes)

preset = nodes.ToobusyFlashVSRSettings()
assert preset.select("24GB+ fast", "2048x1152 landscape") == (1024, 576, 2, 21, 8, False, False, "fast")
assert preset.select("16GB balanced", "1152x2048 portrait") == (576, 1024, 2, 21, 8, True, False, "balanced")
assert preset.select("12GB safe", "1792x1024 landscape") == (896, 512, 2, 21, 8, True, True, "safe")

loader = nodes.ToobusyFlashVSRLoader()
handle = loader.load("dit", "projection", "prompt", False, True)[0]
assert handle.offload is True
assert handle.aggressive_offload is True
assert nodes.ToobusyFlashVSRSampler.INPUT_TYPES()["required"]["chunk_frames"][1]["min"] == 21
decoder_inputs = nodes.ToobusyFlashVSRDecoder.INPUT_TYPES()
assert decoder_inputs["optional"]["tile_preset_override"] == ("STRING", {"forceInput": True})

# runtime.py drags in torch/PIL/model code, so lift the pure helper out by AST
# instead of importing the module.
runtime_source = (ROOT / "flashvsr_node" / "backend" / "runtime.py").read_text(encoding="utf-8")
resample_fn = next(
    node
    for node in ast.parse(runtime_source).body
    if isinstance(node, ast.FunctionDef) and node.name == "resample_method"
)
resample_ns = {}
exec(compile(ast.Module(body=[resample_fn], type_ignores=[]), "<resample_method>", "exec"), resample_ns)
resample_method = resample_ns["resample_method"]

# shrinking must prefilter, enlarging must interpolate; nearest-exact does neither
assert resample_method(1280 * 720, 1024 * 576) == "area"
assert resample_method(1192 * 670, 1024 * 576) == "area"
assert resample_method(832 * 480, 1024 * 576) == "bicubic"
# equal pixel counts are a no-op resize; bicubic leaves them untouched
assert resample_method(1024 * 576, 1024 * 576) == "bicubic"
# never hand common_upscale the unfiltered path again
assert all(
    resample_method(src, dst) in ("area", "bicubic")
    for src in (399360, 589824, 921600, 2073600)
    for dst in (399360, 589824, 921600, 2073600)
)

print("FlashVSR settings tests passed")
