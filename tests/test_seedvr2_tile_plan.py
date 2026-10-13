"""Tile planning for 2BZ SeedVR2 Tile Restore (pure Python, no ComfyUI runtime).

Guarantees: tiles cover every pixel, stay inside the image, all share one size,
neighbours overlap by at least the requested amount, small images are one tile,
and small images are enlarged only up to the quality target.
"""

import importlib.util
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("tile_plan", os.path.join(ROOT, "retouch_node", "tile_plan.py"))
tp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tp)


def _check(width, height, mp, overlap):
    tiles = tp.plan_tiles(width, height, mp, overlap)
    covered = [[0] * width for _ in range(1)]  # columns only, rows checked separately
    sizes = {(w, h) for _, _, w, h in tiles}
    assert len(sizes) == 1, sizes
    for x, y, w, h in tiles:
        assert x >= 0 and y >= 0 and x + w <= width and y + h <= height, (x, y, w, h, width, height)
    xs = sorted({x for x, _, _, _ in tiles})
    ys = sorted({y for _, y, _, _ in tiles})
    tw, th = next(iter(sizes))
    assert xs[0] == 0 and xs[-1] + tw == width
    assert ys[0] == 0 and ys[-1] + th == height
    if len(tiles) > 1:
        assert tw * th <= mp * 1e6 * 1.1, (tw, th, mp)
    for a, b in zip(xs, xs[1:]):
        assert a + tw - b >= min(overlap, tw // 2), ("x overlap", a, b, tw)
    for a, b in zip(ys, ys[1:]):
        assert a + th - b >= min(overlap, th // 2), ("y overlap", a, b, th)
    del covered
    return tiles


def test_small_image_is_one_tile():
    assert tp.plan_tiles(1024, 1024, 2.0, 128) == [(0, 0, 1024, 1024)]


def test_sheet_is_tiled():
    tiles = _check(5760, 3240, 2.0, 128)
    assert len(tiles) >= 9


def test_odd_sizes_and_budgets():
    for w, h in ((2880, 2880), (960, 2880), (4097, 1033), (1888, 1056), (7000, 900)):
        for mp in (0.5, 1.0, 2.0, 3.0, 4.0):
            for ov in (32, 128, 256):
                _check(w, h, mp, ov)


def test_work_scale():
    assert tp.work_scale(4000, 3000, 3.0) == 1.0
    s = tp.work_scale(1000, 1000, 3.0)
    assert abs(1000 * 1000 * s * s - 3e6) < 1e3
    assert tp.work_scale(100, 100, 3.0) == 4.0  # capped
    assert tp.work_scale(1000, 1000, 0.0) == 1.0


def test_no_wasted_overlap():
    # 1732x1732 at 2 MP used to get four 1408x1408 tiles; now the smallest covering tiles.
    tiles = tp.plan_tiles(1732, 1732, 2.0, 128)
    assert len(tiles) == 4 and tiles[0][2] <= 944, tiles
    for w, h, mp in ((5760, 3240, 2.0), (1732, 1732, 2.0), (2880, 2880, 3.0)):
        t = tp.plan_tiles(w, h, mp, 128)
        assert tp.feather_width(t, 128) == 128 or len(t) == 1


def test_edge_ramps():
    assert tp.edge_ramps(0, 0, 100, 100, 100, 100, 32) == (0, 0, 0, 0)
    assert tp.edge_ramps(50, 0, 100, 100, 200, 100, 32) == (32, 32, 0, 0)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("SeedVR2 tile plan tests passed")
