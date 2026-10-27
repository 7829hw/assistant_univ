# -*- coding: utf-8 -*-
"""pilot_010 선택 단계 변형 V4·V8 빌드(결정 250 AB4). Full arm만. 모델 호출 없음.
``pilot_009/build/build9rc7.py``(그대로)의 방식을 따른다. 바꾼 것만 적는다.

    hfvenv/bin/python sft_dpo_inventory/pilot_010/build/build10v.py --variant V4|V8
    # -> build/<V>/full/{sft_train,sft_valid}.jsonl·manifest.json, build/<V>/order_b2_o<seed>.json, build/<V>/build_summary.json

1. 바탕: RC7 Full 1,993레코드 중 거부 레코드(159)를 뺀 답하는 레코드 1,834(RC7 그대로; 결정 235 거르기는 RC7에 이미 반영).
2. 더하는 답하는 레코드(승인 corpus v6):
   a. batch013 승인 77(결정 247): J-b013 base 표본(greedy 1 + 8) 중 corpus v6 판정(``judge10.py`` → ``pilot_010/self/Jb013_full_judgement_v6.json``) 정답 표본,
      8b 자체 출처 ``json_only``, build9rc7의 batch012 r2와 같은 형식·계약(``target_ok``)·길이 ≤ 12,288, 질문당 상한 4(``random.Random(20261016)``).
   b. 근접 대조 teacher 레코드: TEACH-C(``teacher_contrast_v2``) 통과 trace(c2 정리 뒤 모든 검사·결정 235 절 이름 거르기 통과, 내용 손실 없음)를
      ``teacher_contrast10b.to_arm_records``(``<think>`` c2 뒤 생각 ``</think>`` + canonical Full JSON)로, ``full_response``(teacher 출처, 결정 86).
      대상 = ``teachc_targets.json`` 250(batch011 r2 40·batch012 r2 40·batch013 77·요금 지표 승인 93), **질문당 최대 2**(내용 중복 제거 뒤 ``Random(f"20261016:contrast:{id}")``).
3. 유형 상한 C-1(τ 0.09, 예외 batch006 변형·batch007, build9rc7와 같은 계산): "새 문항" = RC7 답하는 질문에 없던 질문(batch013, 그리고 RC7에 들지 못했던
   근접 대조·요금 지표 대상 질문 — 이번에 teacher 레코드가 생김). 칸마다 새 문항을 먼저(``Random(f"{SEED}:{cell}:v10new")``), 남은 자리를 RC7 질문(``Random(f"{SEED}:{cell}")``,
   build9rc7와 같은 순서)으로. 밀려난 RC7 질문은 레코드째(더한 teacher 레코드 포함) 뺀다. 상한에서 잘린 새 문항도 뺀다.
4. 거부 레코드(r1, 상한 예외): R = round(ρ · N / (1 − ρ)), ρ = 0.04(V4)·0.08(V8), N = 답하는 레코드. 대상 질문 batch011 r1 60 + batch012 r1 승인 60(build9rc7와 같음).
   S-1(base 모델 순수 거부 표본, ``json_only``) 먼저(질문당 최대 4, 내용 중복 제거, 질문을 고친 b011-015·b012-001·021·039 제외), 넘치면 가장 많은 질문부터 줄임.
   모자라면 teacher 거부 trace(``pilot_009/build/teacher_filter9.json``의 쓸 trace, ``full_response``)로 질문별 합이 고르게(합이 가장 적은 질문부터; **같은 합이면
   ``Random(f"{SEED}:refusal_tie:{V}")``로 섞은 질문 순서** — build9rc7는 id 순이었으나 R < 질문 수인 V4에서 id 순이면 뒤쪽 batch012 질문만 빠지므로 바꿈), 질문당 합 최대 4.
5. 검사: 길이 ≤ 12,288, teacher 레코드 질문 문장 = 대상 질문(corpus v6), 질문 목록 sha256, O4' 순서 파일 3개(43·20261016·7)와 연속 길이(최대 ≤ 4).
   손실 token·마스크는 ``mask_audit10.py``.
"""
import argparse
import hashlib
import json
import random
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
P10 = HERE.parent
INV = P10.parent
ROOT = INV.parent
for p in (ROOT, INV / "pilot_004_prep", INV / "pilot_prep_004/type_target", INV / "pilot_006_prep/aug300", INV / "thinking_prep_001",
          INV / "pilot_006_prep/self_samples", INV / "pilot_007/train", INV / "pilot_006/teacher", INV / "pilot_009/teacher", P10 / "teacher", HERE):
    sys.path.insert(0, str(p))
RC7 = INV / "pilot_009/build/RC7"
RAW11 = ROOT / "training/generated/pilot_008/self/raw/Jb011_full_raw.jsonl"
RAW12 = ROOT / "training/generated/pilot_009/self/raw/Jb012_full_raw.jsonl"
RAW13 = ROOT / "training/generated/pilot_010/self/raw/Jb013_full_raw.jsonl"
JUDGE13 = P10 / "self/Jb013_full_judgement_v6.json"
FILTER9 = INV / "pilot_009/build/teacher_filter9.json"
TRACES_R = ROOT / "training/generated/pilot_009/teacher_teachr/traces.jsonl"
TRACES_C = ROOT / "training/generated/pilot_010/teacher_teachc/traces.jsonl"
TARGETS_C = P10 / "teacher/teachc_targets.json"
SELF_CAP, REF_CAP, CON_CAP, MAXLEN, SEED = 4, 4, 2, 12288, 20261016
SHARES = {"V4": 0.04, "V8": 0.08}
ORDER_SEEDS = (43, 20261016, 7)
MODIFIED = frozenset({"b011:b011-015", "b012:b012-001", "b012:b012-021", "b012:b012-039"})


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
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", required=True, choices=sorted(SHARES))
    ap.add_argument("--contrast-traces", default=str(TRACES_C), help="시험용(기본 = TEACH-C 원문)")
    ap.add_argument("--out-root", default=str(HERE), help="시험용(기본 = build/)")
    a = ap.parse_args()
    V, SHARE = a.variant, SHARES[a.variant]
    traces_c = Path(a.contrast_traces)
    OUT = Path(a.out_root) / V
    RC = f"{V}: pilot_010 선택 단계 변형"
    import approved6 as AP
    AP.VERSION = "v6"
    AP.MANIFEST["v6"] = "manifest_v6.json"
    import hf_thinking as H
    import order7b
    import teacher_contrast10b as TC10
    C2 = TC10.C2
    import teacher_refusal9 as TR
    import type_caps as TC
    from grounding.full_renderer import render_full
    from training.data import thinking as TH
    from training.data.validation import assess, target_ok
    from training.trainer_common import expected_system_prompt, render_prompt
    from transformers import AutoTokenizer
    from type_target import profile
    corpus = AP.load(version="v6")
    tok = AutoTokenizer.from_pretrained(H.MODEL, revision=H.REVISION)
    cfg = {"chat_template_kwargs": {"enable_thinking": True}}
    system = expected_system_prompt("full")
    plen = {}

    def length(rec):
        q = rec["messages"][1]["content"]
        if q not in plen:
            plen[q] = len(tok(render_prompt(tok, rec["messages"][:2], cfg), add_special_tokens=False)["input_ids"])
        return plen[q] + len(tok(rec["messages"][2]["content"], add_special_tokens=False)["input_ids"]) + 1

    rc7 = read_jsonl(RC7 / "full/sft_train.jsonl")
    base = [r for r in rc7 if not r["metadata"].get("refusal_source")]
    old_q = sorted({r["metadata"]["source_record_id"] for r in base})
    old_set = set(old_q)
    grp = lambda g: {c: corpus[c] for c in corpus if corpus[c]["corpus_group"] == g}  # noqa: E731
    kind = lambda c: corpus[c]["provenance"]["kind"]  # noqa: E731
    b011, b012, b013 = grp("batch011"), grp("batch012"), grp("batch013")
    r1q = sorted(c for c in b011 if kind(c) == "r1_refusal") + sorted(c for c in b012 if kind(c) == "r1_refusal")
    stats = Counter()
    add_self, add_con = defaultdict(list), defaultdict(list)
    # 2a. batch013 8b 레코드
    judged = json.loads(JUDGE13.read_text(encoding="utf-8"))
    ok_traces = {t for q in judged["per_question"] if q["status"] == "approved" for t in q["correct_trace_ids"]}
    cand = defaultdict(list)
    for r in read_jsonl(RAW13):
        cid = f"b013:{r['id']}"
        if cid not in b013 or r["trace_id"] not in ok_traces:
            continue
        try:
            good = target_ok(assess(TH.response_json(r["raw_text"]), corpus[cid]["question"]), {})
        except Exception:  # noqa: BLE001
            good = False
        if not good:
            stats["b013_self:contract_dropped"] += 1
            continue
        rec = {"messages": [{"role": "system", "content": system}, {"role": "user", "content": corpus[cid]["question"]}, {"role": "assistant", "content": r["raw_text"]}],
               "metadata": {"source_record_id": cid, "source": "hf", "loss_scope": "json_only", "grounding_target": "full", "trace_id": f"Jb013:{r['trace_id']}",
                            "trace_sha256": r["raw_sha256"], "format": TH.FORMAT, "origin": "Jb013 vLLM BF16 base sample (approved-gold v6 correct)",
                            "representation": "flat", "corpus_group": "batch013", "_rc": RC, "k3_scope_name_family": False, "parent_intent": cid}}
        n = length(rec)
        rec["metadata"]["tokens"] = n
        if n > MAXLEN:
            stats["b013_self:over_len"] += 1
            continue
        cand[cid].append(rec)
        stats["b013_self:usable"] += 1
    rng = random.Random(SEED)
    for cid in sorted(cand):
        uniq = dedup(cand[cid])
        add_self[cid] = sorted(rng.sample(uniq, min(SELF_CAP, len(uniq))), key=lambda r: r["metadata"]["trace_id"])
    b013_no_sample = sorted(c for c in b013 if c not in add_self)
    # 2b. 근접 대조 teacher 레코드
    targets = {t["id"]: t for t in json.loads(TARGETS_C.read_text(encoding="utf-8"))}
    question_mismatch = [c for c, t in targets.items() if t["question"] != corpus[c]["question"] or t["semantics"] != corpus[c]["semantics"]]
    pass_rows = defaultdict(list)
    for t in read_jsonl(traces_c):
        if t["pass"]:
            pass_rows[t["id"]].append(t)
    for cid in sorted(targets):
        recs = []
        for t in pass_rows.get(cid, []):
            edited, removed, lost = C2.edit_thinking(t["thinking"] or "")
            if lost or C2.sha(edited) != t["c2"]["thinking_sha256_after"]:
                stats["contrast:c2_mismatch"] += 1
                continue
            tr = {"trace_id": t["trace_id"], "thinking": edited, "model": t["model"], "model_digest": t["model_digest"]}
            r = TC10.to_arm_records(tr, corpus[cid]["semantics"], corpus[cid]["question"], cid)["full"]
            if r["messages"][0]["content"] != system:
                raise SystemExit(f"system prompt mismatch {cid}")
            r["metadata"].update(origin="TEACH-C teacher_contrast_v2 (qwen3.8:27b, checks passed, c2·결정 235 거르기)", format=TH.FORMAT, representation="flat",
                                 corpus_group=corpus[cid]["corpus_group"], contrast_source="teacher", contrast_set=targets[cid]["set"], _rc=RC,
                                 k3_scope_name_family=False, parent_intent=cid, c2_removed_lines=len(removed), thinking_sha256_raw=t["thinking_sha256"])
            n = length(r)
            r["metadata"]["tokens"] = n
            if n > MAXLEN:
                stats["contrast:over_len"] += 1
                continue
            recs.append(r)
        uniq = dedup(recs)
        if uniq:
            add_con[cid] = sorted(random.Random(f"{SEED}:contrast:{cid}").sample(uniq, min(CON_CAP, len(uniq))), key=lambda r: r["metadata"]["trace_id"])
    contrast_no_trace = sorted(c for c in targets if c not in add_con)
    # 3. 유형 상한 C-1
    new_q = sorted((set(add_self) | set(add_con)) - old_set)
    allq = old_q + new_q
    cell = {c: profile(render_full(corpus[c]["semantics"]))["cell"] for c in allq}
    b6 = json.loads((INV / "batch006/candidates_checked.json").read_text(encoding="utf-8"))["candidates"]
    exempt = frozenset(f"t2pc:{c['id']}" for c in b6 if c.get("variant")) | frozenset(c for c in allq if corpus[c]["corpus_group"] == "batch007")
    nonex = [c for c in allq if c not in exempt]
    m_total, caps = TC.caps_for(Counter(cell[c] for c in nonex), TC.DEVD, 0.09)
    by_cell = defaultdict(lambda: {"new": [], "old": []})
    new_set = set(new_q)
    for c in nonex:
        by_cell[cell[c]]["new" if c in new_set else "old"].append(c)
    keep, cap_report = set(c for c in allq if c in exempt), {}
    for cl, g in sorted(by_cell.items()):
        cap = caps.get(cl, 0)
        new_o, old_o = sorted(g["new"]), sorted(g["old"])
        random.Random(f"{TC.SEED}:{cl}:v10new").shuffle(new_o)
        random.Random(f"{TC.SEED}:{cl}").shuffle(old_o)
        take_new = new_o[:cap]
        take_old = old_o[:max(0, cap - len(take_new))]
        displaced = sorted(set(old_o) - set(take_old))
        keep |= set(take_new) | set(take_old)
        cap_report[cl] = {"cap": cap, "new_available": len(new_o), "new_added": len(take_new), "existing_available": len(old_o),
                          "existing_kept": len(take_old), "existing_not_kept": len(displaced), "displaced_ids": displaced,
                          "new_capped_out": sorted(set(new_o) - set(take_new))}
    displaced_old = sorted(c for c in old_q if c not in keep)
    capped_new = sorted(c for c in new_q if c not in keep)
    rows = [r for r in base if r["metadata"]["source_record_id"] in keep]
    for cid in sorted(keep):
        rows += add_self.get(cid, [])
        rows += add_con.get(cid, [])
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
    while sum(len(v) for v in refusal.values()) > R:
        top = max(refusal, key=lambda c: (len(refusal[c]), c))
        refusal[top].pop()
    filt = json.loads(FILTER9.read_text(encoding="utf-8"))
    traces_r = {t["trace_id"]: t for t in read_jsonl(TRACES_R)}
    pools = {}
    for c in r1q:
        if c in MODIFIED and c.startswith("b012"):
            pools[c] = []
            continue
        lst = list(filt["usable"].get(c, []))
        random.Random(f"{SEED}:teacher:{c}").shuffle(lst)
        pools[c] = lst
    tie = list(r1q)
    random.Random(f"{SEED}:refusal_tie:{V}").shuffle(tie)
    tie_rank = {c: i for i, c in enumerate(tie)}
    t_count = Counter()
    tgr = {t["id"]: t for t in json.loads((INV / "pilot_009/teacher/teachr_targets.json").read_text(encoding="utf-8"))}
    while sum(len(refusal[c]) for c in r1q) < R:
        open_q = [c for c in r1q if len(refusal[c]) < REF_CAP and t_count[c] < len(pools[c])]
        if not open_q:
            break
        c = min(open_q, key=lambda x: (len(refusal[x]), tie_rank[x]))
        u = pools[c][t_count[c]]
        t = traces_r[u["trace_id"]]
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
        if tgr[c]["question"] != corpus[c]["question"]:
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
    man = json.loads((RC7 / "full/manifest.json").read_text(encoding="utf-8"))
    s = man["sft"]
    s.update(generated_at=datetime.now(timezone.utc).isoformat(), release_candidate=V,
             note=f"pilot_010 {V} = RC7 답하는 레코드 + batch013 승인분(8b json_only) + 근접 대조 teacher(TEACH-C v2, 질문당 2, full_response) + r1 거부 {round(SHARE * 100)}%(S-1 + teacher 거부 trace); build10v.py",
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
    con_rows = [r for r in rows if r["metadata"].get("contrast_source") == "teacher"]
    kept_targets = [c for c in targets if c in keep]
    summary = {"label": V, "built": datetime.now(timezone.utc).isoformat(), "base": "RC7 full (거부 레코드 159 뺌)", "approved_corpus": "v6 (manifest_v6.json)",
               "refusal_share_target": SHARE, "records": len(rows), "questions": len(final_q), "question_list_sha256": s["question_list_sha256"],
               "composition": {"rc7_answered_base": len(base), "rc7_kept_records": len([r for r in base if r["metadata"]["source_record_id"] in keep]),
                               "rc7_dropped_records": len([r for r in base if r["metadata"]["source_record_id"] not in keep]),
                               "b013_self_records": sum(len(add_self[c]) for c in add_self if c in keep), "b013_self_questions": sum(1 for c in add_self if c in keep),
                               "contrast_teacher_records": len(con_rows), "contrast_teacher_questions": len({r["metadata"]["source_record_id"] for r in con_rows}),
                               "contrast_teacher_by_set": dict(Counter(r["metadata"]["contrast_set"] for r in con_rows)),
                               "contrast_per_question": dict(sorted(Counter(len(add_con.get(c, [])) for c in kept_targets).items())),
                               "answered_records_N": n_nonref, "refusal_records": len(ref_rows),
                               "refusal_s1": sum(1 for r in ref_rows if r["metadata"]["refusal_source"] == "S-1"),
                               "refusal_teacher": sum(1 for r in ref_rows if r["metadata"]["refusal_source"] == "teacher"),
                               "refusal_questions": sum(1 for c in r1q if refusal[c]), "refusal_share": round(len(ref_rows) / len(rows), 4),
                               "refusal_target_R": R, "refusal_filled": len(ref_rows) >= R,
                               "refusal_per_question": dict(sorted(Counter(len(refusal[c]) for c in r1q).items())),
                               "teacher_records_total(full_response)": sum(1 for r in rows if r["metadata"]["loss_scope"] == "full_response")},
               "refusal_by_gap": {g: {"questions": sum(1 for c in r1q if corpus[c]["provenance"]["gap"] == g),
                                      "records": sum(len(refusal[c]) for c in r1q if corpus[c]["provenance"]["gap"] == g)}
                                  for g in sorted({corpus[c]["provenance"]["gap"] for c in r1q})},
               "by_loss_scope": dict(Counter(r["metadata"]["loss_scope"] for r in rows)),
               "type_cap": {"tau": 0.09, "max_total_nonexempt": m_total, "cells": cap_report, "tv_final": round(tv, 4), "new_questions": len(new_q),
                            "new_kept": len(new_q) - len(capped_new), "existing_questions_displaced": displaced_old, "new_capped_out": capped_new},
               "excluded": {"b013_no_correct_sample(8b 없음)": b013_no_sample, "contrast_targets_without_pass_trace": contrast_no_trace},
               "self_stats": dict(stats),
               "inputs": {"rc7_train": sha(RC7 / "full/sft_train.jsonl"), "corpus_v6": sha(INV / "pilot_006_prep/approved/approved_train_v6.jsonl"),
                          "teacher_filter9": sha(FILTER9), "teachr_traces": sha(TRACES_R), "teachc_traces": sha(traces_c), "teachc_targets": sha(TARGETS_C),
                          "jb013_judgement_v6": sha(JUDGE13), "jb011_raw": sha(RAW11), "jb012_raw": sha(RAW12), "jb013_raw": sha(RAW13)},
               "checks": {"over_maxlen": over, "teacher_question_mismatch": sorted(set(question_mismatch)), "orders": orders,
                          "all_orders_max_run_ok": all(v["max_run_ok"] for v in orders.values())}}
    (OUT / "build_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("records", "questions", "composition")}, ensure_ascii=False, indent=1))
    print(json.dumps({"tv": summary["type_cap"]["tv_final"], "displaced": len(displaced_old), "new": len(new_q), "new_capped_out": len(capped_new),
                      "excluded": {k: len(v) for k, v in summary["excluded"].items()},
                      "checks": {"over": len(over), "mismatch": summary["checks"]["teacher_question_mismatch"], "orders_ok": summary["checks"]["all_orders_max_run_ok"],
                                 "max_runs": {k: v["run_stats"] for k, v in orders.items()}}}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
