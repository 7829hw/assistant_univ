# Full vs Partial-P0 paired A/B 계획 (ab_p0) — 확정 2026-10-09(사용자)

질문: 같은 모델·같은 추론 설정에서 **출력 contract만** Full → Partial로 바꾸면 결과가 나빠지지 않는가(non-inferior).
prompt 축소(Partial-P1)와 thinking OFF는 이 측정에 섞지 않는다. P0가 통과하면 별도 계획으로 잰다.

## 1. 고정 조건

| 항목 | 값 |
|---|---|
| 코드 | branch `geoflow/partial-grounding`, parser/composer = `9cb8a39`(실행 의미 코드 지문 `ab88a19e`). 측정 중 코드를 바꾸지 않는다 |
| 모델 | Ollama `qwen3:8b` digest `500a1f06…`(base, cell E 조건), 서버 0.40.1(사용자 컨테이너 그대로) |
| 장비 | RTX PRO 6000 Blackwell 1장 `GPU-d4308fbb…`. 결정 56의 장비 절차(`path_repeat_001/PLAN.md` 4절)를 따른다 |
| Full arm | 기본 prompt, 결합 system prompt hash `87048d0c…` |
| P0 arm | `evaluation/partial_grounding/prompts/partial_p0.yaml`(`--planner-prompt`), hash `d7f4c12a…`. 원본과 다른 곳은 task 한 줄과 output_format뿐 |
| 공통 | think 미지정(thinking 켜짐), `--condition-check`, 기준일 2026-09-25, mock·legacy, unload_per_question, 문항 순서 file, `--record-env` |
| greedy | temperature 0(기존 요청) |
| sampling | temperature 0.6, top_p 0.95, top_k 20, 회차 seed 20261010–20261014(path_repeat_001과 같은 seed와 호출 seed 규칙). 같은 회차의 두 arm은 같은 seed |
| 문항 | 업체 100(`evaluation/vendor100/gold.yaml`). 결정 57의 예외 |

## 2. 셀 순서

1. smoke: P0 greedy, 001–003. 분석에 쓰지 않는다. 세 문항 모두 JSON이 읽히고 grounding 계약 오류(`JSON_NOT_FOUND`, `JSON_PARSE_FAILED`,
   `UNKNOWN_KEY`, `INVALID_CONCEPT`, `MISSING_CONCEPTS`)가 없어야 다음으로 간다. 아니면 멈추고 보고한다.
2. greedy: Full → P0.
3. sampling: 회차 r마다 두 arm. 홀수 회차는 Full 먼저, 짝수 회차는 P0 먼저(시간에 따른 표류를 상쇄).

셀마다 `path_repeat_001/cell_guard.py`로 precheck → 실행 중 watch(100% GPU, context 40960, 문항 생성 속도 하한
77.6 tok/s = path_repeat_001에서 정한 값) → wait-empty → postcheck. guard가 멈춘 셀은 `ABORTED_*`로 남기고 전체를
멈춘 뒤 보고한다. 기반 장애가 아니면 셀을 다시 돌리지 않는다. 결과가 이상해도 다시 돌리지 않는다.

## 3. 지표(문항 100개, arm별)

- semantic correctness = (`match` + `expected_refusal`) / 100
- answerable semantic correctness = `match` / 답해야 할 문항 수
- refusal correctness = `expected_refusal` / 거부해야 할 문항 수
- grounding failure = 최종 결과가 grounding 단계 오류로 끝난 문항 수(failure census의 stage가 planning인 오류 코드)와
  `grounding_ok`가 거짓인 문항 수(둘 다 적는다)
- execution completion = 답해야 할 문항 중 Tool 실행까지 끝나 답한 문항(outcome answered) 비율
- malformed/structural errors = 첫 계획 응답이 grounding 계약에서 거부된 문항 수(JSON 형식, 모르는 key, concept·role·
  source·subtype 계약 오류). 재질의로 회복됐는지도 적는다
- final JSON tokens = 첫 계획 응답의 최종 JSON 길이(Qwen3-8B tokenizer), thinking 길이, eval_count, 지연(참고)

## 4. 판정(P0 → P1 진행 조건, 사용자 기준)

| Gate | 기준 |
|---|---|
| semantic correctness | P0 − Full ≥ −1%p |
| answerable semantic correctness | P0 − Full ≥ −1%p |
| refusal correctness | 의미 있는 악화 없음(거부 문항에서 P0만 틀린 문항이 sampling에서 체계적이지 않음) |
| grounding failure | 증가하지 않음 |
| execution completion | P0 − Full ≥ −1%p |
| malformed/structural errors | P0 < Full |
| final JSON tokens | replay에서 본 감소(약 −46%)가 유지됨 |

- 점수 기준은 sampling 5회의 회차 평균 차이(같은 seed끼리 짝)다. 문항 단위 paired bootstrap 95% CI와 paired
  permutation p를 함께 적는다. greedy 한 쌍은 따로 적고 판정에 단독으로 쓰지 않는다(path_repeat_001에서 greedy 한
  번이 sampling 범위를 벗어났다).
- 문항별 표: 문항마다 k_Full, k_P0(5회 중 정답 수)와 greedy 결과. `Full 정답 / P0 오답`, `Full 오답 / P0 정답`
  문항을 회차별·합계로 나열하고, |k_Full − k_P0| ≥ 4인 문항을 체계적 차이로 따로 본다.
- `regression_event_refusal.yaml`의 업체 100 문항(061, 090, 099, 080)은 결과를 따로 표로 남긴다.

## 5. 다음 단계(이 계획 밖)

P0가 통과하면 HF Qwen3-8B(BF16)에서 같은 A/B를 재현하고(HF harness에 prompt 선택을 더한다), 그 뒤 Partial-P1
(불필요해진 설명 삭제), Partial thinking ON 대 OFF 순서로 간다. 각 단계는 별도 계획으로 정한다.
fingerprint 고정 테스트 3건은 모델 실험으로 동작을 확정한 뒤 한 번만 갱신한다.
