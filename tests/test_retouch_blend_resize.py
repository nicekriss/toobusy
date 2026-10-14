"""2BZ Retouch Blend / Frequency Detail Transfer must shrink a larger restored image without aliasing.

A VOSR2 result is ~2.8x the original's side on a 1 MP input. Plain bicubic shrinking turned
fine stripes above the original's Nyquist limit into coarse moire, which the high-pass then
amplified (stair-stepped hair and jaw lines). With antialias the stripes average out.
"""

import importlib.util
import os

import sys

try:
    import torch
except ImportError:  # CI runs each test file as a script without torch
    if __name__ == "__main__":
        print("retouch blend resize tests skipped (torch not installed)")
        sys.exit(0)
    import pytest
    pytest.skip("torch not installed", allow_module_level=True)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("frequency_detail", os.path.join(ROOT, "retouch_node", "frequency_detail.py"))
fd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fd)


def _stripes(h, w, period):
    x = torch.arange(w).float()
    row = ((x // (period / 2)) % 2) * 0.6 + 0.2  # 0.2 / 0.8 stripes
    return row.view(1, 1, w, 1).expand(1, h, w, 3).clone()


def test_shrinking_fine_stripes_does_not_alias():
    original = torch.full((1, 120, 120, 3), 0.5)
    restored = _stripes(339, 339, 2.0)  # 2.825x larger, stripes far above the original's Nyquist limit
    out, _ = fd.ToobusyRetouchBlend().blend(original, restored, 1.6, 1.4, 3.0, 8, 8.0, None)
    # averaged stripes = flat 0.5, so the result must stay close to the flat original
    assert float((out - original).abs().max()) < 0.08


def test_frequency_transfer_shrink_does_not_alias():
    base = torch.full((1, 120, 120, 3), 0.5)
    detail = _stripes(339, 339, 2.0)
    out, _ = fd.ToobusyFrequencyDetailTransfer().transfer(base, detail, 3.0, 1.25)
    assert float((out - base).abs().max()) < 0.08


def test_same_size_and_enlarge_unchanged_path():
    original = torch.rand(1, 64, 64, 3)
    assert fd._resize_image(original, 64, 64) is original
    up = fd._resize_image(original, 128, 128)
    assert up.shape == (1, 128, 128, 3)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("retouch blend resize tests passed")
