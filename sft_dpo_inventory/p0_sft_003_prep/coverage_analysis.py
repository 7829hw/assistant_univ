# -*- coding: utf-8 -*-
"""H2·H3 분석(PLAN.md 3·4·6·7절). 모델 호출 없음.

    python sft_dpo_inventory/p0_sft_003_prep/coverage_analysis.py   # -> coverage_analysis.json, failure_attribution.csv
"""
import collections
import csv
import importlib.util
import json
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
from training.annotations.inventory import family_key  # noqa: E402

P2 = ROOT / "sft_dpo_inventory/p0_sft_002"
P1 = ROOT / "sft_dpo_inventory/p0_sft_001"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


A = _load("ab_p0_3_analyze", ROOT / "evaluation/partial_grounding/ab_p0_3/analyze.py")
P, V98 = A.P, A.V98
EV = P.V
FIELDS = ("dimension", "dimension_target", "bucket", "aggregation", "rollup", "order", "vicinity", "answer", "taxi_type")


def read_jsonl(path):
    return [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x.strip()]


def feats(payload, expected="answered"):
    """PLAN 3절 feature. payload는 Full gold(평가: gold_grounding, 학습: target_full)."""
    if not payload or payload.get("unsupported") or expected != "answered":
        return {"refusal": expected if expected != "answered" else "unsupported", "measure": None}
    concepts = payload.get("concepts") or []
    f = payload.get("factors") or {}
    locs = [c for c in concepts if c.get("subtype") in ("place", "scope")]
    valued = [c for c in locs if c.get("value")]
    roles = sorted((c.get("attributes") or {}).get("od_role") or "-" for c in valued)
    dt = f.get("dimension_target")
    rset = {r for r in roles if r != "-"}
    measure = next((c.get("subtype") for c in concepts if c.get("concept") in ("AMOUNT", "PROPORTION")), None)
    return {"refusal": None, "measure": measure,
            "dimension": f.get("dimension"), "dimension_target": dt, "od_roles": tuple(roles),
            "od_ne_dt": bool(dt and rset and dt not in rset),
            "bucket": f.get("bucket"), "aggregation": f.get("aggregation"), "rollup": f.get("rollup"),
            "order": f.get("order"), "answer": None if f.get("answer") == "value" else f.get("answer"),
            "vicinity": bool(f.get("vicinity")), "taxi_type": f.get("taxi_type"),
            "n_places": sum(c.get("subtype") == "place" for c in valued),
            "has_scope": any(c.get("subtype") == "scope" for c in valued),
            "answer_place": any(c.get("subtype") == "place" and not c.get("value") for c in locs)}


def place_pattern(ft):
    return None if ft["refusal"] else (ft["n_places"], ft["has_scope"], ft["answer_place"])


def exact_family(payload, ft, expected="answered"):
    if ft["refusal"]:
        return f"refusal:{ft['refusal']}"
    return f"{family_key(payload)}|{place_pattern(ft)}"


def near_family(ft):
    if ft["refusal"]:
        return f"refusal:{ft['refusal']}"
    return json.dumps([ft["measure"], ft["dimension"] is not None, ft["dimension_target"], ft["bucket"],
                       ft["n_places"] > 0, ft["has_scope"]])


def coverage(ft, ef, nf, train):
    same = lambda key: sum(t["ft"].get(key) == ft.get(key) for t in train)  # noqa: E731
    return {"exact_family_count": sum(t["exact"] == ef for t in train),
            "near_family_count": sum(t["near"] == nf for t in train),
            "same_measure_count": same("measure") if ft.get("measure") else 0,
            "same_dimension_target_count": same("dimension_target") if ft.get("dimension_target") else None,
            "same_bucket_count": same("bucket") if ft.get("bucket") else None,
            "same_od_role_pattern_count": same("od_roles") if not ft["refusal"] else 0,
            "same_scope_pattern_count": sum(place_pattern(t["ft"]) == place_pattern(ft) for t in train) if not ft["refusal"] else 0}


def sparse(cov):
    return cov["exact_family_count"] == 0 and cov["near_family_count"] <= 1


def train_set(rows):
    out = []
    for r in rows:
        m = r["metadata"]
        ft = feats(m["target_full"])
        out.append({"id": m["source_record_id"], "source": m["source"], "ft": ft,
                    "exact": exact_family(m["target_full"], ft), "near": near_family(ft), "payload": m["target_full"]})
    return out


def dist(train, keys=("measure", "dimension", "dimension_target", "od_roles", "od_ne_dt", "bucket", "aggregation",
                      "rollup", "order", "vicinity", "taxi_type", "has_scope", "n_places", "answer")):
    return {k: dict(collections.Counter(str(t["ft"].get(k)) for t in train).most_common()) for k in keys}


def diff_kinds(diffs):
    """grounding diff → (omission 필드 목록, commission 필드·예측값 목록)."""
    omit, commit = [], []
    for d in diffs:
        key, want, got = (d[0], d[1], d[2]) if isinstance(d, list) and len(d) == 3 else (d if isinstance(d, str) else d[0], None, None)
        if key == "no_grounding":
            omit.append("grounding")
            continue
        if key in ("places", "scopes"):
            w, g = want or [], got or []
            if any(x not in g for x in w):
                omit.append(key)
            if any(x not in w for x in g):
                commit.append((key, None))
            continue
        if key == "factor:aggregation_spec":
            for i, name in enumerate(("bucket", "aggregation", "rollup", "answer")):
                wv = want[i] if want and i < len(want) else None
                gv = got[i] if got and i < len(got) else None
                if wv not in (None, "unspecified") and gv in (None, "unspecified"):
                    omit.append(name)
                elif gv not in (None, "unspecified") and gv != wv:
                    commit.append((name, gv))
            continue
        field = key.split(":", 1)[-1]
        if want is not None and got is None:
            omit.append(field)
        elif got is not None and got != want:
            commit.append((field, got))
    return omit, commit


def main():
    v006 = train_set(read_jsonl(ROOT / "training/generated/reviewed_gold_v006_p0/sft_train.jsonl"))
    r70 = train_set(read_jsonl(ROOT / "training/generated/p0_sft_002/r70/sft_train.jsonl"))
    r70_ids = {t["id"] for t in r70}
    # 9·10절: 분포와 coverage ratio
    dv, dr = dist(v006), dist(r70)
    ratio = {}
    named = {"bucket": lambda t: t["ft"].get("bucket") is not None,
             "dimension_target": lambda t: t["ft"].get("dimension_target") is not None,
             "dt_pickup": lambda t: t["ft"].get("dimension_target") == "pickup",
             "dt_dropoff": lambda t: t["ft"].get("dimension_target") == "dropoff",
             "dt_both": lambda t: t["ft"].get("dimension_target") == "both",
             "od_ne_dt": lambda t: t["ft"].get("od_ne_dt"),
             "od_role_any": lambda t: bool([r for r in t["ft"].get("od_roles", ()) if r != "-"]),
             "od_role_both": lambda t: "both" in t["ft"].get("od_roles", ()),
             "aggregation": lambda t: t["ft"].get("aggregation") is not None,
             "rollup": lambda t: t["ft"].get("rollup") is not None,
             "order": lambda t: t["ft"].get("order") is not None,
             "vicinity": lambda t: t["ft"].get("vicinity"),
             "scope": lambda t: t["ft"].get("has_scope"),
             "place": lambda t: (t["ft"].get("n_places") or 0) > 0,
             "dimension_h3": lambda t: t["ft"].get("dimension") == "h3",
             "dimension_emd": lambda t: t["ft"].get("dimension") == "emd",
             "dimension_sigungu": lambda t: t["ft"].get("dimension") == "sigungu",
             "dimension_sido": lambda t: t["ft"].get("dimension") == "sido",
             "dimension_dayofweek": lambda t: t["ft"].get("dimension") == "dayofweek",
             "gap_a": lambda t: t["source"] == "augment_dt_event", "gap_b": lambda t: t["source"] == "augment_od_vs_dt"}
    for m in sorted({t["ft"]["measure"] for t in v006 if t["ft"]["measure"]}):
        named[f"measure_{m}"] = (lambda mm: lambda t: t["ft"].get("measure") == mm)(m)
    for name, fn in named.items():
        a, b = sum(map(fn, v006)), sum(map(fn, r70))
        ratio[name] = {"v006": a, "r70": b, "ratio": round(b / a, 3) if a else None}
    families = {"v006_exact": len({t["exact"] for t in v006}), "r70_exact": len({t["exact"] for t in r70}),
                "v006_near": len({t["near"] for t in v006}), "r70_near": len({t["near"] for t in r70})}

    # 6절: panel 그룹과 regression
    panel = json.loads((P2 / "diagnostic_panel.json").read_text(encoding="utf-8"))
    stratum = {p["key"]: p["stratum"] for p in panel["items"]}
    EV.GOLD_PATH = P2 / "diagnostic_panel_gold.yaml"
    gold = {i["id"]: i for i in EV.load_gold(EV.GOLD_PATH)["items"]}
    rows = {"base": {}, "r70_json": {}, "r70_full": {}}
    for key in gold:
        s, i = key.split(":", 1)
        rows["base"][key] = {r["id"]: r for r in json.loads((P1 / f"evaluation/base/{s}.json").read_text(encoding="utf-8"))["rows"]}[i]
    for arm in ("json", "full"):
        rows[f"r70_{arm}"] = {r["id"]: r for r in json.loads((P2 / f"mechanism_probe/r70_{arm}.json").read_text(encoding="utf-8"))["rows"]}
    raws = collections.defaultdict(list)
    for line in (ROOT / "training/generated/p0_sft_002/mechanism_raw/probe_r70_full.jsonl").read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        raws[r["id"]].append(r)
    base_raw = {}
    for s in ("sel154", "valid98", "vendor100", "aux_test_v1"):
        for line in (ROOT / f"training/generated/p0_sft_001/eval_raw/base_{s}.jsonl").read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            if r["call"] == 0:
                base_raw[f"{s}:{r['id']}"] = r
    full_raw0 = {k: v[0] for k, v in raws.items() if v and v[0]["call"] == 0}
    top_value = {f: collections.Counter(t["ft"].get(f) for t in r70 if t["ft"].get(f) is not None).most_common(1)
                 for f in FIELDS + ("measure",)}
    items, groups = [], collections.Counter()
    for key, item in gold.items():
        payload = EV.gold_grounding(item)
        ft = feats(payload, item.get("expected_outcome", "answered"))
        ef, nf = exact_family(payload, ft), near_family(ft)
        cov = coverage(ft, ef, nf, r70)
        views = {}
        for m in rows:
            v = P.item_view(item, rows[m][key])
            v.update(V98.extra_view(item, rows[m][key]))
            v["malformed_first"] = v["first_error"] in V98.MALFORMED
            views[m] = v
        bc, fc = views["base"]["correct"], views["r70_full"]["correct"]
        group = "A" if bc and fc else "B" if bc else "C" if fc else "D"
        groups[group] += 1
        _, diffs = EV.grounding_check(item, rows["r70_full"][key].get("grounding"))
        omit, commit = diff_kinds(diffs or [])
        related = [t["id"] for t in r70 if t["exact"] == ef] or [t["id"] for t in r70 if t["near"] == nf] or \
            ([t["id"] for t in r70 if ft.get("measure") and t["ft"].get("measure") == ft["measure"]])
        tags = []
        if group == "B":
            if sparse(cov):
                tags.append("COVERAGE_GAP")
            if views["r70_full"]["structural"] or views["r70_full"]["malformed_first"]:
                tags.append("STRUCTURAL_FAILURE")
            if any(r["done_reason"] == "length" for r in raws.get(key, [])):
                tags.append("GENERATION_LIMIT")
            if omit and rows["r70_full"][key].get("grounding"):
                tags.append("SEMANTIC_OMISSION")
            near_vals = collections.defaultdict(set)
            for t in r70:
                if t["near"] == nf:
                    for f in FIELDS:
                        near_vals[f].add(t["ft"].get(f))
            for field, val in commit:
                if val is not None and ((top_value.get(field) and top_value[field][0][0] == val) or val in near_vals.get(field, set())):
                    tags.append("TRACE_PATTERN_TRANSFER")
                    break
            if not tags:
                tags.append("UNCLEAR")
        g_full = rows["r70_full"][key].get("grounding")
        g_base = rows["base"][key].get("grounding")
        items.append({"key": key, "stratum": stratum[key], "question": item["question"], "group": group,
                      "exact_family": ef[:12], "near_family": nf, "features": {k: (list(v) if isinstance(v, tuple) else v) for k, v in ft.items()},
                      "base": views["base"]["category"], "r70_json": views["r70_json"]["category"], "r70_full": views["r70_full"]["category"],
                      "r70_json_correct": views["r70_json"]["correct"],
                      "coverage": cov, "sparse": sparse(cov), "tags": tags, "omission": omit,
                      "commission": [[f, v] for f, v in commit], "diffs": diffs,
                      "related_train_ids": related[:12], "related_train_n": len(related),
                      "base_grounding": g_base, "r70_full_grounding": g_full,
                      "h3": {"base_json_chars": len(json.dumps(g_base, ensure_ascii=False)) if g_base else 0,
                             "full_json_chars": len(json.dumps(g_full, ensure_ascii=False)) if g_full else 0,
                             "base_thinking_chars": len(base_raw[key]["raw_text"].split("</think>")[0]) if key in base_raw else None,
                             "full_thinking_chars": len(full_raw0[key]["raw_text"].split("</think>")[0]) if key in full_raw0 else None}})
    B = [x for x in items if x["group"] == "B"]
    C = [x for x in items if x["group"] == "C"]
    tag_counts = collections.Counter(t for x in B for t in x["tags"])
    by_cov = {}
    for name, sel in (("sparse", lambda x: x["sparse"]), ("covered", lambda x: not x["sparse"])):
        xs = [x for x in items if sel(x) and x["base"] in ("match", "expected_refusal")]
        by_cov[name] = {"base_correct": len(xs), "r70_full_wrong": sum(x["group"] == "B" for x in xs),
                        "r70_json_wrong": sum(not x["r70_json_correct"] for x in xs)}

    # 6절: H3 지표
    def h3(model):
        out = collections.Counter()
        n_place = n_dt = n_bucket = 0
        lens, nf_, nc_ = [], [], []
        for key, item in gold.items():
            gp = EV.gold_grounding(item) or {}
            gf = gp.get("factors") or {}
            g = rows[model][key].get("grounding") or {}
            f = g.get("factors") or {}
            cs = g.get("concepts") or []
            if g:
                lens.append(len(json.dumps(g, ensure_ascii=False)))
                nf_.append(len(f))
                nc_.append(len(cs))
            if any(c.get("subtype") == "place" and c.get("value") for c in gp.get("concepts") or []):
                n_place += 1
                out["place_included"] += any(c.get("subtype") == "place" and c.get("value") for c in cs)
            for k, cnt in (("dimension_target", "dt"), ("bucket", "bucket")):
                if gf.get(k):
                    out[f"{cnt}_gold"] += 1
                    out[f"{cnt}_included"] += bool(f.get(k))
                elif f.get(k):
                    out[f"{cnt}_overinclude"] += 1
        return {"grounding_present": len(lens), "json_chars_median": statistics.median(lens) if lens else None,
                "factor_count_mean": round(statistics.mean(nf_), 2) if nf_ else None,
                "concept_count_mean": round(statistics.mean(nc_), 2) if nc_ else None,
                "place_gold": n_place, **dict(out)}
    h3_metrics = {m: h3(m) for m in rows}
    h3_metrics["thinking_chars_median"] = {
        "base": statistics.median(len(r["raw_text"].split("</think>")[0]) for k, r in base_raw.items() if k in gold),
        "r70_full": statistics.median(len(r["raw_text"].split("</think>")[0]) for r in full_raw0.values())}
    silent = sum(1 for x in B if "SEMANTIC_OMISSION" in x["tags"] and not {"STRUCTURAL_FAILURE", "GENERATION_LIMIT"} & set(x["tags"]))

    # 7절 보조: 403문항, family가 v006에 있는가
    v006_exact = {t["exact"] for t in v006}
    aux = {}
    for model in ("gold_only", "clean_hybrid"):
        cnt = collections.Counter()
        for s, path in (("sel154", "evaluation/partial_grounding/ab_p0_3/sel154_gold.yaml"),
                        ("valid98", "sft_dpo_inventory/pilot_001_analysis/decision43/valid98_gold.yaml"),
                        ("vendor100", "evaluation/vendor100/gold.yaml"),
                        ("aux_test_v1", "sft_dpo_inventory/pilot_002/aux_test/aux_test_gold.yaml")):
            EV.GOLD_PATH = ROOT / path
            g = {i["id"]: i for i in EV.load_gold(EV.GOLD_PATH)["items"]}
            base = {r["id"]: r for r in json.loads((P1 / f"evaluation/base/{s}.json").read_text(encoding="utf-8"))["rows"]}
            sft = {r["id"]: r for r in json.loads((P1 / f"evaluation/{model}/{s}.json").read_text(encoding="utf-8"))["rows"]}
            for i, item in g.items():
                payload = EV.gold_grounding(item)
                ft = feats(payload, item.get("expected_outcome", "answered"))
                cov_ = "covered" if exact_family(payload, ft) in v006_exact else "uncovered"
                bc = base[i]["category"] in ("match", "expected_refusal")
                sc = sft[i]["category"] in ("match", "expected_refusal")
                cnt[f"{cov_}_n"] += 1
                cnt[f"{cov_}_base_correct"] += bc
                cnt[f"{cov_}_regression"] += bc and not sc
                cnt[f"{cov_}_improvement"] += sc and not bc
        aux[model] = dict(cnt)
        for c in ("covered", "uncovered"):
            aux[model][f"{c}_regression_rate_of_base_correct"] = round(cnt[f"{c}_regression"] / cnt[f"{c}_base_correct"], 3) if cnt[f"{c}_base_correct"] else None

    result = {"families": families, "distribution": {"v006": dv, "r70": dr}, "coverage_ratio": ratio,
              "panel_groups": dict(groups), "regression_tags": dict(tag_counts), "silent_omission_regressions": silent,
              "regression_n": len(B), "improvement_n": len(C), "by_coverage": by_cov,
              "improvements": [{"key": x["key"], "stratum": x["stratum"], "coverage": x["coverage"], "related_train_n": x["related_train_n"],
                                "base": x["base"], "r70_full": x["r70_full"]} for x in C],
              "h3": h3_metrics, "aux_403_family_coverage": aux, "items": items}
    (HERE / "coverage_analysis.json").write_text(json.dumps(result, ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8")
    with open(HERE / "failure_attribution.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["item_id", "group", "stratum", "near_family", "base_result", "r70_full_result", "r70_json_result", "tags",
                    "exact_family_count", "near_family_count", "same_measure_count", "omission", "commission", "diffs",
                    "base_grounding", "r70_full_grounding", "related_train_ids"])
        for x in sorted(items, key=lambda x: (x["group"], x["key"])):
            if x["group"] not in ("B", "C"):
                continue
            w.writerow([x["key"], x["group"], x["stratum"], x["near_family"], x["base"], x["r70_full"], x["r70_json"],
                        ";".join(x["tags"]), x["coverage"]["exact_family_count"], x["coverage"]["near_family_count"],
                        x["coverage"]["same_measure_count"], ";".join(x["omission"]),
                        json.dumps(x["commission"], ensure_ascii=False), json.dumps(x["diffs"], ensure_ascii=False),
                        json.dumps(x["base_grounding"], ensure_ascii=False), json.dumps(x["r70_full_grounding"], ensure_ascii=False),
                        ";".join(x["related_train_ids"])])
    print(json.dumps({k: result[k] for k in ("families", "panel_groups", "regression_tags", "silent_omission_regressions",
                                             "by_coverage", "aux_403_family_coverage")}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
