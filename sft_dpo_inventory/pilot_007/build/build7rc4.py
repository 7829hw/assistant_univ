# -*- coding: utf-8 -*-
"""RC4 빌드(pilot_007 A2 C2, B단계 준비 — **학습에 쓰지 않음**). RC4 = RC3c + batch010 승인분 + S-focus 정답 표본. 모델 호출 없음.

    hfvenv/bin/python sft_dpo_inventory/pilot_007/build/build7rc4.py   # -> build/RC4/{full,partial}/…, build/RC4/order_o<seed>.json

RC3c 레코드는 그대로 두고 더하기만 한다(``build6rc``를 처음부터 다시 돌리면 질문 순서대로 쓰는 난수 때문에 RC3c의 8b 선택이 바뀌므로).
- 새 8b 레코드: ``build6rc``의 8b 경로와 같은 형식·계약(``response_json`` → Partial은 ``complete_grounding_payload`` → ``target_ok``), 승인 gold 판정은 corpus v3
  (``judge7.py`` = judge6 + v3). 출처 J-b010(batch010 50문항 두 arm 표본 9개)과 S-focus(arm별 64표본).
- 길이 상한 12,288(결정 125), 같은 원문 하나로, 질문당 8b 상한 4: batch010 질문은 정답 표본에서 ``random.Random(20261016)``으로 4개(새 난수 줄기, RC3c와 무관),
  S-focus 질문은 RC3c에 있는 8b 수를 빼고 남은 자리만큼 새 정답 표본에서.
- teacher: batch010에는 teacher trace가 없다(새 수집 없음, 결정 166). RC3c teacher 레코드는 그대로.
- 두 arm 모두 레코드가 있는 질문만(두 arm 질문 목록 같음). 평가 셋 강한 겹침 검사는 ``build6rc``와 같은 규칙을 새 질문에 적용.
- 유형 상한 τ 0.09(결정 88·92): build6rc와 같은 예외·계산(``caps_for``)을 RC3c + 새 질문 전체 위에서 하고, RC3c 질문은 빼지 않은 채 칸 자리를 먼저 차지,
  새 질문은 칸마다 남은 자리만큼(같은 칸별 섞기 순서). RC3c 질문이 이미 상한을 넘는 칸은 보고만.
- 순서(결정 168): ``train/order7``로 순서 seed 43·20261016·7의 질문 순서 파일(``order_o<seed>.json``)을 쓰고 두 arm 질문 순서가 같은지 확인한다.
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
RC3C, OUT = HERE / "RC3c", HERE / "RC4"
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
    rc3c = {arm: read_jsonl(RC3C / arm / "sft_train.jsonl") for arm in ("full", "partial")}
    old_q = sorted({r["metadata"]["source_record_id"] for r in rc3c["full"]})
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
                                    "_rc": "RC4: B단계 준비(학습 전 후보)"}}
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
    # build6rc와 같은 예외(결정 92: batch006 실차 대조 변형 + batch007)와 같은 상한 계산(caps_for, τ 0.09)을 RC3c + 새 질문 전체 위에서 한다.
    # RC3c 질문은 빼지 않고 자기 칸의 자리를 먼저 차지한다. 새 질문은 칸마다 남은 자리(상한 − RC3c 수)를 build6rc와 같은 칸별 섞기 순서로 채운다.
    b6 = json.loads((INV / "batch006/candidates_checked.json").read_text(encoding="utf-8"))["candidates"]
    exempt = frozenset(f"t2pc:{c['id']}" for c in b6 if c.get("variant")) | frozenset(c for c in allq if corpus[c]["corpus_group"] == "batch007")
    nonex = [c for c in allq if c not in exempt]
    m_total, caps = TC.caps_for(Counter(cell[c] for c in nonex), TC.DEVD, 0.09)
    old_in_cell = Counter(cell[c] for c in old_q if c not in exempt)
    final_new, cap_report = [], {}
    by_cell = defaultdict(list)
    for c in kept_new:
        by_cell[cell[c]].append(c)
    for cl, qs in sorted(by_cell.items()):
        order = sorted(qs)
        random.Random(f"{TC.SEED}:{cl}").shuffle(order)
        room = max(0, caps.get(cl, 0) - old_in_cell.get(cl, 0))
        take = [c for c in order if c in exempt] + [c for c in order if c not in exempt][:room]
        final_new += take
        cap_report[cl] = {"cap": caps.get(cl, 0), "rc3c": old_in_cell.get(cl, 0), "new_available": len(qs), "new_added": len(take)}
    final_new = sorted(final_new)
    for c in set(kept_new) - set(final_new):
        reason[c] = "type_cap"
    over = {cl: {"cap": caps.get(cl, 0), "rc3c": n} for cl, n in old_in_cell.items() if n > caps.get(cl, 0)}
    final_q = sorted(old_q + final_new)
    OUT.mkdir(parents=True, exist_ok=True)
    built = {}
    for arm in ("full", "partial"):
        d = OUT / arm
        d.mkdir(exist_ok=True)
        rows = list(rc3c[arm])
        for cid in sorted(add[arm]):
            if cid in old_q or cid in final_new:
                for r in add[arm][cid]:  # build6rc 쓰기 단계와 같은 metadata 보강
                    meta = {**r["metadata"], **meta_of(cid), "format": TH.FORMAT, "source_record_id": cid, "grounding_target": arm, "representation": "flat",
                            "corpus_group": corpus[cid]["corpus_group"], "_rc": "RC4: B단계 준비(학습 전 후보)",
                            "k3_scope_name_family": bool(corpus[cid].get("k3_scope_name_family"))}
                    meta.setdefault("parent_intent", cid)
                    rows.append({"messages": r["messages"], "metadata": meta})
        with (d / "sft_train.jsonl").open("w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        (d / "sft_valid.jsonl").write_text("", encoding="utf-8")
        man = json.loads((RC3C / arm / "manifest.json").read_text(encoding="utf-8"))
        s = man["sft"]
        s.update(generated_at=datetime.now(timezone.utc).isoformat(), release_candidate="RC4",
                 note=f"pilot_007 RC4 = RC3c({arm}) + batch010 승인분(8b J-b010) + S-focus 정답 표본; B단계 준비(학습 전 후보). build7rc4.py",
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
    summary = {"label": "RC4", "base": "RC3c", "built": built, "questions": {"rc3c": len(old_q), "batch010_approved": len(new_q), "batch010_added": len(final_new),
                                                                            "total": len(final_q), "batch010_not_added": reason},
               "question_list_sha256": hashlib.sha256("\n".join(final_q).encode()).hexdigest(), "s_focus_added_records": sfq,
               "order_sha256": {str(k): v for k, v in orders.items()},
               "type_cap": {"tau": 0.09, "max_total_nonexempt": m_total, "new_question_cells": cap_report, "rc3c_cells_over_cap(kept, 보고만)": over}, "self_stats": dict(stats), "approved_corpus": "v3 (manifest_v3.json)",
               "teacher": "RC3c 그대로(batch010 teacher 없음, 결정 166 새 수집 없음)", "use": "B단계 준비 — A2에서 학습에 쓰지 않음"}
    (OUT / "build_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
