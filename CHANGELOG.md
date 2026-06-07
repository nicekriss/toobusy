# Changelog

이 프로젝트의 주요 변경 사항을 기록합니다. (Keep a Changelog 형식, 날짜는 YYYY-MM-DD)

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
