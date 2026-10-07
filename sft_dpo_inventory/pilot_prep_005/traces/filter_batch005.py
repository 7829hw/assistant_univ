# -*- coding: utf-8 -*-
"""batch005 thinking trace에 학습 필터를 적용하고 DPO 쌍을 재판정한다(작업 지시 3). 모델·GPU를 쓰지 않는다(tokenizer만 CPU).

    python sft_dpo_inventory/pilot_prep_005/traces/filter_batch005.py

입력: ``collect_traces.py``의 trace 원문(``training/generated/thinking_traces/batch005``, ignore 경로)과 요약·후보
(``traces/batch005/summary.json``·``candidates.json``), gold ``trace_inputs/batch005``(= v005의 batch005 58문항).
v004 데이터(``pilot_prep_003/data/build_v004_thinking.py``)와 같은 순서·같은 함수로 거른다. 학습 데이터는 만들지 않는다.

1. 정답 표본이 없는 질문: 후보가 없다. 목록을 남긴다(teacher 수집 대상).
2. 결정 4: 생성 token과 ``tokenizer(raw_text + eos)``가 다른 trace를 쓰는 SFT 후보·DPO 쌍을 뺀다.
3. 결정 40-D: 고정한 루프 기준(``pilot_prep_004/loop_filter``의 ``is_loop``: L1 끝부분 반복 ≥ 3, L2 압축률 ≤ 0.086,
   L3 같은 줄 반복 ≥ 21)에 걸리는 trace를 쓰는 SFT 후보·DPO 쌍을 뺀다(SFT target, chosen, rejected 어느 자리든).
4. 결정 18: SFT total(prompt + 생성 + 1) > 12,887, DPO 문장당 > 13,833이면 뺀다(자르지 않음).
5. 계약 필터: SFT target·DPO chosen의 응답 JSON이 ``target_ok``를 통과해야 한다(결정 14 정지 target은 같은 정지면 통과).
6. 결정 6: DPO rejected를 운영 경로(정규화, 조건 계층, compose, validate, 실행; provider는 결정 11)로 다시 판정해
   ``kept_operational_wrong``만 남긴다. b005-59의 trace 쌍도 같은 규칙이다.
   참고로 검토 시트의 승인 쌍 36개(HF 첫 응답)도 같은 함수로 다시 판정해 적는다(b005-59-hf는 import 때 판정과 같아야 한다).
출력(원문 없음): ``traces/batch005_filtered.json``(남은 후보 id, 단계별 수, 정답 표본 없는 질문), ``traces/batch005_rejudgment.json``.
"""
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_prep_003/data"))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_prep_004/loop_filter"))

from build_v004_thinking import CAP_DPO_PER_SEQUENCE, CAP_SFT_TOTAL, judge_rejected, tokenizer  # noqa: E402
from apply_filter import is_loop, loop_metrics, split_think  # noqa: E402

GEN = ROOT / "training/generated"
TRACES = GEN / "thinking_traces/batch005/traces.jsonl"
SUMMARY = HERE / "batch005"
CORPUS = GEN / "pilot_prep_005/trace_inputs/batch005/sft_train.jsonl"
HF_OUTPUTS = ROOT / "sft_dpo_inventory/batch005/hf_outputs.json"
DECISIONS = ROOT / "sft_dpo_inventory/pilot_prep_005/import/decisions_005.jsonl"


def read(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def main():
    import provider_eval as P
    from training.data import thinking
    from training.data.validation import assess, target_ok
    summary = json.loads((SUMMARY / "summary.json").read_text(encoding="utf-8"))
    if hashlib.sha256(TRACES.read_bytes()).hexdigest() != summary["summary"]["traces_sha256"]:
        raise SystemExit("trace 파일 hash가 요약과 다르다")
    cands = json.loads((SUMMARY / "candidates.json").read_text(encoding="utf-8"))
    traces = {r["trace_id"]: r for r in read(TRACES)}
    gold = {r["metadata"]["source_record_id"]: r for r in read(CORPUS)}
    tok = tokenizer()

    mismatched, loops, lengths, contract = set(), {}, {}, {}
    for tid, row in traces.items():
        lengths[tid] = row["prompt_tokens"] + row["generated_tokens"] + 1
        if row["done_reason"] == "stop" and row["think_closed"]:
            if tok(row["raw_text"] + tok.eos_token, add_special_tokens=False)["input_ids"] != row["generated_ids"]:
                mismatched.add(tid)
        m = loop_metrics(row.get("thinking") or split_think(row["raw_text"])[0])
        reasons = is_loop(m) if m else ["empty_thinking"]
        if reasons:
            loops[tid] = reasons
    no_correct = sorted(summary["summary"]["no_correct_sample"])

    def contract_ok(tid):
        if tid not in contract:
            row = traces[tid]
            record = gold[row["source_record_id"]]
            try:
                payload = thinking.response_json(row["raw_text"])
                contract[tid] = bool(target_ok(assess(payload, record["messages"][1]["content"]), record["metadata"]))
            except Exception:  # noqa: BLE001 - 응답 JSON을 읽을 수 없음
                contract[tid] = False
        return contract[tid]

    steps = {"sft": Counter(), "dpo": Counter()}
    sft_keep = []
    for c in cands["sft"]:
        tid = c["trace_id"]
        reason = ("no_correct_question" if c["source_record_id"] in no_correct else
                  "decision4_tokenization_mismatch" if tid in mismatched else
                  "decision40D_loop" if tid in loops else
                  "decision18_over_length" if lengths[tid] > CAP_SFT_TOTAL else
                  "contract_target_ok_failed" if not contract_ok(tid) else None)
        steps["sft"][reason or "kept"] += 1
        if reason is None:
            sft_keep.append(c)
    judged, dpo_keep, rejudge_rows = {}, [], []
    for c in cands["dpo"]:
        ch, rj = c["chosen"], c["rejected"]
        reason = ("no_correct_question" if c["source_record_id"] in no_correct else
                  "decision4_tokenization_mismatch" if ch in mismatched or rj in mismatched else
                  "decision40D_loop" if ch in loops or rj in loops else
                  "decision18_over_length" if max(lengths[ch], lengths[rj]) - 1 > CAP_DPO_PER_SEQUENCE else
                  "contract_chosen_failed" if not contract_ok(ch) else None)
        if reason:
            steps["dpo"][reason] += 1
            continue
        record = gold[c["source_record_id"]]
        g = json.loads(record["messages"][2]["content"])
        if rj not in judged:
            judged[rj] = judge_rejected(traces[rj]["raw_text"], record["messages"][1]["content"], g, P.provider_for(g)[0])
        v = judged[rj]
        steps["dpo"]["decision6_" + v["category"]] += 1
        rejudge_rows.append({"chosen": ch, "rejected": rj, "source_record_id": c["source_record_id"],
                             **{k: v.get(k) for k in ("provider", "category", "reason", "outcome", "error_code",
                                                      "repair_request_kinds", "final_grounding_diffs")}})
        if v["category"] == "kept_operational_wrong":
            dpo_keep.append({**c, "operational_rejudgment": {k: v.get(k) for k in ("provider", "reason", "outcome", "error_code")}})

    # 참고: 검토 시트에서 승인한 HF 첫 응답 쌍 36개의 결정 6 재판정.
    accepted_pairs = {d["candidate_id"] for d in read(DECISIONS) if d["status"] == "accepted" and d["candidate_id"].endswith("-hf")}
    hf = {o["id"]: o for o in json.loads(HF_OUTPUTS.read_text(encoding="utf-8"))["rows"]}
    reviewed = {}
    for cid in sorted(accepted_pairs):
        sid = cid.removesuffix("-hf")
        record = gold[sid]
        g = json.loads(record["messages"][2]["content"])
        # 12·14의 출력은 고치기 전 문장으로 생성됐다. 재판정은 고친 문장(학습 레코드의 질문)으로 한다.
        v = judge_rejected(hf[sid]["raw_text"], record["messages"][1]["content"], g, P.provider_for(g)[0])
        reviewed[cid] = {k: v.get(k) for k in ("category", "reason", "outcome", "error_code")}
    per_question = Counter(c["source_record_id"] for c in sft_keep)
    dpo_q = Counter(c["source_record_id"] for c in dpo_keep)
    out = {
        "traces": str(TRACES.relative_to(ROOT)), "traces_sha256": summary["summary"]["traces_sha256"],
        "questions": summary["summary"]["questions"], "greedy_correct": summary["summary"]["greedy_correct"],
        "pass_at_8": summary["summary"]["pass_at_8"], "truncated_generations": summary["summary"]["truncated_generations"],
        "no_correct_sample_questions": no_correct,
        "no_kept_sft_after_filters": sorted(set(gold) - set(per_question) - set(no_correct)),
        "tokenization_mismatch": sorted(mismatched),
        "loop_flagged": loops,
        "length_caps": {"sft_total": CAP_SFT_TOTAL, "dpo_per_sequence": CAP_DPO_PER_SEQUENCE},
        "candidates_before": {"sft": len(cands["sft"]), "dpo": len(cands["dpo"])},
        "filter_steps": {k: dict(v) for k, v in steps.items()},
        "kept": {"sft": len(sft_keep), "sft_questions": len(per_question), "dpo": len(dpo_keep), "dpo_questions": len(dpo_q)},
        "sft_per_question": dict(sorted(per_question.items())), "dpo_per_question": dict(sorted(dpo_q.items())),
        "dpo_rejudgment": {"pairs_judged": len(rejudge_rows), "unique_rejected": len(judged),
                           "by_reason": dict(Counter(f"{r['category']}:{r['reason']}" for r in rejudge_rows)),
                           "by_provider": dict(Counter(r["provider"] for r in rejudge_rows)),
                           "b005-59_pairs": dict(Counter(r["category"] for r in rejudge_rows if r["source_record_id"] == "b005-59"))},
        "reviewed_hf_pairs_rejudgment(reference)": {"pairs": len(reviewed),
                                                    "by_category": dict(Counter(v["category"] for v in reviewed.values())),
                                                    "rows": reviewed},
        "sft_kept_trace_ids": [c["trace_id"] for c in sft_keep],
        "dpo_kept_pairs": [{"chosen": c["chosen"], "rejected": c["rejected"]} for c in dpo_keep],
    }
    (HERE / "batch005_rejudgment.json").write_text(json.dumps(rejudge_rows, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (HERE / "batch005_filtered.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("questions", "greedy_correct", "pass_at_8", "truncated_generations",
                                          "no_correct_sample_questions", "no_kept_sft_after_filters", "filter_steps", "kept",
                                          "dpo_rejudgment")}, ensure_ascii=False, indent=1))
    print(json.dumps(out["reviewed_hf_pairs_rejudgment(reference)"]["by_category"], ensure_ascii=False))


if __name__ == "__main__":
    main()
