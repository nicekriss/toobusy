# LTX2.3 Compact AV Sampler

This ComfyUI custom node package folds common LTX2.3 workflow blocks into compact nodes.

## Install

Copy this folder into:

```text
ComfyUI/custom_nodes/ltx23_compact_sampler_node
```

Then restart ComfyUI.

## Nodes

The nodes appear under:

```text
LTXV/compact
```

## LTX2.3 Empty AV Latents

Folds `EmptyLTXVLatentVideo` and `LTXVEmptyLatentAudio` into one node.

Inputs:

- `audio_vae`
- `width`
- `height`
- `duration_seconds`
- `frame_rate`
- `batch_size`
- `add_terminal_frame`
- `use_custom_audio`
- optional `audio`

Outputs:

- `video_latent`
- `audio_latent`
- `frame_count`
- `latent_frame_count`
- `frame_rate_int`
- `frame_rate_float`

`frame_count` is `duration_seconds * frame_rate`. `latent_frame_count` adds one terminal frame by default to match the common LTX setup.

When `use_custom_audio` is off, the node uses `LTXVEmptyLatentAudio`.
When `use_custom_audio` is on, connect an `audio` input and the node uses:

`LTXVAudioVAEEncode -> SolidMask(0) -> SetLatentNoiseMask`

## LTX2.3 Prompt Guide

Folds prompt/negative encoding and LTX frame-rate conditioning into one node.

Inputs:

- `clip`
- `prompt`
- `negative_prompt`
- `frame_rate`
- `duration_seconds`
- `add_terminal_frame`
- `language`

Outputs:

- `positive`
- `negative`
- `frame_rate_int`
- `frame_rate_float`
- `frame_count`
- `latent_frame_count`

## LTX2.3 Compact AV Sampler

Folds the common AV sampling block into one node:

`LTXVConcatAVLatent -> CFGGuider -> KSamplerSelect -> ManualSigmas -> SamplerCustomAdvanced -> LTXVSeparateAVLatent -> LTXVCropGuides`

Inputs:

- `model`
- `positive`
- `negative`
- `video_latent`
- `audio_latent`
- `seed`
- `cfg`
- `sampler_name`
- `manual_sigmas`
- optional `sigmas`

`manual_sigmas` is used by default. If a `SIGMAS` input is connected to the optional `sigmas` socket, the node uses that injected sigma schedule instead.

Outputs:

- `positive`
- `negative`
- `video_latent`
- `audio_latent`

The output `video_latent` is the latent returned from `LTXVCropGuides`.
