# 예제 워크플로우

각 노드가 **무엇을 접는지** 한눈에 보여주는 검증된 워크플로우를 여기에 둡니다.
(kijai 정찰에서 배운 점: "노드가 있다"보다 "이 워크플로우 열면 돌아간다"가 신뢰를 만든다.)

## 넣는 방법

1. ComfyUI에서 노드를 실제로 배선해 동작을 확인합니다.
2. 메뉴 → **Workflow → Export (.json)** 로 내보냅니다.
3. 이 폴더에 `노드이름.json` 으로 저장합니다 (예: `z_image_turbo.json`).
4. 루트 README에서 해당 노드 섹션에 링크합니다.

## 들어있는 워크플로우

- [x] **`korean_scene_to_ideogram4.json`** — 한국어 장면 → Prompt Polish → (Import polished로) Layout Builder → Ideogram4 T2I.
  한국어 한 줄이 영어 구조화 프롬프트 + 레이아웃 + 이미지로 흐르는 flagship 흐름. 필요한 모델은 워크플로우 안 Note 노드에 링크되어 있음(Comfy-Org Ideogram4 / Qwen3-VL / Gemma4 / Flux2 VAE).
  - 흐름: `Prompt Polish`의 `ideogram_json` 출력을 복사 → `Layout Builder`의 **Import polished**에 붙여넣고 박스 확인/수정 → `Ideogram4 T2I`로 생성.

## 권장 목록 (추가로 만들면 좋은 것)

- [ ] `z_image_turbo.json` — t2i 그래프 ~10노드 → 1노드 (flagship)
- [ ] `ltx_compact_av_sampler.json` — 샘플링 블록 8노드 → 1노드
- [ ] `keyframe_maker.json` — 5단계 기획 → 1노드 (텍스트 생성 CLIP 연결 포함)
- [ ] `storyboard_board.json` — 인라인 보드 → IMAGE export
- [ ] `ideogram_layout_to_t2i.json` — Layout Builder → Ideogram4 T2I 연결
