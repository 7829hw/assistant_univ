# -*- coding: utf-8 -*-
"""batch010 초안(Claude, 2026-10-18, pilot_007 A단계 C3, 결정 169 O5). 질문·정답 호출·근거는 여기 손으로 적었다. **승인이 아니다.**

    python3 sft_dpo_inventory/batch010/write_drafts10.py  # -> candidates_draft.yaml

P 약점(세션 4 A3·A5: P의 U 증가 대부분이 장소 빠뜨림, bucket은 다섯 셋 모두 P 열세)을 두 arm 공통 데이터로 메운다:
- g1 "<지역> 소속 택시"에서 장소 유지(20): 장소 하나(od 없음) + 결제(billing) 측정. 구조는 ``free_structures10.json``의 빈 구조만(s1 4 + s3 bucket 16).
- g2 "…으로 들어온·…에서 나간" 장소 유지(10): 실차 건수에서 장소가 한 끝만 제한(들어온 = 하차 끝, 나간 = 승차 끝). s2 빈 구조(모두 dimension 있음).
- g3 bucket(20): 주별·월별 먼저 집계(s3 빈 구조 10) + bucket ↔ dimension 대조(s3d 빈 구조 10: "요일별·시도별"은 기간을 먼저 집계하지 않고 결과를 나눔).
  현재 코드는 billing dimension과 장소를 함께 받지 않아(PARAM_VALUE_FORBIDS_INPUT) 대조 문항은 장소 없이 쓴다.
규칙(batch009와 같음): 결정 120 겹침(결정 140 예외는 scope 이름 조회만 — 이번에는 그 유형 없음), trunk 표기(장소 하나 = ``get_place_scope`` + ``$resolve.scope``,
한 끝 장소 = ``scope_pickup``/``scope_dropoff``), mock gazetteer 장소만(시도 4·시군구 8·읍면동 10), 보호 셋 문장을 보지 않음.
측정어: revenue 수입, active_taxi_count 활성 택시 대수, active_taxi_ratio 가동률, operating_days 운행 일수. bucket 문장은 "…별 <안쪽 집계> … 중/을 <바깥 집계>"로
안쪽(aggregation)과 바깥(rollup)을 둘 다 말한다. 기준일 2026-09-25.
"""
from pathlib import Path

import yaml

C = []


def add(n, gap, q, calls, why):
    C.append({"id": f"b010-{n:02d}", "gap": gap, "question": q, "gold_text": "\n".join(calls), "rationale": why})


def P(name, region=None):
    return f"get_place_scope(name={name}" + (f", region={region}" if region else "") + ")"


def B(**kw):
    return "get_billing_metrics(" + ", ".join(f"{k}={v}" for k, v in kw.items()) + ")"


def T(**kw):
    return "get_trip_count(" + ", ".join(f"{k}={v}" for k, v in kw.items()) + ")"


R = "$resolve.scope"
SO = "'<지역> 소속 택시' = 그 지역 scope(od 없음). 장소를 빠뜨리면 전국 값이 된다. "
BK = "bucket: 기간을 {b} 단위로 먼저 {a}(aggregation)으로 낸 뒤 그 값들의 {r}(rollup). "
AK = {"avg": "평균", "sum": "합계", "max": "최대", "min": "최소", "med": "중간값"}

# ---- g1: 소속 장소 유지(20)
g1 = [
    ("올해 대구 소속 택시의 활성 택시 대수 최댓값은?", [P("대구"), B(metric="active_taxi_count", scope=R, date="this_year", aggregation="max")], "집계 최대, bucket 없음."),
    ("지난달 부산 소속 개인택시의 활성 택시 대수 중간값을 알려줘", [P("부산"), B(metric="active_taxi_count", scope=R, date="last_month", taxi_type="private", aggregation="med")], "집계 중간값."),
    ("이번 달 인천 소속 택시 가동률의 최솟값은 얼마야?", [P("인천"), B(metric="active_taxi_ratio", scope=R, date="this_month", aggregation="min")], "집계 최소."),
    ("올해 서울 소속 법인택시의 가동률 중간값을 보여줘", [P("서울"), B(metric="active_taxi_ratio", scope=R, date="this_year", taxi_type="corporate", aggregation="med")], "집계 중간값."),
    ("올해 대구 소속 택시의 월별 평균 활성 택시 대수 중 가장 적은 값은?",
     [P("대구"), B(metric="active_taxi_count", scope=R, date="this_year", aggregation="avg", bucket="month", rollup="min")], BK.format(b="월", a="평균", r="최소")),
    ("올해 부산 소속 택시의 월별 최대 활성 택시 대수 가운데 가장 큰 값을 알려줘",
     [P("부산"), B(metric="active_taxi_count", scope=R, date="this_year", aggregation="max", bucket="month", rollup="max")], BK.format(b="월", a="최대", r="최대")),
    ("지난달 대구 수성구 소속 택시의 주별 활성 택시 대수 중간값 중 가장 낮은 값은?",
     [P("수성구", "대구"), B(metric="active_taxi_count", scope=R, date="last_month", aggregation="med", bucket="week", rollup="min")], BK.format(b="주", a="중간값", r="최소")),
    ("이번 달 부산진구 소속 개인택시의 주별 최소 활성 택시 대수를 평균 내면 얼마야?",
     [P("부산진구", "부산"), B(metric="active_taxi_count", scope=R, date="this_month", taxi_type="private", aggregation="min", bucket="week", rollup="avg")],
     BK.format(b="주", a="최소", r="평균")),
    ("올해 인천 소속 택시의 월별 평균 가동률을 다시 평균 낸 값은?",
     [P("인천"), B(metric="active_taxi_ratio", scope=R, date="this_year", aggregation="avg", bucket="month", rollup="avg")], BK.format(b="월", a="평균", r="평균")),
    ("올해 서울 소속 개인택시의 월별 최고 가동률 중 가장 낮은 값을 알려줘",
     [P("서울"), B(metric="active_taxi_ratio", scope=R, date="this_year", taxi_type="private", aggregation="max", bucket="month", rollup="min")], BK.format(b="월", a="최대", r="최소")),
    ("지난달 대구 소속 택시의 주별 평균 가동률 중 가장 높은 값은?",
     [P("대구"), B(metric="active_taxi_ratio", scope=R, date="last_month", aggregation="avg", bucket="week", rollup="max")], BK.format(b="주", a="평균", r="최대")),
    ("이번 달 부산 수영구 소속 법인택시의 주별 최저 가동률 중 가장 낮은 값을 보여줘",
     [P("수영구", "부산"), B(metric="active_taxi_ratio", scope=R, date="this_month", taxi_type="corporate", aggregation="min", bucket="week", rollup="min")],
     BK.format(b="주", a="최소", r="최소")),
    ("올해 부산 소속 택시의 월별 운행 일수 합계 중 가장 많은 값은?",
     [P("부산"), B(metric="operating_days", scope=R, date="this_year", aggregation="sum", bucket="month", rollup="max")], BK.format(b="월", a="합계", r="최대")),
    ("올해 대구 소속 개인택시의 월별 평균 운행 일수의 중간값을 알려줘",
     [P("대구"), B(metric="operating_days", scope=R, date="this_year", taxi_type="private", aggregation="avg", bucket="month", rollup="med")], BK.format(b="월", a="평균", r="중간값")),
    ("지난달 서울 소속 택시의 주별 운행 일수 합계를 평균 내면?",
     [P("서울"), B(metric="operating_days", scope=R, date="last_month", aggregation="sum", bucket="week", rollup="avg")], BK.format(b="주", a="합계", r="평균")),
    ("이번 달 인천 소속 법인택시의 주별 최대 운행 일수 중 가장 작은 값은?",
     [P("인천"), B(metric="operating_days", scope=R, date="this_month", taxi_type="corporate", aggregation="max", bucket="week", rollup="min")], BK.format(b="주", a="최대", r="최소")),
    ("올해 대구 소속 택시의 월별 최대 수입을 평균 낸 값은 얼마야?",
     [P("대구"), B(metric="revenue", scope=R, date="this_year", aggregation="max", bucket="month", rollup="avg")], BK.format(b="월", a="최대", r="평균")),
    ("올해 부산 소속 개인택시의 월별 수입 중간값 가운데 가장 큰 값을 알려줘",
     [P("부산"), B(metric="revenue", scope=R, date="this_year", taxi_type="private", aggregation="med", bucket="month", rollup="max")], BK.format(b="월", a="중간값", r="최대")),
    ("지난달 대구 달서구 소속 택시의 주별 수입 합계 중 가장 적은 값은?",
     [P("달서구", "대구"), B(metric="revenue", scope=R, date="last_month", aggregation="sum", bucket="week", rollup="min")], BK.format(b="주", a="합계", r="최소")),
    ("이번 달 서울 소속 법인택시의 주별 평균 수입의 중간값은?",
     [P("서울"), B(metric="revenue", scope=R, date="this_month", taxi_type="corporate", aggregation="avg", bucket="week", rollup="med")], BK.format(b="주", a="평균", r="중간값")),
]
for i, (q, calls, why) in enumerate(g1, 1):
    add(i, "g1_affiliation_place", q, calls, SO + why)

IN = "'…으로 들어온·…에 들어온' = 그 장소가 하차(도착) 끝, '…에서 나간·빠져나간' = 승차(출발) 끝(od_role). 묶는 끝은 dimension_target. "
# ---- g2: 들어온·나간 장소 유지(10)
g2 = [
    ("지난주 부산 초량동에서 나간 실차를 도착 시도별로 셌을 때 가장 적은 두 곳은?",
     [P("초량동", "부산"), T(scope_pickup="$pickup.scope", date="last_week", dimension="sido", dimension_target="dropoff", order="bottom", limit=2)], "나간 = 승차 끝, 도착 시도별 = dt 하차, 순위 하위 2."),
    ("이번 달 대구 동인동에서 나간 실차 건수를 출발 읍면동과 도착 읍면동 짝별로 보여줘",
     [P("동인동", "대구"), T(scope_pickup="$pickup.scope", date="this_month", dimension="emd", dimension_target="both")], "나간 = 승차 끝, 짝별 = dt both."),
    ("지난주 대구 중앙로동에서 나간 실차를 도착 H3 셀별로 세어줘",
     [P("중앙로동", "대구"), T(scope_pickup="$pickup.scope", date="last_week", dimension="h3", dimension_target="dropoff")], "나간 = 승차 끝, 도착 H3 셀별 = dt 하차."),
    ("이번 달 대구 태평로동에서 나간 실차가 가장 많이 도착한 H3 셀 세 곳은?",
     [P("태평로동", "대구"), T(scope_pickup="$pickup.scope", date="this_month", dimension="h3", dimension_target="dropoff", order="top", limit=3)], "순위 상위 3."),
    ("지난달 대구 동성로동에서 빠져나간 실차가 가장 적게 도착한 H3 셀 두 곳은?",
     [P("동성로동", "대구"), T(scope_pickup="$pickup.scope", date="last_month", dimension="h3", dimension_target="dropoff", order="bottom", limit=2)], "빠져나간 = 승차 끝, 순위 하위 2."),
    ("지난주 부산 초량동으로 들어온 실차를 출발 시도별로 세어줘",
     [P("초량동", "부산"), T(scope_dropoff="$dropoff.scope", date="last_week", dimension="sido", dimension_target="pickup")], "들어온 = 하차 끝, 출발 시도별 = dt 승차."),
    ("이번 달 대구 동인동으로 들어온 실차가 가장 많이 출발한 시도 두 곳은?",
     [P("동인동", "대구"), T(scope_dropoff="$dropoff.scope", date="this_month", dimension="sido", dimension_target="pickup", order="top", limit=2)], "순위 상위 2."),
    ("지난달 부산 초읍동으로 들어온 실차가 가장 적게 출발한 시도는?",
     [P("초읍동", "부산"), T(scope_dropoff="$dropoff.scope", date="last_month", dimension="sido", dimension_target="pickup", order="bottom", limit=1)], "순위 하위 1."),
    ("지난주 대구 신천동에 들어온 실차 건수를 출발 시군구별로 보여줘",
     [P("신천동", "대구"), T(scope_dropoff="$dropoff.scope", date="last_week", dimension="sigungu", dimension_target="pickup")], "들어온 = 하차 끝, 출발 시군구별."),
    ("이번 달 대구 두류동으로 들어온 실차를 출발 읍면동별로 세어줘",
     [P("두류동", "대구"), T(scope_dropoff="$dropoff.scope", date="this_month", dimension="emd", dimension_target="pickup")], "들어온 = 하차 끝, 출발 읍면동별."),
]
for i, (q, calls, why) in enumerate(g2, 21):
    add(i, "g2_inflow_outflow_place", q, calls, IN + why)

# ---- g3: bucket(10) + bucket ↔ dimension 대조(10)
g3b = [
    ("올해 대구 택시의 주별 평균 수입 가운데 가장 낮은 값은?", [P("대구"), B(metric="revenue", scope=R, date="this_year", aggregation="avg", bucket="week", rollup="min")], ("주", "평균", "최소")),
    ("올해 부산 택시의 월별 최대 수입 중 가장 작은 값을 알려줘", [P("부산"), B(metric="revenue", scope=R, date="this_year", aggregation="max", bucket="month", rollup="min")], ("월", "최대", "최소")),
    ("지난달 인천 택시의 주별 최대 활성 택시 대수를 평균 내줘", [P("인천"), B(metric="active_taxi_count", scope=R, date="last_month", aggregation="max", bucket="week", rollup="avg")], ("주", "최대", "평균")),
    ("올해 서울 개인택시의 월별 최소 활성 택시 대수 중 가장 큰 값은?",
     [P("서울"), B(metric="active_taxi_count", scope=R, date="this_year", taxi_type="private", aggregation="min", bucket="month", rollup="max")], ("월", "최소", "최대")),
    ("이번 달 대구 법인택시의 주별 가동률 중간값 가운데 가장 높은 값은?",
     [P("대구"), B(metric="active_taxi_ratio", scope=R, date="this_month", taxi_type="corporate", aggregation="med", bucket="week", rollup="max")], ("주", "중간값", "최대")),
    ("올해 부산진구 택시의 월별 최저 가동률을 평균 낸 값은?", [P("부산진구", "부산"), B(metric="active_taxi_ratio", scope=R, date="this_year", aggregation="min", bucket="month", rollup="avg")], ("월", "최소", "평균")),
    ("지난달 대구 수성구 택시의 주별 평균 운행 일수를 다시 평균 내면 얼마야?",
     [P("수성구", "대구"), B(metric="operating_days", scope=R, date="last_month", aggregation="avg", bucket="week", rollup="avg")], ("주", "평균", "평균")),
    ("올해 인천 법인택시의 월별 최대 운행 일수 중 가장 큰 값은?",
     [P("인천"), B(metric="operating_days", scope=R, date="this_year", taxi_type="corporate", aggregation="max", bucket="month", rollup="max")], ("월", "최대", "최대")),
    ("이번 달 대구 개인택시의 주별 운행 일수 중간값 가운데 가장 작은 값을 보여줘",
     [P("대구"), B(metric="operating_days", scope=R, date="this_month", taxi_type="private", aggregation="med", bucket="week", rollup="min")], ("주", "중간값", "최소")),
    ("지난달 부산 택시의 주별 수입 합계의 중간값은?", [P("부산"), B(metric="revenue", scope=R, date="last_month", aggregation="sum", bucket="week", rollup="med")], ("주", "합계", "중간값")),
]
for i, (q, calls, (b, a, r)) in enumerate(g3b, 31):
    add(i, "g3_bucket", q, calls, BK.format(b=b, a=a, r=r) + "장소는 결제 기록의 소속 지역 scope.")
DIM = "대조: '…별'이 기간을 먼저 집계하는 bucket이 아니라 결과를 {d}로 나누는 dimension이다(먼저 집계 없음). 장소 없음(현재 코드가 billing dimension + scope를 받지 않음). "
g3d = [
    ("올해 요일별 평균 수입을 알려줘", [B(metric="revenue", date="this_year", aggregation="avg", dimension="dayofweek")], "요일", "집계 평균."),
    ("올해 최대 수입이 가장 높은 요일은?", [B(metric="revenue", date="this_year", aggregation="max", dimension="dayofweek", order="top", limit=1)], "요일", "집계 최대, 순위 상위 1."),
    ("올해 요일별 활성 택시 대수를 보여줘", [B(metric="active_taxi_count", date="this_year", dimension="dayofweek")], "요일", "집계 없음."),
    ("지난달 시도별 평균 활성 택시 대수는?", [B(metric="active_taxi_count", date="last_month", aggregation="avg", dimension="sido")], "시도", "집계 평균."),
    ("올해 최저 가동률이 가장 낮은 두 요일은?", [B(metric="active_taxi_ratio", date="this_year", aggregation="min", dimension="dayofweek", order="bottom", limit=2)], "요일", "집계 최소, 순위 하위 2."),
    ("이번 달 요일별 평균 가동률을 보여줘", [B(metric="active_taxi_ratio", date="this_month", aggregation="avg", dimension="dayofweek")], "요일", "집계 평균."),
    ("올해 운행 일수 합계가 가장 많은 요일 두 개는?", [B(metric="operating_days", date="this_year", aggregation="sum", dimension="dayofweek", order="top", limit=2)], "요일", "집계 합계, 순위 상위 2."),
    ("지난달 시도별 운행 일수 중간값을 알려줘", [B(metric="operating_days", date="last_month", aggregation="med", dimension="sido")], "시도", "집계 중간값."),
    ("올해 수입 중간값이 가장 높은 시도 두 곳은?", [B(metric="revenue", date="this_year", aggregation="med", dimension="sido", order="top", limit=2)], "시도", "집계 중간값, 순위 상위 2."),
    ("이번 달 최대 활성 택시 대수가 가장 적은 시도는?", [B(metric="active_taxi_count", date="this_month", aggregation="max", dimension="sido", order="bottom", limit=1)], "시도", "집계 최대, 순위 하위 1."),
]
for i, (q, calls, d, why) in enumerate(g3d, 41):
    add(i, "g3_bucket_vs_dimension", q, calls, DIM.format(d=d) + why)

# ---- 2차(b010-51–55): 1차 검사에서 빠진 5건(b010-11·14·15 Jaccard ≥ 0.5, b010-25 H3 경로 NOT_FOUND, b010-46 같은 grounding)만큼 다른 빈 구조로 다시 씀.
#      1차 후보와 결과는 지우지 않는다(batch009 2차와 같은 방식).
add(51, "g1_affiliation_place", "지난달 대구 소속 법인택시의 주별 평균 활성 택시 대수 가운데 가장 적은 값은?",
    [P("대구"), B(metric="active_taxi_count", scope=R, date="last_month", taxi_type="corporate", aggregation="avg", bucket="week", rollup="min")], SO + BK.format(b="주", a="평균", r="최소"))
add(52, "g1_affiliation_place", "이번 달 부산 소속 개인택시의 주별 가동률 중간값 중 가장 낮은 값을 알려줘",
    [P("부산"), B(metric="active_taxi_ratio", scope=R, date="this_month", taxi_type="private", aggregation="med", bucket="week", rollup="min")], SO + BK.format(b="주", a="중간값", r="최소"))
add(53, "g1_affiliation_place", "올해 서울 소속 택시의 월별 최소 운행 일수 가운데 가장 큰 값은?",
    [P("서울"), B(metric="operating_days", scope=R, date="this_year", aggregation="min", bucket="month", rollup="max")], SO + BK.format(b="월", a="최소", r="최대"))
add(54, "g2_inflow_outflow_place", "이번 달 대구 중앙로동으로 들어온 실차 건수를 출발·도착 읍면동 짝으로 나눴을 때 가장 많은 두 짝은?",
    [P("중앙로동", "대구"), T(scope_dropoff="$dropoff.scope", date="this_month", dimension="emd", dimension_target="both", order="top", limit=2)], IN + "들어온 = 하차 끝, 짝별 = dt both, 순위 상위 2.")
add(55, "g3_bucket_vs_dimension", "올해 최고 가동률이 가장 높은 시도 두 곳은?",
    [B(metric="active_taxi_ratio", date="this_year", aggregation="max", dimension="sido", order="top", limit=2)], DIM.format(d="시도") + "집계 최대, 순위 상위 2.")

assert len(C) == 55 and len({c["question"] for c in C}) == 55
(Path(__file__).resolve().parent / "candidates_draft.yaml").write_text(
    yaml.safe_dump({"batch": "batch010", "status": "초안(승인 아님)", "author": "Claude", "date": "2026-10-18", "candidates": C}, allow_unicode=True, sort_keys=False),
    encoding="utf-8")
print(len(C))
