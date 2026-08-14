# Changelog

## [0.4.6] - 2026-08-10

### Changed
- Reworked the FlashVSR source inspection test to avoid dynamic `exec`, keeping
  Registry security scans clean without changing installed node behavior.

## [0.4.5] - 2026-08-10

### Added
- Added `toobusy Wan Animate 2 Long Sampler`, which automatically divides a
  target frame count into valid `4k+1` Wan chunks, continues motion with a
  one-frame overlap, and crops the final result to the requested exact length.
- Exposed the final `MODEL`, `CONDITIONING`, `SAMPLER`, and `SIGMAS` sockets so
  users can keep attention, caching, LoRA, and sampling policy outside the
  compact node.
- Added 12GB, 16GB, and 24GB starting-point guidance for 33, 49, and 81 frames
  per sampler chunk.

### Fixed
- The Animate 2 chunk-plan readout now detects a link connected directly to the
  `total_frames` widget input instead of showing the stale stored widget value.

이 프로젝트의 주요 변경 사항을 기록합니다. (Keep a Changelog 형식, 날짜는 YYYY-MM-DD)

## [Unreleased]

### Added
- Added a 32GB aggressive VRAM profile and 128-aligned high-resolution presets.

### Fixed
- Padded short FlashVSR inputs to the minimum 25-frame streaming layout and
  rejected misaligned LQ input before it can lose tail guidance.
- Ignored placeholder FlashAttention modules that do not expose a callable
  attention function, allowing the installed fallback backend to be selected.

## [0.4.4] - 2026-08-07

### Fixed
- FlashVSR now resamples with a filter that matches the resize direction: `area`
  when shrinking the source, `bicubic` when enlarging it. Both directions
  previously used `nearest-exact`, which drops samples without prefiltering, so
  shrinking aliased and the surviving pixels shifted from frame to frame once
  anything moved — the sampler was conditioned on a shimmering low-quality
  input. Enlarging duplicated pixels into blocky edges the model then preserved.
  Sources close to the selected working resolution were barely affected, which
  is why the issue only showed up on larger inputs such as 0.8MP or 1280x720.
  Working resolution and tensor sizes are unchanged, so the verified 12GB, 16GB,
  and 24GB+ VRAM profiles still apply.
## [0.4.3] - 2026-08-07

### Fixed
- Connected the VRAM preset's decoder mode through a dedicated string override
  input so ComfyUI no longer rejects the workflow as an incompatible combo link.

## [0.4.2] - 2026-08-07

### Added
- Added a VRAM and resolution preset node for 12GB, 16GB, and 24GB+ GPUs.
- Added aggressive sampler offload for 12GB-class GPUs.

### Changed
- Fast decode now uses two orientation-aware strips when the latent size fits
  the verified tile budget.
- Offloaded DiT blocks now release the previous block before loading the next.
- Long Sampler now exposes 21 frames as its minimum supported chunk size.

## [0.4.1] - 2026-08-07

### Added
- Added `toobusy FlashVSR Loader`, `Long Sampler`, and `Full Decoder` for the
  FlashVSR v1.1 Full + Block-Sparse Attention path.
- Added long-video chunking with overlap blending and a 24GB VRAM reference
  preset (`2x`, 1024x576, 21-frame chunks, 8-frame overlap).
- Added `safe`, `balanced`, and `fast` VAE decode tile presets.

### Changed
- FlashVSR loads the DiT and VAE in separate phases and releases each phase
  before loading the next one. Large GPU models are not retained globally
  between queue runs.

### Fixed
- Stopped the decoder from mutating cached sampler latents, allowing users to
  compare decode presets without rerunning or corrupting the sampler output.

## [0.3.9] - 2026-07-19

### Fixed
- Restored positional compatibility for existing Ideogram Prompt Polish
  workflows. `release_clip_after_run` is now appended after all pre-existing
  widgets instead of being inserted before the image-analysis controls.
- Added a frontend migration for workflows saved with the broken v0.3.8 widget
  order, preventing `balanced` and `debug_raw` values from being validated as
  the wrong fields.

## [0.3.8] - 2026-07-18

### Added
- Added an optional in-node SageAttention switch for both Ideogram 4 model
  branches, applied after LoRA and CFG model patches.
- Added `release_clip_after_run` to Ideogram Prompt Polish so a large prompt
  CLIP such as Gemma 4 can leave VRAM without globally unloading every model.
- Added movable whiteboard artboards, nested layer groups, safer drawing and
  recovery, and sequential image-list output for all artboards.

### Changed
- Ideogram 4 Quality, Default, and Turbo now apply the complete official
  sampler, schedule, and CFG settings. Manual tuning remains available through
  Custom mode, while a resolved-settings readout shows what will actually run.

### Fixed
- Avoided the broad cache destruction caused by using a global VRAM cleaner as
  the hand-off between prompt generation and Ideogram model initialization.
- Improved whiteboard coordinate handling, resizing, layer ownership, and
  restoration after frontend state changes.

## [0.3.7] - 2026-07-10

### Added
- `toobusy Wan SCAIL Extend Sampler`에 `continue_video` 입력을 추가했습니다. 이전에
  생성한 영상의 잘된 부분을 잘라 연결하면 base 청크를 건너뛰고, 그 영상의 꼬리
  프레임을 SCAIL-2 `previous_frames` 앵커로 사용해 이어서 생성합니다. 포즈 비디오는
  이어지는 지점부터 자동으로 걸어가며(`video_frame_offset`), `target total` 모드에서는
  불러온 프레임 수가 목표에 포함됩니다. 목표를 이미 채웠다면 불러온 영상을 그대로
  통과시킵니다.

### Fixed
- 캔버스 프레임 리드아웃이 `continue_video`나 `target_total_frames_input`이 연결된
  경우 위젯값 기준의 잘못된 분할 계획 대신 "실행 시 결정"을 표시하고, 링크
  연결/해제 시 즉시 갱신되도록 했습니다.

## [0.3.6] - 2026-07-09

### Fixed
- Fixed SCAIL target total frame links so the generated frame count wiring stays
  consistent in the folded SCAIL workflow.
- Removed the folded-node loader output cache so internal UNET/CLIP/VAE loader
  calls behave like normal ComfyUI graphs and do not hold extra VRAM across
  consecutive queue runs.
- Removed the Face Mask YOLO model cache for the same reason; optional detector
  models are no longer retained in module globals after a run.

## [0.3.4] - 2026-06-22

### Fixed
- `toobusy Hires Upscale`도 내부 `UpscaleModelLoader`를 v0.3.3의 공유 캐시(`_load_cached`)로
  돌려, 반복 실행마다 업스케일 모델을 다시 읽어 VRAM이 피크를 치던 부분을 줄였습니다.
  (업스케일 연산 자체의 메모리 사용은 4x 업스케일 특성상 별개이며 `scale_by`로 조절합니다.)

## [0.3.3] - 2026-06-22

### Fixed
- Z-Image Turbo, Flux2 Klein, Ideogram4 T2I가 내부에서 UNET/CLIP/VAE 로더를 호출할 때
  같은 모델을 반복 실행마다 다시 읽어 VRAM 피크와 대기 시간이 커지던 문제를 줄였습니다.
  공유 helper에 작은 LRU 캐시를 추가해 같은 loader/class/argument 조합은 재사용합니다.
- 캐시 추가 후 standalone 테스트의 fake loader 호출 기록이 테스트 사이에 남지 않도록
  관련 테스트 격리를 보강했습니다.

## [0.3.2] - 2026-06-21

### Fixed
- Comfy Registry 보안 스캐너(YARA)가 `tests/test_prompt_polish.py`의 `__import__("json")`을
  obfuscation/code-execution으로 오탐해 0.2.14~0.3.1이 flagged 처리되던 문제를 해결했습니다.
  해당 코드를 일반 `import json`으로 바꾸고, `.comfyignore`에 `tests/`·`.vscode/`를 추가해
  발행 패키지에서 테스트/개발 파일을 제외합니다. (노드 동작 변경 없음)

## [0.3.1] - 2026-06-21

### Fixed
- `toobusy Reference Board` 노드 프리뷰 카드 드래그아웃이 이미지뿐 아니라 오디오/텍스트/LoRA
  에서도 동작하도록 보강했습니다. 오디오·이미지는 파일/URL로, 텍스트·LoRA는 텍스트로
  드래그됩니다.

### Changed
- `toobusy Reference Board` 오버레이 에디터에서 오디오 카드를 더 넓게(가로형) 표시하고 재생
  막대를 키워, 세로 카드에서 재생바가 너무 작던 문제를 개선했습니다.

## [0.3.0] - 2026-06-21

레퍼런스 기반 제작 생태계(Reference Board → Prompt Director → Flux2 Klein)를 처음으로 공개합니다.

### Added
- `toobusy Reference Board`: 이미지/오디오/텍스트/LoRA 카드를 한 보드에서 구성해 하나의
  `TOOBUSY_BUNDLE`로 묶는 노드. 오버레이 에디터에서 카드 추가/역할 지정/노트 작성, 프리셋
  저장·로드(이름 기반 고유 ID), 노드 프리뷰에서 등록 카드만 표시.
  - 카드 호버 시 큰 미리보기 팝업, 카드 드래그아웃(다른 앱/브라우저로 이미지 끌어다 놓기),
    카드 이미지 클릭/드롭 교체(설정 유지).
  - 카드 부착 모듈: `Erase Face`(몸의 얼굴 제거) / `Keep Face Only`(얼굴만 남기기) /
    `Remove Background`(배경 제거) — 카드 이미지에 서버측에서 적용.
  - 텍스트 카드(Goal/Style/Negative/Custom)와 레퍼런스 이름 삽입 칩.
  - 독립 LoRA 카드 및 Face 카드 FaceSwap LoRA 선택(로컬 lora 드롭다운).
- `toobusy Flux2 Klein Prompt Director`: Bundle을 받아 버튼 패널로 최종 프롬프트를 구성하는
  노드. 연결된 Reference Board의 등록 카드만 버튼으로 동적 표시, 선택 순서 유지,
  `FaceSwap`/`Product Swap`/`Character Swap` 플래그, Camera/Lighting/Style 프리셋 칩.
- `toobusy Bundle Unpack` / `toobusy Bundle Get`: Bundle에서 역할별 이미지·오디오·프롬프트·
  LoRA를 꺼내는 노드(Get은 연결 보드 기준 역할 드롭다운).
- `toobusy Background Remove`(optional, rembg) / `toobusy Face Mask`(optional, YOLO→mediapipe→
  opencv 단계 검출): 배경 제거 및 얼굴 erase/keep 마스킹 노드.
- `toobusy DreamID-Omni Loader/Talker`(optional): 설치된 DreamID-Omni 노드에 위임하는 토킹헤드
  골격(별도 모델·의존성 필요).

### Changed
- `toobusy Flux2 Klein`: `TOOBUSY_BUNDLE`을 직접 받아 빈 레퍼런스 슬롯을 채우고, 번들 LoRA를
  적용. `bundle_reference_order`에 `auto`(기본, Director 스왑 플래그를 따름) 및 `product_swap`/
  `character_swap` 추가. positive 프롬프트 입력 박스를 기본적으로 작게 표시.

### Fixed
- Reference Board 프리셋이 한글 등 비ASCII 이름에서 같은 ID로 충돌해 덮어쓰여 사라지던 문제를
  이름 해시 기반 고유 ID + 원자적 저장으로 수정.
- Bundle Unpack이 실제 이미지(다중 원소 텐서)에서 `payload or blank`의 불리언 평가로 오류나던
  문제를 수정.

## [0.2.14] - 2026-06-19

### Added
- `toobusy Keyframe Maker` 공개 보강:
  기존 6개 출력은 유지하면서 `transition_prompts`, `prompt_relay_block`,
  `shot_table_json`, `validation_report`를 뒤에 추가했습니다. `fast / standard / full`
  `output_mode`를 추가해 로컬 LLM 사용 시 불필요한 전환 프롬프트/한국어 해석 생성을
  건너뛸 수 있습니다.
- `toobusy Keyframe Maker`에 `product_image_mode` 추가:
  `design reference only`(기본), `packaging/form reference`, `exact product identity` 중
  선택할 수 있습니다. 기본값에서는 `idea`가 제품 카테고리·사용법·광고 문법을 결정하고,
  `product_image`는 외형·재질·색감·실루엣·패키지 톤 참고로만 사용합니다.
- `toobusy Ideogram Prompt Polish`에 `analysis_mode` 추가:
  `fast / balanced / detailed`로 이미지 분석 상세도를 조절합니다. 기본 `balanced`는
  Layout Builder 초안용으로 요소 수와 desc 길이를 줄여 속도를 우선합니다.
- `toobusy Ideogram Prompt Polish`에 `debug_raw` 추가:
  기본값에서는 `llm_raw`를 비우거나 짧게 잘라 workflow 저장 데이터가 과도하게 커지는 것을
  줄이고, 필요할 때만 전체 raw 응답을 확인할 수 있습니다.

### Changed
- `toobusy Ideogram Layout Builder` 프론트엔드 phase 2 facelift:
  헤더, 카드, 인스펙터 섹션, chip, 버튼 variant 스타일을 정리했습니다.
- Prompt Polish 이미지 분석 기본 프롬프트를 "느린 정밀 분석기"보다 "빠른 Layout Builder
  초안 생성기"에 맞게 조정했습니다. mixed Korean/Latin 텍스트는 기본적으로 분리하지 않고
  하나의 텍스트 요소로 유지합니다.
- Prompt Polish 텍스트-only scene 프롬프트가 Layout Builder용 elements/bbox를 더 적극적으로
  생성하도록 보강했습니다.
- Keyframe Maker의 product image 분석을 story-side 제품 정의와 reference-side 시각 정의로
  분리했습니다. 향수 광고처럼 `idea`가 제품 동작을 명시한 경우 reference 이미지가 세럼/스킨케어
  포장처럼 보여도 사용 문법을 덮어쓰지 않도록 안내합니다.

### Fixed
- Prompt Polish JSON fallback에서 elements가 완전히 비어 보이지 않도록 중앙 main subject
  placeholder를 채웁니다.
- Keyframe Maker `validation_report`에 product image와 idea 사이의 perfume/skincare 계열
  충돌 경고를 추가했습니다.

## [0.2.13] - 2026-06-17

### Added
- `toobusy Ideogram Prompt Polish`에 **이미지 지시 모드** 드롭다운 추가:
  기본 `Analyze image literally`는 기존처럼 연결된 이미지를 있는 그대로 분석하고,
  새 `Transform by scene text`는 **이미지를 레이아웃/구도 참고로만 사용**하면서
  `Scene` 입력의 지시에 따라 주제·텍스트·선수/팀/국가 같은 내용을 다시 씁니다.
  예: 외국 선수 카드 이미지를 참고해 같은 카드 레이아웃을 유지하되 한국 선수 카드
  내용으로 변환하는 JSON 초안을 만들 수 있습니다.

### Changed
- `toobusy Ideogram Layout Builder` 레이어 UX 개선:
  선택한 박스를 `Ctrl+Shift+↑`로 최상단, `Ctrl+Shift+↓`로 최하단으로 보낼 수 있습니다.
  오른쪽 `Layers` 목록에서는 레이어 이름을 드래그해 원하는 위치로 직접 재정렬할 수 있고,
  드래그 중에는 레이어 사이에 삽입선이 표시됩니다. 목록 하단에는 이 조작을 알려주는
  작고 얌전한 도움말을 추가했습니다.
- Ideogram4 대표 예제 워크플로우 `docs/workflows/korean_scene_to_ideogram4.json`을
  최신 운영자 export로 교체했습니다. README 링크 경로는 그대로 유지됩니다.

### Fixed
- Prompt Polish 이미지 분석 출력 안정화:
  텍스트 생성 길이를 제한하고, 레이아웃 출력이 과하게 길어지지 않도록 압축했으며,
  LLM 호출 동작을 복원했습니다.
- Layout Builder의 한글 오버레이 split 경로에서 bbox 구조가 더 안정적으로 유지되도록
  후속 hotfix를 반영했습니다.

## [0.2.12] - 2026-06-16

### Added
- `toobusy Ideogram Layout Builder`에 **`text_overlay_mode` 토글 + `text_json` 출력** 추가 —
  한글 반자동 파이프라인의 완결. 토글 ON이면 `ideogram_json`에서 **텍스트 요소를 빼서**(Ideogram이
  그림/배경만 생성, 깨진 한글 안 그림) 새 `text_json` 출력으로 분리하고, 그걸 `Layout Text Overlay`에
  물려 **크리스피한 한글**을 얹습니다. OFF면 텍스트가 이미지에 포함(영어 등 기존 동작). `text_json`은
  항상 텍스트 전용으로 나옵니다. (출력은 뒤에 append라 기존 워크플로우 슬롯 호환.)
- **`toobusy Layout Text Overlay`** 신규 노드: 생성된 이미지 **위에 실제 글자를 렌더**해 — Ideogram4가
  한글을 못 그려도 **크리스피한 한글 헤드라인**을 얹습니다. **인터랙티브 에디터**(이미지 배경 위에
  텍스트를 띄워 **드래그·인라인 편집·폰트크기(모서리 핸들/슬라이더)·색·정렬**) + Pillow 렌더로
  출력이 미리보기와 일치. `layout_json`(Prompt Polish 출력 등)을 연결하면 `type:"text"` 요소가
  자동 시드되어 손 안 대도 헤드라인이 배치됨. 한글 폰트(malgun) 폴백. 좌표는 0~1 정규화라
  해상도 무관. 흐름: `Ideogram4 → Layout Text Overlay(+layout_json) → 한글 박힌 최종 이미지`.
- `toobusy Ideogram Prompt Polish` 이미지 모드에 **이미지 색 자동 추출** 추가: 비전 LLM이 팔레트를
  비워 보내 결과가 탁해지던 문제를 보완 — 비어 있으면 **실제 이미지 픽셀에서 전체 팔레트 + 각 요소
  bbox 영역의 대표색**을 뽑아 채웁니다(LLM이 채운 색은 보존).
- **`toobusy Ideogram Prompt Polish`에 이미지 분석 모드** 추가: optional `image` 입력 + 비전
  모델(예: Gemma 4)을 연결하면, 씬 텍스트 변환 대신 **이미지 1장을 분석해 같은 Ideogram4
  레이아웃 JSON 초안**으로 만듭니다 — 보이는 텍스트를 **원문 그대로(한글 포함)** 읽고, 의미 있는
  요소(제목/섹션/아이콘 등)를 중복 없이 bbox와 함께 잡습니다. 이미지를 안 물리면 기존 씬
  폴리셔 그대로(하위호환). 이미 있던 TextGenerate 이미지 입력 + Ideogram 스키마 프롬프트 +
  JSON 추출/정형 로직을 그대로 재활용 — 새 의존성 0. 출력 `ideogram_json`을 Layout Builder의
  `imported_json`에 물리고 `⟳ Pull from input`으로 캔버스에 올립니다.
- `toobusy Ideogram Layout Builder`에 **`⟳ Pull from input` 버튼 + 입력 소켓 2개**(`imported_json`,
  `image`) 추가. 업스트림(예: Prompt Polish 이미지 모드)의 `ideogram_json`을 `imported_json`에,
  원본 이미지를 `image`에 연결한 뒤 버튼을 누르면 — **그 빌더에 필요한 앞단 노드만 부분 실행**
  (전체 큐 안 돌림)하고, 결과 JSON을 **캔버스에 박스로** 올리고 원본 이미지를 **반투명 백드롭
  으로** 깔아줘요(박스가 실제 이미지 위에 정확히 겹침). 빌더를 `OUTPUT_NODE`로 + 실행 시 값을
  프론트로 돌려주는 방식(`onExecuted`). 기존 수동 빌더/Import polished 0 변경.

### Fixed
- `toobusy Ideogram Layout Builder` 캔버스에서 박스 선택 후 **Delete/Backspace를 누르면 노드 전체가
  삭제되던** 문제 수정 — 키 이벤트 전파(`stopPropagation`)를 막아, 캔버스 편집 중 Delete는
  **선택한 박스만** 지웁니다(화살표 nudge·Esc도 동일 처리).

## [0.2.11] - 2026-06-15

### Changed
- `toobusy Wan SCAIL Extend Sampler`의 **color_match에 조절기 2개** 추가. ① **`color_match_strength`**
  (0~1, 기본 1.0): 청크 색보정을 얼마나 세게 당길지. 씬 색이 실제로 바뀌는 영상(예: 파란
  클로즈업 → 줌아웃 와이드샷)에서 풀강도 보정이 다음 씬을 파랗게 물들일 때 낮추면 됨(0 =
  color_match off와 동일). ② **`color_sample`**(whole chunk 기본 / last frame): 앵커 청크의
  **어느 프레임이 색 기준이 되는지**. `whole chunk`는 청크 전체 색을 평균내 색이 튀는 마지막
  프레임(클로즈업 등) 하나가 다음 청크를 끌어당기는 걸 막고, `last frame`은 이음새 프레임에
  정확히 맞춤(가장 매끄러운 이음새, 단 튀는 꼬리 프레임에 취약). 내부 Reinhard LAB 통계를
  단일 프레임 → 참조 프레임 전체 풀링으로 바꿔 평균 앵커를 지원(단일 프레임 동작은 불변).
  (운영자 제안 — 색 드리프트 불만 대응)
- `toobusy Wan SCAIL Extend Sampler`에 **`frame_mode`** 토글 추가. 기본 `target total`
  모드에서는 **원하는 총 프레임(`target_total_frames`) 하나만** 입력하면 노드가
  `base_frames` 크기 청크로 자동 분할해 필요한 만큼 익스텐드를 돌립니다 — 중간 청크는
  모두 같은 크기, 마지막 청크만 목표에 가장 가깝게(4k+1 격자) 자동 조절. 익스텐드
  슬롯을 한 칸씩 쌓을 필요가 없고, readout이 실제 분할 내역(`81 + 76 = 157 frames ·
  ~9.8s · 1 extend`)과 청크 수를 보여줍니다. `manual segments` 모드는 기존 +/- 슬롯
  방식 그대로(파워유저용). auto 모드는 슬롯 상한(8)에 안 묶이고 내부 안전 상한 64까지
  분할합니다. 포즈 영상보다 긴 목표는 콘솔 경고. (운영자 제안)
- SCAIL-2 예제 워크플로우 `docs/workflows/wan21_scail2.json`을 최신
  `toobusy Wan SCAIL Extend Sampler` 중심 예제로 교체했습니다. 새 예제는
  `frame_mode`와 color_match 조절기를 테스트하기 쉬운 36노드 구성입니다.

## [0.2.10] - 2026-06-13

### Added
- **`toobusy Flux2 Klein`** 신규 노드: Flux2 Klein 9B 레퍼런스 그래프(UNETLoader +
  FluxKVCache + CLIP/VAE 로더 + CLIPTextEncode + 레퍼런스 N개 ImageScaleToTotalPixels
  →VAEEncode→ReferenceLatent 체인 + BasicGuider + RandomNoise + KSamplerSelect +
  Flux2Scheduler + EmptyFlux2LatentImage + SamplerCustomAdvanced + VAEDecode)를
  1노드로 접었습니다. 레퍼런스 `＋/✕` 동적 슬롯(최대 5), LoRA 슬롯, `size_mode`
  (from reference/ratio+megapixels/manual)와 사이즈 readout, passthrough 출력
  (model/model_clean/clip/vae/positive), 모델 자동 감지, info 배지.
- **`toobusy Load CLIP`** 신규 노드: safetensors/`.gguf` 텍스트 인코더를 한 노드로
  로드하면서, 토큰을 추가한 커스텀/파인튜닝 LLM(예: Dolphin 128258 vs 코어 128256)도
  로드되게 합니다. 잘라내지 않고 **모델 임베딩을 파일 크기에 맞춰 키워**(전체 토큰
  보존) 처리하며, 후킹은 로드 동안만 적용되고 항상 원복됩니다. 로딩은 표준 로더에
  위임(`.gguf`는 ComfyUI-GGUF, 나머지는 코어 CLIPLoader)해 toobusy에 GGUF 의존성을
  더하지 않습니다. 로컬 LLM 프롬프트 인핸서 체인에 유용.

### Changed
- `toobusy Wan SCAIL Extend Sampler`에 **`color_anchor`**(first chunk / previous
  chunk) 옵션 추가. 청크 확장의 누적 색빠짐(VAE 왕복으로 청크마다 채도가 조금씩
  깎임)을 막기 위해, color_match가 **첫 청크의 마지막 프레임을 고정 앵커**로
  삼도록 기본값을 `first chunk`로 했습니다. `previous chunk`는 이전 청크 기준
  (이음새 가장 매끄럽지만 드리프트를 따라감). (운영자 피드백)
- `toobusy Flux2 Klein`에 **`size_mode`**(from reference / ratio + megapixels /
  manual)와 **사이즈 readout**을 추가했습니다. 레퍼런스 #1이 ratio/megapixels를
  조용히 덮어쓰던 동작이 이제 명시적이고(기본 `from reference`라 동작 불변), readout이
  실제 출력 크기·소스를 보여줘 "1:1@1MP로 설정했는데 레퍼런스 크기로 나오는" 혼란을
  없앱니다. 레퍼런스 연결 상태에서도 `ratio + megapixels`로 강제 가능. 레퍼런스
  슬롯 최대 3→5로 확대. (운영자 피드백)

### Fixed
- **공용 `_call_node`의 V3 노드 스키마 기본값 크래시 수정**: 코어 V3 노드가 새 필수
  입력을 추가하면(예: `ImageScaleToTotalPixels`의 `resolution_steps`) 직접 호출 시
  `TypeError`로 터졌습니다. 이제 헬퍼가 INPUT_TYPES 기본값을 실행기처럼 채우고 V3
  normalizer 시그니처를 해석해, 코어가 위젯을 추가해도 모든 폴드가 안 깨집니다.
- **`toobusy ZIT ControlNet` pose 전처리 KeyError 수정**: 공용 `_call_node`가
  미리보기 UI가 있는 노드의 `{"ui": ..., "result": (...)}` 반환을 튜플로 풀지
  않아 DWPose(controlnet_aux) 호출 후 `result[0]`이 `KeyError: 0`으로 터졌습니다.
  헬퍼가 이제 dict-result와 V3 NodeOutput을 모두 출력 튜플로 정규화합니다(미리보기
  출력이 있는 모든 코어/커스텀 노드에 적용).
- **`toobusy Flux2 Klein` 실행 불가 버그 수정**(검수): 레퍼런스 컨디셔닝이 백엔드에
  존재하지 않는 서브그래프 UUID 클래스를 호출하고 있었음 → 원본 워크플로우의 실제
  체인(`ImageScaleToTotalPixels`(lanczos·1MP) → `VAEEncode` → `ReferenceLatent`)
  으로 교체. 내부 CLIP 로더 타입 `lumina2` → `flux2` 수정, 자체 `_call_node` 사본을
  V3 기본값 채움이 포함된 공용 헬퍼로 교체.

### Changed
- `toobusy Z-Image Turbo`에 **컨디셔닝/레이턴트 입력 추가**: `positive_override`/
  `negative_override`(CONDITIONING — 연결 시 해당 프롬프트 텍스트 무시, 둘 다
  연결 + LoRA 없음이면 텍스트 인코더 로드 자체를 스킵)와 `latent_override`
  (LATENT — image 입력보다 우선, 크기는 레이턴트를 따르고 `denoise`가 변환 강도).
  Z-Image → Hires Upscale → **다시 Z-Image(latent in)** 로 외부 샘플러 없이
  하이레즈 픽스 루프가 닫힙니다. (운영자 피드백)
- **모델 기본값 자동 감지를 전 노드로 확대**: `_scan_for`(퍼지 스캔)를 공용 모듈로
  승격하고 `toobusy Ideogram4 T2I`(조건/무조건 모델 구분 포함)와 `toobusy Flux2
  Klein`에 적용. 새 노드를 꺼내면 폴더에서 알맞은 모델이 자동 선택됩니다.
- `toobusy Flux2 Klein`에 passthrough 출력 추가(`model`/`model_clean`/`clip`/
  `vae`/`positive`) — Z-Image Turbo와 같은 규약, 기존 슬롯 순서 유지.
- `toobusy Z-Image Turbo`의 **모델 기본값 자동 감지** 개선: 정확한 파일명 일치
  대신 퍼지 스캔(zimage/z-image/z_image + turbo/textEncoder/vae 등)으로 모델
  폴더에서 Z-Image 파일을 찾아 새 노드의 기본값으로 잡습니다. 파일명/폴더
  구성이 달라도(z_image_bf16, ZIT/zImage_* 등) 처음부터 올바른 모델이 선택됩니다.
  (운영자 피드백)
- `toobusy Z-Image Turbo`에 **passthrough 출력 6개 추가**: `model`(LoRA+shift+
  zit_control까지 — 이 노드가 실제 샘플링한 그 모델), `model_clean`(로드 직후
  원본 — 2차 패스에서 LoRA를 갈아끼울 때), `clip`/`vae`, `positive`/`negative`
  (인코딩된 컨디셔닝). `toobusy Hires Upscale`(vae)나 2차 샘플러 패스에 외부
  로더/CLIPTextEncode 없이 바로 연결됩니다. 기존 출력 슬롯 순서는 유지(뒤에 추가).
  주의: zit_control 포함 `model`은 컨트롤 맵이 해당 런 해상도에 묶여 있어 다른
  해상도 2차 패스엔 `model_clean` 권장. (운영자 피드백)
- `toobusy ZIT ControlNet` UI 정리: Basic 표면은 타입별 **스위치 + 스트렝스**만
  남기고, 전처리 토글 3개("이미 만든 컨트롤 맵" 모드)·전처리 해상도·canny
  임계값은 `Show advanced settings` 뒤로 이동했습니다(기본 동작 불변). 우상단
  info 배지 추가. (운영자 피드백)

### Added
- **`toobusy Paint Canvas`** 신규 노드: 그래프 맨 앞단의 오픈캔버스풍 페인팅 노드.
  필압 브러시/지우개/스포이드, 레이어(순서/불투명도/병합), 줌·팬, Undo/Redo,
  **자동저장 온오프 토글**(끄면 Save 버튼으로만 커밋). 출력 image(합성) +
  painted_mask(칠한 영역) + canvas_data. 그린 그림이 큐마다 ZIT ControlNet /
  img2img 입력으로 들어가는 "AI가 완성해주는" 루프의 입구.
- **`toobusy ZIT ControlNet`** 신규 노드: Z-Image Turbo 앞에 붙는 depth/canny/pose
  컨트롤 모듈. 슬롯별 이미지 입력+스위치+스트렝스, 내부 전처리(MiDaS/DWPose는
  controlnet_aux, Canny는 코어 폴백)와 결과 미리보기, Fun-ControlNet-Union 모델
  패치 번들(`ZIT_CONTROL`) 출력. 여러 슬롯 동시 ON 시 패치 누적으로 서로 다른
  컨트롤 이미지를 중첩 적용. `toobusy Z-Image Turbo`에 optional `zit_control`
  입력 추가 — 연결 시 최종 모델(override/LoRA 포함)에 생성 해상도로 리사이즈된
  컨트롤 맵 패치 적용, **미연결 시 기존 동작 불변**(회귀 테스트 보장).
- **`toobusy Hires Upscale`** 신규 노드: 하이레즈 픽스 전처리 콤보
  (UpscaleModelLoader → ImageUpscaleWithModel → ImageScaleBy → VAEEncode, 4노드)를
  1노드로 접었습니다. Remacri 기본 선호, `scale_by` 0.50 기본(4x 모델 → 2x),
  1.0이면 리샘플 생략, `upscale_model` override 소켓, image/latent/width/height 출력.

## [0.2.9] - 2026-06-12

### Added
- **`toobusy Wan SCAIL Extend Sampler`** 신규 노드: Wan 2.1 SCAIL-2 영상의 생성+익스텐드
  그래프(~22 코어 노드 + Get/Set 배선)를 1노드로 접었습니다. 익스텐드 청크는
  `＋ Add / ✕ Remove` 동적 슬롯(최대 8), offset/previous_frames 체이닝 내부 자동,
  Reinhard LAB 이음새 색보정 내장, 총 프레임 readout + 모드 표시, info 배지.
  `replacement_mode`(animation/replacement)는 Basic 노출이며 마스크 배경 규약
  불일치 시 콘솔 경고를 냅니다. 최신 코어의 SCAIL-2 `WanSCAILToVideo` 필요
  (구코어에선 명확한 업데이트 안내 에러). 예제 풀 그래프 `wan21_scail2.json` +
  결과 영상 추가. (PR #45, #47)

- `toobusy Storyboard Board`에 **keyframes 출력**: 보드의 이미지 카드를 `K`로 키프레임
  마킹(순번 배지)하면 마킹 순서대로 `width x height`에 피팅된 IMAGE 배치로 출력됩니다
  (`keyframe_fit`: crop/pad/stretch). 이미지 → 키프레임 → 영상 흐름의 다리.
  익스포트 텍스트에 한글 폰트(맑은 고딕) 폴백 추가. (PR #46)
- `toobusy Ideogram Layout Builder`에 **레퍼런스 이미지 백드롭**: 캔버스 밑에 이미지를
  깔고(투명도 조절) 그 위에 박스를 트레이싱. Import polished에서 PNG를 불러오면 그
  PNG가 레퍼런스로 자동 적용(Apply 시). 이미지는 가이드 전용으로 워크플로우/프롬프트에
  들어가지 않고 브라우저 localStorage에만 저장됩니다. (PR #43, #44)

### Changed
- **`toobusy Storyboard Board` 전면 리디자인** — Excalidraw 스타일 무한 화이트보드로
  재작성했습니다. 무한 캔버스 팬/줌(휠 = 커서 기준 줌, Space 드래그 = 팬), DPR 대응
  선명 렌더, 도트 그리드, 출력 프레임 표시, 플로팅 아이콘 툴바(드래그로 도형 그리기),
  인라인 텍스트 편집(팝업 제거), Ctrl+V 이미지 붙여넣기(자동 다운스케일 임베드),
  컨텍스트 속성 패널(색 스와치/선 두께/폰트 프리셋), 4코너 비율 유지 리사이즈, 이미지
  카드 라운드+그림자, info 배지. 그래프 줌 상태와 무관하게 좌표가 정확하며 노드 세로
  리사이즈를 따라갑니다. 기존 `board_data` 스키마와 출력 슬롯 순서는 그대로 호환.
  (PR #46, #48)

## [0.2.8] - 2026-06-09

### Added
- `toobusy Z-Image Turbo`와 `toobusy Ideogram4 T2I`에 **외부 모델 override 입력**을
  추가했습니다(Z-Image: `model/clip/vae_override`, Ideogram4: `model/uncond_model/clip/vae_override`).
  연결된 override는 해당 내부 로더(`UNETLoader`/`CLIPLoader`/`VAELoader`)를 건너뛰고,
  비워 두면 기존처럼 이름 위젯으로 내부 로드합니다. GGUF 등 다른 로더의 MODEL/CLIP/VAE를
  결합 없이 흘려보낼 수 있습니다. (PR #33)
- `toobusy Z-Image Turbo`에 **직접 해상도 입력**(`width`/`height`)을 추가했습니다. 둘 다
  `> 0`이면 `ratio_preset`+`megapixels` 대신 그 값을 사용합니다(`divisible_by`로 반올림).
- `toobusy Z-Image Turbo`에 **img2img 자동 전환**을 추가했습니다. 선택형 `image` 입력을
  연결하면 `VAEEncode`로 시작 latent을 만들고(`EmptyLatentImage` 대신) `denoise`가 변환
  강도가 됩니다. `width`/`height` 지정 시 소스를 그 크기로 스케일(center crop), 미지정 시
  소스 크기를 따릅니다. 해상도 미리보기 위젯이 t2i/img2img·manual 상태를 표시합니다.
- override / 해상도 / img2img 동작을 검증하는 회귀 테스트
  `tests/test_model_overrides.py`, `tests/test_zimage_resolution_i2i.py`를 추가하고
  CI에서 `tests/test_*.py`를 자동 검출해 실행합니다(ComfyUI 런타임 불필요).
- `toobusy Z-Image Turbo` 예제 워크플로우(`docs/workflows/z_image_turbo.json`)와 워크플로우
  이미지·결과 샘플을 추가하고 README 노드 소개에 연결했습니다.

### Changed
- `toobusy Z-Image Turbo`의 **Basic/Advanced 구성을 재정비**했습니다. 모델 로드 슬롯
  (`model_name`/`clip_name`/`vae_name`)을 **기본 노출**해 초보자가 어떤 모델이 물렸는지
  바로 확인할 수 있게 했고(Advanced에 숨기지 않음), Advanced에는 expert 튜닝
  (`divisible_by`/`cfg`/`sampler_name`/`scheduler`/`denoise`/`aura_shift`)과 LoRA만 남겼습니다.
- 모델 **override 입력 소켓**(`model_override`/`clip_override`/`vae_override`)을 Advanced에서만
  노출하도록 바꿨습니다. 초보자에겐 불필요한 고급 입력이라 Basic에서는 숨기되, 이미 연결된
  소켓은 절대 제거하지 않아 기존 그래프가 깨지지 않습니다. `image`(img2img) 입력은 그대로 노출.
- 항상 떠 있던 2줄 `folds` 설명 텍스트를 **노드 우상단 `i` info 배지 + 호버 툴팁**으로
  교체했습니다(노드 화면을 덜 어지럽게). 툴팁은 노드 본문을 가리지 않도록 노드 **오른쪽
  바깥**에 표시됩니다.
- `toobusy Z-Image Turbo`가 더 이상 **LoRA를 자동으로 켜지 않습니다**(`lora_slots` 기본 0,
  `lora_1_enable` 기본 False). 슬롯 1은 추천 LoRA 이름으로 미리 채워져 있어 `Add LoRA slot`
  한 번이면 바로 쓸 수 있지만, 켜기 전에는 아무 LoRA도 적용되지 않습니다.
- `resolution_readout`을 **클릭 불가한 표시 전용 + 강조 색**으로 바꿨습니다(클릭 시 편집
  입력칸이 뜨던 미완성 느낌 제거).
- info 배지 호버 툴팁에 **너무바쁜베짱이 시그니처**를 절제해서 넣었습니다 — 제목줄 +
  fold 설명 + 얇은 구분선 아래 희미한 `fold the graph — 너무바쁜베짱이` 한 줄. 본문에는
  공통 accent 색(readout·배지·툴팁 제목)만 잔잔하게 유지.

### Removed
- **`toobusy HF Model Auto Loader` 노드를 제거**했습니다(`toobusy/Setup` 버킷도 함께 제거).
  인터넷에서 모델을 직접 내려받는 경로가 Registry 보안 스캔에서 불필요한 마찰을 일으켰고,
  모델 안내는 워크플로우 Note 노드 방식이 더 명확합니다. 함께 `huggingface_hub` 의존성도
  제거해 패키지를 의존성 0으로 만들었습니다.

### Fixed
- CI byte-compile 목록에서 빠져 있던 `ideogram_prompt_polish_node`를 추가했습니다.
- 예제 워크플로우 `korean_scene_to_ideogram4.json`를 모델 링크 Note 노드 방식으로 갱신하고,
  Ideogram4 T2I 위젯을 0.2.7 LoRA 슬롯 추가 이후 레이아웃(위젯 36개)에 맞춰 재정렬했습니다.
  이전 예제는 LoRA 슬롯 추가 전(위젯 20개)으로 저장돼 있어 로드 시 `mu`/`cfg_override` 값이
  `lora_*_name` 칸으로 밀려 "유효하지 않은 LoRA"로 실행이 막혔습니다.

## [0.2.7] - 2026-06-08

### Added
- `toobusy Ideogram4 T2I`에 Z-Image Turbo와 같은 최대 5개 **LoRA 슬롯**을 추가했습니다.
  활성화된 슬롯은 `LoraLoader` 체인으로 conditional 모델과 CLIP에 순서대로 적용되며,
  `ideogram4_unconditional` 모델은 원본 checkpoint를 유지합니다.

### Changed
- **LoRA 슬롯 삭제를 직관적으로** 개선했습니다(Ideogram4 T2I · Z-Image Turbo). 전역
  `Remove LoRA slot`(항상 마지막 슬롯만 숨기고 값은 남김)을 **슬롯별 `✕ Remove LoRA N`**
  버튼으로 교체 — 보고 있는 슬롯을 직접 삭제하면 아래 슬롯들이 위로 당겨지고 비워진
  마지막 슬롯은 초기화됩니다. `Add LoRA slot`은 그대로 유지됩니다.
- Layout Builder 요소별 색상 팔레트를 고정 3칸에서 **`+`로 최대 5색까지 동적 추가**하는
  방식으로 바꿨습니다. 각 swatch에 제거 버튼을 제공하고, `Clear colors`는 전체 unset으로
  되돌립니다.

### Fixed
- 요소 팔레트가 5색 한도에 도달했을 때 `+` 버튼이 비활성으로 보여도 계속 추가되던 문제를
  막았습니다(`makeButton`의 `pointerup` 경로가 `disabled`를 존중).
- 처음 unset 상태에서 색을 추가해도 `Clear colors`가 disabled로 남아있던 상태 갱신 버그를
  수정했습니다.

## [0.2.6] - 2026-06-08

### Fixed
- Layout Builder **Load PNG**가 ComfyUI PNG metadata 전체를 재귀 검색하다가, 실제 생성에
  연결되지 않은 예전 `PrimitiveStringMultiline` JSON을 먼저 불러올 수 있던 문제를
  수정했습니다. 이제 ComfyUI `prompt` metadata에서는 `ToobusyIdeogram4T2I.prompt`에
  연결된 `IdeogramLayoutBuilder` 상태를 우선 복원하고, 그 후에만 일반 JSON 탐색으로
  fallback합니다.
- ComfyUI에서 PNG/workflow를 열 때 저장된 Layout Builder `widgets_values`가 커스텀
  에디터 UI에 늦게 반영되는 경우를 보완해, 캔버스 박스/scene/해상도가 저장 당시 상태로
  다시 동기화되도록 했습니다.

## [0.2.5] - 2026-06-08

### Changed
- Ideogram Layout Builder의 기본 캔버스 해상도를 `1024 x 1024`에서
  `2048 x 2048`로 올렸습니다. 1K square preset은 보조 preset으로 남겼습니다.

### Added
- Layout Builder `Import polished` 모달에 **Load PNG**를 추가했습니다. ComfyUI PNG
  metadata(`prompt`/`workflow` 등) 안의 Prompt Polish / Ideogram JSON payload를 찾아
  기존 JSON 검증·미리보기·`Apply` 흐름으로 불러올 수 있습니다.

## [0.2.4] - 2026-06-07

### Added
- 예제 워크플로우 `docs/workflows/korean_scene_to_ideogram4.json` — 한국어 장면 →
  Prompt Polish → (Import polished로) Layout Builder → Ideogram4 T2I 흐름. 운영자가
  실제로 돌려 검증한 flagship 워크플로우. README/예제 문서에서 링크.

### Changed
- Keyframe Maker에 `keyframe_prompt_line` 리스트 출력을 추가했습니다. 기존
  `keyframe_prompts` 여러 줄 텍스트를 앞뒤 공백 제거 + 빈 줄 제거 후 한 줄씩
  하위 노드로 보낼 수 있습니다.
- 별도 splitter였던 `toobusy Prompt Lines` 노드는 제거했습니다. 키프레임 프롬프트
  분배까지 Keyframe Maker 안으로 접어, Plan 흐름의 노드 수를 줄였습니다.
- Layout Builder에 현재 캔버스/scene/style/palette/해상도를 새 노드 기본 상태로
  되돌리는 `Reset` 버튼을 추가했습니다. 저장된 preset은 지우지 않습니다.

## [0.2.3] - 2026-06-07

### Changed
- Layout Builder의 **`Import polished`** 흐름을 한 줄 `window.prompt()`에서 큰
  붙여넣기 모달로 개선했습니다. Prompt Polish / Ideogram JSON을 넉넉한 textarea에
  붙여넣고, JSON 파싱 오류와 payload 형식 오류를 인라인으로 확인한 뒤, 유효할 때만
  scene·요소 수 미리보기를 보고 `Apply`할 수 있습니다. `Apply` 전에는 현재 캔버스와
  scene/style/background/palette 필드를 교체하지 않습니다.

## [0.2.2] - 2026-06-07

### Added
- Ideogram Layout Builder에 **`Import polished`** 버튼: Prompt Polish가 만든
  Ideogram JSON을 붙여넣으면, 요소 개수·scene 요약으로 **미리보기 확인** 후
  `Apply`할 때만 캔버스(박스)+scene/style/background/palette 필드에 반영됩니다.
  확인 전에는 현재 작업 내용을 보존(덮어쓰지 않음). bbox 순서도 자동 변환.
  → Coda의 v0.3 "작업대에서 preview→Apply" UX의 sound 부분.
  (빌더 안에서 LLM을 직접 호출하는 *라이브 버튼*은 서버 라우트+모델 접근 설계가
  필요해 ComfyUI 실구동 검증과 함께 별도 단계로 진행 예정.)

## [0.2.1] - 2026-06-07

### Added
- **Plan 파이프라인 연결**: Ideogram Layout Builder가 이제 Prompt Polish의 전체
  Ideogram payload(`compositional_deconstruction.elements`)를 입력으로 받아들이고,
  bbox를 Ideogram 순서 `[y,x,y,x]` → 캔버스 순서 `[x,y,x,y]`로 올바르게 변환합니다.
  덕분에 `Prompt Polish → Layout Builder → Ideogram4 T2I`가 좌표까지 정확히 연결됩니다
  (한국어 장면 → 구조화 레이아웃 → 이미지). 기존 입력 형식(배열, `{elements}`)은 그대로 동작.

### Changed
- Prompt Polish: `preserve_intent`가 켜졌을 때 한국어의 정서·분위기·관계성 뉘앙스를
  보존하고 서구식 stock 프롬프트로 평탄화하지 않도록 지시를 강화.

## [0.2.0] - 2026-06-07

### Added
- **toobusy Ideogram Prompt Polish** (`toobusy/Plan`): 한국어/영어 장면 한 줄을
  Ideogram 4 친화 **영어 구조화 프롬프트 JSON**으로 접는 노드. 한국어 기획 →
  영어 번역 → Ideogram 구조화의 멀티스텝을 한 노드로. 입력 장면은 절대 덮어쓰지
  않고(출력만 따로 나옴) 원본을 보존. LLM이 마크다운 펜스/잡설/트레일링 콤마로
  깨진 JSON을 뱉어도 견고하게 추출·검증하고, 실패 시 장면으로 graceful 폴백 +
  명확한 오류 메시지(`clip`에 텍스트 생성 모델 필요). 스타일 모드(Literal/
  Cinematic/Product/Character/Poster), 언어(Auto/Korean/English), `preserve_intent`,
  `fill_missing_fields` 옵션.

## [0.1.1] - 2026-06-07

### Changed
- ComfyUI Registry에 `neobabae` 퍼블리셔로 첫 발행 (`[tool.comfy].PublisherId`).

## [0.1.0] - 2026-06-07

첫 패키징 릴리스. 정체성을 **"번거로운 멀티스텝을 노드 하나로 접는다"**로 정하고,
노드 메뉴를 `toobusy/Plan` · `toobusy/Make` · `toobusy/Setup` 세 갈래로 정리.

### Added
- 패키징: `pyproject.toml`(Registry), `LICENSE`(MIT), `.comfyignore`, `CHANGELOG`, GitHub Actions CI(Python compile + JS 문법 체크).
- Ideogram Layout Builder: 요소 역할(role) 힌트, 레이아웃 템플릿, `strict_text`/`reinforce_text`/`include_global_palette` 토글, 레이어 리스트, 키보드 단축키.
- Storyboard Board: 텍스트 사후 편집, 리사이즈 핸들, 속성 바(색/채움/선/폰트/z-order/복제), Undo/Redo, 프리뷰 텍스트 래핑(익스포트와 일치).
- Z-Image Turbo: Basic/Advanced 토글, 해상도 미리보기 readout.
- LTX2.3 Empty AV Latents: 해상도/길이/오디오 readout + 커스텀 오디오 미연결 경고.
- LTX2.3 Compact AV Sampler: `manual_sigmas` Advanced 숨김 + SIGMAS 연결 시 오버라이드 표시.
- Keyframe Maker: 생성 결과를 override로 복사하는 버튼.

### Changed
- 카테고리 7개 파편 → 3버킷(Plan/Make/Setup)으로 통합.
- HF Model Auto Loader: `download_if_missing` 기본값 `True` → `False`(스캔/리포트 우선), `Open on Hugging Face` 버튼으로 정정.
- Ideogram4 T2I 표시명을 "(local model)"로 명확화 — 웹 API가 아니라 로컬 모델 샘플러임.
- 모델 경로 기본값의 백슬래시를 포워드슬래시로 변경(크로스플랫폼).
- README 전면 한글화 + 접기 정체성 반영.

### Fixed
- Layout Builder: 최소 크기(40px) 박스가 백엔드에서 조용히 삭제되던 문제, 깨진 `elements_json`이 그래프 전체를 중단시키던 문제, 해상도 입력이 타이핑 중 클램프되던 문제.
- HF Model Auto Loader: 존재하지 않는 위젯을 참조해 동작하지 않던 다운로드 버튼.
- 죽은 중복 JS 파일 및 미사용 `WEB_DIRECTORY` 정리.
