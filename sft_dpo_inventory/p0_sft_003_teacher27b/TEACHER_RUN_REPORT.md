# 27B Teacher Recovery 실행 보고

2026-10-14. 계획 `IMPORT_AND_TEACHER_PLAN.md`(커밋 `ca05ece`), 결정 79·80. 원 기록은 `import/`.

## 1. 결론

- **G2 metadata hard gate FAIL로 중단했다.**
  - 실패한 기준: "template 원문에 thinking 처리(`<think>`)가 있음"이다.
  - 반입한 모델의 template 원문은 `{{ .Prompt }}`(13자, 통과용)다. `<think>`가 없다.
  - thinking 처리는 Modelfile의 `RENDERER qwen3.8` / `PARSER qwen3.5`(Ollama 0.40.3 내장 코드)가 한다.
  - 사전 등록 기준을 결과 뒤에 바꾸지 않았다(결정 78 판정과 같은 원칙).
- G0 pull: 성공. G1 digest: **PASS**(64 hex 전체 일치).
- G2의 나머지 hard 기준은 모두 통과했다: Q4_K_M, capabilities, qwen3 계열.
  - Q4_K_M, capabilities 4개, Modelfile parameters 7개, model·projector blob digest가 과거·registry 기록과 같다.
- G3–G6(compatibility, 생성, 판정, 사람 검토, coverage)은 **실행하지 않았다**.
  - 27B 호출 0회, teacher trace 0, coverage 83/154 그대로.
- `qwen3.8:27b`는 store에 남겨 두었다(삭제·재-pull·tag 변경 0).
- 새 SFT·DPO 0.

## 2. Git 무결성

- 시작 remote HEAD: `09889a2ac74cfa6bcba6133fc7c61f3ef4f06c79`.
- 작업 단위마다 commit → push → fetch 뒤 HEAD = `origin/geoflow/partial-grounding`을 확인했다. force push·amend·history 변경 0.

| 단위 | commit |
|---|---|
| 계획·결정 79·80 | `ca05ece` |
| pull 기록(G0) | `4fe19f2` |
| post-import 검증(G1 PASS, G2 FAIL) | `7258410` |
| 이 REPORT와 미실행 스크립트 | 이 커밋 |

## 3. Provenance decision 보완

- 결정 79(사용자 승인)는 결정 78을 바꾸지 않고 보완한다.
  - 내용: registry manifest body sha256이 과거 digest `aaee06c3…`와 전체 일치하므로 동일 artifact의 충분한 근거로 인정하고, pull을 승인한다.
  - 상태는 PROVENANCE_REGISTRY_BODY_HASH_MATCH다.
- 결정 80: teacher 수집은 호출마다 `keep_alive: 0`, 다음 호출 전 `/api/ps` 빈 상태를 확인한다. 이번에는 호출이 없어 적용되지 않았다.

## 4. Model pull(`import/pull_record.json`)

| 항목 | 값 |
|---|---|
| 명령 | `docker exec ollama ollama pull qwen3.8:27b`(기존 컨테이너·store, 재시작·설정 변경 없음) |
| 사전 확인 | GPU compute 프로세스 0, `/api/ps` 빈 상태 |
| 시각 | 2026-10-14T08:46:44Z – 08:55:38Z(약 9분) |
| 결과 | rc 0, 출력 마지막 줄 `verifying sha256 digest` → `writing manifest` → `success` |
| store 크기 | 5,225,398,539 → 22,967,273,542 B(+17,741,875,003 B) |
| 받은 layer | projector `ac3714bf…` 931 MB, model `f5f1dd89…` 16 GB, config `492b2922…` 215 B |

- 늘어난 크기는 layer 합 17,741,871,939 B + config 215 B + manifest와 맞는다.

## 5. Post-import digest 검증(G1, `import/tags_after.json`)

| 항목 | 값 |
|---|---|
| `/api/tags` digest | `aaee06c39dcf2437cde036998d960e1fc1494b8191be7cc9657d01e509097813` |
| 기대값 | `aaee06c39dcf2437cde036998d960e1fc1494b8191be7cc9657d01e509097813` |
| 일치 | **64 hex 전체 일치 → PASS** |
| size | 17,741,872,154 B(manifest layer + config 합과 같음) |
| qwen3:8b | digest `500a1f06…` 그대로 |

## 6. Metadata/compatibility(G2, `import/show_after.json`, `import/integrity.json`)

### hard 기준

| 기준 | 값 | 판정 |
|---|---|---|
| quantization_level | Q4_K_M(file_type 15) | PASS |
| capabilities | completion, vision, tools, thinking(과거 4개와 같음) | PASS |
| family | `qwen35`(general.architecture `qwen35`) | PASS(해석 포함) |
| template에 `<think>` | template 원문 `{{ .Prompt }}`, `<think>` 없음 | **FAIL** |

- family는 원문이 `qwen35`(Qwen3.5 계열 architecture)다. "qwen3 계열"로 읽어 PASS로 적었지만 해석이 들어간 항목이다.

### 기록·비교(deviation)

| 항목 | 값 | 과거와 |
|---|---|---|
| parameters | temperature 1, top_k 20, top_p 0.95, min_p 0, presence_penalty 0, repeat_penalty 1, draft_num_predict 4 | 같음 |
| Modelfile FROM | model blob `f5f1dd89…`, projector blob `ac3714bf…` | registry manifest와 같음 |
| RENDERER / PARSER | `qwen3.8` / `qwen3.5` | 과거 기록 없음(비교 불가) |
| `thinking` 필드 | values `[false, low, medium, xhigh]`, default `medium` | 과거(0.35.1) 기록 없음 |
| context_length | model_info 262,144 | 같음(`/api/ps` 실측은 호출이 없어 미측정) |
| requires | 0.32.12 | – |
| Ollama | 0.40.3(과거 teacher 0.35.1) | 다름(계획에 적힌 차이) |

- `thinking` 필드는 0.40.3이 thinking 수준을 나눠 보여 주는 형식이다. `think: true`가 어느 수준(medium?)으로 매핑되는지는 확인하지 않았다(호출 0).
  - 과거 teacher(0.35.1, `think: true`)와 같은 thinking 동작인지는 G3에서 확인할 항목이었다.

### compatibility 10문항(G3)

- **실행하지 않았다**(G2 FAIL). context·num_predict·thinking 동작 차이의 실측값, 속도 기준도 없다.

## 7. 31문항 generation

- 실행하지 않았다. 27B 호출 0회.
- 31문항 manifest는 바뀌지 않았다(sha256 `65a016e0…`, id 순서 hash `9850b727…`, 이번에 다시 확인).

## 8. Correct trace yield

- 해당 없음(생성 0). greedy·sampling 정답 0/0, 정답 trace가 1개 이상인 문항 0.

## 9. quality_gate_v1

- 적용 대상 없음. `quality_gate_v1.py`는 바뀌지 않았다(sha256 `f57e2d3e…`, `0c42288` 이후 변경 0).

## 10. 사람 검토

- 대상 없음. 승인 0, 거부 0.

## 11. Feature별 recovery

- 0. dt pickup·dropoff·both, od_role ≠ dt, Gap A·B 모두 회수 0.

## 12. Reasoning coverage 변화

- 83/154 → **83/154**(변화 없음).
- 구성: HF Qwen3-8B R70 70, HF Qwen3-8B M2 회수 10, M3 기존 trace 회수 3, Ollama qwen3.8:27b 0.

## 13. 남은 missing reasoning

- 71문항: M1 59, M2 실패 11, M3 실패 1(b006-11).
- 27B 대상(M1 ∩ {P1, P2}) 31문항은 그대로 남았다.
  - P1 22, P2 9
  - v005 18, Gap A 10, Gap B 3
  - dt pickup 12, dropoff 7, both 6, none 6
  - od_ne_dt 13

## 14. 다음 단계

**사용자 결정이 필요하다.** 선택지는 다음과 같다.

**A. G2 template 기준 보완 승인(권장)**

- 근거:
  - 0.40.3에서 이 모델의 thinking 처리는 template 문자열이 아니라 Modelfile의 `RENDERER qwen3.8` / `PARSER qwen3.5`에 있다. template `{{ .Prompt }}`는 renderer가 만든 prompt를 그대로 넘기는 통과용이다.
  - capabilities에 thinking이 있다.
  - artifact 자체(digest, blob)는 과거 승인 teacher와 같다.
- 보완 기준: "template 원문에 `<think>` **또는** Modelfile에 RENDERER/PARSER가 있고 capabilities에 thinking이 있음".
- 실제 thinking 동작은 G3 compatibility가 실측으로 확인한다. G3 기준 1–6은 그대로 둔다(thinking 비어 있지 않음, content에 think tag 없음, JSON, stop, GPU 100%).
- 승인 문구 예:
  > "qwen3.8:27b의 thinking 처리가 Ollama 0.40.3 내장 RENDERER qwen3.8 / PARSER qwen3.5에 있으므로, G2의 template 기준을 'template에 `<think>` 또는 RENDERER/PARSER + capabilities thinking'으로 보완한다. G3 이후 hard gate는 바꾸지 않고 진행을 승인한다."
- 함께 정할 수 있는 것: family `qwen35`를 "qwen3 계열"로 인정하는지 명시.

**B. 기준 유지**

- 이번 artifact·Ollama 버전으로는 27B teacher 경로를 닫는다.
- M1 P1·P2 31문항은 다른 수단(예: 8B 표본 확대, 사람 작성 reasoning)으로 회수한다. 별도 계획이 필요하다.

미실행 스크립트(`ollama_call.py`, `compat_check.py`, `teacher_generate.py`, `judge_select.py`)는 계획대로 작성만 해 두었다. A를 승인하면 이 스크립트로 G3부터 진행한다.
