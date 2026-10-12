# P0.3 sel154 독립 검증 결과

2026-10-12. 사전 계획: `PLAN.md`(결정 61). 원자료: `raw/`. 분석: `analysis.json`(사전 고정 `analyze.py`), `paired_items.csv`,
사후 탐색 `explore_p0_3.json`(`explore_p0_3.py`, 판정에 쓰지 않음). 무결성 표: `integrity.txt`.

## 1. 결론

- **전체 정확도는 점 추정상 Full과 같은 수준이다.**
  - sampling 5회 기준 semantic correctness는 Full 71.82%, P0.3 71.69%로 −0.13%p다.
  - 문항 단위 paired bootstrap 95% CI는 −4.7 ~ +4.3%p다.
  - −1%p 기준 통계적 비열등은 확인되지 않았다. CI 폭(약 ±4.5%p)이 기준보다 훨씬 넓다.
- **H4(dimension_target)와 H5(week/month)는 사전 정의대로 불통과다.**
  - P0.3의 dimension_target 누락률은 43%로 P0 26%, Full 27%보다 오히려 높다. P0.3 − P0 = +17%p(CI +6 ~ +29), permutation p = 0.017이다.
  - 첫 응답에서 dimension에 week/month를 넣은 관측은 P0.3 13건, Full 5건으로 8건 많다. 사전 기준 "Full보다 5건 이상"에 해당한다.
  - 다만 week/month 오류는 repair 단계에서 모두 고쳐졌다. 최종 bucket 차이는 세 arm 모두 0이고, bucket 부분집합 정답률도 Full과 같은 수준이다(79.2 vs 80.0%).
- **결론 분기는 사전 계획 9절의 B다.** 전체 성능은 점 추정상 통과했지만 dimension_target 문제는 남았고 더 나빠졌다.
  - P0.3를 candidate로 동결하지 않는다.
  - HF 재현과 P0.4 작성으로 넘어가지 않는다.
- **핵심 질문에 대한 답:**
  - "쓰지 말라"는 경계 규칙에 목적지를 명시하는 것만으로는 독립 set에서 dimension_target 누락이 줄지 않았다.
  - 대신 첫 응답 structural error(13.4 → 9.0)와 grounding failure(12.6 → 8.6)는 줄었다.
  - 그 대가로 실패가 조용한 오답으로 바뀌었다(answered_wrong 85 → 106). 13장에서 다시 다룬다.

## 2. 실행 환경과 무결성 확인

| 항목 | 값 |
|---|---|
| 모델 | Ollama `qwen3:8b`, digest `500a1f06` |
| Ollama | **0.40.3**(아래 참고) |
| GPU | RTX PRO 6000 `GPU-d4308fbb…`, 모든 cell `ollama ps` 100% GPU, context 40960 |
| code fingerprint | `ab88a19e`(19 cell 모두 일치) |
| prompt hash | Full `87048d0c`, P0 `d7f4c12a`, P0.3 `8b157c9a`(모든 cell에서 기대값과 일치) |
| gold | `sel154_gold.yaml` sha256 `aab80783`(모든 cell 일치) |
| 문항 수 | 모든 cell 154/154 |
| seed | greedy temperature 0, sampling 0.6/0.95/20, round r의 seed는 20261009+r. 세 arm이 같은 seed를 쓰고, arm 순서는 PLAN대로 돌렸다 |
| timeout / retry | 0 / 0(모든 호출 `done_reason=stop`) |
| 속도 guard(77.6 tok/s) | 모든 측정 cell 통과. cell별 최저 112.8 ~ 140.8 tok/s |
| model reset | 실패 0 |

실행 경과(모두 `PLAN.md` 끝의 기록에 남겼다):

1. 2026-10-11 첫 시도는 host 재부팅 뒤 컨테이너가 깨져 precheck에서 멈췄다. 모델 호출은 없었다.
2. 사용자가 컨테이너를 복구했고, Ollama가 0.40.1에서 0.40.3으로 바뀌었다. 사용자 지시("최신버전으로")에 따라 0.40.3으로 쟀다.
   - `cell_guard.py`의 기대 버전을 환경변수로 받게 했다. 기본값은 0.40.1이고 이 run만 0.40.3을 지정한다.
   - 세 arm을 모두 같은 버전으로 쟀으므로 arm 간 비교는 한 버전 안의 비교다.
   - ab_p0과 ab_valid98(0.40.1)의 수치와 직접 비교하면 버전 차이가 섞인다.
3. 첫 smoke는 컨테이너 재생성 직후 첫 호출이 느려(43.7 tok/s, load 43.6 s) guard에 걸렸다.
   - 결과는 `raw/smoke/ABORTED_p0_3_smoke.*`로 남겼고 판정에 쓰지 않는다.
   - 진단 호출에서 206 tok/s를 확인했다. 이후 model unload를 기다렸다가 `run_all.sh`를 처음부터 다시 쟀다. 이는 무효 측정의 대체다.
4. 결과를 본 뒤 `analyze.py`에서 분석이 멈추지 않도록 한 가지만 고쳤다.
   - 원인: 첫 응답 재검사 중 parser가 GeoFlowError가 아닌 `TypeError`를 냈다(concept value가 dict인 응답).
   - 처리: 실행 harness와 같은 `UNHANDLED_EXCEPTION` 구조 오류로 센다.
   - 범위: Full 관측 2건(`indepv4/k18` greedy와 r2)에만 해당한다. P0과 P0.3에는 해당 관측이 없다.
   - 지표와 부분집합 정의는 바꾸지 않았다.

## 3. 평가셋 구성

sel154는 selection_v1(100문항)과 같은 후보 pool에서 남은 54문항을 합친 것이다(결정 61, 실행 전 확정).

| | 값 |
|---|---|
| 문항 | 154 |
| expected_outcome | answered 144, unsupported 5, needs_clarification 5 |
| dt(gold에 dimension_target) | 20 |
| bucket(gold에 bucket) | 24 |
| refusal | 10 |

- **오염 관계:**
  - selection_v1은 checkpoint 선택에 쓰였지만 P0.x prompt 설계에는 쓰이지 않았다.
  - valid98과 vendor100은 P0.x 설계에 쓰였으므로 이 판정에서 제외했다.
- **gold 점검:** gold payload를 frozen pipeline에 넣으면 Full과 Partial 모두 144 match, 10 expected_refusal이 나온다.
- **단일 사용:** 이 set은 P0.3 판정에 한 번만 쓴다. 결과를 봤으므로 이후 P0.x 설계 근거로 쓰면 오염된다.

## 4. Full / P0 / P0.3 전체 결과

sampling 5회 평균. 괄호 안은 회차별 범위다.

| 지표 | Full | P0 | P0.3 |
|---|---:|---:|---:|
| semantic correctness | 71.82% (70.1–73.4) | 71.30% (70.1–72.7) | 71.69% (66.9–76.0) |
| answerable semantic correctness | 71.53% | 71.25% | 71.11% |
| refusal correctness | 76.0% | 72.0% | 80.0% |
| execution completion | 83.33% | 81.25% | 85.83% |
| grounding failure(건/회) | 12.6 | 15.4 | 8.6 |
| grounding_ok(건/회) | 103.2 | 102.2 | 103.6 |
| 첫 응답 structural error(건/회) | 13.4 | 15.2 | 9.0 |
| malformed JSON(첫/최종) | 0 / 0 | 0 / 0 | 0 / 0 |
| repair 호출(건/회) | 38.0 | 29.2 | 38.6 |
| repair 뒤 정답률 | 51.6% | 43.0% | 45.3% |

greedy는 판정에 쓰지 않고 참고로만 본다.

| greedy | Full | P0 | P0.3 |
|---|---:|---:|---:|
| semantic | 77.92% | 68.83% | 74.03% |
| answerable | 77.78% | 67.36% | 73.61% |
| refusal | 80% | 90% | 80% |
| completion | 88.2% | 80.6% | 88.9% |
| structural | 12 | 18 | 5 |

greedy는 한 번의 결정적 실행이라 분산을 반영하지 못한다. 그래도 P0.3가 Full보다 −3.9%p 낮다는 점은 적어 둔다.

## 5. Gate 판정

| 지표 | Full | P0 | P0.3 | P0.3 − Full | 판정 |
|---|---:|---:|---:|---:|---|
| semantic correctness | 71.82 | 71.30 | 71.69 | −0.13%p (CI −4.7 ~ +4.3) | 점 추정상 통과. 통계적 non-inferiority는 확인되지 않음 |
| answerable semantic correctness | 71.53 | 71.25 | 71.11 | −0.42%p (CI −5.1 ~ +4.4) | 점 추정상 통과. 통계적 non-inferiority는 확인되지 않음 |
| refusal correctness | 76 | 72 | 80 | +4%p (CI −4 ~ +14) | 통과. 문항별 악화는 k23 하나(8장) |
| execution completion | 83.33 | 81.25 | 85.83 | +2.5%p | 통과 |
| grounding failure | 12.6 | 15.4 | 8.6 | −4.0 | 통과 |
| first-response structural error | 13.4 | 15.2 | 9.0 | −4.4 | 통과 |
| malformed JSON | 0 | 0 | 0 | 0 | 통과 |
| final JSON tokens(평균) | 119.3 | 66.2 | 62.4 | −47.7% | 통과 |
| dimension_target omission(dt 관측 100) | 27% | 26% | 43% | +16%p (CI +7 ~ +26). P0 대비 +17%p (CI +6 ~ +29) | **불통과**(P0보다 개선이어야 함) |
| week/month-as-dimension(sampling 합계) | 5 | 4 | 13 | +8 | **불통과**(사전 기준 +5 이상) |

가설별 판정:

- H1(semantic ≥ Full − 1%p): 점 추정상 통과, 통계적으로는 미확인.
- H2(answerable ≥ Full − 1%p): 점 추정상 통과, 통계적으로는 미확인.
- H3(structural ≤ Full): 통과.
- H4(dt 누락 < P0, 또는 Full + 5%p 이내): 불통과.
- H5(week/month가 P0.2 valid98 수준으로 재현되지 않음): 불통과.
  - 사전 정의는 "Full보다 5건 이상 많으면 뚜렷한 증가"이고, P0.3는 Full보다 8건 많다.
  - 참고로 P0.2 valid98의 15건(Full 1건)보다는 적다. 최종 결과에는 영향이 없었다(7장).
- H6(JSON token < Full): 통과.

## 6. dimension_target 부분집합(20문항, arm별 sampling 100관측)

| | Full | P0 | P0.3 |
|---|---:|---:|---:|
| 정답률 | 44% | 39% | 35% |
| P0.3 − Full paired(CI) | | −5%p (−16 ~ +6) | −9%p (−20 ~ +1) |
| 최종 dimension_target 누락(gold 값 → None) | 27 | 26 | 43 |
| 최종 dimension_target 잘못된 값 | 0 | 1 | 0 |
| 최종 grounding 없음(no_grounding, 따로 셈) | 7 | 17 | 3 |
| 첫 응답 dimension_target 누락 | 30 | 33 | 47 |
| 첫 응답 dimension에 pickup/dropoff/both | 3 | 9 | 1 |
| dt가 아닌 문항에 dimension_target이 생김 | 7 | 1 | 6 |
| od_role ↔ dimension_target 혼동(attribution D, 전체) | 13 | 9 | 14 |
| 첫 응답에서 dt 없이 같은 값의 od_role만 둠(사후 탐색) | 5 | 10 | 8 |

- **P0.3가 줄인 것:** dimension에 pickup/dropoff/both를 넣는 오류(3 / 9 / 1)와 no_grounding(7 / 17 / 3).
- **P0.3가 줄이지 못한 것:** dimension_target 자체를 적지 않는 누락. 누락 43건 중 장소 od_role로 대신 적은 경우는 8건뿐이다.
- **누락이 몰린 문항(P0.3, 5회 중):**
  - n35, k28, n05, k34가 각 5회.
  - m03, m04가 각 4회.
  - g12, n34, m02가 각 3회.
  - 이 가운데 n05와 k28은 Full에서 각 1회와 3회였다.
- **공통 표현:** 질문이 "승차 지역별"처럼 그룹 기준을 직접 말하지 않고, 끝점이 사건 표현 안에 들어 있다.
  - 예: "내린 위치를 H3 셀 기준으로", "어느 H3 셀에서 가장 많이 내렸는지", "승차 건수를 시도 단위로".
  - rule 11 B의 예시는 "승차 지역별"과 "하차 지역별"뿐이다. 모델이 이 표면 표현이 있을 때만 dimension_target을 적는 것처럼 보인다. 이는 사후 해석이며 검증된 것은 아니다.
- **답:** P0.3는 P0.2에서 발견된 dimension_target 누락 문제를 독립 set에서 줄이지 못했다. 오히려 Full과 P0(둘 다 약 27%)보다 늘렸다.
  - sel154에서는 P0도 Full과 누락률이 같다. 따라서 이 set에서는 role 제거 자체가 누락을 늘린다는 근거도 없다.

## 7. bucket 부분집합(24문항, arm별 sampling 120관측)

| | Full | P0 | P0.3 |
|---|---:|---:|---:|
| 정답률 | 80.0% | 80.8% | 79.2% |
| P0.3 − Full paired(CI) | | +0.8%p (−9.2 ~ +11.7) | −0.8%p (−10.8 ~ +9.2) |
| 최종 bucket 누락 / 잘못된 값 | 0 / 0 | 0 / 0 | 0 / 0 |
| 첫 응답 bucket 누락 | 4 | 3 | 10 |
| 첫 응답 `"dimension": "week"` | 3 | 2 | 7 |
| 첫 응답 `"dimension": "month"` | 2 | 2 | 6 |
| aggregation_spec 차이(aggregation/rollup 혼동) | 27 | 25 | 23 |
| factor:dimension 차이 | 0 | 0 | 0 |

- week/month를 dimension에 넣은 관측은 모두 bucket 부분집합 안에 있다.
  - P0.3: n20 1, k37 2, g43 1, n23 1, g29 1, g30 3, c08e 2, g28 1, c08d 1회.
  - 이 첫 응답 오류는 repair 뒤 최종 grounding에서 모두 사라졌다. 최종 bucket 차이는 0이다.
- bucket 부분집합의 남은 오류는 주로 aggregation_spec(aggregation/rollup)이며 세 arm이 비슷하다.
- rule 11 D("week와 month를 dimension에 넣지 않습니다")가 있는데도 첫 응답의 time-as-dimension이 Full의 2.6배다. 금지와 목적지를 함께 적어도 첫 응답 행동은 개선되지 않았다.

## 8. refusal 분석

expected outcome별 confusion(sampling 5회 합계):

| expected | 결과 | Full | P0 | P0.3 |
|---|---|---:|---:|---:|
| answered(720) | correct answer | 515 | 513 | 512 |
| | refused_unsupported | 31 | 36 | 26 |
| | refused_clarification | 3 | 0 | 4 |
| | failed | 86 | 99 | 72 |
| | other wrong answer | 85 | 72 | 106 |
| unsupported(25) | expected_refusal | 24 | 23 | 23 |
| | wrong_refusal_kind(needs_clarification로 거부) | 1 | 2 | 2 |
| | answered_instead_of_refusal | 0 | 0 | 0 |
| needs_clarification(25) | expected_refusal | 14 | 13 | 17 |
| | wrong_refusal_kind | 3 | 1 | 1 |
| | answered_instead_of_refusal | 8 | 11 | 7 |

answered 문항에서 P0.3는 failed가 줄고 other wrong answer가 늘었다(Full 대비 −14, +21). 실패가 조용한 오답으로 바뀐 것이다.
(`analysis.json`의 confusion은 Full unsupported 1건과 needs_clarification 3건을 `failed`로 적었다. 위 표는 문항별 재집계(`explore_p0_3.json`) 기준이다.)

문항별 결과(sampling 5회, `g:`는 greedy):

| 문항 | expected | Full | P0 | P0.3 |
|---|---|---|---|---|
| old44/g17 | unsupported | 정답 5, g정답 | 정답 5, g정답 | 정답 5, g정답 |
| indepv2/n25 | unsupported | 정답 5, g정답 | 정답 3, 잘못된 kind 2, g정답 | 정답 5, g정답 |
| indepv2/n27 | unsupported | 정답 5, g정답 | 정답 5, g정답 | 정답 5, g정답 |
| indepv3/m39 | unsupported | 정답 5, g정답 | 정답 5, g정답 | 정답 5, g정답 |
| indepv4/k23 | unsupported | 정답 4, 잘못된 kind 1, g정답 | 정답 5, g정답 | **정답 3, 잘못된 kind 2**, g정답 |
| old44/g44 | needs_clarification | 정답 4, 잘못된 kind 1, g정답 | 정답 4, 답함 1, g정답 | 정답 4, 답함 1, g정답 |
| indepv3/m24 | needs_clarification | 정답 2, 답함 2, 잘못된 kind 1, g잘못된 kind | 답함 4, 잘못된 kind 1, g답함 | 정답 2, 답함 3, g정답 |
| contrast/c08b | needs_clarification | 정답 5, g정답 | 정답 4, 답함 1, g정답 | 정답 5, g정답 |
| indepv2/n23 | needs_clarification | 정답 1, 답함 3, 잘못된 kind 1, g정답 | 정답 4, 답함 1, g정답 | 정답 2, 답함 2, 잘못된 kind 1, g답함 |
| indepv4/k39 | needs_clarification | 정답 2, 답함 3, g답함 | 정답 1, 답함 4, g정답 | **정답 4**, 답함 1, g답함 |

- P0.3가 Full보다 나빠진 refusal 문항은 k23 하나다(unsupported를 needs_clarification으로 거부 2회).
- k39는 좋아졌다(2 → 4회). 나머지는 같거나 ±1회다.
- 10문항, 50관측 규모라 의미 있는 악화로 보지 않는다.

## 9. 오류 유형 A–I

정답이 아닌 관측(sampling 합계)을 PLAN 8절 규칙으로 나눈다. 한 관측이 여러 범주에 들 수 있다.

| 범주 | Full | P0 | P0.3 | P0.3 − Full |
|---|---:|---:|---:|---:|
| A. model semantic decision | 69 | 62 | 74 | +5 |
| B. concept/factor/attribute boundary | 31 | 67 | 19 | −12 |
| C. dimension_target omission | 27 | 26 | 43 | **+16** |
| D. od_role ↔ dimension_target confusion | 13 | 9 | 14 | +1 |
| E. bucket ↔ dimension confusion | 2 | 3 | 7 | +5 |
| F. place/scope value omission | 34 | 17 | 19 | −15 |
| G. measure omission | 34 | 36 | 44 | +10 |
| H. refusal error | 46 | 50 | 40 | −6 |
| I. parser/composer/repair failure | 40 | 34 | 38 | −2 |

- I의 최종 오류 코드: Full은 NOT_FOUND 10, MISSING_RELATION_QUALIFIER 10, INVALID_FACTOR_COMBINATION 10. P0.3는 MISSING_RELATION_QUALIFIER 13, INVALID_FACTOR_COMBINATION 8, NOT_FOUND 7, UNSUPPORTED_COMBINATION 6.
- 첫 응답 census(sampling 합계):

  | census | Full | P0 | P0.3 |
  |---|---:|---:|---:|
  | A_non_subtype | 20 | 89 | 10 |
  | B_dimension_as_place | 44 | 39 | 39 |
  | C_measure_missing_or_multiple | 9 | 25 | 18 |
  | D_scope_value_missing | 5 | 3 | 1 |
  | E1_od_as_dimension | 4 | 9 | 1 |
  | E2_bucket_as_dimension | 5 | 4 | 13 |
  | E3_time_format | 2 | 7 | 7 |
  | F_place_answer_missing | 6 | 10 | 18 |

**J. exploratory**(사후 발견, A–I 정의는 바꾸지 않음): scope id 역조회 질문에서 답이 될 장소 concept를 빠뜨리는 문제.

- 해당 문항:
  - indepv2/n40 "scope:gz:3982는 어떤 장소야?"
  - indepv4/k21 "…scope:district:2723010100 이라고 나와 있는데 이게 어느 동이야?"
- 결과: Full과 P0은 5/5(P0 n40은 4/5) 정답이고, P0.3는 0/5다.
- P0.3 첫 응답은 scope concept 하나만 두고 값 없는 답 place concept를 빼서 `NO_MEASURE`가 된다. 이 패턴이 census F_place_answer_missing(6 → 18)과 G 증가에 섞여 있다.
- rule 11 A의 예시가 모두 값이 있는 place라서 생긴 부작용일 수 있다. 사후 가설이며 이번에는 고치지 않는다(사용자 지시 5절).

## 10. 문항별 paired 분석

회차별 2×2(Full vs P0.3, 5회 합계 770관측):

| | P0.3 정답 | P0.3 오답 |
|---|---:|---:|
| Full 정답 | 456 | 97 |
| Full 오답 | 96 | 121 |

- greedy 2×2: 둘 다 정답 98, Full만 22, P0.3만 16, 둘 다 오답 18.
- 참고 비교(5회 합계):
  - Full vs P0: 둘 다 정답 456, Full만 97, P0만 93, 둘 다 오답 124.
  - P0 vs P0.3: 둘 다 정답 449, P0만 100, P0.3만 103, 둘 다 오답 118.
- 문항별 k_P0.3 − k_Full 분포: −5: 2, −3: 7, −2: 9, −1: 20, 0: 76, +1: 21, +2: 13, +3: 4, +4: 1, +5: 1.

일관된 변화(|k차| ≥ 4, k는 5회 중 정답 수):

| 구분 | 문항 | k Full / P0 / P0.3 | 내용 |
|---|---|---|---|
| P0.3가 Full보다 일관되게 좋아짐 | indepv3/m12 | 0/4/5 | 승차·하차 모두 중구 안인 실차 수 |
| | indepv3/m32 | 0/3/4 | 법인택시 공차율 중간값 |
| P0.3가 Full보다 일관되게 나빠짐 | indepv2/n40 | 5/4/0 | scope id 역조회(J) |
| | indepv4/k21 | 5/5/0 | scope id 역조회(J) |
| P0보다 P0.3에서 회복 | contrast/c05c | 3/1/5 | 주말 대구 통행량 최소 시군구 |
| P0보다 P0.3에서 새로 나빠짐 | indepv2/n08 | 4/5/1 | 달서구행·광안동 승차 실차 수 |
| | indepv2/n09 | 3/5/1 | 수성구 안 읍면동 노선(dt) |
| | indepv2/n40 | 5/4/0 | (J) |
| | indepv4/k21 | 5/5/0 | (J) |
| | indepv3/m29 | 0/4/0 | 광안리 최고 속도 |

dt 부분집합의 문항별 k(Full/P0/P0.3):

| 문항 | k | 문항 | k |
|---|---|---|---|
| g12 | 2/3/2 | c01a | 4/4/2 |
| c04b | 5/5/5 | n06 | 2/1/3 |
| n34 | 1/2/2 | n35 | 0/0/0 |
| m03 | 1/2/0 | m04 | 0/0/0 |
| m05 | 3/2/1 | m09 | 3/4/5 |
| k26 | 3/1/2 | k27 | 2/0/1 |
| k28 | 0/1/0 | c01b | 5/3/5 |
| c04a | 3/2/2 | n05 | 3/1/0 |
| n09 | 3/5/1 | m02 | 3/1/2 |
| k33 | 1/2/2 | k34 | 0/0/0 |

거부 판단이 바뀐 문항, 새로 structural failure가 생긴 문항 목록은 `analysis.json`의 `pairs`에 있다. 전체 문항별 k와 회차별 결과는 `paired_items.csv`에 있다.

## 11. 출력 길이와 실행 비용

| 지표(sampling 회차 평균) | Full | P0 | P0.3 | P0.3 / Full |
|---|---:|---:|---:|---:|
| 최종 JSON token 평균(Qwen3 tokenizer) | 119.3 | 66.2 | 62.4 | −47.7% |
| 문항 eval_count 중앙값 | 748.3 | 658.8 | 532.4 | −28.9% |
| thinking 길이 중앙값(문자) | 2195 | 2229 | 1759 | −19.9% |
| 문항 wall-clock 중앙값(s) | 7.66 | 7.06 | 6.61 | −13.7% |
| cell 전체 wall-clock(s) | 1409 | 1284 | 1191 | −15.5% |
| repair 호출(건/회) | 38.0 | 29.2 | 38.6 | +0.6 |
| timeout / retry | 0 / 0 | 0 / 0 | 0 / 0 | |

- token 감소는 유지됐다. P0.3는 P0보다도 JSON이 조금 짧다.
- thinking 길이가 P0(2229)와 달리 P0.3(1759)에서 20% 줄었다. rule 11이 추론을 줄이는 쪽으로 작용했는지는 이 자료만으로는 알 수 없다.
- 정확도 gate를 token 감소와 맞바꿔 판정하지 않았다.

## 12. 해석상의 한계

- **표본 크기:**
  - 154문항 × 5회로 문항 단위 CI가 ±4.5%p 안팎이다. −1%p 비열등을 보일 검정력이 없다. "Full과 같다"가 아니라 "이 크기의 차이는 가려낼 수 없다"로 읽어야 한다.
  - dt 20문항과 refusal 10문항은 더 작다. 다만 dt 누락의 P0 대비 증가(+17%p, CI +6 ~ +29)는 CI가 0을 넘는다.
- **사후 해석:** dt 세부 패턴(사건 표현 안의 끝점, od_role 대체), J(scope 역조회)는 결과를 본 뒤 정한 것이다. 같은 set으로 확인할 수 없다.
- **버전:** Ollama가 0.40.3이다. ab_p0과 ab_valid98(0.40.1)의 Full 수치와 arm 밖에서 비교하면 버전 차이가 섞인다.
- **P0.2 미측정:** P0.2는 sel154에서 재지 않았다. "P0.3가 P0.2보다 나은가"는 이 run으로 답하지 않는다.
- **관측 지표의 의미:** week/month 첫 응답 오류는 repair로 회복돼 최종 정답률에는 영향이 없었다. H5 불통과는 사전 정의(첫 응답 관측 수)에 따른 것이다.
- **단일 사용:** sel154는 이제 결과를 본 set이다. 이후 P0.x 설계 근거로 쓰면 오염된다.

## 13. 다음 단계

사전 계획 9절의 B 분기다(전체 성능은 점 추정상 통과, dimension_target 문제는 남음). prompt는 더 고치지 않고 다음 순서로 분해할 것을 제안한다. 이번 단계에서는 실행하지 않는다.

1. **instruction following과 semantic ambiguity 분리:**
   - dt 누락이 몰린 문항(n35, k28, n05, k34, m03, m04)의 gold를 다시 검토해 질문 문장이 그룹 기준 끝점을 실제로 하나로 정하는지 본다.
   - Full도 같은 문항(n35 0/5, k34 0/5, m04 0/5)에서 실패한다. 일부는 prompt와 무관한 모델 해석 문제이거나 gold 모호성일 수 있다.
   - 이 검토는 사람이 확인해야 하며, annotation 추천을 승인으로 보지 않는다.
2. **sampling instability:** 문항별 k가 1–4인 문항의 비율과 회차별 분산(P0.3 회차 범위 66.9–76.0%, Full 70.1–73.4%)을 비교한다. P0.3의 분산이 더 큰지 본다. 기존 raw만 쓰고 모델 호출은 하지 않는다.
3. **rule 11의 역효과 가설(사후):**
   - 가설 1: "승차 지역별" 같은 표면 예시가 dimension_target의 trigger를 좁혔다.
   - 가설 2: 모든 place 예시에 값이 있어 값 없는 답 place 생략(J)을 유도했다.
   - 두 가설 모두 기존 raw의 thinking 텍스트에서 rule 11 언급과 해당 판단을 세는 방식으로 먼저 확인할 수 있다. 새 측정이 필요하면 sel154가 아닌 새 holdout을 정한 뒤에 한다.
4. **하지 않는 것:** P0.4 작성, P0.3 rule 추가, 예시 추가, HF 재현, P0.3 candidate 동결.

P0와 비교하면 P0.3는 structural error, B boundary, no_grounding을 분명히 줄였다(B 67 → 19, structural 15.2 → 9.0). 이 점에서 "목적지 명시"가 첫 응답 계약 준수에는 도움이 됐을 수 있다. 그러나 사전에 목표로 한 dimension_target 누락에는 도움이 되지 않았고, 새 오류 유형(J)이 생겼다.
