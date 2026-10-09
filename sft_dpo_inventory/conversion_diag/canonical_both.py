# -*- coding: utf-8 -*-
"""계약 표기(한 장소 od_role both + dimension_target both)가 현재 pipeline에서 언제 실행되고 언제 멈추는지 확인한다(결정 63 E-2).

    python sft_dpo_inventory/conversion_diag/canonical_both.py --out canonical_both.json

- 모델 호출 없음. 고정한 planner 출력(JSON)을 ``ReplayClient``로 넣고, pilot_002 평가와 같은 pipeline
  (``provider_eval.make_pipeline``: flat, 조건 계층 켬, condition_notes 끔, 기준일 2026-09-25, provider mock)으로 돌린다.
  ``--provider reference``는 같은 pipeline을 reference provider(실행 계약이 다른 도구 구현)로 돌린 대조다.
- 재생에 없는 모델 호출(재질의)이 필요해지면 ``replay exhausted``로 멈춘다. 그 경우 "추가 호출 필요"로 적는다.
- 조건 계층은 질문 문장을 읽으므로, 변형마다 그 grounding과 맞는 질문 문장을 만든다(문장은 이 스크립트 안의 틀).
- 코드·라벨은 고치지 않는다. 질문 원문은 결과에 넣지 않고 변형 설명만 남긴다(093 원문은 업체 100 문항).
"""
import argparse
import itertools
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("ASSISTANT_TOOL_PROVIDER", "mock")
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_prep_002/valid_eval"))

import evaluate_vendor100 as EV  # noqa: E402
import provider_eval as P  # noqa: E402
from failure_census import ReplayClient  # noqa: E402

PLACES = {  # 단위: (name, region, 질문 표현)
    "sido": ("부산", "", "부산"),
    "sigungu": ("수성구", "대구", "대구 수성구"),
    "emd": ("동인동", "대구 중구", "대구 중구 동인동"),  # mock 장소 사전에 있는 읍면동
}
DIMS = {"emd": "읍면동", "sigungu": "시군구", "sido": "시도", "h3": "h3 격자", "dayofweek": "요일"}
DATES = {"this_month": "이번 달", "20260901-20260930": "2026년 9월 1일부터 9월 30일까지", "20260915": "2026년 9월 15일"}


def plan(place, role, *, notation="both", od_role="both", dimension="emd", dimension_target="both", order="bottom", limit=2,
         date="this_month", extra=None):
    name, region, _ = PLACES[place]
    loc = {"id": "c1", "text": name, "concept": "LOCATION", "subtype": "place", "role": role, "source": "user",
           "value": {"name": name, "region": region}}
    if od_role:
        loc["attributes"] = {"od_role": od_role}
    if notation == "old":  # 옛 표기: 같은 장소를 pickup·dropoff 두 개로
        locs = [dict(loc, id="c0", attributes={"od_role": "pickup"}), dict(loc, id="c1", attributes={"od_role": "dropoff"})]
    elif notation == "pickup":  # 대조: 한쪽 끝만
        locs = [dict(loc, attributes={"od_role": "pickup"})]
    else:
        locs = [loc]
    factors = {"date": date}
    if dimension:
        factors["dimension"] = dimension
    if dimension_target:
        factors["dimension_target"] = dimension_target
    if order:
        factors["order"] = order
    if limit is not None:
        factors["limit"] = limit
    factors.update(extra or {})
    return {"concepts": [*locs,
                         {"id": "c2", "concept": "EVENT", "subtype": "trip", "role": "SUPPORT", "source": "implicit"},
                         {"id": "c3", "concept": "AMOUNT", "subtype": "trip_count", "role": "MEASURE", "source": "implicit"}],
            "factors": factors}


def question(place, *, dimension="emd", dimension_target="both", order="bottom", limit=2, date="this_month"):
    _, _, text = PLACES[place]
    q = f"{DATES[date]} {text} 안에서 오간 실차 구간"
    if dimension:
        unit = DIMS[dimension]
        tgt = {"both": f"{unit} 출발지-도착지 조합별로", "pickup": f"출발 {unit}별로", "dropoff": f"도착 {unit}별로",
               None: f"{unit}별로"}[dimension_target]
        q += f"을 {tgt} 세면"
        if order:
            q += " 가장 적은" if order == "bottom" else " 가장 많은"
            q += f" {limit}개는?"
        else:
            q += " 어떻게 되나요?"
    else:
        q += " 건수는?"
    return q


PROVIDER = "mock"


def run(content, q):
    pipeline = P.make_pipeline(ReplayClient([json.dumps(content, ensure_ascii=False)]), PROVIDER)
    try:
        obs = EV.run_item(pipeline, q)
    except Exception as error:  # noqa: BLE001
        return {"outcome": "crash", "error_code": type(error).__name__, "detail": str(error)[:200]}
    trace = obs.get("planner_trace") or []
    return {"outcome": obs["outcome"], "error_code": obs["error_code"], "error_context": obs["error_context"],
            "measure_calls": [{"tool": c["tool"], "args": c["args"]}
                              for c in obs["calls"] if c["tool"] not in ("get_place_scope", "get_scope_name")],
            "lookups": [c["args"].get("name") for c in obs["calls"] if c["tool"] == "get_place_scope"],
            "final_grounding_factors": (obs.get("grounding") or {}).get("factors"),
            "final_od_roles": [((c.get("attributes") or {}).get("od_role"), c.get("role"))
                               for c in (obs.get("grounding") or {}).get("concepts", []) if c.get("concept") == "LOCATION"],
            "condition_corrections": obs.get("condition_corrections"),
            "planner_calls": len(trace) if isinstance(trace, list) else None}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--provider", choices=["mock", "reference"], default="mock")
    args = ap.parse_args()
    global PROVIDER
    PROVIDER = args.provider
    cases = []

    def add(group, desc, content, q):
        cases.append({"group": group, "case": desc, "plan_factors": content["factors"],
                      "plan_locations": [(c["value"], c["role"], (c.get("attributes") or {}).get("od_role"))
                                         for c in content["concepts"] if c["concept"] == "LOCATION"],
                      **run(content, q)})

    # A. 093 HF-최종 최종 grounding 재현과 한 가지씩 뺀 것(부산 = 시도, 이번 달, emd, bottom 2)
    hf093 = plan("sido", "COND", extra={"aggregation": "min"})
    q093 = question("sido")  # 093 원문과 같은 조건의 문장(원문은 쓰지 않음)
    add("A_093", "HF-최종 최종 grounding 그대로(role COND, od_role both, dt both, bottom 2, aggregation min)", hf093, q093)
    add("A_093", "aggregation 뺌(role COND)", plan("sido", "COND"), q093)
    add("A_093", "aggregation 뺌, role SUBCOND(계약 표기)", plan("sido", "SUBCOND"), q093)
    add("A_093", "role SUBCOND + aggregation min", plan("sido", "SUBCOND", extra={"aggregation": "min"}), q093)
    add("A_093", "gold 옛 표기(장소 두 개 pickup·dropoff, dt both)", {
        "concepts": [dict(plan("sido", "SUBCOND")["concepts"][0], id="c0", attributes={"od_role": "pickup"}),
                     dict(plan("sido", "SUBCOND")["concepts"][0], id="c1", attributes={"od_role": "dropoff"}),
                     *plan("sido", "SUBCOND")["concepts"][1:]],
        "factors": plan("sido", "SUBCOND")["factors"]}, q093)
    # B. b004-24 계약 표기(수성구 = 시군구, 9월 범위, emd, top 3)
    b24 = plan("sigungu", "SUBCOND", order="top", limit=3, date="20260901-20260930")
    add("B_b004-24", "b004-24 정답 grounding 그대로", b24,
        question("sigungu", order="top", limit=3, date="20260901-20260930"))
    # C. 조건을 하나씩 바꾼 격자(role SUBCOND, od_role both, aggregation 없음)
    # 표기마다: both(계약 표기), old(장소 두 개), pickup(대조: 한쪽 끝, 질문 문장은 같음)
    for place, dim, ol, date, notation in itertools.product(PLACES, DIMS, [True, False], DATES, ("both", "old", "pickup")):
        order, limit = ("bottom", 2) if ol else (None, None)
        add("C_grid", f"표기 {notation} / 장소 {place} / dimension {dim} / order·limit {'있음' if ol else '없음'} / 날짜 {date}",
            plan(place, "SUBCOND", notation=notation, dimension=dim, order=order, limit=limit, date=date),
            question(place, dimension=dim, order=order, limit=limit, date=date))
    # D. dimension_target 바꿈(시도·emd·이번 달·bottom 2)
    for dt in ("pickup", "dropoff", None):
        add("D_dt", f"장소 sido / dimension_target {dt}",
            plan("sido", "SUBCOND", dimension_target=dt), question("sido", dimension_target=dt))
    # E. dimension 없음(한 장소 both, 단일 값)
    for place, notation in itertools.product(PLACES, ("both", "old")):
        add("E_nodim", f"표기 {notation} / 장소 {place} / dimension 없음",
            plan(place, "SUBCOND", notation=notation, dimension=None, dimension_target=None, order=None, limit=None),
            question(place, dimension=None))
    Path(args.out).write_text(json.dumps(cases, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for c in cases:
        print(c["group"], "|", c["case"], "|", c["outcome"], c["error_code"] or "", c.get("error_context") or "")


if __name__ == "__main__":
    main()
