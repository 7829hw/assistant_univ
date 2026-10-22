# -*- coding: utf-8 -*-
"""refusal_dev 초안(pilot_008 P3, 결정 219): 거부를 따로 재는 **개발 셋**(학습에 쓰지 않음). **승인이 아니다.** Claude가 손으로 적음.

    python3 write_drafts_rdev.py   # -> candidates_draft.yaml

- 쓰임: pilot_008 seed·checkpoint 고르기와 거부 진단. 최종 판정에는 쓰지 않는다.
- batch011과 따로 썼다(문장·장소·구조 조합을 다르게). 겹침 검사(``batch011/build_candidates11.py --set refusal_dev``) 대상에 batch011 초안 전체를 넣는다.
- 보호 셋·개발 셋·n33 문장을 보지 않음. 장소는 mock gazetteer 이름만. 기준일 2026-09-25.
- rdev-051은 1차 문장이 batch011 b011-092와 Jaccard 0.75라 2차로 바꿈(``excluded_round1.json``).
- 거부 30(6범주 × 5, 정답 target ``{"unsupported": true}``) + 근접 대조 30(6묶음 × 5, batch010 빈 구조 중 batch011이 쓰지 않은 조합).
"""
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent

R1 = {
    "rd_metric": ("측정값이 계약 목록에 없음", [
        "지난주 부산 택시 손님들의 평균 탑승 인원은?",
        "이번 달 대구 동구 택시 고장 신고 건수를 알려줘",
        "작년 인천 택시가 쓴 LPG 충전 금액 합계는?",
        "지난달 서울 택시 운전자 피로도 지수 평균은?",
        "올해 수성구 택시 안에서 분실물이 접수된 건수는?",
    ]),
    "rd_bucket": ("묶음 단위가 week·month 밖", [
        "지난주 대구 택시 수입을 하루하루 나눠 합계로 보여줘",
        "작년 인천 택시 운행일수를 3개월 단위로 묶어 평균 내줘",
        "최근 5년간 부산 택시 가동률을 해마다 보여줘",
        "지난주 동대구역 택시 통행량을 10분마다 나눠 알려줘",
        "이번 달 서울 활성 택시 대수를 오전과 오후로 나눠 평균 내줘",
    ]),
    "rd_entity": ("개별 차량·기사·승객·회사 단위", [
        "번호판 끝자리가 7인 택시들의 지난달 운행일수는?",
        "지난주 부산에서 수입이 가장 적었던 택시 기사 세 명은?",
        "이번 달 대구 택시 회사 중 가동률이 가장 높은 곳은?",
        "작년 인천에서 같은 승객이 가장 많이 이용한 택시 번호는?",
        "지난달 광안리에서 탄 손님들의 성별 비율은?",
    ]),
    "rd_forecast": ("미래 값의 예측", [
        "다음 달 대구 수성구 택시 통행량이 얼마나 될지 예측해줘",
        "내일 오후 부산진구 택시 공차율 예상치를 알려줘",
        "내년 인천 택시 수입 증가율을 전망해줘",
        "다가오는 겨울에 서울 택시 가동률이 어떻게 변할지 예측해줘",
        "다음 주 월요일 동대구역 택시 통행량 예측값은?",
    ]),
    "rd_mode": ("택시가 아닌 교통수단", [
        "지난달 대구 도시철도 이용객 수는?",
        "이번 주 부산 마을버스 운행 횟수를 알려줘",
        "작년 인천 택배 차량 통행량은?",
        "지난주 서울 공유 자전거 반납 건수를 보여줘",
        "올해 대구 시외버스 터미널 이용객 수는?",
    ]),
    "rd_domain": ("택시 운행 데이터 분석이 아닌 질문", [
        "다음 주 부산 미세먼지 예보 알려줘",
        "광안리 근처 숙소 추천해줘",
        "대구 수성구에 있는 초등학교 목록 보여줘",
        "서울 택시 면허를 따려면 어떻게 해야 해?",
        "동대구역 열차 시간표를 알려줘",
    ]),
}

P = lambda n, r=None: f"get_place_scope(name={n}" + (f", region={r}" if r else "") + ")\n"  # noqa: E731
BM = "get_billing_metrics"
R2 = [
    ("rdc_metric", "올해 대구 소속 택시 가동률 최솟값은?", P("대구") + f"{BM}(metric=active_taxi_ratio, scope=$resolve.scope, date=this_year, aggregation=min)"),
    ("rdc_metric", "지난달 부산 택시 수입을 주별 최솟값으로 낸 뒤 그 평균은?", P("부산") + f"{BM}(metric=revenue, scope=$resolve.scope, date=last_month, aggregation=min, bucket=week, rollup=avg)"),
    ("rdc_metric", "작년 시도별 택시 운행일수 중간값을 보여줘", f"{BM}(metric=operating_days, date=last_year, aggregation=med, dimension=sido)"),
    ("rdc_metric", "지난달 요일별 택시 수입 최댓값은?", f"{BM}(metric=revenue, date=last_month, aggregation=max, dimension=dayofweek)"),
    ("rdc_metric", "올해 서울 활성 택시 대수를 월별 최솟값으로 낸 뒤 그 평균은?", P("서울") + f"{BM}(metric=active_taxi_count, scope=$resolve.scope, date=this_year, aggregation=min, bucket=month, rollup=avg)"),
    ("rdc_bucket", "작년 대구 택시 운행일수를 주별 평균으로 낸 다음 합계는?", P("대구") + f"{BM}(metric=operating_days, scope=$resolve.scope, date=last_year, aggregation=avg, bucket=week, rollup=sum)"),
    ("rdc_bucket", "올해 인천 택시 수입을 월별 합계로 낸 뒤 그 합계들을 다시 더하면?", P("인천") + f"{BM}(metric=revenue, scope=$resolve.scope, date=this_year, aggregation=sum, bucket=month, rollup=sum)"),
    ("rdc_bucket", "지난달 부산 택시 가동률을 주별 중간값으로 낸 다음 그 평균은?", P("부산") + f"{BM}(metric=active_taxi_ratio, scope=$resolve.scope, date=last_month, aggregation=med, bucket=week, rollup=avg)"),
    ("rdc_bucket", "작년 서울 활성 택시 대수를 월별 최댓값으로 낸 뒤 그중 최솟값은?", P("서울") + f"{BM}(metric=active_taxi_count, scope=$resolve.scope, date=last_year, aggregation=max, bucket=month, rollup=min)"),
    ("rdc_bucket", "지난달 요일별 택시 운행일수 합계를 보여줘", f"{BM}(metric=operating_days, date=last_month, aggregation=sum, dimension=dayofweek)"),
    ("rdc_entity", "지난주 광안동에서 나간 실차가 도착한 H3 셀별 건수는?", P("광안동", "부산") + "get_trip_count(scope_pickup=$pickup.scope, date=last_week, dimension=h3, dimension_target=dropoff)"),
    ("rdc_entity", "지난주 동인동에 도착한 실차를 출발 시도별로 보여줘", P("동인동", "대구") + "get_trip_count(scope_dropoff=$dropoff.scope, date=last_week, dimension=sido, dimension_target=pickup)"),
    ("rdc_entity", "지난주 중앙로동으로 들어온 실차를 출발 H3 셀 기준으로 볼 때 가장 적은 두 곳은?", P("중앙로동", "대구") + "get_trip_count(scope_dropoff=$dropoff.scope, date=last_week, dimension=h3, dimension_target=pickup, order=bottom, limit=2)"),
    ("rdc_entity", "작년 시도별 활성 택시 대수 최댓값이 가장 작은 두 곳은?", f"{BM}(metric=active_taxi_count, date=last_year, aggregation=max, dimension=sido, order=bottom, limit=2)"),
    ("rdc_entity", "올해 시도별 택시 가동률 평균이 가장 높은 두 곳은?", f"{BM}(metric=active_taxi_ratio, date=this_year, aggregation=avg, dimension=sido, order=top, limit=2)"),
    ("rdc_forecast", "지난달 대구 택시 수입을 월별 최솟값으로 본 뒤 그중 가장 큰 값은?", P("대구") + f"{BM}(metric=revenue, scope=$resolve.scope, date=last_month, aggregation=min, bucket=month, rollup=max)"),
    ("rdc_forecast", "작년 부산 택시 운행일수를 주별 최댓값으로 낸 뒤 그 합계는?", P("부산") + f"{BM}(metric=operating_days, scope=$resolve.scope, date=last_year, aggregation=max, bucket=week, rollup=sum)"),
    ("rdc_forecast", "지난달 인천 택시 가동률을 월별 최댓값으로 낸 뒤 그 중간값은?", P("인천") + f"{BM}(metric=active_taxi_ratio, scope=$resolve.scope, date=last_month, aggregation=max, bucket=month, rollup=med)"),
    ("rdc_forecast", "작년 요일별 활성 택시 대수 중간값을 알려줘", f"{BM}(metric=active_taxi_count, date=last_year, aggregation=med, dimension=dayofweek)"),
    ("rdc_forecast", "지난주 요일별 택시 수입 합계가 가장 많은 두 요일은?", f"{BM}(metric=revenue, date=last_week, aggregation=sum, dimension=dayofweek, order=top, limit=2)"),
    ("rdc_mode", "지난주 두산동이 목적지였던 택시 실차가 주로 출발한 시도 상위 두 곳을 알려줘", P("두산동", "대구") + "get_trip_count(scope_dropoff=$dropoff.scope, date=last_week, dimension=sido, dimension_target=pickup, order=top, limit=2)"),
    ("rdc_mode", "지난주 초량동으로 들어온 택시 실차를 출발 H3 셀로 나눠 가장 많은 두 곳은?", P("초량동", "부산") + "get_trip_count(scope_dropoff=$dropoff.scope, date=last_week, dimension=h3, dimension_target=pickup, order=top, limit=2)"),
    ("rdc_mode", "지난주 중앙로동에서 탄 택시 실차의 도착 H3 셀 중 가장 많은 두 곳은?", P("중앙로동", "대구") + "get_trip_count(scope_pickup=$pickup.scope, date=last_week, dimension=h3, dimension_target=dropoff, order=top, limit=2)"),
    ("rdc_mode", "지난주 수성구에 도착한 택시 실차를 출발 시도별로 세어줘", P("수성구", "대구") + "get_trip_count(scope_dropoff=$dropoff.scope, date=last_week, dimension=sido, dimension_target=pickup)"),
    ("rdc_mode", "지난주 달서구에서 탄 택시 실차를 출발·도착 동 쌍으로 나눠 보여줘", P("달서구", "대구") + "get_trip_count(scope_pickup=$pickup.scope, date=last_week, dimension=emd, dimension_target=both)"),
    ("rdc_domain", "올해 시도별 택시 운행일수 평균이 가장 낮은 두 곳은?", f"{BM}(metric=operating_days, date=this_year, aggregation=avg, dimension=sido, order=bottom, limit=2)"),
    ("rdc_domain", "지난달 요일별 택시 가동률 중간값을 보여줘", f"{BM}(metric=active_taxi_ratio, date=last_month, aggregation=med, dimension=dayofweek)"),
    ("rdc_domain", "작년 시도별 택시 수입 중간값이 가장 높은 두 곳은?", f"{BM}(metric=revenue, date=last_year, aggregation=med, dimension=sido, order=top, limit=2)"),
    ("rdc_domain", "지난주 부산진구로 들어온 실차를 출발 동별로 보여줘", P("부산진구") + "get_trip_count(scope_dropoff=$dropoff.scope, date=last_week, dimension=emd, dimension_target=pickup)"),
    ("rdc_domain", "이번 달 요일별 활성 택시 대수 최솟값이 가장 큰 두 요일은?", f"{BM}(metric=active_taxi_count, date=this_month, aggregation=min, dimension=dayofweek, order=top, limit=2)"),
]


def main():
    cands, n = [], 0
    for gap, (why, qs) in R1.items():
        for q in qs:
            n += 1
            cands.append({"id": f"rdev-{n:03d}", "gap": gap, "kind": "r1_refusal", "question": q, "gold_text": "", "target": '{"unsupported": true}', "rationale": why})
    for gap, q, g in R2:
        n += 1
        cands.append({"id": f"rdev-{n:03d}", "gap": gap, "kind": "r2_contrast", "question": q, "gold_text": g, "rationale": "근접 대조(지원되는 질문, batch010 빈 구조)"})
    doc = {"set": "refusal_dev", "status": "초안(승인 아님, 개발 셋 — 학습에 쓰지 않음)", "author": "Claude", "date": "2026-10-22", "reference_date": "2026-09-25", "candidates": cands}
    (HERE / "candidates_draft.yaml").write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(len(cands))


if __name__ == "__main__":
    main()
