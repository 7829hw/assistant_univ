# P0 thinking trace 수집 계획(준비만, 실행하지 않음)

2026-10-13. 결정 64(P0를 SFT 기준 contract로), 결정 66(trace 원문 보존).

## 1. 시작 조건(모두 충족해야 수집한다)

1. resident_isolated 격리 확인 실험 통과(`../resident_isolation/RESULT.md`). **2026-10-13 불통과.** Ollama 경로로 모으려면 새 격리 방법이 확인을 통과하거나, unload_per_question으로 모으는 것을 사용자가 정해야 한다.
2. batch006 사람 승인 끝, `reviewed_gold_v006_p0`(v005 111 + 승인분) 생성.
3. 수집 모델 결정(3절, 사용자).
4. CLAUDE.md 13·14번 장비 확인(컨테이너 GPU, 속도 guard, 상주 기록).

## 2. 기존 Full trace를 쓰지 않는 이유

- pilot_002 SFT 379레코드는 Full prompt(87048d0c)에서 생성됐다.
- 379/379의 thinking이 role·MEASURE·SUBCOND·EVENT 같은 Full 구조어를 쓴다(중앙값 9회, `conversion_report.json`).
- JSON만 P0로 바꾸면 "Full 구조를 계획한 추론 + P0 답"이 되어 추론과 답의 계약이 어긋난다.
- 따라서 P0 prompt로 새로 모은다.

## 3. 수집 모델: 사용자 결정 필요

| 후보 | 이전 승인 | 지금 사용 가능 | 비고 |
|---|---|---|---|
| HF base Qwen3-8B(BF16, `enable_thinking=True`) | 예. SFT trace의 기본 출처(thinking_prep_001, pilot_001·002, 결정 9의 HF-E 경로) | 예(GPU·HF 경로) | 학습 대상과 같은 정밀도·렌더링. 다만 Ollama 상주 실행이 아니라 HF 생성이므로 이번 지시의 "trace 수집은 resident_isolated"와 맞지 않는다 |
| Ollama `qwen3:8b`(Q4_K_M, digest 500a1f06) | SFT trace 출처로는 승인된 적 없음(평가용) | 예(유일하게 올라와 있는 모델) | resident_isolated로 돌 수 있다. 양자화 모델의 추론을 BF16 학습에 쓰는 것이 이전과 다르다 |
| Ollama `qwen3.8:27b` teacher | 예. 정답 표본이 없는 질문에만(결정 21·48·50) | **아니오.** 지금 컨테이너에 없다. pull은 금지(CLAUDE.md 4) | 쓰려면 모델 반입 승인이 필요하다 |

- 임의로 고르지 않는다. 사용자가 정할 때까지 수집하지 않는다.
- 검토 의견: 이전 절차와 가장 가까운 조합은 "HF base(주 출처) + 정답 표본이 없는 질문만 teacher"다. 그러나 Ollama 상주 수집 지시와 27b 부재 때문에 그대로는 할 수 없다. 둘 중 무엇을 바꿀지가 결정 사항이다.

## 4. 실행 방식(Ollama 경로를 고를 때)

- `run_collect.sh`(수집 시작 때 작성)가 `resident_lib.sh`의 `resident_begin`(빈 GPU 확인 → 판정 무관 warm-up → 상주 감시)을 부른다.
- 이어서 `collect_p0_traces.py`를 실행하고, `cell_guard watch`(속도·GPU)와 `resident_end`(unload·reload·컨테이너 재시작 0)로 감싼다.
- 요청마다 `PrefixCacheReset`으로 서버 KV cache를 같은 상태로 만든다. 모델은 내리지 않는다. isolation 요청은 표본·점수·token 지표에 넣지 않는다.
- 문항 사이와 셀 사이에 unload, wait-empty, 컨테이너 조작이 없다.

## 5. 표본과 판정

- 질문마다 greedy 1개 + sampling 8개(temperature 0.6, top_p 0.95, top_k 20). seed = `call_seed(round_seed, item_id, k)`.
  - 기존 HF 수집과 같은 개수다.
- 판정은 조건 계층 전 원 출력 기준이다(기존 `collect_traces.judge`와 같은 취지).
  - `match_raw`: P0 응답을 parser로 완성한 뒤 평가 비교 정규형이 target과 같은가.
  - `match_after_conditions`: 운영 경로 결과·의미 서명(EVENT 제외)이 같은가. 따로 센다.
- 학습 후보 선별(필터, 질문당 최대 개수, 정답 표본 없는 질문 처리)은 수집 뒤 별도 결정으로 정한다. 기존 필터를 그대로 쓴다.
  - 기존 필터: tokenize 왕복·렌더 경계, 계약, 길이(결정 18), 루프(결정 40-D), 질문당 상한.

## 6. 저장 항목(결정 66: thinking 원문 보존)

- 표본마다 `collect_p0_traces.py`가 jsonl 한 줄로 남긴다.
  - 식별: question, item id, dataset version, source(v005·augment_*)
  - 실행 조건: system prompt hash, model, model digest, Ollama 버전, options·seed·round_seed
  - 원문: thinking 원문, 최종 응답 원문
  - 지표: eval_count, prompt_eval_count, duration, load_duration
  - 기타: isolation reset 결과, 판정, 시각
- 결정 33에 따라 생성 데이터와 원문은 commit한다. 경로는 `training/generated/thinking_traces/p0_<run>/`.
- 평가 harness에도 `--record-thinking`을 더했다(생성에는 영향 없음, code fingerprint 범위 밖).

## 7. 규모와 시간(추정)

- v005 111 + batch006 승인분(최대 43)이면 최대 154질문 × 9표본 = 1,386요청(+ isolation 요청 같은 수).
- qwen3:8b Ollama 기준으로 표본당 약 7–8초면 약 3시간이다.

## 8. dry-run 확인(모델 호출 없음)

- `collect_p0_traces.py --dry-run`: P0 system prompt hash `d7f4c12a`, 메시지 [system, user], v005 111건에서 요청 999개 예정.
- 판정 함수 오프라인 확인: target 자신과 Full target을 응답으로 넣으면 `match_raw`·`match_after_conditions` 모두 참이다.
