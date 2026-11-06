# -*- coding: utf-8 -*-
"""ablation_013 빌드(결정 263 D4·A0 짝 seed). 입력 = pilot_010 V4 빌드 결과, ablation_011 빌드 기록(모두 그대로 둠). 모델 호출 없음.
``build10w.py``·``build11.py``·``build12.py``는 고치지 않는다.

    runtime/envs/hf/bin/python sft_dpo_inventory/ablation_013/build/build13.py
    # -> build/A3T/full/{sft_train,sft_valid}.jsonl·manifest.json, build/removed_A3T.json, build/loss_tokens_A0.json,
    #    build/orders/record_order_A3T_o<seed>.json(seed 1102·211102·2026113),
    #    build/orders/order_b2_o<seed>.json·record_order_A0_o<seed>.json(새 seed 2026117·2026131), build/build_summary.json

A3T(결정 263 D4)
- 대상 풀 = V4 질문 중 요금 지표가 아닌 근접 대조 질문: corpus v6 ``provenance.kind == "r2_contrast"``(batch011·012 r2, batch013 c1·c2)이면서
  요금 지표(``view.measure.subtype`` ∈ BILLING, build11과 같은 정의)가 아닌 질문 ∪ 근접 대조 teacher 레코드(``contrast_source == "teacher"``)가 있는 질문 중 요금 지표가 아닌 것.
  batch013 c1(요금 지표 근접 대조)은 정의상 모두 요금 지표여야 한다(아니면 멈춤). 거부 레코드가 있는 질문은 풀에 없어야 한다(아니면 멈춤). 풀이 비면 멈춤.
- 손실 token = 학습 코드의 렌더(``training.trainer_common.render_records``, ``train_a11.install_override``, A0-o1102 config)로 completion token 수(mask_audit12와 같은 방법).
  근접 대조 teacher 손실 비중 = 남은 레코드 중 ``contrast_source == "teacher"`` 레코드의 손실 token 합 / 남은 레코드 손실 token 합.
- 뽑기: ``numpy.random.default_rng(20261106).permutation(풀 크기)``(풀은 id 정렬) 순서로 질문을 하나씩 통째로 빼고(그 질문의 V4 레코드 전부: teacher trace·json_only),
  뺄 때마다 비중을 다시 계산해 A3 값(mask_audit12의 A3 비중) ± 2pp 안에 들면 멈춘다. 풀을 다 빼도 못 들면 다 뺀 상태를 쓰고 실제 비중을 보고한다.
- 순서: ablation_011 A0 레코드 열(``ablation_011/build/orders/record_order_A0_o<seed>.json``)에서 빠진 레코드만 지움(상대 순서 유지), 같은 질문 연속 ≤ 4(넘으면 멈춤).

A0 새 순서 seed(결정 263, 2026117·2026131)
- ``order7b.order_file({"full": V4 레코드}, seed)``(O4', build11과 같은 호출) → ``orders/order_b2_o<seed>.json``; 그 순서의 A0 레코드 열 → ``orders/record_order_A0_o<seed>.json``(train_a11 형식).
  같은 질문 연속 ≤ 4(넘으면 멈춤). build11의 기존 seed 1102로 같은 호출을 돌려 ablation_011 파일과 바이트 단위로 같은지 먼저 확인한다(재현 검사; 다르면 멈춤).
"""
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import yaml

HERE = Path(__file__).resolve().parent
A13 = HERE.parent
INV = A13.parent
ROOT = INV.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(INV / "thinking_prep_001"))
sys.path.insert(0, str(INV / "ablation_011/train"))
sys.path.insert(0, str(INV / "pilot_007/train_data"))
import order7b  # noqa: E402

V4 = INV / "pilot_010/build/V4"
A11B = INV / "ablation_011/build"
CORPUS = INV / "pilot_006_prep/approved/approved_train_v6.jsonl"
V4_QLIST_SHA = "d559b3e1acca8c8dbd3592d3e0c2302e1890b88801f5df5d160a35938ef54b98"
OLD_SEEDS = (1102, 211102, 2026113)
NEW_SEEDS = (2026117, 2026131)
DRAW_SEED = 20261106
TOL_PP = 2.0
MAX_RUN = order7b.MAX_RUN
BILLING = {"revenue", "active_taxi_count", "active_taxi_ratio", "operating_days"}  # build11과 같음


def sha_file(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def key(r):
    m = r["metadata"]
    return f"{m['source_record_id']}|{m['trace_id']}"


def qid(r):
    return r["metadata"]["source_record_id"]


def is_ct(r):
    return r["metadata"].get("contrast_source") == "teacher"


def loss_tokens(recs):
    import train_a11
    train_a11.install_override()
    import hf_thinking as H
    from training.trainer_common import render_records
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(H.MODEL, revision=H.REVISION)
    cfg = yaml.safe_load((INV / "ablation_011/train/configs/A0-o1102.yaml").read_text(encoding="utf-8"))
    rows = render_records(tok, recs, cfg, "sft")
    return {key(r): len(tok(row["completion"], add_special_tokens=False)["input_ids"]) for r, row in zip(recs, rows)}


def share(keys, lt, ct_keys):
    tot = sum(lt[k] for k in keys)
    return 100.0 * sum(lt[k] for k in keys if k in ct_keys) / tot


def shares3(recs, lt):
    tot = sum(lt[key(r)] for r in recs)
    ref = sum(lt[key(r)] for r in recs if r["metadata"].get("refusal_source"))
    ct = sum(lt[key(r)] for r in recs if is_ct(r))
    return {"refusal": round(100 * ref / tot, 2), "contrast_teacher": round(100 * ct / tot, 2), "rest": round(100 * (tot - ref - ct) / tot, 2), "loss_tokens_total": tot}


def tool_group(corpus, q):
    sub = ((corpus[q].get("view") or {}).get("measure") or {}).get("subtype")
    if sub is None:
        return "없음(거부 질문)"
    return {"revenue": "get_billing_metrics", "active_taxi_count": "get_billing_metrics", "active_taxi_ratio": "get_billing_metrics", "operating_days": "get_billing_metrics",
            "trip_count": "get_trip_count", "passage_count": "get_passage_count", "place": "get_scope_name"}.get(sub, f"기타({sub})")


def composition(recs, corpus, lt):
    by_tool, q_tool = Counter(), Counter()
    for r in recs:
        by_tool[tool_group(corpus, qid(r))] += 1
    for q in {qid(r) for r in recs}:
        q_tool[tool_group(corpus, q)] += 1
    return {"records": len(recs), "steps": len(recs), "questions": len({qid(r) for r in recs}),
            "refusal_records": sum(1 for r in recs if r["metadata"].get("refusal_source")),
            "contrast_teacher_records": sum(1 for r in recs if is_ct(r)),
            "contrast_teacher_billing_records": sum(1 for r in recs if is_ct(r) and ((corpus[qid(r)].get("view") or {}).get("measure") or {}).get("subtype") in BILLING),
            "by_loss_scope": dict(Counter(r["metadata"]["loss_scope"] for r in recs)),
            "loss_share_pct": shares3(recs, lt),
            "records_by_tool": dict(sorted(by_tool.items())), "questions_by_tool": dict(sorted(q_tool.items()))}


def write_arm(name, lines, recs, v4_manifest, note):
    d = HERE / name / "full"
    d.mkdir(parents=True, exist_ok=True)
    (d / "sft_train.jsonl").write_text("".join(l + "\n" for l in lines), encoding="utf-8")
    (d / "sft_valid.jsonl").write_text("", encoding="utf-8")
    man = json.loads(json.dumps(v4_manifest))
    s = man["sft"]
    q = sorted({qid(r) for r in recs})
    s.update(generated_at=datetime.now(timezone.utc).isoformat(), release_candidate=f"ablation_013 {name}", note=note, train_count=len(recs), validation_count=0,
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
              "v4_question_list_sha256_ok": hashlib.sha256("\n".join(sorted({qid(r) for r in recs})).encode()).hexdigest() == V4_QLIST_SHA,
              "v4_lines_roundtrip": all(json.dumps(r, ensure_ascii=False) == l for r, l in zip(recs, lines)),
              "record_keys_unique": len({key(r) for r in recs}) == len(recs)}
    if not all(checks.values()):
        raise SystemExit(f"input check failed: {checks}")
    corpus = {r["id"]: r for r in (json.loads(l) for l in CORPUS.read_text(encoding="utf-8").splitlines() if l.strip())}
    billing = {c for c, x in corpus.items() if ((x.get("view") or {}).get("measure") or {}).get("subtype") in BILLING}
    c1 = {c for c, x in corpus.items() if x["corpus_group"] == "batch013" and (x.get("provenance") or {}).get("group") == "c1"}
    if not c1 <= billing:
        raise SystemExit(f"batch013 c1 not all billing: {sorted(c1 - billing)[:5]}")
    v4q = {qid(r) for r in recs}
    ref_q = {qid(r) for r in recs if r["metadata"].get("refusal_source")}
    r2 = {q for q in v4q if (corpus[q].get("provenance") or {}).get("kind") == "r2_contrast"}
    ct_q = {qid(r) for r in recs if is_ct(r)}
    pool = sorted((r2 | ct_q) - billing)
    if not pool:
        raise SystemExit("STOP: A3T pool empty")
    if set(pool) & ref_q:
        raise SystemExit("STOP: refusal question in A3T pool")
    lt = loss_tokens(recs)
    (HERE / "loss_tokens_A0.json").write_text(json.dumps({"note": "V4(A0) 레코드별 손실 token(completion token 수; train_a11 렌더, A0-o1102 config). build13.py", "loss_tokens": lt},
                                                         ensure_ascii=False, indent=0) + "\n", encoding="utf-8")
    ma12 = json.loads((INV / "ablation_012/build/mask_audit12.json").read_text(encoding="utf-8"))
    a3_share = 100 * ma12["A3"]["loss_share_3way"]["contrast_teacher"]
    a0_share_audit = 100 * ma12["A0"]["loss_share_3way"]["contrast_teacher"]
    ct_keys = {key(r) for r in recs if is_ct(r)}
    all_keys = [key(r) for r in recs]
    a0_share = share(all_keys, lt, ct_keys)
    if abs(a0_share - a0_share_audit) > 0.01:
        raise SystemExit(f"A0 share {a0_share:.4f} != mask_audit12 {a0_share_audit:.4f}")
    lo, hi = a3_share - TOL_PP, a3_share + TOL_PP
    by_q = {}
    for r in recs:
        by_q.setdefault(qid(r), []).append(key(r))
    perm = np.random.default_rng(DRAW_SEED).permutation(len(pool))
    removed_q, removed_k, trace = [], set(), []
    reached = False
    for i in perm:
        q = pool[i]
        removed_q.append(q)
        removed_k |= set(by_q[q])
        s = share([k for k in all_keys if k not in removed_k], lt, ct_keys)
        trace.append({"step": len(removed_q), "question": q, "records": len(by_q[q]), "share_pct": round(s, 3)})
        if lo <= s <= hi:
            reached = True
            break
    keep_recs = [r for r in recs if key(r) not in removed_k]
    final_share = share([key(r) for r in keep_recs], lt, ct_keys)
    removed_recs = [r for r in recs if key(r) in removed_k]
    rem_body = {"arm": "A3T", "rule": "A0 − 요금 지표가 아닌 근접 대조 질문(질문 단위 통째로), default_rng(20261106).permutation 순서로 하나씩, A3 비중 ± 2pp에 들면 멈춤",
                "draw_seed": DRAW_SEED, "target_share_pct": round(a3_share, 3), "accept_range_pct": [round(lo, 3), round(hi, 3)], "reached_target": reached,
                "pool_questions": len(pool), "pool_question_list_sha256": hashlib.sha256("\n".join(pool).encode()).hexdigest(), "pool": pool,
                "removed_questions": len(removed_q), "removed_records": len(removed_k), "final_share_pct": round(final_share, 3), "trace": trace,
                "removed": [{"key": key(r), "corpus_group": r["metadata"]["corpus_group"], "loss_scope": r["metadata"]["loss_scope"], "contrast_teacher": is_ct(r),
                             "contrast_set": r["metadata"].get("contrast_set"), "loss_tokens": lt[key(r)]} for r in removed_recs]}
    (HERE / "removed_A3T.json").write_text(json.dumps(rem_body, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    sel = [i for i, r in enumerate(recs) if key(r) not in removed_k]
    h = write_arm("A3T", [lines[i] for i in sel], keep_recs, v4_manifest,
                  f"ablation_013 A3T = V4에서 요금 지표가 아닌 근접 대조 질문 {len(removed_q)}개(레코드 {len(removed_k)})를 뺌(뽑기 seed {DRAW_SEED}); build13.py")
    a3_recs = [json.loads(l) for l in (A11B / "A3/full/sft_train.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    a3_keys = {key(r) for r in a3_recs}
    if not a3_keys <= set(all_keys):
        raise SystemExit("A3 not subset of A0")
    summary = {"label": "ablation_013 build13 (결정 263 D4·A0 짝 seed)", "built": datetime.now(timezone.utc).isoformat(),
               "input": {"v4_train": str(v4_path.relative_to(ROOT)), "v4_train_sha256": sha_file(v4_path), "corpus_v6_sha256": sha_file(CORPUS),
                         "mask_audit12_sha256": sha_file(INV / "ablation_012/build/mask_audit12.json"),
                         "a11_build_summary_sha256": sha_file(A11B / "build_summary.json"), "a12_build_summary_sha256": sha_file(INV / "ablation_012/build/build_summary.json")},
               "checks": checks,
               "a3t": {"pool_rule": "(corpus provenance.kind == r2_contrast ∪ 근접 대조 teacher 레코드가 있는 질문) − 요금 지표(subtype ∈ BILLING), V4 안, id 정렬",
                       "pool_questions": len(pool), "pool_records": sum(len(by_q[q]) for q in pool),
                       "pool_by_group": dict(Counter(corpus[q]["corpus_group"] + ":" + str((corpus[q].get("provenance") or {}).get("group") or (corpus[q].get("provenance") or {}).get("kind")) for q in pool)),
                       "pool_contrast_teacher_records": sum(1 for q in pool for k in by_q[q] if k in ct_keys),
                       "target_share_pct": round(a3_share, 3), "accept_range_pct": [round(lo, 3), round(hi, 3)], "a0_share_pct": round(a0_share, 3),
                       "reached_target": reached, "removed_questions": len(removed_q), "removed_records": len(removed_k), "final_share_pct": round(final_share, 3),
                       "share_if_entire_pool_removed_pct": round(share([k for k in all_keys if k.split("|", 1)[0] not in set(pool)], lt, ct_keys), 3),
                       "train_file": "sft_dpo_inventory/ablation_013/build/A3T/full/sft_train.jsonl", "train_sha256": h[0], "question_list_sha256": h[1]},
               "composition": {"A0": composition(recs, corpus, lt), "A3": composition(a3_recs, corpus, lt),
                               "A3R-d1": composition([r for r in recs if key(r) in set(json.loads((INV / "ablation_012/build/orders/record_order_A3R-d1_o1102.json").read_text(encoding="utf-8"))["record_sequence"])], corpus, lt),
                               "A3R-d2": composition([r for r in recs if key(r) in set(json.loads((INV / "ablation_012/build/orders/record_order_A3R-d2_o1102.json").read_text(encoding="utf-8"))["record_sequence"])], corpus, lt),
                               "A3T": composition(keep_recs, corpus, lt), "A3T_removed": composition(removed_recs, corpus, lt)},
               "orders": {}}
    od = HERE / "orders"
    od.mkdir(exist_ok=True)
    # 재현 검사: build11 호출로 seed 1102 순서 파일이 ablation_011 것과 같은지
    o_chk = order7b.order_file({"full": recs}, OLD_SEEDS[0])
    old = json.loads((A11B / f"orders/order_b2_o{OLD_SEEDS[0]}.json").read_text(encoding="utf-8"))
    if json.dumps(o_chk, ensure_ascii=False, indent=1) + "\n" != (A11B / f"orders/order_b2_o{OLD_SEEDS[0]}.json").read_text(encoding="utf-8") or o_chk["order_sha256"] != old["order_sha256"]:
        raise SystemExit("order7b.order_file does not reproduce ablation_011 order_b2_o1102.json")
    summary["order_reproduction_check"] = {"seed": OLD_SEEDS[0], "byte_identical_to_ablation_011": True}
    for s in OLD_SEEDS:
        a0 = json.loads((A11B / f"orders/record_order_A0_o{s}.json").read_text(encoding="utf-8"))
        a0_seq = a0["record_sequence"]
        if a0_seq != a0["a0_record_sequence"] or order7b.sha(a0_seq) != a0["record_sequence_sha256"] or set(a0_seq) != set(all_keys):
            raise SystemExit(f"ablation_011 A0 order o{s} check failed")
        seq = [k for k in a0_seq if k not in removed_k]
        rs = order7b.run_stats([k.split("|", 1)[0] for k in seq])
        body = {"arm": "A3T", "seed": s, "rule": "ablation_011 A0 O4' 레코드 열(record_order_A0_o<seed>.json)에서 이 arm에 없는 레코드만 지움(상대 순서 유지)",
                "a0_order_file": f"order_b2_o{s}.json(ablation_011/build/orders)", "a0_order_sha256": a0["a0_order_sha256"],
                "a0_record_sequence_sha256": a0["a0_record_sequence_sha256"], "records": len(seq), "record_sequence_sha256": order7b.sha(seq), "run_stats": rs,
                "max_run_limit": MAX_RUN, "max_run_ok": rs["max_run"] <= MAX_RUN, "a0_record_sequence": a0_seq, "record_sequence": seq}
        (od / f"record_order_A3T_o{s}.json").write_text(json.dumps(body, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        summary["orders"][f"A3T_o{s}"] = {"records": len(seq), "record_sequence_sha256": body["record_sequence_sha256"], "run_stats": rs, "max_run_ok": body["max_run_ok"]}
        if not body["max_run_ok"]:
            (HERE / "build_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
            raise SystemExit(f"STOP: A3T o{s} max run {rs['max_run']} > {MAX_RUN}")
    for s in NEW_SEEDS:
        o = order7b.order_file({"full": recs}, s)
        (od / f"order_b2_o{s}.json").write_text(json.dumps(o, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        a0_seq = [key(r) for r in order7b.order_records(recs, o["order"])]
        rs = order7b.run_stats([k.split("|", 1)[0] for k in a0_seq])
        body = {"arm": "A0", "seed": s, "rule": "A0 O4' 순서(order_b2_o<seed>.json, order7b.order_records) 그대로(build11 A0와 같은 방법)",
                "a0_order_file": f"order_b2_o{s}.json", "a0_order_sha256": o["order_sha256"], "a0_record_sequence_sha256": order7b.sha(a0_seq),
                "records": len(a0_seq), "record_sequence_sha256": order7b.sha(a0_seq), "run_stats": rs, "max_run_limit": MAX_RUN,
                "max_run_ok": rs["max_run"] <= MAX_RUN, "a0_record_sequence": a0_seq, "record_sequence": a0_seq}
        (od / f"record_order_A0_o{s}.json").write_text(json.dumps(body, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        summary["orders"][f"A0_o{s}"] = {"order_b2_sha256": o["order_sha256"], "records": len(a0_seq), "record_sequence_sha256": body["record_sequence_sha256"],
                                         "run_stats": rs, "max_run_ok": body["max_run_ok"], "order7b_arm_run_stats": o["arms"]["full"]["run_stats"]}
        if not body["max_run_ok"]:
            (HERE / "build_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
            raise SystemExit(f"STOP: A0 o{s} max run {rs['max_run']} > {MAX_RUN}")
    (HERE / "build_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"checks": checks, "a3t": {k: v for k, v in summary["a3t"].items()}, "orders": {k: v["run_stats"]["max_run"] for k, v in summary["orders"].items()},
                      "comp": {a: (c["records"], c["questions"], c["loss_share_pct"]) for a, c in summary["composition"].items()}}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
