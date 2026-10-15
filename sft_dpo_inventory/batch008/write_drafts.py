# -*- coding: utf-8 -*-
"""batch008 초안(Claude, 2026-10-15, pilot_006 준비 W7b). 질문·정답 호출·근거는 여기 손으로 적었다. **승인이 아니다.**

    python sft_dpo_inventory/batch008/write_drafts.py  # -> candidates_draft.yaml

계획서 v2 6.4절과 300문항 v2 xlsx `보강_필요` 시트의 공백 가운데 넷(지시 W7b):
- g1 순위 없는 dimension_target(8): 실차 건수를 승차·하차 끝으로 묶되 순위(order/limit)가 없다. "순위 질문이면 dt" 지름길을 막는다.
- g2 implicit endpoint 동사형 dimension_target(10): "태운 곳", "내려준 곳", "내린 곳", "차에 오른 곳"처럼 승차·하차·출발·도착이라는 말 없이 끝을 표현한다.
- g3 value 없는 place 대조(8 = 4쌍): 답이 장소 이름인 질문(scope 이름 조회, value 없는 place가 측정값)과, "어디야"로 묻지만 실제로는
  묶음 단위 순위인 질문(장소 개념 없이 dimension + order). Partial 구조 회귀(value 없는 place를 measure로 읽음, MULTIPLE_MEASURES) 대응.
- g4 bucket ↔ dimension 대조쌍(6쌍 = 12): 같은 지표·기간에서 "주별·월별로 집계한 뒤 다시 집계"(bucket + rollup)와 "요일별·지역별"(dimension)만 다르다.
  bucket은 get_billing_metrics만 받고, 이 tool은 scope와 dimension을 함께 쓰지 못하므로 두 질문 모두 장소 없이 썼다.
원칙: 보호 셋(업체 100, selection_v1·v2, valid98, aux_test_v1), n33, 300문항 문장을 보거나 바꿔 쓰지 않고 새로 썼다. partial-grounding batch006 Gap A의
"손님을 태운 위치" 표현은 피했다. 장소는 mock gazetteer에 있는 이름만 썼다. 주변(vicinity)과 dimension을 함께 쓰는 문항은 현재 코드가 거부하므로 쓰지 않았다.
정답은 업체 형식 Tool 호출로 적고, grounding은 그 호출에서 역산한다(``evaluate_vendor100.derive_grounding``). 기준일 2026-09-25.
"""
from pathlib import Path

import yaml

C = []


def add(n, gap, group, q, calls, why):
    C.append({"id": f"b008-{n:02d}", "gap": gap, "group": group, "question": q, "gold_text": "\n".join(calls), "rationale": why})


DT = "실차 건수(trip_count). 장소가 제한하는 끝=od_role(scope_pickup/scope_dropoff), 묶는 끝=dimension_target. "
NORANK = "순위·개수 제한이 없으므로 order·limit 없음. "
# ---- g1: 순위 없는 dimension_target
add(1, "g1_dt_no_rank", "g1", "지난주 대구 중구에서 출발한 실차 이동 건수를 도착한 읍면동별로 보여줘",
    ["get_place_scope(name=중구, region=대구)", "get_trip_count(scope_pickup=$pickup.scope, date=last_week, dimension=emd, dimension_target=dropoff)"],
    DT + "중구 출발=pickup, 도착한 읍면동별=dropoff로 묶음. " + NORANK)
add(2, "g1_dt_no_rank", "g1", "이번 달 부산 수영구에 도착한 실차 건수를 출발 시군구별로 나눠줘",
    ["get_place_scope(name=수영구, region=부산)", "get_trip_count(scope_dropoff=$dropoff.scope, date=this_month, dimension=sigungu, dimension_target=pickup)"],
    DT + "수영구 도착=dropoff, 출발 시군구별=pickup으로 묶음. " + NORANK)
add(3, "g1_dt_no_rank", "g1", "2026년 9월 1일부터 7일까지 대구 달서구에서 승차한 실차 건수를 승차 H3 셀별로 알려줘",
    ["get_place_scope(name=달서구, region=대구)", "get_trip_count(scope_pickup=$pickup.scope, date=20260901-20260907, dimension=h3, dimension_target=pickup)"],
    DT + "달서구 승차=pickup, 승차 H3별=pickup. " + NORANK)
add(4, "g1_dt_no_rank", "g1", "주말 동안 부산진구로 들어온 실차 이동을 하차 읍면동 기준으로 세어줘",
    ["get_place_scope(name=부산진구, region=부산)", "get_trip_count(scope_dropoff=$dropoff.scope, date=weekend, dimension=emd, dimension_target=dropoff)"],
    DT + "부산진구로 들어온=dropoff, 하차 읍면동 기준=dropoff. " + NORANK)
add(5, "g1_dt_no_rank", "g1", "평일 오전 7시부터 9시까지 대구 수성구 출발 실차 건수를 출발 읍면동별로 정리해줘",
    ["get_place_scope(name=수성구, region=대구)",
     "get_trip_count(scope_pickup=$pickup.scope, date=weekday, time=070000-090000, dimension=emd, dimension_target=pickup)"],
    DT + "수성구 출발=pickup, 출발 읍면동별=pickup. " + NORANK)
add(6, "g1_dt_no_rank", "g1", "지난달 인천에서 끝난 실차 운행 건수를 하차 시군구별로 보여줘",
    ["get_place_scope(name=인천)", "get_trip_count(scope_dropoff=$dropoff.scope, date=last_month, dimension=sigungu, dimension_target=dropoff)"],
    DT + "인천에서 끝난=dropoff, 하차 시군구별=dropoff. " + NORANK)
add(7, "g1_dt_no_rank", "g1", "2026년 9월 20일 대구 동구에서 태워 부산으로 간 실차 건수를 하차 읍면동별로 보여줘",
    ["get_place_scope(name=동구, region=대구)", "get_place_scope(name=부산)",
     "get_trip_count(scope_pickup=$pickup.scope, scope_dropoff=$dropoff.scope, date=20260920, dimension=emd, dimension_target=dropoff)"],
    DT + "대구 동구에서 태워=pickup, 부산으로 간=dropoff, 하차 읍면동별=dropoff(od 둘 중 하나로 묶음). " + NORANK)
add(8, "g1_dt_no_rank", "g1", "이번 주 서울에서 출발한 실차 이동 건수를 출발지 H3 기준으로 묶어줘",
    ["get_place_scope(name=서울)", "get_trip_count(scope_pickup=$pickup.scope, date=this_week, dimension=h3, dimension_target=pickup)"],
    DT + "서울 출발=pickup, 출발지 H3 기준=pickup. " + NORANK)
# ---- g2: implicit endpoint 동사형
IMP = "승차·하차·출발·도착이라는 말이 없다. 손님을 태운 곳=승차 끝(pickup), 내려준·내린 곳=하차 끝(dropoff). 건수이므로 trip_count. "
add(9, "g2_implicit_endpoint", "g2", "지난주 대구에서 손님을 태운 곳을 읍면동별로 세어줘",
    ["get_place_scope(name=대구)", "get_trip_count(scope_pickup=$pickup.scope, date=last_week, dimension=emd, dimension_target=pickup)"],
    IMP + "대구에서 태운=pickup, 태운 곳 읍면동별=pickup.")
add(10, "g2_implicit_endpoint", "g2", "이번 달 부산에서 손님을 내려준 곳을 시군구별로 보여줘",
    ["get_place_scope(name=부산)", "get_trip_count(scope_dropoff=$dropoff.scope, date=this_month, dimension=sigungu, dimension_target=dropoff)"],
    IMP + "부산에서 내려준=dropoff, 내려준 곳 시군구별=dropoff.")
add(11, "g2_implicit_endpoint", "g2", "주말 동안 손님을 가장 많이 태운 H3 셀 5곳은?",
    ["get_trip_count(date=weekend, dimension=h3, dimension_target=pickup, order=top, limit=5)"],
    IMP + "장소 제한 없음. 태운 곳=pickup으로 H3 묶음, 상위 5.")
add(12, "g2_implicit_endpoint", "g2", "평일 저녁 6시부터 9시까지 손님을 내려준 곳이 가장 적은 읍면동 3곳은?",
    ["get_trip_count(date=weekday, time=180000-210000, dimension=emd, dimension_target=dropoff, order=bottom, limit=3)"],
    IMP + "내려준 곳=dropoff로 읍면동 묶음, 하위 3.")
add(13, "g2_implicit_endpoint", "g2", "지난달 대구 수성구에서 태운 손님을 내려준 곳을 시군구별로 알려줘",
    ["get_place_scope(name=수성구, region=대구)", "get_trip_count(scope_pickup=$pickup.scope, date=last_month, dimension=sigungu, dimension_target=dropoff)"],
    IMP + "수성구에서 태운=pickup(장소 제한), 내려준 곳으로 묶음=dropoff(od_role ≠ dimension_target).")
add(14, "g2_implicit_endpoint", "g2", "2026년 9월 1일부터 15일까지 부산 수영구에 내려준 손님을 어디서 태웠는지 읍면동별로 보여줘",
    ["get_place_scope(name=수영구, region=부산)", "get_trip_count(scope_dropoff=$dropoff.scope, date=20260901-20260915, dimension=emd, dimension_target=pickup)"],
    IMP + "수영구에 내려준=dropoff(장소 제한), 어디서 태웠는지=pickup으로 묶음.")
add(15, "g2_implicit_endpoint", "g2", "이번 주 서울에서 손님이 차에 오른 곳을 H3 단위로 나눠 보여줘",
    ["get_place_scope(name=서울)", "get_trip_count(scope_pickup=$pickup.scope, date=this_week, dimension=h3, dimension_target=pickup)"],
    IMP + "손님이 차에 오른 곳=pickup.")
add(16, "g2_implicit_endpoint", "g2", "지난주 대구에서 손님이 내린 곳을 구별로 보여줘",
    ["get_place_scope(name=대구)", "get_trip_count(scope_dropoff=$dropoff.scope, date=last_week, dimension=sigungu, dimension_target=dropoff)"],
    IMP + "손님이 내린 곳=dropoff. 구별=sigungu.")
add(17, "g2_implicit_endpoint", "g2", "휴일에 부산에서 손님을 많이 태운 동네 상위 3곳은?",
    ["get_place_scope(name=부산)", "get_trip_count(scope_pickup=$pickup.scope, date=holiday, dimension=emd, dimension_target=pickup, order=top, limit=3)"],
    IMP + "동네=읍면동. 태운=pickup.")
add(18, "g2_implicit_endpoint", "g2", "지난달 대구에서 손님을 내려준 데가 가장 적은 시군구 2곳은?",
    ["get_place_scope(name=대구)", "get_trip_count(scope_dropoff=$dropoff.scope, date=last_month, dimension=sigungu, dimension_target=dropoff, order=bottom, limit=2)"],
    IMP + "내려준 데=dropoff.")
# ---- g3: value 없는 place 대조(쌍마다 a = 답이 장소 이름, b = "어디"지만 묶음 순위)
NAME = "답이 장소 이름이다: scope 이름 조회(get_scope_name). Full 계약에서 value 없는 place가 측정값(MEASURE)이고 scope는 조건이다. "
RANK = "'어디야'로 묻지만 답은 묶음 단위(dimension)의 순위 1곳이다. value 없는 place 개념을 만들지 않는다(측정값은 하나). "
add(19, "g3_valueless_place", "g3-p1", "scope:gz:3982는 어디야?", ["get_scope_name(scope=scope:gz:3982)"], NAME)
add(20, "g3_valueless_place", "g3-p1", "이번 주 부산 수영구에서 택시가 가장 많이 지나간 읍면동은 어디야?",
    ["get_place_scope(name=수영구, region=부산)", "get_passage_count(scope=$resolve.scope, date=this_week, dimension=emd, order=top, limit=1)"],
    RANK + "통행량(passage_count), 수영구는 값 있는 장소 조건.")
add(21, "g3_valueless_place", "g3-p2", "scope:district:2726010100은 어느 동네를 가리켜?", ["get_scope_name(scope=scope:district:2726010100)"], NAME)
add(22, "g3_valueless_place", "g3-p2", "지난달 대구 수성구에서 손님을 가장 적게 태운 동네는 어디야?",
    ["get_place_scope(name=수성구, region=대구)",
     "get_trip_count(scope_pickup=$pickup.scope, date=last_month, dimension=emd, dimension_target=pickup, order=bottom, limit=1)"],
    RANK + "실차 건수(태운=pickup), 동네=읍면동.")
add(23, "g3_valueless_place", "g3-p3", "scope:h3:8830e1d8dffffff가 어떤 곳인지 이름을 알려줘", ["get_scope_name(scope=scope:h3:8830e1d8dffffff)"], NAME)
add(24, "g3_valueless_place", "g3-p3", "주말에 대구 중구에서 빈 택시가 가장 많이 다닌 H3 셀은 어디야?",
    ["get_place_scope(name=중구, region=대구)",
     "get_passage_count(scope=$resolve.scope, date=weekend, taxi_status=vacant, dimension=h3, order=top, limit=1)"],
    RANK + "빈 택시=vacant 통행량.")
add(25, "g3_valueless_place", "g3-p4", "scope:edge:1742에 해당하는 장소 이름이 뭐야?", ["get_scope_name(scope=scope:edge:1742)"], NAME)
add(26, "g3_valueless_place", "g3-p4", "지난주 부산에서 택시 통행량이 가장 적은 구는 어디야?",
    ["get_place_scope(name=부산)", "get_passage_count(scope=$resolve.scope, date=last_week, dimension=sigungu, order=bottom, limit=1)"],
    RANK + "구=시군구.")
# ---- g4: bucket ↔ dimension 대조쌍
BUCKET = "기간을 주·월 단위로 나눠 1차 집계(aggregation)한 뒤 그 값들을 다시 집계(rollup) = bucket + rollup. 요일·지역별 묶음(dimension)이 아니다. "
DIM = "요일·지역별로 나눠 보이는 것 = dimension. 기간 구간(bucket)이 아니고 rollup도 없다. "
add(27, "g4_bucket_dimension", "g4-p1", "지난달 개인택시 수입을 주 단위로 합한 다음 그 평균을 내줘",
    ["get_billing_metrics(metric=revenue, date=last_month, taxi_type=private, aggregation=sum, bucket=week, rollup=avg)"], BUCKET + "주 단위로 합한=sum, week; 평균=rollup avg.")
add(28, "g4_bucket_dimension", "g4-p1", "지난달 개인택시 수입을 요일별로 합해서 보여줘",
    ["get_billing_metrics(metric=revenue, date=last_month, taxi_type=private, aggregation=sum, dimension=dayofweek)"], DIM + "요일별 합계.")
add(29, "g4_bucket_dimension", "g4-p2", "올해 법인택시 운행 일수를 월별로 평균 낸 값 가운데 가장 큰 값은?",
    ["get_billing_metrics(metric=operating_days, date=this_year, taxi_type=corporate, aggregation=avg, bucket=month, rollup=max)"], BUCKET + "월별 평균=avg, month; 가장 큰 값=rollup max.")
add(30, "g4_bucket_dimension", "g4-p2", "올해 법인택시 운행 일수의 평균을 시도별로 알려줘",
    ["get_billing_metrics(metric=operating_days, date=this_year, taxi_type=corporate, aggregation=avg, dimension=sido)"], DIM + "시도별 평균.")
add(31, "g4_bucket_dimension", "g4-p3", "이번 달 택시 가동률을 주별로 평균 내고 그중 가장 낮은 값을 알려줘",
    ["get_billing_metrics(metric=active_taxi_ratio, date=this_month, aggregation=avg, bucket=week, rollup=min)"], BUCKET + "주별 평균 → 최솟값.")
add(32, "g4_bucket_dimension", "g4-p3", "이번 달 택시 가동률 평균을 요일별로 보여줘",
    ["get_billing_metrics(metric=active_taxi_ratio, date=this_month, aggregation=avg, dimension=dayofweek)"], DIM + "요일별 평균.")
add(33, "g4_bucket_dimension", "g4-p4", "지난해 활성택시 대수를 월마다 평균 낸 뒤 그 중간값을 구해줘",
    ["get_billing_metrics(metric=active_taxi_count, date=last_year, aggregation=avg, bucket=month, rollup=med)"], BUCKET + "월마다 평균 → 중간값.")
add(34, "g4_bucket_dimension", "g4-p4", "지난해 활성택시 대수 평균이 가장 많은 요일은?",
    ["get_billing_metrics(metric=active_taxi_count, date=last_year, aggregation=avg, dimension=dayofweek, order=top, limit=1)"], DIM + "요일별 평균 중 상위 1.")
add(35, "g4_bucket_dimension", "g4-p5", "지난달 법인택시 수입을 주마다 합한 값 중 최솟값은?",
    ["get_billing_metrics(metric=revenue, date=last_month, taxi_type=corporate, aggregation=sum, bucket=week, rollup=min)"], BUCKET + "주마다 합 → 최솟값.")
add(36, "g4_bucket_dimension", "g4-p5", "지난달 법인택시 수입 합계를 시군구별로 알려줘",
    ["get_billing_metrics(metric=revenue, date=last_month, taxi_type=corporate, aggregation=sum, dimension=sigungu)"], DIM + "시군구별 합계.")
add(37, "g4_bucket_dimension", "g4-p6", "올해 개인택시 가동률의 월별 최댓값을 구한 뒤 평균을 내줘",
    ["get_billing_metrics(metric=active_taxi_ratio, date=this_year, taxi_type=private, aggregation=max, bucket=month, rollup=avg)"], BUCKET + "월별 최댓값=max, month → 평균=rollup avg.")
add(38, "g4_bucket_dimension", "g4-p6", "올해 개인택시 가동률 최댓값을 요일별로 알려줘",
    ["get_billing_metrics(metric=active_taxi_ratio, date=this_year, taxi_type=private, aggregation=max, dimension=dayofweek)"], DIM + "요일별 최댓값.")

if __name__ == "__main__":
    out = Path(__file__).resolve().parent / "candidates_draft.yaml"
    out.write_text(yaml.safe_dump({"authored_by": "Claude 2026-10-15(pilot_006 준비 W7b)", "approval": "none",
                                   "reference_date": "2026-09-25", "candidates": C}, allow_unicode=True, sort_keys=False, width=140),
                   encoding="utf-8")
    print(len(C))
