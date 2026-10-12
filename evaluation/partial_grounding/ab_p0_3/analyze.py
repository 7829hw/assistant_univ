# -*- coding: utf-8 -*-
"""ab_p0_3 분석(PLAN.md 5–8절). 모델을 부르지 않는다. 결과를 보기 전에 고정했다.

    python evaluation/partial_grounding/ab_p0_3/analyze.py --out evaluation/partial_grounding/ab_p0_3/analysis.json \
        --csv evaluation/partial_grounding/ab_p0_3/paired_items.csv

raw/{arm}_greedy.json, raw/{arm}_sample_r{1..5}.json(arm = full, p0, p0_3)을 읽는다. 셀 지표·confusion·census·repair는
ab_valid98/analyze.py, 문항 지표·paired 검정·JSON token은 ab_p0/analyze.py의 함수를 그대로 쓴다(정의가 같다).
더하는 것: 세 arm 비교 쌍, 부분집합(dt·bucket·refusal, gold factor로 고정), dimension_target 누락률,
week/month-as-dimension, 오류 귀속 A–I.

``--raw``·``--gold``·``--arms``는 다른 기록으로 이 스크립트를 점검할 때만 쓴다(예: ab_valid98 raw, full,p0_2).
"""

import argparse
import collections
import csv
import importlib.util
import json
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def _load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


V98 = _load_module("ab_valid98_analyze", HERE.parent / "ab_valid98" / "analyze.py")
P = V98.P

_first_response_check = P.first_response_check


def _first_response_check_total(row, question):
    """결과 뒤 추가(2026-10-12): parser가 GeoFlowError가 아닌 예외를 내는 첫 응답(concept value가 dict 등)은
    실행 harness와 같은 UNHANDLED_EXCEPTION 구조 오류로 센다. 정의는 바꾸지 않고 분석이 죽지 않게만 한다."""
    try:
        return _first_response_check(row, question)
    except Exception:
        return "UNHANDLED_EXCEPTION", None


P.first_response_check = _first_response_check_total

GOLD = HERE / "sel154_gold.yaml"
ARMS = ("full", "p0", "p0_3")
TIME_DIMENSIONS = {"week", "month", "day", "hour"}
BOUNDARY_ERRORS = {"INVALID_CONCEPT", "UNKNOWN_ATTRIBUTE", "UNKNOWN_FACTOR"}
VALUE_ERRORS = {"VALUELESS_CONCEPT", "MISSING_CONCEPT_VALUE", "UNGROUNDED_SCOPE"}
MEASURE_ERRORS = {"NO_MEASURE", "MULTIPLE_MEASURES"}
ATTRIBUTION = ("A_semantic_decision", "B_boundary", "C_dimension_target_omission", "D_od_role_dimension_target_confusion",
               "E_bucket_dimension_confusion", "F_place_scope_value_omission", "G_measure_omission", "H_refusal",
               "I_pipeline_failure")


def load(raw, name):
    path = raw / f"{name}.json"
    if not path.is_file():
        return None
    return {row["id"]: row for row in json.loads(path.read_text(encoding="utf-8"))["rows"]}


def gold_factors(item):
    return (P.V.gold_grounding(item) or {}).get("factors") or {}


def diffs(row):
    out = []
    for d in row.get("grounding_diffs") or []:
        if isinstance(d, (list, tuple)) and d:
            out.append((d[0], d[1] if len(d) > 1 else None, d[2] if len(d) > 2 else None))
        else:
            out.append((str(d), None, None))
    return out


def first_dimension(row):
    payloads = V98.plan_payloads(row)
    factors = payloads[0].get("factors") if payloads and isinstance(payloads[0].get("factors"), dict) else {}
    return factors.get("dimension")


def attribution(view, row):
    """PLAN.md 8절. 정답 관측은 빈 집합."""
    if view["correct"]:
        return set()
    found = set()
    ds = diffs(row)
    keys = {k for k, _, _ in ds}
    dt = [(g, p) for k, g, p in ds if k == "factor:dimension_target"]
    census = set(view["census"])
    first_error = view["first_error"]
    if census & {"A_non_subtype", "B_dimension_as_place", "E1_od_as_dimension"} or first_error in BOUNDARY_ERRORS:
        found.add("B_boundary")
    if any(g is not None and p is None for g, p in dt):
        found.add("C_dimension_target_omission")
    d_flag = (dt and "places" in keys) or any(g is None and p is not None for g, p in dt)
    if d_flag:
        found.add("D_od_role_dimension_target_confusion")
    e_flag = view["first_dimension"] in TIME_DIMENSIONS or {"factor:bucket", "factor:dimension"} <= keys
    if e_flag:
        found.add("E_bucket_dimension_confusion")
    if first_error in VALUE_ERRORS or census & {"D_scope_value_missing", "F_place_answer_missing"}:
        found.add("F_place_scope_value_omission")
    if first_error in MEASURE_ERRORS or "measure" in keys:
        found.add("G_measure_omission")
    if not view["answerable"] or view["category"] in ("refused_unsupported", "refused_clarification"):
        found.add("H_refusal")
    if view["category"] == "answered_mismatch":
        rest = keys - {"factor:dimension_target", "measure"}
        if d_flag:
            rest -= {"places"}
        if e_flag:
            rest -= {"factor:bucket", "factor:dimension"}
        if rest:
            found.add("A_semantic_decision")
    if view["outcome"] == "failed" and not found & {"B_boundary", "E_bucket_dimension_confusion",
                                                     "F_place_scope_value_omission", "G_measure_omission", "H_refusal"}:
        found.add("I_pipeline_failure")
    return found


def rate_by_item(cells, arm, rounds, ids, key):
    return {i: sum(bool(cells[(arm, r)][i][key]) for r in rounds) / len(rounds) for i in ids}


def subset_summary(cells, rounds, ids, arms, base):
    out = {"n": len(ids)}
    if not ids or not rounds:
        return out
    rate = {arm: rate_by_item(cells, arm, rounds, ids, "correct") for arm in arms}
    out["correct"] = {arm: statistics.mean(rate[arm].values()) for arm in arms}
    out["paired_vs_" + base] = {arm: P.paired(rate[base], rate[arm], ids) for arm in arms if arm != base}
    return out


def pair_report(cells, rounds, ids, gold, a, b, k, refused, structural):
    rate = {arm: {i: k[arm][i] / len(rounds) for i in ids} for arm in (a, b)}
    answerable = [i for i in ids if gold[i]["expected_outcome"] == "answered"]
    refusal = [i for i in ids if i not in answerable]
    out = {"paired": {"all": P.paired(rate[a], rate[b], ids), "answerable": P.paired(rate[a], rate[b], answerable),
                      "refusal": P.paired(rate[a], rate[b], refusal) if refusal else None},
           "two_by_two": {}}
    for r in rounds:
        counts = collections.Counter((cells[(a, r)][i]["correct"], cells[(b, r)][i]["correct"]) for i in ids)
        out["two_by_two"][r] = {f"{a}_correct_{b}_correct": counts[(True, True)], f"{a}_correct_{b}_wrong": counts[(True, False)],
                                f"{a}_wrong_{b}_correct": counts[(False, True)], f"{a}_wrong_{b}_wrong": counts[(False, False)]}
    out["consistently_better"] = [i for i in ids if k[b][i] - k[a][i] >= 4]
    out["consistently_worse"] = [i for i in ids if k[a][i] - k[b][i] >= 4]
    out["refusal_changed"] = [{"id": i, "expected": gold[i]["expected_outcome"], f"refused_{a}": refused[a][i],
                               f"refused_{b}": refused[b][i]} for i in ids if refused[a][i] != refused[b][i]]
    out["new_structural"] = [{"id": i, f"structural_{a}": structural[a][i], f"structural_{b}": structural[b][i]}
                             for i in ids if structural[b][i] > 0 and structural[a][i] == 0]
    greedy = {arm: cells.get((arm, "greedy")) for arm in (a, b)}
    if all(greedy.values()):
        counts = collections.Counter((greedy[a][i]["correct"], greedy[b][i]["correct"]) for i in ids)
        out["greedy_two_by_two"] = {"both_correct": counts[(True, True)], f"{a}_only": counts[(True, False)],
                                    f"{b}_only": counts[(False, True)], "both_wrong": counts[(False, False)]}
    return out


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--csv", required=True)
    parser.add_argument("--raw", default=str(HERE / "raw"))
    parser.add_argument("--gold", default=str(GOLD))
    parser.add_argument("--arms", default=",".join(ARMS))
    args = parser.parse_args(argv)
    arms = tuple(args.arms.split(","))
    base = arms[0]
    raw, gold_path = Path(args.raw), Path(args.gold)
    P.V.GOLD_PATH = gold_path
    gold = {item["id"]: item for item in P.V.load_gold(gold_path)["items"]}
    for item in gold.values():
        item.setdefault("expected_outcome", "answered")
    ids = list(gold)
    subsets = {"dt": [i for i in ids if gold_factors(gold[i]).get("dimension_target")],
               "bucket": [i for i in ids if gold_factors(gold[i]).get("bucket")],
               "refusal": [i for i in ids if gold[i]["expected_outcome"] != "answered"]}

    cells, attributions = {}, {}
    for arm in arms:
        for name in V98.NAMES:
            rows = load(raw, f"{arm}_{name}")
            if rows is None:
                continue
            views = {}
            for i, row in rows.items():
                view = P.item_view(gold[i], row)
                view.update(V98.extra_view(gold[i], row))
                view["malformed_first"] = view["first_error"] in V98.MALFORMED
                view["first_dimension"] = first_dimension(row)
                ds = diffs(row)
                view["dt_omitted"] = any(k == "factor:dimension_target" and g is not None and p is None for k, g, p in ds)
                view["no_grounding"] = any(k == "no_grounding" for k, _, _ in ds)
                view["time_as_dimension"] = view["first_dimension"] in TIME_DIMENSIONS
                view["attribution"] = sorted(attribution(view, row))
                views[i] = view
            cells[(arm, name)] = views
    result = {"arms": arms, "base": base, "subsets": {k: {"n": len(v), "ids": v} for k, v in subsets.items()},
              "missing": [f"{a}_{n}" for a in arms for n in V98.NAMES if (a, n) not in cells],
              "cells": {f"{a}_{n}": V98.cell_metrics(list(v.values())) for (a, n), v in sorted(cells.items())}}
    rounds = [n for n in V98.NAMES[1:] if all((arm, n) in cells for arm in arms)]
    result["sampling_rounds"] = rounds
    keys = ("semantic_correctness", "answerable_semantic_correctness", "refusal_correctness", "execution_completion",
            "grounding_failure", "grounding_ok", "structural_first_response", "malformed_first", "malformed_final",
            "repair_items", "repair_calls", "repair_success_correct", "repair_success_answered", "timeouts", "retries",
            "median_eval_count", "median_thinking_chars", "median_wall_s", "total_wall_s")
    summary = {}
    for key in keys:
        per = {arm: [result["cells"][f"{arm}_{r}"][key] for r in rounds] for arm in arms}
        if not rounds or any(value is None for arm in arms for value in per[arm]):
            summary[key] = per if rounds else None
            continue
        summary[key] = {arm: {"mean": statistics.mean(per[arm]), "rounds": per[arm]} for arm in arms}
        summary[key]["diff_vs_" + base] = {arm: summary[key][arm]["mean"] - summary[key][base]["mean"]
                                           for arm in arms if arm != base}
    result["sampling_summary"] = summary
    obs = {arm: [cells[(arm, r)][i] for r in rounds for i in ids] for arm in arms}
    result["sampling_confusion"] = {arm: V98.confusion(obs[arm]) for arm in arms}
    result["sampling_census"] = {arm: dict(collections.Counter(c for v in obs[arm] for c in v["census"])) for arm in arms}
    result["attribution"] = {arm: {c: sum(c in v["attribution"] for v in obs[arm]) for c in ATTRIBUTION} for arm in arms}
    result["attribution_final_errors_I"] = {arm: dict(collections.Counter(v["error_code"] for v in obs[arm]
                                                                          if "I_pipeline_failure" in v["attribution"]))
                                            for arm in arms}

    if rounds:
        dt = subsets["dt"]
        omission = {arm: rate_by_item(cells, arm, rounds, dt, "dt_omitted") for arm in arms}
        result["dimension_target_omission"] = {
            "n_items": len(dt), "n_observations": len(dt) * len(rounds),
            "rate": {arm: statistics.mean(omission[arm].values()) if dt else None for arm in arms},
            "count": {arm: sum(cells[(arm, r)][i]["dt_omitted"] for r in rounds for i in dt) for arm in arms},
            "no_grounding": {arm: sum(cells[(arm, r)][i]["no_grounding"] for r in rounds for i in dt) for arm in arms},
            "paired": ({f"{x}_minus_{y}": P.paired(omission[y], omission[x], dt)
                        for x, y in ((arms[-1], arms[1] if len(arms) > 2 else base), (arms[-1], base))} if dt else None)}
        result["time_as_dimension"] = {
            "all": {arm: sum(v["time_as_dimension"] for v in obs[arm]) for arm in arms},
            "bucket_subset": {arm: sum(cells[(arm, r)][i]["time_as_dimension"] for r in rounds for i in subsets["bucket"])
                              for arm in arms},
            "items": {arm: dict(collections.Counter(i for r in rounds for i in ids if cells[(arm, r)][i]["time_as_dimension"]))
                      for arm in arms}}
        result["subset_correctness"] = {name: subset_summary(cells, rounds, sub, arms, base) for name, sub in subsets.items()}
        k = {arm: {i: sum(cells[(arm, r)][i]["correct"] for r in rounds) for i in ids} for arm in arms}
        refused = {arm: {i: sum(cells[(arm, r)][i]["outcome"] in V98.REFUSALS for r in rounds) for i in ids} for arm in arms}
        structural = {arm: {i: sum(cells[(arm, r)][i]["structural"] for r in rounds) for i in ids} for arm in arms}
        pairs = [(base, arm) for arm in arms[1:]] + ([(arms[1], arms[2])] if len(arms) > 2 else [])
        result["pairs"] = {f"{a}_vs_{b}": pair_report(cells, rounds, ids, gold, a, b, k, refused, structural)
                           for a, b in pairs}
    else:
        k = refused = structural = None

    tokens = {}
    for arm in arms[1:]:
        P.ARMS = (base, arm)
        tokens[arm] = P.json_tokens({key: v for key, v in cells.items() if key[0] in (base, arm)})
    result["json_tokens"] = tokens

    with open(args.csv, "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["id", "expected", *(f"in_{s}" for s in subsets), *(f"k_{arm}" for arm in arms), "n_rounds",
                         *(f"greedy_{arm}" for arm in arms), *(f"refused_{arm}" for arm in arms),
                         *(f"structural_{arm}" for arm in arms), *(f"{arm}_{r}" for r in rounds for arm in arms)])
        for i in ids:
            writer.writerow([i, gold[i]["expected_outcome"], *(int(i in subsets[s]) for s in subsets),
                             *((k[arm][i] if k else None) for arm in arms), len(rounds),
                             *((cells.get((arm, "greedy")) or {}).get(i, {}).get("category") for arm in arms),
                             *((refused[arm][i] if refused else None) for arm in arms),
                             *((structural[arm][i] if structural else None) for arm in arms),
                             *(cells[(arm, r)][i]["category"] for r in rounds for arm in arms)])
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for key in keys:
        value = summary.get(key)
        if isinstance(value, dict) and "diff_vs_" + base in value:
            print(f"{key:32s} " + "  ".join(f"{arm} {value[arm]['mean']:.4g}" for arm in arms))
    for name in ("dimension_target_omission", "time_as_dimension", "subset_correctness", "attribution", "json_tokens"):
        print(name, json.dumps(result.get(name), ensure_ascii=False)[:1500])
    for name, rep in (result.get("pairs") or {}).items():
        print(name, json.dumps(rep["paired"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
