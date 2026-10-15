# -*- coding: utf-8 -*-
"""C11: 학습 길이 최종(결정 125 F4). 모델 호출 없음.

    hfvenv/bin/python length_final.py   # -> length_final.json

- 입력: ``PROVISIONAL_L12288/lengths.json``(build6 ``--with-j6 --max-seq-length 12288``: J1·J6 정답 표본 전부와 pilot_004 판 teacher·8b 레코드),
  ``m1_result_v2.json``(M1·M1b 결론).
- 더해서 세션 3 teacher(표현 중립 지시) 길이 추정: T0 trace 160개(``training/generated/pilot_006/teacher_t0/traces.jsonl``)를 ``teacher6.to_arm_records``로
  두 arm 레코드로 만들어 build6과 같은 방법(학습 렌더링 입력 + 응답 + 1)으로 잰다. T0 지시는 수정 제안 대상이라(C5) 참고값이다.
"""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_006/teacher"))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/thinking_prep_001"))
LIMIT = 12288


def main():
    import hf_thinking as H
    import teacher6 as T6
    from transformers import AutoTokenizer
    from training.data.common import read_jsonl
    from training.trainer_common import render_prompt
    tok = AutoTokenizer.from_pretrained(H.MODEL, revision=H.REVISION)
    cfg = {"chat_template_kwargs": {"enable_thinking": True}}
    lengths = json.loads((HERE / "PROVISIONAL_L12288/lengths.json").read_text(encoding="utf-8"))
    m1 = json.loads((HERE / "m1_result_v2.json").read_text(encoding="utf-8"))
    canon = {}
    for r in read_jsonl(ROOT / "sft_dpo_inventory/pilot_006_prep/canonical/canonical_records.jsonl"):
        canon.setdefault(r["id"], r)
    t0 = {"full": [], "partial": []}
    missing = 0
    for t in read_jsonl(ROOT / "training/generated/pilot_006/teacher_t0/traces.jsonl"):
        c = canon.get(t["id"])
        if c is None:
            missing += 1
            continue
        for arm, rec in T6.to_arm_records(t, c["semantics"], c["question"], t["id"]).items():
            n_in = len(tok(render_prompt(tok, rec["messages"][:2], cfg), add_special_tokens=False)["input_ids"])
            n_out = len(tok(rec["messages"][2]["content"], add_special_tokens=False)["input_ids"]) + 1
            t0[arm].append({"trace_id": t["trace_id"], "input": n_in, "response": n_out, "tokens": n_in + n_out})

    def stats(v):
        v = sorted(v)
        return {"n": len(v), "p50": v[len(v) // 2], "p90": v[int(0.9 * (len(v) - 1))], "p99": v[int(0.99 * (len(v) - 1))], "max": v[-1],
                f"over_{LIMIT}": sum(x > LIMIT for x in v)} if v else None
    out = {"decision": "125(F4)", "L_req": lengths["L_req"], "L_req_argmax": lengths["argmax"],
           "m1_conclusion": m1["conclusion"], "m1_peak_mib": m1["peak_mib"], "limit_mib": 47104,
           "max_seq_length": m1["conclusion"].get("max_seq_length"),
           "candidates_by_arm_kind": lengths["by_arm_kind"],
           "provisional_build_records_over_limit": lengths["over_limit_build_candidates"],
           "provisional_build_questions_lost": lengths["questions_without_records_after_limit"],
           "t0_teacher_estimate": {arm: stats([x["tokens"] for x in v]) for arm, v in t0.items()},
           "t0_teacher_response_tokens": {arm: stats([x["response"] for x in v]) for arm, v in t0.items()},
           "t0_missing_questions": missing,
           "inputs": {p: hashlib.sha256((HERE / p).read_bytes()).hexdigest() for p in ("PROVISIONAL_L12288/lengths.json", "m1_result_v2.json")}}
    (HERE / "length_final.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("L_req", "m1_conclusion", "m1_peak_mib", "candidates_by_arm_kind", "t0_teacher_estimate", "t0_teacher_response_tokens",
                                          "t0_missing_questions")}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
