# LTX2.3 Compact AV Sampler

This ComfyUI custom node folds the common LTX2.3 AV sampling block into one node:

`LTXVConcatAVLatent -> CFGGuider -> KSamplerSelect -> ManualSigmas -> SamplerCustomAdvanced -> LTXVSeparateAVLatent -> LTXVCropGuides`

## Install

Copy this folder into:

```text
ComfyUI/custom_nodes/ltx23_compact_sampler_node
```

Then restart ComfyUI.

## Node

The nodes appear under:

```text
toobusy/LTXV
```

## toobusy LTX2.3 Empty AV Latents

Folds `EmptyLTXVLatentVideo` and `LTXVEmptyLatentAudio` into one node.

Inputs:

- `audio_vae`
- `ratio_preset`
- `megapixels`
- `divisible_by`
- `length`
- `frame_rate`
- `batch_size`
- `use_custom_audio`
- optional `audio`

Outputs:

- `video_latent`
- `audio_latent`
- `length`
- `frame_rate_int`
- `frame_rate_float`
- `width`
- `height`

The node calculates `width` and `height` from `ratio_preset * megapixels`, rounded to `divisible_by`. `length` is passed to both `EmptyLTXVLatentVideo.length` and `LTXVEmptyLatentAudio.frames_number`.

When `use_custom_audio` is off, the node uses `LTXVEmptyLatentAudio`.
When `use_custom_audio` is on, connect an `audio` input and the node uses:

`LTXVAudioVAEEncode -> SolidMask(0) -> SetLatentNoiseMask`

## toobusy LTX2.3 Prompt Guide

Folds prompt/negative encoding and LTX frame-rate conditioning into one node.

Inputs:

- `clip`
- `prompt`
- `negative_prompt`
- `frame_rate`
- `duration_seconds`
- `language`

Outputs:

- `positive`
- `negative`
- `frame_rate_int`
- `frame_rate_float`
- `length`

`length` is calculated from `duration_seconds * frame_rate + 1` so it can be connected directly to `toobusy LTX2.3 Empty AV Latents.length`. `language` is used for dialogue-duration estimation. If the prompt contains quoted dialogue, the node displays a recommended minimum duration from the dialogue length. `Auto` switches between Korean and English heuristics based on the quoted text.

## toobusy LTX2.3 Compact AV Sampler

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

## LTXVCropGuides behavior

The node always runs `LTXVCropGuides` after `LTXVSeparateAVLatent`.

In LTX guide/keyframe workflows, guide frames are appended to the video latent and tracked through conditioning. `LTXVCropGuides` removes those guide frames and clears the keyframe indices before the latent continues to the next stage. If there are no guide keyframes, ComfyUI's `LTXVCropGuides` passes the latent and conditioning through unchanged.

## Outputs

- `positive`
- `negative`
- `video_latent`
- `audio_latent`

The output layout matches the compacted block shown in the screenshot: crop-guided positive/negative/video latent outputs plus the separated audio latent.
