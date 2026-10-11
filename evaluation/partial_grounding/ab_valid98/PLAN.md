# Full vs Partial-P0.2 paired A/B on valid98 (ab_valid98) — 확정 2026-10-11(사용자, 결정 60)

질문: 업체 100의 오류를 보고 고친 P0.2가 독립된 질문 집합(valid98)과 거부 문항에서도 Full contract와 동등하거나 나은가.
이 측정은 P0.2를 개선하려는 것이 아니다. 결과를 보기 전에는 prompt(P0.3, 082 규칙, factor 규칙, 예시), parser completion,
repair prompt를 고치지 않는다. 업체 100은 다시 돌리지 않는다.

## 1. 고정 기준

| 항목 | 값 |
|---|---|
| Full prompt | 기본 `prompts/geoflow_planner.yaml`, hash `87048d0c…` |
| P0.2 prompt | `evaluation/partial_grounding/prompts/partial_p0_2.yaml`, hash `87fd3441…` |
| 코드 | parser/composer `9cb8a39`, 실행 의미 코드 지문 `ab88a19e`, P0.2 결과 commit `93d2aa9` |
| 모델·장비 | Ollama `qwen3:8b`(base, cell E 조건), ab_p0와 같음. 결정 56의 장비 절차와 `cell_guard.py`(77.6 tok/s) |
| 설정 | ab_p0 `PLAN.md` 1절과 같다: think 미지정, `--condition-check`, 기준일 2026-09-25, mock·legacy, unload_per_question, 문항 순서 file, `--record-env`, greedy = temperature 0, sampling = 0.6/0.95/20, seed 20261010–20261014(같은 회차 두 arm 같은 seed), context·max tokens는 harness 기본(두 arm 같음) |
| 문항 | `sft_dpo_inventory/pilot_001_analysis/decision43/valid98_gold.yaml`(결정 29의 valid98을 업체 100 형식으로 모은 것, 결정 43) |

## 2. 평가 계약(실행 전 확인, 2026-10-11)

- 98문항: answered 93, needs_clarification 3(`stage_v7/s01b`, `s01d`, `s02c`, expected_error AMBIGUOUS_INNER_AGGREGATION 또는
  AMBIGUOUS_AGGREGATION_STAGE), unsupported 2(`stage_v7/s03b`, `s03d`, expected_error UNVERIFIED_TIMS_CONTRACT). 기타 없음.
- 기존 Full 결과: valid98 Ollama 기록은 결정 43의 B-conv·Ollama-최종(다른 모델, 옛 장비)과 HF 기록뿐이다. 같은 조건의 Full이 없으므로
  Full도 잰다.
- 채점은 harness의 `evaluate_vendor100.score`(업체 100과 같음). 범주의 뜻(구현 기준):
  - 답해야 할 문항: `match`(정답), `answered_mismatch`(답했지만 다름), `refused_unsupported`·`refused_clarification`(답해야 하는데
    거부; 요청서의 refused_supported에 해당), `failed`(실패).
  - 거부해야 할 문항: `expected_refusal`(기대한 종류로 멈췄고 오류 코드도 허용 목록에 있음 = 정답), `wrong_refusal_reason`(종류는 맞지만
    오류 코드가 다름, 오답), `answered_instead_of_refusal`(답함), `wrong_refusal_kind`(그 밖의 결과 전부: 다른 종류의 거부와 실패).
    별도의 failed_instead_of_refusal 범주는 없으므로, refusal confusion 표에서는 `wrong_refusal_kind`를 기록된 outcome으로 나눠
    "failed"와 "다른 종류의 거부"로 보인다(정의를 바꾸지 않고 나눠 보이기만 한다).
  - 정답 = `match` + `expected_refusal`. `refused_unsupported`는 정답이 아니다.
- refusal correctness는 측정할 수 있지만 거부 문항이 5개뿐이라 검정력이 매우 낮다. 문항별로 보고한다.
- harness는 `--planner-prompt`로 prompt를 고른다(ab_p0와 같음).

## 3. 실행 전 contract 검사(`contract_check.py` → `contract_check.json`)

P0.2 예시 1–6은 모두 answered. valid98 98문항의 정답 grounding을 Full과 Partial(`to_partial`)로 같은 pipeline에 넣은 결과가 98문항 모두
같다(match 93, expected_refusal 5). 유형별 대표: answerable `stage_v7/s01a`, unsupported `stage_v7/s03b`, needs_clarification
`stage_v7/s01b`, scope 직접 입력 `heldout_v9/h36`, place `stage_v7/s01a`, dimension `stage_v7/s04a`, OD `heldout_v8/t01`.

## 4. 셀(`run_all.sh`, 출력 `raw/`)

1. smoke: P0.2 greedy, `stage_v7/s01a,s01b,s01c`. ab_p0와 같은 통과 조건(계약 오류 없음). 분석에 쓰지 않는다.
2. greedy: Full → P0.2.
3. sampling r1–r5: 홀수 회차 Full 먼저, 짝수 회차 P0.2 먼저.

guard가 멈춘 셀은 `ABORTED_*`로 남기고 전체를 멈춘 뒤 보고한다. 결과가 이상해도 다시 돌리지 않는다.

## 5. 지표와 분석(`analyze.py` → `analysis.json`, `paired_items.csv`)

- Primary: semantic correctness, answerable semantic correctness, refusal correctness, execution completion, grounding failure
  (ab_p0와 같은 정의).
- Structural: 첫 응답 structural error, 최종 grounding error, malformed JSON(JSON_NOT_FOUND·JSON_PARSE_FAILED), repair 호출 수와
  repair 성공률(repair 호출이 있었던 문항 중 최종 정답 비율, 최종 답함 비율).
- Efficiency: 최종 JSON token(Qwen3-8B tokenizer), eval_count, thinking 길이, 문항 wall-clock, timeout 수, 재호출(retry) 수.
- Refusal confusion: expected outcome별 결과 분포(arm별).
- P0.2 오류 census A–F(요청서 6절 분류).
- Paired: 문항별 k_Full/5, k_P0.2/5, 회차별 2×2, 일관된 개선·악화(|k차| ≥ 4), 거부 판단이 바뀐 문항, 새 structural failure 문항,
  paired bootstrap 95% CI와 sign-flip permutation p. greedy는 따로 적고 판정에 단독으로 쓰지 않는다.

## 6. Gate(사용자 기준)

| Metric | Gate |
|---|---|
| semantic correctness | Full 대비 −1%p 이내 |
| answerable semantic correctness | Full 대비 −1%p 이내 |
| refusal correctness | 의미 있는 악화 없음 |
| grounding failure | 증가하지 않음 |
| execution completion | Full 대비 −1%p 이내 |
| structural error | Full보다 증가하지 않는 것이 이상적 |
| malformed output | 거의 0 |
| final JSON tokens | Full보다 감소 유지 |

CI로 −1%p non-inferiority를 보일 수 없으면 point estimate, 문항별 결과, CI를 모두 보이고 증명되었다고 쓰지 않는다.
결과에 따른 다음 단계(사용자 지시): A 통과 → P0.2를 candidate contract로 동결하고 HF에서 재현. B 정답률 유지·거부 악화 → 거부 악화
문항을 분리한 뒤 최소 변경을 별도 실험으로 설계. C 명확한 악화 → P0와 P0.2 차이 중 어떤 규칙이 일반화를 해쳤는지 분석.
