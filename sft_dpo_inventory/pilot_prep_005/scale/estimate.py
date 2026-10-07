# -*- coding: utf-8 -*-
"""pilot_002 데이터의 예상 규모(작업 지시 5). 데이터를 만들지 않고 이미 정한 필터 결과만 센다. 모델을 부르지 않는다.

    python sft_dpo_inventory/pilot_prep_005/scale/estimate.py

구성 요소(모두 이미 거른 것):
- r1: pilot_001에 쓴 v004 thinking 데이터(``thinking_v004_t2pc_r1``: 결정 4·6·18·계약 필터·결정 27 적용, 루프 0).
- batch005 HF: ``traces/batch005_filtered.json``(결정 4·40-D·18·계약·6 적용).
- teacher 17: ``teacher/selected_teacher.json``(질문당 4개, 결정 48). 표본 검토(결정 27 방식) 전이므로 그 결과로 줄 수 있다.
- batch005 teacher(포함 여부 미정): ``teacher/batch005_no_correct/summary.json``의 정답 표본 수(필터 전).
경우: (A) teacher 미포함 = r1 + batch005 HF, (B) teacher 포함 = A + teacher 17, (참고) B + batch005 teacher 정답 표본(상한 4 가정).
유형 분포: ``pilot_prep_004/type_target``의 정의(집계 × dimension × dimension_target)로 질문 단위·레코드 단위를 세고,
개발 셋 454질문(집계 통계)과의 총변동거리(TV)를 적는다.
"""
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
P5 = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_prep_004/type_target"))

from type_target import profile, tv  # noqa: E402

GEN = ROOT / "training/generated"
GOLD = GEN / "reviewed_gold_v005_t2pc/sft_train.jsonl"
R1 = GEN / "thinking_v004_t2pc_r1"
DEV = json.loads((ROOT / "sft_dpo_inventory/pilot_prep_004/type_target/type_target.json").read_text(encoding="utf-8"))["dev_distribution"]


def read(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def describe(sft_sids, dpo_sids, sources, gold):
    """sft_sids/dpo_sids: 레코드마다 질문 id 목록. sources: 레코드마다 출처."""
    stop = {sid for sid, r in gold.items() if r["metadata"].get("target_kind") == "t2pc_stop_grounding"}
    prof = {sid: profile(json.loads(r["messages"][-1]["content"]), sid not in stop) for sid, r in gold.items()}
    qs = sorted(set(sft_sids))
    q_cells = Counter(prof[s]["cell"] for s in qs)
    r_cells = Counter(prof[s]["cell"] for s in sft_sids)
    q_share = {k: round(v / len(qs), 4) for k, v in sorted(q_cells.items())}
    r_share = {k: round(v / len(sft_sids), 4) for k, v in sorted(r_cells.items())}
    return {"sft_records": len(sft_sids), "sft_questions": len(qs), "dpo_pairs": len(dpo_sids),
            "dpo_questions": len(set(dpo_sids)),
            "sft_by_source": {k: {"records": v, "share": round(v / len(sft_sids), 3)} for k, v in Counter(sources).items()},
            "question_cells": q_share, "record_cells": r_share,
            "tv_vs_dev": {"question": tv(q_share, DEV["share"]), "record": tv(r_share, DEV["share"])},
            "stop_target_records": sum(s in stop for s in sft_sids)}


def main():
    gold = {r["metadata"]["source_record_id"]: r for r in read(GOLD)}
    r1_sft = [r["metadata"]["source_record_id"] for r in read(R1 / "sft_train.jsonl")]
    r1_dpo = [r["metadata"]["source_record_id"] for r in read(R1 / "dpo_train.jsonl")]
    f = json.loads((P5 / "traces/batch005_filtered.json").read_text(encoding="utf-8"))
    b5_sft = [t.split(":")[0] for t in f["sft_kept_trace_ids"]]
    b5_dpo = [p["chosen"].split(":")[0] for p in f["dpo_kept_pairs"]]
    sel = json.loads((P5 / "teacher/selected_teacher.json").read_text(encoding="utf-8"))
    t_sft = [sid for sid, ids in sel["selected_trace_ids"].items() for _ in ids]
    bt_path = P5 / "teacher/batch005_no_correct/summary.json"
    bt = json.loads(bt_path.read_text(encoding="utf-8")) if bt_path.exists() else {"questions": []}
    bt_sft = [q["source_record_id"] for q in bt["questions"] for _ in range(min(4, q["correct_samples_of_8"]))]
    cases = {
        "A_teacher_excluded": (r1_sft + b5_sft, r1_dpo + b5_dpo, ["r1(v004 HF)"] * len(r1_sft) + ["batch005 HF"] * len(b5_sft)),
        "B_teacher17_included": (r1_sft + b5_sft + t_sft, r1_dpo + b5_dpo,
                                 ["r1(v004 HF)"] * len(r1_sft) + ["batch005 HF"] * len(b5_sft) + ["teacher17"] * len(t_sft)),
        "B_plus_batch005_teacher(reference, cap 4, before filters)": (
            r1_sft + b5_sft + t_sft + bt_sft, r1_dpo + b5_dpo,
            ["r1(v004 HF)"] * len(r1_sft) + ["batch005 HF"] * len(b5_sft) + ["teacher17"] * len(t_sft)
            + ["batch005 teacher"] * len(bt_sft)),
    }
    out = {"dev_distribution": DEV["share"],
           "inputs": {"r1": {"sft": len(r1_sft), "dpo": len(r1_dpo), "questions": len(set(r1_sft))},
                      "batch005_hf": {"sft": len(b5_sft), "dpo": len(b5_dpo), "questions": len(set(b5_sft))},
                      "teacher17": {"sft": len(t_sft), "questions": len(set(t_sft))},
                      "batch005_teacher": {"sft_cap4_before_filters": len(bt_sft), "questions": len(set(bt_sft))}},
           "gold_questions_without_any_record": {
               name: sorted(set(gold) - set(sft)) for name, (sft, _, _) in cases.items()},
           "cases": {name: describe(sft, dpo, src, gold) for name, (sft, dpo, src) in cases.items()}}
    (HERE / "estimate.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k != "gold_questions_without_any_record"}, ensure_ascii=False, indent=1))
    print({k: len(v) for k, v in out["gold_questions_without_any_record"].items()})


if __name__ == "__main__":
    main()
