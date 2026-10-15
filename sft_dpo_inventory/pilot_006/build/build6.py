# -*- coding: utf-8 -*-
"""pilot_006 데이터 빌드 도구(C6): canonical + teacher trace + 8b 자체 표본 → 두 arm(Full, Partial)의 SFT 레코드. 모델 호출 없음.

    hfvenv/bin/python sft_dpo_inventory/pilot_006/build/build6.py --mode provisional [--with-j6]

- **provisional**(세션 2): 지금 승인된 데이터만(trunk pilot_004 판 131질문, pg 수용 147 중 trunk와 겹치지 않는 질문, J1·J6 정답 표본).
  출력 ``PROVISIONAL/``. **학습에 쓰지 않는다**(파일 머리 ``_provisional``, README). final 모드는 세션 3에서 승인 결과를 넣어 만든다.
- 질문: canonical 레코드(``pilot_006_prep/canonical/canonical_records.jsonl``)의 semantics. 미승인(초안)·EDIT_REQUIRED(결정 121)·결정 119 제외는 자동으로 뺀다.
- 레코드(결정 86 출처별 손실 범위, ``metadata.loss_scope``):
  - teacher(``full_response``): provisional은 pilot_004 판의 기존 teacher 레코드(t2pc)와 pg reasoning_v001의 27b teacher(``t27b_*``)의 thinking을 쓰고,
    답 JSON은 canonical 렌더(Full = ``render_full``, Partial = ``render_partial``)로 붙인다. **표현 중립 지시로 모은 trace가 아니다**(``teacher_neutral: false``).
    질문당 최대 4개(결정 48, seed 20261016).
  - 8b 자체(``json_only``): arm 자신의 prompt로 모은 정답 표본만. Full = pilot_004 판 8b 자체 레코드(t2pc) + J1 정답 표본(pg), Partial = J6 정답 표본(pg, ``--with-j6``).
    원문 그대로(자기 JSON). 같은 원문은 하나로, 질문당 최대 4개(seed 20261016).
- 두 arm 질문 목록: 두 arm 모두 레코드가 하나 이상인 질문만 남긴다(한쪽에만 있으면 두 arm에서 뺌). 질문 목록 sha256이 같아야 한다.
- 유형 상한(결정 88·92, τ 0.09): 질문 단위(``pilot_004_prep/type_caps.capped``). 결정 92 예외 = trunk batch006 실차 대조 질문.
- 평가 셋 겹침: 보호 셋 5개 + augmentation_holdout_v1과 강한 겹침(정규화 질문, 문자 3-gram Jaccard ≥ 0.5, 같은 grounding)이 있는 질문은 뺀다.
- 길이(결정 125 F4): 레코드마다 입력(arm system prompt + 질문, 학습 렌더링) + 응답 token. ``L_req`` = 모든 후보 레코드(상한 전, 두 arm,
  J1 정답 표본 전부, J6이 있으면 J6 정답 표본 전부)를 담는 가장 작은 256 배수. M1용으로 arm별 가장 긴 레코드 10개를 낸다.
출력: ``<out>/{full,partial}/sft_train.jsonl, sft_valid.jsonl, manifest.json``, ``<out>/build_summary.json``, ``<out>/lengths.json``, ``<out>/m1/``.
"""
import argparse
import hashlib
import json
import math
import random
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_004_prep"))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_prep_004/type_target"))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_006/teacher"))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_006_prep/aug300"))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/thinking_prep_001"))

INV = ROOT / "sft_dpo_inventory"
SEED, TEACHER_CAP, SELF_CAP = 20261016, 4, 4
P004 = ROOT / "training/generated/thinking_pilot004_t2pc/sft_train.jsonl"
J1_RAW = ROOT / "training/generated/pilot_006/self_full/raw/self_full_raw.jsonl"
J6_RAW = ROOT / "training/generated/pilot_006/self_partial/raw/self_partial_raw.jsonl"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def thinking_of(content):
    head = content.split("</think>", 1)[0]
    return head[len("<think>\n"):] if head.startswith("<think>\n") else head.lstrip("<think>").lstrip("\n")


def main():
    import evaluate_vendor100 as EV
    import teacher6 as T6
    import type_caps as TC
    from grounding.canonical import record as canon_record  # noqa: F401
    from grounding.full_renderer import render_full
    from training.data.common import read_jsonl
    from training.data.split import question_key
    from training.trainer_common import expected_system_prompt, render_prompt
    from type_target import profile
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=("provisional",), required=True)
    p.add_argument("--with-j6", action="store_true")
    p.add_argument("--out", default=str(HERE / "PROVISIONAL"))
    a = p.parse_args()
    out = Path(a.out)
    rng = random.Random(SEED)

    # ---- 질문
    canon = read_jsonl(INV / "pilot_006_prep/canonical/canonical_records.jsonl")
    held = set(json.loads((INV / "pg_imports/acceptance_e6.json").read_text(encoding="utf-8"))["pg_batch006_edit_required(held)"])
    questions, by_key, dropped = {}, {}, Counter()
    for r in canon:
        if r["source"] == "t2pc_v006":
            sid = r["provenance"]["source_record_id"]
        elif r["source"] == "pg_reasoning_v001":
            sid0 = r["provenance"]["source_record_id"]
            sid = f"pg-{sid0}" if sid0.startswith("b006-") else sid0
            if sid in held:
                dropped["pg_edit_required(decision 121)"] += 1
                continue
        else:
            dropped[f"not_approved:{r['source']}"] += 1
            continue
        k = question_key(r["question"])
        if k in by_key:
            continue
        qid = f"{'t2pc' if r['source'] == 't2pc_v006' else 'pg'}:{sid}"
        by_key[k] = qid
        questions[qid] = {"qid": qid, "sid": sid, "source": r["source"], "question": r["question"], "semantics": r["semantics"],
                          "pg_rr_sid": r["provenance"]["source_record_id"] if r["source"] == "pg_reasoning_v001" else None}
    # ---- teacher 후보
    teacher = {"full": defaultdict(list), "partial": defaultdict(list)}
    p004 = read_jsonl(P004)
    # 질문별 trunk metadata(정지 target: target_kind·expected_stop, parent_intent·family)는 reviewed_gold_v006_t2pc에서(135질문, pg와 같은 v005 질문 포함)
    t2pc_meta = {r["metadata"]["source_record_id"]: r["metadata"] for r in read_jsonl(ROOT / "training/generated/reviewed_gold_v006_t2pc/sft_train.jsonl")}
    for rec in p004:
        sid = rec["metadata"]["source_record_id"]
        t2pc_meta.setdefault(sid, rec["metadata"])
        qid = f"t2pc:{sid}"
        if qid not in questions or rec["metadata"].get("loss_scope") != "full_response":
            continue
        trace = {"trace_id": rec["metadata"]["trace_id"], "thinking": thinking_of(rec["messages"][-1]["content"]),
                 "model": rec["metadata"].get("teacher_model"), "model_digest": rec["metadata"].get("teacher_model_digest")}
        for arm, r in T6.to_arm_records(trace, questions[qid]["semantics"], questions[qid]["question"], qid).items():
            r["metadata"]["teacher_neutral"] = False
            r["metadata"]["origin"] = "pilot_004 teacher record"
            teacher[arm][qid].append(r)
    rr = {r["metadata"]["source_record_id"]: r for r in read_jsonl(INV / "pg_imports/reviewed_reasoning_v001/dataset.jsonl")}
    for qid, q in questions.items():
        if not q["pg_rr_sid"]:
            continue
        r0 = rr[q["pg_rr_sid"]]
        if not str(r0["metadata"].get("reasoning_source", "")).startswith("t27b"):
            continue
        trace = {"trace_id": r0["metadata"].get("trace_id") or f"{q['pg_rr_sid']}:pg_t27b", "thinking": thinking_of(r0["messages"][-1]["content"]),
                 "model": r0["metadata"].get("teacher_model"), "model_digest": r0["metadata"].get("teacher_digest")}
        for arm, r in T6.to_arm_records(trace, q["semantics"], q["question"], qid).items():
            r["metadata"]["teacher_neutral"] = False
            r["metadata"]["origin"] = f"pg reviewed_reasoning_v001 {r0['metadata'].get('reasoning_source')}"
            teacher[arm][qid].append(r)
    # ---- 8b 자체 후보
    selfrec = {"full": defaultdict(list), "partial": defaultdict(list)}
    for rec in p004:
        qid = f"t2pc:{rec['metadata']['source_record_id']}"
        if qid in questions and rec["metadata"].get("loss_scope") == "json_only":
            selfrec["full"][qid].append({**rec, "metadata": {**rec["metadata"], "grounding_target": "full", "origin": "pilot_004 8b self record"}})

    from grounding.completion import complete_grounding_payload
    from training.data import thinking as TH
    from training.data.validation import assess, target_ok
    contract_dropped = Counter()

    def add_samples(arm, judgement, raw_path):
        jd = json.loads(judgement.read_text(encoding="utf-8"))
        ok = {t for q in jd["per_question"] for t in q["correct_trace_ids"]}
        raws = {}
        for line in raw_path.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            if r["trace_id"] in ok:
                raws[r["trace_id"]] = r
        system = expected_system_prompt(arm)
        for tid, r in raws.items():
            sid = r["id"][len("pg-rr-"):] if r["id"].startswith("pg-rr-") else None
            if sid is None:
                continue
            name = f"pg-{sid}" if sid.startswith("b006-") else sid
            qid = f"pg:{name}"
            if qid not in questions:
                continue
            # 채점 일치(grounding_check)에 더해 학습 계약도 통과해야 한다(pilot_004 빌드의 contract_ok와 같은 조건)
            try:
                tgt = TH.response_json(r["raw_text"])
                tgt = complete_grounding_payload(tgt) if arm == "partial" else tgt
                base = t2pc_meta.get(questions[qid]["sid"], {})
                ok_contract = target_ok(assess(tgt, questions[qid]["question"]), {k: base[k] for k in ("target_kind", "expected_stop") if base.get(k) is not None})
            except Exception:  # noqa: BLE001
                ok_contract = False
            if not ok_contract:
                contract_dropped[arm] += 1
                continue
            selfrec[arm][qid].append({"messages": [{"role": "system", "content": system}, {"role": "user", "content": questions[qid]["question"]},
                                                   {"role": "assistant", "content": r["raw_text"]}],
                                      "metadata": {"source_record_id": qid, "source": "hf", "loss_scope": "json_only", "grounding_target": arm,
                                                   "trace_id": tid, "trace_sha256": r["raw_sha256"], "format": "thinking",
                                                   "origin": f"{'J1' if arm == 'full' else 'J6'} vLLM BF16 base sample(judged correct)"}})
    add_samples("full", INV / "pilot_006_prep/self_samples/j1_judgement.json", J1_RAW)
    if a.with_j6:
        add_samples("partial", INV / "pilot_006_prep/self_samples/j6_judgement.json", J6_RAW)

    # ---- 길이(상한 전 모든 후보)
    import hf_thinking as H
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(H.MODEL, revision=H.REVISION)
    cfg = {"chat_template_kwargs": {"enable_thinking": True}}
    plen = {}

    def length(rec):
        key = (hashlib.sha256(rec["messages"][0]["content"].encode("utf-8")).hexdigest(), rec["messages"][1]["content"])
        if key not in plen:
            plen[key] = len(tok(render_prompt(tok, rec["messages"][:2], cfg), add_special_tokens=False)["input_ids"])
        return plen[key] + len(tok(rec["messages"][2]["content"], add_special_tokens=False)["input_ids"]) + 1

    cand_lengths = []
    for arm in ("full", "partial"):
        for kind, pool in (("teacher", teacher[arm]), ("self", selfrec[arm])):
            for qid, recs in pool.items():
                for r in recs:
                    cand_lengths.append({"arm": arm, "kind": kind, "qid": qid, "trace_id": r["metadata"]["trace_id"], "tokens": length(r), "_rec": r})
    # J1 정답 표본 전부(승인 전 질문 포함)도 L_req 후보에 넣는다(Full). J6도 있으면(Partial).
    extra = []
    for arm, jpath, rpath in (("full", INV / "pilot_006_prep/self_samples/j1_judgement.json", J1_RAW),
                              ("partial", INV / "pilot_006_prep/self_samples/j6_judgement.json", J6_RAW)):
        if arm == "partial" and not a.with_j6:
            continue
        ok = {t for q in json.loads(jpath.read_text(encoding="utf-8"))["per_question"] for t in q["correct_trace_ids"]}
        items = {json.loads(l)["id"]: json.loads(l)["question"] for l in (INV / "pilot_006_prep/gpu/inputs/self_questions.jsonl").read_text(encoding="utf-8").splitlines()}
        system = expected_system_prompt(arm)
        for line in rpath.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            if r["trace_id"] in ok:
                rec = {"messages": [{"role": "system", "content": system}, {"role": "user", "content": items[r["id"]]}, {"role": "assistant", "content": r["raw_text"]}]}
                rec["metadata"] = {"source_record_id": r["id"], "source": "hf", "loss_scope": "json_only", "grounding_target": arm,
                                   "trace_id": r["trace_id"], "origin": "M1 length candidate (approval not required for memory check)"}
                extra.append({"arm": arm, "kind": "self_all_correct", "qid": r["id"], "trace_id": r["trace_id"], "tokens": length(rec), "_rec": rec})
    all_len = cand_lengths + extra
    max_tok = max(x["tokens"] for x in all_len)
    l_req = int(math.ceil(max_tok / 256) * 256)

    # ---- 선택(상한)
    def pick(recs, cap):
        seen, uniq = set(), []
        for r in recs:
            h = hashlib.sha256(r["messages"][2]["content"].encode("utf-8")).hexdigest()
            if h not in seen:
                seen.add(h)
                uniq.append(r)
        return sorted(rng.sample(uniq, min(cap, len(uniq))), key=lambda r: r["metadata"]["trace_id"])

    arm_recs = {arm: {qid: pick(teacher[arm].get(qid, []), TEACHER_CAP) + pick(selfrec[arm].get(qid, []), SELF_CAP) for qid in questions}
                for arm in ("full", "partial")}
    both = [qid for qid in questions if arm_recs["full"][qid] and arm_recs["partial"][qid]]
    one_side = {qid: [arm for arm in ("full", "partial") if arm_recs[arm][qid]] for qid in questions if qid not in both}
    # ---- 평가 셋 겹침(강한 겹침)
    import check_aug300 as W6
    targets = W6.load_targets(None)
    strong = {}
    prot = ("selection_v1", "selection_v2", "aux_test_v1", "valid98", "vendor100")
    hold = [(i["id"], i["question"], EV.derive_grounding(i["gold"])) for i in read_jsonl(INV / "pilot_006_prep/aug300/augmentation_300.jsonl")
            if i["status"] == "holdout"]
    sets = {n: targets[n] for n in prot}
    sets["augmentation_holdout_v1"] = hold
    views = {n: {json.dumps(EV._grounding_view(pl), ensure_ascii=False, sort_keys=True, default=str) for _, _, pl in rows if pl} for n, rows in sets.items()}
    qkeys = {n: {question_key(q): rid for rid, q, _ in rows} for n, rows in sets.items()}
    grams = {n: [(rid, W6.grams(question_key(q))) for rid, q, _ in rows] for n, rows in sets.items()}
    for qid in both:
        q = questions[qid]
        k = question_key(q["question"])
        g = W6.grams(k)
        v = json.dumps(EV._grounding_view(render_full(q["semantics"])), ensure_ascii=False, sort_keys=True, default=str)
        hits = [f"{n}:question" for n in sets if k in qkeys[n]]
        hits += [f"{n}:jaccard" for n in sets if max((len(g & vg) / len(g | vg) for _, vg in grams[n]), default=0) >= 0.5]
        hits += [f"{n}:same_grounding" for n in sets if v in views[n]]
        if hits:
            strong[qid] = hits
    kept_q = [qid for qid in both if qid not in strong]
    # ---- 유형 상한(질문 단위)
    b6 = json.loads((INV / "batch006/candidates_checked.json").read_text(encoding="utf-8"))["candidates"]
    exempt = frozenset(f"t2pc:{c['id']}" for c in b6 if c.get("variant"))
    cell = {qid: profile(render_full(questions[qid]["semantics"]))["cell"] for qid in kept_q}
    capped, caps, m = TC.capped([{"qid": q} for q in kept_q], lambda it: cell[it["qid"]], lambda it: it["qid"], 0.09, exempt)
    final_q = sorted(it["qid"] for it in capped)
    qlist_sha = hashlib.sha256("\n".join(final_q).encode("utf-8")).hexdigest()
    # ---- 쓰기
    from training.data.thinking import FORMAT
    out.mkdir(parents=True, exist_ok=True)
    manifests = {}
    for arm in ("full", "partial"):
        d = out / arm
        d.mkdir(exist_ok=True)
        rows = []
        for qid in final_q:
            for r in arm_recs[arm][qid]:
                meta = dict(r["metadata"])
                base = t2pc_meta.get(questions[qid]["sid"], {})
                for key in ("target_kind", "expected_stop"):
                    if base.get(key) is not None:
                        meta[key] = base[key]
                meta.update(format=FORMAT, source_record_id=qid, parent_intent=base.get("parent_intent", qid), family=base.get("family"),
                            grounding_target=arm, representation="flat", _provisional="학습에 쓰지 않음(pilot_006 세션 2 시험 빌드)")
                rows.append({"messages": r["messages"], "metadata": meta})
        with open(d / "sft_train.jsonl", "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        (d / "sft_valid.jsonl").write_text("", encoding="utf-8")
        system = expected_system_prompt(arm)
        man = {"sft": {"generated_at": datetime.now(timezone.utc).isoformat(), "representation": "flat", "format": FORMAT,
                       "prompt_hash": hashlib.sha256(system.encode()).hexdigest(), "grounding_target": arm, "provisional": True,
                       "note": "학습에 쓰지 않음(pilot_006 세션 2 시험 빌드)", "train_count": len(rows), "validation_count": 0, "questions": len(final_q),
                       "question_list_sha256": qlist_sha, "issues": [],
                       "by_source": dict(Counter(r["metadata"]["loss_scope"] for r in rows)),
                       "output_hashes": {"sft_train.jsonl": sha(d / "sft_train.jsonl"), "sft_valid.jsonl": sha(d / "sft_valid.jsonl")}}, "dpo": {}}
        (d / "manifest.json").write_text(json.dumps(man, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        manifests[arm] = man["sft"]
    # ---- M1 세트(arm별 가장 긴 레코드 10개, 상한 전 후보 중)
    m1_list = {}
    for m1_name, cap in (("m1", None), ("m1_12288", 12288)):
      m1 = out / m1_name
      m1.mkdir(exist_ok=True)
      for arm in ("full", "partial"):
          # 메모리 확인은 승인과 무관하므로 길이 후보 전체(J1·J6 정답 표본 전부 포함)에서 가장 긴 10개
          from grounding.completion import complete_grounding_payload
          from training.data import thinking as TH
          from training.data.validation import assess, target_ok

          def trainable(x):
              r = x["_rec"]
              meta = dict(r.get("metadata") or {})
              base = t2pc_meta.get(questions[x["qid"]]["sid"], {}) if x["qid"] in questions and x["kind"] != "self_all_correct" else {}
              meta.update({k: base[k] for k in ("target_kind", "expected_stop") if base.get(k) is not None})
              t = TH.response_json(r["messages"][2]["content"])
              t = complete_grounding_payload(t) if arm == "partial" else t
              return target_ok(assess(t, r["messages"][1]["content"]), meta)
          top = []
          for x in sorted((x for x in all_len if x["arm"] == arm and (cap is None or x["tokens"] <= cap)), key=lambda x: -x["tokens"]):
              if len(top) == 10:
                  break
              if trainable(x):
                  top.append(x)
          m1_list[f"{m1_name}:{arm}"] = [{k: x[k] for k in ("qid", "kind", "trace_id", "tokens")} for x in top]
          d = m1 / arm
          d.mkdir(exist_ok=True)
          with open(d / "sft_train.jsonl", "w", encoding="utf-8") as f:
              for x in top:
                  r = x["_rec"]
                  base = t2pc_meta.get(questions[x["qid"]]["sid"], {}) if x["qid"] in questions else {}
                  if x["kind"] == "self_all_correct":
                      base = {}
                  meta = {**r["metadata"], "format": FORMAT, "parent_intent": f"m1-{x['trace_id']}", "source_record_id": x["qid"],
                          **{k: base[k] for k in ("target_kind", "expected_stop") if base.get(k) is not None}}
                  f.write(json.dumps({"messages": r["messages"], "metadata": meta}, ensure_ascii=False) + "\n")
          (d / "sft_valid.jsonl").write_text("", encoding="utf-8")
          system = expected_system_prompt(arm)
          (d / "manifest.json").write_text(json.dumps({"sft": {"representation": "flat", "format": FORMAT, "prompt_hash": hashlib.sha256(system.encode()).hexdigest(),
                                                               "issues": [], "note": "M1 메모리 확인 전용(결정 129)",
                                                               "output_hashes": {"sft_train.jsonl": sha(d / "sft_train.jsonl"), "sft_valid.jsonl": sha(d / "sft_valid.jsonl")}},
                                                       "dpo": {}}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    lengths = {"L_req": l_req, "max_tokens": max_tok, "argmax": {k: v for k, v in max(all_len, key=lambda x: x["tokens"]).items() if k != "_rec"},
               "by_arm_kind": {}, "m1_longest_10_per_arm": m1_list}
    for arm in ("full", "partial"):
        for kind in ("teacher", "self", "self_all_correct"):
            v = [x["tokens"] for x in all_len if x["arm"] == arm and x["kind"] == kind]
            if v:
                v.sort()
                lengths["by_arm_kind"][f"{arm}:{kind}"] = {"n": len(v), "p50": v[len(v) // 2], "p99": v[int(0.99 * (len(v) - 1))], "max": v[-1],
                                                           "over_11392": sum(t > 11392 for t in v)}
    (out / "lengths.json").write_text(json.dumps(lengths, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    summary = {"mode": a.mode, "with_j6": a.with_j6, "provisional_note": "학습에 쓰지 않음", "questions_pool": len(questions), "dropped_pool": dict(dropped),
               "questions_with_records_both_arms": len(both), "questions_one_side_only": {k: v for k, v in one_side.items()},
               "one_side_count": dict(Counter("+".join(v) or "none" for v in one_side.values())),
               "strong_overlap_dropped": strong, "type_cap": {"tau": 0.09, "caps(non-exempt)": caps, "exempt": len(exempt & set(kept_q)), "kept": len(final_q)},
               "final_questions": len(final_q), "question_list_sha256": qlist_sha, "records": {arm: manifests[arm]["train_count"] for arm in manifests},
               "records_by_loss_scope": {arm: manifests[arm]["by_source"] for arm in manifests}, "L_req": l_req,
               "self_samples_dropped_contract": dict(contract_dropped),
               "caps": {"teacher_per_question": TEACHER_CAP, "self_per_question": SELF_CAP, "seed": SEED},
               "inputs": {str(p.relative_to(ROOT)): sha(p) for p in (P004, J1_RAW, INV / "pilot_006_prep/canonical/canonical_records.jsonl",
                                                                       INV / "pilot_006_prep/self_samples/j1_judgement.json")}}
    (out / "build_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k not in ("questions_one_side_only", "strong_overlap_dropped", "inputs")}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
