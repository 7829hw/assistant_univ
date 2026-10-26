# -*- coding: utf-8 -*-
"""pilot_009 준비 GPU 사용률과 10분 넘는 유휴 구간(``pilot_008/gpu/utilization_main.py`` 사본: 시작·이유·출력 이름만).

    python3 sft_dpo_inventory/pilot_009/gpu/utilization_prep.py --end ISO   # -> utilization_prep.json

시작 = 큐 시작(2026-10-26 16:22:52, runs.log). 이전 timeline 줄은 시작 시각으로 걸러진다. 이유는 ``REASONS``(세션 기록에서 손으로 적음).
"""
import argparse
import json
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
START = datetime.fromisoformat("2026-10-26T16:22:52+09:00")
GPUS = {"GPU-2445b100-70d8-e384-3a24-0249eeefc64d": "2445b100(index 0)", "GPU-a5ce83d0-6ca2-5e3a-276c-4c965ea9c555": "a5ce83d0(index 1)",
        "GPU-48f798cc-9437-50ac-d604-448bbad7b311": "48f798cc(index 2, Ollama GPU)"}
REASONS = {g: [("2026-10-26T16:22", "큐 시작(16:22:52) 직후: J 작업은 batch012·refusal_dev 확장 초안과 겹침 검사(CPU)가 끝나야 입력이 생김(P2 커밋 a11c626, ready 16:34)")]
           for g in ("2445b100(index 0)", "a5ce83d0(index 1)")}
REASONS["48f798cc(index 2, Ollama GPU)"] = [("2026-10-26T16:24", "T-R 시도 1 guard 멈춤 뒤 원인 확인·실행기 2판·큐 다시 시작(PLAN_DEVIATIONS 1)"),
                                           ("2026-10-26T18:04", "TEACH-R2 끝 뒤 /api/ps 빔 대기(지시 2절), 남은 J-rdev2 2개는 이미 GPU 0·1에서 실행 중 — 준비된 작업 없음")]
def main():
    p = argparse.ArgumentParser()
    p.add_argument("--end", required=True)
    a = p.parse_args()
    end = datetime.fromisoformat(a.end)
    out_name = "utilization_prep.json"
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
