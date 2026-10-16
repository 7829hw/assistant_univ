# -*- coding: utf-8 -*-
"""pilot_006 학습 직전 빌드(RC, 세션 2b H8). ``build6.py``(세션 2 시험 빌드)를 바꾸지 않고 새로 쓴 파일. 모델 호출 없음. **학습 전 후보, PLAN 고정 전.**

    hfvenv/bin/python sft_dpo_inventory/pilot_006/build/build6rc.py --out sft_dpo_inventory/pilot_006/build/RC1

재료(세션 2b 지시 H8):
- 질문: 승인 corpus(R0, ``pilot_006_prep/approved/approved_train_v1.jsonl``): trunk 131, pg 154, aug300 train 승인, batch007 27, batch008 10.
  같은 정규화 질문(pg v005 ``pg:ann-…`` = trunk ``t2pc:ann-…``)은 하나로 합치고 trunk id를 쓴다. batch009는 승인 전이라 넣지 않는다.
- teacher(``full_response``): TEACH(결정 132 G2, 지시 v2) trace 가운데 자동 검사 (a)(b) 모두 통과한 것만. thinking + canonical 답 JSON(Full = ``render_full``,
  Partial = ``render_partial``)으로 두 arm 레코드(``teacher6v2.to_arm_records``). 질문당 최대 4개(결정 48). pilot_004·pg reasoning의 이전 teacher는 쓰지 않는다(G2).
- 8b 자체(``json_only``): arm 자신의 prompt로 모은 vLLM 표본 가운데 승인 gold 판정(``judge6.py``, 조건 계층 전 원응답)으로 정답이고 학습 계약(``target_ok``)도
  통과한 것. Full = J1·J9·S32F-a·S32F-b·J10(full), Partial = J6·J8·S32P-a·S32P-b·J10(partial). 원문 그대로, 같은 원문은 하나로, 질문당 최대 4개.
  pilot_004 판 8b 자체(pilot_003 HF trace)는 쓰지 않는다(G3). 질문이 바뀐 문항의 이전 문구 출력은 판정에서 이미 빠진다(``invalid_old_question``).
규칙:
- 길이(결정 125 규칙 3·4): 레코드 길이(학습 렌더링 입력 + 응답 + 1) > ``--max-seq-length``(12,288)이면 상한 선택 전에 뺀다.
- 두 arm 질문 목록: 두 arm 모두 레코드가 하나 이상인 질문만. 질문 목록 sha256 같음.
- 평가 셋 강한 겹침(정규화 질문·Jaccard ≥ 0.5·같은 grounding): selection_v1·selection_v2·aux_test_v1·valid98·augmentation_holdout_v1과 겹치면 뺀다.
  업체 100은 결정 106으로 개발 셋이 되었고 `보류_vendor100` 58문항을 train으로 되돌렸으므로 빼지 않고 ``vendor100_overlap``으로 보고만 한다
  (build6 시험 빌드는 업체 100도 뺐다 — 세션 2b에서 바꾼 점).
- 유형 상한(결정 88·92, τ 0.09, 질문 단위 ``type_caps.capped``). 결정 92 예외 = trunk batch006 실차 대조 변형 + batch007(PLAN_DRAFT 1절).
- 원문·판정 파일이 아직 없는 출처(진행 중 작업)는 건너뛰고 ``missing_sources``에 적는다(RC1이 부분 빌드인지 표시).
출력: ``<out>/{full,partial}/sft_train.jsonl·sft_valid.jsonl(빈 파일)·manifest.json``, ``<out>/build_summary.json``, ``<out>/lengths.json``,
``<out>/questions.json``(질문별 출처·레코드 수·빠진 이유).
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
ROOT = HERE.parents[2]
INV = ROOT / "sft_dpo_inventory"
GEN = ROOT / "training/generated/pilot_006"
R1 = INV / "pilot_006_prep/self_samples/r1"
for p in (ROOT, INV / "pilot_004_prep", INV / "pilot_prep_004/type_target", INV / "pilot_006/teacher", INV / "pilot_006_prep/aug300",
          INV / "thinking_prep_001", INV / "pilot_006_prep/self_samples"):
    sys.path.insert(0, str(p))
SEED, TEACHER_CAP, SELF_CAP = 20261016, 4, 4
SELF = {"full": [("J1", GEN / "self_full/raw/self_full_raw.jsonl", R1 / "j1_approved.json"),
                 ("J9", GEN / "self_2b/raw/J9_raw.jsonl", R1 / "j9_approved.json"),
                 ("S32F-a", GEN / "self_2b/raw/S32F-a_raw.jsonl", R1 / "s32f_a_approved.json"),
                 ("S32F-b", GEN / "self_2b/raw/S32F-b_raw.jsonl", R1 / "s32f_b_approved.json"),
                 ("J10", GEN / "self_2b/raw/J10_full_raw.jsonl", R1 / "j10_full_approved.json")],
        "partial": [("J6", GEN / "self_partial/raw/self_partial_raw.jsonl", R1 / "j6_approved.json"),
                    ("J8", GEN / "self_2b/raw/J8_raw.jsonl", R1 / "j8_approved.json"),
                    ("S32P-a", GEN / "self_2b/raw/S32P-a_raw.jsonl", R1 / "s32p_a_approved.json"),
                    ("S32P-b", GEN / "self_2b/raw/S32P-b_raw.jsonl", R1 / "s32p_b_approved.json"),
                    ("J10", GEN / "self_2b/raw/J10_partial_raw.jsonl", R1 / "j10_partial_approved.json")]}
TEACH = GEN / "teacher_v2/traces.jsonl"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_jsonl(p):
    return [json.loads(l) for l in Path(p).read_text(encoding="utf-8").splitlines() if l.strip()]


def main():
    import approved6 as AP
    import check_aug300 as W6
    import evaluate_vendor100 as EV
    import hf_thinking as H
    import teacher6v2 as T2
    import type_caps as TC
    from grounding.completion import complete_grounding_payload
    from grounding.full_renderer import render_full
    from training.data import thinking as TH
    from training.data.split import question_key
    from training.data.thinking import FORMAT
    from training.data.validation import assess, target_ok
    from training.trainer_common import expected_system_prompt, render_prompt
    from transformers import AutoTokenizer
    from type_target import profile
    p = argparse.ArgumentParser()
    p.add_argument("--out", required=True)
    p.add_argument("--max-seq-length", type=int, default=12288)
    p.add_argument("--label", default="RC1")
    a = p.parse_args()
    out = Path(a.out)
    rng = random.Random(SEED)
    corpus = AP.load()
    # ---- 질문(정규화 질문으로 합침, trunk 우선)
    order = {"trunk": 0, "pg": 1, "aug300": 2, "batch007": 3, "batch008": 4, "batch009": 5}
    questions, alias, by_key = {}, {}, {}
    for cid, rec in sorted(corpus.items(), key=lambda kv: (order[kv[1]["corpus_group"]], kv[0])):
        k = question_key(rec["question"])
        if k in by_key:
            alias[cid] = by_key[k]
            continue
        by_key[k] = cid
        questions[cid] = rec
    t2pc_meta = {r["metadata"]["source_record_id"]: r["metadata"] for r in read_jsonl(ROOT / "training/generated/reviewed_gold_v006_t2pc/sft_train.jsonl")}

    def meta_of(cid):
        rec = questions[cid]
        if rec["corpus_group"] != "trunk":
            return {}
        base = t2pc_meta.get(rec["provenance"]["source_record_id"], {})
        return {k: base[k] for k in ("target_kind", "expected_stop", "parent_intent", "family") if base.get(k) is not None}

    def canon(cid):
        return alias.get(cid, cid)
    missing = []
    # ---- teacher
    teacher = {"full": defaultdict(list), "partial": defaultdict(list)}
    teach_stats = Counter()
    if TEACH.exists():
        for t in read_jsonl(TEACH):
            teach_stats["traces"] += 1
            cid = canon(t["id"])
            if cid not in questions:
                teach_stats["not_in_corpus"] += 1
                continue
            if not t.get("pass"):
                teach_stats["check_failed"] += 1
                continue
            teach_stats["pass"] += 1
            for arm, r in T2.to_arm_records({"trace_id": t["trace_id"], "thinking": t["thinking"], "model": t["model"], "model_digest": t["model_digest"]},
                                            questions[cid]["semantics"], questions[cid]["question"], cid).items():
                r["metadata"]["origin"] = "TEACH teacher v2 (qwen3.8:27b, checks a+b passed)"
                teacher[arm][cid].append(r)
    else:
        missing.append(str(TEACH.relative_to(ROOT)))
    # ---- 8b 자체
    selfrec = {"full": defaultdict(list), "partial": defaultdict(list)}
    self_stats = Counter()
    for arm, sources in SELF.items():
        system = expected_system_prompt(arm)
        for name, raw, judge in sources:
            if not raw.exists() or not judge.exists():
                missing.append(f"{arm}:{name}")
                continue
            ok = {t for q in json.loads(judge.read_text(encoding="utf-8"))["per_question"] if q["status"] == "approved" for t in q["correct_trace_ids"]}
            for r in read_jsonl(raw):
                if r["trace_id"] not in ok:
                    continue
                cid = canon(AP.corpus_id(r["id"]))
                if cid not in questions:
                    continue
                try:
                    tgt = TH.response_json(r["raw_text"])
                    tgt = complete_grounding_payload(tgt) if arm == "partial" else tgt
                    good = target_ok(assess(tgt, questions[cid]["question"]), {k: v for k, v in meta_of(cid).items() if k in ("target_kind", "expected_stop")})
                except Exception:  # noqa: BLE001
                    good = False
                if not good:
                    self_stats[f"{arm}:contract_dropped"] += 1
                    continue
                self_stats[f"{arm}:{name}"] += 1
                selfrec[arm][cid].append({"messages": [{"role": "system", "content": system}, {"role": "user", "content": questions[cid]["question"]},
                                                       {"role": "assistant", "content": r["raw_text"]}],
                                          "metadata": {"source_record_id": cid, "source": "hf", "loss_scope": "json_only", "grounding_target": arm,
                                                       "trace_id": f"{name}:{r['trace_id']}", "trace_sha256": r["raw_sha256"], "format": "thinking",
                                                       "origin": f"{name} vLLM BF16 base sample (approved-gold correct)"}})
    # ---- 길이
    tok = AutoTokenizer.from_pretrained(H.MODEL, revision=H.REVISION)
    cfg = {"chat_template_kwargs": {"enable_thinking": True}}
    plen = {}

    def length(rec):
        key = (hashlib.sha256(rec["messages"][0]["content"].encode()).hexdigest(), rec["messages"][1]["content"])
        if key not in plen:
            plen[key] = len(tok(render_prompt(tok, rec["messages"][:2], cfg), add_special_tokens=False)["input_ids"])
        return plen[key] + len(tok(rec["messages"][2]["content"], add_special_tokens=False)["input_ids"]) + 1
    lens, over = defaultdict(list), []
    for arm in ("full", "partial"):
        for kind, pool in (("teacher", teacher[arm]), ("self", selfrec[arm])):
            for cid in list(pool):
                keep = []
                for r in pool[cid]:
                    n = length(r)
                    r["metadata"]["tokens"] = n
                    lens[f"{arm}:{kind}"].append(n)
                    if n > a.max_seq_length:
                        over.append({"arm": arm, "kind": kind, "id": cid, "trace_id": r["metadata"]["trace_id"], "tokens": n})
                    else:
                        keep.append(r)
                pool[cid] = keep

    # ---- 상한 선택
    def pick(recs, cap):
        seen, uniq = set(), []
        for r in recs:
            h = hashlib.sha256(r["messages"][2]["content"].encode()).hexdigest()
            if h not in seen:
                seen.add(h)
                uniq.append(r)
        return sorted(rng.sample(uniq, min(cap, len(uniq))), key=lambda r: r["metadata"]["trace_id"])
    arm_recs = {arm: {cid: pick(teacher[arm].get(cid, []), TEACHER_CAP) + pick(selfrec[arm].get(cid, []), SELF_CAP) for cid in sorted(questions)}
                for arm in ("full", "partial")}
    reason = {}
    both = []
    for cid in sorted(questions):
        f, pp = bool(arm_recs["full"][cid]), bool(arm_recs["partial"][cid])
        if f and pp:
            both.append(cid)
        else:
            reason[cid] = "no_records_both_arms" if not f and not pp else ("no_partial_records" if f else "no_full_records")
    # ---- 평가 셋 강한 겹침
    targets = W6.load_targets(None)
    prot = ("selection_v1", "selection_v2", "aux_test_v1", "valid98", "vendor100")  # vendor100은 보고만(결정 106)
    hold = [(i["id"], i["question"], EV.derive_grounding(i["gold"])) for i in read_jsonl(INV / "pilot_006_prep/aug300/augmentation_300.jsonl")
            if i["status"] == "holdout"]
    sets = {n: targets[n] for n in prot}
    sets["augmentation_holdout_v1"] = hold
    views = {n: {json.dumps(EV._grounding_view(pl), ensure_ascii=False, sort_keys=True, default=str) for _, _, pl in rows if pl} for n, rows in sets.items()}
    qkeys = {n: {question_key(q) for _, q, _ in rows} for n, rows in sets.items()}
    grams = {n: [W6.grams(question_key(q)) for _, q, _ in rows] for n, rows in sets.items()}
    strong, vendor_only = {}, {}
    for cid in both:
        q = questions[cid]
        k = question_key(q["question"])
        g = W6.grams(k)
        v = json.dumps(EV._grounding_view(render_full(q["semantics"])), ensure_ascii=False, sort_keys=True, default=str)
        hits = [f"{n}:question" for n in sets if k in qkeys[n]]
        hits += [f"{n}:jaccard" for n in sets if max((len(g & vg) / len(g | vg) for vg in grams[n]), default=0) >= 0.5]
        hits += [f"{n}:same_grounding" for n in sets if v in views[n]]
        if hits and all(h.startswith("vendor100:") for h in hits):
            vendor_only[cid] = hits
        elif hits:
            strong[cid] = [h for h in hits if not h.startswith("vendor100:")]
            reason[cid] = "eval_strong_overlap"
    kept_q = [cid for cid in both if cid not in strong]
    # ---- 유형 상한
    b6 = json.loads((INV / "batch006/candidates_checked.json").read_text(encoding="utf-8"))["candidates"]
    exempt = frozenset(f"t2pc:{c['id']}" for c in b6 if c.get("variant")) | frozenset(c for c in questions if questions[c]["corpus_group"] == "batch007")
    cell = {cid: profile(render_full(questions[cid]["semantics"]))["cell"] for cid in kept_q}
    capped, caps, _ = TC.capped([{"qid": q} for q in kept_q], lambda it: cell[it["qid"]], lambda it: it["qid"], 0.09, exempt)
    final_q = sorted(it["qid"] for it in capped)
    for cid in set(kept_q) - set(final_q):
        reason[cid] = "type_cap"
    qlist_sha = hashlib.sha256("\n".join(final_q).encode()).hexdigest()
    # ---- 쓰기
    out.mkdir(parents=True, exist_ok=True)
    manifests = {}
    for arm in ("full", "partial"):
        d = out / arm
        d.mkdir(exist_ok=True)
        rows = []
        for cid in final_q:
            for r in arm_recs[arm][cid]:
                meta = {**r["metadata"], **meta_of(cid), "format": FORMAT, "source_record_id": cid, "grounding_target": arm, "representation": "flat",
                        "corpus_group": questions[cid]["corpus_group"], "_rc": f"{a.label}: 학습 전 후보, PLAN 고정 전"}
                meta.setdefault("parent_intent", cid)
                rows.append({"messages": r["messages"], "metadata": meta})
        with open(d / "sft_train.jsonl", "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        (d / "sft_valid.jsonl").write_text("", encoding="utf-8")
        system = expected_system_prompt(arm)
        man = {"sft": {"generated_at": datetime.now(timezone.utc).isoformat(), "representation": "flat", "format": FORMAT,
                       "prompt_hash": hashlib.sha256(system.encode()).hexdigest(), "grounding_target": arm, "release_candidate": a.label,
                       "note": "학습 전 후보, PLAN 고정 전(pilot_006 세션 2b)", "train_count": len(rows), "validation_count": 0, "questions": len(final_q),
                       "question_list_sha256": qlist_sha, "issues": [], "by_source": dict(Counter(r["metadata"]["loss_scope"] for r in rows)),
                       "max_seq_length": a.max_seq_length,
                       "output_hashes": {"sft_train.jsonl": sha(d / "sft_train.jsonl"), "sft_valid.jsonl": sha(d / "sft_valid.jsonl")}}, "dpo": {}}
        (d / "manifest.json").write_text(json.dumps(man, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        manifests[arm] = man["sft"]

    def st(v):
        v = sorted(v)
        return {"n": len(v), "p50": v[len(v) // 2], "p90": v[int(0.9 * (len(v) - 1))], "max": v[-1], f"over_{a.max_seq_length}": sum(x > a.max_seq_length for x in v)} if v else None
    (out / "lengths.json").write_text(json.dumps({"max_seq_length": a.max_seq_length, "by_arm_kind": {k: st(v) for k, v in lens.items()},
                                                  "over_limit_dropped": over}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    qrows = []
    for cid in sorted(questions):
        qrows.append({"id": cid, "group": questions[cid]["corpus_group"], "aliases": sorted(k for k, v in alias.items() if v == cid),
                      "in_build": cid in final_q, "reason": None if cid in final_q else reason.get(cid),
                      "teacher_pass": {arm: len(teacher[arm].get(cid, [])) for arm in ("full", "partial")},
                      "self_correct": {arm: len(selfrec[arm].get(cid, [])) for arm in ("full", "partial")},
                      "records": {arm: len(arm_recs[arm][cid]) if cid in final_q else 0 for arm in ("full", "partial")}})
    (out / "questions.json").write_text(json.dumps(qrows, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    summary = {"label": a.label, "status": "학습 전 후보, PLAN 고정 전", "missing_sources": missing, "partial_build": bool(missing),
               "corpus_records": len(corpus), "questions_after_merge": len(questions), "merged_aliases": len(alias),
               "questions_with_records_both_arms": len(both), "dropped": dict(Counter(reason.values())),
               "strong_overlap": strong, "vendor100_overlap(report only, decision 106)": vendor_only, "type_cap": {"tau": 0.09, "caps(non-exempt)": caps, "exempt_in_pool": len(exempt & set(kept_q)), "kept": len(final_q)},
               "final_questions": len(final_q), "final_by_group": dict(Counter(questions[c]["corpus_group"] for c in final_q)),
               "question_list_sha256": qlist_sha, "records": {arm: manifests[arm]["train_count"] for arm in manifests},
               "records_by_loss_scope": {arm: manifests[arm]["by_source"] for arm in manifests},
               "teacher": dict(teach_stats), "self": dict(self_stats), "over_limit_dropped": len(over),
               "caps": {"teacher_per_question": TEACHER_CAP, "self_per_question": SELF_CAP, "seed": SEED},
               "inputs": {"approved_train_v1": sha(AP.APPROVED / "approved_train_v1.jsonl"),
                          **({"teacher_v2_traces": sha(TEACH)} if TEACH.exists() else {}),
                          **{f"{arm}:{n}": sha(j) for arm, src in SELF.items() for n, _, j in src if j.exists()}}}
    (out / "build_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k not in ("strong_overlap", "inputs")}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
