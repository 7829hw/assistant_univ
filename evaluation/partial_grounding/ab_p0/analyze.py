# -*- coding: utf-8 -*-
"""ab_p0 분석(PLAN.md 3·4절). 모델을 부르지 않는다.

    python evaluation/partial_grounding/ab_p0/analyze.py --out evaluation/partial_grounding/ab_p0/analysis.json
    python evaluation/partial_grounding/ab_p0/analyze.py --arms full,p0_1 --out .../analysis_p0_1.json

runs/{A,B}_greedy.json, runs/{A,B}_sample_r{1..5}.json을 읽는다(기본 A=full, B=p0). 없는 회차는 건너뛰고 적는다.
"""

import argparse
import collections
import json
import random
import statistics
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "evaluation" / "partial_grounding"))

import evaluate_vendor100 as V  # noqa: E402
from analyze_replay import causes  # noqa: E402
from failure_census import stage_of  # noqa: E402
from geoflow.errors import GeoFlowError  # noqa: E402
from geoflow.planner import GeoFlowPlanner, parse_planner_json  # noqa: E402

ARMS = ("full", "p0")    # --arms로 바꾼다. 앞이 기준(A), 뒤가 비교(B)
ROUNDS = (1, 2, 3, 4, 5)
CORRECT = {"match", "expected_refusal"}
#: 최종 결과가 grounding 단계에서 멈춘 오류(failure census stage).
GROUNDING_STAGES = {"PLANNER_CALL", "GROUNDING_PARSE"}
#: 출력 contract(형식·구조) 오류. 모델의 판단에 따른 거부(UNSUPPORTED_QUESTION)는 넣지 않는다.
STRUCTURAL_STAGES = {"PLANNER_CALL", "GROUNDING_PARSE"}
REGRESSION_IDS = ("061", "080", "090", "099")
TOKENIZER = ("/data/hwkim/path_repeat_001/hf-cache/hub/models--Qwen--Qwen3-8B/snapshots/"
             "b968826d9c46dd6066d109eabc6255188de91218")


def load(name):
    path = HERE / "runs" / f"{name}.json"
    if not path.is_file():
        return None
    return {row["id"]: row for row in json.loads(path.read_text(encoding="utf-8"))["rows"]}


def first_plan(row):
    calls = row.get("llm_calls") or []
    return calls[0] if calls and calls[0].get("kind", "plan") == "plan" else None


_PLANNER = GeoFlowPlanner(client=None, condition_check=True, clock=lambda: date(2026, 9, 25))


def first_response_check(row, question):
    """첫 계획 응답만으로 grounding 계약을 통과하는가. (오류 코드 또는 None, payload 또는 None)."""
    call = first_plan(row)
    if call is None or call.get("failed"):
        return "PLANNER_CALL_FAILED", None
    text = call.get("content") or ""
    try:
        payload = parse_planner_json(text)
    except GeoFlowError as error:
        return error.code, None
    try:
        _PLANNER._validate_payload(payload, text, question)
    except GeoFlowError as error:
        return error.code, payload
    return None, payload


def item_view(item, row):
    code, payload = first_response_check(row, item["question"])
    call = first_plan(row) or {}
    final = row.get("error_code")
    return {
        "category": row["category"],
        "correct": row["category"] in CORRECT,
        "answerable": item.get("expected_outcome", "answered") == "answered",
        "outcome": row.get("outcome"),
        "error_code": final,
        "grounding_failure": bool(final) and stage_of(final) in GROUNDING_STAGES,
        "grounding_ok": row.get("grounding_ok"),
        "first_error": code,
        "structural": bool(code) and stage_of(code) in STRUCTURAL_STAGES,
        "recovered": bool(code) and stage_of(code) in STRUCTURAL_STAGES and row["category"] in CORRECT,
        "full_style_fields": sorted(causes(payload)) if payload and "concepts" in payload else [],
        "json_text": _json_text(call.get("content") or ""),
        "eval_count": call.get("eval_count"),
        "thinking_chars": call.get("thinking_chars"),
        "duration_ms": sum(c.get("duration_ms") or 0 for c in row.get("llm_calls") or []),
    }


def _json_text(text):
    try:
        return json.dumps(parse_planner_json(text), ensure_ascii=False, separators=(",", ":"))
    except GeoFlowError:
        return None


def metrics(views):
    answerable = [v for v in views if v["answerable"]]
    refusal = [v for v in views if not v["answerable"]]
    rate = lambda items, key: sum(bool(v[key]) for v in items) / len(items) if items else None  # noqa: E731
    return {
        "n": len(views),
        "semantic_correctness": rate(views, "correct"),
        "answerable_semantic_correctness": rate(answerable, "correct"),
        "refusal_correctness": rate(refusal, "correct"),
        "grounding_failure": sum(v["grounding_failure"] for v in views),
        "grounding_ok": sum(bool(v["grounding_ok"]) for v in views),
        "execution_completion": (sum(v["outcome"] == "answered" for v in answerable) / len(answerable)
                                 if answerable else None),
        "structural_first_response": sum(v["structural"] for v in views),
        "structural_recovered": sum(v["recovered"] for v in views),
        "categories": dict(collections.Counter(v["category"] for v in views)),
        "first_errors": dict(collections.Counter(v["first_error"] for v in views if v["first_error"])),
        "final_errors": dict(collections.Counter(v["error_code"] for v in views if v["error_code"])),
        "full_style_field_errors": dict(collections.Counter(c for v in views for c in v["full_style_fields"])),
        "median_eval_count": _median(v["eval_count"] for v in views),
        "median_thinking_chars": _median(v["thinking_chars"] for v in views),
        "median_duration_ms": _median(v["duration_ms"] for v in views),
    }


def _median(values):
    values = [value for value in values if value is not None]
    return statistics.median(values) if values else None


def paired(per_item_full, per_item_p0, ids, *, seed=20261009, draws=10000):
    """문항별 정답률 차이(P0 − Full)의 평균, paired bootstrap 95% CI, sign-flip permutation p."""
    diffs = [per_item_p0[i] - per_item_full[i] for i in ids]
    mean = statistics.mean(diffs)
    rng = random.Random(seed)
    boots = sorted(statistics.mean(rng.choice(diffs) for _ in diffs) for _ in range(draws))
    flips = sum(abs(statistics.mean(d if rng.random() < 0.5 else -d for d in diffs)) >= abs(mean) - 1e-12
                for _ in range(draws))
    return {"mean": mean, "ci95": [boots[int(0.025 * draws)], boots[int(0.975 * draws) - 1]],
            "permutation_p": (flips + 1) / (draws + 1)}


def main(argv=None):
    global ARMS
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--arms", default=",".join(ARMS))
    args = parser.parse_args(argv)
    ARMS = tuple(args.arms.split(","))
    a, b = ARMS
    gold = {item["id"]: item for item in V.load_gold(ROOT / "evaluation/vendor100/gold.yaml")["items"]}
    cells = {}
    for arm in ARMS:
        for name in ("greedy", *(f"sample_r{r}" for r in ROUNDS)):
            rows = load(f"{arm}_{name}")
            if rows is not None:
                cells[(arm, name)] = {i: item_view(gold[i], row) for i, row in rows.items()}
    result = {"cells": {}, "missing": [f"{a}_{n}" for a in ARMS for n in ("greedy", *(f"sample_r{r}" for r in ROUNDS))
                                       if (a, n) not in cells]}
    for (arm, name), views in sorted(cells.items()):
        result["cells"][f"{arm}_{name}"] = metrics(list(views.values()))

    rounds = [f"sample_r{r}" for r in ROUNDS if (a, f"sample_r{r}") in cells and (b, f"sample_r{r}") in cells]
    ids = sorted(gold)
    if rounds:
        result["sampling_rounds"] = rounds
        summary = {}
        for key in ("semantic_correctness", "answerable_semantic_correctness", "refusal_correctness",
                    "execution_completion", "grounding_failure", "grounding_ok", "structural_first_response",
                    "median_eval_count", "median_thinking_chars"):
            per = {arm: [result["cells"][f"{arm}_{r}"][key] for r in rounds] for arm in ARMS}
            if any(value is None for arm in ARMS for value in per[arm]):
                summary[key] = None     # 해당 문항이 없다(업체 100에는 거부해야 할 문항이 없다)
                continue
            summary[key] = {arm: {"mean": statistics.mean(per[arm]), "rounds": per[arm]} for arm in ARMS}
            summary[key]["diff_mean"] = summary[key][b]["mean"] - summary[key][a]["mean"]
        result["sampling_summary"] = summary
        k = {arm: {i: sum(cells[(arm, r)][i]["correct"] for r in rounds) for i in ids} for arm in ARMS}
        rate = {arm: {i: k[arm][i] / len(rounds) for i in ids} for arm in ARMS}
        answerable = [i for i in ids if gold[i].get("expected_outcome", "answered") == "answered"]
        refusal = [i for i in ids if i not in answerable]
        result["paired"] = {"all": paired(rate[a], rate[b], ids),
                            "answerable": paired(rate[a], rate[b], answerable)}
        if refusal:
            result["paired"]["refusal"] = paired(rate[a], rate[b], refusal)
        result["items"] = [{"id": i, "question": gold[i]["question"], "expected": gold[i].get("expected_outcome"),
                            f"k_{a}": k[a][i], f"k_{b}": k[b][i],
                            f"greedy_{a}": cells.get((a, "greedy"), {}).get(i, {}).get("category"),
                            f"greedy_{b}": cells.get((b, "greedy"), {}).get(i, {}).get("category")}
                           for i in ids]
        result["systematic"] = [row for row in result["items"] if abs(row[f"k_{a}"] - row[f"k_{b}"]) >= 4]
        result["discordant"] = {
            r: {f"{a}_correct_{b}_wrong": [i for i in ids if cells[(a, r)][i]["correct"]
                                           and not cells[(b, r)][i]["correct"]],
                f"{a}_wrong_{b}_correct": [i for i in ids if not cells[(a, r)][i]["correct"]
                                           and cells[(b, r)][i]["correct"]]}
            for r in rounds}
        result["regression_set"] = [row for row in result["items"] if row["id"] in REGRESSION_IDS]
    if (a, "greedy") in cells and (b, "greedy") in cells:
        g = {arm: cells[(arm, "greedy")] for arm in ARMS}
        result["greedy_discordant"] = {
            f"{a}_correct_{b}_wrong": [i for i in ids if g[a][i]["correct"] and not g[b][i]["correct"]],
            f"{a}_wrong_{b}_correct": [i for i in ids if not g[a][i]["correct"] and g[b][i]["correct"]]}
    result["json_tokens"] = json_tokens(cells)
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({key: result.get(key) for key in ("missing", "sampling_summary", "paired", "systematic",
                                                         "greedy_discordant", "json_tokens")},
                     ensure_ascii=False, indent=1))
    for name, cell in result["cells"].items():
        print(name, {key: cell[key] for key in ("semantic_correctness", "grounding_ok", "grounding_failure",
                                                "structural_first_response", "execution_completion")})
    return 0


def json_tokens(cells):
    try:
        from transformers import AutoTokenizer
        tokenizer = AutoTokenizer.from_pretrained(TOKENIZER)
    except Exception as error:  # noqa: BLE001 - 토큰 수는 참고 지표다
        return {"error": f"{type(error).__name__}: {error}"}
    out = {}
    for arm in ARMS:
        lengths = [len(tokenizer(view["json_text"]).input_ids)
                   for (cell_arm, _), views in cells.items() if cell_arm == arm
                   for view in views.values() if view["json_text"]]
        out[arm] = {"n": len(lengths), "mean": statistics.mean(lengths) if lengths else None}
    a, b = ARMS
    if out.get(a, {}).get("mean") and out.get(b, {}).get("mean"):
        out["reduction"] = 1 - out[b]["mean"] / out[a]["mean"]
    return out


if __name__ == "__main__":
    raise SystemExit(main())
