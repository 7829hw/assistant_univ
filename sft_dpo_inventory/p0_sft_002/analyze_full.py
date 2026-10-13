# -*- coding: utf-8 -*-
"""p0_sft_002 R70 403문항 진단 평가 분석(PLAN.md 8절). p0_sft_001/analyze.py를 그대로 옮기고 모델·입력 경로만 바꿨다.

원 문서: p0_sft_001 분석(PLAN.md 7절, 결과를 보기 전에 고정). 모델 호출 없음.

    python sft_dpo_inventory/p0_sft_001/analyze.py      # -> analysis.json, items.csv

입력: evaluation/{model}/{set}.json(model = base, gold_only, clean_hybrid; set = sel154, valid98, vendor100, aux_test_v1).
지표·문항 판정은 ab_p0_3/ab_valid98/ab_p0 분석 함수를 그대로 쓴다(`P.item_view`, `V98.extra_view`, `V98.cell_metrics`).
- semantic correctness = category ∈ {match, expected_refusal}
- answerable semantic correctness, refusal correctness, execution completion, grounding failure, grounding_ok
- first-response structural error(`structural_first_response`), malformed JSON(`malformed_first`, `malformed_final`)
부분집합(gold로 고정):
- dt_any / dt_pickup / dt_dropoff / dt_both: gold factors.dimension_target
- od_ne_dt: gold 장소 od_role 집합이 있고 dimension_target이 그 집합에 없다(dataset_stats와 같은 정의, Gap B형)
- gap_a_event: sel154의 사전 분류(root_cause.EXPRESSION == "event", 11문항, Gap A형 사건 표현)
- bucket: gold factors.bucket
- scope_reverse: gold에 값 있는 scope와 값 없는 답 place가 함께 있다
- refusal: expected_outcome != answered
비교(문항 단위, 같은 문항끼리): gold_only − base(H1), clean_hybrid − gold_only(H2), clean_hybrid − base.
- 정답 0/1 차이의 평균, paired bootstrap 95% CI, sign-flip permutation p(`P.paired`, seed 20261009)
- 엇갈린 문항 수(b: 앞 모델만 정답, c: 뒤 모델만 정답)와 exact McNemar 양측 p
- 주 결과는 네 셋을 합친 403문항이다. 셋별 값도 같이 적는다.
"""
import collections
import csv
import importlib.util
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
AB = ROOT / "evaluation/partial_grounding/ab_p0_3"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


A = _load("ab_p0_3_analyze", AB / "analyze.py")
RC = _load("ab_p0_3_root_cause", AB / "root_cause.py")
P, V98 = A.P, A.V98
MODELS = ("base", "r70_json", "r70_full")
SETS = {
    "sel154": ROOT / "evaluation/partial_grounding/ab_p0_3/sel154_gold.yaml",
    "valid98": ROOT / "sft_dpo_inventory/pilot_001_analysis/decision43/valid98_gold.yaml",
    "vendor100": ROOT / "evaluation/vendor100/gold.yaml",
    "aux_test_v1": ROOT / "sft_dpo_inventory/pilot_002/aux_test/aux_test_gold.yaml",
}
PAIRS = (("base", "r70_json"), ("r70_json", "r70_full"), ("base", "r70_full"))
KEYS = ("semantic_correctness", "answerable_semantic_correctness", "refusal_correctness", "execution_completion",
        "grounding_failure", "grounding_ok", "structural_first_response", "malformed_first", "malformed_final",
        "median_eval_count", "median_thinking_chars")


def mcnemar(b, c):
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def subsets_for(set_name, gold):
    out = collections.defaultdict(list)
    for i, item in gold.items():
        payload = P.V.gold_grounding(item) or {}
        f = payload.get("factors") or {}
        concepts = payload.get("concepts") or []
        key = f"{set_name}:{i}"
        dt = f.get("dimension_target")
        roles = {(c.get("attributes") or {}).get("od_role") for c in concepts if c.get("subtype") in ("place", "scope")} - {None}
        if dt:
            out["dt_any"].append(key)
            out[f"dt_{dt}"].append(key)
            if roles and dt not in roles:
                out["od_ne_dt"].append(key)
        if f.get("bucket"):
            out["bucket"].append(key)
        if any(c.get("subtype") == "scope" and c.get("value") for c in concepts) and \
                any(c.get("subtype") == "place" and not c.get("value") for c in concepts):
            out["scope_reverse"].append(key)
        if item.get("expected_outcome", "answered") != "answered":
            out["refusal"].append(key)
        if set_name == "sel154" and RC.EXPRESSION.get(i) == "event":
            out["gap_a_event"].append(key)
    return out


def main():
    views = {m: {} for m in MODELS}
    golds, subsets, missing = {}, collections.defaultdict(list), []
    for set_name, path in SETS.items():
        P.V.GOLD_PATH = path
        gold = {item["id"]: item for item in P.V.load_gold(path)["items"]}
        golds[set_name] = gold
        for k, v in subsets_for(set_name, gold).items():
            subsets[k].extend(v)
        for model in MODELS:
            f = (ROOT / "sft_dpo_inventory/p0_sft_001/evaluation/base" if model == "base" else HERE / "full_eval" / model) / f"{set_name}.json"
            if not f.is_file():
                missing.append(f"{model}/{set_name}")
                continue
            rows = {r["id"]: r for r in json.loads(f.read_text(encoding="utf-8"))["rows"]}
            if set(rows) != set(gold):
                raise SystemExit(f"{model}/{set_name}: 문항 집합이 gold와 다르다")
            for i, row in rows.items():
                v = P.item_view(gold[i], row)
                v.update(V98.extra_view(gold[i], row))
                v["malformed_first"] = v["first_error"] in V98.MALFORMED
                views[model][f"{set_name}:{i}"] = v
    result = {"missing": missing, "sets": {s: len(g) for s, g in golds.items()},
              "subsets": {k: len(v) for k, v in sorted(subsets.items())}}
    groups = {"pooled": None, **{s: [k for k in views["base"] if k.startswith(s + ":")] for s in SETS}}
    complete = [m for m in MODELS if len(views[m]) == sum(len(g) for g in golds.values())]
    result["complete_models"] = complete
    table = {}
    for gname, ids in groups.items():
        for model in complete:
            vs = list(views[model].values()) if ids is None else [views[model][k] for k in ids]
            m = V98.cell_metrics(vs)
            table.setdefault(gname, {})[model] = {k: m.get(k) for k in KEYS} | {"n": len(vs), "correct": sum(v["correct"] for v in vs)}
    result["metrics"] = table
    sub_table = {}
    for sname, ids in sorted(subsets.items()):
        for model in complete:
            vs = [views[model][k] for k in ids]
            sub_table.setdefault(sname, {})[model] = {"n": len(vs), "correct": sum(v["correct"] for v in vs),
                                                      "rate": round(sum(v["correct"] for v in vs) / len(vs), 3) if vs else None,
                                                      "structural_first_response": sum(v["structural"] for v in vs)}
    result["subsets_metrics"] = sub_table
    pairs = {}
    for a, b in PAIRS:
        if a not in complete or b not in complete:
            continue
        for gname, ids in [("pooled", list(views[a]))] + [(s, groups[s]) for s in SETS] + \
                [(f"subset:{k}", v) for k, v in sorted(subsets.items())]:
            if not ids:
                continue
            ca = {k: int(views[a][k]["correct"]) for k in ids}
            cb = {k: int(views[b][k]["correct"]) for k in ids}
            only_a = sum(ca[k] and not cb[k] for k in ids)
            only_b = sum(cb[k] and not ca[k] for k in ids)
            stat = P.paired(ca, cb, ids)
            pairs.setdefault(f"{b}_vs_{a}", {})[gname] = {
                "n": len(ids), "correct": [sum(ca.values()), sum(cb.values())], "diff_mean": round(stat["mean"], 4),
                "ci95": [round(x, 4) for x in stat["ci95"]], "permutation_p": round(stat["permutation_p"], 4),
                f"only_{a}": only_a, f"only_{b}": only_b, "mcnemar_p": round(mcnemar(only_a, only_b), 4),
                "structural": [sum(views[a][k]["structural"] for k in ids), sum(views[b][k]["structural"] for k in ids)]}
    result["pairs"] = pairs
    (HERE / "full_eval" / "analysis.json").write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    with open(HERE / "full_eval" / "items.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["key", *(f"{m}_category" for m in complete), *(f"{m}_structural" for m in complete),
                    *(f"{m}_first_error" for m in complete), "subsets"])
        member = collections.defaultdict(list)
        for k, ids in subsets.items():
            for i in ids:
                member[i].append(k)
        for key in (views[complete[0]] if complete else {}):
            w.writerow([key, *(views[m][key]["category"] for m in complete), *(int(views[m][key]["structural"]) for m in complete),
                        *(views[m][key]["first_error"] or "" for m in complete), ";".join(sorted(member[key]))])
    print(json.dumps({"missing": missing, "complete": complete,
                      "pooled": {m: table.get("pooled", {}).get(m, {}).get("semantic_correctness") for m in complete}},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
