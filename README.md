# toobusy

ComfyUI custom nodes for reducing busy video-generation workflows.

The current public focus is:

- `toobusy Keyframe Maker`
- `toobusy Prompt Lines`
- `toobusy Storyboard Board`
- `toobusy LTX2.3` compact workflow nodes
- `toobusy Z-Image Turbo`

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

This node turns an optional reference image and a short idea into storyboard/keyframe text outputs.
It can be used for product commercials, music videos, and short drama-style sequences.

Modes:

- `Product Commercial`: analyzes the image as a product reference and plans a commercial sequence.
- `Music Video`: analyzes the image as a subject/visual reference and plans a mood-driven music-video sequence.
- `Short Drama`: analyzes the image as a subject/visual reference and plans a short narrative sequence.

Inputs:

- `clip`: a text-generation capable CLIP/text encoder, for example the Gemma/LTX text model used by ComfyUI `TextGenerate`.
- `product_image` optional: product, subject, or visual reference image. If omitted, the node builds a reference brief from `idea`, `style`, and `fixed_elements`.
- `mode`: storyboard mode. Current options are `Product Commercial`, `Music Video`, and `Short Drama`.
- `idea`: the core event, transformation, story hook, or scene direction.
- `style`: visual tone, camera style, lighting, mood, genre.
- `fixed_elements`: product/character/colors/background rules that should remain consistent across shots.
- `shot_count`: number of shots to generate when `shot_beats_override` is empty.
- `seed`: base seed. The node uses `seed`, `seed + 1`, `seed + 2`, and `seed + 3` across its internal text-generation stages.
- `product_brief_override` optional: if filled, image/text brief generation is skipped and this text is used as the reference brief.
- `shot_beats_override` optional: if filled, shot-beat generation is skipped.

Outputs:

- `product_brief`: compatibility name for the generated reference brief. In non-product modes this is a subject/visual brief.
- `shot_beats`
- `keyframe_prompts`
- `korean_story`

Internal flow:

```text
product_image + mode -> reference brief
or idea + style + fixed + mode -> reference brief
reference brief + idea + style + fixed + shot_count -> shot beats
shot beats + reference brief + style + fixed -> keyframe prompts
brief + idea + style + beats + keyframe prompts -> Korean story explanation
```

Override behavior:

- If `product_brief_override` is filled, the image/text brief generation result is ignored.
- If `shot_beats_override` is filled, shot-beat generation is ignored.
- When `shot_beats_override` is used, the effective shot count is the number of non-empty lines in the override text, not the `shot_count` widget.

The frontend adds a small toobusy-tinted input guide and summary panel so the node remains readable after text is entered.

### toobusy Prompt Lines

Category:

```text
toobusy/Text
```

Splits multiline text into line-by-line prompt items, so `toobusy Keyframe Maker.keyframe_prompts` can be used without another custom PromptLine-style node.

Inputs:

- `source`: multiline text to split.
- `start_index`: first line index to use, zero-based.
- `max_rows`: maximum number of lines to output.
- `remove_empty_lines`: removes blank lines before slicing.
- `strip_lines`: trims whitespace from each line.

Outputs:

- `line`: list output. Connect this to a prompt/string input to run downstream nodes once per selected line.
- `text`: selected lines joined back into one multiline string.
- `count`: number of selected non-empty lines.

### toobusy Storyboard Board

Category:

```text
toobusy/Storyboard
```

A small whiteboard/moodboard node for planning video ideas, storylines, visual references, and shot structure inside ComfyUI.
It is inspired by canvas-style creative workspaces, but it stays local and exports a normal ComfyUI `IMAGE`.

Inputs:

- `board_data`: serialized board JSON. The frontend hides this and edits it through the board editor.
- `width` / `height`: exported image size.
- `background`: board background color, for example `#f4f1e8`.
- `image_1` to `image_6` optional: connect images here, then place matching image slots in the board editor.

Editor features:

- `Open board editor` opens the canvas editor.
- Add text notes, image slots, rectangles, ellipses, arrows, and freehand pen strokes.
- Select and drag items freely on the board.
- Image slot items render from the matching `image_1` through `image_6` inputs.
- `Apply` saves the board back into the node, and queueing the node exports the board as an image.

Outputs:

- `image`: rendered board image.
- `board_data`: saved board JSON for reuse or debugging.

### toobusy Z-Image Turbo

Category:

```text
toobusy/Z-Image
```

Folds a compact Z-Image Turbo text-to-image workflow into one node, without the final `SaveImage` node.

Internal flow:

```text
UNETLoader + CLIPLoader + VAELoader
-> optional LoraLoader slot chain
-> ModelSamplingAuraFlow
-> CLIPTextEncode positive/negative
-> EmptyLatentImage
-> KSampler
-> VAEDecode
```

Inputs include:

- `model_name`: diffusion model/UNET file, for example `ZIT\zImage_turbo.safetensors`.
- `clip_name`: text encoder file, for example `ZIT\zImage_textEncoder.safetensors`.
- `vae_name`: VAE file, for example `FLUX1\ae.safetensors`.
- `positive` / `negative`: prompt text.
- `ratio_preset`, `megapixels`, `divisible_by`: resolution is calculated from aspect ratio and target megapixels.
- `seed`, `steps`, `cfg`, `sampler_name`, `scheduler`, `denoise`, `aura_shift`.
- LoRA slots: the frontend adds `Add LoRA slot` and `Remove LoRA slot` buttons. Up to 5 LoRA slots can be shown, and each slot has its own enable toggle, LoRA file, and strength.

LoRA behavior:

- Uses ComfyUI's built-in `LoraLoader`, so the rgthree Power Lora Loader is not required.
- Enabled slots are applied in slot order.
- Disabled slots and slots set to `None` are skipped.

Outputs:

- `image`
- `latent`
- `width`
- `height`

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
2. Polish the compact Z-Image Turbo generation node.
3. Prepare the repository for ComfyUI-Manager registration and public video release.
