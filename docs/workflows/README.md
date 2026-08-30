# 예제 워크플로우

각 노드가 **무엇을 접는지** 한눈에 보여주는 검증된 워크플로우를 여기에 둡니다.
워크플로우 파일은 사용자가 바로 열어 구조와 연결 방식을 확인할 수 있는 실행 예제입니다.

## 넣는 방법

1. ComfyUI에서 노드를 실제로 배선해 동작을 확인합니다.
2. 메뉴 → **Workflow → Export (.json)** 로 내보냅니다.
3. 이 폴더에 `노드이름.json` 으로 저장합니다 (예: `z_image_turbo.json`).
4. 루트 README에서 해당 노드 섹션에 링크합니다.

## 들어있는 워크플로우

- [x] **`minimax_h3_single_image_6edit.json`** — MiniMax H3 Ref2V + T=1 이미지 VAE로
  한 장에 여섯 가지 편집을 생성하는 예제. `toobusy MiniMax H3 Image Latent`를 사용해
  ComfyUI 코어 수정 없이 단일 프레임 H3 AV latent를 샘플러에 공급합니다.

- [x] **`flashvsr_v11_full_bsa_long.json`** — FlashVSR v1.1 Full + BSA 장시간 영상용 2x 예제.
  `1024x576`, 21프레임 청크, 8프레임 오버랩, tiled VAE 디코드를 사용합니다. RTX 3090 24GB에서 검증했습니다.

- [x] **`wan21_scail2.json`** — Wan 2.1 SCAIL-2 모션 트랜스퍼 예제(36노드, 검증용).
  레퍼런스 이미지 + 댄스 영상 → `toobusy Wan SCAIL Extend Sampler` 중심 구성으로 베이스 + 익스텐드 흐름을 확인합니다. 결과 영상: `wan21_scail2_sample.mp4`. 최신 ComfyUI 코어(SCAIL-2) + SAM3/KJNodes/VHS 필요.
- [x] **`korean_scene_to_ideogram4.json`** — 한국어 장면 → Prompt Polish → (Import polished로) Layout Builder → Ideogram4 T2I.
  한국어 한 줄이 영어 구조화 프롬프트 + 레이아웃 + 이미지로 흐르는 flagship 흐름. 필요한 모델은 워크플로우 안 Note 노드에 링크되어 있음(Comfy-Org Ideogram4 / Qwen3-VL / Gemma4 / Flux2 VAE).
  - 흐름: `Prompt Polish`의 `ideogram_json` 출력을 복사 → `Layout Builder`의 **Import polished**에 붙여넣고 박스 확인/수정 → `Ideogram4 T2I`로 생성.
- [x] **`z_image_turbo.json`** — `toobusy Z-Image Turbo` 한 노드로 t2i 그래프(~10노드)를 접는 예제.
  `image` 입력에 Load Image를 연결하면 자동으로 img2img로 전환됨. 필요한 모델은 워크플로우 안 Note 노드에 링크되어 있음(Comfy-Org Z-Image Turbo / Qwen3-4B / Flux VAE).

- [x] **`2BZ_H3_character_sheet_2stage_v1.json`** / **`..._v1_EN.json`** — MiniMax H3로 캐릭터 시트를
  만드는 2단계 워크플로우. 1단계는 얼굴 사진 1장 + 의상 이미지 1장으로 전면·측면·후면 3뷰를 만들고,
  2단계(기본 OFF)는 포즈·소품·배경 패널 1~4장을 더해 최종 16:9 시트로 합성합니다.
  `toobusy MiniMax H3 Image Latent`(T=1 이미지 VAE)와 `toobusy MiniMax H3 Semantic Reference`를 사용하며
  커스텀 노드 `toobusy` v0.4.9 이상(ComfyUI Manager에서 `toobusy` 검색)과 `rgthree`가 필요합니다. RTX 3090 24GB에서 1단계 약 100~125초, 2단계 약 105초.
  `_EN` 은 노드/그룹/노트를 전부 영어로 옮기고 한국어 자동번역 단계를 뺀 해외 배포용입니다.
  원본 아이디어: [r/StableDiffusion 게시글](https://www.reddit.com/r/StableDiffusion/comments/1vr1i18/minimax_h3_as_image_editor_6_edits_in_one_shot_at/)

## 권장 목록 (추가로 만들면 좋은 것)

- [ ] `ltx_compact_av_sampler.json` — 샘플링 블록 8노드 → 1노드
- [ ] `keyframe_maker.json` — 5단계 기획 → 1노드 (텍스트 생성 CLIP 연결 포함)
- [ ] `storyboard_board.json` — 인라인 보드 → IMAGE export
- [ ] `ideogram_layout_to_t2i.json` — Layout Builder → Ideogram4 T2I 연결
