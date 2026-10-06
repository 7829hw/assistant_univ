# -*- coding: utf-8 -*-
"""thinking_prep_001의 thinking 후보에 결정 4·6·7·8(DECISIONS.md)을 적용한 pilot 데이터를 만든다. CPU만 쓴다.

    python sft_dpo_inventory/pipeline_pilot_001/build_pilot_data.py \
        --output training/generated/thinking_v003_t2pc_pilot

- 결정 4: ``thinking_prep_001/traces/tokenization_check.json``의 불일치 trace 10개를 쓰는 SFT 후보와 DPO 쌍을 뺀다.
- 결정 8: 정답 표본이 하나도 없는 7문항(``traces/summary.json``의 no_correct_sample)을 뺀다.
- 결정 7: ``compile_stop`` 표시는 거르지 않는다(표시는 metadata에 남는다).
- 결정 6: DPO rejected 표본마다 응답 본문을 HF-E와 같은 운영 경로(정규화, 조건 계층, compose, validate,
  mock·legacy 실행)에 넣어 최종 grounding을 gold와 비교한다. 모델은 부르지 않는다.
  - 운영 경로가 두 번째 모델 호출을 요청하면 기록된 응답이 없으므로 그 호출은 실패한다. 요청 종류로 나눈다.
    - 장소 조회 재질의(mock provider가 합성 장소명 나래구·솔빛시 등을 모름): grounding은 이미 정규화·조건 계층·
      검증을 지난 뒤이므로, 기록된 grounding을 gold와 비교한다.
    - 그 밖의 재질의(계약·검증 오류): 운영 경로에서 첫 응답이 실패하므로 gold와 다른 것으로 보고 남긴다.
  - 분류: kept_operational_wrong(최종 grounding이 gold와 다르거나 grounding이 없음) /
    dropped_condition_layer_fixed(gold와 같고 조건 계층이 값을 바꿈) / dropped_other(그 밖의 이유).
- 거른 후보 목록을 만든 뒤 ``training.data.build_thinking.build``로 SFT·DPO를 만든다(계약 판정 제외는 거기서 한 번 더).
- 입력(trace 원문, thinking_prep_001 생성물)은 고치지 않는다. 출력은 ignore 경로(training/generated)이고,
  요약과 거른 후보 목록(원문 없음)은 ``data/``에 둔다.
"""
import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

PREP = ROOT / "sft_dpo_inventory/thinking_prep_001"
TRACES = ROOT / "training/generated/thinking_traces/v003_t2pc_train/traces.jsonl"
CORPUS = ROOT / "training/generated/reviewed_gold_v003_t2pc"
REFERENCE_DATE = date(2026, 9, 25)


class ReplayRepairRequested(Exception):
    """운영 경로가 두 번째 모델 호출(재질의)을 요청했다. 기록된 응답은 첫 응답뿐이다."""


class ReplayClient:
    """기록된 thinking 응답 하나를 돌려주는 client. 두 번째 호출은 재질의이므로 멈춘다."""

    model = "replay"

    def __init__(self, raw_text):
        from training.data import thinking
        reasoning, answer = thinking.split_response(raw_text)
        self.reasoning, self.answer, self.calls, self.requests = reasoning, answer, 0, []

    def chat(self, messages, tools=None, **kwargs):
        self.calls += 1
        if self.calls > 1:
            self.requests.append((messages[-1].get("content") or "").split("\n", 1)[0])
            raise ReplayRepairRequested("replay has no repair response")
        return {"message": {"content": self.answer, "thinking": self.reasoning}, "done_reason": "stop"}


PLACE_REPAIR_PREFIX = "방금 고른 장소로 조회했으나"


def operational_judgment(raw_text, question, gold):
    import evaluate_vendor100 as EV
    from geoflow import providers
    from geoflow.pipeline import GeoFlowPipeline
    EV.REFERENCE_DATE = REFERENCE_DATE
    client = ReplayClient(raw_text)
    pipeline = GeoFlowPipeline.create(
        client=client, tool_executor=EV._executor(), aggregation_grounding="flat", clock=lambda: REFERENCE_DATE,
        condition_check=True, condition_notes=False,
        execution_profile=providers.profile_for(providers.MOCK, providers.LEGACY))
    try:
        observed = EV.run_item(pipeline, question)
    except Exception as error:  # noqa: BLE001 - evaluate_vendor100 llm과 같은 처리
        observed = EV._crashed(error)
    kinds = sorted({"place_lookup" if r.startswith(PLACE_REPAIR_PREFIX) else "other_repair" for r in client.requests})
    item = {"gold_grounding": gold, "gold": None}
    out = {"model_calls_requested": client.calls, "repair_request_kinds": kinds,
           "outcome": observed["outcome"], "error_code": observed["error_code"],
           "condition_corrections": observed.get("condition_corrections") or []}
    if "other_repair" in kinds:
        out.update(category="kept_operational_wrong", reason="first_response_needs_contract_repair",
                   repair_requests=client.requests)
        return out
    if observed["error_code"] == "UNHANDLED_EXCEPTION":
        out.update(category="dropped_other", reason="unhandled_exception",
                   exception=observed["planner_trace"].get("exception"))
        return out
    same, diffs = EV.grounding_check(item, observed["grounding"])
    out["final_grounding_diffs"] = json.loads(json.dumps(diffs, ensure_ascii=False))
    if not same:
        out.update(category="kept_operational_wrong",
                   reason="final_grounding_differs" if observed["grounding"] else "no_final_grounding")
    elif out["condition_corrections"]:
        out.update(category="dropped_condition_layer_fixed", reason="equal_to_gold_after_condition_layer")
    else:
        out.update(category="dropped_other", reason="equal_to_gold_without_condition_correction")
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=str(ROOT / "training/generated/thinking_v003_t2pc_pilot"))
    args = parser.parse_args()
    from training.data import build_thinking
    from training.data.common import read_jsonl

    output = Path(args.output)
    if output.exists():
        raise SystemExit(f"Output already exists: {output}")
    traces = {row["trace_id"]: row for row in read_jsonl(TRACES)}
    candidates = json.loads((PREP / "traces/candidates.json").read_text(encoding="utf-8"))
    mismatched = {m["trace_id"] for m in json.loads((PREP / "traces/tokenization_check.json").read_text(
        encoding="utf-8"))["mismatches"]}
    no_correct = set(json.loads((PREP / "traces/summary.json").read_text(encoding="utf-8"))["summary"]["no_correct_sample"])
    gold = {r["metadata"]["source_record_id"]: r for r in read_jsonl(CORPUS / "sft_train.jsonl")}

    steps = {"sft": Counter(), "dpo": Counter()}
    sft = []
    for cand in candidates["sft"]:
        if cand["source_record_id"] in no_correct:
            steps["sft"]["decision8_no_correct_question"] += 1
        elif cand["trace_id"] in mismatched:
            steps["sft"]["decision4_tokenization_mismatch"] += 1
        else:
            sft.append(cand)
    judged, dpo, rejudge_rows = {}, [], []
    for cand in candidates["dpo"]:
        if cand["source_record_id"] in no_correct:
            steps["dpo"]["decision8_no_correct_question"] += 1
            continue
        if cand["chosen"] in mismatched or cand["rejected"] in mismatched:
            steps["dpo"]["decision4_tokenization_mismatch"] += 1
            continue
        record = gold[cand["source_record_id"]]
        if cand["rejected"] not in judged:
            judged[cand["rejected"]] = operational_judgment(
                traces[cand["rejected"]]["raw_text"], record["messages"][1]["content"],
                json.loads(record["messages"][2]["content"]))
        verdict = judged[cand["rejected"]]
        steps["dpo"]["decision6_" + verdict["category"]] += 1
        rejudge_rows.append({"chosen": cand["chosen"], "rejected": cand["rejected"],
                             "source_record_id": cand["source_record_id"],
                             "prep_rejected_correct_after_condition_layer": cand["rejected_correct_after_condition_layer"],
                             **{k: verdict[k] for k in ("category", "reason", "outcome", "error_code", "repair_request_kinds")},
                             "final_grounding_diffs": verdict.get("final_grounding_diffs")})
        if verdict["category"] == "kept_operational_wrong":
            dpo.append({**cand, "operational_rejudgment": {k: verdict[k] for k in ("reason", "outcome", "error_code", "repair_request_kinds")}})

    data_dir = HERE / "data"
    data_dir.mkdir(exist_ok=True)
    filtered = data_dir / "candidates_pilot.json"
    filtered.write_text(json.dumps({"sft": sft, "dpo": dpo}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    built = build_thinking.build(TRACES, filtered, CORPUS, "train", output)

    agreement = Counter((r["prep_rejected_correct_after_condition_layer"], r["category"]) for r in rejudge_rows)
    summary = {
        "inputs": {"traces": str(TRACES.relative_to(ROOT)),
                   "traces_sha256": hashlib.sha256(TRACES.read_bytes()).hexdigest(),
                   "candidates": "sft_dpo_inventory/thinking_prep_001/traces/candidates.json",
                   "corpus": str(CORPUS.relative_to(ROOT)), "split": "train",
                   "reference_date": REFERENCE_DATE.isoformat()},
        "decisions_applied": ["4 tokenization mismatch traces excluded", "6 DPO operational re-judgment",
                              "7 compile_stop kept", "8 no-correct questions excluded"],
        "candidates_before": {"sft": len(candidates["sft"]), "dpo": len(candidates["dpo"])},
        "filter_steps": {k: dict(v) for k, v in steps.items()},
        "candidates_after_filters": {"sft": len(sft), "dpo": len(dpo)},
        "dpo_rejudgment": {
            "pairs_judged": len(rejudge_rows), "unique_rejected_traces": len(judged),
            "pairs_by_category": dict(Counter(r["category"] for r in rejudge_rows)),
            "pairs_by_reason": dict(Counter(f"{r['category']}:{r['reason']}" for r in rejudge_rows)),
            "pairs_by_outcome": dict(Counter(f"{r['category']}:{r['outcome']}:{r['error_code']}" for r in rejudge_rows)),
            "prep_condition_flag_vs_operational": {f"prep_fixed={k[0]}->{k[1]}": v for k, v in sorted(
                agreement.items(), key=str)}},
        "build": built,
        "output": str(output.relative_to(ROOT)) if ROOT in output.resolve().parents else str(output),
        "manifest_sha256": hashlib.sha256((output / "manifest.json").read_bytes()).hexdigest(),
    }
    (data_dir / "rejudgment.json").write_text(json.dumps(rejudge_rows, ensure_ascii=False, indent=1) + "\n",
                                              encoding="utf-8")
    (data_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("filter_steps", "candidates_after_filters", "build")}, ensure_ascii=False))
    print(json.dumps(summary["dpo_rejudgment"], ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
