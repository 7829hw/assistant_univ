# -*- coding: utf-8 -*-
"""pilot_007 A2단계 GPU 사용률과 10분 넘는 유휴 구간(``utilization7.py`` 사본: 세션 시작·이유·출력 이름만 A2).

    python3 sft_dpo_inventory/pilot_007/gpu/utilization_a2.py --end ISO   # -> utilization_A2.json

세션 시작 = ``session_A2_check.txt``(2026-10-19 13:28). A2 이전 timeline 줄(A단계)은 시작 시각으로 걸러진다. 이유는 ``REASONS``(세션 기록에서 손으로 적음).
"""
import argparse
import json
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
START = datetime.fromisoformat("2026-10-19T13:28:33+09:00")
GPUS = {"GPU-2445b100-70d8-e384-3a24-0249eeefc64d": "2445b100(index 0)", "GPU-a5ce83d0-6ca2-5e3a-276c-4c965ea9c555": "a5ce83d0(index 1)",
        "GPU-48f798cc-9437-50ac-d604-448bbad7b311": "48f798cc(index 2, Ollama GPU)"}
REASONS = {
    "2445b100(index 0)": [("2026-10-19T13:28", "세션 시작 확인 → 결정 기록, S0 config·dry-run·lr 확인((a) lr 합 질문 → 결정 183), S1 scheduler8, S2 PLAN_A2·FREEZE_A2 고정 뒤 큐 시작(13:41)")],
    "a5ce83d0(index 1)": [("2026-10-19T13:28", "세션 시작 확인 → 결정 기록, S0–S2 뒤 큐 시작(13:41)"),
                          ("2026-10-19T22:59", "준비된 작업 없음: 마지막 작업 E-A2q_R1p-o43이 GPU 0에서 실행 중(작업 하나 = GPU 하나)")],
    "48f798cc(index 2, Ollama GPU)": [("2026-10-19T13:28", "사용 금지(결정 180: 다른 사용자 배정) → 20:30경 사용자 허락(결정 184) 뒤 scheduler9 작성·커밋·worktree, 21:14 시작"),
                                      ("2026-10-19T22:56", "GPU 2 큐(옮긴 작업 셋) 끝 — 남은 작업은 scheduler8(GPU 0·1) 몫")],
}
GPUS["GPU-48f798cc-9437-50ac-d604-448bbad7b311"] = "48f798cc(index 2, Ollama GPU)"  # 이름표는 이전 판 그대로(지금 Ollama GPU는 GPU 0 — 결정 181)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--end", required=True)
    a = p.parse_args()
    end = datetime.fromisoformat(a.end)
    out_name = "utilization_A2.json"
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
