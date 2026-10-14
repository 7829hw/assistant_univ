# G2 기준 보완과 재개 계획

고정: 2026-10-14, G3 실행 전. 결정 81. `IMPORT_AND_TEACHER_PLAN.md`(`ca05ece`)를 보완한다. 기존 G2 FAIL 기록(`import/integrity.json`, `7258410`)과 `TEACHER_RUN_REPORT.md`(`a2a4bbc`)는 고치지 않는다.

## 1. 기존 G2 FAIL

- 사전 기준 "template 원문에 thinking 처리(`<think>`)가 있음"이 FAIL이었다.
  - template 원문은 `{{ .Prompt }}`이고 `<think>`가 없다.
  - thinking 처리는 Modelfile의 `RENDERER qwen3.8` / `PARSER qwen3.5`(Ollama 0.40.3 내장)가 한다.
- 나머지는 artifact와 일치했다: Q4_K_M, capabilities, model·projector blob, Modelfile parameters, architecture `qwen35`.

## 2. 보완(결정 81, 사용자 승인) — G2_COMPATIBILITY_RULE_SUPPLEMENTED

- thinking metadata 기준은 다음 중 하나를 충족하면 된다.
  - Route A: template 원문이 thinking protocol(`<think>`)을 표현한다.
  - Route B: RENDERER가 있고, PARSER가 있고, capabilities에 thinking이 있다.
- 현재 모델은 Route B다: `RENDERER qwen3.8`, `PARSER qwen3.5`, capability thinking.
- family 기준: `family = qwen35`, `general.architecture = qwen35`는 이 exact-digest artifact의 실제 metadata이므로 "qwen3 계열"을 충족한다. 문자열을 바꾸지 않는다.
- 보완 기준에서 G2는 **PASS(보완 기준)**다. 기존 G2 FAIL 기록은 그대로 남는다.

## 3. 바뀌지 않는 것(재확인 2026-10-14)

| 항목 | 값 |
|---|---|
| model digest(`/api/tags`) | `aaee06c39dcf2437cde036998d960e1fc1494b8191be7cc9657d01e509097813`(G1 그대로, 재-pull 없음) |
| 31문항 manifest | sha256 `65a016e0…`, id 순서 hash `9850b727…` |
| quality_gate_v1 | sha256 `f57e2d3e1045fcf7cb00cfd577b5b8850281158bee52c6d3bd3787bd828bf392` |
| P0 prompt | `d7f4c12a` |
| G3 PASS 기준 1–6, 속도 기준 | `IMPORT_AND_TEACHER_PLAN.md` 그대로 |
| G4 설정 | greedy 1 + sampling 4(0.6/0.95/20), seed 2026101500 + 10 × item_index + sample_index, `think: true`, num_predict 미지정 |
| G5 판정·필터·ranking·사람 검토 기준 | 그대로. top-1 거부 시 대체 없음(TEACHER_RECOVERY_FAILED) |
| 격리 | 결정 80: 호출마다 `keep_alive: 0`, 다음 호출 전 `/api/ps` 빈 상태. resident·resident_isolated 사용 안 함 |

## 4. 실행 전에 고정한 기록·guard 보강(판정 기준 변경 아님)

결과를 보기 전에 다음만 추가했다(`ollama_call.py`, `teacher_generate.py`).

- **호출 전 precheck**(G3·G4 모든 호출). 하나라도 어기면 그 호출 전에 중단한다.
  - host `nvidia-smi -L`에 GPU `GPU-d4308fbb-d17f-3609-676a-935c6072c831`가 보임
  - 컨테이너 `docker exec ollama nvidia-smi -L`에 같은 UUID가 보임
  - GPU compute 프로세스 0(HF 0, 다른 프로세스 0. 모델은 직전 호출 뒤 내려가 있어야 함)
  - 컨테이너 상태 running(restart 수·시작 시각 기록)
  - `/api/ps` 빈 상태(최대 60초 대기)
- **timeout·retry**: 기존 계획에 규칙이 없었다. 호출당 timeout 3600초, 재시도 없음으로 고정한다.
  - 시간 초과·연결 오류는 실패 호출로 기록한다(G3에서는 http_ok FAIL, G4에서는 guard 중단).
- **raw 필드 추가(G4)**: `mode`(greedy/sampling), `parsed_output`(`parse_planner_json` 결과, 실패하면 오류 이름). 판정은 G5에서만 한다.

## 5. G3 문항

- 결정 31 render check(`pilot_001/ollama/render_check_*.json`)와 같은 10문항이다(id 목록 일치 확인).
- `ann-da98b3941dfa1c7ce800`(item_index 0), `ann-0e4edbda1cb1bec194c1`(item_index 5)는 31문항 대상과 겹친다.
  - compatibility 출력은 G4·판정·학습에 쓰지 않는다. G4는 이 두 문항도 계획대로 새로 5호출한다.

## 6. 순서

G2 보완(이 문서) → commit·push → G3 → PASS일 때만 G4 → raw commit·push → G5 판정·선택 → commit·push → 사람 검토 → commit·push → coverage → 최종 REPORT·결정.

- G3 FAIL이면 G4 이후는 0회다.
- M1 P3, M2 실패 11, M3 실패 1은 이번 batch에 넣지 않는다. 새 SFT·DPO 0. `qwen3.8:27b`는 store에 둔다.
