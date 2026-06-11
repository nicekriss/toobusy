# Changelog

이 프로젝트의 주요 변경 사항을 기록합니다. (Keep a Changelog 형식, 날짜는 YYYY-MM-DD)

## [Unreleased]

### Added
- **`toobusy Wan SCAIL Extend Sampler`** 신규 노드: Wan 2.1 SCAIL-2 영상의 생성+익스텐드
  그래프(CLIPTextEncode x2 + CLIPVisionEncode + ModelSamplingSD3 + KSamplerSelect +
  BasicScheduler + 청크마다 WanSCAILToVideo→SamplerCustom→VAEDecode + 익스텐드마다
  오버랩 트리밍/Reinhard LAB 색보정 + 프레임 결합, 익스텐드 2개 기준 ~22 코어 노드)를
  하나의 노드로 접었습니다. 익스텐드 청크는 `＋ Add / ✕ Remove` 동적 슬롯(최대 8)로
  추가하며 offset/previous_frames 체이닝은 내부 자동 처리. 총 프레임 readout, 우상단
  `i` info 배지 + 시그니처 툴팁, Basic/Advanced 게이팅 포함. 회귀 테스트
  `tests/test_wan_scail_extend_sampler.py` 추가. 최신 코어의 `WanSCAILToVideo`(SCAIL-2
  확장 입력)가 필요하며, 구버전 코어에선 명확한 업데이트 안내 에러를 냅니다.
- `toobusy Ideogram Layout Builder`에 **레퍼런스 이미지 백드롭**: 캔버스 밑에 이미지를
  깔고(투명도 조절) 그 위에 박스를 트레이싱. Import polished에서 PNG를 불러오면 그
  PNG가 레퍼런스로 자동 적용(Apply 시). 이미지는 가이드 전용으로 워크플로우/프롬프트에
  들어가지 않고 브라우저 localStorage에만 저장됩니다. (PR #43, #44)

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
