# -*- coding: utf-8 -*-
"""RC5 빌드(pilot_007 A3 S1, 결정 187). RC5 = 승인 corpus v3 + c2 teacher trace + 두 arm 8b 자체 정답 표본(S-focus 포함) + batch010 승인분. 모델 호출 없음.
``build7rc4.py``의 사본에서 바탕과 유형 상한만 바꿨다.

    hfvenv/bin/python sft_dpo_inventory/pilot_007/build/build7rc5.py   # -> build/RC5/{full,partial}/…, build/RC5/order_o<seed>.json, build/RC5/build_summary.json

- 바탕: RC3(정리 전, 386질문)의 레코드. teacher 레코드는 c2 편집본(``teacher/c2_records_<arm>.jsonl``, 결정 185)으로 바꾸고 c2에서 빠진 trace(내용 손실 18–19)는 뺀다.
  8b 레코드는 RC3 그대로(RC3 질문마다 상한 4로 이미 고름).
- 새 8b 레코드(RC4와 같음): J-b010(batch010 50문항)·S-focus, 승인 gold v3 판정(``judge7.py``), build6rc 8b 형식·계약·metadata, 길이 ≤ 12,288, 질문당 8b 상한 4
  (batch010은 ``random.Random(20261016)``, S-focus는 RC3 8b 수를 뺀 남은 자리).
- **유형 상한(결정 187)**: build6rc와 같은 예외(결정 92: batch006 실차 대조 변형 + batch007)·같은 계산(``caps_for``, τ 0.09)을 RC3 + batch010 전체 위에서 한다.
  칸마다 batch010 질문을 먼저 고르고(칸별 섞기 순서), 남은 자리를 기존 질문으로 같은 규칙(``apply_caps``와 같은 칸별 섞기 순서)대로 채운다. batch010 때문에 밀려난 기존 질문은
  두 arm에서 뺀다. 칸별: 들어간 batch010 수, 밀려난 기존 질문 수·id, 최종 분포의 TV(개발 분포 대비 Σ max(0, dev − share)).
- 두 arm 모두 레코드가 있는 질문만(질문 목록 같음), 평가 셋 강한 겹침 검사는 새 질문에 build6rc와 같은 규칙. 순서 공유(결정 168) 순서 파일 43·20261016·7.
"""
import hashlib
import json
import random
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
INV = ROOT / "sft_dpo_inventory"
for p in (ROOT, INV / "pilot_004_prep", INV / "pilot_prep_004/type_target", INV / "pilot_006/teacher", INV / "pilot_006_prep/aug300",
          INV / "thinking_prep_001", INV / "pilot_006_prep/self_samples", HERE.parent / "train"):
    sys.path.insert(0, str(p))
RC3, OUT = ROOT / "sft_dpo_inventory/pilot_006/build/RC3", HERE / "RC5"
C2 = HERE.parent / "teacher"
GEN = ROOT / "training/generated/pilot_007/self"
SELF7 = INV / "pilot_007/self"
SOURCES = {arm: [("Jb010", GEN / f"raw/Jb010_{arm}_raw.jsonl", SELF7 / f"Jb010_{arm}_judgement_v3.json"),
                 ("SF", GEN / f"raw/SF_{arm}_raw.jsonl", SELF7 / f"SF_{arm}_judgement_v3.json")] for arm in ("full", "partial")}
SELF_CAP, MAXLEN, SEED = 4, 12288, 20261016
ORDER_SEEDS = (43, 20261016, 7)


def read_jsonl(p):
    return [json.loads(l) for l in Path(p).read_text(encoding="utf-8").splitlines() if l.strip()]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    import approved6 as AP
    AP.VERSION = "v3"
    AP.MANIFEST["v3"] = "manifest_v3.json"
    import check_aug300 as W6
    import evaluate_vendor100 as EV
    import hf_thinking as H
    import order7
    import type_caps as TC
    from grounding.completion import complete_grounding_payload
    from grounding.full_renderer import render_full
    from training.data import thinking as TH
    from training.data.split import question_key
    from training.data.validation import assess, target_ok
    from training.trainer_common import expected_system_prompt, render_prompt
    from transformers import AutoTokenizer
    from type_target import profile
    corpus = AP.load(version="v3")
    rc3c = {}
    c2drop = {}
    for arm in ("full", "partial"):
        c2 = {r["metadata"]["trace_id"]: r for r in read_jsonl(C2 / f"c2_records_{arm}.jsonl")}
        base, dropped = [], 0
        for r in read_jsonl(RC3 / arm / "sft_train.jsonl"):
            if r["metadata"]["loss_scope"] == "full_response":
                if r["metadata"]["trace_id"] not in c2:
                    dropped += 1
                    continue
                r = c2[r["metadata"]["trace_id"]]
            base.append(r)
        rc3c[arm], c2drop[arm] = base, dropped
    base_q_arm = {arm: {r["metadata"]["source_record_id"] for r in rc3c[arm]} for arm in rc3c}
    old_q = sorted(base_q_arm["full"] & base_q_arm["partial"])
    new_q = sorted(c for c in corpus if corpus[c]["corpus_group"] == "batch010")
    t2pc_meta = {r["metadata"]["source_record_id"]: r["metadata"] for r in read_jsonl(ROOT / "training/generated/reviewed_gold_v006_t2pc/sft_train.jsonl")}

    def meta_of(cid):
        rec = corpus[cid]
        if rec["corpus_group"] != "trunk":
            return {}
        base = t2pc_meta.get(rec["provenance"]["source_record_id"], {})
        return {k: base[k] for k in ("target_kind", "expected_stop") if base.get(k) is not None}

    def cid_of(raw_id):
        return f"b010:{raw_id}" if raw_id.startswith("b010-") else AP.corpus_id(raw_id)
    tok = AutoTokenizer.from_pretrained(H.MODEL, revision=H.REVISION)
    cfg = {"chat_template_kwargs": {"enable_thinking": True}}

    def length(rec):
        return len(tok(render_prompt(tok, rec["messages"][:2], cfg), add_special_tokens=False)["input_ids"]) + len(tok(rec["messages"][2]["content"], add_special_tokens=False)["input_ids"]) + 1
    selfrec, stats = {"full": defaultdict(list), "partial": defaultdict(list)}, Counter()
    for arm, sources in SOURCES.items():
        system = expected_system_prompt(arm)
        for name, raw, judge in sources:
            ok = {t for q in json.loads(judge.read_text(encoding="utf-8"))["per_question"] if q["status"] == "approved" for t in q["correct_trace_ids"]}
            for r in read_jsonl(raw):
                if r["trace_id"] not in ok:
                    continue
                cid = cid_of(r["id"])
                if cid not in corpus:
                    stats[f"{arm}:{name}:not_in_corpus"] += 1
                    continue
                try:
                    tgt = TH.response_json(r["raw_text"])
                    tgt = complete_grounding_payload(tgt) if arm == "partial" else tgt
                    good = target_ok(assess(tgt, corpus[cid]["question"]), meta_of(cid))
                except Exception:  # noqa: BLE001
                    good = False
                if not good:
                    stats[f"{arm}:{name}:contract_dropped"] += 1
                    continue
                rec = {"messages": [{"role": "system", "content": system}, {"role": "user", "content": corpus[cid]["question"]},
                                    {"role": "assistant", "content": r["raw_text"]}],
                       "metadata": {"source_record_id": cid, "source": "hf", "loss_scope": "json_only", "grounding_target": arm,
                                    "trace_id": f"{name}:{r['trace_id']}", "trace_sha256": r["raw_sha256"], "format": "thinking",
                                    "origin": f"{name} vLLM BF16 base sample (approved-gold v3 correct)", "corpus_group": corpus[cid]["corpus_group"],
                                    "_rc": "RC5: A3 학습·B단계 후보"}}
                n = length(rec)
                rec["metadata"]["tokens"] = n
                if n > MAXLEN:
                    stats[f"{arm}:{name}:over_{MAXLEN}"] += 1
                    continue
                selfrec[arm][cid].append(rec)
                stats[f"{arm}:{name}:usable"] += 1
    rng = random.Random(SEED)
    add = {"full": {}, "partial": {}}
    for arm in ("full", "partial"):
        have = Counter(r["metadata"]["source_record_id"] for r in rc3c[arm] if r["metadata"]["loss_scope"] == "json_only")
        have_sha = {hashlib.sha256(r["messages"][2]["content"].encode()).hexdigest() for r in rc3c[arm]}
        for cid in sorted(selfrec[arm]):
            seen, uniq = set(have_sha), []
            for r in selfrec[arm][cid]:
                h = hashlib.sha256(r["messages"][2]["content"].encode()).hexdigest()
                if h not in seen:
                    seen.add(h)
                    uniq.append(r)
            room = SELF_CAP - have.get(cid, 0)
            if room > 0 and uniq:
                add[arm][cid] = sorted(rng.sample(uniq, min(room, len(uniq))), key=lambda r: r["metadata"]["trace_id"])
    reason = {}
    new_both = [c for c in new_q if add["full"].get(c) and add["partial"].get(c)]
    for c in new_q:
        if c not in new_both:
            reason[c] = "no_full_records" if not add["full"].get(c) else "no_partial_records"
    targets = W6.load_targets(None)
    prot = ("selection_v1", "selection_v2", "aux_test_v1", "valid98", "vendor100")
    hold = [(i["id"], i["question"], EV.derive_grounding(i["gold"])) for i in read_jsonl(INV / "pilot_006_prep/aug300/augmentation_300.jsonl") if i["status"] == "holdout"]
    sets = {n: targets[n] for n in prot}
    sets["augmentation_holdout_v1"] = hold
    views = {n: {json.dumps(EV._grounding_view(pl), ensure_ascii=False, sort_keys=True, default=str) for _, _, pl in rows if pl} for n, rows in sets.items()}
    qkeys = {n: {question_key(q) for _, q, _ in rows} for n, rows in sets.items()}
    grams = {n: [W6.grams(question_key(q)) for _, q, _ in rows] for n, rows in sets.items()}
    strong = {}
    for cid in new_both:
        q = corpus[cid]
        k, g = question_key(q["question"]), W6.grams(question_key(q["question"]))
        v = json.dumps(EV._grounding_view(render_full(q["semantics"])), ensure_ascii=False, sort_keys=True, default=str)
        hits = [f"{n}:question" for n in sets if k in qkeys[n]] + [f"{n}:jaccard" for n in sets if max((len(g & vg) / len(g | vg) for vg in grams[n]), default=0) >= 0.5]
        hits += [f"{n}:same_grounding" for n in sets if v in views[n]]
        hits = [h for h in hits if not h.startswith("vendor100:")]
        if hits:
            strong[cid] = hits
            reason[cid] = "eval_strong_overlap"
    kept_new = [c for c in new_both if c not in strong]
    allq = old_q + kept_new
    cell = {c: profile(render_full(corpus[c]["semantics"]))["cell"] for c in allq}
    b6 = json.loads((INV / "batch006/candidates_checked.json").read_text(encoding="utf-8"))["candidates"]
    exempt = frozenset(f"t2pc:{c['id']}" for c in b6 if c.get("variant")) | frozenset(c for c in allq if corpus[c]["corpus_group"] == "batch007")
    nonex = [c for c in allq if c not in exempt]
    m_total, caps = TC.caps_for(Counter(cell[c] for c in nonex), TC.DEVD, 0.09)
    by_cell = defaultdict(lambda: {"new": [], "old": []})
    for c in nonex:
        by_cell[cell[c]]["new" if c in set(kept_new) else "old"].append(c)
    keep, cap_report = set(c for c in allq if c in exempt), {}
    for cl, g in sorted(by_cell.items()):
        cap = caps.get(cl, 0)
        new_o, old_o = sorted(g["new"]), sorted(g["old"])
        random.Random(f"{TC.SEED}:{cl}:batch010").shuffle(new_o)
        random.Random(f"{TC.SEED}:{cl}").shuffle(old_o)
        take_new = new_o[:cap]
        take_old = old_o[:max(0, cap - len(take_new))]
        # batch010이 없었을 때 기존 질문이 차지했을 자리(같은 칸별 섞기 순서로 상한까지)
        old_alone = old_o[:cap]
        displaced = sorted(set(old_alone) - set(take_old))
        keep |= set(take_new) | set(take_old)
        cap_report[cl] = {"cap": cap, "batch010_available": len(new_o), "batch010_added": len(take_new), "existing_available": len(old_o),
                          "existing_kept": len(take_old), "existing_displaced_by_batch010": len(displaced), "displaced_ids": displaced,
                          "existing_over_cap_without_batch010": max(0, len(old_o) - cap)}
    final_new = sorted(c for c in kept_new if c in keep)
    for c in set(kept_new) - set(final_new):
        reason[c] = "type_cap"
    dropped_old = sorted(c for c in old_q if c not in keep)
    old_q = sorted(c for c in old_q if c in keep)
    fin = Counter(cell[c] for c in old_q + final_new if c not in exempt)
    tot = sum(fin.values())
    tv = sum(max(0.0, TC.DEVD.get(k, 0) - fin.get(k, 0) / tot) for k in set(TC.DEVD) | set(fin))
    over = {}
    final_q = sorted(old_q + final_new)
    OUT.mkdir(parents=True, exist_ok=True)
    built = {}
    for arm in ("full", "partial"):
        d = OUT / arm
        d.mkdir(exist_ok=True)
        rows = [r for r in rc3c[arm] if r["metadata"]["source_record_id"] in set(old_q)]
        for cid in sorted(add[arm]):
            if cid in old_q or cid in final_new:
                for r in add[arm][cid]:  # build6rc 쓰기 단계와 같은 metadata 보강
                    meta = {**r["metadata"], **meta_of(cid), "format": TH.FORMAT, "source_record_id": cid, "grounding_target": arm, "representation": "flat",
                            "corpus_group": corpus[cid]["corpus_group"], "_rc": "RC5: A3 학습·B단계 후보",
                            "k3_scope_name_family": bool(corpus[cid].get("k3_scope_name_family"))}
                    meta.setdefault("parent_intent", cid)
                    rows.append({"messages": r["messages"], "metadata": meta})
        with (d / "sft_train.jsonl").open("w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        (d / "sft_valid.jsonl").write_text("", encoding="utf-8")
        man = json.loads((RC3 / arm / "manifest.json").read_text(encoding="utf-8"))
        s = man["sft"]
        s.update(generated_at=datetime.now(timezone.utc).isoformat(), release_candidate="RC5",
                 note=f"pilot_007 RC5 = RC3({arm}, teacher c2 편집) + batch010 승인분(8b J-b010, 상한 칸에서 우선) + S-focus 정답 표본; build7rc5.py",
                 train_count=len(rows), validation_count=0, questions=len(final_q), question_list_sha256=hashlib.sha256("\n".join(final_q).encode()).hexdigest(),
                 by_source=dict(Counter(r["metadata"]["loss_scope"] for r in rows)),
                 output_hashes={"sft_train.jsonl": sha(d / "sft_train.jsonl"), "sft_valid.jsonl": sha(d / "sft_valid.jsonl")})
        (d / "manifest.json").write_text(json.dumps(man, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        built[arm] = {"records": len(rows), "added": len(rows) - len(rc3c[arm]), "by_source": s["by_source"], "sft_train_sha256": s["output_hashes"]["sft_train.jsonl"]}
    orders = {}
    qids = {arm: [r["metadata"]["source_record_id"] for r in read_jsonl(OUT / arm / "sft_train.jsonl")] for arm in ("full", "partial")}
    for sd in ORDER_SEEDS:
        o = order7.order_file(qids, sd)
        for arm in ("full", "partial"):
            assert order7.question_sequence(order7.order_records(read_jsonl(OUT / arm / "sft_train.jsonl"), sd)) == o["order"], (arm, sd)
        (OUT / f"order_o{sd}.json").write_text(json.dumps(o, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        orders[sd] = o["order_sha256"]
    sfq = {cid: {arm: len(add[arm].get(cid, [])) for arm in add} for cid in old_q if any(cid in add[a] for a in add)}
    summary = {"label": "RC5", "base": "RC3 + c2 teacher", "built": built, "questions": {"rc3c": len(old_q), "batch010_approved": len(new_q), "batch010_added": len(final_new),
                                                                            "total": len(final_q), "batch010_not_added": reason},
               "question_list_sha256": hashlib.sha256("\n".join(final_q).encode()).hexdigest(), "s_focus_added_records": sfq,
               "order_sha256": {str(k): v for k, v in orders.items()},
               "type_cap": {"tau": 0.09, "max_total_nonexempt": m_total, "cells": cap_report, "tv_final": round(tv, 4),
                            "existing_questions_dropped_by_cap": dropped_old},
               "c2_teacher_records_dropped": c2drop, "self_stats": dict(stats), "approved_corpus": "v3 (manifest_v3.json)",
               "teacher": "RC3 teacher의 c2 편집본(결정 185; batch010 teacher 없음)", "use": "A3 학습(Full)·B단계 후보"}
    (OUT / "build_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
