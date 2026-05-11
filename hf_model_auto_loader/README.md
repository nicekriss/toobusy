# HF Model Auto Loader + Preset (ComfyUI Custom Node)

원하는 모델을 **프리셋으로 선택**하거나 직접 파일명을 넣어서, 로컬 ComfyUI 모델 폴더에서 탐색하고 자동 로드까지 수행합니다.

- 있으면: `found=True`, 경로 반환
- 체크포인트 카테고리 + `autoload_checkpoint=True`면: MODEL/CLIP/VAE까지 즉시 로드
- 없으면: `MISSING` + Hugging Face URL 출력
- 노드 버튼: **Download (HF)**

## 설치

이 저장소를 `ComfyUI/custom_nodes/drawings`로 클론 후 재시작하세요.

## 입력

- `preset`: 자주 쓰는 모델 프리셋
- `model_name`: 프리셋 무시하고 직접 지정할 파일명 (비우면 프리셋값 사용)
- `model_category`: 검색 카테고리
- `huggingface_url`: 다운로드 링크 (비우면 프리셋값 사용)
- `autoload_checkpoint`: 체크포인트 발견 시 자동 로드 여부

## 출력

- `resolved_model_path` (STRING)
- `found` (BOOLEAN)
- `status` (STRING)
- `download_url` (STRING)
- `model` (MODEL)
- `clip` (CLIP)
- `vae` (VAE)

## 동작 주의사항

- 자동 로드는 현재 **checkpoints 카테고리**에서만 수행됩니다.
- lora/controlnet/vae 등은 경로 확인까지만 하고 실제 적용은 해당 전용 로더 노드와 연결해야 합니다.
