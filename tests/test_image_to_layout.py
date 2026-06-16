"""Regression tests for toobusy Image -> Ideogram Layout.

Covers the pure draft-building logic that must never drift:

  * INPUT_TYPES exposing the FL2MODEL input and the analysis modes;
  * Florence2Run region parsing across the shapes its `data` output can take
    (bboxes/labels dict, list-of-entries, quad_boxes);
  * pixel/normalized bbox -> Ideogram 0..1000 [y_min,x_min,y_max,x_max];
  * obj/text element typing, max_elements cap, tiny-text simplify;
  * the clear "install ComfyUI-Florence2" error when the node is missing.

Standalone- and pytest-runnable, no ComfyUI runtime. Florence2Run is mocked.
"""

import importlib.util
import json
import os
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _install_stubs():
    pkg = types.ModuleType("toobusy")
    pkg.__path__ = [ROOT]
    sys.modules["toobusy"] = pkg

    # ltx module: only _call_node is imported by the node under test; stub it so
    # tests can swap it for a fake Florence2Run.
    ltx_pkg = types.ModuleType("toobusy.ltx23_compact_sampler_node")
    ltx_pkg.__path__ = [os.path.join(ROOT, "ltx23_compact_sampler_node")]
    sys.modules["toobusy.ltx23_compact_sampler_node"] = ltx_pkg
    ltx_mod = types.ModuleType("toobusy.ltx23_compact_sampler_node.ltx23_compact_sampler")
    ltx_mod._call_node = lambda *a, **k: ()
    sys.modules["toobusy.ltx23_compact_sampler_node.ltx23_compact_sampler"] = ltx_mod

    # ideogram_layout_builder.nodes has no ComfyUI deps; load the real thing so
    # the bbox/clamp/palette helpers are exercised for real.
    ib_pkg = types.ModuleType("toobusy.ideogram_layout_builder")
    ib_pkg.__path__ = [os.path.join(ROOT, "ideogram_layout_builder")]
    sys.modules["toobusy.ideogram_layout_builder"] = ib_pkg
    _load(
        "toobusy.ideogram_layout_builder.nodes",
        os.path.join("ideogram_layout_builder", "nodes.py"),
    )


def _load(modname, relpath):
    path = os.path.join(ROOT, relpath)
    spec = importlib.util.spec_from_file_location(modname, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[modname] = module
    spec.loader.exec_module(module)
    return module


_install_stubs()
_mod = _load(
    "toobusy.image_to_layout_node.image_to_layout",
    os.path.join("image_to_layout_node", "image_to_layout.py"),
)


class _FakeImage:
    """IMAGE tensor stand-in: shape [1, H, W, 3]. Square so pixel==normalized*1000
    math is easy to assert."""

    def __init__(self, side=1000):
        self.side = side

    @property
    def shape(self):
        return (1, self.side, self.side, 3)

    def __getitem__(self, item):
        raise TypeError("no real pixels")  # palette extraction falls back to []


def _fake_florence(responses):
    """Build a fake _call_node that returns (image, mask, caption, data) per task."""

    def call(class_name, **kwargs):
        assert class_name == "Florence2Run"
        task = kwargs["task"]
        caption, data = responses.get(task, ("", None))
        return (kwargs["image"], None, caption, data)

    return call


def _run(responses, **overrides):
    _mod._call_node = _fake_florence(responses)
    kwargs = dict(
        image=_FakeImage(),
        florence2_model="fl2",
        analysis_mode="Full Setup",
        caption_detail="more_detailed_caption",
        max_elements=12,
        include_ocr_text=True,
        include_color_palette=True,
        simplify_small_text=True,
    )
    kwargs.update(overrides)
    json_str, hld, background, palette, width, height = _mod.ToobusyImageToIdeogramLayout().analyze(**kwargs)
    return json.loads(json_str), hld, background, palette, width, height


# --- INPUT_TYPES -------------------------------------------------------------

def test_input_types_exposes_florence_model_and_modes():
    required = _mod.ToobusyImageToIdeogramLayout.INPUT_TYPES()["required"]
    assert required["image"][0] == "IMAGE"
    assert required["florence2_model"][0] == "FL2MODEL"
    assert required["analysis_mode"][0][0] == "Full Setup"


def test_outputs_are_ideogram_json_plus_fields():
    cls = _mod.ToobusyImageToIdeogramLayout
    assert cls.RETURN_NAMES == ("ideogram_json", "high_level_description", "background", "color_palette", "width", "height")


# --- region parsing / bbox ---------------------------------------------------

def test_caption_to_phrase_grounding_becomes_obj_elements_in_ideogram_bbox():
    payload, hld, _bg, _pal, w, h = _run({
        "more_detailed_caption": ("A bold poster with a person and a headline.", None),
        "caption_to_phrase_grounding": ("", {"bboxes": [[100, 50, 850, 480]], "labels": ["a surprised person"]}),
    })
    assert hld.startswith("A bold poster")
    elements = payload["compositional_deconstruction"]["elements"]
    assert len(elements) == 1
    el = elements[0]
    assert el["type"] == "obj" and el["desc"] == "a surprised person"
    # canvas [x_min,y_min,x_max,y_max]=[100,50,850,480] (square 1000) ->
    # ideogram [y_min,x_min,y_max,x_max].
    assert el["bbox"] == [50, 100, 480, 850]


def test_ocr_with_region_becomes_text_elements():
    payload, *_ = _run({
        "caption_to_phrase_grounding": ("", {"bboxes": [], "labels": []}),
        "ocr_with_region": ("", {"bboxes": [[120, 520, 360, 950]], "labels": ["HEADLINE"]}),
    })
    text = [el for el in payload["compositional_deconstruction"]["elements"] if el["type"] == "text"]
    assert len(text) == 1 and text[0]["text"] == "HEADLINE"
    assert text[0]["bbox"] == [520, 120, 950, 360]


def test_quad_boxes_are_reduced_to_extent():
    payload, *_ = _run({
        "ocr_with_region": ("", {"quad_boxes": [[120, 520, 360, 520, 360, 950, 120, 950]], "labels": ["X"]}),
        "caption_to_phrase_grounding": ("", None),
    })
    text = [el for el in payload["compositional_deconstruction"]["elements"] if el["type"] == "text"]
    assert text and text[0]["bbox"] == [520, 120, 950, 360]


def test_list_of_entries_shape_is_parsed():
    payload, *_ = _run({
        "caption_to_phrase_grounding": ("", [{"bbox": [10, 10, 500, 500], "label": "thing"}]),
    }, include_ocr_text=False)
    objs = [el for el in payload["compositional_deconstruction"]["elements"] if el["type"] == "obj"]
    assert objs and objs[0]["desc"] == "thing"


def test_normalized_ocr_coords_scale_to_thousand():
    # ocr_with_region often returns 0..1 normalized boxes.
    payload, *_ = _run({
        "ocr_with_region": ("", [{"box": [0.1, 0.2, 0.4, 0.6], "label": "T"}]),
        "caption_to_phrase_grounding": ("", None),
    })
    text = [el for el in payload["compositional_deconstruction"]["elements"] if el["type"] == "text"]
    assert text and text[0]["bbox"] == [200, 100, 600, 400]


def test_bare_box_list_is_parsed_as_objects():
    # dense_region_caption's data output is a bare list of [x1,y1,x2,y2] boxes
    # (no labels). _iter_regions must still yield boxes.
    regions = list(_mod._iter_regions([[10, 10, 500, 500], [0, 0, 200, 200]]))
    assert [box for box, _ in regions] == [[10, 10, 500, 500], [0, 0, 200, 200]]
    assert all(label == "" for _, label in regions)
    # also the one-item-per-image wrapping: [[box, box]]
    wrapped = list(_mod._iter_regions([[[10, 10, 500, 500]]]))
    assert wrapped and wrapped[0][0] == [10, 10, 500, 500]


def test_task_token_keyed_wrapper_is_parsed():
    data = {"<CAPTION_TO_PHRASE_GROUNDING>": {"bboxes": [[1, 2, 3, 4]], "labels": ["cat"]}}
    regions = list(_mod._iter_regions(data))
    assert regions == [([1, 2, 3, 4], "cat")]


def test_special_tokens_stripped_from_labels():
    assert _mod._clean_text("</s>person<pad>") == "person"
    assert _mod._clean_text("<s>a man</s>") == "a man"
    payload, *_ = _run({
        "more_detailed_caption": ("A man.", None),
        "caption_to_phrase_grounding": ("", {"bboxes": [[0, 0, 500, 500]], "labels": ["</s>a man"]}),
    }, include_ocr_text=False)
    objs = payload["compositional_deconstruction"]["elements"]
    assert objs[0]["desc"] == "a man"


# --- options -----------------------------------------------------------------

def test_max_elements_caps_and_keeps_largest():
    boxes = [[0, 0, 100, 100], [0, 0, 900, 900], [0, 0, 300, 300]]
    payload, *_ = _run({
        "caption_to_phrase_grounding": ("", {"bboxes": boxes, "labels": ["small", "big", "mid"]}),
    }, max_elements=2, include_ocr_text=False)
    descs = {el["desc"] for el in payload["compositional_deconstruction"]["elements"]}
    assert descs == {"big", "mid"}  # the two largest survive


def test_simplify_small_text_drops_tiny_ocr():
    payload, *_ = _run({
        "caption_to_phrase_grounding": ("", None),
        "ocr_with_region": ("", {"bboxes": [[0, 0, 10, 10]], "labels": ["©"]}),
    }, simplify_small_text=True)
    assert all(el["type"] != "text" for el in payload["compositional_deconstruction"]["elements"])


def test_empty_analysis_falls_back_to_one_obj():
    payload, hld, *_ = _run({"more_detailed_caption": ("Just a scene.", None)})
    elements = payload["compositional_deconstruction"]["elements"]
    assert len(elements) == 1 and elements[0]["type"] == "obj"


def test_medium_option_sets_style_and_photo_exclusivity():
    photo, *_ = _run({"more_detailed_caption": ("A snowy scene.", None)}, medium="photograph")
    assert photo["style_description"]["medium"] == "photograph"
    assert photo["style_description"]["photo"]  # photo filled for photographs
    graphic, *_ = _run({"more_detailed_caption": ("A thumbnail.", None)}, medium="graphic_design")
    assert graphic["style_description"]["medium"] == "graphic_design"
    assert graphic["style_description"]["photo"] == ""  # no photo for graphics


# --- error path --------------------------------------------------------------

def test_missing_florence_node_gives_clear_error():
    def boom(class_name, **kwargs):
        raise RuntimeError("Required ComfyUI core node 'Florence2Run' is not available.")

    _mod._call_node = boom
    try:
        _mod.ToobusyImageToIdeogramLayout().analyze(image=_FakeImage(), florence2_model="x")
    except RuntimeError as exc:
        assert "ComfyUI-Florence2" in str(exc)
    else:
        raise AssertionError("expected RuntimeError when Florence2Run is missing")


# --- palette extraction (torch only) -----------------------------------------

def test_palette_extracts_dominant_hex_from_tensor():
    try:
        import torch
    except ImportError:
        print("SKIP test_palette_extracts_dominant_hex_from_tensor (no torch)")
        return
    # A frame that is mostly pure red with a smaller blue patch.
    frame = torch.zeros(1, 20, 20, 3)
    frame[..., 0] = 1.0  # red everywhere
    frame[:, :, :5, 0] = 0.0
    frame[:, :, :5, 2] = 1.0  # left quarter is blue
    palette = _mod._extract_palette(frame, 8)
    assert palette, "expected at least one color"
    # 255 quantizes to bucket 240 (0xF0), 0 -> 16 (0x10).
    assert palette[0] == "#F01010", f"dominant should be red-ish, got {palette[0]}"
    assert any(c == "#1010F0" for c in palette), "blue patch should appear"


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except AssertionError as exc:
                failures += 1
                print(f"FAIL {name}: {exc}")
    if failures:
        print(f"\n{failures} test(s) failed")
        sys.exit(1)
    print("\nall tests passed")
