# -*- coding: utf-8 -*-
# [pilot_006 준비 W3 이식] 원본: geoflow/partial-grounding 커밋 ab9d215의 evaluation/partial_grounding/ab_valid98/analyze.py. 본문은 원본 그대로다(아래 '이식 수정' 줄 제외).
# 원본의 경로 상수(ROOT 등)는 원 위치 기준이라 이 위치에서 바로 돌리려면 경로 인자를 확인한다. 참고값 경로(HF greedy·Ollama, 다른 장비)의 기록용 도구다.
"""ab_valid98 분석(PLAN.md 5절). 모델을 부르지 않는다.

    python evaluation/partial_grounding/ab_valid98/analyze.py --out evaluation/partial_grounding/ab_valid98/analysis.json \
        --csv evaluation/partial_grounding/ab_valid98/paired_items.csv

raw/{full,p0_2}_greedy.json, raw/{full,p0_2}_sample_r{1..5}.json을 읽는다. 문항별 지표·gate 지표·paired 검정은
ab_p0/analyze.py의 함수를 그대로 쓰고(정의가 같다), 거부 confusion·repair·timeout·오류 census A–F를 더한다.
"""

import argparse
import collections
import csv
import importlib.util
import json
import re
import statistics
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
# ab_p0/analyze.py. 이 파일과 이름이 같아 경로로 읽는다.
_spec = importlib.util.spec_from_file_location("ab_p0_analyze", HERE.parent / "ab_p0" / "analyze.py")
P = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(P)

from geoflow.errors import GeoFlowError  # noqa: E402
from geoflow.grounding import CONCEPT_SUBTYPES  # noqa: E402
from geoflow.planner import parse_planner_json  # noqa: E402

GOLD = ROOT / "sft_dpo_inventory/pilot_001_analysis/decision43/valid98_gold.yaml"
ARMS = ("full", "p0_2")
NAMES = ("greedy", *(f"sample_r{r}" for r in P.ROUNDS))
MALFORMED = {"JSON_NOT_FOUND", "JSON_PARSE_FAILED"}
SUBTYPES = {s for values in CONCEPT_SUBTYPES.values() for s in values}
MEASURES = {s for core, values in CONCEPT_SUBTYPES.items() if core.value in ("AMOUNT", "PROPORTION") for s in values}
DIMENSION_WORDS = {"읍면동", "시군구", "시도", "h3", "H3", "H3 셀", "요일", "셀"}
TIME_FORMAT = re.compile(r"^\d{6}-\d{6}$")
REFUSALS = {"unsupported", "needs_clarification"}


def load(name):
    path = HERE / "raw" / f"{name}.json"
    if not path.is_file():
        return None
    return {row["id"]: row for row in json.loads(path.read_text(encoding="utf-8"))["rows"]}


def plan_payloads(row):
    """모든 계획(plan) 응답의 payload. 읽을 수 없으면 건너뛴다."""
    out = []
    for call in row.get("llm_calls") or []:
        if call.get("kind", "plan") != "plan" or call.get("failed"):
            continue
        try:
            payload = parse_planner_json(call.get("content") or "")
        except GeoFlowError:
            continue
        if isinstance(payload, dict):
            out.append(payload)
    return out


def census(payload, item):
    """요청서 6절 A–F. 첫 계획 응답에 대해 해당하는 분류 집합."""
    found = set()
    concepts = payload.get("concepts") if isinstance(payload, dict) else None
    if not isinstance(concepts, list):
        return found
    concepts = [c for c in concepts if isinstance(c, dict)]
    for c in concepts:
        subtype = c.get("subtype")
        attributes = c.get("attributes") if isinstance(c.get("attributes"), dict) else {}
        value = c.get("value") if isinstance(c.get("value"), dict) else {}
        if subtype not in SUBTYPES:
            found.add("A_non_subtype")
        if subtype == "place" and ("dimension" in attributes or value.get("name") in DIMENSION_WORDS):
            found.add("B_dimension_as_place")
        if subtype == "scope" and not c.get("value"):
            found.add("D_scope_value_missing")
    measures = [c for c in concepts if c.get("subtype") in MEASURES]
    valueless_place = [c for c in concepts if c.get("subtype") == "place" and not c.get("value")]
    if len(measures) > 1 or (not measures and not valueless_place):
        found.add("C_measure_missing_or_multiple")
    factors = payload.get("factors") if isinstance(payload.get("factors"), dict) else {}
    if factors.get("dimension") in ("pickup", "dropoff", "both"):
        found.add("E1_od_as_dimension")
    if factors.get("dimension") in ("week", "month"):
        found.add("E2_bucket_as_dimension")
    if "time" in factors and not TIME_FORMAT.match(str(factors["time"])):
        found.add("E3_time_format")
    asks_place = any(call["tool"] == "get_scope_name" for call in item["gold"])
    if asks_place and not valueless_place:
        found.add("F_place_answer_missing")
    return found


def extra_view(item, row):
    calls = row.get("llm_calls") or []
    plans = [c for c in calls if c.get("kind", "plan") == "plan"]
    repairs = [c for c in calls if c.get("kind") == "repair"]
    payloads = plan_payloads(row)
    try:
        wall = (datetime.fromisoformat(row["finished_at"]) - datetime.fromisoformat(row["started_at"])).total_seconds()
    except (KeyError, TypeError, ValueError):
        wall = None
    return {
        "expected": item["expected_outcome"],
        "malformed_first": False,           # 아래에서 first_error로 채운다
        "malformed_final": row.get("error_code") in MALFORMED,
        "repair_calls": len(repairs),
        "timeouts": sum(1 for c in calls if c.get("failed") and "Timeout" in str(c.get("error"))),
        "retries": max(0, len(plans) - 1),
        "wall_s": wall,
        "census": sorted(census(payloads[0], item)) if payloads else ["unreadable_first_response"],
    }


def confusion(views):
    """expected outcome별 결과. 범주는 harness score의 것이고, 거부 문항의 wrong_refusal_kind만 outcome으로 나눠 보인다."""
    table = collections.defaultdict(collections.Counter)
    for v in views:
        if v["expected"] == "answered":
            key = {"match": "answered_correctly", "answered_mismatch": "answered_wrong",
                   "refused_unsupported": "refused(unsupported)", "refused_clarification": "refused(clarification)",
                   "failed": "failed"}.get(v["category"], v["category"])
        elif v["category"] == "wrong_refusal_kind":
            key = "failed" if v["outcome"] == "failed" else f"wrong_refusal_kind({v['outcome']})"
        else:
            key = v["category"]
        table[v["expected"]][key] += 1
    return {k: dict(c) for k, c in table.items()}


def cell_metrics(views):
    out = P.metrics(views)
    repaired = [v for v in views if v["repair_calls"]]
    out.update({
        "malformed_first": sum(v["malformed_first"] for v in views),
        "malformed_final": sum(v["malformed_final"] for v in views),
        "final_grounding_errors": sum(v["grounding_failure"] for v in views),
        "repair_items": len(repaired),
        "repair_calls": sum(v["repair_calls"] for v in views),
        "repair_success_correct": (sum(v["correct"] for v in repaired) / len(repaired)) if repaired else None,
        "repair_success_answered": (sum(v["outcome"] == "answered" for v in repaired) / len(repaired)) if repaired else None,
        "timeouts": sum(v["timeouts"] for v in views),
        "retries": sum(v["retries"] for v in views),
        "median_wall_s": P._median(v["wall_s"] for v in views),
        "total_wall_s": sum(v["wall_s"] or 0 for v in views),
        "confusion": confusion(views),
        "census": dict(collections.Counter(c for v in views for c in v["census"])),
    })
    return out


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--csv", required=True)
    args = parser.parse_args(argv)
    P.V.GOLD_PATH = GOLD
    gold = {item["id"]: item for item in P.V.load_gold(GOLD)["items"]}
    ids = list(gold)
    cells = {}
    for arm in ARMS:
        for name in NAMES:
            rows = load(f"{arm}_{name}")
            if rows is None:
                continue
            views = {}
            for i, row in rows.items():
                view = P.item_view(gold[i], row)
                view.update(extra_view(gold[i], row))
                view["malformed_first"] = view["first_error"] in MALFORMED
                views[i] = view
            cells[(arm, name)] = views
    result = {"arms": ARMS, "missing": [f"{a}_{n}" for a in ARMS for n in NAMES if (a, n) not in cells],
              "cells": {f"{a}_{n}": cell_metrics(list(v.values())) for (a, n), v in sorted(cells.items())}}
    a, b = ARMS
    rounds = [n for n in NAMES[1:] if (a, n) in cells and (b, n) in cells]
    keys = ("semantic_correctness", "answerable_semantic_correctness", "refusal_correctness", "execution_completion",
            "grounding_failure", "grounding_ok", "structural_first_response", "malformed_first", "malformed_final",
            "repair_items", "repair_calls", "repair_success_correct", "repair_success_answered", "timeouts", "retries",
            "median_eval_count", "median_thinking_chars", "median_wall_s", "total_wall_s")
    summary = {}
    for key in keys:
        per = {arm: [result["cells"][f"{arm}_{r}"][key] for r in rounds] for arm in ARMS}
        if not rounds or any(value is None for arm in ARMS for value in per[arm]):
            summary[key] = {arm: per[arm] for arm in ARMS} if rounds else None
            continue
        summary[key] = {arm: {"mean": statistics.mean(per[arm]), "rounds": per[arm]} for arm in ARMS}
        summary[key]["diff_mean"] = summary[key][b]["mean"] - summary[key][a]["mean"]
    result["sampling_rounds"] = rounds
    result["sampling_summary"] = summary
    result["sampling_confusion"] = {arm: confusion([cells[(arm, r)][i] for r in rounds for i in ids]) for arm in ARMS}
    result["sampling_census"] = {arm: dict(collections.Counter(c for r in rounds for i in ids
                                                               for c in cells[(arm, r)][i]["census"])) for arm in ARMS}

    k = {arm: {i: sum(cells[(arm, r)][i]["correct"] for r in rounds) for i in ids} for arm in ARMS}
    refused = {arm: {i: sum(cells[(arm, r)][i]["outcome"] in REFUSALS for r in rounds) for i in ids} for arm in ARMS}
    structural = {arm: {i: sum(cells[(arm, r)][i]["structural"] for r in rounds) for i in ids} for arm in ARMS}
    if rounds:
        rate = {arm: {i: k[arm][i] / len(rounds) for i in ids} for arm in ARMS}
        answerable = [i for i in ids if gold[i]["expected_outcome"] == "answered"]
        refusal = [i for i in ids if i not in answerable]
        result["paired"] = {"all": P.paired(rate[a], rate[b], ids), "answerable": P.paired(rate[a], rate[b], answerable),
                            "refusal": P.paired(rate[a], rate[b], refusal) if refusal else None}
        result["two_by_two"] = {}
        for r in rounds:
            counts = collections.Counter((cells[(a, r)][i]["correct"], cells[(b, r)][i]["correct"]) for i in ids)
            result["two_by_two"][r] = {f"{a}_correct_{b}_correct": counts[(True, True)],
                                       f"{a}_correct_{b}_wrong": counts[(True, False)],
                                       f"{a}_wrong_{b}_correct": counts[(False, True)],
                                       f"{a}_wrong_{b}_wrong": counts[(False, False)]}
        result["consistently_better"] = [i for i in ids if k[b][i] - k[a][i] >= 4]
        result["consistently_worse"] = [i for i in ids if k[a][i] - k[b][i] >= 4]
        result["refusal_changed"] = [{"id": i, "expected": gold[i]["expected_outcome"],
                                      f"refused_{a}": refused[a][i], f"refused_{b}": refused[b][i]}
                                     for i in ids if refused[a][i] != refused[b][i]]
        result["new_structural"] = [{"id": i, f"structural_{a}": structural[a][i], f"structural_{b}": structural[b][i]}
                                    for i in ids if structural[b][i] > 0 and structural[a][i] == 0]
    greedy = {arm: cells.get((arm, "greedy")) for arm in ARMS}
    if all(greedy.values()):
        counts = collections.Counter((greedy[a][i]["correct"], greedy[b][i]["correct"]) for i in ids)
        result["greedy_two_by_two"] = {"both_correct": counts[(True, True)], f"{a}_only": counts[(True, False)],
                                       f"{b}_only": counts[(False, True)], "both_wrong": counts[(False, False)],
                                       f"{a}_correct_{b}_wrong": [i for i in ids if greedy[a][i]["correct"] and not greedy[b][i]["correct"]],
                                       f"{a}_wrong_{b}_correct": [i for i in ids if not greedy[a][i]["correct"] and greedy[b][i]["correct"]]}
    P.ARMS = ARMS
    result["json_tokens"] = P.json_tokens(cells)

    with open(args.csv, "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        header = ["id", "expected", f"k_{a}", f"k_{b}", "n_rounds", f"greedy_{a}", f"greedy_{b}",
                  f"refused_{a}", f"refused_{b}", f"structural_{a}", f"structural_{b}",
                  *(f"{arm}_{r}" for r in rounds for arm in ARMS)]
        writer.writerow(header)
        for i in ids:
            writer.writerow([i, gold[i]["expected_outcome"], k[a][i], k[b][i], len(rounds),
                             (greedy[a] or {}).get(i, {}).get("category"), (greedy[b] or {}).get(i, {}).get("category"),
                             refused[a][i], refused[b][i], structural[a][i], structural[b][i],
                             *(cells[(arm, r)][i]["category"] for r in rounds for arm in ARMS)])
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({key: result.get(key) for key in ("missing", "paired", "consistently_better", "consistently_worse",
                                                         "refusal_changed", "new_structural", "greedy_two_by_two",
                                                         "json_tokens", "sampling_confusion", "sampling_census")},
                     ensure_ascii=False, indent=1))
    for key in keys:
        value = summary.get(key)
        if isinstance(value, dict) and "diff_mean" in value:
            print(f"{key:28s} {a} {value[a]['mean']:.4g} {b} {value[b]['mean']:.4g} diff {value['diff_mean']:+.4g}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
