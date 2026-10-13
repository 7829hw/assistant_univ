# -*- coding: utf-8 -*-
"""P0 thinking trace 품질 통계(모델 호출 없음, tokenizer만 CPU). 출력: trace_quality.json.

    HF_HOME=/data/hwkim/path_repeat_001/hf-cache HF_HUB_OFFLINE=1 \
      python evaluation/partial_grounding/sft_p0/trace_quality.py

- 입력: `collect_p0_traces_hf.py`의 원문(`training/generated/thinking_traces/p0_v006_hf/traces.jsonl`)과 v006.
- 범주(수집 때 판정): EXACT_OR_SEMANTIC_MATCH, STRUCTURALLY_REPAIRABLE, SEMANTIC_MISMATCH, REFUSAL_MISMATCH, UNPARSEABLE.
- thinking 확인(결정 66): thinking이 닫혔고 비어 있지 않은 trace만 trace dataset 후보다.
- 기본 채택(결정 67): EXACT_OR_SEMANTIC_MATCH + thinking 있음. 같은 질문에서 원문이 같은 trace는 하나로 센다.
- 참고(다음 SFT 단계 preregistration에서 확정): 기존 학습 필터를 같은 함수로 적용한 수.
  - 결정 4: 생성 token과 `tokenizer(raw_text + eos)`가 같아야 한다.
  - 결정 40-D: 루프 기준(`pilot_prep_004/loop_filter.is_loop`).
  - 결정 18: SFT total(prompt + 생성 + 1) ≤ 12,887.
  - 질문당 상한(결정 48·50의 4개)은 적용하지 않고, 적용했을 때의 수만 적는다.
- 집계 축: 출처(v005, augment_dt_event = Gap A, augment_od_vs_dt = Gap B), dimension_target(pickup·dropoff·both),
  od_role ≠ dimension_target(dataset_stats와 같은 정의).
"""
import collections
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/thinking_prep_001"))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_prep_003/data"))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_prep_004/loop_filter"))

TRACES = ROOT / "training/generated/thinking_traces/p0_v006_hf/traces.jsonl"
DATASET = ROOT / "training/generated/reviewed_gold_v006_p0/sft_train.jsonl"
MATCH = "EXACT_OR_SEMANTIC_MATCH"
CATEGORIES = (MATCH, "STRUCTURALLY_REPAIRABLE", "SEMANTIC_MISMATCH", "REFUSAL_MISMATCH", "UNPARSEABLE")
PER_QUESTION_CAP = 4


def axes(target):
    f = target.get("factors") or {}
    roles = {(c.get("attributes") or {}).get("od_role") for c in target.get("concepts") or []
             if c.get("subtype") in ("place", "scope")} - {None}
    dt = f.get("dimension_target")
    return {"dimension_target": dt, "od_ne_dt": bool(dt and roles and dt not in roles), "dimension": f.get("dimension")}


def rate(n, d):
    return {"n": n, "of": d, "rate": round(n / d, 3) if d else None}


def group_stats(rows, qids):
    """trace 수준·질문 수준 성공률."""
    tr = [r for r in rows if r["item_id"] in qids]
    greedy = [r for r in tr if r["kind"] == "greedy"]
    samples = [r for r in tr if r["kind"] == "sample"]
    by_q = collections.defaultdict(list)
    for r in tr:
        by_q[r["item_id"]].append(r)
    return {"questions": len(qids),
            "trace_match": rate(sum(r["judge"]["category"] == MATCH for r in tr), len(tr)),
            "greedy_match": rate(sum(r["judge"]["category"] == MATCH for r in greedy), len(greedy)),
            "sample_match": rate(sum(r["judge"]["category"] == MATCH for r in samples), len(samples)),
            "questions_with_any_match": rate(sum(any(x["judge"]["category"] == MATCH for x in v) for v in by_q.values()),
                                             len(by_q)),
            "categories": dict(collections.Counter(r["judge"]["category"] for r in tr))}


def main():
    from build_v004_thinking import CAP_SFT_TOTAL, tokenizer
    from apply_filter import is_loop, loop_metrics
    rows = [json.loads(x) for x in TRACES.read_text(encoding="utf-8").splitlines() if x.strip()]
    data = {}
    for x in DATASET.read_text(encoding="utf-8").splitlines():
        r = json.loads(x)
        data[r["metadata"]["source_record_id"]] = {"source": r["metadata"]["source"],
                                                   **axes(json.loads(r["messages"][2]["content"]))}
    tok = tokenizer()
    for r in rows:
        r["thinking_ok"] = bool(r["think_closed"] and (r.get("thinking") or "").strip())
        roundtrip = (r["done_reason"] == "stop" and r["think_closed"]
                     and tok(r["raw_text"] + tok.eos_token, add_special_tokens=False)["input_ids"] == r["generated_ids"])
        m = loop_metrics(r.get("thinking") or "")
        loop = is_loop(m) if m else ["empty_thinking"]
        total = r["prompt_tokens"] + r["generated_tokens"] + 1
        r["filters"] = {"decision4_roundtrip_ok": bool(roundtrip), "decision40D_loop": loop or [],
                        "decision18_total": total, "decision18_ok": total <= CAP_SFT_TOTAL}
    missing = sorted(set(data) - {r["item_id"] for r in rows})
    per_q = collections.Counter(r["item_id"] for r in rows)
    incomplete = {k: v for k, v in per_q.items() if v != 9}

    # 기본 채택: 정답 + thinking 있음, 같은 질문의 같은 원문은 하나로.
    adopted, seen = [], set()
    for r in rows:
        if r["judge"]["category"] == MATCH and r["thinking_ok"] and (r["item_id"], r["raw_sha256"]) not in seen:
            seen.add((r["item_id"], r["raw_sha256"]))
            adopted.append(r)
    filtered = [r for r in adopted if r["filters"]["decision4_roundtrip_ok"] and not r["filters"]["decision40D_loop"]
                and r["filters"]["decision18_ok"]]
    capped = sum(min(PER_QUESTION_CAP, v) for v in collections.Counter(r["item_id"] for r in filtered).values())
    drop_steps = collections.Counter()
    for r in adopted:
        f = r["filters"]
        drop_steps["decision4_tokenization_mismatch" if not f["decision4_roundtrip_ok"] else
                   "decision40D_loop" if f["decision40D_loop"] else
                   "decision18_over_length" if not f["decision18_ok"] else "kept"] += 1

    all_q = set(data)
    by_source = {s: {k for k, v in data.items() if v["source"] == s} for s in ("v005", "augment_dt_event", "augment_od_vs_dt")}
    by_dt = {dt: {k for k, v in data.items() if v["dimension_target"] == dt} for dt in ("pickup", "dropoff", "both")}
    od_ne = {k for k, v in data.items() if v["od_ne_dt"]}
    new = by_source["augment_dt_event"] | by_source["augment_od_vs_dt"]
    no_match_q = sorted(k for k in all_q if not any(r["judge"]["category"] == MATCH for r in rows if r["item_id"] == k))
    # 정답 표본이 없는 신규 문항: 실패 형태(지시 30절: gold·teacher capacity·prompt 문제를 가리기 위한 자료).
    fail_detail = {}
    for k in sorted(set(no_match_q) & new):
        tr = [r for r in rows if r["item_id"] == k]
        fail_detail[k] = {"categories": dict(collections.Counter(r["judge"]["category"] for r in tr)),
                          "raw_diff_keys": dict(collections.Counter(d[0] for r in tr for d in r["judge"].get("raw_diffs") or [])),
                          "greedy_parsed_factors": (tr[0].get("parsed") or {}).get("factors") if tr else None}
    diff_keys_new = collections.Counter(d[0] for r in rows if r["item_id"] in new and r["judge"]["category"] != MATCH
                                        for d in r["judge"].get("raw_diffs") or [])
    out = {
        "traces": str(TRACES.relative_to(ROOT)), "traces_sha256": hashlib.sha256(TRACES.read_bytes()).hexdigest(),
        "questions_in_dataset": len(data), "questions_collected": len(per_q), "missing_questions": missing,
        "incomplete_questions": incomplete, "traces_total": len(rows),
        "kinds": dict(collections.Counter(r["kind"] for r in rows)),
        "categories": {c: sum(r["judge"]["category"] == c for r in rows) for c in CATEGORIES},
        "thinking": {"ok": sum(r["thinking_ok"] for r in rows), "missing_or_unclosed": sum(not r["thinking_ok"] for r in rows),
                     "truncated_length": sum(r["done_reason"] == "length" for r in rows)},
        "exact_json": sum(bool(r["judge"].get("exact_json")) for r in rows),
        "overall": group_stats(rows, all_q),
        "by_source": {s: group_stats(rows, q) for s, q in by_source.items()},
        "by_dimension_target": {dt: group_stats(rows, q) for dt, q in by_dt.items()},
        "od_role_ne_dimension_target": group_stats(rows, od_ne),
        "new_items": group_stats(rows, new),
        "new_items_mismatch_diff_keys": dict(diff_keys_new.most_common()),
        "questions_without_match": {"count": len(no_match_q), "ids": no_match_q,
                                    "new_items": sorted(set(no_match_q) & new)},
        "new_items_without_match_detail": fail_detail,
        "adoption": {
            "rule": "EXACT_OR_SEMANTIC_MATCH + thinking 있음, 질문별 원문 중복 제거(결정 67)",
            "adopted_unique": len(adopted),
            "adopted_questions": len({r["item_id"] for r in adopted}),
            "adopted_by_source": dict(collections.Counter(data[r["item_id"]]["source"] for r in adopted)),
            "existing_filters_reference": {"steps": dict(drop_steps), "after_filters": len(filtered),
                                           "after_filters_questions": len({r["item_id"] for r in filtered}),
                                           "after_filters_by_source": dict(collections.Counter(
                                               data[r["item_id"]]["source"] for r in filtered)),
                                           f"with_per_question_cap_{PER_QUESTION_CAP}": capped},
            "structurally_repairable_unique": len({(r["item_id"], r["raw_sha256"]) for r in rows
                                                   if r["judge"]["category"] == "STRUCTURALLY_REPAIRABLE"}),
            "adopted_trace_ids": [r["trace_id"] for r in adopted],
            "after_filters_trace_ids": [r["trace_id"] for r in filtered],
        },
        "generated_tokens_median": sorted(r["generated_tokens"] for r in rows)[len(rows) // 2] if rows else None,
        "thinking_chars_median": sorted(len(r.get("thinking") or "") for r in rows)[len(rows) // 2] if rows else None,
    }
    (HERE / "trace_quality.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k not in ("adoption", "new_items_without_match_detail")},
                     ensure_ascii=False, indent=1))
    print(json.dumps({k: v for k, v in out["adoption"].items() if not k.endswith("trace_ids")}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
