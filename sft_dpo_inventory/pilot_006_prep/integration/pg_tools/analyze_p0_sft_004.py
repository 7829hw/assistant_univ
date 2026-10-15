# -*- coding: utf-8 -*-
# [pilot_006 준비 W3 이식] 원본: geoflow/partial-grounding 커밋 ab9d215의 sft_dpo_inventory/p0_sft_004/analyze.py. 본문은 원본 그대로다(아래 '이식 수정' 줄 제외).
# 원본의 경로 상수(ROOT 등)는 원 위치 기준이라 이 위치에서 바로 돌리려면 경로 인자를 확인한다. 참고값 경로(HF greedy·Ollama, 다른 장비)의 기록용 도구다.
"""p0_sft_004 분석(PLAN.md 8–10절, 결과를 보기 전에 고정). 모델 호출 0(thinking token 수는 tokenizer CPU).

    HF_HOME=/data/hwkim/path_repeat_001/hf-cache HF_HUB_OFFLINE=1 /data/hwkim/path_repeat_001/venv/py/bin/python \
        sft_dpo_inventory/p0_sft_004/analyze.py
    # -> analysis/metrics.json, analysis/paired_transitions.csv, analysis/error_attribution.csv, analysis/reasoning_samples.jsonl,
    #    analysis/recall.json

입력: evaluation/{base,full154,json154}/{sel154,valid98,vendor100,aux_test_v1}.json, raw는 training/generated/p0_sft_004/eval_raw/,
train recall은 train_recall/{model}.jsonl, 부분집합은 subsets.json(평가 전 commit).
- 문항 판정·지표는 p0_sft_001 analyze와 같은 함수(`P.item_view`, `V98.extra_view`, `V98.cell_metrics`)다.
  semantic correctness = category ∈ {match, expected_refusal}. 기존 `_grounding_view`·채점은 바꾸지 않는다.
- thinking 지표(첫 plan 호출): emission(thinking 글자 > 0이고 done_reason stop), thinking 글자 p50·p90,
  thinking token p50·p90(raw 원문의 `</think>` 앞 부분을 Qwen3-8B tokenizer로 센다), direct-JSON 첫 응답 비율(thinking 0),
  생성 token(eval_count) p50·p90, 문항 wall 시간 p50.
- 비교: full154−base, json154−base, full154−json154. 차이 평균, paired bootstrap 95% CI·permutation p(`P.paired`, seed 고정),
  exact McNemar, 전이 4칸.
- 오류 분류(자동, 다중 tag): grounding_diffs와 범주에서 PLACE_OMISSION, OD_ROLE_ERROR, DIM_TARGET_ERROR, DIMENSION_ERROR,
  AGGREGATION_ERROR, BUCKET_ERROR, MEASURE_ERROR, STRUCTURAL_ERROR, REFUSAL_ERROR, GENERATION_FAILURE, OTHER.
- gate(PLAN 9절)·candidate 규칙(PLAN 10절)을 그대로 계산한다.
- reasoning 표본: 모델마다 정답 10 + 오답 10, sha256(model:key) 오름차순(결정적). 사람 검토는 REPORT에서 한다.
"""
import collections
import csv
import hashlib
import importlib.util
import json
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
spec = importlib.util.spec_from_file_location("a001", ROOT / "sft_dpo_inventory/p0_sft_001/analyze.py")
A1 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(A1)
P, V98, SETS, mcnemar = A1.P, A1.V98, A1.SETS, A1.mcnemar
MODELS = ("base", "full154", "json154")
PAIRS = (("base", "full154"), ("base", "json154"), ("json154", "full154"))
RAW = ROOT / "training/generated/p0_sft_004/eval_raw"
KEYS = A1.KEYS
TAGS = ("PLACE_OMISSION", "OD_ROLE_ERROR", "DIM_TARGET_ERROR", "DIMENSION_ERROR", "AGGREGATION_ERROR", "BUCKET_ERROR",
        "MEASURE_ERROR", "STRUCTURAL_ERROR", "REFUSAL_ERROR", "GENERATION_FAILURE", "OTHER")
SUBSET_ORDER = ("dt_any", "dt_pickup", "dt_dropoff", "dt_both", "od_ne_dt", "bucket", "aggregation", "order", "h3", "sido",
                "sigungu", "emd", "gap_a_like", "gap_b_like", "implicit_endpoint_all", "implicit_endpoint_verb",
                "scope_reverse", "refusal")


def pct(xs, p):
    xs = sorted(x for x in xs if x is not None)
    return xs[min(len(xs) - 1, int(round(p / 100 * (len(xs) - 1))))] if xs else None


def error_tags(row, view):
    tags = set()
    cat = row["category"]
    if cat in ("match", "expected_refusal"):
        return []
    if cat in ("answered_instead_of_refusal", "wrong_refusal_kind", "wrong_refusal_reason", "refused_unsupported", "refused_clarification"):
        tags.add("REFUSAL_ERROR")
    calls = row.get("llm_calls") or []
    first = calls[0] if calls else {}
    if not calls or first.get("done_reason") == "length" or not (first.get("content") or "").strip():
        tags.add("GENERATION_FAILURE")
    if view.get("structural"):
        tags.add("STRUCTURAL_ERROR")
    for d in row.get("grounding_diffs") or []:
        if d == "no_grounding":
            tags.add("STRUCTURAL_ERROR")
            continue
        field = d[0] if isinstance(d, list) else str(d)
        if field in ("places", "scopes"):
            a, b = d[1] or [], d[2] or []
            name = lambda x: tuple(x[:2]) if isinstance(x, list) else x
            if sorted(map(name, a)) == sorted(map(name, b)):
                tags.add("OD_ROLE_ERROR")
            else:
                tags.add("PLACE_OMISSION")
                if {x[-1] for x in a if isinstance(x, list)} != {x[-1] for x in b if isinstance(x, list)}:
                    tags.add("OD_ROLE_ERROR")
        elif field == "factor:dimension_target":
            tags.add("DIM_TARGET_ERROR")
        elif field == "factor:dimension":
            tags.add("DIMENSION_ERROR")
        elif field in ("factor:bucket", "factor:answer", "factor:rollup"):
            tags.add("BUCKET_ERROR")
        elif field == "factor:aggregation_spec":
            a, b = d[1], d[2]
            if not isinstance(a, list) or not isinstance(b, list) or a[:1] != b[:1]:
                tags.add("BUCKET_ERROR")
            if not isinstance(a, list) or not isinstance(b, list) or a[1:] != b[1:]:
                tags.add("AGGREGATION_ERROR")
        elif field == "factor:aggregation":
            tags.add("AGGREGATION_ERROR")
        elif field == "measure":
            tags.add("MEASURE_ERROR")
        else:
            tags.add("OTHER")
    if row.get("outcome") == "failed" and not tags:
        tags.add("STRUCTURAL_ERROR")
    return sorted(tags) or ["OTHER"]


def thinking_tokens(tok, raw_rows):
    out = {}
    for r in raw_rows:
        if r.get("call") != 0:
            continue
        text = r.get("raw_text") or ""
        head = text.split("</think>", 1)[0] if "</think>" in text else (text if "<think>" in text else "")
        head = head.split("<think>", 1)[-1]
        out[r["id"]] = len(tok(head, add_special_tokens=False)["input_ids"]) if head.strip() else 0
    return out


def main():
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained("Qwen/Qwen3-8B", revision="b968826d9c46dd6066d109eabc6255188de91218")
    subsets = json.loads((HERE / "subsets.json").read_text(encoding="utf-8"))["subsets"]
    views, rows_all, think = {m: {} for m in MODELS}, {m: {} for m in MODELS}, {m: {} for m in MODELS}
    golds = {}
    for set_name, path in SETS.items():
        P.V.GOLD_PATH = path
        gold = {item["id"]: item for item in P.V.load_gold(path)["items"]}
        golds[set_name] = gold
        for model in MODELS:
            f = HERE / "evaluation" / model / f"{set_name}.json"
            rows = {r["id"]: r for r in json.loads(f.read_text(encoding="utf-8"))["rows"]}
            if set(rows) != set(gold):
                raise SystemExit(f"{model}/{set_name}: 문항 집합이 gold와 다르다")
            raw = [json.loads(x) for x in (RAW / f"{model}_{set_name}.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
            tt = thinking_tokens(tok, raw)
            for i, row in rows.items():
                v = P.item_view(gold[i], row)
                v.update(V98.extra_view(gold[i], row))
                v["malformed_first"] = v["first_error"] in V98.MALFORMED
                key = f"{set_name}:{i}"
                views[model][key] = v
                rows_all[model][key] = row
                first = (row.get("llm_calls") or [{}])[0]
                think[model][key] = {"chars": first.get("thinking_chars") or 0, "tokens": tt.get(i),
                                     "emitted": bool(first.get("thinking_chars")) and first.get("done_reason") == "stop",
                                     "direct_json": not first.get("thinking_chars"), "eval_count": first.get("eval_count"),
                                     "wall_s": v.get("wall_s")}
    keys = list(views["base"])
    result = {"n": len(keys), "subset_sizes": {k: len(subsets.get(k, [])) for k in SUBSET_ORDER}}
    metrics = {}
    for gname, ids in [("pooled", keys)] + [(s, [k for k in keys if k.startswith(s + ":")]) for s in SETS]:
        for m in MODELS:
            vs = [views[m][k] for k in ids]
            cm = V98.cell_metrics(vs)
            metrics.setdefault(gname, {})[m] = {k: cm.get(k) for k in KEYS} | {"n": len(vs), "correct": sum(v["correct"] for v in vs)}
    result["metrics"] = metrics
    th = {}
    for m in MODELS:
        t = list(think[m].values())
        th[m] = {"n": len(t), "emission_rate": round(sum(x["emitted"] for x in t) / len(t), 4),
                 "direct_json_rate": round(sum(x["direct_json"] for x in t) / len(t), 4),
                 "thinking_chars_p50": pct([x["chars"] for x in t], 50), "thinking_chars_p90": pct([x["chars"] for x in t], 90),
                 "thinking_tokens_p50": pct([x["tokens"] for x in t], 50), "thinking_tokens_p90": pct([x["tokens"] for x in t], 90),
                 "eval_count_p50": pct([x["eval_count"] for x in t], 50), "eval_count_p90": pct([x["eval_count"] for x in t], 90),
                 "wall_s_p50": pct([x["wall_s"] for x in t], 50)}
    result["thinking"] = th
    sub = {}
    for s in SUBSET_ORDER:
        ids = subsets.get(s, [])
        for m in MODELS:
            vs = [views[m][k] for k in ids]
            sub.setdefault(s, {})[m] = {"n": len(vs), "correct": sum(v["correct"] for v in vs),
                                        "rate": round(sum(v["correct"] for v in vs) / len(vs), 4) if vs else None,
                                        "structural": sum(v["structural"] for v in vs)}
    result["subsets"] = sub
    pairs, trans_rows = {}, []
    for a, b in PAIRS:
        for gname, ids in [("pooled", keys)] + [(s, [k for k in keys if k.startswith(s + ":")]) for s in SETS] + \
                [(f"subset:{s}", subsets.get(s, [])) for s in SUBSET_ORDER]:
            if not ids:
                continue
            ca = {k: int(views[a][k]["correct"]) for k in ids}
            cb = {k: int(views[b][k]["correct"]) for k in ids}
            stat = P.paired(ca, cb, ids)
            t = collections.Counter((ca[k], cb[k]) for k in ids)
            pairs.setdefault(f"{b}_vs_{a}", {})[gname] = {
                "n": len(ids), "correct": [sum(ca.values()), sum(cb.values())], "diff_pp": round(100 * stat["mean"], 2),
                "ci95_pp": [round(100 * x, 2) for x in stat["ci95"]], "permutation_p": round(stat["permutation_p"], 4),
                "transitions": {"c_c": t[(1, 1)], "c_w": t[(1, 0)], "w_c": t[(0, 1)], "w_w": t[(0, 0)]},
                "mcnemar_p": round(mcnemar(t[(1, 0)], t[(0, 1)]), 4),
                "structural": [sum(views[a][k]["structural"] for k in ids), sum(views[b][k]["structural"] for k in ids)]}
        for k in keys:
            x, y = views[a][k]["correct"], views[b][k]["correct"]
            if x != y:
                member = [s for s in SUBSET_ORDER if k in subsets.get(s, [])]
                trans_rows.append({"pair": f"{b}_vs_{a}", "key": k, "question": rows_all[a][k]["question"],
                                   "transition": "c_w" if x else "w_c", f"cat_a": rows_all[a][k]["category"],
                                   "cat_b": rows_all[b][k]["category"],
                                   "tags_a": ";".join(error_tags(rows_all[a][k], views[a][k])),
                                   "tags_b": ";".join(error_tags(rows_all[b][k], views[b][k])), "subsets": ";".join(member)})
    result["pairs"] = pairs
    err = collections.defaultdict(collections.Counter)
    err_rows = []
    for m in MODELS:
        for k in keys:
            tg = error_tags(rows_all[m][k], views[m][k])
            for t in tg:
                err[m][t] += 1
            if tg:
                err_rows.append({"model": m, "key": k, "category": rows_all[m][k]["category"], "tags": ";".join(tg),
                                 "diffs": json.dumps(rows_all[m][k].get("grounding_diffs"), ensure_ascii=False)[:400]})
    result["error_taxonomy"] = {m: {t: err[m][t] for t in TAGS} for m in MODELS}
    # gate(PLAN 9절)
    def g(m):
        pm, pb = metrics["pooled"][m], metrics["pooled"]["base"]
        s = lambda name, mm: sub[name][mm]["rate"]
        gates = {"1_overall_within_2pp": pm["semantic_correctness"] >= pb["semantic_correctness"] - 0.02,
                 "2_structural_le_base": pm["structural_first_response"] <= pb["structural_first_response"],
                 "3_dt_ge_base": s("dt_any", m) >= s("dt_any", "base"),
                 "4_bucket_within_5pp": s("bucket", m) >= s("bucket", "base") - 0.05,
                 "5_thinking_ge_95": th[m]["emission_rate"] >= 0.95,
                 "6_malformed_le_base": pm["malformed_first"] <= pb["malformed_first"]}
        strong = (pm["semantic_correctness"] >= pb["semantic_correctness"] and s("dt_any", m) > s("dt_any", "base")
                  and pm["structural_first_response"] < pb["structural_first_response"] and th[m]["emission_rate"] >= 0.95)
        return {"gates": gates, "viable": all(gates.values()), "strong_success": strong}
    gates = {m: g(m) for m in ("full154", "json154")}
    result["gates"] = gates
    viable = [m for m in ("full154", "json154") if gates[m]["viable"]]
    if not viable:
        cand, why = "NONE", "두 arm 모두 viable gate 미통과"
    elif len(viable) == 1:
        cand, why = viable[0], "한 arm만 viable"
    else:
        f_, j_ = metrics["pooled"]["full154"]["semantic_correctness"], metrics["pooled"]["json154"]["semantic_correctness"]
        if abs(f_ - j_) >= 0.01:
            cand, why = ("full154" if f_ > j_ else "json154"), "overall semantic 차이 ≥ 1.0pp"
        else:
            cand, why = None, "tie(<1.0pp) → tie-break"
            for name, better in (("dt_any", lambda a, b: a > b), ("structural", lambda a, b: a < b),
                                 ("bucket", lambda a, b: a > b), ("implicit_endpoint_all", lambda a, b: a > b)):
                if name == "structural":
                    a_, b_ = metrics["pooled"]["full154"]["structural_first_response"], metrics["pooled"]["json154"]["structural_first_response"]
                else:
                    a_, b_ = sub[name]["full154"]["rate"], sub[name]["json154"]["rate"]
                if a_ != b_:
                    cand, why = ("full154" if better(a_, b_) else "json154"), f"tie-break: {name}"
                    break
            if cand is None:
                cand, why = "full154", "tie-break 전부 동률 → 사전 규칙 없음(보고)"
    result["candidate"] = {"viable": viable, "candidate": cand, "reason": why}
    # reasoning 표본
    samples = []
    for m in MODELS:
        order = sorted(keys, key=lambda k: hashlib.sha256(f"{m}:{k}".encode()).hexdigest())
        raw_by = {}
        for s in SETS:
            for x in (RAW / f"{m}_{s}.jsonl").read_text(encoding="utf-8").splitlines():
                x = json.loads(x)
                if x.get("call") == 0:
                    raw_by[f"{s}:{x['id']}"] = x["raw_text"]
        for want, n in ((True, 10), (False, 10)):
            for k in [k for k in order if bool(views[m][k]["correct"]) == want][:n]:
                samples.append({"model": m, "key": k, "correct": want, "category": rows_all[m][k]["category"],
                                "question": rows_all[m][k]["question"], "raw_text": raw_by.get(k),
                                "grounding_diffs": rows_all[m][k].get("grounding_diffs")})
    out = HERE / "analysis"
    out.mkdir(exist_ok=True)
    (out / "metrics.json").write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    with open(out / "paired_transitions.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(trans_rows[0]) if trans_rows else ["pair"])
        w.writeheader()
        w.writerows(trans_rows)
    with open(out / "error_attribution.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["model", "key", "category", "tags", "diffs"])
        w.writeheader()
        w.writerows(err_rows)
    with open(out / "reasoning_samples.jsonl", "w", encoding="utf-8") as f:
        for s in samples:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")
    # train recall
    rec = {}
    for m in MODELS:
        p = HERE / "train_recall" / f"{m}.jsonl"
        if not p.exists():
            continue
        rs = [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines()[1:] if x.strip()]
        canon = [r for r in rs if r["canonical"]]
        by_src = collections.defaultdict(list)
        for r in rs:
            by_src[r["reasoning_source"]].append(r)
        rec[m] = {"n": len(rs), "exact": sum(r["category"] == "EXACT_OR_SEMANTIC_MATCH" for r in rs),
                  "categories": dict(collections.Counter(r["category"] for r in rs)),
                  "thinking_rate": round(sum(r["thinking_emitted"] for r in rs) / len(rs), 4),
                  "unparseable": sum(r["category"] == "UNPARSEABLE" for r in rs),
                  "by_source": {s: {"n": len(v), "exact": sum(r["category"] == "EXACT_OR_SEMANTIC_MATCH" for r in v)} for s, v in by_src.items()},
                  "canonical": {r["item_id"]: {"category": r["category"], "slots": r["slots"], "gold_slots": r["gold_slots"],
                                               "dt_ok": r["slots"]["dimension_target"] == r["gold_slots"]["dimension_target"],
                                               "od_ok": r["slots"]["od_roles"] == r["gold_slots"]["od_roles"],
                                               "h3_text_bad": any((t or "").strip() in ("H3 셀", "H3셀", "셀") for t in r["slots"]["measure_texts"]),
                                               "thinking_emitted": r["thinking_emitted"]} for r in canon}}
    (out / "recall.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"pooled": {m: metrics["pooled"][m]["semantic_correctness"] for m in MODELS}, "thinking": th,
                      "gates": gates, "candidate": result["candidate"],
                      "recall": {m: {k: v[k] for k in ("n", "exact", "thinking_rate")} for m, v in rec.items()}},
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
