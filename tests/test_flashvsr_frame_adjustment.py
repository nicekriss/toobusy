import ast
import pathlib


ROOT = pathlib.Path(__file__).resolve().parents[1]
UTILS = ROOT / "flashvsr_node" / "backend" / "examples" / "WanVSR" / "utils" / "utils.py"

tree = ast.parse(UTILS.read_text(encoding="utf-8"))
adjust = next(
    node
    for node in tree.body
    if isinstance(node, ast.FunctionDef) and node.name == "calculate_frame_adjustment_simple"
)
input_frames = next(
    node
    for node in adjust.body
    if isinstance(node, ast.Assign) and ast.unparse(node.targets[0]) == "input_frames"
)
assert ast.unparse(input_frames.value) == "max(original_frames, 21)"

assignments = {
    ast.unparse(node.targets[0]): ast.unparse(node.value)
    for node in adjust.body
    if isinstance(node, ast.Assign)
}
assert assignments["frames_to_add"] == "input_frames + 4 - original_frames"
assert assignments["frames_to_remove"] == "output_frames - original_frames"

print("FlashVSR frame adjustment tests passed")
