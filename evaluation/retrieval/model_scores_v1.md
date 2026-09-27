# 모델별 점수 — 예시 검색 평가 셋 v1

2026-09-27 측정(run 폴더 이름은 KST 기준 20260928_*). 채점 condition_scoring v2.7, 분석 id `v2.7-models`.

## 조건

- 질문: `evaluation/retrieval/retrieval_eval_v1.yaml` 17문항(답할 수 있음 13, 목록 2, 모호 2).
  **이 셋은 이미 development다**(2026-09-26 qwen3:8b A/B/C 비교에 사용). 아래 점수는 모델 간 비교용
  development 점수이며 holdout 성능이 아니다.
- arm 3개(같은 코드 `ae91c42` + runner `--think` 옵션): A `structured+cc`, B `+rx`(lexical 검색 top-3,
  임베딩 아님), C `+fx`(고정 예시 ex03·ex09·ex10).
- reference provider(합성 데이터), 기준일 2026-09-25, condition_check on, temperature 0, 관측마다 모델
  상태 초기화, chat timeout 300초(재시도 1회), 반복 1회(qwen3:8b는 전날 2회 반복의 원문이 같았다).
- think: 기본은 `auto`(payload에 think를 넣지 않음 = 모델 기본값, 이전 측정과 같음).
  **qwen3.5:9b와 gemma4:12b는 기본값으로 측정하지 못해 `think off`로 쟀다.** 조건이 다르므로 다른
  모델과 같은 줄에서 비교할 때 주의한다.

## 결과

correct = 답할 수 있는 13문항 중 답을 냈고 집계 의미 계획과 조건이 맞은 수(`correct_answer`). 계산 정답 =
reference 값(과 선택 구간)이 gold와 같은 수(13 중). 결과 종류 = 17문항 중 결과 종류가 gold와 같은 수
(`outcome_ok`: 답/확인 필요/지원 안 함. 목록·모호 문항의 올바른 거부·확인 요청은 여기서만 센다).
지연은 관측 하나의 중앙값(모델 재적재 포함).

| 모델 | think | arm | correct /13 | 계산 정답 /13 | 결과 종류 /17 | 조용한 오답 | 부당한 거부 | 입력 token 중앙값 | 지연 중앙값 |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| qwen3.8:27b | auto | A | **13** | 13 | 14 | 2 | 0 | 5,687 | 14.7초 |
| | | B | 13 | 13 | **16** | 0 | 0 | 6,496 | 13.7초 |
| | | C | 13 | 13 | 15 | 0 | 0 | 6,498 | 14.1초 |
| gemma4:12b | **off** | A | 11 | 12 | 12 | 4 | 1 | 5,919 | 6.5초 |
| | | B | 11 | 11 | 15 | 3 | 0 | 6,776 | 6.9초 |
| | | C | 11 | 11 | 11 | 3 | 2 | 6,787 | 6.8초 |
| qwen3:8b | auto | A | 9 | 9 | 12 | 6 | 1 | 6,116 | 6.7초 |
| | | B | 9 | 10 | 11 | 6 | 2 | 6,983 | 7.2초 |
| | | C | **12** | 12 | 13 | 5 | 0 | 6,989 | 6.7초 |
| gemma4:e4b | auto | A | 7 | 7 | 9 | 3 | 4 | 5,917 | 9.0초 |
| | | B | 7 | 7 | 8 | 1 | 6 | 6,774 | 8.7초 |
| | | C | 10 | 10 | 12 | 2 | 2 | 6,785 | 9.1초 |
| qwen3.5:9b | **off** | A | 0 | 0 | 8 | 10 | 5 | 5,689 | 5.4초 |
| | | B | 2 | 2 | 5 | 3 | 9 | 6,498 | 5.9초 |
| | | C | 2 | 2 | 5 | 5 | 8 | 6,500 | 5.9초 |

무효 관측: 위 표의 모든 run에서 0.

run: `20260928_031222_models_qwen3_8_27b`, `20260928_043647_models_gemma4_12b_think_off`,
`20260928_035455_models_qwen3_8b`, `20260928_033630_models_gemma4_e4b`,
`20260928_044307_models_qwen3_5_9b_think_off`(모두 `evaluation/structured_grounding/` 아래).

## 관찰

- qwen3.8:27b는 세 arm 모두 답할 수 있는 13문항을 전부 맞혔다. 모호 문항 e16은 세 arm 모두 확인 요청으로
  정확히 멈췄고, e17은 B·C에서 멈추고 A에서는 sum으로 짐작했다(조용한 오답). 목록 문항은 e15를 A에서
  값으로 지어냈고(조용한 오답), 나머지는 형식 오류(INVALID_AGGREGATION_PLAN)로 멈췄다. B만 e14를
  `{"unsupported": true}`로 정확히 거부했다.
- qwen3:8b 재측정은 전날 run(`20260926_214029_retrieval_eval_v1`, 반복 0)과 51개 원문이 모두 같다.
  점수도 같다(A 9, B 9, C 12 = 전날 34관측 기준 18/18/24).
- 검색(B)이 A보다 correct를 올린 모델은 qwen3.5:9b(0 → 2, think off)뿐이고 나머지는 같다. 고정 예시(C)는
  qwen3:8b(+3)와 gemma4:e4b(+3)에서 올랐다. 모델별 문항 17개·1회라 차이 1–3은 문항 1–3개의 차이다.
- gemma4:e4b와 qwen3.5:9b는 부당한 거부가 많고 예시를 붙이면 늘어나는 경우가 있다(e4b B 6, 3.5 B 9).
  qwen3.5:9b(think off)의 실패는 대부분 grounding 형식 오류(VALUELESS_CONCEPT, INVALID_SUBTYPE,
  NO_OPERATOR)와 장소 누락(질문의 장소 없이 전체 데이터로 답한 조용한 오답)이다.

## 측정하지 못한 조건(기록 보존)

| 모델 | 조건 | 결과 | run |
|---|---|---|---|
| qwen3.5:9b | think auto | 첫 관측(e01, A)이 300초 timeout 2회로 실패. 다시 시도해도 같아 중단 | `20260928_032605_models_qwen3_5_9b`, `20260928_042633_models_qwen3_5_9b_r2` |
| gemma4:12b | think auto | 첫 관측이 300초 timeout 2회로 실패해 중단. 따로 한 호출 probe도 900초 안에 끝나지 않음 | `20260928_034427_models_gemma4_12b` |

따로 한 probe(e01, 같은 system prompt, 모델이 이미 올라온 상태): qwen3.5:9b think off 6.1초,
think auto 21.6초(생성 3,379 token, thinking 10,604자). gemma4:12b think off 6.3초, think auto 900초 초과.
qwen3.5:9b가 probe에서는 22초인데 평가 run에서 300초를 넘은 이유(초기화 직후 cold load와의 관계 등)는
확인하지 못했다.

## 재현

    python structured_grounding_eval.py run evaluation/retrieval/retrieval_eval_v1.yaml \
      --name models_<tag> --model <MODEL> [--think off] --provider reference --repeat 1 \
      --arms structured+cc,structured+cc+rx,structured+cc+fx
    python condition_scoring.py evaluation/structured_grounding/<RUN> --analysis-id v2.7-models
