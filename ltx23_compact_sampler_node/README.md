# LTX2.3 Compact AV Sampler

This ComfyUI custom node folds the common LTX2.3 AV sampling block into one node:

`CFGGuider -> KSamplerSelect -> ManualSigmas -> SamplerCustomAdvanced -> LTXVSeparateAVLatent -> LTXVCropGuides`

## Install

Copy this folder into:

```text
ComfyUI/custom_nodes/ltx23_compact_sampler_node
```

Then restart ComfyUI.

## Node

The node appears under:

```text
LTXV/compact -> LTX2.3 Compact AV Sampler
```

## Inputs

- `noise`
- `model`
- `positive`
- `negative`
- `latent_image`
- `cfg`
- `sampler_name`
- `sigmas`

## Outputs

- `positive`
- `negative`
- `video_latent`
- `audio_latent`

The output layout matches the compacted block shown in the screenshot: crop-guided positive/negative/video latent outputs plus the separated audio latent.
