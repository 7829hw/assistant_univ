# -*- coding: utf-8 -*-
"""pilot_007 B2단계 GPU 사용률과 10분 넘는 유휴 구간(``utilization_b.py`` 사본: 세션 시작·이유·출력 이름만 B2).

    python3 sft_dpo_inventory/pilot_007/gpu/utilization_b2.py --end ISO   # -> utilization_B2.json

세션 시작 = ``session_B2_check.txt``(2026-10-21 10:46). 이전 timeline 줄은 시작 시각으로 걸러진다. 이유는 ``REASONS``(세션 기록에서 손으로 적음).
"""
import argparse
import json
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
START = datetime.fromisoformat("2026-10-21T10:46:56+09:00")
GPUS = {"GPU-2445b100-70d8-e384-3a24-0249eeefc64d": "2445b100(index 0)", "GPU-a5ce83d0-6ca2-5e3a-276c-4c965ea9c555": "a5ce83d0(index 1)",
        "GPU-48f798cc-9437-50ac-d604-448bbad7b311": "48f798cc(index 2, Ollama GPU)"}
REASONS = {g: [("2026-10-21T10:46", "세션 시작 확인 → 결정 205–210 기록, O4' 순서 도구·순서 파일 5개·연속 길이 표, config·dry-run/tokenizer-check 20개, 작업 표·spec, PLAN_B2·FREEZE_B2 뒤 큐 시작(11:03, 지시 순서)")]
           for g in ("2445b100(index 0)", "a5ce83d0(index 1)", "48f798cc(index 2, Ollama GPU)")}
GPUS["GPU-48f798cc-9437-50ac-d604-448bbad7b311"] = "48f798cc(index 2, Ollama GPU)"  # B: Ollama GPU = GPU 2(결정 191·198)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--end", required=True)
    a = p.parse_args()
    end = datetime.fromisoformat(a.end)
    out_name = "utilization_B2.json"
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
