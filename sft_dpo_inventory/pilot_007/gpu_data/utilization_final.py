# -*- coding: utf-8 -*-
"""pilot_007 최종 판정 GPU 사용률과 10분 넘는 유휴 구간(``utilization_b2.py`` 사본: 세션 시작·이유·출력 이름만).

    python3 sft_dpo_inventory/pilot_007/gpu_data/utilization_final.py --end ISO   # -> utilization_final.json

세션 시작 = ``session_final_check.txt``(2026-10-22 11:02). 이전 timeline 줄은 시작 시각으로 걸러진다. 이유는 ``REASONS``(세션 기록에서 손으로 적음).
"""
import argparse
import json
from datetime import datetime
from pathlib import Path

HERE = Path("/home/hwkim/assistant_univ/sft_dpo_inventory/pilot_007/gpu")
START = datetime.fromisoformat("2026-10-22T11:02:14+09:00")
GPUS = {"GPU-2445b100-70d8-e384-3a24-0249eeefc64d": "2445b100(index 0)", "GPU-a5ce83d0-6ca2-5e3a-276c-4c965ea9c555": "a5ce83d0(index 1)",
        "GPU-48f798cc-9437-50ac-d604-448bbad7b311": "48f798cc(index 2, Ollama GPU)"}
REASONS = {g: [("2026-10-22T11:02", "세션 시작 확인 → 결정 211–216, 후보 고르기, gold 변환, 채점 규칙, PLAN_FINAL·FREEZE_FINAL 뒤 측정 시도 1(11:11, 모델 요청 전 실패) → 정정 1·FREEZE_FINAL2 뒤 측정(11:17)")]
           for g in ("2445b100(index 0)", "a5ce83d0(index 1)", "48f798cc(index 2, Ollama GPU)")}
REASONS["a5ce83d0(index 1)"].append(("2026-10-22T11:51", "후보 셀 끝(작업 둘뿐): base 셀(GPU 0) 진행 중, 이어 지연 창(GPU 0) 동안 비움 — 결정 216"))
REASONS["48f798cc(index 2, Ollama GPU)"].append(("2026-10-22T11:02", "결정 216: 최종 판정은 GPU 0·1만 씀(GPU 2는 worker 아님)"))
GPUS["GPU-48f798cc-9437-50ac-d604-448bbad7b311"] = "48f798cc(index 2, Ollama GPU)"  # B: Ollama GPU = GPU 2(결정 191·198)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--end", required=True)
    a = p.parse_args()
    end = datetime.fromisoformat(a.end)
    out_name = "utilization_final.json"
    rows = [json.loads(line) for line in (HERE / "timeline.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    rows = [r for r in rows if r["kind"] != "status_correction" and datetime.fromisoformat(r["start"]) >= START]
    session = (end - START).total_seconds()
    out = {"session": {"start": START.isoformat(), "end": end.isoformat(), "hours": round(session / 3600, 2)}, "gpus": {}}
    for uuid, name in GPUS.items():
        jobs = sorted(((datetime.fromisoformat(r["start"]), datetime.fromisoformat(r["end"]), r["job_id"], r["status"]) for r in rows
                       if r["gpu_uuid"] == uuid), key=lambda x: x[0])
        busy = sum((e - s).total_seconds() for s, e, _, _ in jobs)
        gaps, cur = [], START
        for s, e, _, _ in jobs + [(end, end, "end", "")]:
            if (s - cur).total_seconds() > 600:
                reason = next((t for at, t in reversed(REASONS.get(name, [])) if cur >= datetime.fromisoformat(at + ":00+09:00")), "")
                gaps.append({"from": cur.isoformat(), "to": s.isoformat(), "minutes": round((s - cur).total_seconds() / 60, 1), "reason": reason})
            cur = max(cur, e)
        out["gpus"][name] = {"jobs": [{"job": j, "start": s.isoformat(), "end": e.isoformat(), "minutes": round((e - s).total_seconds() / 60, 1),
                                       "status": st} for s, e, j, st in jobs],
                             "busy_hours": round(busy / 3600, 2), "utilization": round(busy / session, 3), "idle_over_10min": gaps}
    (HERE / out_name).write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
