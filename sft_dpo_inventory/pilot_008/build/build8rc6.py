# -*- coding: utf-8 -*-
"""RC6 빌드(pilot_008 S2, 결정 223 X3). RC6 = RC5 Full + batch011 승인분. Full arm만(결정 213). 모델 호출 없음.

    hfvenv/bin/python sft_dpo_inventory/pilot_008/build/build8rc6.py   # -> build/RC6/full/{sft_train,sft_valid}.jsonl·manifest.json, build/RC6/order_b2_o<seed>.json,
                                                                         #    build/RC6/build_summary.json

1. 바탕: RC5 Full 1,811레코드(``pilot_007/build/RC5/full``) 그대로.
2. r2 근접 대조(batch011 승인 40): J-b011 base 표본(greedy 1 + 8) 중 승인 corpus v4 판정(``judge8.py`` → ``self/Jb011_full_judgement_v4.json``) 정답 표본,
   build7rc5와 같은 8b 형식·계약(``target_ok``)·길이 ≤ 12,288, 질문당 8b 상한 4(``random.Random(20261016)``). 표본이 없는 문항은 들어가지 못함.
3. **유형 상한 C-1**(결정 88·92·223): RC5 질문 + 새 r2에 build7rc5와 같은 계산(예외: batch006 변형·batch007, τ 0.09, ``caps_for``). 칸마다 batch011 r2를 먼저
   (``Random(f"{SEED}:{cell}:batch011")`` 순서), 남은 자리를 기존 질문(``Random(f"{SEED}:{cell}")`` 순서)으로. 밀려난 기존 질문은 레코드째 뺀다.
4. **거부 레코드(r1, 상한 예외)**: 수 R = round(0.08 · N / 0.92)(N = 거부 아닌 Full 레코드) — 거부가 전체의 8%. 출처 S-3:
   S-1 J-b011 base 순수 거부 표본(응답 JSON이 정확히 ``{"unsupported": true}``, 생성 끝, 길이 ≤ 12,288; 질문당 최대 4, 내용 중복 제거; 질문을 고친 b011-015 제외) 먼저,
   S-2 ``refusal_targets8``(짧은 근거 + ``{"unsupported": true}``)로 모자란 만큼 — 질문별 합이 고르게(합이 가장 적은 질문부터 하나씩), 질문당 합 최대 4.
   못 채우면 채운 만큼(실제 비율 보고). 손실 범위는 모두 ``json_only``(결정 86), 손실 가중 없음.
5. 검사: 길이 ≤ 12,288, 손실 token(거부 레코드 JSON token), 같은 범주 r2가 RC6에 들어갔는지(모델 거부 표본이 생긴 r1 범주), 질문 목록 sha256,
   O4' 순서 파일 5개(43·20261016·7·11·2027)와 연속 길이(최대 ≤ 4).
"""
import hashlib
import json
import random
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
P8 = HERE.parent
INV = P8.parent
ROOT = INV.parent
for p in (ROOT, INV / "pilot_004_prep", INV / "pilot_prep_004/type_target", INV / "pilot_006_prep/aug300", INV / "thinking_prep_001",
          INV / "pilot_006_prep/self_samples", INV / "pilot_007/train", HERE):
    sys.path.insert(0, str(p))
RC5 = INV / "pilot_007/build/RC5"
OUT = HERE / "RC6"
RAW = ROOT / "training/generated/pilot_008/self/raw/Jb011_full_raw.jsonl"
JUDGE = P8 / "self/Jb011_full_judgement_v4.json"
SELF_CAP, REF_CAP, MAXLEN, SEED, SHARE = 4, 4, 12288, 20261016, 0.08
ORDER_SEEDS = (43, 20261016, 7, 11, 2027)
TARGET_JSON = '{"unsupported": true}'


def read_jsonl(p):
    return [json.loads(l) for l in Path(p).read_text(encoding="utf-8").splitlines() if l.strip()]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    import approved6 as AP
    AP.VERSION = "v4"
    AP.MANIFEST["v4"] = "manifest_v4.json"
    import hf_thinking as H
    import order7b
    import refusal_targets8 as RT
    import type_caps as TC
    from grounding.full_renderer import render_full
    from training.data import thinking as TH
    from training.data.validation import assess, target_ok
    from training.trainer_common import expected_system_prompt, render_prompt
    from transformers import AutoTokenizer
    from type_target import profile
    corpus = AP.load(version="v4")
    tok = AutoTokenizer.from_pretrained(H.MODEL, revision=H.REVISION)
    cfg = {"chat_template_kwargs": {"enable_thinking": True}}
    system = expected_system_prompt("full")

    def length(rec):
        return len(tok(render_prompt(tok, rec["messages"][:2], cfg), add_special_tokens=False)["input_ids"]) + len(tok(rec["messages"][2]["content"], add_special_tokens=False)["input_ids"]) + 1

    base = read_jsonl(RC5 / "full/sft_train.jsonl")
    old_q = sorted({r["metadata"]["source_record_id"] for r in base})
    b011 = {c: corpus[c] for c in corpus if corpus[c]["corpus_group"] == "batch011"}
    r2q = sorted(c for c in b011 if b011[c]["provenance"]["kind"] == "r2_contrast")
    r1q = sorted(c for c in b011 if b011[c]["provenance"]["kind"] == "r1_refusal")
    judged = json.loads(JUDGE.read_text(encoding="utf-8"))
    ok_traces = {t for q in judged["per_question"] if q["status"] == "approved" for t in q["correct_trace_ids"]}
    raws = read_jsonl(RAW)
    stats = Counter()
    # 2. r2 8b 레코드
    cand = defaultdict(list)
    for r in raws:
        cid = f"b011:{r['id']}"
        if cid not in r2q or r["trace_id"] not in ok_traces:
            continue
        try:
            good = target_ok(assess(TH.response_json(r["raw_text"]), corpus[cid]["question"]), {})
        except Exception:  # noqa: BLE001
            good = False
        if not good:
            stats["r2:contract_dropped"] += 1
            continue
        rec = {"messages": [{"role": "system", "content": system}, {"role": "user", "content": corpus[cid]["question"]}, {"role": "assistant", "content": r["raw_text"]}],
               "metadata": {"source_record_id": cid, "source": "hf", "loss_scope": "json_only", "grounding_target": "full", "trace_id": f"Jb011:{r['trace_id']}",
                            "trace_sha256": r["raw_sha256"], "format": TH.FORMAT, "origin": "Jb011 vLLM BF16 base sample (approved-gold v4 correct)",
                            "representation": "flat", "corpus_group": "batch011", "_rc": "RC6: pilot_008 학습 후보", "k3_scope_name_family": False, "parent_intent": cid}}
        n = length(rec)
        rec["metadata"]["tokens"] = n
        if n > MAXLEN:
            stats["r2:over_len"] += 1
            continue
        cand[cid].append(rec)
        stats["r2:usable"] += 1
    rng = random.Random(SEED)
    add = {}
    for cid in sorted(cand):
        seen, uniq = set(), []
        for r in cand[cid]:
            h = hashlib.sha256(r["messages"][2]["content"].encode()).hexdigest()
            if h not in seen:
                seen.add(h)
                uniq.append(r)
        add[cid] = sorted(rng.sample(uniq, min(SELF_CAP, len(uniq))), key=lambda r: r["metadata"]["trace_id"])
    no_records = [c for c in r2q if c not in add]
    # 3. 유형 상한 C-1
    allq = old_q + sorted(add)
    cell = {c: profile(render_full(corpus[c]["semantics"]))["cell"] for c in allq}
    b6 = json.loads((INV / "batch006/candidates_checked.json").read_text(encoding="utf-8"))["candidates"]
    exempt = frozenset(f"t2pc:{c['id']}" for c in b6 if c.get("variant")) | frozenset(c for c in allq if corpus[c]["corpus_group"] == "batch007")
    nonex = [c for c in allq if c not in exempt]
    m_total, caps = TC.caps_for(Counter(cell[c] for c in nonex), TC.DEVD, 0.09)
    by_cell = defaultdict(lambda: {"new": [], "old": []})
    for c in nonex:
        by_cell[cell[c]]["new" if c in add else "old"].append(c)
    keep, cap_report = set(c for c in allq if c in exempt), {}
    for cl, g in sorted(by_cell.items()):
        cap = caps.get(cl, 0)
        new_o, old_o = sorted(g["new"]), sorted(g["old"])
        random.Random(f"{TC.SEED}:{cl}:batch011").shuffle(new_o)
        random.Random(f"{TC.SEED}:{cl}").shuffle(old_o)
        take_new = new_o[:cap]
        take_old = old_o[:max(0, cap - len(take_new))]
        displaced = sorted(set(old_o[:cap]) - set(take_old))
        keep |= set(take_new) | set(take_old)
        cap_report[cl] = {"cap": cap, "batch011_available": len(new_o), "batch011_added": len(take_new), "existing_available": len(old_o),
                          "existing_kept": len(take_old), "existing_displaced_by_batch011": len(displaced), "displaced_ids": displaced}
    new_kept = sorted(c for c in add if c in keep)
    capped_new = sorted(c for c in add if c not in keep)
    dropped_old = sorted(c for c in old_q if c not in keep)
    rows = [r for r in base if r["metadata"]["source_record_id"] in keep]
    for cid in new_kept:
        rows += add[cid]
    fin = Counter(cell[c] for c in keep if c not in exempt)
    tot = sum(fin.values())
    tv = sum(max(0.0, TC.DEVD.get(k, 0) - fin.get(k, 0) / tot) for k in set(TC.DEVD) | set(fin))
    n_nonref = len(rows)
    # 4. 거부 레코드
    R = round(SHARE * n_nonref / (1 - SHARE))
    s1 = defaultdict(list)
    for r in raws:
        cid = f"b011:{r['id']}"
        if cid not in r1q or cid == "b011:b011-015" or r.get("done_reason") != "stop" or "</think>" not in r["raw_text"]:
            continue
        tail = r["raw_text"].split("</think>", 1)[1].strip()
        try:
            if json.loads(tail) != {"unsupported": True}:
                continue
        except Exception:  # noqa: BLE001
            continue
        rec = {"messages": [{"role": "system", "content": system}, {"role": "user", "content": corpus[cid]["question"]}, {"role": "assistant", "content": r["raw_text"]}],
               "metadata": {"source_record_id": cid, "source": "hf", "loss_scope": "json_only", "grounding_target": "full", "trace_id": f"Jb011:{r['trace_id']}",
                            "trace_sha256": r["raw_sha256"], "format": TH.FORMAT, "origin": "S-1 Jb011 vLLM BF16 base sample (model refusal, exact {\"unsupported\": true})",
                            "representation": "flat", "corpus_group": "batch011", "refusal_source": "S-1", "_rc": "RC6: pilot_008 학습 후보",
                            "k3_scope_name_family": False, "parent_intent": cid}}
        n = length(rec)
        rec["metadata"]["tokens"] = n
        if n > MAXLEN:
            stats["s1:over_len"] += 1
            continue
        s1[cid].append(rec)
    rng = random.Random(f"{SEED}:refusal")
    refusal = defaultdict(list)
    for cid in sorted(s1):
        seen, uniq = set(), []
        for r in s1[cid]:
            h = hashlib.sha256(r["messages"][2]["content"].encode()).hexdigest()
            if h not in seen:
                seen.add(h)
                uniq.append(r)
        refusal[cid] = sorted(rng.sample(uniq, min(REF_CAP, len(uniq))), key=lambda r: r["metadata"]["trace_id"])
    n_s1 = sum(len(v) for v in refusal.values())
    if n_s1 > R:  # S-1만으로 넘치면 질문별로 고르게 줄인다(가장 많은 질문부터)
        while sum(len(v) for v in refusal.values()) > R:
            top = max(refusal, key=lambda c: (len(refusal[c]), c))
            refusal[top].pop()
    s2_count = Counter()
    while sum(len(refusal[c]) for c in r1q) < R:
        open_q = [c for c in r1q if len(refusal[c]) < REF_CAP]
        if not open_q:
            break
        c = min(open_q, key=lambda x: (len(refusal[x]), x))
        qid, gap = c.split(":", 1)[1], corpus[c]["provenance"]["gap"]
        v = s2_count[c]
        text = RT.content(qid, gap, v)
        rec = {"messages": [{"role": "system", "content": system}, {"role": "user", "content": corpus[c]["question"]}, {"role": "assistant", "content": text}],
               "metadata": {"source_record_id": c, "source": "refusal_target", "loss_scope": "json_only", "grounding_target": "full", "trace_id": f"S2:{qid}:v{v}",
                            "trace_sha256": hashlib.sha256(text.encode()).hexdigest(), "format": TH.FORMAT,
                            "origin": "S-2 거부 target(refusal_targets8, 짧은 근거 + {\"unsupported\": true}, 결정 223)", "representation": "flat",
                            "corpus_group": "batch011", "refusal_source": "S-2", "_rc": "RC6: pilot_008 학습 후보", "k3_scope_name_family": False, "parent_intent": c}}
        rec["metadata"]["tokens"] = length(rec)
        refusal[c].append(rec)
        s2_count[c] += 1
    ref_rows = [r for c in r1q for r in refusal[c]]
    rows += ref_rows
    # 5. 검사·쓰기
    over = [r["metadata"]["trace_id"] for r in rows if (r["metadata"].get("tokens") or length(r)) > MAXLEN]
    json_tok = Counter(len(tok(r["messages"][2]["content"].split("</think>", 1)[1].strip(), add_special_tokens=False)["input_ids"]) for r in ref_rows)
    gap_s1 = {corpus[c]["provenance"]["gap"].replace("r1_", "") for c in refusal if any(r["metadata"]["refusal_source"] == "S-1" for r in refusal[c])}
    r2_gap = {g: [c for c in r2q if corpus[c]["provenance"]["gap"] == f"r2_{g}"] for g in gap_s1}
    r2_cover = {g: {"r2_items": len(v), "in_rc6": sum(1 for c in v if c in new_kept), "missing": [c for c in v if c not in new_kept]} for g, v in r2_gap.items()}
    final_q = sorted({r["metadata"]["source_record_id"] for r in rows})
    d = OUT / "full"
    d.mkdir(parents=True, exist_ok=True)
    with (d / "sft_train.jsonl").open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    (d / "sft_valid.jsonl").write_text("", encoding="utf-8")
    man = json.loads((RC5 / "full/manifest.json").read_text(encoding="utf-8"))
    s = man["sft"]
    s.update(generated_at=datetime.now(timezone.utc).isoformat(), release_candidate="RC6",
             note="pilot_008 RC6 = RC5 Full + batch011 승인분(r2 8b J-b011 상한 칸에서 우선, r1 거부 S-1 base 표본 + S-2 거부 target 8%); build8rc6.py",
             train_count=len(rows), validation_count=0, questions=len(final_q), question_list_sha256=hashlib.sha256("\n".join(final_q).encode()).hexdigest(),
             by_source=dict(Counter(r["metadata"]["loss_scope"] for r in rows)),
             output_hashes={"sft_train.jsonl": sha(d / "sft_train.jsonl"), "sft_valid.jsonl": sha(d / "sft_valid.jsonl")})
    (d / "manifest.json").write_text(json.dumps(man, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    orders = {}
    recs = read_jsonl(d / "sft_train.jsonl")
    for sd in ORDER_SEEDS:
        o = order7b.order_file({"full": recs}, sd)
        (OUT / f"order_b2_o{sd}.json").write_text(json.dumps(o, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        orders[sd] = {"order_sha256": o["order_sha256"], "max_run_ok": o["max_run_ok"], "run_stats": o["arms"]["full"]["run_stats"]}
    summary = {"label": "RC6", "built": datetime.now(timezone.utc).isoformat(), "base": "RC5 full", "approved_corpus": "v4 (manifest_v4.json)",
               "records": len(rows), "questions": len(final_q), "question_list_sha256": s["question_list_sha256"],
               "composition": {"rc5_kept": len([r for r in base if r["metadata"]["source_record_id"] in keep]), "rc5_dropped_records": len(base) - len([r for r in base if r["metadata"]["source_record_id"] in keep]),
                               "r2_records": sum(len(add[c]) for c in new_kept), "r2_questions": len(new_kept), "refusal_records": len(ref_rows),
                               "refusal_s1": sum(1 for r in ref_rows if r["metadata"]["refusal_source"] == "S-1"),
                               "refusal_s2": sum(1 for r in ref_rows if r["metadata"]["refusal_source"] == "S-2"),
                               "refusal_questions": sum(1 for c in r1q if refusal[c]), "refusal_share": round(len(ref_rows) / len(rows), 4),
                               "refusal_target_R": R, "refusal_filled": len(ref_rows) >= R,
                               "refusal_per_question": dict(Counter(len(refusal[c]) for c in r1q)),
                               "s1_questions": sorted(c for c in refusal if any(r["metadata"]["refusal_source"] == "S-1" for r in refusal[c]))},
               "by_loss_scope": dict(Counter(r["metadata"]["loss_scope"] for r in rows)), "by_origin": dict(Counter(r["metadata"]["origin"][:60] for r in rows)),
               "type_cap": {"tau": 0.09, "max_total_nonexempt": m_total, "cells": cap_report, "tv_final": round(tv, 4),
                            "existing_questions_displaced": dropped_old, "r2_capped_out": capped_new, "r2_no_correct_sample": no_records},
               "r2_coverage_for_s1_categories": r2_cover, "self_stats": dict(stats),
               "checks": {"over_maxlen": over, "refusal_json_tokens": dict(json_tok), "orders": orders,
                          "all_orders_max_run_ok": all(v["max_run_ok"] for v in orders.values())}}
    (OUT / "build_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("records", "questions", "composition")}, ensure_ascii=False, indent=1))
    print(json.dumps({"tv": summary["type_cap"]["tv_final"], "displaced": len(dropped_old), "r2_capped_out": capped_new, "r2_no_sample": no_records,
                      "r2_cover": r2_cover, "checks": {"over": len(over), "json_tok": dict(json_tok), "orders_ok": summary["checks"]["all_orders_max_run_ok"]}},
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
