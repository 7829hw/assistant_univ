# reviewed_reasoning_v001

2026-10-14 freeze. 결정 85. 생성: `build_canonical.py`(final-6), `build_dataset.py`(154). 모델 호출 0.

## 1. 구성(154/154, 답만 있는 레코드 0)

| reasoning 출처 | 수 |
|---|---:|
| HF Qwen3-8B R70(`hf8b_r70`) | 70 |
| HF Qwen3-8B M2 회수(`hf8b_m2`) | 10 |
| M3 기존 trace 회수(`hf8b_m3`) | 3 |
| Ollama qwen3.8:27b P1/P2(`t27b_p12`) | 27 |
| Ollama qwen3.8:27b remaining(`t27b_remaining`) | 38 |
| manual canonical(`manual_canonical`) | 6 |

- 질문 출처: v005 111, Gap A(augment_dt_event) 26, Gap B(augment_od_vs_dt) 17.
- 레코드: v006의 system·user를 그대로 쓴다. assistant는 `<think>\n{thinking}\n</think>\n\n{v006 P0 target 문자열}`이다.
  - 최종 답은 reasoning 출처와 무관하게 frozen v006 P0 gold다.
- `dataset.jsonl` sha256 `071ccdbee8c74694a189e861bb572975c6198da9c79b7cc93a558f531decea49`.
- item 순서 sha256 `8522deaa8a99fda2816a689e7285db195d5e20ecbbbe66359603a2515c210dff`(v006 순서).
- 문항마다 provenance(`manifest.json`): 출처, teacher model/revision/digest, generation batch, seed, 검토 판정, canonical 여부, thinking·final hash.

## 2. final-6 canonical(`canonical_review.json`, `canonical_rationales.jsonl`)

- gold 재검토: 6/6 CLEAR_GOLD(GOLD_PROBLEM 0).
- canonical 6/6 APPROVE_CANONICAL.
- reasoning_source = manual_canonical, teacher_model = null. 각 1회만 넣었고 oversampling 0이다.

| id | 이유 |
|---|---|
| b006-05·15·20·26 | implicit pickup(27B 5/5 실패) |
| b006-19 | implicit dropoff(27B 5/5 실패) |
| b006-34 | 27B top-1 reasoning-final 충돌로 거부 |

- 형식: 해당 slot(measure / place restriction / place od_role / grouping dimension / dimension_target / order·limit) 한 줄씩 + 1–2문장.
  - 장소 제한 끝과 묶는 끝을 따로 결정한다고 적었다.
  - b006-34는 "H3 셀은 dimension이지 concept·measure text가 아니다"를 명시했다.
- 언어: 다른 148 trace처럼 영어 thinking이고, 질문 표현은 한국어로 인용했다.

## 3. 무결성(`integrity.json`) — 154/154 전부 통과

- id unique 154, 누락 0, 중복 0, reasoning 154, 최종 답 154. 답만 있는 레코드 0.
- 최종 답 = metadata.target_p0 = v006 문자열(바이트).
- Full gold에서 결정적 변환한 P0와 같다. 운영 경로(assess_t2pc) 실행 결과·의미 서명(EVENT 제외)이 Full gold와 같다.
- outcome: answered 142, 정지 target 12(v006과 같음).
- EVENT 삽입 0, P0 contract 그대로. `_grounding_view`는 바꾸지 않았다.

## 4. 오염(`contamination.json`)

| 평가셋 | question | id | template | family |
|---|---:|---:|---:|---:|
| vendor100 | 0 | 0 | 11 | 20 |
| valid98 | 0 | 0 | 11 | 20 |
| sel154 | 0 | 0 | 8 | 11 |
| aux_test_v1 | 0 | 0 | 8 | 11 |

- 모든 template·family 겹침은 v005 문항의 legacy 허용분(결정 15·54)이다. 새 겹침은 0이다.
- 보호 원본 겹침 0. v006 검사(`v006_verification.json`) 결과와 문항별로 같다.

## 5. token 길이(`token_lengths.json`, Qwen3-8B tokenizer, 학습과 같은 렌더링)

| | min | p50 | p90 | p95 | max |
|---|---:|---:|---:|---:|---:|
| prompt | 6,907 | 6,924 | 6,941 | 6,952 | 6,966 |
| thinking | 141 | 704 | 1,262 | 1,662 | 2,011 |
| final | 45 | 87 | 106 | 116 | 147 |
| total | 7,116 | 7,721 | 8,298 | 8,671 | 8,995 |

| 출처 묶음 | n | thinking 평균 | p50 | p90 |
|---|---:|---:|---:|---:|
| HF 8B | 83 | 906.9 | 791 | 1,662 |
| 27B | 65 | 661.2 | 625 | 1,132 |
| canonical | 6 | 162.3 | 161 | 166 |

- 최대 8,995 token이라 기존 max_seq_length 11,392로 전부 손실 없이 들어간다.
- canonical은 짧지만(141–188 token) slot마다 근거가 있다. 인위로 늘리지 않았다.

## 6. 고정

- 이후 학습·평가 결과를 보고 이 파일을 고치지 않는다. 개선은 reviewed_reasoning_v002에서만 한다.
