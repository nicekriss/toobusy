# 예제 워크플로우

각 노드가 **무엇을 접는지** 한눈에 보여주는 검증된 워크플로우를 여기에 둡니다.
워크플로우 파일은 사용자가 바로 열어 구조와 연결 방식을 확인할 수 있는 실행 예제입니다.

## 넣는 방법

1. ComfyUI에서 노드를 실제로 배선해 동작을 확인합니다.
2. 메뉴 → **Workflow → Export (.json)** 로 내보냅니다.
3. 이 폴더에 `노드이름.json` 으로 저장합니다 (예: `z_image_turbo.json`).
4. 루트 README에서 해당 노드 섹션에 링크합니다.

## 들어있는 워크플로우

- [x] **`korean_scene_to_ideogram4.json`** — 한국어 장면 → Prompt Polish → (Import polished로) Layout Builder → Ideogram4 T2I.
  한국어 한 줄이 영어 구조화 프롬프트 + 레이아웃 + 이미지로 흐르는 flagship 흐름. 필요한 모델은 워크플로우 안 Note 노드에 링크되어 있음(Comfy-Org Ideogram4 / Qwen3-VL / Gemma4 / Flux2 VAE).
  - 흐름: `Prompt Polish`의 `ideogram_json` 출력을 복사 → `Layout Builder`의 **Import polished**에 붙여넣고 박스 확인/수정 → `Ideogram4 T2I`로 생성.
- [x] **`z_image_turbo.json`** — `toobusy Z-Image Turbo` 한 노드로 t2i 그래프(~10노드)를 접는 예제.
  `image` 입력에 Load Image를 연결하면 자동으로 img2img로 전환됨. 필요한 모델은 워크플로우 안 Note 노드에 링크되어 있음(Comfy-Org Z-Image Turbo / Qwen3-4B / Flux VAE).

## 권장 목록 (추가로 만들면 좋은 것)

- [ ] `ltx_compact_av_sampler.json` — 샘플링 블록 8노드 → 1노드
- [ ] `keyframe_maker.json` — 5단계 기획 → 1노드 (텍스트 생성 CLIP 연결 포함)
- [ ] `storyboard_board.json` — 인라인 보드 → IMAGE export
- [ ] `ideogram_layout_to_t2i.json` — Layout Builder → Ideogram4 T2I 연결
