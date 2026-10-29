# -*- coding: utf-8 -*-
"""pilot_010 준비 세션 GPU 사용률(``pilot_009/gpu/utilization_main.py`` 사본: 세션 시작·이유만). 원 설명: pilot_009 본 세션 GPU 사용률과 10분 넘는 유휴 구간(``pilot_007/gpu/utilization_b2.py`` 사본: 세션 시작·이유·출력 이름·timeline 위치만).

    python3 sft_dpo_inventory/pilot_010/gpu_data/utilization_prep10.py --end ISO   # -> utilization_prep10.json

세션 시작 = ``session_main_check.txt``(2026-10-26 21:04). 이전 timeline 줄은 시작 시각으로 걸러진다. 이유는 ``REASONS``(세션 기록에서 손으로 적음).
"""
import argparse
import json
from datetime import datetime
from pathlib import Path

HERE = Path("/home/hwkim/assistant_univ/sft_dpo_inventory/pilot_010/gpu")
START = datetime.fromisoformat("2026-10-27T12:59:36+09:00")
GPUS = {"GPU-2445b100-70d8-e384-3a24-0249eeefc64d": "2445b100(index 0)", "GPU-a5ce83d0-6ca2-5e3a-276c-4c965ea9c555": "a5ce83d0(index 1)",
        "GPU-48f798cc-9437-50ac-d604-448bbad7b311": "48f798cc(index 2, Ollama GPU)"}
REASONS = {g: [("2026-10-27T12:59", "세션 시작 확인(prep_check) → 결정 241–246 기록, P1(근접 대조 지시·검사·T-C 문항·규칙·실행기·스케줄러) 뒤 큐 시작(13:41, 지시 순서)")]
           for g in ("2445b100(index 0)", "a5ce83d0(index 1)", "48f798cc(index 2, Ollama GPU)")}
REASONS["2445b100(index 0)"].append(("2026-10-27T13:41", "J 작업은 batch013 초안(P2)이 있어야 시작(ready/J-b013, 13:50); 이번 세션은 학습·평가 셀이 없어 GPU 0·1에 줄 다른 작업 없음"))
REASONS["a5ce83d0(index 1)"].append(("2026-10-27T13:41", "J 작업은 batch013 초안(P2)이 있어야 시작(ready/J-b013, 13:50); 이번 세션은 학습·평가 셀이 없어 GPU 0·1에 줄 다른 작업 없음"))
REASONS["a5ce83d0(index 1)"].append(("2026-10-27T14:00", "준비된 작업 없음: 지시 2.2 작업 표의 J 작업 끝(남은 J-b013은 GPU 0), TEACH-C는 Ollama GPU 전용이고 T-C 불통과로 하지 않음"))
GPUS["GPU-48f798cc-9437-50ac-d604-448bbad7b311"] = "48f798cc(index 2, Ollama GPU)"  # B: Ollama GPU = GPU 2(결정 191·198)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--end", required=True)
    a = p.parse_args()
    end = datetime.fromisoformat(a.end)
    out_name = "utilization_prep10.json"
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
