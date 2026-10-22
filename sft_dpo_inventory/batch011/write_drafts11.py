# -*- coding: utf-8 -*-
"""batch011 초안(pilot_008 P2, 결정 219): 학습용 거부(r1)·근접 대조(r2) 문항. **승인이 아니다.** Claude가 손으로 적음.

    python3 write_drafts11.py   # -> candidates_draft.yaml

- 보호 셋·개발 셋·n33 문장을 보지 않고 새로 썼다. 장소는 mock gazetteer 이름만(시도 4·시군구 8·읍면동 10·장소 5). 기준일 2026-09-25.
- r1 거부(60 = 6범주 × 10): 계약(``pilot_008/refusal_contract.md`` 1절)의 모델 거부 (M) — 측정값·조건·대상을 계약 개념과 factor로 적을 수 없는 질문.
  정답 target = ``{"unsupported": true}``(``gold_text`` 비움). 범주: 없는 지표, 없는 묶음 단위(bucket은 week·month뿐), 개인·차량 단위, 예측(미래 날짜 표현 없음),
  다른 교통수단, 도메인 밖.
- r2 근접 대조(40): r1 범주와 비슷해 보이지만 지원되는 질문. 업체 형식 정답 호출(``get_place_scope`` + ``$resolve.scope``, 한 끝 장소 ``$pickup``·``$dropoff``).
- 묶음 단위는 mock에서 실행되는 조합만(bucket + rollup은 안쪽 aggregation과 함께, billing dimension은 scope 없이 — batch010 확인 규칙).
- r2 1차(단순 구조 40)는 검사에서 모두 보호 넷 family(selection_v2·holdout·valid98·aux)라 빠져, batch010 빈 구조로 다시 썼다(2차). 1차 기록은 ``excluded_r2_round1.json``.
"""
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent

R1 = {
    "r1_metric": ("측정값이 계약 목록(통행량·속도·rpm·실차 건수·요금·수입·활성 택시 대수·가동률·운행 일수·공차율)에 없다 → 비슷한 값으로 바꾸지 않고 unsupported", [
        "지난주 대구 택시 승객 수 합계는 몇 명이야?",
        "이번 달 부산 수영구에서 손님이 택시를 기다린 평균 대기 시간은?",
        "작년 서울에서 택시 교통사고가 몇 건 났어?",
        "지난달 인천 택시들의 연료 소비량 합계를 알려줘",
        "올해 대구 중구 택시가 내뿜은 탄소 배출량은 얼마나 돼?",
        "지난주 동대구역에서 출발한 택시의 평균 주행 거리는?",
        "이번 주 부산진구 택시 호출 중 배차에 실패한 비율은?",
        "지난달 대구 택시 기사들의 하루 평균 근무 시간은 얼마야?",
        "올해 서울 택시 승객 만족도 점수 평균을 보여줘",
        "이번 달 광안리 일대 택시가 받은 팁 합계는?",
    ]),
    "r1_bucket": ("묶음 단위가 week·month 밖(날짜·시간·분기·반기·연도·분 단위) → factor로 적을 수 없음", [
        "지난달 대구 택시 수입을 날짜별로 합계 내서 보여줘",
        "작년 부산 개인택시 운행일수를 분기별로 합쳐줘",
        "올해 서울 택시 가동률을 반기별 평균으로 알려줘",
        "지난주 수성구 택시 통행량을 한 시간 단위로 나눠서 보여줘",
        "이번 달 인천 활성 택시 대수를 하루 단위로 평균 내줘",
        "대구 택시 수입을 연도별로 나눠 최근 3년을 비교해줘",
        "지난주 동성로 택시 속도를 15분 단위 평균으로 보여줘",
        "올해 달서구 택시 운행일수를 격주 단위로 합산해줘",
        "작년 부산 동구 택시 수입의 분기별 최댓값은?",
        "이번 달 두류동에서 출발한 실차 건수를 30분 간격으로 세어줘",
    ]),
    "r1_entity": ("개별 차량·기사·승객·회사 단위 → 계약에 그 대상(개념·dimension)이 없음", [
        "차량번호 27가1234 택시의 지난달 수입은?",
        "대구에서 지난주 가장 많이 운행한 택시 기사 이름이 뭐야?",
        "이번 달 부산 택시 기사별 수입 순위 상위 5명을 알려줘",
        "서울에서 작년 운행일수가 가장 많은 택시 차량은 어느 차야?",
        "지난주 동대구역에서 손님을 태운 택시 차량 목록을 보여줘",
        "올해 인천 법인택시를 회사별로 나눠 가동률을 비교해줘",
        "지난달 수성구에서 승객 한 명이 택시를 몇 번 탔는지 알려줘",
        "이번 주 대구 중구 택시 가운데 요금을 가장 많이 받은 차 한 대는?",
        "지난달 광안동에서 탄 승객들의 연령대 분포는?",
        "작년 서울 개인택시 기사들의 평균 경력 연수는?",
    ]),
    "r1_forecast": ("미래 값의 예측·전망 → 날짜 factor에 미래 표현이 없고 계약에 예측 개념이 없음", [
        "다음 주 대구 택시 통행량을 예측해줘",
        "내일 동대구역 택시 통행량이 얼마나 될지 알려줘",
        "다음 달 부산 택시 수입은 얼마로 예상돼?",
        "내년 서울 택시 가동률 전망을 보여줘",
        "다음 주말 광안리 택시 속도가 어떻게 될지 예측해줘",
        "다음 달 인천 활성 택시 대수 추정치를 알려줘",
        "모레 대구 중구 택시 공차율은 어느 정도일까?",
        "앞으로 일주일 동안 수성구 택시 통행량 변화를 예측해줘",
        "다가오는 연휴에 부산진구 택시 통행량이 얼마나 늘지 알려줘",
        "내년 대구 개인택시 운행일수를 추정해줘",
    ]),
    "r1_mode": ("택시가 아닌 교통수단 → 데이터·개념이 택시뿐", [
        "지난주 대구 시내버스 승객 수를 알려줘",
        "이번 달 부산 지하철 이용 건수는?",
        "작년 서울 공공자전거 대여 건수를 보여줘",
        "지난달 동대구역 KTX 승하차 인원은?",
        "이번 주 대구 중구 화물차 통행량을 알려줘",
        "지난주 인천 렌터카 대여 건수는 몇 건이야?",
        "올해 수영구 전동 킥보드 이용 횟수를 알려줘",
        "지난달 부산진구 배달 오토바이 통행량은?",
        "이번 달 대구 자가용 평균 속도는 얼마야?",
        "지난주 서울 대리운전 호출 건수를 보여줘",
    ]),
    "r1_domain": ("택시 운행 데이터 분석이 아닌 질문 → 도구로 답할 수 없음", [
        "내일 대구 날씨 어때?",
        "동성로 근처 맛집 추천해줘",
        "동대구역에서 가장 가까운 주차장은 어디야?",
        "부산 택시 기본요금이 얼마야?",
        "광안리까지 가는 가장 빠른 길을 알려줘",
        "대구 수성구 인구가 몇 명이야?",
        "택시 앱으로 호출하는 방법을 알려줘",
        "서울 아파트 평균 매매가는?",
        "초량동에 있는 병원 목록을 보여줘",
        "인천 공항 가는 리무진 버스 시간표 알려줘",
    ]),
}

# r2: (gap, question, gold_text, rationale) — batch010 빈 구조(``batch010/free_structures10.json``: 보호 넷 family 밖, 현재 코드가 답함)만 씀. 1차에 쓴 단순 구조 40개는 모두 보호 넷 family라 뺐다.
R2 = [
    ('r2_metric', '지난해 부산에서 활성 택시 대수가 가장 많았을 때 몇 대였어?', 'get_place_scope(name=부산)\nget_billing_metrics(metric=active_taxi_count, scope=$resolve.scope, date=last_year, aggregation=max)', '활성 택시 대수(r1 승객 수와 대조)'),  # 3차(겹침·검증 사슬로 2차 문항 교체)
    ('r2_metric', '올해 서울 소속 택시 가동률의 중간값을 알려줘', 'get_place_scope(name=서울)\nget_billing_metrics(metric=active_taxi_ratio, scope=$resolve.scope, date=this_year, aggregation=med)', '가동률(r1 만족도와 대조)'),
    ('r2_metric', '지난달 대구 택시 운행일수를 주별로 합한 뒤 그 주별 합계의 중간값은?', 'get_place_scope(name=대구)\nget_billing_metrics(metric=operating_days, scope=$resolve.scope, date=last_month, aggregation=sum, bucket=week, rollup=med)', '운행 일수(r1 근무 시간과 대조)'),
    ('r2_metric', '작년 인천 택시 수입을 월별 중간값으로 낸 뒤 그중 최댓값은?', 'get_place_scope(name=인천)\nget_billing_metrics(metric=revenue, scope=$resolve.scope, date=last_year, aggregation=med, bucket=month, rollup=max)', '수입(r1 팁·연료비와 대조)'),
    ('r2_metric', '작년 요일별 택시 수입 평균을 보여줘', 'get_billing_metrics(metric=revenue, date=last_year, aggregation=avg, dimension=dayofweek)', '수입 요일별(r1 사고 건수와 대조)'),
    ('r2_metric', '작년 시도별 택시 수입이 가장 적은 두 곳은?', 'get_billing_metrics(metric=revenue, date=last_year, dimension=sido, order=bottom, limit=2)', '수입 시도별(r1 배출량과 대조)'),
    ('r2_metric', '지난달 시도별로 택시 운행일수 최댓값을 구했을 때 가장 큰 두 곳은?', 'get_billing_metrics(metric=operating_days, date=last_month, aggregation=max, dimension=sido, order=top, limit=2)', '활성 대수 시도별(r1 배차 실패율과 대조)'),  # 3차(겹침·검증 사슬로 2차 문항 교체)
    ('r2_bucket', '지난달 대구 택시 수입을 주별 합계로 낸 뒤 그 주별 합계들의 최솟값은?', 'get_place_scope(name=대구)\nget_billing_metrics(metric=revenue, scope=$resolve.scope, date=last_month, aggregation=sum, bucket=week, rollup=min)', '주별(r1 날짜별과 대조)'),
    ('r2_bucket', '작년 부산 택시 운행일수를 월별 최댓값으로 구한 다음 그 값들의 평균은?', 'get_place_scope(name=부산)\nget_billing_metrics(metric=operating_days, scope=$resolve.scope, date=last_year, aggregation=max, bucket=month, rollup=avg)', '월별(r1 분기별과 대조)'),
    ('r2_bucket', '올해 서울 택시 가동률을 주별 최솟값으로 낸 뒤 그 평균은?', 'get_place_scope(name=서울)\nget_billing_metrics(metric=active_taxi_ratio, scope=$resolve.scope, date=this_year, aggregation=min, bucket=week, rollup=avg)', '주별(r1 반기별과 대조)'),
    ('r2_bucket', '이번 달 인천 활성 택시 대수를 주별 중간값으로 구하고 그중 가장 큰 값은?', 'get_place_scope(name=인천)\nget_billing_metrics(metric=active_taxi_count, scope=$resolve.scope, date=this_month, aggregation=med, bucket=week, rollup=max)', '주별(r1 하루 단위와 대조)'),
    ('r2_bucket', '작년 대구 수성구 택시 수입을 월별 최댓값으로 낸 뒤 그 중간값은?', 'get_place_scope(name=수성구, region=대구)\nget_billing_metrics(metric=revenue, scope=$resolve.scope, date=last_year, aggregation=max, bucket=month, rollup=med)', '월별(r1 분기별 최댓값과 대조)'),
    ('r2_bucket', '올해 부산진구 택시 운행일수를 주별 합계로 낸 다음 그 합계들을 모두 더하면?', 'get_place_scope(name=부산진구)\nget_billing_metrics(metric=operating_days, scope=$resolve.scope, date=this_year, aggregation=sum, bucket=week, rollup=sum)', '주별(r1 격주와 대조)'),
    ('r2_bucket', '작년 요일별 택시 운행일수를 보여줘', 'get_billing_metrics(metric=operating_days, date=last_year, dimension=dayofweek)', '요일별 dimension(r1 한 시간 단위와 대조)'),
    ('r2_entity', '작년 시도별 택시 운행일수 합계가 가장 적은 두 곳은?', 'get_billing_metrics(metric=operating_days, date=last_year, aggregation=sum, dimension=sido, order=bottom, limit=2)', '시도 단위(r1 차량별 최다와 대조)'),
    ('r2_entity', '지난주 동대구역에서 출발한 실차를 도착 H3 셀별로 세어줘', 'get_place_scope(name=동대구역)\nget_trip_count(scope_pickup=$pickup.scope, date=last_week, dimension=h3, dimension_target=dropoff)', '셀 단위(r1 차량 목록과 대조)'),
    ('r2_entity', '지난주 수성구에서 탄 실차를 출발 동과 도착 동의 조합으로 나눠 알려줘', 'get_place_scope(name=수성구, region=대구)\nget_trip_count(scope_pickup=$pickup.scope, date=last_week, dimension=emd, dimension_target=both)', '읍면동 짝(r1 승객 한 명과 대조)'),  # 3차(겹침·검증 사슬로 2차 문항 교체)
    ('r2_entity', '지난주 광안리에 도착한 실차를 출발 시도별로 세어줘', 'get_place_scope(name=광안리)\nget_trip_count(scope_dropoff=$dropoff.scope, date=last_week, dimension=sido, dimension_target=pickup)', '출발 시도(r1 승객 연령대와 대조)'),
    ('r2_entity', '지난주 초량동으로 들어온 실차를 출발 시군구별로 보여줘', 'get_place_scope(name=초량동, region=부산)\nget_trip_count(scope_dropoff=$dropoff.scope, date=last_week, dimension=sigungu, dimension_target=pickup)', '출발 시군구(r1 기사 이름과 대조)'),
    ('r2_entity', '지난주 두류동에서 나간 실차가 가장 많이 도착한 H3 셀 두 곳은?', 'get_place_scope(name=두류동, region=대구)\nget_trip_count(scope_pickup=$pickup.scope, date=last_week, dimension=h3, dimension_target=dropoff, order=top, limit=2)', '셀 순위(r1 차 한 대와 대조)'),
    ('r2_entity', '지난주 신천동이 도착지인 실차를 승차한 동 기준으로 집계해줘', 'get_place_scope(name=신천동, region=대구)\nget_trip_count(scope_dropoff=$dropoff.scope, date=last_week, dimension=emd, dimension_target=pickup)', '출발 읍면동(r1 회사별과 대조)'),  # 3차(겹침·검증 사슬로 2차 문항 교체)
    ('r2_forecast', '작년 대구 택시 수입을 주별 평균으로 낸 뒤 그 주별 평균들의 최솟값은?', 'get_place_scope(name=대구)\nget_billing_metrics(metric=revenue, scope=$resolve.scope, date=last_year, aggregation=avg, bucket=week, rollup=min)', '작년(r1 내년 전망과 대조)'),
    ('r2_forecast', '지난달 서울 활성 택시 대수를 주별 최댓값으로 낸 다음 그 평균은?', 'get_place_scope(name=서울)\nget_billing_metrics(metric=active_taxi_count, scope=$resolve.scope, date=last_month, aggregation=max, bucket=week, rollup=avg)', '지난달(r1 다음 달 추정과 대조)'),
    ('r2_forecast', '작년 부산 택시 가동률을 월별 중간값으로 낸 뒤 그 최솟값은?', 'get_place_scope(name=부산)\nget_billing_metrics(metric=active_taxi_ratio, scope=$resolve.scope, date=last_year, aggregation=med, bucket=month, rollup=min)', '작년(r1 내년 가동률 전망과 대조)'),
    ('r2_forecast', '지난주 택시 운행일수의 요일별 최솟값을 알려줘', 'get_billing_metrics(metric=operating_days, date=last_week, aggregation=min, dimension=dayofweek)', '지난주(r1 다음 주 예측과 대조)'),  # 3차(겹침·검증 사슬로 2차 문항 교체)
    ('r2_forecast', '작년 인천 택시 운행일수를 월별 합계로 낸 뒤 그 최댓값은?', 'get_place_scope(name=인천)\nget_billing_metrics(metric=operating_days, scope=$resolve.scope, date=last_year, aggregation=sum, bucket=month, rollup=max)', '작년(r1 내년 운행일수 추정과 대조)'),
    ('r2_forecast', '작년 대구 중구 택시 수입을 월별 중간값으로 낸 뒤 그 중간값은?', 'get_place_scope(name=중구, region=대구)\nget_billing_metrics(metric=revenue, scope=$resolve.scope, date=last_year, aggregation=med, bucket=month, rollup=med)', '작년(r1 다음 달 수입 예상과 대조)'),
    ('r2_forecast', '지난달 대구 택시 가동률을 주별 최댓값으로 낸 뒤 그중 가장 큰 값은?', 'get_place_scope(name=대구)\nget_billing_metrics(metric=active_taxi_ratio, scope=$resolve.scope, date=last_month, aggregation=max, bucket=week, rollup=max)', '지난달(r1 모레와 대조)'),
    ('r2_mode', '지난주 태평로동에서 탄 택시 실차의 도착 시도를 따졌을 때 가장 적은 두 곳은?', 'get_place_scope(name=태평로동, region=대구)\nget_trip_count(scope_pickup=$pickup.scope, date=last_week, dimension=sido, dimension_target=dropoff, order=bottom, limit=2)', '택시 실차(r1 시내버스와 대조)'),  # 3차(겹침·검증 사슬로 2차 문항 교체)
    ('r2_mode', '지난주 중앙로동에 도착한 택시 실차를 출발 H3 셀별로 볼 때 가장 많은 두 곳은?', 'get_place_scope(name=중앙로동, region=대구)\nget_trip_count(scope_dropoff=$dropoff.scope, date=last_week, dimension=h3, dimension_target=pickup, order=top, limit=2)', '택시 실차(r1 지하철과 대조)'),
    ('r2_mode', '지난주 태평로동에 도착한 택시 실차를 출발 H3 셀별로 볼 때 가장 적은 두 곳은?', 'get_place_scope(name=태평로동, region=대구)\nget_trip_count(scope_dropoff=$dropoff.scope, date=last_week, dimension=h3, dimension_target=pickup, order=bottom, limit=2)', '택시 실차(r1 공공자전거와 대조)'),
    ('r2_mode', '지난주 광안동에 도착한 택시 실차를 출발 시도별로 볼 때 가장 많은 두 곳은?', 'get_place_scope(name=광안동, region=부산)\nget_trip_count(scope_dropoff=$dropoff.scope, date=last_week, dimension=sido, dimension_target=pickup, order=top, limit=2)', '택시 실차(r1 KTX와 대조)'),
    ('r2_mode', '지난주 두류동에 내린 택시 실차를 출발 동–도착 동 쌍으로 묶었을 때 상위 두 쌍은?', 'get_place_scope(name=두류동, region=대구)\nget_trip_count(scope_dropoff=$dropoff.scope, date=last_week, dimension=emd, dimension_target=both, order=top, limit=2)', '택시 실차(r1 렌터카와 대조)'),  # 3차(겹침·검증 사슬로 2차 문항 교체)
    ('r2_mode', '지난주 동인동에 도착한 택시 실차를 출발 시도별로 볼 때 가장 적은 두 곳은?', 'get_place_scope(name=동인동, region=대구)\nget_trip_count(scope_dropoff=$dropoff.scope, date=last_week, dimension=sido, dimension_target=pickup, order=bottom, limit=2)', '택시 실차(r1 배달 오토바이와 대조)'),
    ('r2_domain', '지난주 두산동에서 나간 실차가 도착한 H3 셀 중 가장 적은 두 곳은?', 'get_place_scope(name=두산동, region=대구)\nget_trip_count(scope_pickup=$pickup.scope, date=last_week, dimension=h3, dimension_target=dropoff, order=bottom, limit=2)', '장소 분석(r1 길안내와 대조)'),
    ('r2_domain', '지난주 초읍동에서 내린 손님들이 어느 동에서 탔는지 동별 실차 건수로 보여줘', 'get_place_scope(name=초읍동, region=부산)\nget_trip_count(scope_dropoff=$dropoff.scope, date=last_week, dimension=emd, dimension_target=pickup)', '장소 분석(r1 병원 목록과 대조)'),  # 3차(겹침·검증 사슬로 2차 문항 교체)
    ('r2_domain', '작년 요일별 택시 가동률이 가장 높은 두 요일은?', 'get_billing_metrics(metric=active_taxi_ratio, date=last_year, dimension=dayofweek, order=top, limit=2)', '요일 분석(r1 날씨와 대조)'),
    ('r2_domain', '지난달 요일별 택시 가동률이 가장 낮은 두 요일은?', 'get_billing_metrics(metric=active_taxi_ratio, date=last_month, dimension=dayofweek, order=bottom, limit=2)', '요일 분석(r1 호출 방법과 대조)'),
    ('r2_domain', '작년 요일별 평균 택시 가동률을 보여줘', 'get_billing_metrics(metric=active_taxi_ratio, date=last_year, aggregation=avg, dimension=dayofweek)', '요일 분석(r1 집값과 대조)'),
    ('r2_domain', '지난달 시도별 택시 수입 최솟값은?', 'get_billing_metrics(metric=revenue, date=last_month, aggregation=min, dimension=sido)', '지역 분석(r1 인구와 대조)'),  # 3차(겹침·검증 사슬로 2차 문항 교체)
]

def main():
    cands, n = [], 0
    for gap, (why, qs) in R1.items():
        for q in qs:
            n += 1
            cands.append({"id": f"b011-{n:03d}", "gap": gap, "kind": "r1_refusal", "question": q, "gold_text": "", "target": '{"unsupported": true}', "rationale": why})
    for gap, q, g, why in R2:
        n += 1
        cands.append({"id": f"b011-{n:03d}", "gap": gap, "kind": "r2_contrast", "question": q, "gold_text": g, "rationale": why})
    doc = {"batch": "batch011", "status": "초안(승인 아님)", "author": "Claude", "date": "2026-10-22", "reference_date": "2026-09-25", "candidates": cands}
    (HERE / "candidates_draft.yaml").write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(len(cands), sum(c["kind"] == "r1_refusal" for c in cands), sum(c["kind"] == "r2_contrast" for c in cands))


if __name__ == "__main__":
    main()
