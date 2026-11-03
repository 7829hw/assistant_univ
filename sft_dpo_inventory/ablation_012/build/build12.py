# -*- coding: utf-8 -*-
"""ablation_012 A3R 빌드(결정 262 D4) — A3(ablation_011)의 무작위 제거 대조 arm. 입력 = pilot_010 V4 빌드 결과와 ablation_011 빌드 기록(둘 다 그대로 둠). 모델 호출 없음.
``build10w.py``·``build11.py``는 고치지 않는다.

    runtime/envs/hf/bin/python sft_dpo_inventory/ablation_012/build/build12.py
    # -> build/A3R-d{1,2}/full/{sft_train,sft_valid}.jsonl·manifest.json, build/removed_A3R-d{1,2}.json,
    #    build/orders/record_order_A3R-d{1,2}_o<seed>.json, build/build_summary.json

- A3 제거 질문 = ``ablation_011/build/removed_A3.json``의 레코드가 하나라도 빠진 질문(149: 통째로 빠진 99 + 일부만 빠진 50). A3 제거 레코드 수 = 462.
- 대상 풀 = V4의 답하는 질문(거부 레코드가 없는 질문 420) − A3 제거 질문 149 = 271질문(id 정렬).
- 뽑기 d: ``numpy.random.default_rng(seed_d)``로 ``rng.choice(271, 99, replace=False)``를 되풀이해, 뽑은 질문의 V4 레코드 합이 462의 ±2%([452.76, 471.24] → 453–471)에
  처음 드는 뽑기를 쓴다. 다시 뽑은 횟수를 기록한다. 1,000번 안에 못 하면 멈춘다. seed d1 = 20261104, d2 = 20261105.
- 뽑은 질문의 V4 레코드를 모두 뺀다(질문 단위). 거부 레코드는 그대로 둔다(A3처럼).
- 순서: ablation_011의 A0 레코드 열(``ablation_011/build/orders/record_order_A0_o<seed>.json``, A0 O4' 순서)에서 빠진 레코드만 지운다(상대 순서 유지).
  같은 질문 연속 길이 ≤ 4(``order7b.MAX_RUN``)를 검사하고, 넘으면 멈춘다.
- 구성 표(A0·A3·A3R-d1·A3R-d2): 측정 subtype 묶음(→ tool)별 레코드·질문, 근접 대조 teacher 레코드, 거부 레코드, 손실 token은 ``mask_audit12.py``가 따로 낸다.
"""
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
A12 = HERE.parent
INV = A12.parent
ROOT = INV.parent
sys.path.insert(0, str(INV / "pilot_007/train_data"))
import order7b  # noqa: E402

V4 = INV / "pilot_010/build/V4"
A11B = INV / "ablation_011/build"
CORPUS = INV / "pilot_006_prep/approved/approved_train_v6.jsonl"
V4_QLIST_SHA = "d559b3e1acca8c8dbd3592d3e0c2302e1890b88801f5df5d160a35938ef54b98"
ORDER_SEEDS = (1102, 211102, 2026113)  # ablation_011 순서 seed
DRAWS = {"A3R-d1": 20261104, "A3R-d2": 20261105}
N_Q, TOL, MAX_TRIES = 99, 0.02, 1000
MAX_RUN = order7b.MAX_RUN
TOOL = {"revenue": "get_billing_metrics", "active_taxi_count": "get_billing_metrics", "active_taxi_ratio": "get_billing_metrics", "operating_days": "get_billing_metrics",
        "trip_count": "get_trip_count", "passage_count": "get_passage_count", "place": "get_scope_name"}


def sha_file(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def key(r):
    m = r["metadata"]
    return f"{m['source_record_id']}|{m['trace_id']}"


def qid(r):
    return r["metadata"]["source_record_id"]


def qlist_sha(recs):
    return hashlib.sha256("\n".join(sorted({qid(r) for r in recs})).encode()).hexdigest()


def tool_group(corpus, q):
    sub = ((corpus[q].get("view") or {}).get("measure") or {}).get("subtype")
    if sub is None:
        return "없음(거부 질문)"
    return TOOL.get(sub, f"기타({sub})")


def composition(recs, corpus):
    by_tool, q_tool = Counter(), Counter()
    for r in recs:
        by_tool[tool_group(corpus, qid(r))] += 1
    for q in {qid(r) for r in recs}:
        q_tool[tool_group(corpus, q)] += 1
    return {"records": len(recs), "questions": len({qid(r) for r in recs}),
            "refusal_records": sum(1 for r in recs if r["metadata"].get("refusal_source")),
            "refusal_share": round(sum(1 for r in recs if r["metadata"].get("refusal_source")) / len(recs), 4),
            "contrast_teacher_records": sum(1 for r in recs if r["metadata"].get("contrast_source") == "teacher"),
            "contrast_teacher_share": round(sum(1 for r in recs if r["metadata"].get("contrast_source") == "teacher") / len(recs), 4),
            "batch013_records": sum(1 for r in recs if r["metadata"]["corpus_group"] == "batch013"),
            "by_loss_scope": dict(Counter(r["metadata"]["loss_scope"] for r in recs)),
            "records_by_tool": dict(sorted(by_tool.items())), "questions_by_tool": dict(sorted(q_tool.items()))}


def write_arm(name, lines, recs, v4_manifest, note):
    d = HERE / name / "full"
    d.mkdir(parents=True, exist_ok=True)
    (d / "sft_train.jsonl").write_text("".join(l + "\n" for l in lines), encoding="utf-8")
    (d / "sft_valid.jsonl").write_text("", encoding="utf-8")
    man = json.loads(json.dumps(v4_manifest))
    s = man["sft"]
    q = sorted({qid(r) for r in recs})
    s.update(generated_at=datetime.now(timezone.utc).isoformat(), release_candidate=f"ablation_012 {name}", note=note, train_count=len(recs), validation_count=0,
             questions=len(q), question_list_sha256=hashlib.sha256("\n".join(q).encode()).hexdigest(),
             by_source=dict(Counter(r["metadata"]["loss_scope"] for r in recs)),
             output_hashes={"sft_train.jsonl": sha_file(d / "sft_train.jsonl"), "sft_valid.jsonl": sha_file(d / "sft_valid.jsonl")})
    (d / "manifest.json").write_text(json.dumps(man, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return s["output_hashes"]["sft_train.jsonl"], s["question_list_sha256"]


def main():
    v4_path = V4 / "full/sft_train.jsonl"
    v4_manifest = json.loads((V4 / "full/manifest.json").read_text(encoding="utf-8"))
    lines = v4_path.read_text(encoding="utf-8").splitlines()
    recs = [json.loads(l) for l in lines]
    checks = {"v4_file_sha256_matches_manifest": sha_file(v4_path) == v4_manifest["sft"]["output_hashes"]["sft_train.jsonl"],
              "v4_question_list_sha256_ok": qlist_sha(recs) == V4_QLIST_SHA,
              "v4_lines_roundtrip": all(json.dumps(r, ensure_ascii=False) == l for r, l in zip(recs, lines)),
              "record_keys_unique": len({key(r) for r in recs}) == len(recs)}
    a3_summary = json.loads((A11B / "build_summary.json").read_text(encoding="utf-8"))
    checks["a11_A0_train_sha256_same"] = a3_summary["arms"]["A0"]["train_sha256"] == sha_file(v4_path)
    if not all(checks.values()):
        raise SystemExit(f"input check failed: {checks}")
    corpus = {r["id"]: r for r in (json.loads(l) for l in CORPUS.read_text(encoding="utf-8").splitlines() if l.strip())}
    removed_a3 = json.loads((A11B / "removed_A3.json").read_text(encoding="utf-8"))["removed"]
    a3_keys = {x["key"] for x in removed_a3}
    n_a3 = len(a3_keys)
    a3_q = sorted({k.split("|", 1)[0] for k in a3_keys})
    per_q = Counter(qid(r) for r in recs)
    ref_q = {qid(r) for r in recs if r["metadata"].get("refusal_source")}
    ans_q = set(per_q) - ref_q
    if any(not r["metadata"].get("refusal_source") for r in recs if qid(r) in ref_q):
        raise SystemExit("question with both refusal and answer records")
    a3_entire = sorted(q for q in a3_q if sum(1 for k in a3_keys if k.startswith(q + "|")) == per_q[q])
    pool = sorted(ans_q - set(a3_q))
    lo, hi = n_a3 * (1 - TOL), n_a3 * (1 + TOL)
    if len(a3_entire) != N_Q:
        raise SystemExit(f"A3 entire-removed questions {len(a3_entire)} != {N_Q}")
    summary = {"label": "ablation_012 build12 (결정 262 D4)", "built": datetime.now(timezone.utc).isoformat(),
               "input": {"v4_train": str(v4_path.relative_to(ROOT)), "v4_train_sha256": sha_file(v4_path), "corpus_v6_sha256": sha_file(CORPUS),
                         "a11_removed_A3_sha256": sha_file(A11B / "removed_A3.json"), "a11_build_summary_sha256": sha_file(A11B / "build_summary.json")},
               "checks": checks,
               "a3_reference": {"removed_records": n_a3, "touched_questions": len(a3_q), "entire_questions": len(a3_entire), "partial_questions": len(a3_q) - len(a3_entire)},
               "pool": {"rule": "V4 답하는 질문 − A3 제거 질문(레코드가 하나라도 빠진 질문) − 거부 질문, id 정렬", "answer_questions": len(ans_q),
                        "refusal_questions": len(ref_q), "a3_questions_excluded": len(a3_q), "pool_questions": len(pool),
                        "pool_records": sum(per_q[q] for q in pool), "pool_question_list_sha256": hashlib.sha256("\n".join(pool).encode()).hexdigest()},
               "draw_rule": {"questions": N_Q, "target_records": n_a3, "tolerance": TOL, "accept_range": [lo, hi], "max_tries": MAX_TRIES,
                             "rng": "numpy.random.default_rng(seed).choice(len(pool), 99, replace=False), 되풀이"},
               "order_seeds": list(ORDER_SEEDS), "arms": {}, "orders": {}}
    keep = {}
    for arm, seed in DRAWS.items():
        rng = np.random.default_rng(seed)
        tries, pick, sizes = 0, None, []
        while tries < MAX_TRIES:
            tries += 1
            idx = rng.choice(len(pool), N_Q, replace=False)
            sel = sorted(pool[i] for i in idx)
            n = sum(per_q[q] for q in sel)
            sizes.append(n)
            if lo <= n <= hi:
                pick = sel
                break
        if pick is None:
            raise SystemExit(f"STOP: {arm} draw did not satisfy ±2% within {MAX_TRIES} tries")
        rm = {key(r) for r in recs if qid(r) in set(pick)}
        keep[arm] = rm
        body = {"arm": arm, "draw_seed": seed, "tries": tries, "redraws": tries - 1, "rejected_record_counts": sizes[:-1], "accepted_record_count": len(rm),
                "questions": pick, "question_list_sha256": hashlib.sha256("\n".join(pick).encode()).hexdigest(),
                "removed": [{"key": key(r), "tool_group": tool_group(corpus, qid(r)), "loss_scope": r["metadata"]["loss_scope"],
                             "contrast_teacher": r["metadata"].get("contrast_source") == "teacher"} for r in recs if key(r) in rm]}
        (HERE / f"removed_{arm}.json").write_text(json.dumps(body, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        sel_idx = [i for i, r in enumerate(recs) if key(r) not in rm]
        h = write_arm(arm, [lines[i] for i in sel_idx], [recs[i] for i in sel_idx], v4_manifest,
                      f"ablation_012 {arm} = V4에서 무작위 답하는 질문 {N_Q}개(뽑기 seed {seed}, A3 제거 질문·거부 질문 제외 풀)의 레코드 {len(rm)}개를 뺌; build12.py")
        summary["arms"][arm] = {"train_file": f"sft_dpo_inventory/ablation_012/build/{arm}/full/sft_train.jsonl", "train_sha256": h[0], "question_list_sha256": h[1],
                                "draw_seed": seed, "tries": tries, "redraws": tries - 1, "removed_records": len(rm), "removed_vs_a3_pct": round(100 * (len(rm) - n_a3) / n_a3, 2),
                                "removed_questions": N_Q, "steps": len(sel_idx), **composition([recs[i] for i in sel_idx], corpus),
                                "removed_composition": composition([r for r in recs if key(r) in rm], corpus)}
    a3_recs = [r for r in recs if key(r) not in a3_keys]
    summary["reference_arms"] = {"A0": composition(recs, corpus), "A3": composition(a3_recs, corpus),
                                 "A3_removed": composition([r for r in recs if key(r) in a3_keys], corpus)}
    od = HERE / "orders"
    od.mkdir(exist_ok=True)
    for s in ORDER_SEEDS:
        a0 = json.loads((A11B / f"orders/record_order_A0_o{s}.json").read_text(encoding="utf-8"))
        a0_seq = a0["record_sequence"]
        if a0_seq != a0["a0_record_sequence"] or order7b.sha(a0_seq) != a0["record_sequence_sha256"] or set(a0_seq) != {key(r) for r in recs}:
            raise SystemExit(f"ablation_011 A0 order o{s} check failed")
        summary["orders"][s] = {"a0_order_file": f"sft_dpo_inventory/ablation_011/build/orders/order_b2_o{s}.json", "a0_order_sha256": a0["a0_order_sha256"],
                                "a0_record_sequence_sha256": a0["a0_record_sequence_sha256"], "arms": {}}
        for arm in DRAWS:
            seq = [k for k in a0_seq if k not in keep[arm]]
            rs = order7b.run_stats([k.split("|", 1)[0] for k in seq])
            body = {"arm": arm, "seed": s, "rule": "ablation_011 A0 O4' 레코드 열(record_order_A0_o<seed>.json)에서 이 arm에 없는 레코드만 지움(상대 순서 유지)",
                    "a0_order_file": f"order_b2_o{s}.json(ablation_011/build/orders)", "a0_order_sha256": a0["a0_order_sha256"],
                    "a0_record_sequence_sha256": a0["a0_record_sequence_sha256"], "records": len(seq), "record_sequence_sha256": order7b.sha(seq), "run_stats": rs,
                    "max_run_limit": MAX_RUN, "max_run_ok": rs["max_run"] <= MAX_RUN, "a0_record_sequence": a0_seq, "record_sequence": seq}
            (od / f"record_order_{arm}_o{s}.json").write_text(json.dumps(body, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
            summary["orders"][s]["arms"][arm] = {"records": len(seq), "record_sequence_sha256": body["record_sequence_sha256"], "run_stats": rs, "max_run_ok": body["max_run_ok"]}
            if not body["max_run_ok"]:
                (HERE / "build_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
                raise SystemExit(f"STOP: {arm} o{s} max run {rs['max_run']} > {MAX_RUN}")
    overlap = len(keep["A3R-d1"] & keep["A3R-d2"])
    summary["d1_d2_removed_record_overlap"] = overlap
    summary["d1_d2_removed_question_overlap"] = len({k.split('|')[0] for k in keep["A3R-d1"]} & {k.split('|')[0] for k in keep["A3R-d2"]})
    (HERE / "build_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"checks": checks, "a3": summary["a3_reference"], "pool": summary["pool"],
                      "arms": {a: {k: v[k] for k in ("tries", "removed_records", "removed_vs_a3_pct", "steps", "contrast_teacher_records", "refusal_share")} for a, v in summary["arms"].items()},
                      "orders": {s: {a: v["run_stats"]["max_run"] for a, v in o["arms"].items()} for s, o in summary["orders"].items()},
                      "overlap_q": summary["d1_d2_removed_question_overlap"]}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
