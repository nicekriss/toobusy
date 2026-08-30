import importlib.util
import os


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_module():
    path = os.path.join(ROOT, "minimax_h3_semantic_reference_node", "minimax_h3_semantic_reference.py")
    spec = importlib.util.spec_from_file_location("toobusy_minimax_h3_semantic_reference", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_module = _load_module()


def test_auto_mode_forwards_safe_visual_reference_and_description():
    node = _module.ToobusyMiniMaxH3SemanticReference()
    image = object()
    analysis = "VISUAL_REFERENCE: YES\nSEMANTIC_DESCRIPTION: isolated oval ruby"
    assert node.check_lazy_status(True, "auto", "PROP", analysis, None) == ["image"]
    assert node.select(True, "auto", "PROP", analysis, image) == (image, "PROP: isolated oval ruby")


def test_auto_mode_blocks_unsafe_visual_reference_but_keeps_semantics():
    node = _module.ToobusyMiniMaxH3SemanticReference()
    image = object()
    analysis = "VISUAL_REFERENCE: NO\nSEMANTIC_DESCRIPTION: tan explorer outfit"
    assert node.check_lazy_status(True, "auto", "", analysis, None) == []
    assert node.select(True, "auto", "", analysis, image) == (None, "tan explorer outfit")


def test_disabled_reference_is_fully_lazy():
    node = _module.ToobusyMiniMaxH3SemanticReference()
    assert node.check_lazy_status(False, "auto", "PROP", None, None) == []
    assert node.select(False, "auto", "PROP", None, object()) == (None, "")


def test_semantic_only_never_requests_or_forwards_image():
    node = _module.ToobusyMiniMaxH3SemanticReference()
    analysis = "VISUAL_REFERENCE: YES\nSEMANTIC_DESCRIPTION: crouched firing stance"
    assert node.check_lazy_status(True, "semantic_only", "", analysis, None) == []
    assert node.select(True, "semantic_only", "", analysis, object()) == (None, "crouched firing stance")


def test_malformed_classifier_output_fails_closed():
    node = _module.ToobusyMiniMaxH3SemanticReference()
    assert node.select(True, "auto", "", "khaki field jacket", object()) == (None, "khaki field jacket")


def test_manifest_compacts_picture_numbers_around_blocked_and_disabled_references():
    node = _module.ToobusyMiniMaxH3ReferenceManifest()
    outfit = "VISUAL_REFERENCE: NO\nSEMANTIC_DESCRIPTION: illustrated explorer outfit"
    pose = "VISUAL_REFERENCE: NO\nSEMANTIC_DESCRIPTION: low retreat stance"
    prop = "VISUAL_REFERENCE: YES\nSEMANTIC_DESCRIPTION: isolated oval ruby"
    result = node.build(True, False, False, outfit, pose, prop, None, None)[0]
    assert "<Picture 2> supplies only the optional reference role 4" in result
    assert "<Picture 3>" not in result
    assert "illustrated explorer outfit" in result


def test_manifest_is_lazy_for_disabled_optional_references():
    node = _module.ToobusyMiniMaxH3ReferenceManifest()
    assert node.check_lazy_status(False, False, False, "outfit", "pose", None, None, None) == []


if __name__ == "__main__":
    test_auto_mode_forwards_safe_visual_reference_and_description()
    test_auto_mode_blocks_unsafe_visual_reference_but_keeps_semantics()
    test_disabled_reference_is_fully_lazy()
    test_semantic_only_never_requests_or_forwards_image()
    test_malformed_classifier_output_fails_closed()
    test_manifest_compacts_picture_numbers_around_blocked_and_disabled_references()
    test_manifest_is_lazy_for_disabled_optional_references()
    print("all tests passed")
