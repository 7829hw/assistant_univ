# Partial-P0.1 측정 계획 — 확정 2026-10-10(사용자, 결정 58)

ab_p0(`REPORT.md`)에서 Partial-P0는 정답률·실행 완료율·JSON 토큰 gate를 통과했지만 structural error(4.2 → 6.4)와
grounding failure(4.8 → 6.8) gate가 불통과였다. 원인은 concept/factor 경계 오류(subtype 자리에 pickup·emd 등,
place.attributes.dimension, MEASURE 누락)였다. P0.1은 이 경계를 output_format에 명시한다.

## 1. prompt

`evaluation/partial_grounding/prompts/partial_p0_1.yaml`, 결합 system prompt hash `09de2009…`.
P0와 다른 곳은 `task`(끝에 다섯 항목)와 `output_format`(사용자 교체안)뿐이다. 재질의 요청문도 같다.

교체안에서 사용자 승인으로 네 곳을 고쳤다. 고정 parser/composer(mock Tool)로 예시를 돌려 본 결과, 예시 2·5는 지역이 없어
`MISSING_REQUIRED_INPUT`, 예시 3(fare + 도착 장소)은 그 조합의 operator가 없어 `UNUSED_CONCEPT`로 멈췄고, 교체안은
장소명이 답인 질문(예: 업체 082)의 규칙을 지웠다.

| 곳 | 교체안 | 측정본 |
|---|---|---|
| 예시 2 | 읍면동별 통행량 상위 3곳 | 부산의 읍면동별 통행량 상위 3곳(부산 place 추가) |
| 예시 3 | 동성로에 도착한 실차의 평균 요금(fare) | 동성로에 도착한 실차 구간 건수(trip_count) |
| 예시 5 | 통행량이 가장 많은 읍면동 | 대구에서 통행량이 가장 많은 읍면동(대구 place 추가) |
| 규칙 6 | — | 지역명 자체를 묻는 질문은 value 없는 place가 측정값이라는 한 줄 |

측정본의 예시 5개와 장소명 답 예는 모두 mock 실행에서 answered다. 실행 의미 코드 지문은 `ab88a19e`로 그대로다.

## 2. 셀

`run_p0_1.sh`: smoke(P0.1 greedy, 001–003, ab_p0와 같은 통과 조건) → P0.1 greedy → P0.1 sampling r1–r5(seed
20261010–20261014). 고정 조건·장비 절차·guard(77.6 tok/s)·중단 규칙은 `PLAN.md` 1·2절과 같다. Full arm은 ab_p0의
`runs/full_*`를 다시 쓴다(측정일만 다르다). P0 셀도 3-way 참고로 비교한다.

## 3. 분석과 판정

`analyze.py --arms full,p0_1 --out analysis_p0_1.json`과 `--arms p0,p0_1`(참고). 지표와 gate는 `PLAN.md` 3·4절과 같다.
추가로 ab_p0 3절의 세 오류 종류(INVALID_CONCEPT, UNKNOWN_ATTRIBUTE, NO_MEASURE)가 줄었는지, 082 같은 장소명 답 문항이
거부로 바뀌지 않았는지 따로 본다.
