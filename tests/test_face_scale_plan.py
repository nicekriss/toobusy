"""2BZ Face-Size Scale Plan (pure Python, no torch / ComfyUI).

Cases come from the 2026-10-15 test images (SAM3 'face' box widths in original pixels).
"""

import importlib.util
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("face_scale", os.path.join(ROOT, "retouch_node", "face_scale.py"))
fs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fs)


def box(w, x=0, y=0):
    return {"x": x, "y": y, "width": w, "height": w * 1.2}


def test_full_body_1mp_goes_x2():
    # Klein full body 832x1232, face 98 px -> about x2 (the "looks great" case, face ~200 px)
    p = fs.plan_face_scale(832, 1232, [[box(98)]])
    assert 2.0 <= p["scale"] <= 2.1
    assert p["upscale"] == 2  # 2.04 needed: VOSR2 x2 then a 2% resize, not x3
    assert p["width"] % 16 == 0 and p["height"] % 16 == 0


def test_boxes_from_a_smaller_detect_image_are_mapped_back():
    # detector saw a 1190-wide copy of a 3328-wide image; box 142 px there = 397 px in the original
    p = fs.plan_face_scale(3328, 4928, [[box(142)]], detect_width=1190)
    assert p["face_px"] in (397, 398)
    assert p["scale"] == 1.0  # face already bigger than the target -> keep size


def test_close_up_keeps_exact_size_and_skips_upscaler():
    p = fs.plan_face_scale(954, 1194, [[box(728)]])
    assert p["scale"] == 1.0 and (p["width"], p["height"]) == (954, 1194)
    assert p["needs_upscale"] is False
    sheet = fs.plan_face_scale(5760, 3240, [[box(844)]])
    assert (sheet["width"], sheet["height"]) == (5760, 3240) and not sheet["needs_upscale"]
    q = fs.plan_face_scale(954, 1194, [[box(728)]], shrink_large_faces=True)
    assert q["scale"] < 0.3


def test_group_shot_uses_largest_face_by_default():
    faces = [[box(113), box(99), box(89), box(58), box(53), box(38)]]
    p = fs.plan_face_scale(1448, 1086, faces)
    assert p["face_px"] == 113 and abs(p["scale"] - 200 / 113) < 0.01
    q = fs.plan_face_scale(1448, 1086, faces, pick="smallest")
    assert q["scale"] == 4.0  # capped


def test_no_face_falls_back_to_megapixels():
    p = fs.plan_face_scale(1024, 1024, [[]], no_face_megapixels=4.0)
    assert p["faces"] == 0 and abs(p["scale"] - 1.953) < 0.01
    big = fs.plan_face_scale(4096, 4096, None, no_face_megapixels=4.0)
    assert big["scale"] == 1.0


def test_upscale_factor_is_whole_and_at_least_two():
    for face, want in ((150, 2), (98, 2), (80, 3), (40, 4), (500, 2)):
        assert fs.plan_face_scale(1000, 1000, [[box(face)]])["upscale"] == want


def test_lazy_pick_asks_only_for_the_branch_it_uses():
    node = fs.ToobusyUseUpscaledIfNeeded()
    assert node.check_lazy_status(True, None, None) == ["upscaled"]
    assert node.check_lazy_status(False, None, None) == ["original"]
    assert node.pick(True, "U", None) == ("U",) and node.pick(False, None, "O") == ("O",)
    assert fs.plan_face_scale(832, 1232, [[box(98)]])["needs_upscale"] is True


def test_json_string_boxes():
    p = fs.plan_face_scale(1000, 1000, '[[{"x": 1, "y": 2, "width": 100, "height": 120}]]')
    assert p["face_px"] == 100 and p["scale"] == 2.0


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("face scale plan tests passed")
