# 27B Teacher 반입 전 검증

2026-10-14. 결정 74–77. 모델 반입·복사·호출, 외부 registry 조회, 8B sampling, SFT는 하지 않았다.

## 1. 결론

- **provenance: PROVENANCE_PARTIAL.**
  - 과거 teacher는 이름(`qwen3.8:27b`)으로 Ollama registry에서 pull된 흔적이 있다(사용자 shell history).
  - 그 tag와 digest `aaee06c3…`의 연결 근거가 없고, 현재 서버에 복사 원본도 없다.
  - 같은 artifact임을 지금은 증명할 수 없다. 이름만 보고 pull하지 않는다.
- **quality_gate_v1을 27B 결과 전에 고정했다.**
  - 기존 사람 판정 111 trace에 한 번 replay한 결과: 거부 19/28을 flag(recall 0.68), 승인 8/83에 flag(precision 0.70).
  - 직전 자동 tier보다 크게 낫다. 다만 사람 검토를 대신할 수준은 아니다.
- **27B generation PLAN을 고정했다**: 31문항, 최대 155 호출, digest 전체 일치·호환성 검증 후에만 실행한다.
- 27B 반입은 **사용자의 원본 지정과 승인**이 필요하다(12절).

## 2. Git 무결성

- 시작: local = remote = `74377676`, 작업 트리 깨끗함, branch `geoflow/partial-grounding`. 다음 decision 번호를 확인한 결과 74였다.
- 작업 단위마다 commit → push → fetch 후 HEAD = `origin/geoflow/partial-grounding`을 확인했다.

| 단위 | commit |
|---|---|
| provenance 조사 계획·결정 74–77 | `da95c22` |
| provenance 조사 결과 | `427fec3` |
| quality_gate_v1 규칙 고정(replay 전) | `0c42288` |
| quality_gate_v1 replay 결과 | `f7f4fd7` |
| 27B generation 사전 등록 | `7617ba1` |
| REPORT | 이 커밋 |

## 3. 과거 teacher identity

| 항목 | 값 |
|---|---|
| 이름 | `qwen3.8:27b`(Ollama) |
| digest | `aaee06c39dcf2437cde036998d960e1fc1494b8191be7cc9657d01e509097813` |
| 양자화 | Q4_K_M |
| 크기 | 17.7 GB |
| size_vram | 18,542,682,438 B |
| context | 262,144 |
| capabilities | completion, vision, tools, thinking |
| Modelfile 파라미터 | temperature 1, top_k 20, top_p 0.95, min_p 0, presence_penalty 0, repeat_penalty 1, draft_num_predict 4 |
| 과거 Ollama | 0.34.4(평가), 0.35.1(teacher) |
| 과거 teacher | think true, temperature 0.6, 표본 8, prompt Full `87048d0c` |

## 4. Provenance 조사(`PROVENANCE_REPORT.md`, `provenance.json`)

- **git(모든 branch, 원격 포함)**:
  - alias 최초는 `7c7cec0`(2026-09-15)다. 이미 로컬에 17.7 GB로 있었다.
  - digest 최초는 `c1f2a08`(2026-10-03, 평가 meta)다.
  - Modelfile, `ollama create`, blob, registry 경로, hf.co 기록은 없다.
- **shell history**: 정확한 문자열 검색만 했다.
  - `docker exec -it ollama ollama pull qwen3.8:27b`와 `ollama run qwen3.8:27b`가 있다(시각 기록 없음).
  - 바로 앞에 `ollama pull gemma4:e4b`가 있다. 2026-09-15 모델 비교 측정 무렵으로 보인다.
- **현재 서버**:
  - 컨테이너 store(`/data/hwkim/ollama`, bind `/root/.ollama`)에는 qwen3:8b뿐이고 `sha256-aaee…` blob이 없다.
  - `~/.ollama`에는 key·cache뿐이다. 옛 경로 `/home/hwkim/sftdpo_work`는 없다.
  - 컨테이너 로그에 27b 줄이 없다.
  - 이 장비는 2026-10-08부터 쓴 새 장비라, 과거 store는 옛 장비에 있었을 것이다.

## 5. 발견한 source 후보

| 후보 | 내용 | 동일성 근거 |
|---|---|---|
| Ollama registry tag `library/qwen3.8:27b` | 과거 pull 명령의 대상 | **없음**(tag는 바뀔 수 있음, 당시 digest 기록 없음) |
| 옛 장비 Ollama store | 과거 teacher가 실행된 곳 | 있으면 manifest digest로 정확히 확인 가능. 위치·접근은 모름 |
| 현재 서버 복사 원본 | 없음 | – |

## 6. Provenance 판정

**PROVENANCE_PARTIAL.**

- EXACT가 아닌 이유: tag와 digest 연결 근거가 없다.
- COPY_SOURCE가 아닌 이유: 현재 서버에 manifest·blob이 없다.
- CONFLICT가 아닌 이유: 후보 원본이 하나뿐이다.

## 7. quality_gate_v1(`QUALITY_GATE_V1.md`, 고정 commit `0c42288`)

**flag**

- GROUPING_UNIT_AS_CONCEPT
- GROUPING_UNIT_AS_PLACE
- HALLUCINATED_SCHEMA_RULE
- UNRETRACTED_WRONG_AGGREGATION
- OD_ROLE_DIM_TARGET_CONFUSION
- CONCLUDED_UNSUPPORTED
- REASONING_FINAL_CONFLICT

**설계 원칙**

- 문장 근거는 thinking 결론 구간(마지막 30%)에서만, 구조 근거는 응답 JSON에서 본다.
- 묶음 단위 vocabulary는 ontology(`FACTOR_SPECS["dimension"]`)에서 읽는다.

**ranking**: flag 수 → thinking 길이 → Wait·Hmm 수 → greedy 먼저 → sample index.

**성격**: 자동 승인기가 아니다(결정 76).

## 8. 기존 trace replay 결과(1회, 조정 없음)

| | 승인 83 | 거부 28 |
|---|---:|---:|
| flag 있음 | 8 | 19 |

flag별 precision:

| flag | precision |
|---|---|
| GROUPING_UNIT_AS_CONCEPT | 1.00 (0/6) |
| CONCLUDED_UNSUPPORTED | 1.00 (0/2) |
| OD_ROLE_DIM_TARGET_CONFUSION | 1.00 (0/1) |
| HALLUCINATED_SCHEMA_RULE | 0.80 |
| GROUPING_UNIT_AS_PLACE | 0.60 |
| UNRETRACTED_WRONG_AGGREGATION | 0.57 |
| REASONING_FINAL_CONFLICT | 걸린 것 없음 |

(괄호 = 승인에 걸린 수 / 거부에 걸린 수)

**주요 false positive**

- 결론 구간에서 "H3 cells as a place"라고 했다가 바로잡음(b006-04 M2)
- bucket이 있는 정당한 "answer is bucket because"(ann-29dc M2)
- 철회 표현이 목록 밖인 aggregation 언급 3개

**주요 false negative**

- 결론 구간 밖에서 말하고 철회하지 않은 aggregation 4개
- 결론 구간 밖의 단위어 place 계획 2개
- Full 잔재·반복(v1 범위 밖) 2개
- 결론 구간 밖의 규칙 주장 1개

## 9. 27B generation preregistration(`GENERATION_PLAN.md`, `7617ba1`)

| 항목 | 값 |
|---|---|
| 대상 | `p0_sft_003_recovery/teacher27b_manifest.json`(sha256 `65a016e0…`) 31문항, 변경 없음 |
| 표본 | greedy 1 + sampling 4(temperature 0.6, top_p 0.95, top_k 20), 최대 155 호출 |
| seed | `2026101500 + 10 × item_index + sample_index` |
| prompt | P0 `d7f4c12a`, `think: true`, gold 미제공 |
| num_predict | 미지정(과거와 같음). 0.40.3 기본 상한 동작은 render check에서 확인 |
| 격리 | unload_per_question, HF 동시 실행 금지, GPU 확인·속도 guard |
| 선택 | 판정 5범주 → EXACT만 → 필터 → quality_gate_v1 ranking 문항당 1개 → 사람 검토, 거부 시 대체 없음 |

## 10. 환경/버전 차이

Ollama 0.35.1(과거 teacher) → 0.40.3(현재). 반입 뒤 확인할 것:

| 항목 | 확인 내용 |
|---|---|
| digest | 전체 일치 |
| 양자화 | Q4_K_M |
| capabilities·Modelfile 파라미터 | 과거 기록과 일치 |
| template·system | sha256 기록(과거 원문 hash 기록이 없어 비교 불가임을 명시) |
| context_length | 과거 262,144. 0.40에서 VRAM 기반 기본값이 달라질 수 있다 |
| num_predict 기본 상한 | rendering 10문항에서 비정상 length 종료가 있는지 |
| thinking | 켬 동작, thinking·본문 분리 |

- 다르면 조용히 바꾸지 않고 이탈로 기록·보고한다.

## 11. 반입 시 예상 비용

| 항목 | 값 |
|---|---|
| 디스크 | 17.7 GB(`/data` 여유 약 11 TB) |
| GPU | 약 17.3 GiB(context 262,144 기준, 97,887 MiB 중) |
| 생성 | 155 호출 + rendering 10. 문항마다 모델 로딩(unload_per_question)이 붙어 약 1–2시간 추정(실측 전) |

## 12. 사용자 승인 필요 사항

exact source를 찾지 못했다. **동일성을 검증할 원본을 찾지 못했고, 지금은 digest metadata만 있다.** 다음 중 하나를 정해 주어야 한다.

1. **옛 장비 원본 지정(권장)**
   - 옛 장비(또는 archive)의 Ollama 모델 store 위치를 알려 주고 복사를 승인한다.
   - 반입 뒤 `/api/tags` digest가 `aaee06c3…`와 전체 일치해야 사용한다.
   - 승인 문구 예: "옛 장비 `<호스트>:<Ollama store 경로>`에서 `qwen3.8:27b`(digest aaee06c39dcf…)의 manifest·blob을 `/data/hwkim/ollama`로 복사해 반입하는 것을 승인한다."
2. **registry tag 검증 뒤 pull 승인**
   - 먼저 `library/qwen3.8:27b` manifest(수 KB)만 조회해 sha256이 `aaee06c3…`와 같은지 본다.
   - 같을 때만 pull하고, pull 뒤 `/api/tags` digest도 확인한다. 다르면 받지 않고 보고한다.
   - 승인 문구 예: "registry `library/qwen3.8:27b`의 manifest 조회를 승인하고, digest가 aaee06c39dcf…와 전체 일치할 때만 pull을 승인한다."
3. **보류**: 27B 없이 진행할 다른 방법을 정한다.

승인을 받아도 반입은 다음 단계에서 한다(결정 77).
