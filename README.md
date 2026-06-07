# toobusy

복잡한 영상 생성 워크플로우를 단순하게 만들어주는 ComfyUI 커스텀 노드 모음입니다.

현재 공개 중점 노드:

- `toobusy Keyframe Maker`
- `toobusy Prompt Lines`
- `toobusy Storyboard Board`
- `toobusy LTX2.3` 컴팩트 워크플로우 노드들
- `toobusy Z-Image Turbo`

이 외에도 몇 개의 추가/실험적 노드(Ideogram Layout Builder, Ideogram4 T2I 포함)가 함께 등록되어 있습니다 — [추가 / 실험적 노드](#추가--실험적-노드) 참고.

## 설치

이 저장소를 `ComfyUI/custom_nodes` 아래에 `toobusy`라는 이름으로 클론한 뒤 ComfyUI를 재시작하세요.

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/nicekriss/toobusy.git toobusy
```

이후 업데이트:

```bash
cd ComfyUI/custom_nodes/toobusy
git pull
```

프런트엔드(JS) 변경을 받은 뒤에는 ComfyUI를 재시작하고 브라우저를 강력 새로고침(hard refresh) 하세요.

## 활성 노드

### toobusy Keyframe Maker

카테고리:

```text
toobusy/Keyframe
```

선택적인 참조 이미지와 짧은 아이디어를 스토리보드/키프레임 텍스트 출력으로 바꿔주는 노드입니다.
제품 광고, 뮤직비디오, 단편 드라마 형식의 시퀀스에 사용할 수 있습니다.

모드:

- `Product Commercial`: 이미지를 제품 참조로 분석하여 광고 시퀀스를 구성합니다.
- `Music Video`: 이미지를 인물/비주얼 참조로 분석하여 무드 중심의 뮤직비디오 시퀀스를 구성합니다.
- `Short Drama`: 이미지를 인물/비주얼 참조로 분석하여 짧은 내러티브 시퀀스를 구성합니다.

입력:

- `clip`: 텍스트 생성이 가능한 CLIP/텍스트 인코더. 예를 들어 ComfyUI `TextGenerate`에서 쓰는 Gemma/LTX 텍스트 모델.
- `product_image` (선택): 제품·인물·비주얼 참조 이미지. 생략하면 `idea`, `style`, `fixed_elements`로부터 참조 브리프를 만듭니다.
- `mode`: 스토리보드 모드. 현재 옵션은 `Product Commercial`, `Music Video`, `Short Drama`.
- `idea`: 핵심 사건, 변화, 스토리 훅, 또는 장면 방향.
- `style`: 비주얼 톤, 카메라 스타일, 조명, 무드, 장르.
- `fixed_elements`: 모든 샷에서 일관되게 유지되어야 하는 제품/캐릭터/색상/배경 규칙.
- `shot_count`: `shot_beats_override`가 비어 있을 때 생성할 샷 개수.
- `seed`: 기본 시드. 내부 텍스트 생성 단계에서 `seed`, `seed + 1`, `seed + 2`, `seed + 3`을 사용합니다.
- `product_brief_override` (선택): 채워져 있으면 이미지/텍스트 브리프 생성을 건너뛰고 이 텍스트를 참조 브리프로 사용합니다.
- `shot_beats_override` (선택): 채워져 있으면 샷 비트 생성을 건너뜁니다.

출력:

- `product_brief`: 생성된 참조 브리프의 호환용 이름. 제품 모드가 아닐 때는 인물/비주얼 브리프입니다.
- `shot_beats`
- `keyframe_prompts`
- `korean_story`

내부 흐름:

```text
product_image + mode -> 참조 브리프
또는 idea + style + fixed + mode -> 참조 브리프
참조 브리프 + idea + style + fixed + shot_count -> 샷 비트
샷 비트 + 참조 브리프 + style + fixed -> 키프레임 프롬프트
브리프 + idea + style + 비트 + 키프레임 프롬프트 -> 한국어 스토리 설명
```

오버라이드 동작:

- `product_brief_override`가 채워져 있으면 이미지/텍스트 브리프 생성 결과는 무시됩니다.
- `shot_beats_override`가 채워져 있으면 샷 비트 생성은 무시됩니다.
- `shot_beats_override`를 사용할 때 실제 샷 개수는 `shot_count` 위젯이 아니라 오버라이드 텍스트의 비어 있지 않은 줄 수가 됩니다.

프런트엔드는 텍스트 입력 후에도 노드가 읽기 쉽도록 toobusy 색조의 입력 가이드와 요약 패널을 덧붙입니다.

### toobusy Prompt Lines

카테고리:

```text
toobusy/Text
```

여러 줄 텍스트를 한 줄씩 프롬프트 항목으로 분리합니다. 덕분에 별도의 PromptLine 류 커스텀 노드 없이도 `toobusy Keyframe Maker.keyframe_prompts`를 바로 사용할 수 있습니다.

입력:

- `source`: 분리할 여러 줄 텍스트.
- `start_index`: 사용할 첫 줄 인덱스(0부터 시작).
- `max_rows`: 출력할 최대 줄 수.
- `remove_empty_lines`: 슬라이싱 전에 빈 줄을 제거합니다.
- `strip_lines`: 각 줄의 앞뒤 공백을 제거합니다.

출력:

- `line`: 리스트 출력. 프롬프트/문자열 입력에 연결하면 선택된 각 줄마다 하위 노드를 한 번씩 실행합니다.
- `text`: 선택된 줄들을 다시 하나의 여러 줄 문자열로 합친 값.
- `count`: 선택된 비어 있지 않은 줄 수.

### toobusy Storyboard Board

카테고리:

```text
toobusy/Storyboard
```

ComfyUI 안에서 영상 아이디어, 스토리라인, 비주얼 참조, 샷 구성을 기획할 수 있는 작은 화이트보드/무드보드 노드입니다.
캔버스형 창작 워크스페이스에서 영감을 받았지만, 로컬에서 동작하며 일반적인 ComfyUI `IMAGE`로 내보냅니다.

입력:

- `board_data`: 직렬화된 보드 JSON. 프런트엔드가 이를 숨기고 인라인 보드와 동기화 상태로 유지합니다.
- `width` / `height`: 내보낼 이미지 크기.
- `background`: 보드 배경색. 예: `#f4f1e8`.

인라인 보드 기능:

- 보드가 노드 안에 바로 보입니다. 별도의 팝업 편집기가 없습니다.
- 이미지 파일을 보드 위로 바로 드래그해서 배치할 수 있습니다. 드롭한 이미지는 `board_data`에 임베드되므로 별도의 이미지 입력 슬롯이 필요 없습니다.
- 텍스트 메모, 사각형, 타원, 화살표, 자유 곡선(펜) 추가.
- 보드 위 항목을 자유롭게 선택·드래그.
- 노드를 큐에 올리면 현재 보드를 이미지로 내보냅니다.

출력:

- `image`: 렌더링된 보드 이미지.
- `board_data`: 재사용·디버깅용으로 저장된 보드 JSON.

### toobusy Z-Image Turbo

카테고리:

```text
toobusy/Z-Image
```

컴팩트한 Z-Image Turbo 텍스트→이미지 워크플로우를 하나의 노드로 묶었습니다(마지막 `SaveImage` 노드는 제외).

내부 흐름:

```text
UNETLoader + CLIPLoader + VAELoader
-> 선택적 LoraLoader 슬롯 체인
-> ModelSamplingAuraFlow
-> CLIPTextEncode positive/negative
-> EmptyLatentImage
-> KSampler
-> VAEDecode
```

주요 입력:

- `model_name`: 디퓨전 모델/UNET 파일. 예: `ZIT\zImage_turbo.safetensors`.
- `clip_name`: 텍스트 인코더 파일. 예: `ZIT\zImage_textEncoder.safetensors`.
- `vae_name`: VAE 파일. 예: `FLUX1\ae.safetensors`.
- `positive` / `negative`: 프롬프트 텍스트.
- `ratio_preset`, `megapixels`, `divisible_by`: 종횡비와 목표 메가픽셀로부터 해상도를 계산합니다.
- `seed`, `steps`, `cfg`, `sampler_name`, `scheduler`, `denoise`, `aura_shift`.
- LoRA 슬롯: 프런트엔드에 `Add LoRA slot` / `Remove LoRA slot` 버튼이 추가됩니다. 최대 5개 슬롯까지 표시할 수 있으며, 각 슬롯은 자체 활성화 토글, LoRA 파일, 강도를 가집니다.

LoRA 동작:

- ComfyUI 내장 `LoraLoader`를 사용하므로 rgthree의 Power Lora Loader가 필요 없습니다.
- 활성화된 슬롯은 슬롯 순서대로 적용됩니다.
- 비활성화된 슬롯과 `None`으로 설정된 슬롯은 건너뜁니다.

출력:

- `image`
- `latent`
- `width`
- `height`

### toobusy LTX2.3 Prompt Guide

카테고리:

```text
toobusy/LTXV
```

프롬프트/네거티브 인코딩과 LTX 프레임레이트 컨디셔닝을 하나의 노드로 묶었습니다.

출력:

- `positive`
- `negative`
- `frame_rate_int`
- `frame_rate_float`
- `length`

`length`는 `duration_seconds * frame_rate + 1`로 계산되므로 `toobusy LTX2.3 Empty AV Latents.length`에 바로 연결할 수 있습니다.

대사 길이 도우미:

- 인용된 대사는 `'...'`, `"..."`, “...”, ‘...’, 「...」, 『...』 형태로 감지합니다.
- `Suggest duration`은 대사 길이로부터 소요 시간을 추정합니다.
- `Apply recommended duration`은 추정값을 `duration_seconds`에 복사합니다.

### toobusy LTX2.3 Empty AV Latents

카테고리:

```text
toobusy/LTXV
```

`EmptyLTXVLatentVideo`와 `LTXVEmptyLatentAudio`를 하나의 노드로 결합합니다.

주요 입력:

- `audio_vae`
- `ratio_preset`
- `megapixels`
- `divisible_by`
- `length`
- `frame_rate`
- `batch_size`
- `use_custom_audio`
- 선택적 `audio`

노드는 `ratio_preset * megapixels`로부터 `width`와 `height`를 계산하고 `divisible_by`에 맞춰 반올림합니다.

`use_custom_audio`가 꺼져 있으면 `LTXVEmptyLatentAudio`로 빈 오디오 latent을 만듭니다.
`use_custom_audio`가 켜져 있으면 `audio` 입력을 연결하고 다음을 사용합니다:

```text
LTXVAudioVAEEncode -> SolidMask(0) -> SetLatentNoiseMask
```

### toobusy LTX2.3 Compact AV Sampler

카테고리:

```text
toobusy/LTXV
```

자주 쓰는 LTX2.3 AV 샘플링 블록을 하나의 노드로 묶었습니다:

```text
RandomNoise -> LTXVConcatAVLatent -> CFGGuider -> KSamplerSelect -> ManualSigmas/SIGMAS -> SamplerCustomAdvanced -> LTXVSeparateAVLatent -> LTXVCropGuides
```

입력:

- `model`
- `positive`
- `negative`
- `video_latent`
- `audio_latent`
- `seed`
- `cfg`
- `sampler_name`
- `manual_sigmas`
- 선택적 `sigmas`

`sigmas`가 연결되어 있으면 주입된 시그마 스케줄을 사용하고, 그렇지 않으면 `manual_sigmas`를 사용합니다.

노드는 샘플링 후 항상 `LTXVCropGuides`를 실행하여 latent이 이어지기 전에 가이드 프레임을 제거합니다.

## 추가 / 실험적 노드

아래 노드들도 `NODE_CLASS_MAPPINGS`를 통해 등록되어 있어 노드 메뉴에 나타나지만, 위의 핵심 노드들보다는 완성도가 낮습니다:

- `hf_model_auto_loader` — Hugging Face 모델 파일을 자동으로 찾아주거나 다운로드합니다.
- `ideogram_layout_builder` (`toobusy Ideogram Layout Builder`) — Ideogram 4
  구조화 프롬프트 JSON과 `width`/`height`를 출력하는 시각적 bbox 편집기입니다.
  캔버스에 영역을 그리고, 각 영역을 텍스트 또는 오브젝트로 지정하고, 전역/요소별
  팔레트를 설정한 뒤 그 JSON을 텍스트 인코더로 연결합니다. 요소별 **역할(role)**
  (headline / subtitle / footer / product label / sign / logo …)은 설명 힌트로
  확장되고, **레이아웃 템플릿**(poster, product ad, packaging, UI, infographic)은
  시작용 박스 세트를 깔아주며, 세 개의 토글이 출력을 제어합니다: `strict_text`
  (정확한 철자 렌더링 힌트), `reinforce_text`(`desc`에 글자 그대로를 한 번 더
  반복 — 끄면 컴팩트 JSON), `include_global_palette`(전역 팔레트를 생략해 색을
  열어둠). 편집 보조로 **레이어 리스트**(가려진 박스도 클릭해 선택 + 앞/뒤 순서
  변경 + 삭제)와 **키보드 단축키**(캔버스 포커스 상태에서 Delete/Backspace 삭제,
  방향키 이동 · Shift로 크게 이동, Esc 선택 해제)를 제공합니다.
- `ideogram4_t2i_node` (`toobusy Ideogram4 T2I`) — 프롬프트로부터 로컬 Ideogram 4
  모델(CLIP `ideogram4`, `Ideogram4Scheduler`)을 실행합니다. Layout Builder의 JSON
  프롬프트와 `width`/`height`를 그대로 받습니다.

## 로드맵

단기 계획:

1. `toobusy Keyframe Maker` 다듬기 마무리.
2. 컴팩트 Z-Image Turbo 생성 노드 다듬기.
3. ComfyUI-Manager 등록 및 공개 영상 릴리스를 위한 저장소 정비.
