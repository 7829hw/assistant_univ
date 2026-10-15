# -*- coding: utf-8 -*-
"""세션 GPU 사용률과 10분 넘는 유휴 구간(지시 5.2). ``timeline.jsonl``과 ``runs.log``(서버 기동·종료 시각)에서 계산한다.

    python3 sft_dpo_inventory/pilot_006_prep/gpu/utilization.py --end ISO

- 세션 시간: ``initial_check.txt``의 확인 시각(2026-10-15 21:39:17) ~ ``--end``.
- 작업 시간: timeline의 작업 시작~끝(서버 기동·종료 제외). 상태 정정(``status_correction``) 줄은 시간에 더하지 않는다(원래 줄과 같은 구간).
- 유휴: 작업이 없는 구간 중 10분 넘는 것. 이유는 ``REASONS``(세션 기록에서 손으로 적음)에서 붙인다.
출력: ``utilization.json``.
"""
import argparse
import json
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
START = datetime.fromisoformat("2026-10-15T21:39:17+09:00")
GPUS = {"GPU-2445b100-70d8-e384-3a24-0249eeefc64d": "2445b100(index 0)", "GPU-a5ce83d0-6ca2-5e3a-276c-4c965ea9c555": "a5ce83d0(index 1)",
        "GPU-48f798cc-9437-50ac-d604-448bbad7b311": "48f798cc(index 2, Ollama GPU)"}
#: (gpu, 구간 시작 이후) → 이유. 구간 시작 시각이 이 값 이상인 첫 항목을 쓴다.
REASONS = {
    "a5ce83d0(index 1)": [("2026-10-15T21:39", "의존 대기: W1·W6 1–4 전(J3 시작 조건)"),
                          ("2026-10-15T22:07", "의존 대기: J4는 W4 1–6 통과가 시작 조건"),
                          ("2026-10-15T22:29", "의존 대기 → J5S·J5R이 HTTP 400으로 무효, J7은 W7b 겹침 검사 대기"),
                          ("2026-10-15T22:37", "준비된 작업 없음: J5·J6은 Partial 길이 한도 결정(사용자) 대기, 이번 세션 허용 작업(J1–J7) 소진")],
    "48f798cc(index 2, Ollama GPU)": [("2026-10-15T21:39", "의존 대기: W1·W6 1–5 전"),
                                      ("2026-10-15T22:10", "의존 대기: J5S는 J4 통과가 시작 조건 → J4 통과 뒤 J5S를 GPU 1에 붙임(GPU 1이 먼저 비었음); 이후 준비된 작업 없음(J6은 사용자 결정 대기)")],
    "2445b100(index 0)": [("2026-10-15T21:39", "의존 대기: W1·W6 1–4 전"), ("2026-10-16T00:00", "준비된 작업 없음(J1 끝, 남은 허용 작업 없음)")],
}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--end", required=True)
    a = p.parse_args()
    end = datetime.fromisoformat(a.end)
    rows = [json.loads(line) for line in (HERE / "timeline.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    rows = [r for r in rows if r["kind"] != "status_correction"]
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
    (HERE / "utilization.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
