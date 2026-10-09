# selection_v1 하락 분석(작업 지시 6, 2026-10-09)

기록만 썼고 모델 호출은 하지 않았다. selection_v1의 gold와 셋 구성은 고치지 않았다. 업체 100과 aux_test_v1은 쓰지 않았다.

- 스크립트: `analysis.py`(공통 로더 `records.py`). 결과: `analysis.json`.
- 대상 기록(HF, 같은 `eval_set.py`·`eval_valid98.py` 조건):
  - selection_v1: base(`pilot_prep_005/sets/runs/selection_base.json`, 82)와 pilot_002 SFT 190·380·570·758, DPO 72·144·216·288(`pilot_002/selection/runs/`).
  - valid98: base(`pilot_prep_003/valid100/runs/base.json`의 98문항, 55), pilot_001 SFT 124·DPO 212, pilot_002 SFT 380·DPO 144.
- 오류 유형은 grounding_ok가 X인 문항마다 하나만 붙였다. 아래 순서에서 먼저 맞는 것을 쓴다.
  1. 출력 없음(생성 상한) / grounding 없음(코드)
  2. 호출 같음·grounding만 다름: 업체식 채점 `match`. 컴파일된 호출이 gold와 같다.
  3. 장소 표기(옛 표기 ↔ both)
  4. 측정값
  5. 질문에 없는 집계 추가: gold에는 집계가 없는데 모델이 넣음.
  6. 장소·역할
  7. 상태 조건
  8. dimension_target
  9. 집계 다름
  10. 기타
- 이 문서의 결론은 진단이다. 판정 규칙은 없다.

## 1. 결론

| 질문 | 결론 | 근거(절) |
|---|---|---|
| 라벨 표기 차이가 selection_v1 하락의 주원인인가 | **아니다(확인됨)**. 최종(DPO 144)에서 base는 맞고 최종은 틀린 9문항 중 표기 때문은 1문항(g12)이다. 옛 표기 문항(n10, k32)은 base도 X다 | 2 |
| 하락은 어디서 오나 | **장소·역할 오류 증가(확인됨)**: base 1 → checkpoint 4–6. 내용은 다음 셋이다 | 3 |
| | ① 출발·도착이 없는 측정값(통행량·rpm·속도)에 `od_role both`를 붙여 NO_OPERATOR로 멈춤 | |
| | ② 도착을 출발로 바꿈(c03c, g11) | |
| | ③ region을 빼거나 나눔(n02, m12) | |
| | **SFT 단계의 "질문에 없는 집계 추가"(가능성 있음)**: base 1 → SFT 3–4. DPO 144에서 2로 줄었다 | 3 |
| 학습 데이터와 관련이 있나 | **가능성 있음**. 학습의 `od_role both`는 모두 trip_count 정답이다(SFT 68 레코드/19질문). 그런데 selection_v1 gold에는 both가 0개다. 학습에는 active_taxi_count, 장소 MEASURE, passage_count + 실차·대기 상태 정답이 0개다 | 4 |
| thinking 길이·생성 상한·루프 | **하락을 설명하지 못한다(확인됨)**. 첫 계획 thinking 중앙값은 2.3–2.6천 자로 base(2.4천)와 비슷하다. 생성 상한 문항은 checkpoint당 0–5개, 그중 base에서 O였다가 잃은 문항은 0–2개다 | 5 |
| selection_v1은 내렸는데 valid98은 오른 이유 | **대부분 설명된다(확인됨).** valid98 base는 gold에 없는 `aggregation: sum`을 15문항에 붙였다(호출은 대부분 gold와 같음). 학습 모델은 이것을 5문항으로 줄였다. selection_v1 base는 같은 경우가 3문항뿐이라 오를 여지가 없었다 | 6 |

- 최종(DPO 144)의 selection_v1 차이는 base 82 → 80이다(잃음 9, 얻음 7). SFT checkpoint는 73–75로 더 낮았다.
- 셀마다 한 번 측정한 결과이므로 2–3문항 차이는 해석하지 않는다.

## 2. 라벨 표기 가설

**selection_v1 gold 중 지금 계약과 다른 표기**(gold grounding 기준)
- 같은 장소의 출발·도착을 장소 두 개(pickup·dropoff)로 적음: **3문항**(indepv2/n10, indepv3/m12, indepv4/k32). 지금 계약은 한 장소 `od_role both`다.
- vicinity: 1문항(indepv4/k03). gold는 factors에 있어 지금 계약과 같다.
- 날짜 형식: grounding 비교에서 `factor:date` 차이는 base와 모든 checkpoint에서 0이다. 날짜 형식은 원인이 아니다.
- 생략 가능한 기본값: gold가 수량 측정값(trip_count·passage_count)에 sum을 적은 문항은 0이다. 학습 모델이 sum을 붙이는 것은 아래 "호출 같음"에 들어간다.

**옛 표기 문항의 결과**
- n10: base와 모든 checkpoint가 `부산 both`로 적어 X다. 호출은 모두 gold와 같다(`match`). base도 X이므로 하락에 기여하지 않는다.
- k32: base는 `aggregation sum` 추가로 X였다. checkpoint는 모두 `수영구 both`로 X이고, 호출은 gold와 같다. base도 X다.
- m12: base와 SFT 190–570은 옛 표기 그대로 O다. SFT 758과 DPO 전부는 `대구 중구`를 장소 이름으로 붙여 NOT_FOUND로 멈췄다. 이것은 표기가 아니라 장소 이름 오류다.

**호출(컴파일 결과)은 gold와 같은데 grounding_ok만 X**

| 셀 | 문항 수 | base는 O인데 이 경우로 X |
|---|---:|---:|
| base | 4(c03c, n02, n10, k32) | – |
| SFT 190 | 5 | 2 |
| SFT 380 | 6 | 4(c01a, n34, m03, k08: 모두 `aggregation sum` 추가) |
| SFT 570 | 6 | 3 |
| SFT 758 | 6 | 3 |
| DPO 72 | 6 | 2 |
| **DPO 144** | **3**(n10, k32, g12) | **1**(g12: `aggregation sum` 추가) |
| DPO 216 | 5 | 1 |
| DPO 288 | 3 | 0 |

- 차이의 내용은 두 가지다. 하나는 수량 측정값에 `aggregation: sum`을 붙인 것이다(Tool 기본값이 합이라 호출은 같다). 다른 하나는 옛 표기 ↔ both다.
- sum을 붙인 문항의 질문에는 "총·합계" 같은 표현이 없다. selection_v1 base 3문항, DPO 144 2문항 모두 그렇다.
  - prompt는 "질문에 집계 표현이 없으면 넣지 않는다"고 한다. 그래서 학습 모델의 출력이 계약상 맞는 표기는 아니다. 실행 결과는 같다.

## 3. 오류 유형 증감

**원천 셋별 grounding_ok**

| 셀 | 전체 | old44 (29) | contrast (14) | indepv2 (18) | indepv3 (21) | indepv4 (18) |
|---|---:|---:|---:|---:|---:|---:|
| base | 82 | 26 | 10 | 12 | 18 | 16 |
| SFT 190 | 74 | 25 | 11 | 9 | 18 | 11 |
| SFT 380 | 75 | 25 | 9 | 11 | 18 | 12 |
| SFT 570 | 75 | 26 | 10 | 11 | 16 | 12 |
| SFT 758 | 73 | 26 | 8 | 10 | 17 | 12 |
| DPO 72 | 72 | 25 | 9 | 10 | 14 | 14 |
| DPO 144 | 80 | 24 | 12 | 12 | 16 | 16 |
| DPO 216 | 78 | 25 | 14 | 10 | 15 | 14 |
| DPO 288 | 78 | 26 | 13 | 12 | 13 | 14 |

- SFT는 indepv2(−1 ~ −3)와 indepv4(−4 ~ −5)에서 많이 잃었다. DPO 144–288은 contrast에서 얻고(+2 ~ +4), DPO 전부가 indepv3에서 잃었다(−2 ~ −5).

**오류 유형(grounding_ok X 문항)**

| 유형 | base | S190 | S380 | S570 | S758 | D72 | D144 | D216 | D288 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 장소·역할 | 1 | 3 | 4 | 5 | 4 | 5 | 6 | 6 | 5 |
| 호출 같음·grounding만 다름 | 4 | 5 | 6 | 6 | 6 | 6 | 3 | 5 | 3 |
| 질문에 없는 집계 추가 | 1 | 3 | 4 | 4 | 3 | 5 | 2 | 1 | 0 |
| 집계 다름 | 3 | 3 | 1 | 1 | 2 | 2 | 2 | 4 | 3 |
| 측정값 | 3 | 2 | 2 | 1 | 4 | 2 | 2 | 2 | 3 |
| dimension_target | 3 | 4 | 1 | 3 | 1 | 3 | 1 | 2 | 2 |
| 출력 없음(생성 상한) | 0 | 1 | 1 | 0 | 2 | 2 | 2 | 0 | 3 |
| grounding 없음(그 밖의 코드) | 3 | 2 | 4 | 3 | 4 | 1 | 0 | 0 | 3 |
| 기타(limit·order, vicinity 등) | 0 | 2 | 1 | 2 | 1 | 2 | 1 | 2 | 0 |
| 상태 조건 | 0 | 1 | 1 | 0 | 0 | 0 | 1 | 0 | 0 |

**장소·역할 오류의 내용**(checkpoint 전체에서 모은 것)
- 출발·도착이 없는 측정값에 `od_role both` 추가. 대부분 NO_OPERATOR로 멈춘다.
  - 대상: passage_count n18·m27·c05c, rpm k06·m39, speed k05.
  - 셀별 수: base 2(g04, n18), SFT 1–3, DPO 2–4.
  - DPO 144: g02(passage_count, 답함), k06(rpm, 멈춤).
- 도착 ↔ 출발 바꿈: c03c(SFT 380·758, DPO 72·144·288), g11(SFT 380·570, DPO 144). base는 0이다.
- region 누락·분리: n02(`중구` region 빠짐, SFT 570·DPO 144), m12(`대구 중구`, SFT 758·DPO 전부), k28(SFT 190).
- 결정 62의 관찰(Ollama-최종의 역할 오류 041·093)과 같은 계열이다. HF 경로의 selection_v1에서도 나타난다.

## 4. 학습 데이터 분포와 대조

pilot_002 실제 학습 파일(`training/generated/thinking_pilot002_t2pc/`)을 썼다. SFT 379 레코드(107질문), DPO chosen 288(45질문).
gold 칸은 문항 수, 학습 칸은 레코드 수다.

| 특징 | selection_v1 | valid98 | SFT | DPO |
|---|---:|---:|---:|---:|
| measure trip_count | 28 | 52 | 162 | 137 |
| measure passage_count | 12 | 8 | 22 | 25 |
| passage_count + taxi_status occupied | 3 | 1 | **0** | **0** |
| passage_count + taxi_status stationary | 1 | 1 | 0 | 0 |
| passage_count + taxi_status vacant | 3 | 2 | 2 | 4 |
| measure active_taxi_count | 6 | 1 | **0** | **0** |
| measure place(장소를 묻는 질문) | 4 | 1 | **0** | **0** |
| measure rpm / speed | 4 / 3 | 1 / 3 | 44 / 40 | 13 / 19 |
| od_role both | **0** | **0** | 68(모두 trip_count) | 40(모두 trip_count) |
| od_role pickup/dropoff | 27 | 44 | 65 | 60 |
| 같은 장소 pickup+dropoff(옛 표기) | 3 | 6 | 0 | 0 |
| dimension_target | 13 | 37 | 99 | 82 |
| aggregation | 53 | 24 | 158 | 109 |
| vicinity | 1 | 3 | 84 | 46 |

- 학습에는 `od_role both`가 많다(trip_count만). selection_v1·valid98 gold에는 0이다. checkpoint가 both를 비 trip 측정값에 붙이는 것(3절)과 방향이 같다.
- selection_v1에 있고 학습에 없는 유형: active_taxi_count, 장소 MEASURE, passage_count + 실차·대기 상태.
  - 실차 통행량은 `PASSAGE_STATUS.md`에서 따로 본다.
- selection_v1은 valid98보다 trip_count·dimension_target 비중이 낮다(28 대 52, 13 대 37). 학습 데이터는 trip_count·dimension_target 비중이 높다.

## 5. thinking 길이·생성 상한·루프

| 셀 | 첫 계획 thinking 글자(중앙/p90/최대) | 생성 token 중앙 | 상한 호출(문항) | 루프 호출(결정 40-D) | 문항 시간 중앙(초) |
|---|---|---:|---|---:|---:|
| base | 2413 / 4437 / 9999 | 763 | 0 | 0 | 22.4 |
| SFT 190 | 2630 / 4817 / 35466 | 791 | 4(c01a, n40) | 4 | 30.0 |
| SFT 380 | 2499 / 4812 / 32554 | 791 | 2(c05c) | 2 | 28.1 |
| SFT 570 | 2322 / 5548 / 13368 | 746 | 0 | 0 | 26.7 |
| SFT 758 | 2410 / 4777 / 36318 | 783 | 4(n10, n18) | 4 | 27.8 |
| DPO 72 | 2648 / 5589 / 34128 | 820 | 4(m05, g04) | 4 | 28.0 |
| DPO 144 | 2335 / 4734 / 34938 | 761 | 4(n18, m03) | 4 | 25.5 |
| DPO 216 | 2319 / 4832 / 10532 | 748 | 2(g24) | 2 | 27.1 |
| DPO 288 | 2554 / 5611 / 33737 | 838 | 10(c07b, m04, m24, m27, g04) | 10 | 27.5 |

- 생성 상한에 걸린 호출은 모두 루프 판정에도 걸렸다.
- base 대비 하락 폭(SFT 7–9, DPO 144 2)에 비해 상한 문항은 0–5개다. 그중 base에서 O였다가 잃은 문항은 checkpoint당 0–2개다(SFT 190 c01a·n40, SFT 380 c05c, DPO 144 m03, DPO 216 g24, DPO 288 m27). 하락의 일부만 설명한다.
- 중앙 thinking 길이는 base와 비슷하다. 긴 꼬리(최대 3만 자대)는 학습 모델에만 있다.

## 6. selection_v1은 내리고 valid98은 오른 이유

| | selection_v1 | valid98 |
|---|---|---|
| base → DPO 144 | 82 → 80(잃음 9, 얻음 7) | 55 → 65(잃음 8, 얻음 18) |
| base의 "gold에 없는 aggregation sum 추가" | 3문항 | **15문항** |
| DPO 144의 같은 경우 | 2문항 | 5문항 |
| DPO 144가 얻은 문항의 base 오류 유형 | dimension_target 3, grounding 없음 2, 집계 1, 집계 추가 1 | 호출 같음 7, 집계 추가 4, 장소·역할 2, 그 밖 5 |

- valid98 base는 수량 측정값에 질문에 없는 `aggregation: sum`을 자주 붙였다.
  - 15문항 중 14문항은 질문에 "총·합계" 표현이 없다. 9문항은 호출이 gold와 같다.
  - 학습 모델은 이것을 덜 붙인다. 학습 데이터의 수량 측정값 + 집계는 SFT 11/379다.
- 이것만으로 valid98 순증(+10)의 대부분이 설명된다. valid98 얻음 18 중 11이 이 두 유형(호출 같음 7, 집계 추가 4)이다.
- selection_v1 base는 이런 오류가 적어서(3) 같은 방식으로 오를 여지가 없었다. 대신 3절의 장소·역할 오류가 늘어 상쇄됐다.
- 참고: valid98은 학습 데이터와 template 4문항·family 6문항이 겹친다(결정 54). selection_v1은 모든 키에서 0이다. 이 겹침이 valid98 상승에 얼마나 기여했는지는 따로 재지 않았다(미확인).

## 7. 사람 검토 항목(표기 차이로 판정된 문항)

selection_v1의 gold와 셋 구성은 고치지 않았다. 아래는 표기 차이 때문에 grounding_ok가 X가 된 문항이다. 판정 방식(표기 차이를 X로 볼지)은 사람이 정한다.

| 문항 | gold 표기 | 모델 출력 | 호출 | X가 된 셀 |
|---|---|---|---|---|
| indepv2/n10 | 같은 장소 `부산` pickup·dropoff 두 개(옛 표기) | `부산` 한 개 `od_role both`(지금 계약) | gold와 같음 | base 포함 모든 셀 |
| indepv4/k32 | 같은 장소 `수영구` pickup·dropoff 두 개(옛 표기) | `수영구` 한 개 both | gold와 같음 | 모든 SFT·DPO(base는 sum 추가로 X) |
| indepv3/m12 | 같은 장소 `중구` pickup·dropoff 두 개(옛 표기) | SFT 758·DPO: `대구 중구`/`중구` 두 개(장소 이름 오류, NOT_FOUND) | 다름 | 표기가 아니라 이름 오류. 참고로 둠 |
| contrast/c03c, indepv2/n02, contrast/c01a, contrast/c03a, contrast/c05c, contrast/c09a, indepv2/n08, indepv2/n34, indepv3/m03, indepv3/m04, indepv4/k03, indepv4/k08, indepv4/k26, old44/g11, old44/g12 | 집계 없음 | 수량 측정값에 `aggregation: sum` 추가(셀마다 다름) | gold와 같음(`match`) | 셀별로 1–6문항(2절 표) |

- sum 추가는 prompt 계약상 틀린 출력이다(질문에 집계 표현 없음). 호출은 같다. grounding_ok에서 X로 둘지는 사람이 정한다.
- valid98에서 gold에 집계가 없는데 질문에 "총·합계" 표현이 있는 문항: heldout_v9/h06, heldout_v8/t02. gold가 sum을 생략한 표기인지 사람이 볼 만하다.
