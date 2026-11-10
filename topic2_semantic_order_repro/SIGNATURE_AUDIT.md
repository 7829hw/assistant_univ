# SIGNATURE_AUDIT — 스케줄러 서명(Train 전용) 점검 (Stage 1)

스크립트 `analysis/stage1_signature_audit.py`, 표 `tables/stage1_signature_audit.json`. 서명은 승인 train 코퍼스(`approved_train_v6`)의 `view`와 실행 정보(없으면 train 증거 기반 metric→tool 사상)에서 만든다.

- 1,984 레코드 / 494 질문 → coarse(tool|metric) 11개, fine 249개. fine 그룹 크기 중앙값 6, **95개가 5레코드 이하**(최대 124).
- coarse 구성: trip_count 655, passage_count 359, billing revenue 199 / active_taxi_count 156 / active_taxi_ratio 153 / operating_days 147, scope_name 124, refusal 79, rpm 55, `unknown|vacant_ratio` 42, `unknown|speed` 15.
- **`fare`, `get_trip_metrics` 그룹은 학습 서명에 존재하지 않는다**(`contains_fare_or_trip_metrics: []`). 학습 레코드에서 `get_trip_metrics`는 0, 요금 문항 직접 레코드도 0에 가깝다(요금이 언급되는 학습 문항은 `b012-043` 1개와 거절 문항 `b011-054`). 승인된 요금 44문항은 V4에 0개(정책 결정 대기, 사용 안 함). 즉 스케줄러는 T1 계열을 **서명으로 구분할 수 없다**: 가장 가까운 것은 billing(`수입/매출`) 계열이며 "billing contrast teacher 298개"가 그 이웃이다.
- `unknown` 처리: tool=unknown 57건(vacant_ratio/speed, 1:1 사상 불가), metric=`?` 79건(거절). 필드별 `none`: agg 1,269, od 1,250, region 247, time 219. subtype fallback은 plan에서 제거했고 `subtype:*` coarse 그룹은 0개(단위 테스트 통과). 승인 실행 정보가 있는 레코드 1,282, 없어 `view` fallback인 레코드 702.
- 동등성 점검: 평가 T1 문항("X 소속 택시의 평균 요금")과 학습의 "X 소속 택시의 평균 수입"(billing, LOCATION 포함 148개 질문 전부 LOCATION 개념 보유)은 **문장 구조가 같고 측정만 다르다**. 서명은 이 둘을 다른 tool(billing vs 없음)로 취급해 "서로 다른 그룹"으로 균형을 맞춘다. 실행 의미 동등성(지역 개념 필수)은 서명에 반영되지 않는다 → M3의 조건부 근거(아래 CAUSAL_HYPOTHESES에서 평가).
- 한계: T1 평가 문항의 서명은 평가 gold에서 만든 진단용이며 스케줄러 입력이 아니다. 서명이 틀렸다는 것과 순서가 T1 하락의 원인이라는 것은 별개의 주장이다.
