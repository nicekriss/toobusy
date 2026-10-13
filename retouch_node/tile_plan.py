"""Pure-Python tile planning for the SeedVR2 tile restore node (no torch, so CI can test it).

The working image is split into tiles of about `tile_megapixels`, every tile the same
size, spread evenly so neighbours overlap by at least `overlap` pixels. A tile never
exceeds the image, and an image that already fits is one tile.
"""

import math


def work_scale(width, height, upscale_small_to_mp, max_scale=4.0):
    """How much to enlarge the input before restoring.

    SeedVR2 face texture keeps rising up to about 2-3 MP and is flat above that
    (measured 2026-10-13: 1 MP x1.52, 2 MP x1.85, 3 MP x1.97, 6 MP x2.06 of the
    original high-pass). Smaller images are enlarged to `upscale_small_to_mp`;
    larger ones are restored at their own size. 0 disables enlarging.
    """
    if upscale_small_to_mp <= 0:
        return 1.0
    pixels = float(width * height)
    target = upscale_small_to_mp * 1e6
    if pixels >= target:
        return 1.0
    return min(max_scale, math.sqrt(target / pixels))


def _count(length, tile_max, overlap):
    if tile_max >= length:
        return 1
    return math.ceil((length - overlap) / (tile_max - overlap))


def _size(length, count, overlap, multiple):
    """Smallest tile that covers `length` in `count` tiles overlapping by `overlap`."""
    if count == 1:
        return length
    size = math.ceil((length + (count - 1) * overlap) / count)
    return min(length, math.ceil(size / multiple) * multiple)


def _starts(length, tile, count):
    if count == 1 or tile >= length:
        return [0]
    return [round(i * (length - tile) / (count - 1)) for i in range(count)]


def plan_tiles(width, height, tile_megapixels, overlap, multiple=16):
    """Return [(x, y, w, h), ...] covering a width x height image.

    The tile count per axis comes from the `tile_megapixels` budget; the tile size
    is then the smallest one that covers the image with at least `overlap` pixels
    shared between neighbours, so no tile does more work than it has to. When one
    side of the image fits inside the budget, tiles take that whole side.
    """
    budget = max(0.05, float(tile_megapixels)) * 1e6
    if width * height <= budget * 1.1:
        return [(0, 0, width, height)]

    side = math.sqrt(budget)
    if width <= side:
        tw_max, th_max = width, budget / width
    elif height <= side:
        tw_max, th_max = budget / height, height
    else:
        tw_max = th_max = side
    overlap = max(0, min(int(overlap), int(tw_max) // 2, int(th_max) // 2))

    nx, ny = _count(width, tw_max, overlap), _count(height, th_max, overlap)
    tw, th = _size(width, nx, overlap, multiple), _size(height, ny, overlap, multiple)
    return [(x, y, tw, th) for y in _starts(height, th, ny) for x in _starts(width, tw, nx)]


def edge_ramps(x, y, w, h, width, height, overlap):
    """Feather widths for (left, right, top, bottom); image borders get no ramp."""
    return (
        overlap if x > 0 else 0,
        overlap if x + w < width else 0,
        overlap if y > 0 else 0,
        overlap if y + h < height else 0,
    )


def feather_width(tiles, overlap):
    """Feather no wider than the smallest overlap actually present between neighbours."""
    width = int(overlap)
    for axis, size in ((0, 2), (1, 3)):
        starts = sorted({t[axis] for t in tiles})
        span = tiles[0][size]
        for a, b in zip(starts, starts[1:]):
            width = min(width, a + span - b)
    return max(0, width)
