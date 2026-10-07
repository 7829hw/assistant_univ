# -*- coding: utf-8 -*-
"""결정 40-A: teacher trace 17문항을 pilot_002 학습 데이터에 넣을 때의 규모를 센다. 데이터를 만들지 않는다. 모델·GPU를 쓰지 않는다.

    CUDA_VISIBLE_DEVICES= HF_HOME=... HF_HUB_OFFLINE=1 python sft_dpo_inventory/pilot_prep_004/teacher_scale/count_teacher.py

- 입력(고치지 않는다): teacher trace(``training/generated/thinking_traces/teacher_qwen3.8_27b/{known7,batch004,v003_valid}``),
  gold ``reviewed_gold_v004_t2pc``, HF base trace ``pilot_prep_003/combined_traces.jsonl``(같은 질문의 prompt token 수와 DPO rejected 후보).
- 변환: ``training.data.thinking.normalize_trace``(``<think>\\n{thinking}\\n</think>\\n\\n{content}``, ``source=teacher``).
- 적용(v004·r1과 같은 순서):
  1. 정답 표본: teacher 판정 ``raw_match``(조건 계층 전 원응답, HF trace와 같은 judge). 같은 응답(raw_sha256)은 하나로 센다.
  2. tokenize 일치(결정 4의 대응): teacher는 생성 token id가 없으므로 결정 4의 비교(생성 id 대 재tokenize)를 그대로 할 수 없다. 대신
     (a) 재tokenize 왕복(decode(tokenize(응답+EOS)) == 응답+EOS, 다시 tokenize하면 같은 id), (b) 학습 렌더링의 token 경계 검사
     (``trainer_common.render_records``: SFT ``json_only``, DPO ``full_response``)를 통과해야 한다.
  3. 계약 필터: ``build_thinking``과 같은 ``target_ok(assess(응답 JSON, 질문), gold metadata)``.
  4. 길이(결정 18): SFT total = prompt token + 응답 token(EOS 포함) + 1 ≤ 12,887, DPO 문장당 ≤ 13,833.
  5. 결정 27의 기준: 결정 23 방식의 사람 검토에서 "우연히 정답"으로 판정된 trace를 뺀다. teacher trace는 아직 검토하지 않았으므로
     빠지는 수는 0이고, 검토 대기로 표시한다.
  6. 결정 40-D: 루프 기준(``../loop_filter/CRITERIA.md``). ``../loop_filter/applied.json``의 판정을 쓴다.
- DPO(참고): teacher 정답(chosen) × 같은 질문의 HF base 오답(rejected, 응답 JSON 파싱 가능, 결정 6의 운영 경로 재판정에서 틀린 것).
  chosen과 rejected의 모델이 다르므로(27b 대 8b) DPO에 넣을지는 사람이 정한다. 가능한 쌍 수만 센다.
- 결과: ``teacher_scale.json``(원문 없음).
"""
import hashlib
import json
import os
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pipeline_pilot_001"))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_prep_002/valid_eval"))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/thinking_prep_001"))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_prep_003/data"))

GEN = ROOT / "training/generated"
TEACHER = GEN / "thinking_traces/teacher_qwen3.8_27b"
CORPUS = GEN / "reviewed_gold_v004_t2pc/sft_train.jsonl"
COMBINED = GEN / "pilot_prep_003/combined_traces.jsonl"
CAP_SFT_TOTAL, CAP_DPO_PER_SEQUENCE = 12887, 13833
CONFIG = {"chat_template_kwargs": {"enable_thinking": True},
          "training": {"max_seq_length": 20000, "max_length": 20000, "max_prompt_length": 20000,
                       "max_completion_length": 20000}}


def read(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def main():
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    from transformers import AutoTokenizer
    import hf_thinking as H
    from build_v004_thinking import judge_rejected
    import provider_eval as P
    from training.data import thinking
    from training.data.validation import assess, target_ok
    from training.trainer_common import render_records
    tok = AutoTokenizer.from_pretrained(H.MODEL, revision=H.REVISION)
    gold = {r["metadata"]["source_record_id"]: r for r in read(CORPUS)}
    hf = read(COMBINED)
    prompt_tokens = {r["source_record_id"]: r["prompt_tokens"] for r in hf}
    loops = json.loads((HERE.parent / "loop_filter/applied.json").read_text(encoding="utf-8"))["flagged"]
    rows, steps, per_q = [], Counter(), {}
    teacher_files = sorted(TEACHER.glob("*/traces.jsonl"))
    for path in teacher_files:
        for raw in read(path):
            trace = thinking.normalize_trace(raw)
            sid = trace["source_record_id"]
            q = per_q.setdefault(sid, {"group": path.parent.name, "samples": 0, "correct": 0, "unique_correct": 0,
                                       "kept_sft": 0, "_seen": set()})
            q["samples"] += 1
            if not trace["verdict"]["raw_match"]:
                continue
            q["correct"] += 1
            if trace["raw_sha256"] in q["_seen"]:
                steps["duplicate_response"] += 1
                continue
            q["_seen"].add(trace["raw_sha256"])
            q["unique_correct"] += 1
            record = thinking.sft_record(trace, gold[sid], source=str(path.relative_to(ROOT)))
            ids = tok(trace["raw_text"] + tok.eos_token, add_special_tokens=False)["input_ids"]
            roundtrip = tok.decode(ids) == trace["raw_text"] + tok.eos_token and \
                tok(tok.decode(ids), add_special_tokens=False)["input_ids"] == ids
            boundary = {}
            for scope in ("json_only", "full_response"):
                try:
                    render_records(tok, [record], {**CONFIG, "thinking": {"loss_scope": scope}}, "sft")
                    boundary[scope] = True
                except ValueError as error:
                    boundary[scope] = str(error)[:120]
            contract = target_ok(assess(thinking.response_json(trace["raw_text"]), gold[sid]["messages"][1]["content"]),
                                 gold[sid]["metadata"])
            total = prompt_tokens[sid] + len(ids) + 1
            row = {"trace_id": trace["trace_id"], "source_record_id": sid, "group": q["group"],
                   "response_tokens": len(ids), "sft_total_tokens": total, "tokenize_roundtrip": roundtrip,
                   "render_boundary": boundary, "contract_ok": bool(contract), "loop": trace["trace_id"] in loops,
                   "decision27_review": "검토 대기(결정 23 방식 표본 검토 전)"}
            if not roundtrip or boundary["json_only"] is not True:
                row["excluded"] = "tokenize"
            elif not contract:
                row["excluded"] = "contract"
            elif total > CAP_SFT_TOTAL:
                row["excluded"] = "length"
            elif row["loop"]:
                row["excluded"] = "loop"
            else:
                row["excluded"] = None
                q["kept_sft"] += 1
            steps[f"sft:{row['excluded'] or 'kept'}"] += 1
            rows.append(row)
    # DPO(참고): teacher 정답 × HF 오답
    kept = [r for r in rows if r["excluded"] is None]
    wrong = {}
    for r in hf:
        if r["source_record_id"] in per_q and not r["verdict"]["raw_match"] and r["verdict"]["parse"] == "ok":
            wrong.setdefault(r["source_record_id"], {})[r["raw_sha256"]] = r
    judged, dpo = {}, Counter()
    for sid, rejected in wrong.items():
        record = gold[sid]
        g = json.loads(record["messages"][2]["content"])
        provider = P.provider_for(g)[0]
        n_chosen = sum(1 for r in kept if r["source_record_id"] == sid)
        for rej in rejected.values():
            if rej["prompt_tokens"] + rej["generated_tokens"] > CAP_DPO_PER_SEQUENCE:
                dpo["rejected_over_length"] += n_chosen
                continue
            v = judge_rejected(rej["raw_text"], record["messages"][1]["content"], g, provider)
            judged[rej["trace_id"]] = v["category"]
            dpo[f"decision6_{v['category']}"] += n_chosen
    chosen_max = {sid: max((r["response_tokens"] for r in kept if r["source_record_id"] == sid), default=0) for sid in per_q}
    over = sum(1 for r in kept if prompt_tokens[r["source_record_id"]] + r["response_tokens"] > CAP_DPO_PER_SEQUENCE)
    for q in per_q.values():
        q.pop("_seen")
    out = {
        "inputs": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in teacher_files},
        "questions": len(per_q), "teacher_traces": sum(q["samples"] for q in per_q.values()),
        "correct": sum(q["correct"] for q in per_q.values()),
        "unique_correct": sum(q["unique_correct"] for q in per_q.values()),
        "sft_steps": dict(steps), "sft_kept": len(kept),
        "sft_kept_questions": sum(1 for q in per_q.values() if q["kept_sft"]),
        "per_question": per_q,
        "sft_kept_tokens": {"response_max": max(r["response_tokens"] for r in kept),
                            "sft_total_max": max(r["sft_total_tokens"] for r in kept)},
        "dpo_reference": {"possible_pairs_by_rejected_judgment": dict(dpo),
                          "possible_pairs_kept_operational_wrong": dpo.get("decision6_kept_operational_wrong", 0),
                          "chosen_over_dpo_cap": over, "unique_rejected_judged": len(judged),
                          "note": "chosen(27b)과 rejected(8b)의 모델이 다르다. DPO에 넣을지는 사람이 정한다."},
        "decision27": "teacher trace는 결정 23 방식 검토 전이라 0개 제외. 검토하면 같은 기준(채점 필드의 추론 오류 = 우연히 정답)으로 뺀다.",
        "rows": rows,
    }
    (HERE / "teacher_scale.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k not in ("rows", "per_question")}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
