# -*- coding: utf-8 -*-
"""RC7 빌드(pilot_009 S2, 결정 235 Z3). RC7 = RC6 + batch012 승인분, S-2를 teacher 거부 trace로 대체. Full arm만. 모델 호출 없음.
``pilot_008/build/build8rc6.py``의 사본(그 파일은 고치지 않음). 바꾼 것만 적는다.

    hfvenv/bin/python sft_dpo_inventory/pilot_009/build/build9rc7.py   # -> build/RC7/full/{sft_train,sft_valid}.jsonl·manifest.json, build/RC7/order_b2_o<seed>.json,
                                                                         #    build/RC7/build_summary.json

1. 바탕: RC6 Full 2,005레코드 중 거부 레코드(S-1·S-2 160)를 뺀 답하는 레코드 1,845(RC5 유지분 + batch011 r2) 그대로.
2. 새 r2(근접 대조):
   - batch012 r2(승인 40): J-b012 base 표본(greedy 1 + 8) 중 승인 corpus v5 판정(``judge9.py`` → ``self/Jb012_full_judgement_v5.json``) 정답 표본,
     build8rc6와 같은 8b 형식·계약(``target_ok``)·길이 ≤ 12,288, 질문당 8b 상한 4(``random.Random(20261016)``). 표본이 없는 11문항은 들어가지 못함(결정 235).
   - batch011 r2 teacher(RC6에 못 들어간 11 중 TEACH-R v3b 통과 trace가 있는 질문): ``teacher_filter9.json``의 쓸 trace(c2 정리·절 이름 거르기 뒤), ``full_response``,
     질문당 상한 4(``random.Random("20261016:r2teacher")``). 통과 trace가 없는 b011-089·090·091은 빠짐(결정 235).
3. **유형 상한 C-1**: RC6 답하는 질문 + 새 r2에 build8rc6와 같은 계산(예외: batch006 변형·batch007, τ 0.09). 칸마다 새 r2(batch012·batch011 teacher)를 먼저
   (``Random(f"{SEED}:{cell}:rc7new")`` 순서), 남은 자리를 기존 질문(``Random(f"{SEED}:{cell}")`` 순서)으로. 밀려난 기존 질문은 레코드째 뺀다.
4. **거부 레코드(r1, 상한 예외)**: R = round(0.08 · N / 0.92)(N = 답하는 레코드). 대상 질문 batch011 r1 60 + batch012 r1 승인 60.
   - S-1 먼저: J-b011·J-b012 base 순수 거부 표본(응답 JSON이 정확히 ``{"unsupported": true}``, 생성 끝, 길이 ≤ 12,288; 질문당 최대 4, 내용 중복 제거;
     질문을 고친 b011-015·b012-001·021·039 제외 — 표본이 원래 질문에 대한 것). ``json_only``.
   - teacher 거부 trace로 모자란 만큼: ``teacher_filter9.json``의 쓸 trace(질문별로 ``Random(f"{SEED}:teacher:{qid}")``로 섞은 순서), 질문별 합이 고르게
     (합이 가장 적은 질문부터 하나씩), 질문당 합 최대 4. 레코드 = ``teacher_refusal9.to_record_content``(``<think>…</think>`` + ``{"unsupported": true}``), ``full_response``(결정 86).
   - S-2는 쓰지 않는다. 못 채우면 채운 만큼(실제 비율 보고).
5. 검사: 길이 ≤ 12,288, teacher 거부 레코드의 질문 문장 = corpus v5 질문, 질문 목록 sha256, O4' 순서 파일 5개(43·20261016·7·11·2027)와 연속 길이(최대 ≤ 4).
   손실 token·마스크는 ``mask_audit9.py``.
"""
import hashlib
import json
import random
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
P9 = HERE.parent
INV = P9.parent
ROOT = INV.parent
for p in (ROOT, INV / "pilot_004_prep", INV / "pilot_prep_004/type_target", INV / "pilot_006_prep/aug300", INV / "thinking_prep_001",
          INV / "pilot_006_prep/self_samples", INV / "pilot_007/train", INV / "pilot_006/teacher", INV / "pilot_009/teacher", HERE):
    sys.path.insert(0, str(p))
RC6 = INV / "pilot_008/build/RC6"
OUT = HERE / "RC7"
RAW11 = ROOT / "training/generated/pilot_008/self/raw/Jb011_full_raw.jsonl"
RAW12 = ROOT / "training/generated/pilot_009/self/raw/Jb012_full_raw.jsonl"
JUDGE12 = P9 / "self/Jb012_full_judgement_v5.json"
FILTER = HERE / "teacher_filter9.json"
TRACES = ROOT / "training/generated/pilot_009/teacher_teachr/traces.jsonl"
SELF_CAP, REF_CAP, R2T_CAP, MAXLEN, SEED, SHARE = 4, 4, 4, 12288, 20261016, 0.08
ORDER_SEEDS = (43, 20261016, 7, 11, 2027)
MODIFIED = frozenset({"b011:b011-015", "b012:b012-001", "b012:b012-021", "b012:b012-039"})
RC = "RC7: pilot_009 학습 후보"


def read_jsonl(p):
    return [json.loads(l) for l in Path(p).read_text(encoding="utf-8").splitlines() if l.strip()]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def dedup(recs):
    seen, uniq = set(), []
    for r in recs:
        h = hashlib.sha256(r["messages"][2]["content"].encode()).hexdigest()
        if h not in seen:
            seen.add(h)
            uniq.append(r)
    return uniq


def main():
    import approved6 as AP
    AP.VERSION = "v5"
    AP.MANIFEST["v5"] = "manifest_v5.json"
    import hf_thinking as H
    import order7b
    import teacher6v3 as T3
    import teacher_refusal9 as TR
    import type_caps as TC
    from grounding.full_renderer import render_full
    from training.data import thinking as TH
    from training.data.validation import assess, target_ok
    from training.trainer_common import expected_system_prompt, render_prompt
    from transformers import AutoTokenizer
    from type_target import profile
    corpus = AP.load(version="v5")
    tok = AutoTokenizer.from_pretrained(H.MODEL, revision=H.REVISION)
    cfg = {"chat_template_kwargs": {"enable_thinking": True}}
    system = expected_system_prompt("full")
    plen = {}

    def length(rec):
        q = rec["messages"][1]["content"]
        if q not in plen:
            plen[q] = len(tok(render_prompt(tok, rec["messages"][:2], cfg), add_special_tokens=False)["input_ids"])
        return plen[q] + len(tok(rec["messages"][2]["content"], add_special_tokens=False)["input_ids"]) + 1

    rc6 = read_jsonl(RC6 / "full/sft_train.jsonl")
    base = [r for r in rc6 if not r["metadata"].get("refusal_source")]
    rc6_refusal = len(rc6) - len(base)
    old_q = sorted({r["metadata"]["source_record_id"] for r in base})
    grp = lambda g: {c: corpus[c] for c in corpus if corpus[c]["corpus_group"] == g}  # noqa: E731
    b011, b012 = grp("batch011"), grp("batch012")
    kind = lambda c: corpus[c]["provenance"]["kind"]  # noqa: E731
    r2q12 = sorted(c for c in b012 if kind(c) == "r2_contrast")
    r1q = sorted(c for c in b011 if kind(c) == "r1_refusal") + sorted(c for c in b012 if kind(c) == "r1_refusal")
    r2q11_missing = sorted(c for c in b011 if kind(c) == "r2_contrast" and c not in old_q)
    stats = Counter()
    # 2a. batch012 r2 8b 레코드
    judged = json.loads(JUDGE12.read_text(encoding="utf-8"))
    ok_traces = {t for q in judged["per_question"] if q["status"] == "approved" for t in q["correct_trace_ids"]}
    raws12 = read_jsonl(RAW12)
    cand = defaultdict(list)
    for r in raws12:
        cid = f"b012:{r['id']}"
        if cid not in r2q12 or r["trace_id"] not in ok_traces:
            continue
        try:
            good = target_ok(assess(TH.response_json(r["raw_text"]), corpus[cid]["question"]), {})
        except Exception:  # noqa: BLE001
            good = False
        if not good:
            stats["r2_b012:contract_dropped"] += 1
            continue
        rec = {"messages": [{"role": "system", "content": system}, {"role": "user", "content": corpus[cid]["question"]}, {"role": "assistant", "content": r["raw_text"]}],
               "metadata": {"source_record_id": cid, "source": "hf", "loss_scope": "json_only", "grounding_target": "full", "trace_id": f"Jb012:{r['trace_id']}",
                            "trace_sha256": r["raw_sha256"], "format": TH.FORMAT, "origin": "Jb012 vLLM BF16 base sample (approved-gold v5 correct)",
                            "representation": "flat", "corpus_group": "batch012", "_rc": RC, "k3_scope_name_family": False, "parent_intent": cid}}
        n = length(rec)
        rec["metadata"]["tokens"] = n
        if n > MAXLEN:
            stats["r2_b012:over_len"] += 1
            continue
        cand[cid].append(rec)
        stats["r2_b012:usable"] += 1
    rng = random.Random(SEED)
    add = {}
    for cid in sorted(cand):
        uniq = dedup(cand[cid])
        add[cid] = sorted(rng.sample(uniq, min(SELF_CAP, len(uniq))), key=lambda r: r["metadata"]["trace_id"])
    r2_b012_no_sample = [c for c in r2q12 if c not in add]
    # 2b. batch011 r2 teacher 레코드(v3b, full_response)
    filt = json.loads(FILTER.read_text(encoding="utf-8"))
    traces = {t["trace_id"]: t for t in read_jsonl(TRACES)}
    rng_t = random.Random(f"{SEED}:r2teacher")
    for cid in r2q11_missing:
        use = filt["usable"].get(cid, [])
        recs = []
        for u in use:
            t = traces[u["trace_id"]]
            tr = {"trace_id": f"{u['trace_id']}", "thinking": u["thinking"], "model": t["model"], "model_digest": t["model_digest"]}
            r = T3.to_arm_records(tr, corpus[cid]["semantics"], corpus[cid]["question"], cid, "v3b")["full"]
            if r["messages"][0]["content"] != system:
                raise SystemExit(f"system prompt mismatch {cid}")
            r["metadata"].update(origin="TEACH-R teacher v3b (qwen3.8:27b, checks passed, c2·section filter)", format=TH.FORMAT, representation="flat",
                                 corpus_group="batch011", _rc=RC, k3_scope_name_family=False, parent_intent=cid, c2_removed_lines=len(u["c2_removed"]),
                                 section_edit=u["edit"], thinking_sha256_raw=t["thinking_sha256"])
            n = length(r)
            r["metadata"]["tokens"] = n
            if n > MAXLEN:
                stats["r2_teacher:over_len"] += 1
                continue
            recs.append(r)
        if recs:
            uniq = dedup(recs)
            add[cid] = sorted(rng_t.sample(uniq, min(R2T_CAP, len(uniq))), key=lambda r: r["metadata"]["trace_id"])
    r2_b011_no_teacher = [c for c in r2q11_missing if c not in add]
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
        random.Random(f"{TC.SEED}:{cl}:rc7new").shuffle(new_o)
        random.Random(f"{TC.SEED}:{cl}").shuffle(old_o)
        take_new = new_o[:cap]
        take_old = old_o[:max(0, cap - len(take_new))]
        displaced = sorted(set(old_o[:cap]) - set(take_old))
        keep |= set(take_new) | set(take_old)
        cap_report[cl] = {"cap": cap, "new_available": len(new_o), "new_added": len(take_new), "existing_available": len(old_o),
                          "existing_kept": len(take_old), "existing_displaced_by_new": len(displaced), "displaced_ids": displaced,
                          "new_capped_out": sorted(set(new_o) - set(take_new))}
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
    for tag, raw_p, pre in (("Jb011", RAW11, "b011"), ("Jb012", RAW12, "b012")):
        for r in read_jsonl(raw_p):
            cid = f"{pre}:{r['id']}"
            if cid not in r1q or cid in MODIFIED or r.get("done_reason") != "stop" or "</think>" not in r["raw_text"]:
                continue
            tail = r["raw_text"].split("</think>", 1)[1].strip()
            try:
                if json.loads(tail) != {"unsupported": True}:
                    continue
            except Exception:  # noqa: BLE001
                continue
            rec = {"messages": [{"role": "system", "content": system}, {"role": "user", "content": corpus[cid]["question"]}, {"role": "assistant", "content": r["raw_text"]}],
                   "metadata": {"source_record_id": cid, "source": "hf", "loss_scope": "json_only", "grounding_target": "full", "trace_id": f"{tag}:{r['trace_id']}",
                                "trace_sha256": r["raw_sha256"], "format": TH.FORMAT,
                                "origin": f"S-1 {tag} vLLM BF16 base sample (model refusal, exact {{\"unsupported\": true}})",
                                "representation": "flat", "corpus_group": corpus[cid]["corpus_group"], "refusal_source": "S-1", "_rc": RC,
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
        uniq = dedup(s1[cid])
        refusal[cid] = sorted(rng.sample(uniq, min(REF_CAP, len(uniq))), key=lambda r: r["metadata"]["trace_id"])
    while sum(len(v) for v in refusal.values()) > R:  # S-1만으로 넘치면 질문별로 고르게 줄인다(가장 많은 질문부터)
        top = max(refusal, key=lambda c: (len(refusal[c]), c))
        refusal[top].pop()
    pools = {}
    for c in r1q:
        if c in MODIFIED and c.startswith("b012"):
            pools[c] = []
            continue
        lst = list(filt["usable"].get(c, []))
        random.Random(f"{SEED}:teacher:{c}").shuffle(lst)
        pools[c] = lst
    t_count = Counter()
    question_mismatch = []
    while sum(len(refusal[c]) for c in r1q) < R:
        open_q = [c for c in r1q if len(refusal[c]) < REF_CAP and t_count[c] < len(pools[c])]
        if not open_q:
            break
        c = min(open_q, key=lambda x: (len(refusal[x]), x))
        u = pools[c][t_count[c]]
        t = traces[u["trace_id"]]
        text = TR.to_record_content(u["thinking"])
        rec = {"messages": [{"role": "system", "content": system}, {"role": "user", "content": corpus[c]["question"]}, {"role": "assistant", "content": text}],
               "metadata": {"source_record_id": c, "source": "teacher", "loss_scope": "full_response", "grounding_target": "full", "trace_id": u["trace_id"],
                            "trace_sha256": hashlib.sha256(text.encode()).hexdigest(), "thinking_sha256_raw": t["thinking_sha256"],
                            "teacher_model": t["model"], "teacher_model_digest": t["model_digest"], "teacher_instruction": t["teacher_instruction"],
                            "teacher_instruction_sha256": t["teacher_instruction_sha256"], "reasoning_human_reviewed": False, "format": TH.FORMAT,
                            "origin": "teacher 거부 trace(TEACH-R teacher_refusal_v1, qwen3.8:27b, checks passed, c2·절 이름 거르기, 결정 235)",
                            "representation": "flat", "corpus_group": corpus[c]["corpus_group"], "refusal_source": "teacher", "_rc": RC,
                            "c2_removed_lines": len(u["c2_removed"]), "section_edit": u["edit"], "k3_scope_name_family": False, "parent_intent": c}}
        rec["metadata"]["tokens"] = length(rec)
        refusal[c].append(rec)
        t_count[c] += 1
    # 검사: teacher 레코드 질문 = TEACH-R 대상 질문
    tg = {t["id"]: t for t in json.loads((P9 / "teacher/teachr_targets.json").read_text(encoding="utf-8"))}
    for c in r1q:
        for r in refusal[c]:
            if r["metadata"]["refusal_source"] == "teacher" and tg[c]["question"] != corpus[c]["question"]:
                question_mismatch.append(c)
    for c in add:
        if any(r["metadata"]["source"] == "teacher" for r in add[c]) and tg[c]["question"] != corpus[c]["question"]:
            question_mismatch.append(c)
    ref_rows = [r for c in r1q for r in refusal[c]]
    rows += ref_rows
    # 5. 검사·쓰기
    over = [r["metadata"]["trace_id"] for r in rows if (r["metadata"].get("tokens") or length(r)) > MAXLEN]
    final_q = sorted({r["metadata"]["source_record_id"] for r in rows})
    d = OUT / "full"
    d.mkdir(parents=True, exist_ok=True)
    with (d / "sft_train.jsonl").open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    (d / "sft_valid.jsonl").write_text("", encoding="utf-8")
    man = json.loads((RC6 / "full/manifest.json").read_text(encoding="utf-8"))
    s = man["sft"]
    s.update(generated_at=datetime.now(timezone.utc).isoformat(), release_candidate="RC7",
             note="pilot_009 RC7 = RC6 답하는 레코드 + batch012 승인분(r2 8b J-b012·batch011 r2 teacher, 상한 칸에서 우선) + r1 거부 8%(S-1 base 표본 + teacher 거부 trace, S-2 없음); build9rc7.py",
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
    teacher_recs = sum(1 for r in rows if r["metadata"]["loss_scope"] == "full_response")
    summary = {"label": "RC7", "built": datetime.now(timezone.utc).isoformat(), "base": "RC6 full (거부 레코드 160 뺌)", "approved_corpus": "v5 (manifest_v5.json)",
               "records": len(rows), "questions": len(final_q), "question_list_sha256": s["question_list_sha256"],
               "composition": {"rc6_answered_base": len(base), "rc6_refusal_removed": rc6_refusal,
                               "rc6_kept": len([r for r in base if r["metadata"]["source_record_id"] in keep]),
                               "rc6_dropped_records": len(base) - len([r for r in base if r["metadata"]["source_record_id"] in keep]),
                               "r2_b012_records": sum(len(add[c]) for c in new_kept if c.startswith("b012")),
                               "r2_b012_questions": sum(1 for c in new_kept if c.startswith("b012")),
                               "r2_b011_teacher_records": sum(len(add[c]) for c in new_kept if c.startswith("b011")),
                               "r2_b011_teacher_questions": sum(1 for c in new_kept if c.startswith("b011")),
                               "answered_records_N": n_nonref, "refusal_records": len(ref_rows),
                               "refusal_s1": sum(1 for r in ref_rows if r["metadata"]["refusal_source"] == "S-1"),
                               "refusal_teacher": sum(1 for r in ref_rows if r["metadata"]["refusal_source"] == "teacher"),
                               "refusal_teacher_section_edited": sum(1 for r in ref_rows if r["metadata"].get("section_edit") == "section_line_strip"),
                               "refusal_questions": sum(1 for c in r1q if refusal[c]), "refusal_share": round(len(ref_rows) / len(rows), 4),
                               "refusal_target_R": R, "refusal_filled": len(ref_rows) >= R,
                               "refusal_per_question": dict(sorted(Counter(len(refusal[c]) for c in r1q).items())),
                               "refusal_questions_without_records": sorted(c for c in r1q if not refusal[c]),
                               "s1_questions": sorted(c for c in refusal if any(r["metadata"]["refusal_source"] == "S-1" for r in refusal[c])),
                               "teacher_records_total(full_response)": teacher_recs, "teacher_record_share": round(teacher_recs / len(rows), 4)},
               "refusal_by_gap": {g: {"questions": sum(1 for c in r1q if corpus[c]["provenance"]["gap"] == g),
                                      "records": sum(len(refusal[c]) for c in r1q if corpus[c]["provenance"]["gap"] == g),
                                      "s1": sum(1 for c in r1q if corpus[c]["provenance"]["gap"] == g for r in refusal[c] if r["metadata"]["refusal_source"] == "S-1")}
                                  for g in sorted({corpus[c]["provenance"]["gap"] for c in r1q})},
               "by_loss_scope": dict(Counter(r["metadata"]["loss_scope"] for r in rows)), "by_origin": dict(Counter(r["metadata"]["origin"][:60] for r in rows)),
               "type_cap": {"tau": 0.09, "max_total_nonexempt": m_total, "cells": cap_report, "tv_final": round(tv, 4),
                            "existing_questions_displaced": dropped_old, "new_r2_capped_out": capped_new,
                            "r2_b012_no_correct_sample(excluded)": r2_b012_no_sample, "r2_b011_no_teacher(excluded)": r2_b011_no_teacher},
               "self_stats": dict(stats),
               "inputs": {"rc6_train": sha(RC6 / "full/sft_train.jsonl"), "corpus_v5": sha(INV / "pilot_006_prep/approved/approved_train_v5.jsonl"),
                          "teacher_filter9": sha(FILTER), "teachr_traces": sha(TRACES), "jb012_judgement_v5": sha(JUDGE12), "jb011_raw": sha(RAW11), "jb012_raw": sha(RAW12)},
               "checks": {"over_maxlen": over, "teacher_question_mismatch": question_mismatch, "orders": orders,
                          "all_orders_max_run_ok": all(v["max_run_ok"] for v in orders.values())}}
    (OUT / "build_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("records", "questions", "composition", "refusal_by_gap")}, ensure_ascii=False, indent=1))
    print(json.dumps({"tv": summary["type_cap"]["tv_final"], "displaced": dropped_old, "new_capped_out": capped_new,
                      "excluded_r2": {"b012_no_sample": r2_b012_no_sample, "b011_no_teacher": r2_b011_no_teacher},
                      "checks": {"over": len(over), "mismatch": question_mismatch, "orders_ok": summary["checks"]["all_orders_max_run_ok"],
                                 "max_runs": {k: v["run_stats"] for k, v in orders.items()}}}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
