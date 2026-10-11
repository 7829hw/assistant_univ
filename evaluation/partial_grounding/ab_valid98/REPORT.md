# Full vs Partial-P0.2 paired A/B on valid98 — 결과(2026-10-11, 결정 60)

질문: 업체 100의 오류를 보고 고친 P0.2가 독립된 질문 집합(valid98)과 거부 문항에서도 Full contract와 동등하거나 나은가.
답: **아니다(gate 불통과).** 정답률 점 추정이 −2.2%p로 −1%p 기준을 넘고, CI(−9.0 ~ +4.5)로는 비열등도 악화도 보일 수 없다.
악화는 한 가지 오류에 몰려 있다. P0.2가 `dimension_target`(OD 결과를 출발·도착 어느 쪽으로 묶을지)을 빠뜨린다. 이 오류는
P0 → P0.1 경계 규칙 추가와 함께 생겼고 업체 100 기록에서도 같은 방향으로 보인다. 다음 단계는 C(어떤 규칙이 일반화를 해쳤는지 분석)이며,
이 보고서 9–10절에 분석 결과와 제안을 적는다. prompt·code는 고치지 않았다.

## 1. 환경 및 checkpoint

| 항목 | 값 |
|---|---|
| 모델 | Ollama 0.40.1 `qwen3:8b` digest `500a1f06…`(Q4_K_M, base, think 미지정 = thinking on) |
| 장비 | RTX PRO 6000 Blackwell `GPU-d4308fbb…`(host·container 같은 UUID, 결정 56 절차) |
| guard | `cell_guard.py`, 기준 77.6 tok/s. 12셀 모두 중단 없음. 문항 생성 속도 최저 125.4, 셀 중앙값 147–159 tok/s |
| 설정 | 기준일 2026-09-25, `--condition-check`, mock·legacy, unload_per_question, 문항 순서 file. greedy(temperature 0) 1회 + sampling(0.6/0.95/20, seed 20261010–20261014) 5회 |
| 순서 | greedy Full → P0.2. sampling 홀수 회차 Full 먼저, 짝수 회차 P0.2 먼저. smoke(`s01a,s01b,s01c`) 통과 |
| 실행 | 2026-10-11 08:35–13:00 UTC, `runs.log` "ALL DONE", 재실행 없음 |

## 2. prompt hash / code fingerprint

| 항목 | 값 |
|---|---|
| Full prompt | `prompts/geoflow_planner.yaml` `87048d0c…` |
| P0.2 prompt | `evaluation/partial_grounding/prompts/partial_p0_2.yaml` `87fd3441…`(동결, 변경 없음) |
| code | 12셀 모두 `code_commit 95e25ae`, `code_dirty []`. `95e25ae`는 `93d2aa9` 이후 `ab_valid98/` 파일만 더했다 |
| 실행 의미 code 지문 | `ab88a19e…`(spec 기록), parser/composer `9cb8a39` 그대로 |
| gold | `valid98_gold.yaml` sha256 `2b9283b1…` |

## 3. dataset 구성

valid98 98문항(결정 29·43): answered 93, needs_clarification 3(`stage_v7/s01b`, `s01d`, `s02c`), unsupported 2(`stage_v7/s03b`,
`s03d`). 출처는 stage_v7 15, heldout_v8 39, heldout_v9 44문항이다. 정답에 `dimension_target`이 있는 문항이 37개(업체 100보다 OD 묶음 문항이
훨씬 많다). 실행 전 contract 검사에서 정답 grounding을 Full과 Partial로 넣은 결과가 98문항 모두 같았다(`contract_check.json`).

## 4. Full vs P0.2 gate table

sampling 5회 평균. CI는 문항 단위 paired bootstrap 95%, p는 sign-flip permutation.

| Metric | Gate | Full | P0.2 | 차이 | CI / 비고 | 판정 |
|---|---|---|---|---|---|---|
| semantic correctness | −1%p 이내 | 60.8 | 58.6 | **−2.2%p** | [−9.0, +4.5], p=0.55 | **불통과(점 추정)** |
| answerable semantic correctness | −1%p 이내 | 61.1 | 59.1 | **−1.9%p** | [−8.8, +4.7], p=0.63 | **불통과(점 추정)** |
| refusal correctness | 의미 있는 악화 없음 | 56.0 | 48.0 | −8.0%p | [−36, +20], p=0.81, 5문항 | 판정 불가(점 추정 악화) |
| execution completion | −1%p 이내 | 74.6 | 82.2 | +7.5%p | | 통과 |
| grounding failure(셀당) | 증가 없음 | 9.4 | 8.2 | −1.2 | | 통과 |
| structural error(첫 응답, 셀당) | 증가 없음 | 9.6 | 8.4 | −1.2 | | 통과 |
| malformed output | 거의 0 | 0 | 0 | 0 | 첫 응답·최종 모두 | 통과 |
| final JSON tokens | 감소 유지 | 123.9 | 64.0 | −48% | | 통과 |

- 회차별 정답률 Full 61.2 / 63.3 / 61.2 / 59.2 / 59.2, P0.2 56.1 / 62.2 / 62.2 / 56.1 / 56.1. 5회 중 2회 P0.2가 같거나 높다.
- greedy(판정에 단독으로 쓰지 않음): Full 66.3, P0.2 59.2(both correct 45, Full만 20, P0.2만 13, 둘 다 틀림 20).
- −1%p 비열등은 CI로 보일 수 없다. 악화도 통계적으로 보인 것이 아니다. "P0.2가 Full과 동등하다"고도 "더 나쁘다고 증명됐다"고도 쓰지 않는다.
- 업체 100(P0.2 81.2 vs Full 81.0)에서와 달리 valid98에서는 점 추정이 gate 밖이다.

## 5. refusal confusion table

sampling 5회 합계(expected outcome별 관측 수). 정답은 answered 문항의 answered_correctly와 거부 문항의 expected_refusal뿐이다.
`refused(unsupported)`·`refused(clarification)`는 답해야 할 문항을 거부한 오답이다.

| expected | 결과 | Full | P0.2 |
|---|---|---|---|
| answered (465) | answered_correctly | 284 | 275 |
| | answered_wrong | 63 | **107** |
| | failed | 86 | 66 |
| | refused(unsupported) | 27 | 14 |
| | refused(clarification) | 5 | 3 |
| needs_clarification (15) | expected_refusal | 8 | 7 |
| | answered_instead_of_refusal | 7 | 3 |
| | failed(wrong_refusal_kind) | 0 | 5 |
| unsupported (10) | expected_refusal | 6 | 5 |
| | failed(wrong_refusal_kind) | 3 | 4 |
| | needs_clarification(wrong_refusal_kind) | 0 | 1 |
| | wrong_refusal_reason | 1 | 0 |

문항별(greedy / r1–r5):

| 문항 | expected | Full | P0.2 |
|---|---|---|---|
| s01b | clarification | ✓ / 답 ✓ 답 답 답(1/5) | ✓ / ✓ ✓ ✓ 답 답(3/5) |
| s01d | clarification | ✓ / ✓ ✓ ✓ 답 ✓(4/5) | 답 / ✓ ✓ fail(INVALID_FACTOR) ✓ fail(INVALID_FACTOR)(3/5) |
| s02c | clarification | 답 / ✓ 답 ✓ 답 ✓(3/5) | ✓ / fail(INVALID_FACTOR) ✓ fail fail 답(1/5) |
| s03b | unsupported | fail / ✓ fail(INVALID_CONCEPT) ✓ ✓ ✓(4/5) | ✓ / fail(INVALID_FACTOR_COMBINATION) ✓ clarification ✓ fail(2/5) |
| s03d | unsupported | fail / fail ✓ 이유 다름 ✓ fail(2/5) | ✓ / fail ✓ ✓ ✓ fail(3/5) |

- 거부 문항 정답 관측 수는 Full 14/25, P0.2 12/25다. 차이는 관측 2개다.
- P0.2는 "거부해야 할 문항에 답하기"가 줄었고(7 → 3), 대신 실패가 늘었다(3 → 9). P0.2의 needs_clarification 실패 5건은 모두
  `INVALID_FACTOR`이며, 첫 응답에 `"dimension": "week"`를 넣고 repair가 범위를 벗어난 경우다(9절 E2).
- 답해야 할 문항을 거부한 경우는 P0.2가 적다(32 → 17).

## 6. paired comparison

| 회차 | 둘 다 정답 | Full만 정답 | P0.2만 정답 | 둘 다 오답 |
|---|---|---|---|---|
| r1 | 42 | 18 | 13 | 25 |
| r2 | 47 | 15 | 14 | 22 |
| r3 | 44 | 16 | 17 | 21 |
| r4 | 41 | 17 | 14 | 26 |
| r5 | 37 | 21 | 18 | 22 |

- 일관된 개선(k_P0.2 − k_Full ≥ 4): `heldout_v8/t02`(1 → 5, Full은 실패), `heldout_v9/h42`(0 → 4, Full은 refused_unsupported 3회).
- 일관된 악화(≤ −4):
  - `heldout_v8/t07`(5 → 1): 동성로에 region "대구"를 붙여 place 불일치.
  - `heldout_v9/h18`(4 → 0): `dimension_target` 누락.
  - `heldout_v9/h36`(4 → 0): scope id의 지역명을 묻는 질문에 NO_MEASURE 4회, unsupported 1회.
- k 차이 ±2–3 문항 28개가 문항별로 `paired_items.csv`에 있다. 악화 쪽(−2·−3) 다수가 OD 묶음 문항(t18, t19, h04, h08, h13, h17, h20, h21)이다.
- 거부 판단이 바뀐 문항 28개(`analysis.json` `refusal_changed`). 대부분 Full이 answerable 문항을 거부하다가 P0.2에서 거부하지 않게 된 경우다
  (h06 3 → 0, h42 4 → 0, h19 2 → 0 등). 반대 방향은 s01a(0 → 2), s02b(0 → 2), t15(0 → 2) 등이다.
- 새 structural failure(Full 0회, P0.2 1회 이상) 14문항. 가장 많은 것은 h36 4회, s02b·s02c 3회다.

## 7. structural error census

첫 응답 기준 패턴 수(sampling 5회 합계, `analyze.py`의 heuristic). A–F는 오류 확정이 아니라 패턴 수다. 예를 들어 B는 Full도
"읍면동" 같은 그룹 이름을 place로 쓰는 경우를 센다.

| 유형 | 정의(heuristic) | Full | P0.2 |
|---|---|---|---|
| A | subtype이 ontology subtype이 아님 | 9 | 6 |
| B | place에 dimension 단어(그룹 기준)가 들어감 | 15 | 24 |
| C | 측정값 concept가 정확히 하나가 아님 | 4 | 4 |
| D | scope concept에 value 없음 | 3 | 0 |
| E1 | dimension에 pickup/dropoff/both | 13 | 6 |
| E2 | dimension에 week/month | 1 | **15** |
| E3 | time 형식이 `HHMMSS-HHMMSS`가 아님 | 1 | 6 |
| F | 정답이 지역명인데 값 없는 place가 없음 | 0 | 4 |

첫 응답 structural error(grounding 검사 오류)는 셀당 Full 9.6, P0.2 8.4다. malformed JSON은 두 arm 모두 0이다. 최종 grounding error는
grounding failure와 같다(9.4 vs 8.2).

## 8. efficiency

| 지표 | Full | P0.2 | 차이 |
|---|---|---|---|
| 최종 JSON token(Qwen3 tokenizer, 평균) | 123.9 | 64.0 | −48% |
| eval_count 중앙값 | 795.8 | 583.9 | −27% |
| thinking 길이 중앙값(chars) | 2394 | 1940 | −19% |
| 문항 wall-clock 중앙값 | 8.63 s | 7.10 s | −18% |
| 셀 총 wall-clock | 983 s | 818 s | −17% |
| repair 호출(셀당) | 35.0 | 25.8 | −26% |
| repair 후 최종 정답 비율 | 40.8% | 34.4% | −6.4%p |
| repair 후 최종 답함 비율 | 57.0% | 56.6% | −0.4%p |
| timeout / retry(sampling) | 0 / 0 | 0 / 0 | |

greedy Full 셀에 timeout 2건, retry 1건이 있었다(sampling에는 없음).

## 9. 새로 발견된 failure mode(기록만, 고치지 않음)

부분집합과 원인 분석은 결과를 본 뒤 정한 탐색 분석이다(`explore_failure_modes.py` → `explore_failure_modes.json`). gate 판정에 쓰지 않는다.

1. **`dimension_target` 누락(주 원인).**
   - valid98 sampling에서 정답이 pickup/dropoff인데 P0.2가 비운 경우는 84건이고, Full은 28건이다.
   - P0.2 answered_wrong 증가(63 → 107)의 대부분이다. 단일 원인 범주 `factor:dimension_target`만으로 Full 13건, P0.2 51건이다.
   - 정답에 `dimension_target`이 있는 37문항: Full 40.0, P0.2 30.8, −9.2%p(CI −19.5 ~ +0.5).
   - 나머지 61문항: Full 73.4, P0.2 75.4, +2.0%p(CI −6.6 ~ +10.5).
   - 업체 100의 기존 기록(재실행 없음, `ab_p0/runs`)에서 같은 누락은 Full 11, P0 9, P0.1 29, P0.2 34건이다. P0에는 없고 P0.1에서 생겼다.
     업체 100에는 이 유형의 문항이 적어 정답률 차이로 드러나지 않았다.
   - 가설(검증 안 됨): P0.1에서 들어온 경계 규칙 2("pickup, dropoff, both … 이런 값을 subtype에 넣지 않습니다")와 규칙 4("pickup, dropoff,
     both를 독립 concept로 만들지 않습니다")가 이 값들을 어디에도 쓰지 말라는 신호로 읽힌다. 두 규칙은 od_role 자리만 알려주고
     `factors.dimension_target` 자리는 말하지 않는다. 의미 section의 dimension_target 설명은 P0.2에 그대로 있다.
2. **`dimension`에 week/month(E2).**
   - 첫 응답 15건(Full 1건), 9문항에서 나왔다. 주로 stage_v7의 주별·월별 rollup 문항이다.
   - factor repair가 dimension을 지우면서 다른 factor까지 바꾸려다 `REPAIR_OUT_OF_SCOPE`로 실패한다. needs_clarification 문항 s01d·s02c의
     실패 5건이 여기서 나왔다.
   - 가설(검증 안 됨): 규칙 2의 금지 목록에 week/month가 들어 있고, 규칙 3이 "그룹 기준은 factors에"라고만 해서 bucket과 dimension을
     구분하지 못한다.
3. **scope id의 지역명 질문(h36, F 4건).** `scope:district:… 이 어느 지역인지` 질문에 값 없는 place를 내지 않아 NO_MEASURE가 나온다(4/5).
   업체 100의 082와 같은 계열이다. 규칙 6의 예외 문장이 있어도 재현된다.
4. **place region 채움(t07).** 동성로에 region "대구"를 붙인다(4/5). 예시 3과 같은 장소명이다. 원인은 모른다.
5. **time 형식(E3 6건, Full 1건).** 적은 수다.

## 10. 다음 단계 추천

**판정: A가 아니다.**

- 정답률 점 추정(−2.2%p, answerable −1.9%p)이 gate 밖이다. 거부 정답률도 점 추정상 나쁘다(5문항이라 판정 불가).
- 정답률이 유지되지 않으므로 B(정답률 유지·거부만 악화)에도 해당하지 않는다.
- 악화가 통계적으로 확실하지는 않다. 하지만 9절의 탐색 분석이 특정 규칙 변경(P0 → P0.1 경계 규칙)과 연결된 일반화 손실을 보여 준다.
  따라서 사용자 지시의 C 경로(어떤 P0 → P0.2 규칙이 일반화를 해쳤는지 분석)를 따른다.
- 그 분석의 1차 결과가 9절이다.

이 단계에서 하지 않은 것: P0.3 작성, 082·h36 전용 규칙, 새 factor 규칙, 예시 추가, parser completion·repair 수정, 업체 100 재실행, push.

사용자 결정이 필요한 제안:

1. P0.2를 candidate contract로 동결하지 않는다. HF 재현은 보류한다.
2. 최소 변경 실험은 따로 설계한다. 후보는 규칙 2·4에서 pickup/dropoff/both, week/month의 **올바른 자리**를 함께 적는 것이다
   (`attributes.od_role` / `factors.dimension_target`, `factors.bucket`). 금지 목록만 두지 않는다.
   - 이것은 valid98 결과를 보고 만든 변경이다. 같은 valid98로 다시 판정하면 독립성이 사라진다.
   - 판정에는 valid98·업체 100이 아닌 다른 보류 집합을 쓰거나, 이 한계를 결정에 명시해야 한다.
3. 비교 기준으로 P0(경계 규칙 없음)도 같은 실험에 넣을 수 있다. 업체 100에서 P0의 `dimension_target` 누락은 Full 수준이었다.
   다만 P0는 structural error gate를 넘지 못했다.

## 파일

- `PLAN.md`: 측정 계획(결정 60). `contract_check.py` / `contract_check.json`: 실행 전 contract 검사.
- `run_cell.sh`, `run_all.sh`, `run_all.log`, `runs.log`: 실행.
- `raw/`: 12셀 + smoke의 결과(`*.json`, `*.jsonl`), guard·pre/post·spec·wait 기록.
- `analyze.py` → `analysis.json`, `paired_items.csv`: 사전 정의 분석.
- `explore_failure_modes.py` → `explore_failure_modes.json`: 결과를 본 뒤의 탐색 분석.
