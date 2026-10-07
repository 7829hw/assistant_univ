# -*- coding: utf-8 -*-
"""결정 47(batch005 검토 결과)을 thor workflow ``decide``로 기록한다. 모델을 부르지 않는다.

    python sft_dpo_inventory/pilot_prep_005/import/record_decisions.py

1. b005-59-hf(조건부): 결정 6의 운영 경로 재판정을 한다. 모델 응답 본문(``batch005/hf_outputs.json``의 원문)을 운영 경로
   (정규화, 조건 계층, compose, validate, 실행)에 넣어 gold와 비교한다. 함수는 v004 데이터의 재판정과 같은
   ``pilot_prep_003/data/build_v004_thinking.judge_rejected``다. ``kept_operational_wrong``이면 승인, 아니면 제외한다.
2. 문장 수정 2건(b005-12, 14): thor queue는 checksum으로 고정되어 질문을 그 자리에서 바꿀 수 없다(``load_queue``).
   그래서 batch004의 정지 queue와 같은 방식으로, 검토한 queue(``batch005/review``, 105행)에서 파생한 queue를 새로 만든다
   (``pilot_prep_005/import/reviewed_queue``).
   - 바꾸는 것: b005-12·12-hf·14·14-hf 네 행의 ``question``(결정 47의 문장), ``note``, ``derived_from``, candidate_hash.
   - 초안 gold와 모델 출력(rejected)은 그대로다. 12-hf·14-hf의 rejected는 고치기 전 문장으로 생성된 출력이라고 ``note``에 적는다.
   - 나머지 101행은 그대로 옮긴다. manifest는 원래 queue의 것(보호 기준·출처·prompt 같음)에 파생 관계와 hash만 새로 적는다.
3. 파생 queue의 105행 모두에 결정을 기록한다(``decisions_005.jsonl``). reviewer는 사용자(hwkim), 근거는
   "Claude 검토 의견을 사용자가 확인·승인(결정 47, 2026-10-08)".
   - gold 승인 58(수정 2 포함, 정지 target 8 포함), gold 제외 2(b005-43, 53).
   - 쌍 승인 35 + 조건부(59-hf) 판정, 쌍 제외 9(8개 + gold 제외에 따른 53-hf).
원래 queue(``batch005/review``)와 그 파일은 바꾸지 않는다.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_prep_003/data"))

from training.annotations.inventory import digest  # noqa: E402
from training.annotations.workflow import decide, load_queue  # noqa: E402
from training.data.common import sha256, write_jsonl  # noqa: E402

QUEUE_A = ROOT / "sft_dpo_inventory/batch005/review"
QUEUE_B = HERE / "reviewed_queue"
DECISIONS = HERE / "decisions_005.jsonl"
HF_OUTPUTS = ROOT / "sft_dpo_inventory/batch005/hf_outputs.json"
REVIEWER = "hwkim"
REASON = "Claude 검토 의견을 사용자가 확인·승인(결정 47, 2026-10-08)"
REWORDED = {
    "b005-12": "2026년 9월 5일 동성로 근처에서 시작하고 끝난 실차 구간은 몇 건이야?",
    "b005-14": "지난달 부산 광안리 근처에서만 오간 택시 실차는 몇 건이었나요?",
}
GOLD_NO = {"b005-43": "업체 100의 026 문장을 거의 그대로 따른 것으로 보여 뺀다(결정 36·47)",
           "b005-53": "업체 100의 025 문장을 거의 그대로 따른 것으로 보여 뺀다(결정 36·47)"}
PAIRS_OK = [f"b005-{n:02d}-hf" for n in (3, 5, 6, 8, 9, 11, 12, 14, 16, 17, 19, 20, 22, 23, 25, 27, 28, 29, 30, 31, 34, 37,
                                         39, 40, 41, 42, 45, 46, 47, 48, 49, 50, 53, 56, 57, 60)]
PAIRS_NO = {**{f"b005-{n:02d}-hf": "한 장소 both와 출발+도착 두 항목은 표기만 다르고 뜻이 같다(결정 47)" for n in (1, 2, 4, 32)},
            **{f"b005-{n:02d}-hf": "날짜 형식만 다르고 조건 계층이 고친다(결정 47·6)" for n in (35, 36, 43, 52)}}
CONDITIONAL = "b005-59-hf"


def rejudge_59(rows):
    from build_v004_thinking import judge_rejected  # sys.path에 pipeline_pilot_001·valid_eval을 넣는다
    import provider_eval as P
    import evaluate_vendor100 as EV
    from datetime import date
    EV.REFERENCE_DATE = date(2026, 9, 25)
    row = next(r for r in rows if r["candidate_id"] == CONDITIONAL)
    out = next(o for o in json.loads(HF_OUTPUTS.read_text(encoding="utf-8"))["rows"] if o["id"] == "b005-59")
    gold = row["proposed_grounding"]
    provider = P.provider_for(gold)[0]
    verdict = judge_rejected(out["raw_text"], row["question"], gold,
                             provider)
    return {"candidate_id": CONDITIONAL, "raw_sha256": out["raw_sha256"], **verdict}


def derived_queue(rows, manifest):
    picked = []
    for row in rows:
        base_id = row["candidate_id"].removesuffix("-hf")
        new = {k: v for k, v in row.items() if k != "candidate_hash"}
        if base_id in REWORDED:
            new["question"] = REWORDED[base_id]
            new["note"] = (f"결정 47(2026-10-08): 질문 문장만 고쳤다(gold는 그대로). 원래 문장: {row['question']}"
                           + (" / rejected는 고치기 전 문장으로 생성된 모델 출력이다." if row["candidate_id"].endswith("-hf") else ""))
            new["derived_from"] = {"queue": str(QUEUE_A.relative_to(ROOT)), "candidate_hash": row["candidate_hash"]}
            new["candidate_hash"] = digest(new)
        else:
            new = dict(row)
        picked.append(new)
    QUEUE_B.mkdir(exist_ok=False)
    write_jsonl(QUEUE_B / "review_queue.jsonl", picked)
    m = dict(manifest)
    m["batch"] = "batch005_reviewed"
    m["derived_from"] = {"queue": str(QUEUE_A.relative_to(ROOT)),
                         "queue_hash": manifest["output_hashes"]["review_queue.jsonl"],
                         "change": "decision 47: question text of b005-12/14 (and their -hf rows) reworded; proposals unchanged"}
    m["output_hashes"] = {"review_queue.jsonl": sha256(QUEUE_B / "review_queue.jsonl")}
    (QUEUE_B / "manifest.json").write_text(json.dumps(m, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return picked


def main():
    rows, manifest = load_queue(QUEUE_A)
    ids = [r["candidate_id"] for r in rows]
    gold_ids = [i for i in ids if not i.endswith("-hf")]
    pair_ids = [i for i in ids if i.endswith("-hf")]
    if len(gold_ids) != 60 or sorted(pair_ids) != sorted(PAIRS_OK + list(PAIRS_NO) + [CONDITIONAL]):
        raise SystemExit("queue 행이 결정 47의 목록과 다르다")
    if DECISIONS.exists() or QUEUE_B.exists():
        raise SystemExit("decisions 파일 또는 파생 queue가 이미 있다")
    v59 = rejudge_59(rows)
    (HERE / "rejudge_b005-59-hf.json").write_text(json.dumps(v59, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    accept_59 = v59["category"] == "kept_operational_wrong"
    picked = derived_queue(rows, manifest)
    load_queue(QUEUE_B)
    out = []
    for row in picked:
        cid = row["candidate_id"]
        base_id = cid.removesuffix("-hf")
        if base_id in GOLD_NO:
            out.append(decide(QUEUE_B, DECISIONS, cid, status="rejected", reviewer=REVIEWER,
                              reason=f"{REASON}: 제외. {GOLD_NO[base_id]}" + (" gold 제외에 따라 쌍도 뺀다" if cid.endswith("-hf") else "")))
        elif cid in PAIRS_NO:
            out.append(decide(QUEUE_B, DECISIONS, cid, status="rejected", reviewer=REVIEWER, reason=f"{REASON}: 쌍 제외. {PAIRS_NO[cid]}"))
        elif cid == CONDITIONAL:
            why = f"조건부 쌍. 결정 6 운영 경로 재판정 {v59['category']}:{v59['reason']}"
            if accept_59:
                out.append(decide(QUEUE_B, DECISIONS, cid, status="accepted", reviewer=REVIEWER, reason=f"{REASON}: {why} → 승인",
                                  semantic_checks=True, negative_wrong=True))
            else:
                out.append(decide(QUEUE_B, DECISIONS, cid, status="rejected", reviewer=REVIEWER, reason=f"{REASON}: {why} → 제외"))
        else:
            extra = ""
            if base_id in REWORDED:
                extra = ": 질문 문장 수정(gold 그대로)" + ("; rejected는 고치기 전 문장으로 생성된 출력" if cid.endswith("-hf") else "")
            out.append(decide(QUEUE_B, DECISIONS, cid, status="accepted", reviewer=REVIEWER, reason=REASON + extra,
                              semantic_checks=True, negative_wrong=cid.endswith("-hf")))
    counts = {"decisions": len(out),
              "gold_accepted": sum(d["status"] == "accepted" and not d["candidate_id"].endswith("-hf") for d in out),
              "gold_rejected": sum(d["status"] == "rejected" and not d["candidate_id"].endswith("-hf") for d in out),
              "pair_accepted": sum(d["status"] == "accepted" and d["candidate_id"].endswith("-hf") for d in out),
              "pair_rejected": sum(d["status"] == "rejected" and d["candidate_id"].endswith("-hf") for d in out),
              "b005-59-hf": {"category": v59["category"], "reason": v59["reason"], "accepted": accept_59}}
    (HERE / "decisions_summary.json").write_text(json.dumps(counts, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(counts, ensure_ascii=False))


if __name__ == "__main__":
    main()
