# -*- coding: utf-8 -*-
"""결정 80(V, batch006 검토 결과)을 thor workflow ``decide``로 기록한다. 모델을 부르지 않는다.

    python sft_dpo_inventory/pilot_003/import/record_decisions.py

- 대상 queue: ``batch006/review``(52행, 바꾸지 않는다). 문장 수정이 없어 파생 queue를 만들지 않는다.
- gold: 승인 24(b006-05 – 28), 제외 4(b006-01 – 04, 결정 47과 같은 판단: 문장 틀이 b005-53과 같음).
- 쌍(24개): 결정 6의 운영 경로 재판정을 모든 쌍에 한다. 함수는 v004·batch005와 같은
  ``pilot_prep_003/data/build_v004_thinking.judge_rejected``(모델 응답 원문을 정규화·조건 계층·compose·validate·실행에 넣어 gold와 비교).
  원문은 ignore 경로 ``training/generated/batch006/raw/hf_outputs_raw.jsonl``에서 읽고 sha256을 queue 기록과 대조한다.
  - 제외: b006-01-hf(gold 제외), 날짜 표기만 다른 b006-22·23·24-hf, 그리고 재판정에서 ``kept_operational_wrong``이 아닌 쌍
    (결정 80: "결정 6의 운영 경로 재판정에서 초안과 같아진다고 표시된 쌍").
  - 승인: 나머지. b006-08-hf는 장소 표기 차이와 함께 ``sum``이 붙어 있어 승인한다(재판정에서 운영 경로 오답이어야 한다).
- reviewer는 사용자(hwkim), 근거는 "Claude 검토 의견을 사용자가 확인·승인(결정 80, 2026-10-13)".
- 출력: ``decisions_006.jsonl``, ``rejudge_pairs.json``, ``decisions_summary.json``.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_prep_003/data"))

from training.annotations.workflow import decide, load_queue  # noqa: E402

QUEUE = ROOT / "sft_dpo_inventory/batch006/review"
RAW = ROOT / "training/generated/batch006/raw/hf_outputs_raw.jsonl"
DECISIONS = HERE / "decisions_006.jsonl"
REVIEWER = "hwkim"
REASON = "Claude 검토 의견을 사용자가 확인·승인(결정 80, 2026-10-13)"
GOLD_NO = {f"b006-{n:02d}": "i1 묶음: 문장 틀이 batch005에서 뺀 b005-53(업체 100의 025를 거의 그대로 따름)과 같아 뺀다(결정 47·80)"
           for n in (1, 2, 3, 4)}
DATE_ONLY = {f"b006-{n:02d}-hf" for n in (22, 23, 24)}


def rejudge(rows):
    from build_v004_thinking import judge_rejected
    import evaluate_vendor100 as EV
    import provider_eval as P
    from datetime import date
    EV.REFERENCE_DATE = date(2026, 9, 25)
    raw = {}
    for line in RAW.read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        raw[r["id"]] = r
    out = {}
    for row in rows:
        if not row["candidate_id"].endswith("-hf"):
            continue
        base = row["candidate_id"].removesuffix("-hf")
        rec = raw[base]
        if rec["raw_sha256"] != row["model_output"]["raw_sha256"]:
            raise SystemExit(f"raw sha256 differs from queue: {base}")
        gold = row["proposed_grounding"]
        provider = P.provider_for(gold)[0]
        out[row["candidate_id"]] = {"raw_sha256": rec["raw_sha256"],
                                    "queue_condition_layer_mark": row.get("decision_6_same_after_condition_layer"),
                                    **judge_rejected(rec["raw_text"], row["question"], gold, provider)}
    return out


def main():
    rows, _ = load_queue(QUEUE)
    ids = [r["candidate_id"] for r in rows]
    if len(ids) != 52 or sum(not i.endswith("-hf") for i in ids) != 28:
        raise SystemExit("queue 행이 batch006 검토 시트와 다르다")
    if DECISIONS.exists():
        raise SystemExit("decisions 파일이 이미 있다")
    judged = rejudge(rows)
    (HERE / "rejudge_pairs.json").write_text(json.dumps(judged, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    out = []
    for row in rows:
        cid = row["candidate_id"]
        base = cid.removesuffix("-hf")
        if base in GOLD_NO:
            out.append(decide(QUEUE, DECISIONS, cid, status="rejected", reviewer=REVIEWER,
                              reason=f"{REASON}: 제외. {GOLD_NO[base]}" + (" gold 제외에 따라 쌍도 뺀다" if cid.endswith("-hf") else "")))
        elif not cid.endswith("-hf"):
            out.append(decide(QUEUE, DECISIONS, cid, status="accepted", reviewer=REVIEWER, reason=REASON, semantic_checks=True))
        elif cid in DATE_ONLY:
            out.append(decide(QUEUE, DECISIONS, cid, status="rejected", reviewer=REVIEWER,
                              reason=f"{REASON}: 쌍 제외. 날짜 표기만 다르다(결정 80). 재판정 {judged[cid]['category']}"))
        elif judged[cid]["category"] != "kept_operational_wrong":
            out.append(decide(QUEUE, DECISIONS, cid, status="rejected", reviewer=REVIEWER,
                              reason=f"{REASON}: 쌍 제외. 결정 6 운영 경로 재판정에서 초안과 같아짐({judged[cid]['category']}:"
                                     f"{judged[cid]['reason']})"))
        else:
            out.append(decide(QUEUE, DECISIONS, cid, status="accepted", reviewer=REVIEWER,
                              reason=f"{REASON}: 쌍 승인. 결정 6 재판정 {judged[cid]['category']}:{judged[cid]['reason']}",
                              semantic_checks=True, negative_wrong=True))
    counts = {"decisions": len(out),
              "gold_accepted": sum(d["status"] == "accepted" and not d["candidate_id"].endswith("-hf") for d in out),
              "gold_rejected": sum(d["status"] == "rejected" and not d["candidate_id"].endswith("-hf") for d in out),
              "pair_accepted": sorted(d["candidate_id"] for d in out if d["status"] == "accepted" and d["candidate_id"].endswith("-hf")),
              "pair_rejected": sorted(d["candidate_id"] for d in out if d["status"] == "rejected" and d["candidate_id"].endswith("-hf")),
              "rejudge": {k: f"{v['category']}:{v['reason']}" for k, v in judged.items()},
              "rejudge_vs_queue_mark": {k: {"queue_mark": v["queue_condition_layer_mark"], "rejudge": v["category"]}
                                        for k, v in judged.items()
                                        if bool(v["queue_condition_layer_mark"]) != (v["category"] != "kept_operational_wrong")}}
    counts["pair_accepted_n"], counts["pair_rejected_n"] = len(counts["pair_accepted"]), len(counts["pair_rejected"])
    (HERE / "decisions_summary.json").write_text(json.dumps(counts, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(counts, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
