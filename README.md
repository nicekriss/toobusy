# toobusy

ComfyUI 커스텀 노드 저장소입니다.

## 설치

`ComfyUI/custom_nodes` 경로에 이 저장소를 `toobusy` 폴더명으로 클론한 뒤 ComfyUI를 재시작하세요.

```bash
git clone https://github.com/nicekriss/toobusy.git toobusy
```

> 이 저장소는 ComfyUI가 `custom_nodes/toobusy/__init__.py`를 직접 import 하는 구조를 사용합니다.
> 따라서 루트의 `__init__.py` 파일이 반드시 있어야 하며, 삭제되면 로딩 에러가 발생합니다.

실제 노드는 `hf_model_auto_loader`, `ideogram_layout_builder`, `ltx23_compact_sampler_node`에 있습니다.

## 포함된 노드

- `HF Model Auto Loader`: ComfyUI 모델 폴더에서 필요한 모델 파일을 찾고 상태를 알려주는 보조 노드입니다.
- `Ideogram Layout Builder`: Ideogram 4용 structured JSON prompt를 시각적인 bbox 캔버스로 만드는 노드입니다.
- `LTX2.3` compact nodes: LTX2.3 워크플로우의 prompt, latent, sampler 구간을 단순화하는 노드 묶음입니다.

## Ideogram Layout Builder

ComfyUI에서 `toobusy / ideogram / Ideogram Layout Builder`로 추가할 수 있습니다.

이 노드는 1000 x 1000 기준 캔버스에서 박스를 추가/이동/리사이즈하고, 각 박스에 텍스트/설명/색상 팔레트를 입력하면 Ideogram 4 워크플로우가 기대하는 JSON 문자열을 출력합니다.

출력 예시는 다음 구조입니다.

```json
{
  "high_level_description": "",
  "style_description": {
    "aesthetics": "",
    "lighting": "",
    "photo": "",
    "medium": "",
    "color_palette": []
  },
  "compositional_deconstruction": {
    "background": "",
    "elements": [
      {
        "type": "obj",
        "bbox": [100, 100, 900, 300],
        "desc": "large headline text",
        "color_palette": ["#FFFFFF", "#111111"]
      }
    ]
  }
}
```

추천 사용 방식:

1. 전체 장면, 스타일, 조명, 배경을 먼저 입력합니다.
2. 제목/제품/서브텍스트처럼 중요한 요소마다 박스를 하나씩 만듭니다.
3. 이미지 안에 들어갈 글자는 `Text` 필드에 정확히 입력합니다.
4. 결과 `ideogram_json` 출력을 Ideogram 4 워크플로우의 prompt 입력에 연결합니다.
