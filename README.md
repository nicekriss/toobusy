# drawings

ComfyUI 커스텀 노드 저장소입니다.

## 설치

`ComfyUI/custom_nodes` 경로에 이 저장소를 `drawings` 폴더명으로 클론한 뒤 ComfyUI를 재시작하세요.

```bash
git clone <this-repo-url> drawings
```

> 이 저장소는 ComfyUI가 `custom_nodes/drawings/__init__.py`를 직접 import 하는 구조를 사용합니다.
> 따라서 루트의 `__init__.py` 파일이 반드시 있어야 하며, 삭제되면 로딩 에러가 발생합니다.

실제 노드는 `hf_model_auto_loader` 폴더에 있습니다.
