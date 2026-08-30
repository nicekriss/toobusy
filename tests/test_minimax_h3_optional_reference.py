import importlib.util
import os


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_module():
    path = os.path.join(ROOT, "minimax_h3_optional_reference_node", "minimax_h3_optional_reference.py")
    spec = importlib.util.spec_from_file_location("toobusy_minimax_h3_optional_reference", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_module = _load_module()


def test_disabled_reference_is_not_requested_or_forwarded():
    node = _module.ToobusyMiniMaxH3OptionalReference()
    assert node.check_lazy_status(False, "weapon", None) == []
    assert node.select(False, "weapon", object()) == (None, "")


def test_enabled_reference_requests_and_forwards_image():
    node = _module.ToobusyMiniMaxH3OptionalReference()
    image = object()
    assert node.check_lazy_status(True, " weapon ", None) == ["image"]
    assert node.select(True, " weapon ", image) == (image, "OPTIONAL REFERENCE ROLE: weapon")


def test_enabled_missing_image_does_not_emit_an_orphan_role():
    node = _module.ToobusyMiniMaxH3OptionalReference()
    assert node.select(True, "weapon", None) == (None, "")


def test_node_contract_exposes_lazy_optional_image():
    inputs = _module.ToobusyMiniMaxH3OptionalReference.INPUT_TYPES()
    assert inputs["required"]["enabled"][0] == "BOOLEAN"
    assert inputs["required"]["role"][1]["multiline"] is True
    assert inputs["optional"]["image"][1]["lazy"] is True
    assert _module.ToobusyMiniMaxH3OptionalReference.RETURN_TYPES == ("IMAGE", "STRING")


if __name__ == "__main__":
    test_disabled_reference_is_not_requested_or_forwarded()
    test_enabled_reference_requests_and_forwards_image()
    test_enabled_missing_image_does_not_emit_an_orphan_role()
    test_node_contract_exposes_lazy_optional_image()
    print("all tests passed")
