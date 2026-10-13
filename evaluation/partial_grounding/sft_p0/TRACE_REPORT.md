# P0 thinking trace 수집 결과(reviewed_gold_v006_p0, HF base Qwen3-8B)

2026-10-13. 결정 66·67. 학습하지 않았다. 숫자는 `trace_quality.json`(`trace_quality.py`)에서 왔다.

## 1. 실행 조건

| 항목 | 값 |
|---|---|
| 모델 | `Qwen/Qwen3-8B@b968826d9c46dd6066d109eabc6255188de91218`(tokenizer 같은 revision), adapter 없음 |
| 실행 | BF16, SDPA, transformers 4.56.2, torch 2.11.0+cu128, RTX PRO 6000 Blackwell(`GPU-d4308fbb…`) |
| 모델 파일 | `HF_HOME=/data/hwkim/path_repeat_001/hf-cache`(offline). 받거나 옮기지 않았다 |
| 생성 | `enable_thinking=True`, max_new_tokens 8192. 질문마다 greedy 1 + sampling 8(temperature 0.6, top_p 0.95, top_k 20, num_return_sequences 8, seed = 20261006 + 질문 순번) |
| 절차 | `thinking_prep_001/collect_traces.py`와 같다. 바뀐 것은 system prompt(P0, prompt hash `d7f4c12a`)와 판정 대상(P0 target)뿐이다 |
| 입력 | v006 154문항, [system, user]. 질문 사이 대화 상태 없음. Ollama 호출 없음(resident 계열 미사용) |
| code fingerprint | `ab88a19e` |
| 시간 | 05:17:52–09:13:18 UTC(3시간 55분). 사전·사후 GPU 0 MiB, Ollama `/api/ps` 비어 있음 |
| 원문 | `training/generated/thinking_traces/p0_v006_hf/traces.jsonl`(1,386줄, 22 MB) |

- 원문 필드(결정 66):
  - 식별: item id, question, dataset version, source
  - 실행 조건: model·revision·tokenizer, prompt hash, seed, 생성 설정
  - 원문: raw_text, thinking, content(최종 응답), 생성 token id
  - 결과: parsed, 판정
- 기존 Full trace(pilot_002)는 쓰지 않았다.

## 2. 전체 결과

| | 값 |
|---|---:|
| 수집 문항 / 결측 / 일부만 | 154 / 0 / 0 |
| trace | 1,386(greedy 154, sampling 1,232) |
| thinking 있음(닫힘·비어 있지 않음) | 1,383 |
| thinking 없음(8192 상한에서 잘림) | 3 → trace dataset에서 제외 |
| EXACT_OR_SEMANTIC_MATCH | 325(23.4%) |
| STRUCTURALLY_REPAIRABLE | 355(25.6%) |
| SEMANTIC_MISMATCH | 703(50.7%) |
| REFUSAL_MISMATCH | 0 |
| UNPARSEABLE | 3 |
| greedy 정답 | 34/154 |
| 정답 표본이 1개 이상인 문항 | 95/154 |
| 정답 표본이 없는 문항 | 59(v005 43, 신규 16) |
| 생성 token 중앙값 / thinking 글자 중앙값 | 841 / 2,879 |

- 판정 기준(collect_p0_traces_hf.judge):
  - EXACT_OR_SEMANTIC_MATCH: 조건 계층 전 원 출력이 Full canonical gold와 `grounding_check`로 같다(기존 trace 판정과 같은 기준).
  - STRUCTURALLY_REPAIRABLE: 원 출력은 다르지만 운영 경로(조건 계층·compose·validate·compile) 뒤 실행 결과와 의미 서명이 target과 같다.
    대부분 날짜·taxi_type처럼 조건 계층이 질문에서 다시 채우는 것이다.

## 3. 출처·축별 teacher 성공률

| 묶음 | 문항 | trace 정답 | greedy 정답 | 정답 표본 있는 문항 |
|---|---:|---:|---:|---:|
| v005 | 111 | 241/999(24.1%) | 27/111 | 68/111 |
| **Gap A**(augment_dt_event) | 26 | **37/234(15.8%)** | 3/26 | 14/26 |
| **Gap B**(augment_od_vs_dt) | 17 | **47/153(30.7%)** | 4/17 | 13/17 |
| dimension_target pickup | 35 | 60/315(19.0%) | 3/35 | 22/35 |
| dimension_target dropoff | 29 | 53/261(20.3%) | 4/29 | 18/29 |
| dimension_target both | 10 | 13/90(14.4%) | 2/10 | 4/10 |
| od_role ≠ dimension_target | 31 | 44/279(15.8%) | 2/31 | 16/31 |

## 4. 신규 문항 실패 원인 분리(지시 30절)

신규 43문항에서 원 출력이 틀린 trace의 차이 항목:

| 차이 | 수 | 내용 |
|---|---:|---|
| places | 159 | 장소의 od_role 누락(수성구·대구·부산 pickup/dropoff → null)이 대부분. "시도"·"동"·"읍면동"·"H3 셀" 같은 묶음 단위어를 장소로 만든 것, 광안리·수성구 끝점 반대도 있다 |
| dimension_target | 128 | 누락이 110(pickup→없음 72, dropoff→없음 38), 반대 끝 18 |
| aggregation_spec | 81 | 질문에 없는 집계(sum 등)를 넣음 |
| dimension | 68 | h3 → emd 25, sigungu/sido → emd 20 등 |
| date | 52 | "2026년 8월" → `202608`, 9/1–9/7 범위 오기 등 |
| scopes | 28 | h3를 scope(`scope:h3`)로 만듦 |

- **gold 문제인가:**
  - 아니라고 본다. 43건 모두 계약·운영 경로 불변식을 통과했다.
  - 실패 형태는 sel154 ROOT_CAUSE와 같은 계열의 teacher 약점(dimension_target 누락, 사건 표현의 끝점 읽기, 묶음 단위어를 장소로 만들기)이다.
- **teacher capacity:**
  - Gap A의 사건 표현 끝점(dimension_target 누락)이 가장 어렵다(trace 15.8%).
  - Gap B는 두 축이 문장에 명시적이라 상대적으로 높다(30.7%).
- **prompt 요인:**
  - P0 prompt의 dimension 예시는 요일별·시도별·시군구별·읍면동별뿐이고 h3 표현이 없다.
  - "H3"가 들어간 질문의 신규 표본은 185/198이 dimension h3다.
  - "셀"만 쓴 질문(b006-21, 22, 37)은 27표본 중 14개가 emd다.
  - P0 prompt는 고치지 않는다(결정 64). 이 표현형은 학습 데이터가 가르칠 대상이다.
- 정답 표본이 없는 신규 16문항: b006-05, 07, 09, 15, 17, 20, 21, 22, 23, 24, 25, 26, 31, 32, 37, 43.
  - 이 문항들에는 HF base에서 나온 정답 reasoning trace가 없다. 틀린 thinking을 정답 JSON과 결합하지 않는다(지시 28절).
  - gold JSON(json_only) 학습, teacher 보충(결정 21·50 방식, 27b 반입 필요), 미사용 중 무엇으로 할지는 다음 단계에서 정한다.

## 5. 채택 가능 trace

| 단계 | trace | 문항 | v005 / Gap A / Gap B |
|---|---:|---:|---|
| 기본 채택: EXACT_OR_SEMANTIC_MATCH + thinking 있음, 질문별 원문 중복 제거 | 325 | 95 | 241 / 37 / 47 |
| 참고: 기존 학습 필터 적용 뒤(결정 4 tokenize 왕복 18개 제외, 결정 40-D 루프 0, 결정 18 길이 0) | 307 | 91 | 228 / 35 / 44 |
| 참고: 위 + 질문당 최대 4개(결정 48·50 상한) | 240 | 91 | |

- STRUCTURALLY_REPAIRABLE(원문 중복 제거 355)은 넣지 않았다. 통계를 본 뒤 따로 정한다(결정 67).
- 필터·상한 적용은 다음 SFT 단계 preregistration에서 확정한다. 채택 trace id 목록은 `trace_quality.json`의 `adoption`에 있다.
- 추론 문장은 사람이 검토하지 않았다. 기존 결정 23·27·49처럼 표본 검토("우연히 정답" 확인)가 필요하다.

## 6. 한계

- Full prompt HF trace(pilot 계열)와 숫자를 직접 비교하지 않는다. 질문 집합과 prompt가 다르다.
- sampling 8개는 한 번의 generate(num_return_sequences 8)로 만든다. 기존 절차와 같으며, 같은 seed라도 batch 구성이 바뀌면 표본이 달라진다.
- 정답 판정은 `_grounding_view` 기반이다(결정 65의 both 표기 한계 그대로).
