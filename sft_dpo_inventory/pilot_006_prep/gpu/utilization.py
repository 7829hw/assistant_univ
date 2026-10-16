# -*- coding: utf-8 -*-
"""세션 GPU 사용률과 10분 넘는 유휴 구간(지시 5.2). ``timeline.jsonl``과 ``runs.log``(서버 기동·종료 시각)에서 계산한다.

    python3 sft_dpo_inventory/pilot_006_prep/gpu/utilization.py --end ISO
    python3 sft_dpo_inventory/pilot_006_prep/gpu/utilization.py --session 2 --end ISO   # 세션 2: 시작 = session2_check.txt(01:14:23), 출력 utilization_s2.json

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
                          ("2026-10-15T22:37", "준비된 작업 없음: J5·J6은 Partial 길이 한도 결정(사용자) 대기, 세션 1 허용 작업 소진 → 세션 1b 지시(23:41)까지"),
                          ("2026-10-16T00:12", "B1 뒤 준비된 작업 없음(J5R'·J6은 J5S' 불통과로 보류, B4는 GPU 2 큐) → 00:30 B4 재측정"),
                          ("2026-10-16T00:46", "세션 끝")],
    "48f798cc(index 2, Ollama GPU)": [("2026-10-15T21:39", "의존 대기: W1·W6 1–5 전"),
                                      ("2026-10-15T22:10", "준비된 작업 없음: J5는 GPU 1이 먼저 비어 거기에 붙였고, 이후 J6은 Partial 길이 한도 결정(사용자) 대기 → 세션 1b 지시(23:41)까지"),
                                      ("2026-10-16T00:29", "B4가 외부 worktree 삭제로 실패한 뒤 GPU 1에서 다시 잼, T0(선택)은 27b guard 위험으로 하지 않음")],
    "2445b100(index 0)": [("2026-10-15T21:39", "의존 대기: W1·W6 1–4 전"), ("2026-10-16T00:37", "준비된 작업 없음(J1 끝, J6은 J5S' 불통과로 보류)")],
}


#: 세션 2(지시 "pilot_006 준비 세션 2", 시작 확인 2026-10-16 01:14:23)
START_S2 = datetime.fromisoformat("2026-10-16T01:14:23+09:00")
REASONS_S2 = {
    "2445b100(index 0)": [("2026-10-16T01:14", "시작 준비(결정 기록·도구 커밋 뒤 큐 시작)"),
                          ("2026-10-16T03:18", "의존 대기: M1은 C6 시험 빌드(L_req·M1 세트)가 시작 조건이고, C6은 J6 판정(C3) 뒤에 만들 수 있었다. "
                                               "J6 판정·대조·검토 자료(C2–C4)와 빌드 도구·학습 코드 분기(C6)를 CPU에서 차례로 하느라 길어졌다"),
                          ("2026-10-16T07:30", "M1 결함(12,288 세트·torch 값) 수정 뒤 M1b")],
    "a5ce83d0(index 1)": [("2026-10-16T01:14", "시작 준비"),
                          ("2026-10-16T02:52", "준비된 작업 없음: 세션 2 GPU 큐 소진(M1·M1b는 한 GPU 단독, GPU 0에 배정). 학습·teacher 수집은 세션 3")],
    "48f798cc(index 2, Ollama GPU)": [("2026-10-16T01:14", "시작 준비"),
                                      ("2026-10-16T02:53", "준비된 작업 없음: 세션 2 GPU 큐 소진. 학습·teacher 수집은 세션 3")],
}


START_S2B = datetime.fromisoformat("2026-10-16T11:08:10+09:00")
REASONS_S2B = {
    "2445b100(index 0)": [("2026-10-16T11:08", "큐 시작"), ("2026-10-16T14:29", "세션 2b GPU 큐 끝(남은 작업 없음)")],
    "a5ce83d0(index 1)": [("2026-10-16T11:08", "큐 시작"),
                          ("2026-10-16T13:54", "준비된 작업 없음: 남은 S32P-b·J10·J11·J12·S32F-b가 다른 GPU에 먼저 붙었다. TEACH(T0' 불통과)가 없어져 vLLM 작업이 계획보다 일찍 소진")],
    "48f798cc(index 2, Ollama GPU)": [("2026-10-16T11:08", "큐 시작"),
                                      ("2026-10-16T11:37", "T0' 뒤 Ollama 모델이 /api/ps에서 내려갈 때까지 vLLM을 올리지 않음(keep_alive, 결정 137·규칙 7)"),
                                      ("2026-10-16T14:10", "세션 2b GPU 큐 끝(남은 작업 없음)")],
}


def main():
    global START, REASONS
    p = argparse.ArgumentParser()
    p.add_argument("--end", required=True)
    p.add_argument("--session", choices=("1", "2", "2b"), default="1")
    a = p.parse_args()
    end = datetime.fromisoformat(a.end)
    out_name = "utilization.json"
    if a.session == "2":
        START, REASONS, out_name = START_S2, REASONS_S2, "utilization_s2.json"
    if a.session == "2b":
        START, REASONS, out_name = START_S2B, REASONS_S2B, "utilization_s2b.json"
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
