"""Keep the base image's shapes and shading (low frequency) and add only the detail image's fine texture (high frequency).

Result = blur(base, sigma) + highpass(detail, sigma) * strength. Strength below about 0.9 softens the image.
"""
import torch
import torch.nn.functional as F

try:
    import comfy.model_management as _mm
except Exception:  # tests / outside ComfyUI
    _mm = None


def _work_device():
    """Blurs on an 18 MP sheet take minutes on CPU and a second on GPU; images are only a few hundred MB."""
    if _mm is None:
        return torch.device("cpu")
    try:
        return _mm.get_torch_device()
    except Exception:
        return torch.device("cpu")


def _gaussian_blur(image, sigma):
    """image: [B,H,W,C] -> 같은 모양. 분리형 가우시안, reflect 패딩."""
    if sigma <= 0:
        return image
    radius = max(1, int(sigma * 3.0))
    x = torch.arange(-radius, radius + 1, dtype=image.dtype, device=image.device)
    kernel = torch.exp(-(x * x) / (2.0 * sigma * sigma))
    kernel = kernel / kernel.sum()
    channels = image.shape[-1]
    t = image.permute(0, 3, 1, 2)
    pad_h = min(radius, t.shape[2] - 1)
    pad_w = min(radius, t.shape[3] - 1)
    kh = kernel[radius - pad_w: radius + pad_w + 1].view(1, 1, 1, -1).repeat(channels, 1, 1, 1)
    kv = kernel[radius - pad_h: radius + pad_h + 1].view(1, 1, -1, 1).repeat(channels, 1, 1, 1)
    t = F.conv2d(F.pad(t, (pad_w, pad_w, 0, 0), mode="reflect"), kh, groups=channels)
    t = F.conv2d(F.pad(t, (0, 0, pad_h, pad_h), mode="reflect"), kv, groups=channels)
    return t.permute(0, 2, 3, 1)


class ToobusyFrequencyDetailTransfer:
    """base_image의 형태·음영(저주파)은 유지하고 detail_image의 미세 질감(고주파)만 입힌다."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "base_image": ("IMAGE", {"tooltip": "형태·음영을 유지할 원본"}),
                "detail_image": ("IMAGE", {"tooltip": "질감을 가져올 이미지 (예: 2BZ SeedVR2 Tile Restore 결과)"}),
                "blur_sigma": ("FLOAT", {"default": 3.0, "min": 0.5, "max": 64.0, "step": 0.5,
                                         "tooltip": "질감/형태 경계. 작을수록 모공급 미세 질감만 옮김"}),
                "detail_strength": ("FLOAT", {"default": 1.25, "min": 0.0, "max": 2.0, "step": 0.05,
                                              "tooltip": "1.0 미만이면 원본보다 뭉개짐. 캐릭터시트 검증값 1.25"}),
            },
            "optional": {
                "mask": ("MASK", {"tooltip": "흰 영역에만 적용 (피부/얼굴 등)"}),
            },
        }

    RETURN_TYPES = ("IMAGE", "IMAGE")
    RETURN_NAMES = ("image", "high_pass_preview")
    FUNCTION = "transfer"
    CATEGORY = "toobusy/retouch"

    def transfer(self, base_image, detail_image, blur_sigma, detail_strength, mask=None):
        base = base_image.float()
        detail = detail_image.float().to(base.device)
        if detail.shape[1:3] != base.shape[1:3]:
            detail = F.interpolate(detail.permute(0, 3, 1, 2), size=base.shape[1:3], mode="bicubic",
                                   align_corners=False).permute(0, 2, 3, 1)
        if detail.shape[0] != base.shape[0]:
            detail = detail[:1].expand(base.shape[0], -1, -1, -1)
        detail = detail[..., : base.shape[-1]]

        high = detail - _gaussian_blur(detail, blur_sigma)  # 음수 포함, 잘라내지 않음
        result = _gaussian_blur(base, blur_sigma) + high * detail_strength

        if mask is not None:
            m = mask.float().to(base.device)
            if m.dim() == 2:
                m = m.unsqueeze(0)
            if m.shape[1:] != base.shape[1:3]:
                m = F.interpolate(m.unsqueeze(1), size=base.shape[1:3], mode="bilinear", align_corners=False).squeeze(1)
            if m.shape[0] != base.shape[0]:
                m = m[:1].expand(base.shape[0], -1, -1)
            m = m.unsqueeze(-1)
            result = base + (result - base) * m

        preview = (high * 4.0 + 0.5).clamp(0.0, 1.0)
        return (result.clamp(0.0, 1.0), preview)


def _resize_mask(mask, height, width, batch, device):
    m = mask.float().to(device)
    if m.dim() == 2:
        m = m.unsqueeze(0)
    if m.shape[1:] != (height, width):
        m = F.interpolate(m.unsqueeze(1), size=(height, width), mode="bilinear", align_corners=False).squeeze(1)
    if m.shape[0] != batch:
        m = m[:1].expand(batch, -1, -1)
    return m.clamp(0.0, 1.0)


def _grow(mask, pixels):
    if pixels <= 0:
        return mask
    k = int(pixels) * 2 + 1
    return F.max_pool2d(mask.unsqueeze(1), kernel_size=k, stride=1, padding=int(pixels)).squeeze(1)


class ToobusyRetouchBlend:
    """Original + restored -> retouched, with a softer strength on skin.

    One node per output tier: everything gets `strength`, the masked area (skin
    from SAM3) gets `skin_strength`. The mask may be any size (detect on a small
    copy to save VRAM); it is scaled to the image, grown and feathered here.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "original": ("IMAGE", {"tooltip": "The input image. Its shapes and shading are kept."}),
                "restored": ("IMAGE", {"tooltip": "2BZ SeedVR2 Tile Restore output. Only its fine texture is used."}),
                "strength": ("FLOAT", {"default": 1.25, "min": 0.0, "max": 2.0, "step": 0.05,
                                       "tooltip": "Texture strength for hair, clothes, background. Below ~0.9 the image gets softer than the original."}),
                "skin_strength": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 2.0, "step": 0.05,
                                            "tooltip": "Texture strength inside the mask (skin). Lower if faces look older or rough."}),
                "blur_sigma": ("FLOAT", {"default": 3.0, "min": 0.5, "max": 64.0, "step": 0.5,
                                         "tooltip": "Texture / shape boundary. Smaller moves only pore-level detail."}),
                "mask_grow": ("INT", {"default": 8, "min": 0, "max": 256, "step": 1, "tooltip": "Grow the skin mask by this many pixels."}),
                "mask_feather": ("FLOAT", {"default": 8.0, "min": 0.0, "max": 128.0, "step": 0.5, "tooltip": "Soften the mask edge (gaussian sigma, pixels)."}),
            },
            "optional": {
                "skin_mask": ("MASK", {"tooltip": "White = skin (e.g. SAM3 Detect with skin:8). Without it, strength applies everywhere."}),
            },
        }

    RETURN_TYPES = ("IMAGE", "MASK")
    RETURN_NAMES = ("image", "used_mask")
    FUNCTION = "blend"
    CATEGORY = "toobusy/retouch"
    DESCRIPTION = ("Frequency-detail retouch in one node: keeps the original's shapes and shading, adds the restored "
                   "image's fine texture, softer on skin.")

    def blend(self, original, restored, strength, skin_strength, blur_sigma, mask_grow, mask_feather, skin_mask=None):
        out_device = original.device
        dev = _work_device()
        base = original[..., :3].float().to(dev)
        b, h, w, _ = base.shape
        detail = restored[..., :3].float().to(dev)
        if detail.shape[1:3] != (h, w):
            detail = F.interpolate(detail.permute(0, 3, 1, 2), size=(h, w), mode="bicubic", align_corners=False).permute(0, 2, 3, 1)
        if detail.shape[0] != b:
            detail = detail[:1].expand(b, -1, -1, -1)
        low = _gaussian_blur(base, blur_sigma)
        high = detail - _gaussian_blur(detail, blur_sigma)
        if skin_mask is None:
            m = torch.zeros((b, h, w), device=base.device)
        else:
            m = _grow(_resize_mask(skin_mask, h, w, b, base.device), mask_grow)
            if mask_feather > 0:
                m = _gaussian_blur(m.unsqueeze(-1), mask_feather).squeeze(-1)
            m = m.clamp(0.0, 1.0)
        k = strength + (skin_strength - strength) * m.unsqueeze(-1)
        return ((low + high * k).clamp(0.0, 1.0).to(out_device), m.to(out_device))


NODE_CLASS_MAPPINGS = {
    "ToobusyFrequencyDetailTransfer": ToobusyFrequencyDetailTransfer,
    "ToobusyRetouchBlend": ToobusyRetouchBlend,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "ToobusyFrequencyDetailTransfer": "2BZ Frequency Detail Transfer",
    "ToobusyRetouchBlend": "2BZ Retouch Blend (skin-aware)",
}
