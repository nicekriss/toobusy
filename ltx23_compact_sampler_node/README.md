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

- `model`
- `positive`
- `negative`
- `latent_image`
- `seed`
- `cfg`
- `sampler_name`
- `manual_sigmas`
- optional `sigmas`

`manual_sigmas` is used by default. If a `SIGMAS` input is connected to the optional `sigmas` socket, the node uses that injected sigma schedule instead.

## Outputs

- `positive`
- `negative`
- `video_latent`
- `audio_latent`

The output layout matches the compacted block shown in the screenshot: crop-guided positive/negative/video latent outputs plus the separated audio latent.
