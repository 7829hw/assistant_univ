# -*- coding: utf-8 -*-
"""진짜 pilot의 thinking 학습 데이터(v004)를 만든다. 모델·GPU를 쓰지 않는다(tokenizer만 CPU로 쓴다).

    python sft_dpo_inventory/pilot_prep_003/data/build_v004_thinking.py

입력(고치지 않는다):
- trace 세 묶음(같은 설정: greedy 1 + 표본 8, seed = 20261006 + 묶음 안 순번, max_new_tokens 8192)
  - ``v003_train``: thinking_prep_001(v003_t2pc train 19문항).
  - ``batch004``: pilot_prep_003(batch004 승인 gold 18문항).
  - ``v003_valid``: pilot_prep_003(v003_t2pc valid였던 16문항, 결정 16·16-1로 학습).
- gold: ``reviewed_gold_v004_t2pc``(53문항, 전부 train).

적용:
1. 결정 4: 생성 token과 decode 원문을 다시 tokenize한 결과가 다른 trace를 쓰는 SFT 후보·DPO 쌍을 뺀다. 세 묶음 모두 같은
   방법(``generated_ids`` 대 ``tokenizer(raw_text + eos)``)으로 다시 계산하고, v003_train은 thinking_prep_001 기록(10개)과 같은지 확인한다.
2. 결정 8·21: 정답 표본이 없는 질문은 후보가 없으므로 빠진다. 목록을 갱신해 남긴다(teacher 대상).
3. 결정 6: DPO rejected마다 응답 본문을 운영 경로(정규화, 조건 계층, compose, validate, 실행)에 넣어 gold와 비교한다.
   provider는 결정 11(장소가 reference로만 풀리면 reference, 그 밖에는 mock). 장소 조회 재질의는 grounding으로 판정하고,
   그 밖의 재질의(계약)는 운영 경로에서도 틀린 것으로 남긴다(pipeline_pilot_001과 같은 규칙).
4. 결정 7: ``compile_stop`` 표시는 거르지 않는다. mock·reference 모두 장소를 모르는 batch004 문항은 metadata에 표시한다.
5. 결정 18: 길이 한도는 pilot_prep_002 추정 안전 한도(보수 A: SFT total 12,887, DPO 문장당 13,833)를 넘지 않는다.
   레코드 길이 = prompt token + 생성 token(EOS 포함) + 1(trainer guard). 한도를 넘는 SFT 후보·DPO 쌍은 자르지 않고 빼서 센다.
6. 계약 필터: ``build_thinking.build``가 ``target_ok``로 다시 거른다(결정 14 정지 target은 같은 정지면 통과).
출력: ``training/generated/thinking_v004_t2pc``(ignored)와 ``data/``(요약, 거른 후보, 재판정, 길이; 원문 없음).
"""
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pipeline_pilot_001"))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_prep_002/valid_eval"))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/thinking_prep_001"))

GEN = ROOT / "training/generated"
SETS = {
    "v003_train": (GEN / "thinking_traces/v003_t2pc_train/traces.jsonl",
                   ROOT / "sft_dpo_inventory/thinking_prep_001/traces"),
    "batch004": (GEN / "thinking_traces/batch004/traces.jsonl", ROOT / "sft_dpo_inventory/pilot_prep_003/traces/batch004"),
    "v003_valid": (GEN / "thinking_traces/v003_t2pc_valid/traces.jsonl",
                   ROOT / "sft_dpo_inventory/pilot_prep_003/traces/v003_valid"),
}
CORPUS = GEN / "reviewed_gold_v004_t2pc"
PREP_TOKENIZATION = ROOT / "sft_dpo_inventory/thinking_prep_001/traces/tokenization_check.json"
CAP_SFT_TOTAL = 12887
CAP_DPO_PER_SEQUENCE = 13833
OUT = GEN / "thinking_v004_t2pc"
COMBINED = GEN / "pilot_prep_003/combined_traces.jsonl"


def tokenizer():
    import os
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    from transformers import AutoTokenizer
    import hf_thinking as H
    return AutoTokenizer.from_pretrained(H.MODEL, revision=H.REVISION)


def judge_rejected(raw_text, question, gold, provider):
    import build_pilot_data as B
    import evaluate_vendor100 as EV
    import provider_eval as P
    client = B.ReplayClient(raw_text)
    try:
        observed = EV.run_item(P.make_pipeline(client, provider), question)
    except Exception as error:  # noqa: BLE001
        observed = EV._crashed(error)
    kinds = sorted({"place_lookup" if r.startswith(B.PLACE_REPAIR_PREFIX) else "other_repair" for r in client.requests})
    out = {"provider": provider, "repair_request_kinds": kinds, "outcome": observed["outcome"],
           "error_code": observed["error_code"], "condition_corrections": observed.get("condition_corrections") or []}
    if "other_repair" in kinds:
        return {**out, "category": "kept_operational_wrong", "reason": "first_response_needs_contract_repair"}
    if observed["error_code"] == "UNHANDLED_EXCEPTION":
        return {**out, "category": "dropped_other", "reason": "unhandled_exception"}
    same, diffs = EV.grounding_check({"gold_grounding": gold, "gold": None}, observed["grounding"])
    out["final_grounding_diffs"] = json.loads(json.dumps(diffs, ensure_ascii=False))
    if not same:
        return {**out, "category": "kept_operational_wrong",
                "reason": "final_grounding_differs" if observed["grounding"] else "no_final_grounding"}
    if out["condition_corrections"]:
        return {**out, "category": "dropped_condition_layer_fixed", "reason": "equal_to_gold_after_condition_layer"}
    return {**out, "category": "dropped_other", "reason": "equal_to_gold_without_condition_correction"}


def main():
    import provider_eval as P
    from training.data import build_thinking
    from training.data.common import read_jsonl
    if OUT.exists() or COMBINED.exists():
        raise SystemExit("output already exists")
    tok = tokenizer()
    gold = {r["metadata"]["source_record_id"]: r for r in read_jsonl(CORPUS / "sft_train.jsonl")}
    traces, sft_c, dpo_c, summaries, set_of = {}, [], [], {}, {}
    for name, (trace_path, summary_dir) in SETS.items():
        rows = read_jsonl(trace_path)
        summary = json.loads((summary_dir / "summary.json").read_text(encoding="utf-8"))
        if hashlib.sha256(trace_path.read_bytes()).hexdigest() != summary["summary"]["traces_sha256"]:
            raise SystemExit(f"trace file hash differs from its summary: {name}")
        summaries[name] = summary["summary"]
        for row in rows:
            if row["trace_id"] in traces:
                raise SystemExit(f"duplicate trace id {row['trace_id']}")
            traces[row["trace_id"]] = row
            set_of[row["trace_id"]] = name
        cands = json.loads((summary_dir / "candidates.json").read_text(encoding="utf-8"))
        for c in cands["sft"]:
            sft_c.append({**c, "trace_set": name})
        for c in cands["dpo"]:
            dpo_c.append({**c, "trace_set": name})

    # 1. tokenization(결정 4)
    mismatched = set()
    for tid, row in traces.items():
        if row["done_reason"] != "stop" or not row["think_closed"]:
            continue
        if tok(row["raw_text"] + tok.eos_token, add_special_tokens=False)["input_ids"] != row["generated_ids"]:
            mismatched.add(tid)
    prep = {m["trace_id"] for m in json.loads(PREP_TOKENIZATION.read_text(encoding="utf-8"))["mismatches"]}
    if {t for t in mismatched if set_of[t] == "v003_train"} != prep:
        raise SystemExit("v003_train tokenization mismatches differ from thinking_prep_001 record")

    # 2. 정답 표본 없는 질문
    no_correct = sorted({sid for s in summaries.values() for sid in s["no_correct_sample"]})
    lengths = {tid: row["prompt_tokens"] + row["generated_tokens"] + 1 for tid, row in traces.items()}
    place_class = {sid: P.provider_for(json.loads(r["messages"][2]["content"]))[1] for sid, r in gold.items()}

    steps = {"sft": Counter(), "dpo": Counter()}
    sft_keep = []
    for c in sft_c:
        if c["source_record_id"] in no_correct:
            steps["sft"]["no_correct_question"] += 1
        elif c["trace_id"] in mismatched:
            steps["sft"]["decision4_tokenization_mismatch"] += 1
        elif lengths[c["trace_id"]] > CAP_SFT_TOTAL:
            steps["sft"]["decision18_over_length"] += 1
        else:
            sft_keep.append({**c, "place_unresolvable_both": place_class[c["source_record_id"]] == "neither"
                             and c["trace_set"] == "batch004"})
    judged, dpo_keep, rejudge_rows = {}, [], []
    for c in dpo_c:
        if c["source_record_id"] in no_correct:
            steps["dpo"]["no_correct_question"] += 1
            continue
        if c["chosen"] in mismatched or c["rejected"] in mismatched:
            steps["dpo"]["decision4_tokenization_mismatch"] += 1
            continue
        if max(lengths[c["chosen"]], lengths[c["rejected"]]) - 1 > CAP_DPO_PER_SEQUENCE:
            steps["dpo"]["decision18_over_length"] += 1
            continue
        record = gold[c["source_record_id"]]
        g = json.loads(record["messages"][2]["content"])
        provider = P.provider_for(g)[0]
        if c["rejected"] not in judged:
            judged[c["rejected"]] = judge_rejected(traces[c["rejected"]]["raw_text"], record["messages"][1]["content"],
                                                   g, provider)
        v = judged[c["rejected"]]
        steps["dpo"]["decision6_" + v["category"]] += 1
        rejudge_rows.append({"chosen": c["chosen"], "rejected": c["rejected"], "source_record_id": c["source_record_id"],
                             "trace_set": c["trace_set"], **{k: v.get(k) for k in (
                                 "provider", "category", "reason", "outcome", "error_code", "repair_request_kinds",
                                 "final_grounding_diffs")}})
        if v["category"] == "kept_operational_wrong":
            dpo_keep.append({**c, "operational_rejudgment": {k: v.get(k) for k in ("provider", "reason", "outcome",
                                                                                   "error_code")},
                             "place_unresolvable_both": place_class[c["source_record_id"]] == "neither"
                             and c["trace_set"] == "batch004"})

    HERE.mkdir(exist_ok=True)
    COMBINED.parent.mkdir(parents=True, exist_ok=True)
    with open(COMBINED, "w", encoding="utf-8") as stream:
        for name, (trace_path, _) in SETS.items():
            stream.write(trace_path.read_text(encoding="utf-8"))
    filtered = HERE / "candidates_v004.json"
    filtered.write_text(json.dumps({"sft": sft_keep, "dpo": dpo_keep}, ensure_ascii=False, indent=1) + "\n",
                        encoding="utf-8")
    built = build_thinking.build(COMBINED, filtered, CORPUS, "train", OUT)
    # place 표시를 레코드 metadata에 남긴다(빌더가 후보 dict의 이 키를 옮기지 않으므로 여기서 대조만 한다).
    sft_rows = read_jsonl(OUT / "sft_train.jsonl")
    dpo_rows = read_jsonl(OUT / "dpo_train.jsonl")
    batch_of = {sid: ("batch004" if sid.startswith("b004-") else
                      "v003_valid" if sid in {r["metadata"]["source_record_id"] for r in read_jsonl(
                          GEN / "reviewed_gold_v003_t2pc/sft_valid.jsonl")} else "v003_train") for sid in gold}
    summary = {
        "inputs": {name: {"traces": str(p.relative_to(ROOT)), "traces_sha256": summaries[name]["traces_sha256"],
                          "questions": summaries[name]["questions"], "pass_at_8": summaries[name]["pass_at_8"],
                          "greedy_correct": summaries[name]["greedy_correct"]} for name, (p, _) in SETS.items()},
        "corpus": str(CORPUS.relative_to(ROOT)),
        "tokenization_mismatch": {"total": len(mismatched), "by_set": dict(Counter(set_of[t] for t in mismatched)),
                                  "trace_ids": sorted(mismatched)},
        "no_correct_sample_questions": no_correct,
        "length_caps": {"sft_total": CAP_SFT_TOTAL, "dpo_per_sequence": CAP_DPO_PER_SEQUENCE,
                        "source": "pilot_prep_002/memory/length_estimate.json (A, conservative)"},
        "candidates_before": {"sft": len(sft_c), "dpo": len(dpo_c)},
        "filter_steps": {k: dict(v) for k, v in steps.items()},
        "dpo_rejudgment": {"pairs_judged": len(rejudge_rows), "unique_rejected": len(judged),
                           "by_category": dict(Counter(r["category"] for r in rejudge_rows)),
                           "by_reason": dict(Counter(f"{r['category']}:{r['reason']}" for r in rejudge_rows)),
                           "by_provider": dict(Counter(r["provider"] for r in rejudge_rows))},
        "build": built,
        "final": {
            "sft": len(sft_rows), "dpo": len(dpo_rows),
            "sft_questions": len({r["metadata"]["source_record_id"] for r in sft_rows}),
            "dpo_questions": len({r["metadata"]["source_record_id"] for r in dpo_rows}),
            "sft_by_origin": dict(Counter(batch_of[r["metadata"]["source_record_id"]] for r in sft_rows)),
            "dpo_by_origin": dict(Counter(batch_of[r["metadata"]["source_record_id"]] for r in dpo_rows)),
            "sft_by_category": dict(Counter(r["metadata"].get("category") or (r["metadata"].get("tags") or ["v003"])[0]
                                            for r in sft_rows)),
            "dpo_negative_category": dict(Counter(r["metadata"]["negative_category"] for r in dpo_rows)),
            "stop_targets(decision 14)": sum(r["metadata"].get("target_kind") == "t2pc_stop_grounding" for r in sft_rows),
            "place_unresolvable_both(batch004)": sorted({c["source_record_id"] for c in sft_keep + dpo_keep
                                                          if c["place_unresolvable_both"]}),
            "flags": dict(Counter(json.dumps(f, ensure_ascii=False)[:80] for r in sft_rows
                                  for f in (r["metadata"].get("v003_flags") or []))),
            "dpo_flags": dict(Counter(json.dumps(f, ensure_ascii=False)[:80] for r in dpo_rows
                                      for v in (r["metadata"].get("v003_flags") or {}).values() for f in v)),
        },
        "output": str(OUT.relative_to(ROOT)),
        "output_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(OUT.iterdir())},
    }
    (HERE / "rejudgment.json").write_text(json.dumps(rejudge_rows, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (HERE / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("tokenization_mismatch", "no_correct_sample_questions", "filter_steps",
                                              "dpo_rejudgment", "final")}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
