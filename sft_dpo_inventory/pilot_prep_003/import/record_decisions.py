# -*- coding: utf-8 -*-
"""결정 13(batch004 검토 결과)·14(지원 불가 target 형식)를 thor workflow ``decide``로 기록하고, 정지 후보 4건의 새 queue를 만든다.

    python sft_dpo_inventory/pilot_prep_003/import/record_decisions.py

1. queue A(``sft_dpo_inventory/batch004/review``, 사용자가 검토한 33행)에 33개 결정을 기록한다
   → ``pilot_prep_003/import/decisions_004.jsonl``. thor ``decide``는 queue 폴더 안의 다른 이름 파일을 거부하므로
   README의 경로(queue 폴더 안) 대신 여기에 둔다. queue는 바꾸지 않는다.
   - 후보 gold 승인 18: accepted, ``--semantic-checks-confirmed``.
   - 쌍 승인 11: accepted, ``--semantic-checks-confirmed --negative-is-wrong``.
   - 쌍 제외 4(b004-24/31/40/41-hf): rejected.
   - reviewer는 사용자(hwkim). 근거: "Claude 검토 의견을 사용자가 확인·승인"(결정 13).
   - queue A의 정지 후보 8행(b004-34/35/40/41과 그 쌍)은 ``unsupported_target_format_undecided``로 막혀 import에서 빠진다.
2. 결정 14로 형식이 정해졌으므로, README의 절차대로 정지 후보 8행만 담은 queue B를 새로 만든다
   (``pilot_prep_003/import/stop_queue``). queue A 행에서 바꾸는 것은 다음뿐이다(candidate_hash는 다시 계산).
   - ``expected_outcome``: ``stop_pending_format_decision`` → ``t2pc_stop_grounding``(결정 14).
   - ``eligibility``: 형식 미정 blocker 제거. ``note``: 결정 14.
   - 초안 grounding·질문·rejected는 그대로다.
   manifest는 queue A의 것을 쓰고(보호 기준·출처·prompt 같음), queue 파일 hash와 파생 관계만 새로 적는다.
   queue B에도 같은 사용자 결정을 기록한다(근거에 결정 13·14).
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))

from training.annotations.inventory import digest  # noqa: E402
from training.annotations.workflow import decide, load_queue  # noqa: E402
from training.data.common import sha256, write_jsonl  # noqa: E402

QUEUE_A = ROOT / "sft_dpo_inventory/batch004/review"
DECISIONS_A = HERE / "decisions_004.jsonl"
QUEUE_B = HERE / "stop_queue"
DECISIONS_B = HERE / "stop_queue_decisions.jsonl"
REVIEWER = "hwkim"
GOLD = ["b004-05", "b004-06", "b004-15", "b004-18", "b004-19", "b004-20", "b004-21", "b004-22", "b004-23", "b004-24",
        "b004-27", "b004-28", "b004-30", "b004-31", "b004-34", "b004-35", "b004-40", "b004-41"]
PAIRS_OK = ["b004-05-hf", "b004-06-hf", "b004-15-hf", "b004-19-hf", "b004-22-hf", "b004-23-hf", "b004-27-hf",
            "b004-28-hf", "b004-30-hf", "b004-34-hf", "b004-35-hf"]
PAIRS_NO = ["b004-24-hf", "b004-31-hf", "b004-40-hf", "b004-41-hf"]
STOP = {"b004-34", "b004-35", "b004-40", "b004-41"}
REASON = "Claude 검토 의견을 사용자가 확인·승인(결정 13, 2026-10-06)"
REASON_PAIR_NO = "Claude 검토 의견을 사용자가 확인·승인: 쌍 제외. 날짜만 다르고 조건 계층이 고친다(결정 13·6, 2026-10-06)"


def record(queue, decisions, ids, extra_reason=""):
    out = []
    for cid in ids:
        if cid in PAIRS_NO:
            out.append(decide(queue, decisions, cid, status="rejected", reviewer=REVIEWER,
                              reason=REASON_PAIR_NO + extra_reason))
        else:
            out.append(decide(queue, decisions, cid, status="accepted", reviewer=REVIEWER, reason=REASON + extra_reason,
                              semantic_checks=True, negative_wrong=cid.endswith("-hf")))
    return out


def stop_queue(rows, manifest):
    picked = []
    for row in rows:
        base_id = row["candidate_id"].removesuffix("-hf")
        if base_id not in STOP:
            continue
        new = {k: v for k, v in row.items() if k != "candidate_hash"}
        new["expected_outcome"] = "t2pc_stop_grounding"
        blockers = [b for b in row["eligibility"]["training_blockers"] if b != "unsupported_target_format_undecided"]
        new["eligibility"] = {"eligible_after_human_review": not blockers, "training_blockers": blockers}
        new["note"] = ("결정 14(2026-10-06): 지원 불가 질문의 학습 target은 T2PC식 정지 grounding이다. 측정값과 조건을 "
                       "grounding으로 적고 코드가 멈춘다.")
        new["derived_from"] = {"queue": str(QUEUE_A.relative_to(ROOT)), "candidate_hash": row["candidate_hash"]}
        new["candidate_hash"] = digest(new)
        picked.append(new)
    QUEUE_B.mkdir(exist_ok=False)
    write_jsonl(QUEUE_B / "review_queue.jsonl", picked)
    m = dict(manifest)
    m["batch"] = "batch004_stop_t2pc"
    m["derived_from"] = {"queue": str(QUEUE_A.relative_to(ROOT)),
                         "queue_hash": manifest["output_hashes"]["review_queue.jsonl"],
                         "change": "expected_outcome and blocker per decision 14; proposals unchanged"}
    m["counts"] = {"queue_rows": len(picked), "sft_gold": sum(r["record_type"] == "sft_gold" for r in picked),
                   "dpo_pair": sum(r["record_type"] == "dpo_pair" for r in picked)}
    m["output_hashes"] = {"review_queue.jsonl": sha256(QUEUE_B / "review_queue.jsonl")}
    (QUEUE_B / "manifest.json").write_text(json.dumps(m, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return picked


def main():
    rows, manifest = load_queue(QUEUE_A)
    ids = [r["candidate_id"] for r in rows]
    if sorted(ids) != sorted(GOLD + PAIRS_OK + PAIRS_NO) or DECISIONS_A.exists():
        raise SystemExit("queue A 행이 결정 13의 목록과 다르거나 decisions 파일이 이미 있다")
    a = record(QUEUE_A, DECISIONS_A, ids)
    picked = stop_queue(rows, manifest)
    load_queue(QUEUE_B)
    b = record(QUEUE_B, DECISIONS_B, [r["candidate_id"] for r in picked], extra_reason="; 형식은 결정 14")
    print(json.dumps({"queue_A": {"decisions": len(a), "accepted": sum(d["status"] == "accepted" for d in a),
                                  "rejected": sum(d["status"] == "rejected" for d in a)},
                      "queue_B": {"rows": len(picked), "decisions": len(b),
                                  "accepted": sum(d["status"] == "accepted" for d in b),
                                  "rejected": sum(d["status"] == "rejected" for d in b)}}, ensure_ascii=False))


if __name__ == "__main__":
    main()
