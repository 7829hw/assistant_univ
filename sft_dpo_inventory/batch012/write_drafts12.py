# -*- coding: utf-8 -*-
"""batch012 초안(pilot_009 준비 P2, 결정 229 Y3): 학습용 거부(r1)·근접 대조(r2) 문항. **승인이 아니다.** Claude가 손으로 적음.

    python3 write_drafts12.py   # -> candidates_draft.yaml

- 보호 셋·개발 셋·protected_final 문장을 보지 않고 새로 썼다(batch011·refusal_dev와 겹치지 않게 표현을 바꿈). 장소는 mock gazetteer 이름만. 기준일 2026-10-26.
- r1 거부(60): 개별 단위 25(기사·차량·회사·승객), 묶음 단위 20(시간·일·분기·반기·연), 다른 교통수단 15. 정답 target = ``{"unsupported": true}``.
  범주 이름(gap)은 batch011과 같다(``r1_entity``·``r1_bucket``·``r1_mode``).
- r2 근접 대조(40): batch010 빈 구조(``batch010/free_structures10.json``, 보호 넷 family 밖)에서 시도·시군구·요일 묶음, 주·월 bucket, 택시 유형(개인·법인), 한 끝 실차 묶음.
  기간은 bucket에 맞게(월별 ≥ 2개월, 주별 ≥ 2주, 요일별 ≥ 1주). batch011 r2와 같은 정답 grounding이 되지 않게 장소·기간·집계 조합을 바꿈.
- 2차: 1차 검사(``excluded_round1.json``)에서 빠진 r1 3(refusal_dev v1과 같은 문장)·r2 16(빈 구조 목록 밖 조합, Jaccard, mock 장소 조합)을 바꾸고,
  검사는 통과했지만 refusal_dev v1 문항과 거의 같은 뜻·문형인 r1 3을 함께 바꿈(개발 셋 오염 방지). 줄 끝 주석에 1차 문장.
"""
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent

R1 = {
    "r1_entity": ("개별 기사·차량·회사·승객 단위 → 계약에 그 대상(개념·묶음 기준)이 없음(택시 유형 개인·법인 구분과 지역 묶음만 됨)", [
        "지난달 대구 택시 기사 한 사람당 평균 수입은 얼마야?",
        "이번 주 수성구에서 가장 오래 운행한 택시의 차량 번호를 알려줘",
        "작년 부산 법인택시 회사 가운데 수입이 가장 많은 곳은?",
        "지난주 동대구역에서 손님을 제일 많이 태운 기사는 누구야?",
        "올해 인천 택시 기사별 운행일수를 보여줘",
        "지난달 서울 택시 차량마다 운행일수를 나열해줘",
        "이번 달 광안리에서 같은 손님이 두 번 넘게 택시를 탄 경우는 몇 번이야?",
        "작년 대구 개인택시 차량 한 대당 연간 수입 순위를 보여줘",
        "지난주 두류동에서 출발한 실차를 운전기사별로 세어줘",
        "올해 부산 택시 운수회사별 활성 택시 대수를 비교해줘",
        "지난달 대구 중구에서 택시를 탄 손님들의 직업 분포는?",  # 2차(1차: 지난달 대구 중구 택시 이용객의 성별 비율은?)
        "이번 주 신천동에서 내린 손님마다 몇 번씩 탔는지 알려줘",
        "작년 서울 택시 기사 가운데 운행일수가 가장 많은 사람을 알려줘",  # 2차(1차: 작년 서울에서 수입이 가장 적은 택시 기사 세 명은?)
        "지난달 달서구 택시 가운데 공차율이 가장 높은 차 한 대를 찾아줘",
        "이번 달 인천 법인택시 회사마다 가동률 평균을 보여줘",
        "지난주 초량동에서 손님을 태운 기사 명단을 보여줘",
        "올해 대구 택시를 차량 단위로 나눠 평균 속도 순위를 매겨줘",
        "지난달 부산진구에서 택시를 가장 자주 이용한 손님은 누구야?",
        "작년 대구 동구 개인택시 사업자별 운행일수 합계는?",
        "이번 주 동성로에서 운행한 택시 대수를 회사 이름별로 나눠줘",
        "지난달 서울 택시 기사마다 수입을 구해서 그 중간값을 알려줘",
        "올해 수영구 택시 손님 한 명이 다시 이용한 비율은?",
        "지난주 태평로동을 지나간 택시들의 번호판 목록을 뽑아줘",
        "작년 인천 택시 회사별 공차율 순위를 알려줘",
        "이번 달 대구 택시 운전자 나이대별 수입을 보여줘",
    ]),
    "r1_bucket": ("묶음 단위가 week·month 밖(시간·하루·분기·반기·연) → factor로 적을 수 없음", [
        "지난달 서울 택시 수입을 하루 단위로 합산해서 보여줘",
        "작년 대구 택시 가동률을 분기마다 평균 내줘",
        "올해 인천 택시 운행일수를 상반기와 하반기로 나눠 합계를 알려줘",
        "지난주 동대구역 택시 통행량을 매시간 단위로 나눠 보여줘",
        "작년 부산 택시 수입을 4분기로 쪼개 합계를 내줘",  # 2차(1차: 최근 5년간 부산 택시 수입을 해마다 비교해줘)
        "이번 달 수성구 택시 공차율을 일별로 보여줘",
        "작년 서울 활성 택시 대수를 분기 단위 최댓값으로 알려줘",
        "지난주 광안리 택시 속도를 2시간 간격 평균으로 보여줘",
        "올해 달서구 택시 수입을 반년 단위로 나눠 비교해줘",
        "지난달 부산진구 실차 건수를 날짜마다 세어줘",
        "작년 대구 중구 택시 운행일수를 분기별 평균으로 내줘",
        "이번 주 동성로 택시 통행량을 1시간마다 끊어서 보여줘",
        "2023년부터 올해까지 인천 택시 가동률을 연 단위로 보여줘",
        "지난달 초량동 택시 RPM을 하루씩 평균 내줘",
        "작년 서울 택시 수입을 3개월 단위로 합산해줘",
        "올해 부산 활성 택시 대수를 반기별 중간값으로 알려줘",
        "지난주 두산동에서 내린 실차 건수를 시간 단위로 집계해줘",
        "이번 달 대구 택시 요금 평균을 날마다 구해줘",
        "작년 수영구 택시 공차율의 분기별 최솟값은?",
        "지난 3년간 대구 택시 운행일수를 해마다 합쳐서 보여줘",
    ]),
    "r1_mode": ("택시가 아닌 교통수단 → 데이터·개념이 택시뿐", [
        "작년 대구 경전철 하루 평균 승객 수는?",  # 2차(1차: 지난달 대구 도시철도 이용객 수는?)
        "이번 주 부산 순환버스 정류장별 승차 인원을 보여줘",  # 2차(1차: 이번 주 부산 마을버스 운행 횟수를 알려줘)
        "작년 인천 시외버스 승차 건수는 몇 건이야?",
        "지난주 서울 고속버스 터미널 출발 편수는?",  # 2차(1차: 지난주 서울 공유 자전거 반납 건수를 보여줘)
        "올해 동대구역 SRT 이용객 수를 알려줘",
        "지난달 수성구 오토바이 통행량은?",
        "이번 달 광안리 관광버스 주차 대수는?",
        "작년 부산 화물 트럭 평균 속도는 얼마야?",
        "지난주 대구 중구 전기 자전거 이용 건수를 보여줘",
        "이번 주 인천 공항철도 승객 수는?",
        "지난달 서울 카셰어링 대여 건수는 몇 건이야?",
        "올해 부산진구 시내버스 평균 배차 간격은?",
        "지난주 동성로 일대 자가용 통행량을 알려줘",
        "작년 인천 여객선 이용객 수를 보여줘",
        "이번 달 달서구 퍼스널 모빌리티 대여 건수는?",
    ]),
}

# r2: (gap, question, gold_text, rationale) — batch010 빈 구조만.
R2 = [
    # 택시 유형·지역·한 끝 실차 묶음(r1 개별 단위와 대조)
    ('r2_entity', '작년 대구 법인택시 수입을 월별 최솟값으로 낸 뒤 그 합계는?', 'get_place_scope(name=대구)\nget_billing_metrics(metric=revenue, scope=$resolve.scope, date=last_year, taxi_type=corporate, aggregation=min, bucket=month, rollup=sum)', '법인택시 유형(r1 회사별과 대조)'),  # 2차(1차: 작년 대구 법인택시 수입을 월별 합계로 낸 뒤 그중 최솟값은?)
    ('r2_entity', '올해 부산 개인택시 운행일수를 주별 최댓값으로 구한 다음 그 중간값은?', 'get_place_scope(name=부산)\nget_billing_metrics(metric=operating_days, scope=$resolve.scope, date=this_year, taxi_type=private, aggregation=max, bucket=week, rollup=med)', '개인택시 유형(r1 기사별 운행일수와 대조)'),  # 2차(1차: 올해 부산 개인택시 운행일수를 주별 평균으로 구한 다음 그 최댓값은?)
    ('r2_entity', '지난달 법인택시 가동률 평균이 가장 낮은 시도 두 곳은?', 'get_billing_metrics(metric=active_taxi_ratio, date=last_month, taxi_type=corporate, aggregation=avg, dimension=sido, order=bottom, limit=2)', '법인택시·시도별(r1 회사마다 가동률과 대조)'),  # 2차(1차: 지난달 시도별 법인택시 가동률 평균을 보여줘)
    ('r2_entity', '작년 요일별 개인택시 수입 합계가 가장 적은 두 요일은?', 'get_billing_metrics(metric=revenue, date=last_year, taxi_type=private, aggregation=sum, dimension=dayofweek, order=bottom, limit=2)', '개인택시·요일별(r1 사업자별과 대조)'),  # 2차(1차: 작년 요일별 개인택시 수입 합계를 알려줘)
    ('r2_entity', '이번 달 두류동을 출발지로 한 실차의 도착 셀별 건수를 알려줘', 'get_place_scope(name=두류동, region=대구)\nget_trip_count(scope_pickup=$pickup.scope, date=this_month, dimension=h3, dimension_target=dropoff)', '도착 셀 묶음(r1 손님마다와 대조)'),  # 2차(1차: 지난달 광안동에서 출발한 실차를 도착 H3 셀별로 세어줘)
    ('r2_entity', '이번 달 초읍동이 도착지인 실차를 승차 시군구별로 집계해줘', 'get_place_scope(name=초읍동, region=부산)\nget_trip_count(scope_dropoff=$dropoff.scope, date=this_month, dimension=sigungu, dimension_target=pickup)', '출발 시군구(r1 기사 명단과 대조)'),  # 2차(1차: 지난달 동인동에 도착한 실차를 출발 시군구별로 보여줘)
    ('r2_entity', '이번 달 초읍동에서 탄 실차의 도착 시도 중 가장 적은 두 곳은?', 'get_place_scope(name=초읍동, region=부산)\nget_trip_count(scope_pickup=$pickup.scope, date=this_month, dimension=sido, dimension_target=dropoff, order=bottom, limit=2)', '도착 시도 순위(r1 가장 자주 이용한 손님과 대조)'),
    ('r2_entity', '지난달 중앙로동에서 출발한 실차를 출발 동과 도착 동의 짝으로 나눠 세어줘', 'get_place_scope(name=중앙로동, region=대구)\nget_trip_count(scope_pickup=$pickup.scope, date=last_month, dimension=emd, dimension_target=both)', '읍면동 짝(r1 같은 손님 재이용과 대조)'),
    ('r2_entity', '이번 달 동대구역에 내린 실차를 출발 시도별로 세어줘', 'get_place_scope(name=동대구역)\nget_trip_count(scope_dropoff=$dropoff.scope, date=this_month, dimension=sido, dimension_target=pickup)', '출발 시도(r1 손님 제일 많이 태운 기사와 대조)'),
    ('r2_entity', '지난달 두산동에 도착한 실차의 출발 동별 건수를 보여줘', 'get_place_scope(name=두산동, region=대구)\nget_trip_count(scope_dropoff=$dropoff.scope, date=last_month, dimension=emd, dimension_target=pickup)', '출발 읍면동(r1 운전기사별과 대조)'),
    ('r2_entity', '이번 달 어린이대공원에서 출발한 실차가 가장 많이 도착한 H3 셀 두 곳은?', 'get_place_scope(name=어린이대공원)\nget_trip_count(scope_pickup=$pickup.scope, date=this_month, dimension=h3, dimension_target=dropoff, order=top, limit=2)', '셀 순위(r1 차량 번호와 대조)'),
    ('r2_entity', '이번 달 두산동에 내린 실차가 적게 출발한 H3 셀 두 곳을 알려줘', 'get_place_scope(name=두산동, region=대구)\nget_trip_count(scope_dropoff=$dropoff.scope, date=this_month, dimension=h3, dimension_target=pickup, order=bottom, limit=2)', '셀 순위(r1 번호판 목록과 대조)'),  # 2차(1차: 지난달 신천동으로 간 실차를 출발 H3 셀 기준으로 볼 때 가장 적은 두 곳은?)
    ('r2_entity', '작년 시도별 개인택시 운행일수 합계를 보여줘', 'get_billing_metrics(metric=operating_days, date=last_year, taxi_type=private, aggregation=sum, dimension=sido)', '개인택시·시도별(r1 차량마다 운행일수와 대조)'),
    ('r2_entity', '올해 요일별 법인택시 활성 택시 대수 최댓값은?', 'get_billing_metrics(metric=active_taxi_count, date=this_year, taxi_type=corporate, aggregation=max, dimension=dayofweek)', '법인택시·요일별(r1 운수회사별과 대조)'),
    ('r2_entity', '지난달 시도별 개인택시 수입 중간값이 가장 큰 두 곳은?', 'get_billing_metrics(metric=revenue, date=last_month, taxi_type=private, aggregation=med, dimension=sido, order=top, limit=2)', '개인택시·시도 순위(r1 수입 적은 기사 세 명과 대조)'),
    ('r2_entity', '올해 인천 법인택시 가동률의 최솟값은?', 'get_place_scope(name=인천)\nget_billing_metrics(metric=active_taxi_ratio, scope=$resolve.scope, date=this_year, taxi_type=corporate, aggregation=min)', '법인택시 유형(r1 회사별 공차율과 대조)'),
    # 주·월 bucket, 요일·시도·시군구 묶음(r1 묶음 단위와 대조)
    ('r2_bucket', '2026년 1월부터 6월까지 대구 택시 수입을 월별 평균으로 낸 뒤 그 최댓값은?', 'get_place_scope(name=대구)\nget_billing_metrics(metric=revenue, scope=$resolve.scope, date=20260101-20260630, aggregation=avg, bucket=month, rollup=max)', '월별(r1 반년 단위와 대조)'),
    ('r2_bucket', '지난달 부산 택시 가동률의 주별 최솟값들 가운데 가장 작은 값은?', 'get_place_scope(name=부산)\nget_billing_metrics(metric=active_taxi_ratio, scope=$resolve.scope, date=last_month, aggregation=min, bucket=week, rollup=min)', '주별(r1 일별과 대조)'),  # 2차(1차: 지난달 부산 택시 가동률을 주별 평균으로 구하고 그중 최솟값은?)
    ('r2_bucket', '올해 대구 수성구 택시 운행일수를 월별 최솟값으로 낸 뒤 그 평균은?', 'get_place_scope(name=수성구, region=대구)\nget_billing_metrics(metric=operating_days, scope=$resolve.scope, date=this_year, aggregation=min, bucket=month, rollup=avg)', '월별(r1 분기별 평균과 대조)'),
    ('r2_bucket', '이번 달 서울 택시 수입을 주별 최댓값으로 구한 다음 그 합계는?', 'get_place_scope(name=서울)\nget_billing_metrics(metric=revenue, scope=$resolve.scope, date=this_month, aggregation=max, bucket=week, rollup=sum)', '주별(r1 하루 단위 합산과 대조)'),
    ('r2_bucket', '작년 달서구 활성 택시 대수를 월별 평균으로 낸 뒤 그 중간값은?', 'get_place_scope(name=달서구, region=대구)\nget_billing_metrics(metric=active_taxi_count, scope=$resolve.scope, date=last_year, aggregation=avg, bucket=month, rollup=med)', '월별(r1 반기별 중간값과 대조)'),
    ('r2_bucket', '2026년 8월부터 9월까지 인천 택시 운행일수를 주별 합계로 낸 뒤 그 중간값은?', 'get_place_scope(name=인천)\nget_billing_metrics(metric=operating_days, scope=$resolve.scope, date=20260801-20260930, aggregation=sum, bucket=week, rollup=med)', '주별(r1 연 단위와 대조)'),  # 2차(1차: 2026년 8월부터 9월까지 인천 택시 운행일수를 주별 합계로 낸 뒤 그 최솟값은?)
    ('r2_bucket', '올해 수영구 택시 수입을 월별 중간값으로 구한 다음 그 합계는?', 'get_place_scope(name=수영구, region=부산)\nget_billing_metrics(metric=revenue, scope=$resolve.scope, date=this_year, aggregation=med, bucket=month, rollup=sum)', '월별(r1 3개월 단위와 대조)'),  # 2차(1차: 올해 부산 동구 택시 수입을 월별 중간값으로 구한 다음 그 합계는?)
    ('r2_bucket', '지난달 대구 중구 택시 가동률을 주별 중간값으로 낸 뒤 그 평균은?', 'get_place_scope(name=중구, region=대구)\nget_billing_metrics(metric=active_taxi_ratio, scope=$resolve.scope, date=last_month, aggregation=med, bucket=week, rollup=avg)', '주별(r1 분기마다 평균과 대조)'),
    ('r2_bucket', '작년 대구 서구 택시 운행일수를 월별 최댓값으로 구하고 그중 최솟값은?', 'get_place_scope(name=서구, region=대구)\nget_billing_metrics(metric=operating_days, scope=$resolve.scope, date=last_year, aggregation=max, bucket=month, rollup=min)', '월별(r1 분기별 최솟값과 대조)'),
    ('r2_bucket', '지난주 요일별 택시 활성 대수 평균을 보여줘', 'get_billing_metrics(metric=active_taxi_count, date=last_week, aggregation=avg, dimension=dayofweek)', '요일별(r1 매시간 단위와 대조)'),
    ('r2_bucket', '지난달 요일별 택시 운행일수 합계가 가장 많은 두 요일은?', 'get_billing_metrics(metric=operating_days, date=last_month, aggregation=sum, dimension=dayofweek, order=top, limit=2)', '요일별 순위(r1 날짜마다와 대조)'),
    ('r2_bucket', '이번 달 요일별 택시 수입 최솟값을 알려줘', 'get_billing_metrics(metric=revenue, date=this_month, aggregation=min, dimension=dayofweek)', '요일별(r1 날마다와 대조)'),
    ('r2_bucket', '지난달 시도별 택시 활성 대수 중간값을 보여줘', 'get_billing_metrics(metric=active_taxi_count, date=last_month, aggregation=med, dimension=sido)', '시도별(r1 시간 단위 집계와 대조)'),
    ('r2_bucket', '올해 시도별 택시 수입 최솟값이 가장 큰 두 곳은?', 'get_billing_metrics(metric=revenue, date=this_year, aggregation=min, dimension=sido, order=top, limit=2)', '시군구별(r1 해마다 비교와 대조)'),  # 2차(1차: 올해 시군구별 택시 수입 합계를 보여줘)
    # 택시라고 밝힌 질문(r1 다른 교통수단과 대조)
    ('r2_mode', '지난달 대구 택시 수입을 주별 합계로 구한 뒤 그 중간값은?', 'get_place_scope(name=대구)\nget_billing_metrics(metric=revenue, scope=$resolve.scope, date=last_month, aggregation=sum, bucket=week, rollup=med)', '택시 수입(r1 도시철도와 대조)'),  # 2차(1차: 지난달 대구 택시 수입의 합계를 주별로 낸 뒤 가장 큰 주의 값은?)
    ('r2_mode', '올해 인천 택시 운행일수를 월별 평균으로 낸 뒤 그 합계는?', 'get_place_scope(name=인천)\nget_billing_metrics(metric=operating_days, scope=$resolve.scope, date=this_year, aggregation=avg, bucket=month, rollup=sum)', '택시 운행일수(r1 시외버스와 대조)'),  # 2차(1차: 올해 인천 택시 운행일수를 월별 평균으로 낸 뒤 그 최솟값은?)
    ('r2_mode', '작년 부산 택시의 활성 대수를 주별 최솟값으로 구하고 그중 가장 큰 값은?', 'get_place_scope(name=부산)\nget_billing_metrics(metric=active_taxi_count, scope=$resolve.scope, date=last_year, aggregation=min, bucket=week, rollup=max)', '택시 활성 대수(r1 화물 트럭과 대조)'),
    ('r2_mode', '지난달 부산 택시들의 가동률을 주 단위 최댓값으로 정리하면 그 중간값은 얼마야?', 'get_place_scope(name=부산)\nget_billing_metrics(metric=active_taxi_ratio, scope=$resolve.scope, date=last_month, aggregation=max, bucket=week, rollup=med)', '택시 가동률(r1 카셰어링과 대조)'),  # 2차(1차: 지난달 서울 택시 가동률을 주별 최솟값으로 낸 뒤 그 중간값은?)
    ('r2_mode', '이번 달 동대구역에서 택시를 타고 출발한 실차가 가장 적게 도착한 H3 셀 두 곳은?', 'get_place_scope(name=동대구역)\nget_trip_count(scope_pickup=$pickup.scope, date=this_month, dimension=h3, dimension_target=dropoff, order=bottom, limit=2)', '택시 실차(r1 SRT와 대조)'),
    ('r2_mode', '지난달 동인동에 택시로 도착한 실차를 출발 동·도착 동 짝으로 묶었을 때 가장 많은 두 쌍은?', 'get_place_scope(name=동인동, region=대구)\nget_trip_count(scope_dropoff=$dropoff.scope, date=last_month, dimension=emd, dimension_target=both, order=top, limit=2)', '택시 실차(r1 관광버스와 대조)'),  # 2차(1차: 지난달 광안리에 택시로 도착한 실차를 출발 동–도착 동 짝으로 묶었을 때 상위 두 쌍은?)
    ('r2_mode', '이번 달 초량동에 택시로 도착한 실차를 출발 시도별로 볼 때 가장 많은 두 곳은?', 'get_place_scope(name=초량동, region=부산)\nget_trip_count(scope_dropoff=$dropoff.scope, date=this_month, dimension=sido, dimension_target=pickup, order=top, limit=2)', '택시 실차(r1 마을버스와 대조)'),
    ('r2_mode', '지난달 태평로동에 택시를 타고 내린 실차를 출발 H3 셀별로 볼 때 가장 많은 두 곳은?', 'get_place_scope(name=태평로동, region=대구)\nget_trip_count(scope_dropoff=$dropoff.scope, date=last_month, dimension=h3, dimension_target=pickup, order=top, limit=2)', '택시 실차(r1 공유 자전거와 대조)'),
    ('r2_mode', '작년 시도별 택시 가동률 최솟값이 가장 작은 두 곳은?', 'get_billing_metrics(metric=active_taxi_ratio, date=last_year, aggregation=min, dimension=sido, order=bottom, limit=2)', '택시 가동률(r1 여객선과 대조)'),  # 2차(1차: 작년 시도별 택시 가동률이 가장 낮은 두 곳은?)
    ('r2_mode', '올해 요일별 택시 활성 대수가 가장 적은 두 요일은?', 'get_billing_metrics(metric=active_taxi_count, date=this_year, dimension=dayofweek, order=bottom, limit=2)', '택시 활성 대수(r1 퍼스널 모빌리티와 대조)'),
]


def main():
    cands, n = [], 0
    for gap, (why, qs) in R1.items():
        for q in qs:
            n += 1
            cands.append({"id": f"b012-{n:03d}", "gap": gap, "kind": "r1_refusal", "question": q, "gold_text": "", "target": '{"unsupported": true}', "rationale": why})
    for gap, q, g, why in R2:
        n += 1
        cands.append({"id": f"b012-{n:03d}", "gap": gap, "kind": "r2_contrast", "question": q, "gold_text": g, "rationale": why})
    doc = {"batch": "batch012", "status": "초안(승인 아님)", "author": "Claude", "date": "2026-10-26", "reference_date": "2026-10-26", "candidates": cands}
    (HERE / "candidates_draft.yaml").write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(len(cands), sum(c["kind"] == "r1_refusal" for c in cands), sum(c["kind"] == "r2_contrast" for c in cands))


if __name__ == "__main__":
    main()
