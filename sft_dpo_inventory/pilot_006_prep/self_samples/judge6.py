# -*- coding: utf-8 -*-
"""R1·H6: 8b 자체 표본을 **승인 gold**(R0 승인 corpus)로 판정한다. 모델 호출 없음. ``judge_self.py``(초안 기준, C2·C3)와 같은 판정 규칙의 새 파일.

    hfvenv/bin/python judge6.py --arm full|partial --raw RAW.jsonl [--raw RAW2.jsonl ...] --out OUT.json [--questions INPUT.jsonl]

- 판정: ``</think>`` 뒤 최종 JSON(``parse_planner_json``; Partial은 ``complete_grounding_payload`` 뒤)을 ``evaluate_vendor100.grounding_check``로
  승인 gold(``approved6.gold_payload``)와 비교. **조건 계층 전** 원응답 기준. 잘림·JSON 없음은 오답. 조건 계층 뒤 일치는 참고로만 센다.
- 질문 문구: 원문의 수집 입력 질문이 승인 corpus 질문과 다르면(질문 수정, R0) 그 표본은 ``invalid_old_question``으로 빼고 판정하지 않는다.
- 상태: ``approved``(승인 train), ``not_approved``(제외·보류·결정 119 제외 등 승인 corpus에 없음), ``holdout``(있으면 안 됨, 경고).
- 길이: 정답 표본마다 학습 렌더링 입력(arm system prompt + 질문) + 응답 + 1 token(build6과 같은 방법). ``over_12288`` 표시.
출력: 질문별 정답 trace id·수, 상태별 집계, 정답 없는 승인 질문(teacher·보강 대상), 12,288 초과 정답 표본.
"""
import argparse
import hashlib
import json
import statistics
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/thinking_prep_001"))
import approved6 as AP  # noqa: E402

LIMIT = 12288


def main():
    import evaluate_vendor100 as EV
    from geoflow import conditions
    from geoflow.errors import GeoFlowError
    from geoflow.planner import parse_planner_json
    from grounding.completion import complete_grounding_payload
    from training.data.thinking import split_response
    p = argparse.ArgumentParser()
    p.add_argument("--arm", choices=("full", "partial"), required=True)
    p.add_argument("--raw", action="append", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--questions", action="append", default=[], help="수집 입력(id·question). 없으면 원문의 question 필드")
    p.add_argument("--no-lengths", action="store_true")
    a = p.parse_args()
    corpus = AP.load(include_holdout=True)
    asked = {}
    for qf in a.questions or [str(ROOT / "sft_dpo_inventory/pilot_006_prep/gpu/inputs/self_questions.jsonl")]:
        for r in AP.read_jsonl(qf):
            asked[r["id"]] = r["question"]
    gold = {}
    tok = None
    if not a.no_lengths:
        import hf_thinking as H
        from transformers import AutoTokenizer
        from training.trainer_common import expected_system_prompt, render_prompt
        tok = AutoTokenizer.from_pretrained(H.MODEL, revision=H.REVISION)
        system = expected_system_prompt(a.arm)
        plen = {}

        def length(question, text):
            if question not in plen:
                plen[question] = len(tok(render_prompt(tok, [{"role": "system", "content": system}, {"role": "user", "content": question}],
                                                       {"chat_template_kwargs": {"enable_thinking": True}}), add_special_tokens=False)["input_ids"])
            return plen[question] + len(tok(text, add_special_tokens=False)["input_ids"]) + 1
    per = defaultdict(list)
    errors = Counter()
    raw_hashes = {}
    for raw in a.raw:
        raw_hashes[raw] = hashlib.sha256(Path(raw).read_bytes()).hexdigest()
        for line in Path(raw).read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            cid = AP.corpus_id(r["id"])
            rec = corpus.get(cid)
            q_used = r.get("question") or asked.get(r["id"])
            v = {"trace_id": r["trace_id"], "kind": r.get("kind"), "done_reason": r.get("done_reason"), "generated_tokens": r.get("generated_tokens"),
                 "raw_match": False, "after_condition_match": None, "parse": "ok", "error": None}
            if rec is None:
                v["status"] = "not_approved"
                per[cid].append(v)
                continue
            if q_used is not None and q_used != rec["question"]:
                v["status"] = "invalid_old_question"
                per[cid].append(v)
                continue
            v["status"] = "holdout" if rec["split"] == "holdout" else "approved"
            g = gold.setdefault(cid, AP.gold_payload(rec))
            try:
                if r.get("done_reason") == "length" or "</think>" not in r["raw_text"]:
                    raise ValueError("truncated_or_no_think_close")
                payload = parse_planner_json(split_response(r["raw_text"])[1])
                if a.arm == "partial":
                    payload = complete_grounding_payload(payload)
                same, diffs = EV.grounding_check({"gold_grounding": g, "gold": None}, payload)
                v["raw_match"] = bool(same)
                v["diffs"] = [d if isinstance(d, str) else d[0] for d in diffs][:6]
                if not same:
                    try:
                        fixed, _ = conditions.reconcile_payload(payload, rec["question"], reference_date=date(2026, 9, 25))
                        v["after_condition_match"] = bool(EV.grounding_check({"gold_grounding": g, "gold": None}, fixed)[0])
                    except GeoFlowError as error:
                        v["after_condition_match"] = False
                        v["error"] = getattr(error, "code", type(error).__name__)
            except Exception as error:  # noqa: BLE001
                v["parse"] = "fail"
                v["error"] = getattr(error, "code", None) or type(error).__name__
            if v["raw_match"] and tok is not None:
                v["tokens"] = length(rec["question"], r["raw_text"])
            if not v["raw_match"]:
                errors.update(v.get("diffs") or [v["error"] or "?"])
            per[cid].append(v)
    questions = []
    for cid, vs in sorted(per.items()):
        status = Counter(v["status"] for v in vs).most_common(1)[0][0]
        judged = [v for v in vs if v["status"] in ("approved", "holdout")]
        ok = [v for v in judged if v["raw_match"]]
        rec = corpus.get(cid)
        questions.append({"id": cid, "group": rec["corpus_group"] if rec else None, "status": status, "samples": len(vs), "judged": len(judged),
                          "correct": len(ok), "greedy_correct": any(v["raw_match"] for v in judged if v["kind"] == "greedy"),
                          "correct_after_condition_only": sum(bool(v["after_condition_match"]) for v in judged if not v["raw_match"]),
                          "truncated": sum(v["done_reason"] == "length" for v in judged), "parse_fail": sum(v["parse"] == "fail" for v in judged),
                          "median_generated_tokens": statistics.median([v["generated_tokens"] for v in vs if v["generated_tokens"] is not None] or [0]),
                          "correct_trace_ids": [v["trace_id"] for v in ok],
                          "correct_over_12288": [{"trace_id": v["trace_id"], "tokens": v["tokens"]} for v in ok if v.get("tokens", 0) > LIMIT],
                          "correct_max_tokens": max((v.get("tokens", 0) for v in ok), default=None)})
    by = defaultdict(Counter)
    for q in questions:
        key = f"{q['status']}:{q['group']}" if q["group"] else q["status"]
        s = by[key]
        s["questions"] += 1
        s["with_correct"] += q["correct"] > 0
        s["no_correct"] += q["judged"] > 0 and q["correct"] == 0
        s["correct_samples"] += q["correct"]
        s["samples"] += q["samples"]
    out = {"arm": a.arm, "raw": {str(Path(k).resolve().relative_to(ROOT)) if str(Path(k).resolve()).startswith(str(ROOT)) else k: v for k, v in raw_hashes.items()},
           "gold": "approved corpus R0 (pilot_006_prep/approved, render_full)", "criterion": "raw output before condition layer, grounding_check vs approved gold"
           + (" (Partial: completion first)" if a.arm == "partial" else ""),
           "approved_version": AP.VERSION, "approved_manifest_sha256": hashlib.sha256((AP.APPROVED / AP.MANIFEST[AP.VERSION]).read_bytes()).hexdigest(),
           "questions": len(questions), "samples": sum(q["samples"] for q in questions), "by_status_group": {k: dict(v) for k, v in sorted(by.items())},
           "no_correct_approved": [q["id"] for q in questions if q["status"] == "approved" and q["judged"] > 0 and q["correct"] == 0],
           "correct_over_12288": [{"id": q["id"], **x} for q in questions for x in q["correct_over_12288"]],
           "top_error_kinds": dict(errors.most_common(15)), "per_question": questions}
    Path(a.out).write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("arm", "questions", "samples", "by_status_group")}, ensure_ascii=False, indent=1),
          "no_correct_approved", len(out["no_correct_approved"]), "over_12288", len(out["correct_over_12288"]))


if __name__ == "__main__":
    main()
