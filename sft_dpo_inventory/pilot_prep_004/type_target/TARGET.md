# batch005 유형 분포 목표 (결정 40-C, 작업 지시 3)

작성: 2026-10-07. 스크립트: `type_target.py`. 결과: `type_target.json`. 모델을 부르지 않았다.
보호 개발 셋은 집계 통계(칸별 건수)만 썼다. 문항 내용과 id는 쓰지 않았다.

## 1. 유형 정의

질문 하나를 1로 센다. 정답 grounding의 factors로 정한다.

- **집계:** `bucket`·`aggregation`·`rollup` 중 하나라도 있으면 "집계 있음"이다. pilot_001 분석 3c의 `factor:aggregation_spec`와 같은 정의다.
- **`dimension`:** 값이 있으면 "있음"이다. 단위(emd, sigungu, sido, h3, dayofweek)는 칸 안 세부로 둔다.
- **`dimension_target`:** 값(pickup, dropoff, both)이 있으면 "있음"이다.
- **칸:** 집계 유무 × dimension 유무 × dimension_target 유무. 개발 셋에 나오는 칸은 5개다.

## 2. 개발 셋과 지금 학습 데이터

**개발 셋**

- 범위: `policy_scale.VENDOR_FORMAT_SETS` 전체에서 업체 100(결정 36)과 사본 cli_check_v14를 뺐다.
- 셋끼리 중복된 질문, 정책·모호 라벨, 정답 grounding이 없는 문항을 뺀 454질문이다.

**학습 데이터**

- pilot_001 SFT의 34질문과 teacher 17질문(결정 40-A)을 합친 51질문이다. 두 묶음은 겹치지 않는다.
- 유형은 reviewed gold(`reviewed_gold_v004_t2pc`) 기준으로 정했다.

| 칸 | 개발 셋 454 | 학습 51질문 | 학습 레코드(참고) r1 124 | 학습 레코드(참고) r1+teacher 245 |
|---|---:|---:|---:|---:|
| 집계 없음, dim 없음, dt 없음 | 0.293 | 0.039 | 0.032 | 0.016 |
| 집계 없음, dim 있음, dt 없음 | 0.082 | 0.078 | 0.081 | 0.061 |
| 집계 없음, dim 있음, dt 있음 | 0.280 | 0.314 | 0.089 | 0.327 |
| 집계 있음, dim 없음, dt 없음 | 0.284 | 0.490 | 0.766 | 0.514 |
| 집계 있음, dim 있음, dt 없음 | 0.062 | 0.078 | 0.032 | 0.082 |
| 총변동거리(TV, 개발 셋 대비) | – | **0.257** | 0.482 | 0.297 |

- 레코드 단위 값은 질문별 trace 수에 따라 달라진다.
  - r1+teacher 열은 teacher 정답 표본 수(`correct_samples_of_8`)를 필터 전 그대로 더한 값이다.
  - 실제 pilot_002 데이터의 레코드 비율은 D(루프 제외)와 계약 필터를 적용하고, batch005 trace를 수집한 뒤 다시 센다.
- 질문 단위로 가장 큰 차이는 "집계 없음, dim 없음, dt 없음" 칸이다(개발 셋 29%, 학습 4%).
  - 예: 집계·묶음 없이 값 하나를 묻는 질문.
  - pilot_001 분석 3c에서 본 dimension_target의 부족(레코드 9% 대 valid98 38%)은 질문 단위에서는 거의 없다(31% 대 28%).
  - 그 차이는 dimension_target 질문이 정답 표본을 적게 얻은 데서 왔다. r1 레코드 단위에서는 dt 있음 칸이 8.9%다.
  - teacher 17질문을 넣으면 레코드 단위로도 32.7%가 된다.

## 3. 배분(새 질문 60건)

방법:

- 기존 학습 질문은 빼지 않는다.
- 칸마다 부족분 `max(0, p_dev × (51+60) − n_train)`을 구하고, 그 비율로 60건을 나눈다(최대 나머지 방식).
- 칸 안의 세부(단위, target 값, od_role)는 개발 셋의 같은 칸 안 비율로 나눈다.

| 칸 | 배분 | 칸 안 세부(배분) |
|---|---:|---|
| 집계 없음, dim 없음, dt 없음 | **30** | od_role 없음 12, pickup+dropoff 9, pickup 6, dropoff 3 |
| 집계 없음, dim 있음, dt 있음 | **15** | 아래 표 |
| 집계 있음, dim 없음, dt 없음 | 7 | 장소 있음(od_role 없음) 6, 장소 없음 1 |
| 집계 없음, dim 있음, dt 없음 | 5 | sigungu 2, emd 1, h3 1, sido(장소 없음) 1 |
| 집계 있음, dim 있음, dt 없음 | 3 | sido(장소 없음) 2, dayofweek(장소 없음) 1 |

"집계 없음, dim 있음, dt 있음" 칸 15건의 세부:

| dimension | dimension_target | 장소 od_role | 건수 |
|---|---|---|---:|
| emd | dropoff | pickup | 2 |
| emd | pickup | dropoff | 2 |
| emd | both | pickup+dropoff | 1 |
| emd | both | pickup | 1 |
| emd | dropoff | pickup+dropoff | 1 |
| emd | dropoff | dropoff | 1 |
| emd | pickup | pickup | 1 |
| emd | pickup | pickup+dropoff | 1 |
| sigungu | dropoff | pickup | 1 |
| sigungu | dropoff | pickup+dropoff | 1 |
| sigungu | pickup | dropoff | 1 |
| sigungu | pickup | 장소 없음 | 1 |
| sigungu | both | 장소 없음 | 1 |

| | 배분 전(51) | 배분 뒤(111) | 개발 셋 |
|---|---:|---:|---:|
| 집계 없음 | 0.431 | 0.649 | 0.654 |
| dimension 있음 | 0.471 | 0.423 | 0.423 |
| dimension_target 있음 | 0.314 | 0.279 | 0.280 |
| 칸 분포 TV | 0.257 | **0.006** | – |

새 질문 수에 따른 TV(같은 방식):

| 새 질문 수 | 0 | 20 | 40 | 60 | 80 | 100 | 150 |
|---|---:|---:|---:|---:|---:|---:|---:|
| TV | 0.257 | 0.071 | 0.010 | 0.006 | 0.005 | 0.005 | 0.004 |

- 질문 단위로는 약 40건이면 차이가 거의 없어진다. 60건은 승인에서 빠질 후보와 레코드 단위 편차를 감안한 여유다.
- 측정값은 배분 기준에 넣지 않았다.
  - 개발 셋의 측정값 비율(참고): trip_count 45%, passage_count 14%, revenue 12%.
  - 작업 지시 4의 겹침 검사(확장 family 포함)가 측정값 선택을 제약한다. 결과는 batch005 보고에 적는다.
- 정지 target(기대 결과가 답이 아닌 문항)은 개발 셋 7.5%, 학습 5.9%다. 이번 배분에는 따로 칸을 두지 않았다.
