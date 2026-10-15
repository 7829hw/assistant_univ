# -*- coding: utf-8 -*-
"""C2·C3: 8b 자체 표본(J1 Full, J6 Partial) 판정. 모델 호출 없음, 필터·import 없음(판정과 목록만).

    hfvenv/bin/python sft_dpo_inventory/pilot_006_prep/self_samples/judge_self.py --arm full|partial

판정 기준(PLAN_DRAFT 3절 "조건 계층 전 원응답 vs canonical"):
- 원응답의 ``</think>`` 뒤 최종 JSON을 ``parse_planner_json``으로 읽는다(Partial arm은 ``grounding.completion.complete_grounding_payload``로 구조 필드를 채운 뒤).
- 정답 = ``evaluate_vendor100.grounding_check``(측정값·장소·od_role·scope·factor·집계 IR, 기본값 정규화)로 gold와 같음. **조건 계층 전** 출력 기준이다.
  참고로 조건 계층(``conditions.reconcile_payload``, 기준일 2026-09-25) 뒤 일치도 따로 센다(학습 필터에는 쓰지 않음).
- gold: 문항 목록(``gpu/inputs/self_questions.jsonl``)의 ``gold_grounding``. 출처별 상태:
  - pg 수용(결정 121) → ``approved_pg``, pg EDIT_REQUIRED 7 → ``held_edit_required``.
  - aug300 train(결정 119로 train 207) → ``draft``(초안 기준, 승인 뒤 다시 판정), 결정 119로 제외된 13 → ``excluded_e4``.
  - batch007 → ``draft``.
- 잘림(done_reason length)·JSON 없음은 오답으로 센다.
출력: ``j1_judgement.json``(full) 또는 ``j6_judgement.json``(partial).
"""
import argparse
import json
import statistics
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))


def main():
    import evaluate_vendor100 as EV
    from geoflow import conditions
    from geoflow.errors import GeoFlowError
    from geoflow.planner import parse_planner_json
    from grounding.completion import complete_grounding_payload
    from training.data.thinking import split_response
    p = argparse.ArgumentParser()
    p.add_argument("--arm", choices=("full", "partial"), required=True)
    a = p.parse_args()
    raw = ROOT / ("training/generated/pilot_006/self_full/raw/self_full_raw.jsonl" if a.arm == "full"
                  else "training/generated/pilot_006/self_partial/raw/self_partial_raw.jsonl")
    items = {json.loads(l)["id"]: json.loads(l) for l in (ROOT / "sft_dpo_inventory/pilot_006_prep/gpu/inputs/self_questions.jsonl").read_text(encoding="utf-8").splitlines()}
    e4 = {r["id"]: r["status_e4"] for r in json.loads((ROOT / "sft_dpo_inventory/pilot_006_prep/aug300/status_e4.json").read_text(encoding="utf-8"))["items"]}
    held = set(json.loads((ROOT / "sft_dpo_inventory/pg_imports/acceptance_e6.json").read_text(encoding="utf-8"))["pg_batch006_edit_required(held)"])

    def gold_status(i):
        it = items[i]
        if it["source"] == "pg_reviewed_reasoning_v001":
            sid = i[len("pg-rr-"):]
            name = f"pg-{sid}" if sid.startswith("b006-") else sid
            return "held_edit_required" if name in held else "approved_pg"
        if it["source"] == "aug300_train":
            return "draft" if e4.get(i) == "train" else "excluded_e4"
        return "draft"

    per = defaultdict(list)
    errors = Counter()
    for line in raw.read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        it = items[r["id"]]
        verdict = {"trace_id": r["trace_id"], "kind": r["kind"], "done_reason": r["done_reason"], "generated_tokens": r["generated_tokens"],
                   "raw_match": False, "after_condition_match": None, "parse": "ok", "error": None}
        payload = None
        try:
            if r["done_reason"] == "length" or "</think>" not in r["raw_text"]:
                raise ValueError("truncated_or_no_think_close")
            payload = parse_planner_json(split_response(r["raw_text"])[1])
            if a.arm == "partial":
                payload = complete_grounding_payload(payload)
            same, diffs = EV.grounding_check({"gold_grounding": it["gold_grounding"], "gold": None}, payload)
            verdict["raw_match"] = bool(same)
            verdict["diffs"] = [d if isinstance(d, str) else d[0] for d in diffs][:6]
            if not same:
                try:
                    fixed, _ = conditions.reconcile_payload(payload, it["question"], reference_date=date(2026, 9, 25))
                    verdict["after_condition_match"] = bool(EV.grounding_check({"gold_grounding": it["gold_grounding"], "gold": None}, fixed)[0])
                except GeoFlowError as error:
                    verdict["after_condition_match"] = False
                    verdict["error"] = getattr(error, "code", type(error).__name__)
        except Exception as error:  # noqa: BLE001 - JSON 없음·계약 밖
            verdict["parse"] = "fail"
            verdict["error"] = getattr(error, "code", None) or type(error).__name__
        if not verdict["raw_match"]:
            errors.update(verdict.get("diffs") or [verdict["error"] or "?"])
        per[r["id"]].append(verdict)
    questions = []
    for i, vs in per.items():
        questions.append({"id": i, "source": items[i]["source"], "gold_status": gold_status(i), "gold_kind": items[i]["gold_kind"],
                          "samples": len(vs), "correct": sum(v["raw_match"] for v in vs),
                          "greedy_correct": any(v["raw_match"] for v in vs if v["kind"] == "greedy"),
                          "correct_after_condition_only": sum(bool(v["after_condition_match"]) for v in vs if not v["raw_match"]),
                          "truncated": sum(v["done_reason"] == "length" for v in vs), "parse_fail": sum(v["parse"] == "fail" for v in vs),
                          "median_generated_tokens": statistics.median(v["generated_tokens"] for v in vs),
                          "correct_trace_ids": [v["trace_id"] for v in vs if v["raw_match"]]})
    questions.sort(key=lambda q: q["id"])
    by_status = defaultdict(Counter)
    for q in questions:
        s = by_status[q["gold_status"]]
        s["questions"] += 1
        s["with_correct"] += q["correct"] > 0
        s["no_correct"] += q["correct"] == 0
        s["greedy_correct"] += q["greedy_correct"]
        s["correct_samples"] += q["correct"]
    out = {"arm": a.arm, "raw": str(raw.relative_to(ROOT)), "criterion": "raw output before condition layer, grounding_check vs gold"
           + (" (Partial: completion first)" if a.arm == "partial" else ""),
           "questions": len(questions), "samples": sum(q["samples"] for q in questions),
           "by_gold_status": {k: dict(v) for k, v in by_status.items()},
           "no_correct_questions(teacher priority)": [q["id"] for q in questions if q["correct"] == 0 and q["gold_status"] in ("approved_pg", "draft")],
           "top_error_kinds": dict(errors.most_common(15)), "per_question": questions,
           "note": "draft 기준 판정은 승인 뒤 다시 한다. 필터·import는 세션 3 데이터 빌드에서."}
    name = "j1_judgement.json" if a.arm == "full" else "j6_judgement.json"
    (HERE / name).write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("arm", "questions", "samples", "by_gold_status", "top_error_kinds")}, ensure_ascii=False, indent=1),
          len(out["no_correct_questions(teacher priority)"]))


if __name__ == "__main__":
    main()
