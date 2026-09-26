# inner 미지정 사례 감사표 (자동 생성)

생성: `aggregation_label_audit.py`. 라벨: `evaluation/labels/aggregation_semantics_v2.yaml`.
기준선 = c547e5c, 현재 = 작업 트리. 재생(LLM 호출 없음), development census.

| run | 관측 | v2 기대 | 전: v1 결과 | 후: 결과(code) | 계획 일치 | 결과 일치 | 오류 단계 | 유형 | 수정 대상 |
|---|---|---|---|---|---|---|---|---|---|
| M0 | b21_p0 주 단위로 집계한 택시 수입의 평균은?<br>grounding `{"aggregation": "avg", "bucket": "week", "rollup": "avg"}` | needs_clarification {"bucket": "week", "inner": "unspecified", "final": "avg"} | CORRECT | unsupported (UNVERIFIED_TIMS_CONTRACT) | 아니오 | 아니오 | grounding | 3, 5, 4 | user_confirmation, evaluation_label |
| M0 | b21_p1 택시 수입을 주 단위로 집계했을 때 평균은?<br>grounding `{"aggregation": "avg", "bucket": "week"}` | needs_clarification {"bucket": "week", "inner": "unspecified", "final": "avg"} | CORRECT | unsupported (UNVERIFIED_TIMS_CONTRACT) | 아니오 | 아니오 | grounding | 3, 5, 4 | user_confirmation, evaluation_label |
| M0 | b21_p2 주 단위 택시 수입의 평균은?<br>grounding `{"bucket": "week", "aggregation": "avg"}` | needs_clarification {"bucket": "week", "inner": "unspecified", "final": "avg"} | CORRECT | unsupported (UNVERIFIED_TIMS_CONTRACT) | 아니오 | 아니오 | grounding | 3, 5, 4 | user_confirmation, evaluation_label |
| M0 | b21_p3 수입의 평균을 주 단위로 집계하면?<br>grounding `{"aggregation": "avg", "bucket": "week"}` | needs_clarification (계획 확정 불가) | CORRECT | unsupported (UNVERIFIED_TIMS_CONTRACT) | - | 아니오 | grounding | 3 | user_confirmation, evaluation_label |
| M0 | b21_p4 택시 수입의 주 단위 집계 평균은?<br>grounding `{"bucket": "week", "rollup": "avg"}` | needs_clarification {"bucket": "week", "inner": "unspecified", "final": "avg"} | CORRECT | needs_clarification (AMBIGUOUS_INNER_AGGREGATION) | 예 | 예 | none | 3, 5, 4 | user_confirmation, evaluation_label |
| M0 | b21_p5 주 단위로 집계하면 택시 수입의 평균은 얼마인가요?<br>grounding `{"bucket": "week", "aggregation": "avg"}` | needs_clarification {"bucket": "week", "inner": "unspecified", "final": "avg"} | SUPPORTED_REJECTION | failed (INVALID_FACTOR_COMBINATION) | 아니오 | 아니오 | grounding | 3, 5, 4 | user_confirmation, evaluation_label |
| M0 | b24_p0 월 단위로 집계한 개인택시 수입의 최대값은?<br>grounding `{"bucket": "month", "aggregation": "max", "taxi_type": "private"}` | needs_clarification {"bucket": "month", "inner": "unspecified", "final": "max"} | CORRECT | unsupported (UNRESOLVED_PERIOD) | 아니오 | 아니오 | grounding | 3, 5, 4 | user_confirmation, evaluation_label |
| M0 | b24_p1 개인택시 수입을 월 단위로 집계했을 때 최대값은?<br>grounding `{"bucket": "month", "aggregation": "max", "taxi_type": "private"}` | needs_clarification {"bucket": "month", "inner": "unspecified", "final": "max"} | SUPPORTED_REJECTION | failed (INVALID_FACTOR_COMBINATION) | 아니오 | 아니오 | grounding | 3, 5, 4 | user_confirmation, evaluation_label |
| M0 | b24_p2 월 단위 개인택시 수입 중 최대값은?<br>grounding `{"bucket": "month", "aggregation": "max", "taxi_type": "private"}` | needs_clarification {"bucket": "month", "inner": "unspecified", "final": "max"} | CORRECT | unsupported (UNRESOLVED_PERIOD) | 아니오 | 아니오 | grounding | 3, 5, 4 | user_confirmation, evaluation_label |
| M0 | b24_p3 수입의 최대값을 월 단위로 개인택시 기준 집계하면?<br>grounding `{"aggregation": "max", "bucket": "month", "taxi_type": "private"}` | needs_clarification (계획 확정 불가) | SILENT_WRONG_PLAN | unsupported (UNRESOLVED_PERIOD) | - | 아니오 | grounding | 3 | user_confirmation, evaluation_label |
| M0 | b24_p4 개인택시의 월 단위 수입 최대값은?<br>grounding `{"bucket": "month", "aggregation": "max", "taxi_type": "private"}` | needs_clarification {"bucket": "month", "inner": "unspecified", "final": "max"} | CORRECT | unsupported (UNRESOLVED_PERIOD) | 아니오 | 아니오 | grounding | 3, 5, 4 | user_confirmation, evaluation_label |
| M0 | b24_p5 월 단위로 집계하면 개인택시 수입의 최대값은 얼마인가요?<br>grounding `{"bucket": "month", "rollup": "max"}` | needs_clarification {"bucket": "month", "inner": "unspecified", "final": "max"} | SILENT_WRONG_PLAN | needs_clarification (AMBIGUOUS_INNER_AGGREGATION) | 예 | 예 | none | 3, 5, 4 | user_confirmation, evaluation_label |
| M0 | f01_p0 월 단위로 합산한 택시 수입의 평균은?<br>grounding `{"bucket": "month", "rollup": "avg"}` | unsupported {"bucket": "month", "inner": "sum", "final": "avg"} | SILENT_WRONG_PLAN | needs_clarification (AMBIGUOUS_INNER_AGGREGATION) | 아니오 | 아니오 | grounding | 1, 4 | grounding, execution |
| M0 | f01_p1 택시 수입을 월 단위로 합산했을 때 평균은?<br>grounding `{"bucket": "month", "rollup": "avg"}` | unsupported {"bucket": "month", "inner": "sum", "final": "avg"} | SILENT_WRONG_PLAN | needs_clarification (AMBIGUOUS_INNER_AGGREGATION) | 아니오 | 아니오 | grounding | 1, 4 | grounding, execution |
| M0 | f01_p2 월 단위로 합산한 수입들의 평균은 얼마인가요?<br>grounding `{"bucket": "month", "rollup": "avg"}` | unsupported {"bucket": "month", "inner": "sum", "final": "avg"} | SILENT_WRONG_PLAN | needs_clarification (AMBIGUOUS_INNER_AGGREGATION) | 아니오 | 아니오 | grounding | 1, 4 | grounding, execution |
| M0 | f01_p3 월 단위로 합산하면 택시 수입의 평균은 얼마인가요?<br>grounding `{"bucket": "month", "rollup": "avg"}` | unsupported {"bucket": "month", "inner": "sum", "final": "avg"} | SILENT_WRONG_PLAN | needs_clarification (AMBIGUOUS_INNER_AGGREGATION) | 아니오 | 아니오 | grounding | 1, 4 | grounding, execution |
| M0 | f02_p0 주 단위로 평균 낸 영업 시간의 최대값은?<br>grounding `{"bucket": "week", "aggregation": "avg", "rollup": "max"}` | unsupported {"bucket": "week", "inner": "avg", "final": "max"} | CORRECT | unsupported (UNVERIFIED_TIMS_CONTRACT) | 예 | 예 | execution_contract | 1, 4 | grounding, execution |
| M0 | f02_p1 영업 시간을 주 단위로 평균 냈을 때 최대값은?<br>grounding `{"bucket": "week", "rollup": "max"}` | unsupported {"bucket": "week", "inner": "avg", "final": "max"} | CORRECT | needs_clarification (AMBIGUOUS_INNER_AGGREGATION) | 아니오 | 아니오 | grounding | 1, 4 | grounding, execution |
| M0 | f02_p2 주 단위 평균 영업 시간 중 최대값은?<br>grounding `{"bucket": "week", "aggregation": "avg", "rollup": "max"}` | unsupported {"bucket": "week", "inner": "avg", "final": "max"} | CORRECT | unsupported (UNVERIFIED_TIMS_CONTRACT) | 예 | 예 | execution_contract | 1, 4 | grounding, execution |
| M0 | f02_p3 주 단위로 평균 내면 영업 시간의 최대값은 얼마인가요?<br>grounding `{"bucket": "week", "aggregation": "avg", "rollup": "max"}` | unsupported {"bucket": "week", "inner": "avg", "final": "max"} | CORRECT | unsupported (UNVERIFIED_TIMS_CONTRACT) | 예 | 예 | execution_contract | 1, 4 | grounding, execution |
| M0 | f03_p0 월 단위 영업 횟수의 합계는?<br>grounding `{"bucket": "month", "rollup": "sum"}` | unsupported {"bucket": "month", "inner": "sum", "final": "sum"} | CORRECT | needs_clarification (AMBIGUOUS_INNER_AGGREGATION) | 아니오 | 아니오 | grounding | 2, 4, 5 | grounding, evaluation_label, execution |
| M0 | f03_p1 영업 횟수를 월 단위로 집계했을 때 합계는?<br>grounding `{"bucket": "month", "rollup": "sum"}` | unsupported {"bucket": "month", "inner": "sum", "final": "sum"} | CORRECT | needs_clarification (AMBIGUOUS_INNER_AGGREGATION) | 아니오 | 아니오 | grounding | 2, 4, 5 | grounding, evaluation_label, execution |
| M0 | f03_p2 월 단위로 집계한 영업 횟수 합계는?<br>grounding `{"bucket": "month", "rollup": "sum"}` | unsupported {"bucket": "month", "inner": "sum", "final": "sum"} | CORRECT | needs_clarification (AMBIGUOUS_INNER_AGGREGATION) | 아니오 | 아니오 | grounding | 2, 4, 5 | grounding, evaluation_label, execution |
| M0 | f03_p3 월 단위로 집계하면 영업 횟수의 합계는 얼마인가요?<br>grounding `{"bucket": "month", "rollup": "sum"}` | unsupported {"bucket": "month", "inner": "sum", "final": "sum"} | CORRECT | needs_clarification (AMBIGUOUS_INNER_AGGREGATION) | 아니오 | 아니오 | grounding | 2, 4, 5 | grounding, evaluation_label, execution |
| M0 | f13_p0 주 단위로 집계한 법인택시 영업 횟수의 평균은?<br>grounding `{"bucket": "week", "aggregation": "avg"}` | needs_clarification {"bucket": "week", "inner": "unspecified", "final": "avg"} | SILENT_WRONG_PLAN | unsupported (UNVERIFIED_TIMS_CONTRACT) | 아니오 | 아니오 | grounding | 3, 5, 4 | user_confirmation, evaluation_label |
| M0 | f13_p1 법인택시 영업 횟수를 주 단위로 집계했을 때 평균은?<br>grounding `{"taxi_type": "corporate", "aggregation": "avg", "bucket": "week"}` | needs_clarification {"bucket": "week", "inner": "unspecified", "final": "avg"} | SUPPORTED_REJECTION | failed (INVALID_FACTOR_COMBINATION) | 아니오 | 아니오 | grounding | 3, 5, 4 | user_confirmation, evaluation_label |
| M0 | f13_p2 법인택시의 주 단위 영업 횟수 평균은?<br>grounding `{"taxi_type": "corporate", "bucket": "week", "aggregation": "avg"}` | needs_clarification {"bucket": "week", "inner": "unspecified", "final": "avg"} | CORRECT | unsupported (UNVERIFIED_TIMS_CONTRACT) | 아니오 | 아니오 | grounding | 3, 5, 4 | user_confirmation, evaluation_label |
| M0 | f13_p3 주 단위로 집계하면 법인택시 영업 횟수의 평균은 얼마인가요?<br>grounding `{"bucket": "week", "aggregation": "avg", "taxi_type": "corporate"}` | needs_clarification {"bucket": "week", "inner": "unspecified", "final": "avg"} | CORRECT | unsupported (UNVERIFIED_TIMS_CONTRACT) | 아니오 | 아니오 | grounding | 3, 5, 4 | user_confirmation, evaluation_label |
| M0 | h12_p0 주 단위로 집계한 개인택시 수입의 최소값은?<br>grounding `{"bucket": "week", "aggregation": "min", "taxi_type": "private"}` | needs_clarification {"bucket": "week", "inner": "unspecified", "final": "min"} | CORRECT | unsupported (UNRESOLVED_PERIOD) | 아니오 | 아니오 | grounding | 3, 5, 4 | user_confirmation, evaluation_label |
| M0 | h12_p1 개인택시 수입을 주 단위로 집계했을 때 최소값은?<br>grounding `{"bucket": "week", "aggregation": "min"}` | needs_clarification {"bucket": "week", "inner": "unspecified", "final": "min"} | SILENT_WRONG_PLAN | unsupported (UNRESOLVED_PERIOD) | 아니오 | 아니오 | grounding | 3, 5, 4 | user_confirmation, evaluation_label |
| M0 | h12_p2 개인택시의 주 단위 수입 최소값은?<br>grounding `{"bucket": "week", "aggregation": "min", "taxi_type": "private"}` | needs_clarification {"bucket": "week", "inner": "unspecified", "final": "min"} | CORRECT | unsupported (UNRESOLVED_PERIOD) | 아니오 | 아니오 | grounding | 3, 5, 4 | user_confirmation, evaluation_label |
| M0 | h12_p3 최소 수입은 주 단위로 개인택시 기준 집계하면 얼마인가요?<br>grounding `{"aggregation": "min", "bucket": "week", "taxi_type": "private"}` | needs_clarification (계획 확정 불가) | CORRECT | unsupported (UNRESOLVED_PERIOD) | - | 아니오 | grounding | 3 | user_confirmation, evaluation_label |
| M2 | b21_p0 주 단위로 집계한 택시 수입의 평균은?<br>grounding `{"bucket": "week", "rollup": "avg"}` | needs_clarification {"bucket": "week", "inner": "unspecified", "final": "avg"} | CORRECT | needs_clarification (AMBIGUOUS_INNER_AGGREGATION) | 예 | 예 | none | 3, 5, 4 | user_confirmation, evaluation_label |
| M2 | b21_p1 택시 수입을 주 단위로 집계했을 때 평균은?<br>grounding `{"bucket": "week", "rollup": "avg"}` | needs_clarification {"bucket": "week", "inner": "unspecified", "final": "avg"} | CORRECT | needs_clarification (AMBIGUOUS_INNER_AGGREGATION) | 예 | 예 | none | 3, 5, 4 | user_confirmation, evaluation_label |
| M2 | b21_p2 주 단위 택시 수입의 평균은?<br>grounding `{"bucket": "week", "rollup": "avg"}` | needs_clarification {"bucket": "week", "inner": "unspecified", "final": "avg"} | CORRECT | needs_clarification (AMBIGUOUS_INNER_AGGREGATION) | 예 | 예 | none | 3, 5, 4 | user_confirmation, evaluation_label |
| M2 | b21_p3 수입의 평균을 주 단위로 집계하면?<br>grounding `{"bucket": "week", "rollup": "avg"}` | needs_clarification (계획 확정 불가) | CORRECT | needs_clarification (AMBIGUOUS_INNER_AGGREGATION) | - | 예 | none | 3 | user_confirmation, evaluation_label |
| M2 | b21_p4 택시 수입의 주 단위 집계 평균은?<br>grounding `{"bucket": "week", "rollup": "avg"}` | needs_clarification {"bucket": "week", "inner": "unspecified", "final": "avg"} | CORRECT | needs_clarification (AMBIGUOUS_INNER_AGGREGATION) | 예 | 예 | none | 3, 5, 4 | user_confirmation, evaluation_label |
| M2 | b21_p5 주 단위로 집계하면 택시 수입의 평균은 얼마인가요?<br>grounding `{"bucket": "week", "rollup": "avg"}` | needs_clarification {"bucket": "week", "inner": "unspecified", "final": "avg"} | CORRECT | needs_clarification (AMBIGUOUS_INNER_AGGREGATION) | 예 | 예 | none | 3, 5, 4 | user_confirmation, evaluation_label |
| M2 | b24_p0 월 단위로 집계한 개인택시 수입의 최대값은?<br>grounding `{"bucket": "month", "rollup": "max", "taxi_type": "private"}` | needs_clarification {"bucket": "month", "inner": "unspecified", "final": "max"} | CORRECT | needs_clarification (AMBIGUOUS_INNER_AGGREGATION) | 예 | 예 | none | 3, 5, 4 | user_confirmation, evaluation_label |
| M2 | b24_p1 개인택시 수입을 월 단위로 집계했을 때 최대값은?<br>grounding `{"taxi_type": "private", "bucket": "month", "rollup": "max"}` | needs_clarification {"bucket": "month", "inner": "unspecified", "final": "max"} | CORRECT | needs_clarification (AMBIGUOUS_INNER_AGGREGATION) | 예 | 예 | none | 3, 5, 4 | user_confirmation, evaluation_label |
| M2 | b24_p2 월 단위 개인택시 수입 중 최대값은?<br>grounding `{"bucket": "month", "rollup": "max", "taxi_type": "private"}` | needs_clarification {"bucket": "month", "inner": "unspecified", "final": "max"} | CORRECT | needs_clarification (AMBIGUOUS_INNER_AGGREGATION) | 예 | 예 | none | 3, 5, 4 | user_confirmation, evaluation_label |
| M2 | b24_p3 수입의 최대값을 월 단위로 개인택시 기준 집계하면?<br>grounding `{"bucket": "month", "rollup": "max", "taxi_type": "private"}` | needs_clarification (계획 확정 불가) | CORRECT | needs_clarification (AMBIGUOUS_INNER_AGGREGATION) | - | 예 | none | 3 | user_confirmation, evaluation_label |
| M2 | b24_p4 개인택시의 월 단위 수입 최대값은?<br>grounding `{"taxi_type": "private", "bucket": "month", "rollup": "max"}` | needs_clarification {"bucket": "month", "inner": "unspecified", "final": "max"} | CORRECT | needs_clarification (AMBIGUOUS_INNER_AGGREGATION) | 예 | 예 | none | 3, 5, 4 | user_confirmation, evaluation_label |
| M2 | b24_p5 월 단위로 집계하면 개인택시 수입의 최대값은 얼마인가요?<br>grounding `{"bucket": "month", "rollup": "max", "taxi_type": "private"}` | needs_clarification {"bucket": "month", "inner": "unspecified", "final": "max"} | CORRECT | needs_clarification (AMBIGUOUS_INNER_AGGREGATION) | 예 | 예 | none | 3, 5, 4 | user_confirmation, evaluation_label |
| M2 | f01_p0 월 단위로 합산한 택시 수입의 평균은?<br>grounding `{"aggregation": "sum", "bucket": "month", "rollup": "avg"}` | unsupported {"bucket": "month", "inner": "sum", "final": "avg"} | CORRECT | unsupported (UNRESOLVED_PERIOD) | 예 | 예 | execution_contract | 1, 4 | grounding, execution |
| M2 | f01_p1 택시 수입을 월 단위로 합산했을 때 평균은?<br>grounding `{"bucket": "month", "aggregation": "sum", "rollup": "avg"}` | unsupported {"bucket": "month", "inner": "sum", "final": "avg"} | CORRECT | unsupported (UNRESOLVED_PERIOD) | 예 | 예 | execution_contract | 1, 4 | grounding, execution |
| M2 | f01_p2 월 단위로 합산한 수입들의 평균은 얼마인가요?<br>grounding `{"bucket": "month", "aggregation": "sum", "rollup": "avg"}` | unsupported {"bucket": "month", "inner": "sum", "final": "avg"} | CORRECT | unsupported (UNRESOLVED_PERIOD) | 예 | 예 | execution_contract | 1, 4 | grounding, execution |
| M2 | f01_p3 월 단위로 합산하면 택시 수입의 평균은 얼마인가요?<br>grounding `{"bucket": "month", "aggregation": "avg", "rollup": "sum"}` | unsupported {"bucket": "month", "inner": "sum", "final": "avg"} | SILENT_WRONG_PLAN | unsupported (UNVERIFIED_TIMS_CONTRACT) | 아니오 | 예 | grounding | 1, 4 | grounding, execution |
| M2 | f02_p0 주 단위로 평균 낸 영업 시간의 최대값은?<br>grounding `{"bucket": "week", "aggregation": "avg", "rollup": "max"}` | unsupported {"bucket": "week", "inner": "avg", "final": "max"} | CORRECT | unsupported (UNVERIFIED_TIMS_CONTRACT) | 예 | 예 | execution_contract | 1, 4 | grounding, execution |
| M2 | f02_p1 영업 시간을 주 단위로 평균 냈을 때 최대값은?<br>grounding `{"bucket": "week", "aggregation": "avg", "rollup": "max"}` | unsupported {"bucket": "week", "inner": "avg", "final": "max"} | CORRECT | unsupported (UNVERIFIED_TIMS_CONTRACT) | 예 | 예 | execution_contract | 1, 4 | grounding, execution |
| M2 | f02_p2 주 단위 평균 영업 시간 중 최대값은?<br>grounding `{"bucket": "week", "aggregation": "avg", "rollup": "max"}` | unsupported {"bucket": "week", "inner": "avg", "final": "max"} | CORRECT | unsupported (UNVERIFIED_TIMS_CONTRACT) | 예 | 예 | execution_contract | 1, 4 | grounding, execution |
| M2 | f02_p3 주 단위로 평균 내면 영업 시간의 최대값은 얼마인가요?<br>grounding `{"bucket": "week", "aggregation": "avg", "rollup": "max"}` | unsupported {"bucket": "week", "inner": "avg", "final": "max"} | CORRECT | unsupported (UNVERIFIED_TIMS_CONTRACT) | 예 | 예 | execution_contract | 1, 4 | grounding, execution |
| M2 | f03_p0 월 단위 영업 횟수의 합계는?<br>grounding `{"bucket": "month", "rollup": "sum"}` | unsupported {"bucket": "month", "inner": "sum", "final": "sum"} | CORRECT | needs_clarification (AMBIGUOUS_INNER_AGGREGATION) | 아니오 | 아니오 | grounding | 2, 4, 5 | grounding, evaluation_label, execution |
| M2 | f03_p1 영업 횟수를 월 단위로 집계했을 때 합계는?<br>grounding `{"bucket": "month", "rollup": "sum"}` | unsupported {"bucket": "month", "inner": "sum", "final": "sum"} | CORRECT | needs_clarification (AMBIGUOUS_INNER_AGGREGATION) | 아니오 | 아니오 | grounding | 2, 4, 5 | grounding, evaluation_label, execution |
| M2 | f03_p2 월 단위로 집계한 영업 횟수 합계는?<br>grounding `{"bucket": "month", "rollup": "sum"}` | unsupported {"bucket": "month", "inner": "sum", "final": "sum"} | CORRECT | needs_clarification (AMBIGUOUS_INNER_AGGREGATION) | 아니오 | 아니오 | grounding | 2, 4, 5 | grounding, evaluation_label, execution |
| M2 | f03_p3 월 단위로 집계하면 영업 횟수의 합계는 얼마인가요?<br>grounding `{"bucket": "month", "rollup": "sum"}` | unsupported {"bucket": "month", "inner": "sum", "final": "sum"} | CORRECT | needs_clarification (AMBIGUOUS_INNER_AGGREGATION) | 아니오 | 아니오 | grounding | 2, 4, 5 | grounding, evaluation_label, execution |
| M2 | f13_p0 주 단위로 집계한 법인택시 영업 횟수의 평균은?<br>grounding `{"bucket": "week", "rollup": "avg", "taxi_type": "corporate"}` | needs_clarification {"bucket": "week", "inner": "unspecified", "final": "avg"} | CORRECT | needs_clarification (AMBIGUOUS_INNER_AGGREGATION) | 예 | 예 | none | 3, 5, 4 | user_confirmation, evaluation_label |
| M2 | f13_p1 법인택시 영업 횟수를 주 단위로 집계했을 때 평균은?<br>grounding `{"taxi_type": "corporate", "bucket": "week", "rollup": "avg"}` | needs_clarification {"bucket": "week", "inner": "unspecified", "final": "avg"} | CORRECT | needs_clarification (AMBIGUOUS_INNER_AGGREGATION) | 예 | 예 | none | 3, 5, 4 | user_confirmation, evaluation_label |
| M2 | f13_p2 법인택시의 주 단위 영업 횟수 평균은?<br>grounding `{"taxi_type": "corporate", "bucket": "week", "rollup": "avg"}` | needs_clarification {"bucket": "week", "inner": "unspecified", "final": "avg"} | CORRECT | needs_clarification (AMBIGUOUS_INNER_AGGREGATION) | 예 | 예 | none | 3, 5, 4 | user_confirmation, evaluation_label |
| M2 | f13_p3 주 단위로 집계하면 법인택시 영업 횟수의 평균은 얼마인가요?<br>grounding `{"bucket": "week", "rollup": "avg", "taxi_type": "corporate"}` | needs_clarification {"bucket": "week", "inner": "unspecified", "final": "avg"} | CORRECT | needs_clarification (AMBIGUOUS_INNER_AGGREGATION) | 예 | 예 | none | 3, 5, 4 | user_confirmation, evaluation_label |
| M2 | h12_p0 주 단위로 집계한 개인택시 수입의 최소값은?<br>grounding `{"bucket": "week", "rollup": "min", "taxi_type": "private"}` | needs_clarification {"bucket": "week", "inner": "unspecified", "final": "min"} | CORRECT | needs_clarification (AMBIGUOUS_INNER_AGGREGATION) | 예 | 예 | none | 3, 5, 4 | user_confirmation, evaluation_label |
| M2 | h12_p1 개인택시 수입을 주 단위로 집계했을 때 최소값은?<br>grounding `{"taxi_type": "private", "bucket": "week", "rollup": "min"}` | needs_clarification {"bucket": "week", "inner": "unspecified", "final": "min"} | CORRECT | needs_clarification (AMBIGUOUS_INNER_AGGREGATION) | 예 | 예 | none | 3, 5, 4 | user_confirmation, evaluation_label |
| M2 | h12_p2 개인택시의 주 단위 수입 최소값은?<br>grounding `{"taxi_type": "private", "bucket": "week", "rollup": "min"}` | needs_clarification {"bucket": "week", "inner": "unspecified", "final": "min"} | CORRECT | needs_clarification (AMBIGUOUS_INNER_AGGREGATION) | 예 | 예 | none | 3, 5, 4 | user_confirmation, evaluation_label |
| M2 | h12_p3 최소 수입은 주 단위로 개인택시 기준 집계하면 얼마인가요?<br>grounding `{"bucket": "week", "rollup": "min", "taxi_type": "private"}` | needs_clarification (계획 확정 불가) | CORRECT | needs_clarification (AMBIGUOUS_INNER_AGGREGATION) | - | 예 | none | 3 | user_confirmation, evaluation_label |

## 요약

```json
{
  "M0": {
    "observations": 32,
    "v1_before_correct": 21,
    "after_outcome": {
      "unsupported": 18,
      "needs_clarification": 11,
      "failed": 3
    },
    "v2_outcome_match": 5,
    "v2_plan_match": 5,
    "error_stage": {
      "grounding": 27,
      "none": 2,
      "execution_contract": 3
    },
    "grounding_invented_inner": 15
  },
  "M2": {
    "observations": 32,
    "v1_before_correct": 31,
    "after_outcome": {
      "needs_clarification": 24,
      "unsupported": 8
    },
    "v2_outcome_match": 28,
    "v2_plan_match": 24,
    "error_stage": {
      "none": 20,
      "execution_contract": 7,
      "grounding": 5
    },
    "grounding_invented_inner": 0
  }
}
```

유형: 1 명시된 inner를 LLM이 누락; 2 질문의 뜻으로 inner가 정해짐; 3 질문이 여러 해석을 허용; 4 명확하지만 현재 도구·계약이 지원하지 않음; 5 기존 라벨·평가 변환 오류
