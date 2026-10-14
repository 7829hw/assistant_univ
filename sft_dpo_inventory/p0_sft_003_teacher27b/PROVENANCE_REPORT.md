# 27B teacher provenance 조사 결과

2026-10-14. 계획 `PROVENANCE_PLAN.md`(커밋 `da95c22`). 근거 목록은 `provenance.json`.

모든 조사는 읽기 전용이었다. pull, download, copy, import를 하지 않았고, 외부 registry 조회와 웹 검색도 하지 않았다.

## 1. 판정: **PROVENANCE_PARTIAL**

**확인한 것**

- alias `qwen3.8:27b`
- digest `aaee06c39dcf2437cde036998d960e1fc1494b8191be7cc9657d01e509097813`
- Q4_K_M, runtime metadata(크기, VRAM, context, capabilities, Modelfile 파라미터)
- 이 모델이 **이름으로 Ollama registry에서 pull됐다는 흔적**(사용자 shell history의 `docker exec -it ollama ollama pull qwen3.8:27b`)

**확인하지 못한 것**

- 그 registry tag(`library/qwen3.8:27b`)가 digest `aaee06c3…`로 해석된다는 근거.
  - registry tag는 바뀔 수 있다. 같은 이름을 다시 pull해도 같은 artifact라는 보장이 없다.
- 현재 서버에 있는 과거 manifest·blob 복사 원본. Ollama store, 홈, 옛 작업 경로 어디에도 없다.

따라서 EXACT도 COPY_SOURCE도 아니다. 후보 원본은 하나뿐이라 CONFLICT도 아니다.

## 2. 추적 경로

| 순서 | 근거 | 내용 |
|---|---|---|
| 1 | git `7c7cec0`(2026-09-15) | alias 최초 등장. 모델별 정확도 표에 17.7 GB로 이미 로컬에 있었다(gemma4:e4b·qwen3.5:9b·qwen3:8b·gemma4:12b와 함께). pull·출처 기록 없음 |
| 2 | shell history 1409–1443행 | `ollama pull gemma4:e4b` 다음에 `ollama pull qwen3.8:27b`, `ollama run qwen3.8:27b`(시각 기록 없음). 1의 비교 측정 무렵으로 보인다 |
| 3 | git `c1f2a08`(2026-10-03, grounding_v9) | digest `aaee06c39dcf…` 최초 기록(평가 meta의 `/api/tags` digest) |
| 4 | grounding_v11 meta | size_vram 18,542,682,438, context 262,144, capabilities completion·vision·tools·thinking, Modelfile 파라미터 |
| 5 | README 검증한 실행 명세 | T2PC 기본 모델, digest `aaee06c39dcf2437…`, Ollama 0.34.4 |
| 6 | pilot_prep_003 teacher summary | teacher 실행: digest 전체 값, Q4_K_M, Ollama 0.35.1, think true, temperature 0.6, 표본 8 |
| 7 | git 전 branch `-S`/`-G` | 27B의 Modelfile·`ollama create`·blob·registry 경로·hf.co 기록 없음 |
| 8 | 현재 서버 | 컨테이너 store(`/data/hwkim/ollama`, bind `/root/.ollama`)에는 qwen3:8b만 있고 `sha256-aaee…` blob 없음. `~/.ollama`에는 key·cache뿐. 옛 경로 `/home/hwkim/sftdpo_work` 없음. 컨테이너 로그에 27b 줄 없음 |

- 이 장비는 2026-10-08부터 쓴 새 장비다(결정 56). 과거 27B는 옛 장비 Ollama store에 있었을 것이다.
- shell history는 정확한 문자열만 검색했다. 다른 내용은 옮기지 않았다.

## 3. digest와 원본의 연결 근거

- **직접 연결 근거는 없다.** digest는 평가·teacher 실행 때 `/api/tags`에서 기록됐다. pull 기록(history)에는 digest가 없다.
- 같은 이름의 registry tag가 그때와 같은 manifest를 가리키는지는 반입 전에 확인해야 한다.

## 4. 같은 artifact임을 증명할 수 있는 방법(사용자 결정 필요)

**(가) 옛 장비 원본에서 복사**

- 옛 장비 Ollama store의 manifest와 blob을 복사한다. 반입 뒤 `/api/tags` digest가 `aaee06c3…`와 정확히 같아야 한다.
- 가장 확실하다. 옛 장비 위치와 접근을 사용자가 지정해야 한다.

**(나) registry tag를 반입 전에 검증**

- `library/qwen3.8:27b`의 manifest(수 KB)만 받아 sha256이 `aaee06c3…`와 정확히 같은지 확인한다. 같을 때만 pull한다.
- 이번 단계에서는 외부 조회도 하지 않았다. 조회와 pull 모두 사용자 승인이 필요하다.
- pull 뒤에도 `/api/tags` digest가 정확히 같아야 한다.

**(다) 원본 불명으로 보류**

- 이름만 보고 pull하지 않는다(결정 74).
