# -*- coding: utf-8 -*-
"""reviewed_reasoning_v001 freeze(지시 14–24절). 모델 호출 0(tokenizer만 CPU).

    HF_HOME=/data/hwkim/path_repeat_001/hf-cache HF_HUB_OFFLINE=1 /data/hwkim/path_repeat_001/venv/py/bin/python \
        sft_dpo_inventory/reviewed_reasoning_v001/build_dataset.py
    # -> dataset.jsonl, manifest.json, integrity.json, contamination.json

- 154 = 모델 생성 승인 148(HF 8B R70 70, HF 8B M2 10, M3 3, 27B P1/P2 27, 27B remaining 38) + manual canonical 6.
- 레코드: v006의 system·user를 그대로, assistant = `<think>\\n{thinking}\\n</think>\\n\\n{v006 P0 target 문자열}`.
  reasoning 출처와 무관하게 최종 답은 frozen v006 P0 gold다. 답만 있는 레코드는 0이다.
- 순서: v006 파일 순서.
- 무결성: id 154 unique, thinking 154, 최종 답 = metadata.target_p0 = v006 문자열, `build_targets.convert`로 Full gold에서 다시 만든
  P0가 같고(결정성) Full·P0 실행 결과·의미 서명이 같다(auto_pass), 최종 답의 운영 경로(assess_t2pc) 실행·서명 = Full gold.
- 오염: verify_v006.overlap(보호 원본·확장 지문·평가셋 4종). v005 template·family 겹침은 결정 15·54 허용분(legacy)으로 따로 센다.
- token 길이: 학습과 같은 렌더링(render_prompt, enable_thinking True)으로 prompt / thinking / final / 전체(prompt + 응답 + EOS).
"""
import collections
import hashlib
import importlib.util
import json
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "evaluation/partial_grounding/sft_p0"))


def sha(b):
    return hashlib.sha256(b if isinstance(b, bytes) else b.encode("utf-8")).hexdigest()


def jl(path):
    return [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x.strip()]


def pct(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(p / 100 * (len(xs) - 1))))]


def dist(xs):
    return {"n": len(xs), "min": min(xs), "p50": pct(xs, 50), "p90": pct(xs, 90), "p95": pct(xs, 95), "max": max(xs),
            "mean": round(statistics.mean(xs), 1)} if xs else {"n": 0}


def sources():
    """item_id -> provenance + thinking."""
    out = {}
    sel = {r["trace_id"]: r for r in jl(ROOT / "sft_dpo_inventory/p0_sft_001/selected_traces.jsonl")}
    for r in jl(ROOT / "training/generated/p0_sft_002/r70/sft_train.jsonl"):
        m = r["metadata"]
        content = r["messages"][2]["content"]
        th = content.split("</think>", 1)[0]
        assert th.startswith("<think>\n") and th.endswith("\n")
        th = th[len("<think>\n"):-1]
        if th != sel[m["trace_id"]]["thinking"]:
            raise SystemExit(f"R70 {m['source_record_id']}: thinking이 selected trace와 다르다")
        out[m["source_record_id"]] = {"reasoning_source": "hf8b_r70", "teacher_model": "Qwen/Qwen3-8B",
                                      "teacher_revision": "b968826d9c46dd6066d109eabc6255188de91218", "teacher_digest": None,
                                      "generation_batch": "p0_v006_hf(p0_sft_001 R70)", "trace_id": m["trace_id"],
                                      "seed": sel[m["trace_id"]].get("seed"), "review_decision": "APPROVE_TRACE",
                                      "review_record": "sft_dpo_inventory/p0_sft_001/trace_review.json", "canonical": False, "thinking": th}
    for r in jl(ROOT / "sft_dpo_inventory/p0_sft_003_recovery/recovered_traces.jsonl"):
        out[r["item_id"]] = {"reasoning_source": {"M2": "hf8b_m2", "M3": "hf8b_m3"}[r["recovery"]], "teacher_model": r["teacher_model"],
                             "teacher_revision": r["teacher_revision"], "teacher_digest": None, "generation_batch": r["generation_batch"],
                             "trace_id": r["trace_id"], "seed": r["seed"], "review_decision": r["review_decision"],
                             "review_record": "sft_dpo_inventory/p0_sft_003_recovery/(m2_review.json|m3_recovery.json)",
                             "canonical": False, "thinking": r["thinking"]}
    for name, path in (("t27b_p12", "sft_dpo_inventory/p0_sft_003_teacher27b/generation/approved_traces.jsonl"),
                       ("t27b_remaining", "sft_dpo_inventory/p0_sft_003_teacher27b_remaining/generation/approved_traces.jsonl")):
        for r in jl(ROOT / path):
            if r["item_id"] in out:
                raise SystemExit(f"중복 item {r['item_id']}")
            out[r["item_id"]] = {"reasoning_source": name, "teacher_model": r["teacher_model"], "teacher_revision": None,
                                 "teacher_digest": r["teacher_digest"], "generation_batch": r["generation_batch"],
                                 "trace_id": r["trace_id"], "seed": r["seed"], "review_decision": r["review_decision"],
                                 "review_record": str(Path(path).parent / "human_review.json"), "canonical": False,
                                 "thinking": r["thinking"]}
    n_model = len(out)
    for r in jl(HERE / "canonical_rationales.jsonl"):
        if r["item_id"] in out:
            raise SystemExit(f"canonical 중복 {r['item_id']}")
        out[r["item_id"]] = {"reasoning_source": "manual_canonical", "teacher_model": None, "teacher_revision": None, "teacher_digest": None,
                             "generation_batch": r["generation_batch"], "trace_id": f"{r['item_id']}:manual_canonical", "seed": None,
                             "review_decision": r["review_decision"], "review_record": "sft_dpo_inventory/reviewed_reasoning_v001/canonical_review.json",
                             "canonical": True, "canonical_reason": r["canonical_reason"], "thinking": r["thinking"]}
    return out, n_model


def main():
    import build_targets as BT
    from training.data import thinking
    from training.data.validation import assess_t2pc
    from training.trainer_common import load_config, render_prompt, tokenizer_for
    vspec = importlib.util.spec_from_file_location("verify_v006", ROOT / "evaluation/partial_grounding/sft_p0/verify_v006.py")
    VV = importlib.util.module_from_spec(vspec)
    vspec.loader.exec_module(VV)

    v006 = jl(ROOT / "training/generated/reviewed_gold_v006_p0/sft_train.jsonl")
    src, n_model = sources()
    ids = [r["metadata"]["source_record_id"] for r in v006]
    model_ids = {i for i, s in src.items() if not s["canonical"]}
    if n_model != 148 or len(src) != 154 or set(src) != set(ids) or len(set(ids)) != 154:
        raise SystemExit(f"구성 불일치: model {n_model}, total {len(src)}, v006 {len(set(ids))}, 차집합 {set(ids) ^ set(src)}")

    config = load_config(ROOT / "training/configs/qwen3_8b_p0_sft002_r70_full.yaml", "sft")
    tok = tokenizer_for(config)
    records, man_items, integ, lengths = [], [], [], []
    guard = VV.Protection.current(VV.CC.GOLD_DIR)
    ext_t, ext_f = VV.extended_fingerprints()
    evk = VV.eval_index()
    contam = []
    for r in v006:
        m = r["metadata"]
        i = m["source_record_id"]
        s = src[i]
        th = s["thinking"]
        if not th.strip() or "<think>" in th or "</think>" in th:
            raise SystemExit(f"{i}: thinking 비었거나 태그 포함")
        final = r["messages"][2]["content"]
        content = "<think>\n" + th + "\n</think>\n\n" + final
        target = json.loads(final)
        meta = {"source_record_id": i, "parent_intent": m.get("parent_intent", i), "source": m["source"],
                "dataset_version": "reviewed_reasoning_v001", "base_gold_version": m["dataset_version"], "contract": m["contract"],
                "prompt_sha256": m["prompt_sha256"], "target_p0": target, "target_full": m["target_full"],
                "example": "reasoning", "format": thinking.FORMAT,
                **{k: s[k] for k in ("reasoning_source", "teacher_model", "teacher_revision", "teacher_digest", "generation_batch",
                                     "trace_id", "seed", "review_decision", "canonical")},
                "thinking_sha256": sha(th), "final_sha256": sha(final)}
        if s["canonical"]:
            meta["canonical_reason"] = s["canonical_reason"]
        rec = {"messages": [r["messages"][0], r["messages"][1], {"role": "assistant", "content": content}], "metadata": meta}
        records.append(rec)
        # 무결성
        q = r["messages"][1]["content"]
        p0, conv = BT.convert(q, m["target_full"])
        a_final, a_full = assess_t2pc(thinking.response_json(content), q), assess_t2pc(m["target_full"], q)
        integ.append({"id": i, "reasoning_present": bool(th.strip()), "final_present": bool(final.strip()),
                      "final_eq_target_p0": thinking.response_json(content) == target,
                      "final_eq_v006_string": content.split("</think>\n\n", 1)[1] == final,
                      "deterministic_conversion": p0 == target, "auto_pass": conv["auto_pass"],
                      "exec_equal_full": BT.exec_view(a_final) == BT.exec_view(a_full),
                      "signature_equal_full": BT.strip_events(a_final.get("signature")) == BT.strip_events(a_full.get("signature")),
                      "outcome": a_final.get("outcome"), "error_code": a_final.get("error_code")})
        hits = VV.overlap(guard, ext_t, ext_f, evk, i, q, m["target_full"])
        legacy = [h for h in hits if m["source"] == "v005" and h.endswith(("template", "family"))]
        contam.append({"id": i, "source": m["source"], "hits": hits, "legacy_allowed": legacy, "new": [h for h in hits if h not in legacy]})
        # token
        prompt = render_prompt(tok, rec["messages"][:2], config)
        pt = len(tok(prompt, add_special_tokens=False)["input_ids"])
        tt = len(tok(th, add_special_tokens=False)["input_ids"])
        ft = len(tok(final, add_special_tokens=False)["input_ids"])
        whole = len(tok(prompt + content + tok.eos_token, add_special_tokens=False)["input_ids"])
        lengths.append({"id": i, "source": s["reasoning_source"], "prompt": pt, "thinking": tt, "final": ft, "total": whole,
                        "response": whole - pt})
        man_items.append({"item_id": i, "question": q, "source": m["source"],
                          **{k: s[k] for k in ("reasoning_source", "teacher_model", "teacher_revision", "teacher_digest",
                                               "generation_batch", "trace_id", "seed", "review_decision", "review_record", "canonical")},
                          "thinking_sha256": meta["thinking_sha256"], "final_sha256": meta["final_sha256"],
                          "thinking_tokens": tt, "total_tokens": whole})
    out = HERE / "dataset.jsonl"
    with open(out, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    order_sha = sha("\n".join(ids))
    checks = {k: sum(bool(x[k]) for x in integ) for k in ("reasoning_present", "final_present", "final_eq_target_p0", "final_eq_v006_string",
                                                        "deterministic_conversion", "auto_pass", "exec_equal_full", "signature_equal_full")}
    integrity = {"unique_ids": len(set(ids)), "records": len(records), "missing": len(set(ids) - set(src)), "duplicates": len(ids) - len(set(ids)),
                 "answer_only_records": sum("<think>" not in r["messages"][2]["content"] for r in records),
                 "checks": checks, "all_pass": all(v == 154 for v in checks.values()),
                 "failures": [x for x in integ if not all(x[k] for k in checks)],
                 "outcomes": dict(collections.Counter(str(x["outcome"]) for x in integ)), "items": integ}
    if not integrity["all_pass"] or integrity["answer_only_records"]:
        (HERE / "integrity.json").write_text(json.dumps(integrity, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        raise SystemExit("무결성 실패 — freeze 중단")
    names = ("vendor100", "valid98", "sel154", "aux_test_v1")
    kinds = ("question", "id", "template", "family")
    table = {n: {k: {"any": sum(any(h in (f"eval:{n}:{k}", f"eval:{n}:both_expanded_{k}") for h in x["hits"]) for x in contam),
                     "new": sum(any(h in (f"eval:{n}:{k}", f"eval:{n}:both_expanded_{k}") for h in x["new"]) for x in contam)}
                 for k in kinds} for n in names}
    prev = json.loads((ROOT / "evaluation/partial_grounding/sft_p0/v006_verification.json").read_text(encoding="utf-8"))
    prev_hits = {x["id"]: sorted(x["overlap"]) for x in prev["items"]}
    contamination = {"eval_sets": table, "protected_any": sum(any(h.startswith("protected:") for h in x["hits"]) for x in contam),
                     "items_with_new_hits": {x["id"]: x["new"] for x in contam if x["new"]},
                     "legacy_allowed_items": sum(bool(x["legacy_allowed"]) for x in contam),
                     "identical_to_v006_verification": all(sorted(x["hits"]) == prev_hits[x["id"]] for x in contam),
                     "note": "질문·최종 답이 v006과 같아 겹침은 v006 검사와 같아야 한다. v005의 template·family 겹침은 결정 15·54 허용분(legacy)",
                     "items": contam}
    by_src = collections.defaultdict(list)
    for x in lengths:
        by_src[x["source"]].append(x)
    group = {"hf8b": ("hf8b_r70", "hf8b_m2", "hf8b_m3"), "t27b": ("t27b_p12", "t27b_remaining"), "canonical": ("manual_canonical",)}
    length_doc = {"all": {k: dist([x[k] for x in lengths]) for k in ("prompt", "thinking", "final", "total")},
                  "by_group": {g: {k: dist([x[k] for x in lengths if x["source"] in members]) for k in ("thinking", "final", "total")}
                               for g, members in group.items()},
                  "by_source": {s: {k: dist([x[k] for x in v]) for k in ("thinking", "total")} for s, v in by_src.items()},
                  "max_total": max(x["total"] for x in lengths), "over_11392": [x["id"] for x in lengths if x["total"] + 1 > 11392],
                  "items": lengths}
    manifest = {"name": "reviewed_reasoning_v001", "records": 154, "dataset_sha256": sha(out.read_bytes()),
                "item_order_sha256": order_sha, "item_ids": ids,
                "composition": {"model_generated_approved": 148, "manual_canonical": 6},
                "by_reasoning_source": dict(collections.Counter(s["reasoning_source"] for s in src.values())),
                "by_question_source": dict(collections.Counter(r["metadata"]["source"] for r in v006)),
                "answer_only_records": 0, "final_answer": "frozen v006 P0 gold string(reviewed_gold_v006_p0)",
                "v006_sha256": sha((ROOT / "training/generated/reviewed_gold_v006_p0/sft_train.jsonl").read_bytes()),
                "prompt_sha256": v006[0]["metadata"]["prompt_sha256"], "token_lengths": {k: v for k, v in length_doc.items() if k != "items"},
                "items": man_items}
    for name, doc in (("manifest.json", manifest), ("integrity.json", integrity), ("contamination.json", contamination),
                      ("token_lengths.json", length_doc)):
        (HERE / name).write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"dataset_sha256": manifest["dataset_sha256"], "order": order_sha, "by_source": manifest["by_reasoning_source"],
                      "integrity": checks, "answer_only": integrity["answer_only_records"], "contam": table,
                      "new_hits": contamination["items_with_new_hits"], "same_as_v006": contamination["identical_to_v006_verification"],
                      "len": length_doc["all"], "by_group": length_doc["by_group"], "over_11392": length_doc["over_11392"]},
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
