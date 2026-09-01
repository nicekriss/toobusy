import ast
import pathlib


ROOT = pathlib.Path(__file__).resolve().parents[1]
PIPELINE = ROOT / "flashvsr_node" / "backend" / "pipelines" / "flashvsr_full.py"

tree = ast.parse(PIPELINE.read_text(encoding="utf-8"))
assert not any(
    isinstance(node, ast.ImportFrom) and node.module == "diffusers"
    for node in tree.body
)
assert "AutoencoderKLWan" in {
    node.value
    for node in ast.walk(tree)
    if isinstance(node, ast.Constant) and isinstance(node.value, str)
}

requirements = (ROOT / "requirements_flashvsr.txt").read_text(encoding="utf-8").splitlines()
assert "diffusers" not in {line.strip() for line in requirements}

print("FlashVSR optional diffusers tests passed")
