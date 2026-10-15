# pilot_006 사람 검토 안내서

작성: 2026-10-16(세션 2, C4). 이 안내서와 시트는 검토를 돕는 자료다. **어떤 시트·초안·validator 통과도 승인이 아니다.** 승인은 사람이 질문을 읽고 내린 결정뿐이다.

## 1. 무엇을 검토하나(위치와 건수)

| 묶음 | 시트(새 버전, 원본은 그대로) | 건수 | 우선순위 |
|---|---|---:|---|
| aug300 semantics 초안 | `pilot_006_prep/aug300_review/review/aug300_review_v2.xlsx`(aug300 시트) | 260(검토 대상) + 13(결정 119 제외, 검토 불필요) | 높음 90 · 보통 57 · 낮음 113 |
| aug300 base 출력 비교 | `pilot_006_prep/aug300_review/review/aug300_review.xlsx`(v1, vllm_outputs 시트) | 64쌍(train만) | – |
| batch007 | `batch007/review/batch007_review_v2.xlsx` | 27 + 모델 출력 비교 25쌍(v1 vllm_outputs 시트) | 높음 27 |
| batch008 | `batch008/review/batch008_review_v1.xlsx` | 10 | 높음 5 · 보통 5 |
| pg EDIT_REQUIRED | `pg_imports/review/pg_edit_required_v1.xlsx` | 7 | 높음 7 |

## 2. 열 설명

- **aug300 시트**: id, 상태(결정 119: train/holdout/제외), 우선순위, 유형, risk_tags, 질문, 정답 호출(xlsx), semantics 요약(측정값·조건 span·od_role·묶음·순위·집계),
  J3 첫 응답(base greedy가 초안과 같은가), J1 일치(base 표본 9개 중 초안과 같은 grounding 수, 조건 계층 전), span(측정 표현을 찾았는가), 검증 사슬(Full·Partial 같은 실행),
  결정 칸 다섯 개.
- **batch007·batch008**: id, 우선순위, 대조·gap, 질문, 초안 grounding, 근거, base 첫 응답, J1(batch007만), 결정 칸.
- **pg EDIT_REQUIRED**: 수정 전·후 질문, 수정 후 gold, pg 근거, 남은 쟁점과 권고(Claude 초안 의견), 결정 칸.
- holdout 53문항은 모델 출력이 봉인이라 신호 열이 비어 있다. 정답·span만 확인한다. 학습·prompt 예시·보강 설계에 쓰지 않는다.

## 3. 판정 선택지

승인 / 수정 / 보류 / 제외.
- **승인**: 초안 그대로 학습(holdout은 평가)에 쓴다.
- **수정**: '수정 grounding' 칸에 고친 grounding을 JSON으로 적는다(업체 형식 정답 호출을 고쳐도 된다. 메모에 적는다).
- **보류**: 지금 판단할 수 없다. 이유를 메모에.
- **제외**: 쓰지 않는다.

## 4. 우선순위 규칙(검토 순서용, 판정이 아님)

- 어려운 risk tag = dt_pickup·dt_dropoff·dt_both·od_both_dt_one·occupied_passage·silcha_trip·vicinity·bucket_week·bucket_month.
- aug300 train: 높음 = J1 ≤ 3/9, 또는 J3 다름이고 J1 ≤ 5/9, 또는 span 미확인, 또는 어려운 tag. 낮음 = J3 같음·J1 ≥ 7/9·span 확인·어려운 tag 없음. 그 밖 보통.
- aug300 holdout: 높음 = span 미확인 또는 어려운 tag, 그 밖 보통.
- batch007·008: 높음 = base 첫 응답이 초안과 다름(또는 J1 ≤ 3/9). pg EDIT_REQUIRED는 모두 높음.
- 시트는 우선순위 → id 순으로 정렬돼 있다. 위에서부터 보면 된다.

## 5. 판단 기준(요약, 상세는 batch007/review/README.md 4절)

1. 측정 대상: 통행량(passage_count) 대 실차 건수(trip_count). "손님을 태운 택시의 통행량"은 passage_count + occupied.
2. 끝(endpoint): 장소가 제한하는 끝 = od_role, 묶는 끝 = dimension_target. "태운 곳"=pickup, "내려준 곳"=dropoff.
3. 묶음: 요일·지역별 = dimension, 주·월 단위로 집계한 뒤 다시 집계 = bucket + rollup.
4. 질문에 없는 운행 상태·집계·묶음·순위를 만들지 않는다. 근처·주변이 있을 때만 vicinity.
5. 문장이 보호된 평가 셋 문장을 바꿔 쓴 것처럼 보이면 제외하고 메모한다.

## 6. 예상 소요 시간

약 **8시간**(`pilot_006_prep/review/priority_counts.json`의 478분). 가정: 문항당 높음 2분, 보통 1분, 낮음 0.5분, 모델 출력 비교 쌍 1분, pg 수정 3분.
낮음 113건을 표본 검토(예: 20%)로 줄이면 약 7시간 반.

## 7. 결과를 돌려받는 방법

- XLSX의 결정 칸을 채워 같은 위치에 저장하거나 새 이름(예: `aug300_review_v2_reviewed.xlsx`)으로 저장해 알려 주면, 세션 3에서 Claude가 읽어
  `training.annotations.workflow decide`로 decisions 파일에 **검토자 이름과 함께** 기록한다(XLSX 편집을 자동으로 승인으로 가져오지 않고, 기록 전에 목록을 보여 확인받는다).
- 표본 검토로 끝낼 묶음(예: 낮음)이 있으면 그 규칙을 함께 알려 준다.
