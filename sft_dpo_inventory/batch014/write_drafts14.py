# -*- coding: utf-8 -*-
"""batch014 초안(결정 263 D5, ablation_013): 근접 대조 보강 + OD 상위 N. **승인이 아니다.** Claude가 손으로 적음. 학습에 쓰지 않는다(승인은 사용자가 세션 뒤에).

    python3 write_drafts14.py   # -> candidates_draft.yaml

- 대상은 ``ablation_012/CONTRAST_PLAN_DRAFT.md``의 서명 수준 정보(tool·metric·aggregation·시간 단위·지역 유형)로만 정했다. CT10K·H-dev·E1·H-final의 문항 원문·template 문장은
  열지 않았고 흉내 내지 않았다. 문체는 batch012·013 초안과 같다. 장소는 mock gazetteer 이름만(시도 4·시군구 8·읍면동 10·POI 5). 기준일 2026-10-26(월).
- 구조는 ``free_structures14.json``(보호 넷·selection_v1·확장·thor family 밖이고 현재 코드가 답하는 구조)에서만 골랐다.
  - **T1·T2(운행 요금 × 시도·없음·시군구) = 0문항**: 운행 요금(`get_trip_metrics fare`)은 장소 없음·시도·시군구의 모든 aggregation 구조가 보호 넷(selection_v2·holdout·valid98·aux_test_v1)·
    selection_v1·확장·thor family에 걸린다(72/72). 결정 120에 따라 쓸 수 없다.
  - **T1v(대체, 지시 범위 밖) 12**: 운행 요금 × POI 주변(``include_vicinity``) × aggregation{avg, med, min, max} × 시간{일, 기간, 주}. family에 vicinity가 들어가 막히지 않는
    유일한 운행 요금 구조다. T1–T5 서명(분석의 서명 분리)에는 들지 않는다(지역 유형 POI). 승인 때 따로 고를 수 있게 묶음을 나눴다.
  - T3 16: 요금 지표 revenue·active_taxi_count·active_taxi_ratio. 장소 있는 시도(빈 구조 = 활성 대수 max·med, 가동률 min·med) 6, 장소 없는 시도·요일 차원 10.
    batch013 c1에 같은 family가 많아(차원·일 단위 집계) 하한으로 썼고, batch013에 없던 하루 날짜·다른 장소 조합을 골랐다.
  - T4 6: 실차 건수 × 하루 × POI 주변 **도착**(빈 구조는 도착 끝 POI뿐; 장소 없음·출발 POI는 막힘).
  - T5 12(근접 대조 아님, 일반 답하는 문항): OD 상위 N — 출발·도착 끝 × dimension × dimension_target × order, limit 2–5. 승인 corpus에 OD 상위 N 정답 문항 26개가 V4에서
    빠져 있어(유형 상한 C-1 등, README 4절) 하한으로 썼다.
- T1v·T3·T4는 문항마다 "짝지을 거부 패턴"을 ``pair_refusal_memo``(메모 열)에 적었다. teacher 입력에는 넣지 않는다(결정 248). ``gap``은 batch011–013과 같은 이름(가까운 거부 범주).
- 2차: 1차 검사(``excluded_round1.json``)에서 빠진 20(연도 없는 날짜 → DATE_AMBIGUOUS 18, Jaccard ≥ 0.5 2: RC5·pg-b006-29, batch013 b013-070)을 고쳤다. 줄 끝 주석에 1차 문장.
- 거부 패턴(``pilot_009/protected_final_v2_pc_patterns.md``) 조합은 쓰지 않았다: 통행 지표에 택시 유형(P-1), 요금 지표의 장소와 시도 차원을 함께(P-a), 장소 없는 H3 요금 차원(P-b),
  통행 건수에 택시 유형(P-h)·월 묶음(P-e), 요금 지표에 운행 상태(P-i), 묶음·rollup 관련 C 패턴(묶음 없음).
"""
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent


def pc(place, region=None, vicinity=False):
    return f"get_place_scope(name={place}" + (f", region={region}" if region else "") + (", include_vicinity=true" if vicinity else "") + ")"


def fare(place, date, agg):
    return pc(place, vicinity=True) + f"\nget_trip_metrics(metric=fare, scope=$resolve.scope, date={date}, aggregation={agg})"


def bill(args, place=None):
    if place:
        return pc(place) + f"\nget_billing_metrics({args.replace('SCOPE', 'scope=$resolve.scope')})"
    return f"get_billing_metrics({args})"


def tc_drop(place, date, time=None):
    return pc(place, vicinity=True) + f"\nget_trip_count(scope_dropoff=$dropoff.scope, date={date}" + (f", time={time}" if time else "") + ")"


#: (묶음, 유형, gap, 질문, 정답 호출, 짝지을 거부 패턴 메모)
T1V = [
    ("T1v", "fare_day", "r2_entity", "2026년 10월 14일 동대구역 주변 택시 요금의 평균은 얼마였어?",
     fare("동대구역", "20261014", "avg"), "기사별 요금(개별 단위)"),
    ("T1v", "fare_day", "r2_metric", "2026년 10월 3일 광안리 근처 택시 요금 중간값을 알려줘",
     fare("광안리", "20261003", "med"), "팁·할증 내역(계약에 없는 요금 항목)"),  # 2차(1차: 10월 3일 광안리 근처 택시 요금 중간값을 알려줘)
    ("T1v", "fare_day", "r2_entity", "2026년 10월 20일 동성로 일대 택시 요금 가운데 가장 낮은 금액은?",
     fare("동성로", "20261020", "min"), "차량별 최저 요금(개별 단위)"),
    ("T1v", "fare_day", "r2_forecast", "2026년 10월 7일 어린이대공원 주변 택시 요금 최댓값은?",
     fare("어린이대공원", "20261007", "max"), "다음 날 요금 예측"),  # 2차(1차: 10월 7일 어린이대공원 주변 택시 요금 최댓값은?)
    ("T1v", "fare_period", "r2_forecast", "2026년 10월 1일부터 10일까지 광안리 근처 택시 평균 요금은?",
     fare("광안리", "20261001-20261010", "avg"), "다음 주 평균 요금 예측"),
    ("T1v", "fare_period", "r2_entity", "2026년 9월 15일부터 24일까지 동대구역 주변 택시 요금의 중간값은?",
     fare("동대구역", "20260915-20260924", "med"), "기사별 요금 중간값(개별 단위)"),  # 2차(1차: 9월 15일부터 24일까지 동대구역 주변 택시 요금의 중간값은?)
    ("T1v", "fare_period", "r2_metric", "2026년 9월 21일부터 9월 30일까지 어린이대공원 근처 택시 요금 최솟값을 보여줘",
     fare("어린이대공원", "20260921-20260930", "min"), "심야 할증 요금만 따로(지표 밖)"),
    ("T1v", "fare_period", "r2_entity", "2026년 10월 8일부터 16일까지 동성로 주변 택시 요금이 가장 높았던 금액은?",
     fare("동성로", "20261008-20261016", "max"), "요금을 가장 많이 받은 기사(개별 단위)"),  # 2차(1차: 10월 8일부터 10월 16일까지 동성로 주변 택시 요금이 가장 높았던 금액은?)
    ("T1v", "fare_week", "r2_metric", "지난주 동성로 근처 택시 요금 평균을 알려줘",
     fare("동성로", "last_week", "avg"), "카드·현금 결제 수단별 요금(지표 밖)"),
    ("T1v", "fare_week", "r2_forecast", "2026년 10월 5일부터 11일까지 한 주 동안 광안리 주변 택시 요금 중간값은?",
     fare("광안리", "20261005-20261011", "med"), "다음 주 요금 중간값 예측"),
    ("T1v", "fare_week", "r2_entity", "지난주 동대구역 일대 택시 요금 최댓값은 얼마야?",
     fare("동대구역", "last_week", "max"), "승객별 최고 요금(개별 단위)"),
    ("T1v", "fare_week", "r2_metric", "2026년 10월 12일부터 18일까지 어린이대공원 근처 택시 요금 중 제일 싼 금액은?",
     fare("어린이대공원", "20261012-20261018", "min"), "통행료 포함 요금(지표 밖)"),  # 2차(1차: 10월 12일부터 18일까지 어린이대공원 근처 택시 요금 중 제일 싼 금액은?)
]

T3 = [
    # 장소 있는 시도(빈 구조: 활성 대수 max·med, 가동률 min·med)
    ("T3", "sido_place", "r2_entity", "지난달 서울 활성 택시 대수가 가장 많았던 날은 몇 대였어?",
     bill("metric=active_taxi_count, SCOPE, date=last_month, aggregation=max", "서울"), "회사별 활성 대수(개별 단위)"),
    ("T3", "sido_place", "r2_bucket", "2026년 8월 인천 활성 택시 대수를 날마다 놓고 본 중간값은?",
     bill("metric=active_taxi_count, SCOPE, date=20260801-20260831, aggregation=med", "인천"), "분기 단위 묶음(지원 안 하는 묶음)"),
    ("T3", "sido_place", "r2_bucket", "2026년 9월 1일부터 20일까지 부산 택시 가동률의 하루 최저치는?",
     bill("metric=active_taxi_ratio, SCOPE, date=20260901-20260920, aggregation=min", "부산"), "시간대별 가동률(지원 안 하는 단위)"),  # 2차(1차: 9월 1일부터 20일까지 부산 택시 가동률의 하루 최저치는?)
    ("T3", "sido_place", "r2_forecast", "지난주 대구 택시 가동률 중간값을 알려줘",
     bill("metric=active_taxi_ratio, SCOPE, date=last_week, aggregation=med", "대구"), "이번 주 가동률 전망(예측)"),
    ("T3", "sido_place", "r2_entity", "2026년 10월 1일부터 15일까지 대구에서 하루 활성 택시가 가장 많았던 때의 대수는?",
     bill("metric=active_taxi_count, SCOPE, date=20261001-20261015, aggregation=max", "대구"), "차량 번호별 운행 여부(개별 단위)"),  # 2차(1차: 10월 1일부터 15일까지 대구에서 하루 활성 택시가 가장 많았던 때의 대수는?)
    ("T3", "sido_place", "r2_forecast", "지난달 서울 택시 가동률이 제일 낮았던 날의 값은?",
     bill("metric=active_taxi_ratio, SCOPE, date=last_month, aggregation=min", "서울"), "다음 달 최저 가동률 예측"),
    # 장소 없는 시도·요일 차원
    ("T3", "dim_sido", "r2_entity", "2026년 10월 14일 하루 시도별 택시 평균 수입을 보여줘",
     bill("metric=revenue, date=20261014, aggregation=avg, dimension=sido"), "기사 한 사람당 수입(개별 단위)"),
    ("T3", "dim_sido", "r2_entity", "2026년 10월 20일 택시 수입 최댓값이 높은 시도 두 곳은?",
     bill("metric=revenue, date=20261020, aggregation=max, dimension=sido, order=top, limit=2"), "수입이 가장 많은 회사(개별 단위)"),  # 2차(1차: 10월 20일 택시 수입 최댓값이 높은 시도 두 곳은?)
    ("T3", "dim_sido", "r2_forecast", "지난달 택시 수입 최솟값이 큰 시도 세 곳을 알려줘",
     bill("metric=revenue, date=last_month, aggregation=min, dimension=sido, order=top, limit=3"), "다음 달 시도별 수입 전망(예측)"),
    ("T3", "dim_dow", "r2_bucket", "지난달 요일별 택시 수입 중간값이 높은 세 요일은?",
     bill("metric=revenue, date=last_month, aggregation=med, dimension=dayofweek, order=top, limit=3"), "시간대별 수입(지원 안 하는 단위)"),
    ("T3", "dim_sido", "r2_entity", "2026년 10월 7일 시도별 활성 택시 대수 중간값은?",
     bill("metric=active_taxi_count, date=20261007, aggregation=med, dimension=sido"), "회사별 활성 대수(개별 단위)"),  # 2차(1차: 10월 7일 시도별 활성 택시 대수 중간값은?)
    ("T3", "dim_dow", "r2_bucket", "지난달 활성 택시 대수의 하루 최솟값이 가장 큰 두 요일은?",
     bill("metric=active_taxi_count, date=last_month, aggregation=min, dimension=dayofweek, order=top, limit=2"), "주차별 나눔(지원 안 하는 묶음)"),
    ("T3", "dim_sido", "r2_entity", "2026년 10월 21일 활성 택시가 가장 많은 시도 세 곳은?",
     bill("metric=active_taxi_count, date=20261021, dimension=sido, order=top, limit=3"), "활성 차량이 가장 많은 회사(개별 단위)"),
    ("T3", "dim_sido", "r2_forecast", "2026년 9월 30일 택시 가동률 평균이 높은 시도 두 곳은?",
     bill("metric=active_taxi_ratio, date=20260930, aggregation=avg, dimension=sido, order=top, limit=2"), "내일 시도별 가동률 예측"),  # 2차(1차: 9월 30일 택시 가동률 평균이 높은 시도 두 곳은?)
    ("T3", "dim_dow", "r2_bucket", "지난달 요일별 택시 가동률 최고치가 높은 두 요일은?",
     bill("metric=active_taxi_ratio, date=last_month, aggregation=max, dimension=dayofweek, order=top, limit=2"), "월초·월말 나눔(지원 안 하는 묶음)"),
    ("T3", "dim_sido", "r2_entity", "2026년 10월 13일 시도별 택시 가동률 중간값을 알려줘",
     bill("metric=active_taxi_ratio, date=20261013, aggregation=med, dimension=sido"), "가동률이 중간인 회사(개별 단위)"),  # 2차(1차: 10월 13일 시도별 택시 가동률 중간값을 알려줘)
]

T4 = [
    ("T4", "poi_drop_day", "r2_domain", "2026년 10월 14일 동대구역 근처에 내린 실차는 몇 건이야?",
     tc_drop("동대구역", "20261014"), "출퇴근 목적 통행만(통행 목적, 계약 밖 요인)"),
    ("T4", "poi_drop_day", "r2_entity", "2026년 10월 20일 아침 7시부터 9시까지 광안리 주변에 도착한 실차 건수는?",
     tc_drop("광안리", "20261020", "070000-090000"), "승객 연령대별 건수(승객 속성)"),  # 2차(1차: 10월 20일 아침 7시부터 9시까지 광안리 주변에 도착한 실차 건수는?)
    ("T4", "poi_drop_day", "r2_entity", "2026년 10월 3일 어린이대공원 근처에서 하차한 택시 실차 건수를 알려줘",
     tc_drop("어린이대공원", "20261003"), "동반 승객 수별 건수(승객 속성)"),  # 2차(1차: 10월 3일 어린이대공원 근처에서 하차한 택시 실차 건수를 알려줘)
    ("T4", "poi_drop_day", "r2_domain", "2026년 9월 30일 저녁 6시부터 8시 사이 동성로 일대로 들어온 실차는 몇 건?",
     tc_drop("동성로", "20260930", "180000-200000"), "관광객 통행만(통행 목적)"),  # 2차(1차: 9월 30일 저녁 6시부터 8시 사이 동성로 일대로 들어온 실차는 몇 건?)
    ("T4", "poi_drop_day", "r2_entity", "2026년 10월 21일 동대구역 주변에서 내린 택시 실차 수를 보여줘",
     tc_drop("동대구역", "20261021"), "짐을 실은 승객의 통행(승객 속성)"),
    ("T4", "poi_drop_day", "r2_domain", "2026년 10월 9일 밤 8시부터 11시까지 광안리 근처에 도착한 실차 건수는?",
     tc_drop("광안리", "20261009", "200000-230000"), "귀가 목적 통행만(통행 목적)"),  # 2차(1차: 10월 9일 밤 8시부터 11시까지 광안리 근처에 도착한 실차 건수는?)
]

TC = "get_trip_count({})"
T5 = [
    ("T5", "od_none", "general", "지난주 실차가 가장 많이 출발한 시도 세 곳은?",
     TC.format("date=last_week, dimension=sido, dimension_target=pickup, order=top, limit=3"), None),
    ("T5", "od_none", "general", "지난달 실차 도착이 가장 적었던 시도 두 곳은?",
     TC.format("date=last_month, dimension=sido, dimension_target=dropoff, order=bottom, limit=2"), None),
    ("T5", "od_none", "general", "2026년 10월 14일 실차가 가장 많이 도착한 H3 셀 다섯 곳을 알려줘",
     TC.format("date=20261014, dimension=h3, dimension_target=dropoff, order=top, limit=5"), None),  # 2차(1차: 10월 14일 실차가 가장 많이 도착한 H3 셀 다섯 곳을 알려줘)
    ("T5", "od_none", "general", "2026년 10월 1일부터 7일까지 출발 셀과 도착 셀 짝으로 실차가 많은 상위 세 짝은?",
     TC.format("date=20261001-20261007, dimension=h3, dimension_target=both, order=top, limit=3"), None),
    ("T5", "od_none", "general", "지난주 실차의 출발 읍면동과 도착 읍면동 짝 가운데 가장 적은 두 짝은?",
     TC.format("date=last_week, dimension=emd, dimension_target=both, order=bottom, limit=2"), None),
    ("T5", "od_pickup", "general", "지난달 대구에서 출발한 실차가 가장 적게 도착한 시도 두 곳은?",
     pc("대구") + "\n" + TC.format("scope_pickup=$pickup.scope, date=last_month, dimension=sido, dimension_target=dropoff, order=bottom, limit=2"), None),
    ("T5", "od_pickup", "general", "2026년 10월 20일 부산에서 출발한 실차를 출발 시군구와 도착 시군구 짝으로 볼 때 가장 적은 세 짝은?",
     pc("부산") + "\n" + TC.format("scope_pickup=$pickup.scope, date=20261020, dimension=sigungu, dimension_target=both, order=bottom, limit=3"), None),  # 2차(1차: 10월 20일 부산에서 출발한 실차를 출발 시군구와 도착 시군구 짝으로 볼 때 가장 적은 세 짝은?)
    ("T5", "od_pickup", "general", "지난주 대구 수성구를 출발지로 한 실차의 도착 H3 셀을 많은 순으로 세 곳 보여줘",
     pc("수성구", "대구") + "\n" + TC.format("scope_pickup=$pickup.scope, date=last_week, dimension=h3, dimension_target=dropoff, order=top, limit=3"), None),  # 2차(1차: 지난주 수성구에서 출발한 실차가 가장 많이 도착한 H3 셀 세 곳은?)
    ("T5", "od_dropoff", "general", "지난달 서울로 들어온 실차는 어느 시도에서 가장 많이 출발했는지 두 곳 알려줘",
     pc("서울") + "\n" + TC.format("scope_dropoff=$dropoff.scope, date=last_month, dimension=sido, dimension_target=pickup, order=top, limit=2"), None),  # 2차(1차: 지난달 서울에 도착한 실차가 가장 많이 출발한 시도 두 곳은?)
    ("T5", "od_dropoff", "general", "2026년 10월 7일 부산으로 들어온 실차를 도착 시군구별로 셌을 때 많은 세 곳은?",
     pc("부산") + "\n" + TC.format("scope_dropoff=$dropoff.scope, date=20261007, dimension=sigungu, dimension_target=dropoff, order=top, limit=3"), None),  # 2차(1차: 10월 7일 부산으로 들어온 실차를 도착 시군구별로 셌을 때 많은 세 곳은?)
    ("T5", "od_dropoff", "general", "2026년 9월 22일부터 28일까지 대구 중구에 도착한 실차가 가장 적게 출발한 H3 셀 두 곳은?",
     pc("중구", "대구") + "\n" + TC.format("scope_dropoff=$dropoff.scope, date=20260922-20260928, dimension=h3, dimension_target=pickup, order=bottom, limit=2"), None),
    ("T5", "od_both", "general", "지난주 수성구에서 출발해 부산에 도착한 실차의 출발 H3 셀 상위 세 곳은?",
     pc("수성구", "대구") + "\n" + pc("부산") + "\n" + TC.format("scope_pickup=$pickup.scope, scope_dropoff=$dropoff.scope, date=last_week, dimension=h3, dimension_target=pickup, order=top, limit=3"), None),
]


def main():
    rows = T1V + T3 + T4 + T5
    assert (len(T1V), len(T3), len(T4), len(T5)) == (12, 16, 6, 12)
    cands = []
    for n, (grp, sub, gap, q, g, memo) in enumerate(rows, 1):
        cands.append({"id": f"b014-{n:03d}", "group": grp, "subtype": sub, "gap": gap, "kind": "general_answer" if grp == "T5" else "r2_contrast",
                      "question": q, "gold_text": g, "pair_refusal_memo": memo})
    doc = {"set": "batch014", "status": "draft (승인 아님, 결정 263; 학습에 쓰지 않음)", "base_date": "2026-10-26", "candidates": cands}
    (HERE / "candidates_draft.yaml").write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False, width=200), encoding="utf-8")
    from collections import Counter
    print(len(cands), Counter(c["group"] for c in cands), Counter(c["gap"] for c in cands))


if __name__ == "__main__":
    main()
