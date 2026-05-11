# HF Model Auto Loader (ComfyUI Custom Node)

ComfyUI 모델 폴더를 스캔해서 워크플로우에서 지정한 모델 파일이 있는지 확인합니다.

- 있으면: `found=True` 와 실제 경로(`resolved_model_path`) 반환
- 없으면: `found=False` 와 `MISSING` 상태 반환
- 노드 내 버튼: **Download (HF)** 클릭 시 입력한 Hugging Face URL 열기

## 설치

`custom_nodes/hf_model_auto_loader` 폴더를 ComfyUI의 `custom_nodes` 아래에 넣고 ComfyUI를 재시작하세요.

## 입력

- `model_name`: 찾을 모델 파일명 (예: `myModel.safetensors`)
- `model_category`: 검색할 Comfy 모델 카테고리 (`checkpoints`, `loras`, `vae`, ...)
- `huggingface_url`: 모델 다운로드 링크

## 출력

- `resolved_model_path` (STRING): 발견된 모델 절대경로, 없으면 빈 문자열
- `found` (BOOLEAN): 발견 여부
- `status` (STRING): 상태 메시지
- `download_url` (STRING): 입력한 URL 그대로 반환

## 참고

이 노드는 "모델 존재 확인 + 경로 반환" 중심입니다.
실제 모델을 로드해 sampler까지 연결하는 자동 체인은 워크플로우 구조(체크포인트/LoRA/ControlNet 별 로더 차이)에 따라 추가 구현이 필요합니다.
