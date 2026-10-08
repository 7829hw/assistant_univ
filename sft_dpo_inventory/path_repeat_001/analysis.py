# -*- coding: utf-8 -*-
"""path_repeat_001 분석(모델 호출 없음). 규칙은 PLAN.md 6절(실행 전에 고정)을 그대로 따른다.

    python sft_dpo_inventory/path_repeat_001/analysis.py [--greedy-only]

- 채점: ``baseline_conditions_001/compare_cells.py``의 ``load_cell()``(grounding_check 재채점, v4, U1–U4, 보고 분류).
- 오류 유형(6.5절)은 최종 grounding을 gold와 다시 비교한 ``grounding_check`` 차이와 ``error_code``로 판별한다.
- 결과는 ``analysis.json``. 질문 문장은 넣지 않는다(문항 id만).
- 업체 100 결과는 경로 진단 기록으로만 쓴다(결정 56). 판정·학습·선택에 쓰지 않는다.
"""
import argparse
import importlib.util
import json
import statistics
import sys
from collections import Counter
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
_spec = importlib.util.spec_from_file_location(
    "compare_cells", ROOT / "sft_dpo_inventory/baseline_conditions_001/compare_cells.py")
C = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(C)
import evaluate_vendor100 as EV  # noqa: E402

RUNS = HERE / "runs"
OLD = {"hf": ROOT / "sft_dpo_inventory/thinking_prep_001/hf_e/HF-E_run1.json",
       "ollama": ROOT / "sft_dpo_inventory/pilot_prep_003/ollama/E.json"}
OLD_HF_RAW = ROOT / "training/generated/thinking_prep_001/HF-E_run1_raw.jsonl"
NEW_GREEDY = {"hf": RUNS / "hf_greedy.json", "ollama": RUNS / "ollama_greedy.json"}
NEW_HF_RAW = ROOT / "training/generated/path_repeat_001/hf_greedy_raw.jsonl"
SAMPLES = {path: [RUNS / f"{path}_sample_r{r}.json" for r in range(1, 6)] for path in ("hf", "ollama")}
NAMES = {"hf": "HF Qwen3-8B (BF16)", "ollama": "Ollama qwen3:8b (Q4_K_M)"}
OLD_SPLIT = "008 013 030 031 041 047 054 059 060 072 073 074 080 083 088 097 100".split()
SEED = 20261009
N_RESAMPLE = 10_000
ERROR_TYPES = ["없는 sum 집계 추가", "실차 통행량을 실차 구간 건수로 해석", "장소를 scope 개념으로 표기",
               "출발/도착 역할을 dimension_target으로 옮김", "차원 오류(읍면동↔시군구)", "그 밖"]


def load_rows(path):
    return {row["id"]: row for row in json.loads(Path(path).read_text(encoding="utf-8"))["rows"]}


def score(path, empty):
    return C.load_cell(path, empty)


def error_types(gold_item, row):
    """6.5절 판별 규칙. grounding_ok가 거짓인 문항×회차에 붙는 유형 목록(그 밖이면 하위 표시와 함께)."""
    ok, diffs = EV.grounding_check(gold_item, row.get("grounding"))
    if ok:
        return [], None
    found = []
    by_key = {}
    for diff in diffs:
        if isinstance(diff, (list, tuple)):
            by_key.setdefault(diff[0], []).append(diff)
    for _, gold, got in by_key.get("factor:aggregation_spec", []):
        gold_agg = gold[1] if isinstance(gold, (list, tuple)) and len(gold) > 1 else None
        got_agg = got[1] if isinstance(got, (list, tuple)) and len(got) > 1 else None
        if gold_agg is None and got_agg == "sum":
            found.append(ERROR_TYPES[0])
    for _, gold, got in by_key.get("measure", []):
        if list(gold or []) == ["AMOUNT", "passage_count"] and list(got or []) == ["AMOUNT", "trip_count"]:
            found.append(ERROR_TYPES[1])
    scope_case = row.get("error_code") == "UNGROUNDED_SCOPE"
    if not scope_case and by_key.get("places") and by_key.get("scopes"):
        _, gold_places, got_places = by_key["places"][0]
        _, gold_scopes, got_scopes = by_key["scopes"][0]
        missing_place = {p[0] for p in gold_places or []} - {p[0] for p in got_places or []}
        extra_scope = {s[0] for s in got_scopes or []} - {s[0] for s in gold_scopes or []}
        scope_case = bool(missing_place and extra_scope)
    if scope_case:
        found.append(ERROR_TYPES[2])
    for _, gold, got in by_key.get("factor:dimension_target", []):
        if gold is None and got in ("pickup", "dropoff", "both"):
            found.append(ERROR_TYPES[3])
    for _, gold, got in by_key.get("factor:dimension", []):
        if gold is not None and got is not None and gold != got:
            found.append(ERROR_TYPES[4])
    if found:
        return found, None
    if "no_grounding" in diffs:
        sub = f"grounding 없음:{row.get('error_code')}"
    else:
        sub = "차이:" + ",".join(sorted(by_key))
    return [ERROR_TYPES[5]], sub


def cell_metrics(scored, rows):
    calls = [c for r in rows.values() for c in r.get("llm_calls") or []]
    thinking = [s["thinking_chars_plan"] for s in scored.values() if s["thinking_chars_plan"] is not None]
    totals = [s["total_ms"] / 1000 for s in scored.values() if s["total_ms"] is not None]
    classes = Counter(s["report_class"] for s in scored.values())
    return {"items": len(scored), "grounding_ok": sum(s["grounding_ok"] for s in scored.values()),
            "정상 답변": classes.get("정상 답변", 0), "U": sum(bool(s["u_flags"]) for s in scored.values()),
            "조용한 오답(U 아님)": classes.get("조용한 오답(U 아님)", 0),
            "실행 실패": sum(s["v4"] == "실행 실패" for s in scored.values()),
            "생성 상한 도달 호출": sum(c.get("done_reason") == "length" for c in calls),
            "thinking_chars_plan_median": statistics.median(thinking) if thinking else None,
            "latency_median_s": round(statistics.median(totals), 1) if totals else None,
            "report_classes": dict(classes)}


def first_call(row):
    plans = [c for c in row.get("llm_calls") or [] if c.get("kind") == "plan"]
    return plans[0] if plans else None


def read_raw(path):
    out = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            record = json.loads(line)
            out.setdefault(record["id"], []).append(record)
    return out


def device_compare(path, old_scored, new_scored, old_rows, new_rows):
    """6.1절: 기존 장비 기록 대 새 장비 greedy(같은 경로)."""
    ids = sorted(old_scored)
    out = {"grounding_ok_old": sum(old_scored[i]["grounding_ok"] for i in ids),
           "grounding_ok_new": sum(new_scored[i]["grounding_ok"] for i in ids)}
    if path == "hf":
        old_raw, new_raw = read_raw(OLD_HF_RAW), read_raw(NEW_HF_RAW)
        first = [i for i in ids if old_raw[i][0]["raw_text"] == new_raw[i][0]["raw_text"]]
        every = [i for i in ids if [r["raw_text"] for r in old_raw[i]] == [r["raw_text"] for r in new_raw[i]]]
        out["basis"] = "첫 호출 원문(raw_text, thinking 포함)"
    else:
        def same_first(i):
            a, b = first_call(old_rows[i]), first_call(new_rows[i])
            return a is not None and b is not None and a.get("content") == b.get("content")
        first = [i for i in ids if same_first(i)]
        out["first_thinking_chars_equal"] = sum(
            (first_call(old_rows[i]) or {}).get("thinking_chars") == (first_call(new_rows[i]) or {}).get("thinking_chars")
            for i in ids)
        every = [i for i in ids if [c.get("content") for c in old_rows[i].get("llm_calls") or []]
                 == [c.get("content") for c in new_rows[i].get("llm_calls") or []]]
        out["basis"] = "첫 plan 호출 content(결정 37 device_check와 같은 기준)"
    out["first_response_byte_equal"] = len(first)
    out["all_calls_equal"] = len(every)
    out["first_response_differs"] = [i for i in ids if i not in first]
    b = [i for i in ids if not old_scored[i]["grounding_ok"] and new_scored[i]["grounding_ok"]]
    c = [i for i in ids if old_scored[i]["grounding_ok"] and not new_scored[i]["grounding_ok"]]
    out.update({"verdict_equal": len(ids) - len(b) - len(c), "b_old_X_new_O": b, "c_old_O_new_X": c})
    out["stop_condition"] = {"byte_equal_below_50": len(first) < 50,
                             "grounding_ok_diff_ge_10": abs(out["grounding_ok_new"] - out["grounding_ok_old"]) >= 10}
    return out


def split_items(a, b):
    return sorted(i for i in a if a[i]["grounding_ok"] != b[i]["grounding_ok"])


def classify(k_hf, k_ollama):
    if k_hf == 5 and k_ollama == 5:
        return "둘 다 안정 정답"
    if k_hf == 0 and k_ollama == 0:
        return "둘 다 안정 오답"
    if abs(k_hf - k_ollama) >= 4:
        return "체계적 차이"
    return "경계"


def bootstrap_and_permutation(diffs):
    rng = np.random.default_rng(SEED)
    boot_rng, perm_rng = rng.spawn(2)
    d = np.asarray(diffs, dtype=float)
    n = len(d)
    means = d[boot_rng.integers(0, n, size=(N_RESAMPLE, n))].mean(axis=1)
    low, high = np.percentile(means, [2.5, 97.5])
    observed = d.mean()
    signs = perm_rng.choice([-1.0, 1.0], size=(N_RESAMPLE, n))
    permuted = (signs * d).mean(axis=1)
    p = (np.sum(np.abs(permuted) >= abs(observed) - 1e-12) + 1) / (N_RESAMPLE + 1)
    return {"mean_diff_hf_minus_ollama": round(float(observed), 4), "ci95": [round(float(low), 4), round(float(high), 4)],
            "ci_includes_zero": bool(low <= 0 <= high), "permutation_p_two_sided": round(float(p), 4),
            "bootstrap": {"resamples": N_RESAMPLE, "seed": SEED, "method": "문항 단위 복원추출, percentile"},
            "permutation": {"resamples": N_RESAMPLE, "seed": SEED, "method": "문항별 부호 뒤집기(spawn 둘째 stream)"}}


def position(value, samples):
    ordered = sorted(samples)
    return {"value": value, "sampling_min": ordered[0], "sampling_max": ordered[-1],
            "within_range": ordered[0] <= value <= ordered[-1],
            "sampling_values_below": sum(s < value for s in samples),
            "sampling_values_equal": sum(s == value for s in samples)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--greedy-only", action="store_true", help="greedy 기준 두 셀의 장비 변경 비교만(3단계 중간 보고)")
    args = parser.parse_args()
    gold = {item["id"]: item for item in EV.load_gold(None)["items"]}
    empty = HERE / ".empty_arm"
    empty.mkdir(exist_ok=True)
    try:
        old = {p: score(OLD[p], empty) for p in OLD}
        old_rows = {p: load_rows(OLD[p]) for p in OLD}
        new = {p: score(NEW_GREEDY[p], empty) for p in NEW_GREEDY if NEW_GREEDY[p].is_file()}
        new_rows = {p: load_rows(NEW_GREEDY[p]) for p in new}
        samples = {} if args.greedy_only else {
            p: [(score(f, empty), load_rows(f)) for f in files] for p, files in SAMPLES.items()
            if all(f.is_file() for f in files)}
    finally:
        empty.rmdir()

    result = {"names": NAMES, "old_split_items": OLD_SPLIT,
              "old_greedy": {p: cell_metrics(old[p], old_rows[p]) for p in old}}
    old_split = split_items(old["hf"], old["ollama"])
    result["old_split_recomputed"] = old_split
    result["old_split_matches_task"] = old_split == OLD_SPLIT
    if len(new) == 2:
        result["new_greedy"] = {p: cell_metrics(new[p], new_rows[p]) for p in new}
        result["device_change"] = {p: device_compare(p, old[p], new[p], old_rows[p], new_rows[p]) for p in new}
        new_split = split_items(new["hf"], new["ollama"])
        result["new_split"] = {"items": new_split, "count": len(new_split),
                               "overlap_with_old_17": sorted(set(new_split) & set(OLD_SPLIT)),
                               "only_new": sorted(set(new_split) - set(OLD_SPLIT)),
                               "only_old": sorted(set(OLD_SPLIT) - set(new_split))}
    if len(samples) == 2:
        per_round = {p: [cell_metrics(s, r) for s, r in samples[p]] for p in samples}
        result["per_round"] = per_round
        result["round_summary"] = {
            p: {"grounding_ok": [m["grounding_ok"] for m in per_round[p]],
                "mean": statistics.mean(m["grounding_ok"] for m in per_round[p]),
                "range": [min(m["grounding_ok"] for m in per_round[p]), max(m["grounding_ok"] for m in per_round[p])]}
            for p in per_round}
        ids = sorted(gold)
        k = {p: {i: sum(s[i]["grounding_ok"] for s, _ in samples[p]) for i in ids} for p in samples}
        types = {p: {i: Counter() for i in ids} for p in samples}
        type_totals = {p: Counter() for p in samples}
        other_detail = {p: Counter() for p in samples}
        for p in samples:
            for _, rows in samples[p]:
                for i in ids:
                    found, sub = error_types(gold[i], rows[i])
                    for name in found:
                        types[p][i][name] += 1
                        type_totals[p][name] += 1
                    if sub:
                        other_detail[p][sub] += 1
        items = {}
        for i in ids:
            items[i] = {"k_hf": k["hf"][i], "k_ollama": k["ollama"][i], "class": classify(k["hf"][i], k["ollama"][i]),
                        "old_greedy": {p: old[p][i]["grounding_ok"] for p in old},
                        "new_greedy": {p: new[p][i]["grounding_ok"] for p in new} if new else None,
                        "error_types": {p: dict(types[p][i]) for p in samples},
                        "representative_error": {
                            p: (min(types[p][i].items(), key=lambda kv: (-kv[1], ERROR_TYPES.index(kv[0])))[0]
                                if types[p][i] else None) for p in samples}}
        result["items"] = items
        result["class_counts"] = dict(Counter(v["class"] for v in items.values()))
        result["old_17_classes"] = {i: items[i]["class"] for i in OLD_SPLIT}
        if "new_split" in result:
            result["new_split_classes"] = {i: items[i]["class"] for i in result["new_split"]["items"]}
        result["not_stable_items"] = [i for i in ids if k["hf"][i] not in (0, 5) or k["ollama"][i] not in (0, 5)]
        result["overall"] = bootstrap_and_permutation([(k["hf"][i] - k["ollama"][i]) / 5 for i in ids])
        result["greedy_position"] = {
            p: {"old": position(result["old_greedy"][p]["grounding_ok"], result["round_summary"][p]["grounding_ok"]),
                **({"new": position(result["new_greedy"][p]["grounding_ok"], result["round_summary"][p]["grounding_ok"])}
                   if "new_greedy" in result else {})} for p in samples}
        result["error_type_counts"] = {p: {name: type_totals[p].get(name, 0) for name in ERROR_TYPES} for p in samples}
        result["error_type_other_detail"] = {p: dict(other_detail[p].most_common()) for p in samples}
    out = HERE / ("analysis_greedy.json" if args.greedy_only else "analysis.json")
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8")
    brief = {"old_greedy": {p: result["old_greedy"][p]["grounding_ok"] for p in old},
             "old_split_matches_task": result["old_split_matches_task"]}
    if "device_change" in result:
        brief["device_change"] = {p: {k_: v for k_, v in d.items() if k_ not in ("first_response_differs",)}
                                  for p, d in result["device_change"].items()}
        brief["new_split"] = result["new_split"]
    if "overall" in result:
        brief["round_summary"] = result["round_summary"]
        brief["overall"] = result["overall"]
        brief["class_counts"] = result["class_counts"]
    print(json.dumps(brief, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
