# toobusy · 너무바쁜베짱이

**번거로운 여러 단계를 노드 하나로 접어버리는** ComfyUI 커스텀 노드 모음입니다.
12개 노드를 일일이 배선하기 귀찮은 사람을 위해, 한 노드가 체인 전체를 삼킵니다.

> **Fold the graph.** — toobusy folds tedious multi-step ComfyUI workflows into single production nodes.

<p align="center">
  <img src="docs/workflows/korean_scene_to_ideogram4.png" width="100%" alt="toobusy 워크플로우 — 한국어 장면을 Prompt Polish → Layout Builder → Ideogram4 T2I로 접는 그래프">
</p>

<table>
  <tr>
    <td align="center" width="50%">
      <a href="docs/workflows/sample1.jpg"><img src="docs/workflows/sample1.jpg" height="170" alt="Ideogram4 samurai action result made with toobusy"></a>
    </td>
    <td align="center" width="50%">
      <a href="docs/workflows/sample2.jpg"><img src="docs/workflows/sample2.jpg" height="170" alt="Bold Korean typography result made with toobusy"></a>
    </td>
  </tr>
  <tr>
    <td align="center" width="50%">
      <a href="docs/workflows/sample3.jpg"><img src="docs/workflows/sample3.jpg" height="170" alt="Magazine cover style result made with toobusy"></a>
    </td>
    <td align="center" width="50%">
      <a href="docs/workflows/sample4.jpg"><img src="docs/workflows/sample4.jpg" height="170" alt="Game poster style result made with toobusy"></a>
    </td>
  </tr>
</table>
<p align="center"><sub>↑ toobusy 노드(Layout Builder · Prompt Polish · Ideogram4 T2I)로 만든 결과 — 클릭하면 원본. 워크플로우: <a href="docs/workflows/korean_scene_to_ideogram4.json">korean_scene_to_ideogram4.json</a></sub></p>

<p align="center">
  <a href="https://youtu.be/1XQLOK40ATw">
    <img src="https://img.youtube.com/vi/1XQLOK40ATw/maxresdefault.jpg" width="72%" alt="toobusy 리뷰/소개 영상 — 너무바쁜베짱이">
  </a>
</p>
<p align="center"><sub>▶ 리뷰·소개 영상 (클릭하면 YouTube) · 너무바쁜베짱이</sub></p>

노드는 세 갈래로 접혀 있습니다:

- **`toobusy/Plan`** — 기획·연출·프롬프트를 접는다: Keyframe Maker, Storyboard Board, Ideogram Layout Builder, Ideogram Prompt Polish
- **`toobusy/Make`** — 생성 파이프라인을 접는다: Z-Image Turbo, Ideogram4 T2I, LTX2.3 3종

현재 대표 흐름:

- `toobusy Ideogram Prompt Polish`
- `toobusy Ideogram Layout Builder`
- `toobusy Ideogram4 T2I`

한국어 장면을 입력하면, Ideogram용 구조화 프롬프트로 정리하고, Layout Builder에서 박스와 구도를 확인한 뒤, 로컬 Ideogram4 모델로 이미지를 생성하는 흐름입니다.

`toobusy Ideogram4 T2I`도 선택형 외부 모델 override 입력을 받습니다: `model_override`·`uncond_model_override`(MODEL), `clip_override`(CLIP), `vae_override`(VAE). 연결된 소켓은 해당 내부 로더를 건너뛰고(미연결 시 `model_name`/`unconditional_model_name`/`clip_name`/`vae_name`으로 내부 로드), GGUF 등 다른 로더의 모델을 그대로 사용할 수 있습니다.

함께 쓰기 좋은 노드:

- `toobusy Keyframe Maker`
- `toobusy Storyboard Board`
- `toobusy Z-Image Turbo`
- `toobusy LTX2.3` 컴팩트 노드들

## 왜 "접기"인가 — Before → After

설치하면 **기존 그래프가 짧아집니다.** 그게 toobusy의 약속입니다.

| 노드 | Before (직접 배선) | After |
|---|---|---|
| **Z-Image Turbo** | UNET·CLIP·VAE 로더 + (LoRA×N) + ModelSamplingAuraFlow + CLIPTextEncode×2 + EmptyLatentImage + KSampler + VAEDecode — 약 10노드 | **1 노드** |
| **Ideogram4 T2I** | 로더 4 + 선택적 LoRA 체인 + 인코딩 + ConditioningZeroOut + CFGOverride + DualModelGuider + RandomNoise + KSamplerSelect + Ideogram4Scheduler + EmptyLatent + SamplerCustomAdvanced + VAEDecode — 약 13노드+ | **1 노드** |
| **LTX2.3 Compact AV Sampler** | RandomNoise + ConcatAVLatent + CFGGuider + KSamplerSelect + ManualSigmas + SamplerCustomAdvanced + SeparateAVLatent + CropGuides — 8노드 | **1 노드** |
| **LTX2.3 Empty AV Latents** | EmptyLTXVLatentVideo + LTXVEmptyLatentAudio (+커스텀 오디오: AudioVAEEncode + SolidMask + SetLatentNoiseMask) | **1 노드** |
| **Keyframe Maker** | 브리프 → 샷 비트 → 비주얼 앵커 → 키프레임 → 스토리, 5단계 수동 프롬프팅 | **1 노드** |
| **Storyboard Board** | 외부 화이트보드 앱 + 캡처 + 임포트 | **노드 안에서 바로** |
| **Ideogram Layout Builder** | 구조화 프롬프트 JSON을 손으로 작성 | **캔버스에 박스 드래그** |
| **Ideogram Prompt Polish** | 한국어 장면 작성 → 영어 번역 → Ideogram 구조화, 매번 머릿속 멀티스텝 | **1 노드** (장면만 한국어로 쓰면 끝) |

> 새 노드 추가 기준도 동일합니다: **"이게 귀찮은 여러 단계를 하나로 접나?"** — Yes만 들어옵니다.

## 필요한 것 & 제약 (솔직하게)

완벽한 척보다 **"이 조건에서 검증됨"** 을 적습니다. 접기 노드는 내부에서 여러 ComfyUI 노드/모델을 호출하므로, 그 전제가 갖춰져야 동작합니다.

| 노드 | 필요한 것 | 제약 / 검증 조건 |
|---|---|---|
| **Keyframe Maker** | `clip`에 **텍스트 생성 가능한 모델**(Gemma/LTX 등) + ComfyUI `TextGenerate` 노드 | 출력 품질은 연결한 LLM에 좌우됩니다. 내부에서 `seed`~`seed+4`를 사용 |
| **Z-Image Turbo** | Z-Image Turbo 디퓨전 모델 + `lumina2` 텍스트 인코더 + VAE | 해당 모델 파일이 모델 폴더에 있어야 합니다 |
| **Ideogram4 T2I** | **로컬 Ideogram 4 모델** + ComfyUI의 Ideogram4 지원 노드(`Ideogram4Scheduler`/`CFGOverride`/`DualModelGuider` 등) + UNET 2개(model/uncond) + `ideogram4` CLIP | **웹 API가 아닙니다.** Ideogram4 미지원 빌드에선 실행 시점에 실패합니다 |
| **LTX2.3 (3종)** | ComfyUI에 LTX 2.3 노드셋(`LTXV*`) 설치 + LTX 모델/VAE/텍스트 인코더 | LTX 지원이 없는 환경에선 실행 시점에 실패합니다 |
| **Storyboard Board** | (코어만) Pillow·numpy·torch | 드롭한 이미지는 `board_data`에 임베드 → 이미지가 많으면 그래프 JSON이 커집니다. 폰트는 arial→기본 폴백 |

> 모델 파일은 저장소에 포함하지 않습니다. 각 모델은 ComfyUI의 해당 폴더(`diffusion_models`/`text_encoders`/`vae`/`loras`)에 직접 두세요.

## 예제 워크플로우

`docs/workflows/`에 "열면 돌아가는" 워크플로우를 둡니다.

- [`korean_scene_to_ideogram4.json`](docs/workflows/korean_scene_to_ideogram4.json) — **한국어 장면 → Prompt Polish → (Import polished로) Layout Builder → Ideogram4 T2I.** 한국어 한 줄이 영어 구조화 프롬프트 + 레이아웃 + 이미지로 흐르는 흐름입니다. 처음 사용자는 이 워크플로우를 먼저 열어 전체 흐름을 확인하는 것을 권장합니다. 필요한 모델 링크는 워크플로우 안 Note 노드에 있습니다.
- [`z_image_turbo.json`](docs/workflows/z_image_turbo.json) — **`toobusy Z-Image Turbo` 한 노드로 t2i 그래프(~10노드)를 접는 예제.** `image` 입력에 Load Image를 연결하면 자동으로 img2img로 전환됩니다. 필요한 모델 링크는 워크플로우 안 Note 노드에 있습니다(Comfy-Org Z-Image Turbo / Qwen3-4B / Flux VAE).

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

## 3분 첫 실행 루트

처음 설치했다면 예제 워크플로우부터 여는 것을 추천합니다.

1. ComfyUI에서 `docs/workflows/korean_scene_to_ideogram4.json`을 드래그해 엽니다.
2. 워크플로우 안의 Note 노드에 적힌 모델 파일과 필요한 커스텀 노드를 준비합니다.
3. `toobusy Ideogram Prompt Polish`에 한국어 장면을 입력합니다.
4. 출력된 `ideogram_json`을 복사합니다.
5. `Ideogram Layout Builder`의 `Import polished`를 눌러 붙여넣고, preview를 확인한 뒤 `Apply`합니다.
6. 박스/색상/구도를 필요하면 수정합니다.
7. `toobusy Ideogram4 T2I`로 이미지를 생성합니다.

핵심 흐름은 이렇습니다:

```text
한국어 장면
-> Ideogram용 구조화 프롬프트
-> Layout Builder에서 구도 확인
-> Ideogram4 이미지 생성
```

`Ideogram4 T2I`는 웹 API가 아니라 로컬 Ideogram4 모델용 노드입니다. 해당 모델과 ComfyUI의 Ideogram4 지원 노드가 준비되어 있어야 합니다.

## 활성 노드

### toobusy Keyframe Maker

카테고리:

```text
toobusy/Plan
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
- `visual_anchor`
- `keyframe_prompts`
- `keyframe_prompt_line`: `keyframe_prompts`를 줄 단위로 나눈 리스트 출력입니다. 앞뒤 공백과 빈 줄은 기본으로 제거되며, 프롬프트/문자열 입력에 연결하면 한 줄씩 하위 노드를 실행합니다.
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

실행 후에는 `Use generated brief as override` / `Use generated shot beats as override` 버튼으로 방금 생성된 브리프·샷 비트를 해당 오버라이드 칸에 그대로 복사할 수 있습니다. 비싼 초기 단계를 고정해두고 이후 단계만 다시 생성하며 반복 작업할 때 유용합니다.

### toobusy Storyboard Board

카테고리:

```text
toobusy/Plan
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

편집 기능:

- **텍스트 사후 편집**: 텍스트 아이템을 더블클릭하거나, 선택 후 속성 바의 `Edit text` 버튼.
- **리사이즈**: 사각형/타원/이미지/텍스트는 코너 핸들, 화살표/선은 양 끝점 핸들을 드래그.
- **속성 바**(선택 아이템): 색상, 채움 + `no fill`(사각형/타원), 선 두께, 폰트 크기(텍스트), `Front`/`Back`(앞/뒤 순서), `Duplicate`(복제).
- **Undo/Redo**: 툴바 버튼 또는 Ctrl/Cmd+Z, Shift+Z(되돌리기 취소) / +Y. 캔버스 포커스 상태에서 Delete/Backspace로 선택 삭제.
- 인라인 캔버스의 텍스트는 익스포트(파이썬 렌더)와 **같은 방식으로 박스 폭에 맞춰 줄바꿈**되어, 미리보기와 출력 이미지의 줄나눔이 일치합니다.

출력:

- `image`: 렌더링된 보드 이미지.
- `board_data`: 재사용·디버깅용으로 저장된 보드 JSON.

### toobusy Z-Image Turbo

카테고리:

```text
toobusy/Make
```

컴팩트한 Z-Image Turbo 텍스트→이미지 워크플로우를 하나의 노드로 묶었습니다(마지막 `SaveImage` 노드는 제외).

<p align="center">
  <a href="docs/workflows/z_image_turbo.json"><img src="docs/workflows/z_image_turbo.png" width="100%" alt="toobusy Z-Image Turbo 워크플로우 — Load Image + 한 노드 + Save Image"></a>
</p>
<p align="center"><sub>↑ <code>toobusy Z-Image Turbo</code> 한 노드로 접은 t2i 워크플로우. 워크플로우: <a href="docs/workflows/z_image_turbo.json">z_image_turbo.json</a> (열면 Note 노드에 모델 다운로드 링크 포함). 결과 예시 → <a href="docs/workflows/z_image_turbo_sample.png">z_image_turbo_sample.png</a></sub></p>

내부 흐름:

```text
UNETLoader + CLIPLoader + VAELoader
-> 선택적 LoraLoader 슬롯 체인
-> ModelSamplingAuraFlow
-> CLIPTextEncode positive/negative
-> EmptyLatentImage  (image 입력이 없을 때 · t2i)
   또는 (선택) ImageScale -> VAEEncode  (image 입력이 있을 때 · img2img)
-> KSampler
-> VAEDecode
```

주요 입력:

- `model_name`: 디퓨전 모델/UNET 파일. 예: `ZIT\zImage_turbo.safetensors`.
- `clip_name`: 텍스트 인코더 파일. 예: `ZIT\zImage_textEncoder.safetensors`.
- `vae_name`: VAE 파일. 예: `FLUX1\ae.safetensors`.
- `positive` / `negative`: 프롬프트 텍스트.
- `ratio_preset`, `megapixels`, `divisible_by`: 종횡비와 목표 메가픽셀로부터 해상도를 계산합니다.
- `width` / `height`(선택): 직접 입력 칸. 둘 다 `0`이면 위 `ratio_preset`+`megapixels`로 계산하고, 둘 다 `> 0`이면 그 해상도를 직접 사용합니다(`divisible_by`로 반올림). 해상도 미리보기 위젯에 `manual -> 가로 x 세로`로 표시됩니다.
- `image`(선택, IMAGE 소켓): **연결하면 자동으로 img2img로 전환**됩니다. 이미지를 `VAEEncode`로 인코딩해 시작 latent으로 쓰고, `denoise`가 변환 강도가 됩니다(낮을수록 원본 보존). `width`/`height`를 지정하면 소스를 그 크기로 스케일(center crop)하고, 비워 두면 소스 이미지 크기를 그대로 따릅니다. 소켓을 비우면 기존 t2i로 동작합니다.
- `seed`, `steps`, `cfg`, `sampler_name`, `scheduler`, `denoise`, `aura_shift`.
- LoRA 슬롯: 프런트엔드에 `Add LoRA slot` / `Remove LoRA slot` 버튼이 추가됩니다. 최대 5개 슬롯까지 표시할 수 있으며, 각 슬롯은 자체 활성화 토글, LoRA 파일, 강도를 가집니다.
- 외부 모델 override(선택): `model_override`(MODEL), `clip_override`(CLIP), `vae_override`(VAE) 입력 소켓입니다. 연결하면 해당 내부 로더(`UNETLoader`/`CLIPLoader`/`VAELoader`)를 건너뛰고 연결된 객체를 그대로 사용하고, 비워 두면 위의 `model_name`/`clip_name`/`vae_name`으로 내부 로드합니다. GGUF 등 다른 로더로 불러온 모델을 그대로 흘려보낼 때 유용합니다.

LoRA 동작:

- ComfyUI 내장 `LoraLoader`를 사용하므로 rgthree의 Power Lora Loader가 필요 없습니다.
- 활성화된 슬롯은 슬롯 순서대로 적용됩니다.
- 비활성화된 슬롯과 `None`으로 설정된 슬롯은 건너뜁니다.

Basic / Advanced:

- 기본은 **Basic 화면**으로, 자주 쓰는 입력이 보입니다: **`model_name`/`clip_name`/`vae_name`(모델 로드 슬롯)**, `positive`, `negative`, `ratio_preset`, `megapixels`, `width`, `height`, `batch_size`, `seed`, `steps`. 모델 로드 슬롯을 기본 노출해, 어떤 모델이 물려 있는지 바로 보고 고칠 수 있습니다(엉뚱한 모델로 헤매는 상황 방지).
- `Show advanced settings` 버튼을 누르면 expert 튜닝 컨트롤(`divisible_by`, `cfg`, `sampler_name`, `scheduler`, `denoise`, `aura_shift`)과 LoRA 슬롯/버튼, 그리고 **모델 override 입력 소켓**(`model_override`/`clip_override`/`vae_override`)이 나타납니다. override 소켓은 고급 입력이라 Basic에서는 숨겨지며(이미 연결돼 있으면 유지), `image`(img2img) 입력은 항상 노출됩니다. 상태는 노드에 저장되어 그래프를 다시 열어도 유지됩니다.
- **info 배지**: 노드 우상단 모서리의 `i` 아이콘에 마우스를 올리면, 이 노드가 어떤 노드들을 접는지(t2i/img2img 흐름 포함) 설명 툴팁이 뜹니다.
- **해상도 미리보기**: `ratio_preset @ megapixels -> 가로 x 세로`(직접 입력 시 `manual -> ...`, 이미지 연결 시 `img2img -> ...`) 표시 위젯이 항상 보여, 큐에 올리기 전에 실제 생성 크기를 확인할 수 있습니다.

출력:

- `image`
- `latent`
- `width`
- `height`

### toobusy LTX2.3 Prompt Guide

카테고리:

```text
toobusy/Make
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
toobusy/Make
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

미리보기 readout:

- 노드에 요약 위젯이 표시됩니다 — `종횡비 @ MP -> 가로 x 세로`, `길이(프레임) @ fps -> ~초`, 그리고 커스텀 오디오 상태.
- `use_custom_audio`가 켜졌는데 `audio` 입력이 연결되지 않았으면 **경고**를 표시합니다(런타임 에러 전에 미리 확인). 연결을 바꾸면 자동 갱신됩니다.

### toobusy LTX2.3 Compact AV Sampler

카테고리:

```text
toobusy/Make
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

`manual_sigmas`는 전문가용 컨트롤이라 기본적으로 숨겨져 있습니다. `Show advanced settings` 버튼으로 펼칠 수 있고, `sigmas` 입력이 연결되면(= `manual_sigmas`를 덮어쓰므로) 자동으로 숨겨지며 현재 시그마 소스를 알려주는 표시가 나타납니다.

노드는 샘플링 후 항상 `LTXVCropGuides`를 실행하여 latent이 이어지기 전에 가이드 프레임을 제거합니다.

## 기타 노드 상세 메모

아래는 설치하면 함께 등록되는 노드들의 상세 메모입니다. 상단 대표 흐름에서 바로 쓰는 노드와, 다른 흐름을 보조하는 노드를 함께 정리합니다:

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
  방향키 이동 · Shift로 크게 이동, Esc 선택 해제)를 제공합니다. **Import polished**는
  Prompt Polish의 `ideogram_json`을 큰 붙여넣기 모달에서 JSON 파싱/형식 검증과
  scene·요소 수 미리보기까지 확인한 뒤, `Apply`를 눌렀을 때만 현재 캔버스와
  scene/style/background/palette 필드를 교체합니다. 같은 모달의 **Load PNG**는
  ComfyUI PNG metadata(`prompt`/`workflow` 등)에 들어있는 Prompt Polish / Ideogram
  JSON을 찾아 같은 preview→Apply 흐름으로 불러옵니다. 기본 캔버스는 Ideogram4
  레이아웃 품질을 우선해 2K 정사각형(`2048 x 2048`)입니다.
- `ideogram4_t2i_node` (`toobusy Ideogram4 T2I`) — 프롬프트로부터 로컬 Ideogram 4
  모델(CLIP `ideogram4`, `Ideogram4Scheduler`)을 실행합니다. Layout Builder의 JSON
  프롬프트와 `width`/`height`를 그대로 받습니다. Z-Image Turbo와 같은 방식의
  **LoRA 슬롯**을 제공하며, `Add LoRA slot` / `Remove LoRA slot`으로 최대 5개까지
  표시할 수 있습니다. 활성화된 슬롯은 conditional 모델과 CLIP에 순서대로 적용되고,
  `ideogram4_unconditional` 모델은 원래 checkpoint를 유지합니다.

## 로드맵

단기 계획:

1. `toobusy Keyframe Maker` 다듬기 마무리.
2. 컴팩트 Z-Image Turbo 생성 노드 다듬기.
3. ComfyUI-Manager 등록 및 공개 영상 릴리스를 위한 저장소 정비.
