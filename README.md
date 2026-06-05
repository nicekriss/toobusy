# toobusy

ComfyUI custom nodes for reducing busy video-generation workflows.

The current public focus is:

- `toobusy Keyframe Maker`
- `toobusy LTX2.3` compact workflow nodes

Experimental older nodes are kept in the repository for reference, but are not registered by default right now.

## Install

Clone this repository into `ComfyUI/custom_nodes` as `toobusy`, then restart ComfyUI.

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/nicekriss/toobusy.git toobusy
```

Update later with:

```bash
cd ComfyUI/custom_nodes/toobusy
git pull
```

After pulling frontend changes, restart ComfyUI and hard-refresh the browser.

## Active Nodes

### toobusy Keyframe Maker

Category:

```text
toobusy/Keyframe
```

This node turns a product image and a short commercial idea into storyboard/keyframe text outputs.

Inputs:

- `clip`: a text-generation capable CLIP/text encoder, for example the Gemma/LTX text model used by ComfyUI `TextGenerate`.
- `product_image`: product reference image.
- `idea`: the core commercial event or transformation.
- `style`: visual tone, camera style, lighting, mood, genre.
- `fixed_elements`: product/character/colors/background rules that should remain consistent across shots.
- `shot_count`: number of shots to generate when `shot_beats_override` is empty.
- `seed`: base seed. The node uses `seed`, `seed + 1`, `seed + 2`, and `seed + 3` across its internal text-generation stages.
- `product_brief_override` optional: if filled, image analysis is skipped and this text is used as the product brief.
- `shot_beats_override` optional: if filled, shot-beat generation is skipped.

Outputs:

- `product_brief`
- `shot_beats`
- `keyframe_prompts`
- `korean_story`

Internal flow:

```text
product_image -> product brief
product brief + idea + style + fixed + shot_count -> shot beats
shot beats + product brief + style + fixed -> keyframe prompts
brief + idea + style + beats + keyframe prompts -> Korean story explanation
```

Override behavior:

- If `product_brief_override` is filled, the product-image analysis result is ignored.
- If `shot_beats_override` is filled, shot-beat generation is ignored.
- When `shot_beats_override` is used, the effective shot count is the number of non-empty lines in the override text, not the `shot_count` widget.

The frontend adds field namecards and an input summary panel so the node remains readable after text is entered.

### toobusy LTX2.3 Prompt Guide

Category:

```text
toobusy/LTXV
```

Folds prompt/negative encoding and LTX frame-rate conditioning into one node.

Outputs:

- `positive`
- `negative`
- `frame_rate_int`
- `frame_rate_float`
- `length`

`length` is calculated from `duration_seconds * frame_rate + 1`, so it can be connected directly to `toobusy LTX2.3 Empty AV Latents.length`.

Dialogue duration helper:

- Quoted dialogue is detected with `'...'`, `"..."`, `“...”`, `‘...’`, `「...」`, and `『...』`.
- `Suggest duration` estimates duration from dialogue length.
- `Apply recommended duration` copies the estimate into `duration_seconds`.

### toobusy LTX2.3 Empty AV Latents

Category:

```text
toobusy/LTXV
```

Combines `EmptyLTXVLatentVideo` and `LTXVEmptyLatentAudio` into one node.

Inputs include:

- `audio_vae`
- `ratio_preset`
- `megapixels`
- `divisible_by`
- `length`
- `frame_rate`
- `batch_size`
- `use_custom_audio`
- optional `audio`

The node calculates `width` and `height` from `ratio_preset * megapixels`, rounded to `divisible_by`.

When `use_custom_audio` is off, it creates empty audio latent with `LTXVEmptyLatentAudio`.
When `use_custom_audio` is on, connect an `audio` input and it uses:

```text
LTXVAudioVAEEncode -> SolidMask(0) -> SetLatentNoiseMask
```

### toobusy LTX2.3 Compact AV Sampler

Category:

```text
toobusy/LTXV
```

Folds the common LTX2.3 AV sampling block into one node:

```text
RandomNoise -> LTXVConcatAVLatent -> CFGGuider -> KSamplerSelect -> ManualSigmas/SIGMAS -> SamplerCustomAdvanced -> LTXVSeparateAVLatent -> LTXVCropGuides
```

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

If `sigmas` is connected, the node uses that injected sigma schedule. Otherwise it uses `manual_sigmas`.

The node always runs `LTXVCropGuides` after sampling so guide frames are removed before the latent continues.

## Hidden Experimental Nodes

These folders are currently kept in the repository but are not exposed through `NODE_CLASS_MAPPINGS`:

- `hf_model_auto_loader`
- `ideogram_layout_builder`

They may come back later, but they are hidden for now to keep the public node list focused.

## Roadmap

Near-term plan:

1. Finish `toobusy Keyframe Maker` polish.
2. Add a compact Z-Image Turbo generation node.
3. Prepare the repository for ComfyUI-Manager registration and public video release.
