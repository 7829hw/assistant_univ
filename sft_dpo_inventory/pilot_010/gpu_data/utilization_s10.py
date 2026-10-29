# -*- coding: utf-8 -*-
"""pilot_010 선택 단계 세션 GPU 사용률과 10분 넘는 유휴 구간(``utilization_prep10.py`` 사본: 세션 시작·이유·출력 이름만).

    python3 sft_dpo_inventory/pilot_010/gpu_data/utilization_s10.py --end ISO   # -> utilization_s10.json

세션 시작 = ``session_S_check.txt``(2026-10-27 18:29:45). 이유는 ``REASONS``(세션 기록에서 손으로 적음).
"""
import argparse
import json
from datetime import datetime
from pathlib import Path

HERE = Path("/home/hwkim/assistant_univ/sft_dpo_inventory/pilot_010/gpu")
START = datetime.fromisoformat("2026-10-27T18:29:45+09:00")
GPUS = {"GPU-2445b100-70d8-e384-3a24-0249eeefc64d": "2445b100(index 0)", "GPU-a5ce83d0-6ca2-5e3a-276c-4c965ea9c555": "a5ce83d0(index 1)",
        "GPU-48f798cc-9437-50ac-d604-448bbad7b311": "48f798cc(index 2, Ollama GPU)"}
G0, G1, G2 = GPUS.values()
REASONS = {g: [("2026-10-27T18:29", "세션 시작 확인 → 결정 247–255 기록, P1(지시 2판·검사·T-C2 문항·규칙·실행기·작업 표) 뒤 큐 시작(지시 순서: T-C2가 첫 GPU 작업)")] for g in (G0, G1, G2)}
for g in (G0, G1):
    REASONS[g][0] = ("2026-10-27T18:29", "세션 시작 확인·P1 뒤(T-C2는 GPU 2) **TEACH-C 의존 대기**(plan_S.json에 미리 적음): 학습은 T-C2·TEACH-C 수집·빌드·PLAN_S 고정 뒤에만 가능, 이 GPU에 줄 다른 작업 없음")
    REASONS[g].append(("2026-10-27T18:50", "TEACH-C 의존 대기(plan_S.json에 미리 적음): 학습은 TEACH-C 수집·빌드·PLAN_S 고정 뒤에만 가능, 이 GPU에 줄 다른 작업 없음"))
REASONS[G2].append(("2026-10-28T01:50", "TEACH-C 끝 → C1 읽기·변형 빌드(build10w 포함)·config·dry-run·PLAN_S·FREEZE_S 뒤 학습 시작(02:13)"))
for g in (G0, G1, G2):
    REASONS[g].append(("2026-10-28T10:45", "평가 셀 끝 → 완료성 검사·원본 커밋·다시 돌리기 작업 표 뒤 R10 시작(11:19)"))
    REASONS[g].append(("2026-10-28T12:05", "남은 GPU 작업 없음(다시 돌리기 한 번만; 선택 단계 학습은 6개로 끝, 판정 단계 학습 금지)"))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--end", required=True)
    a = p.parse_args()
    end = datetime.fromisoformat(a.end)
    out_name = "utilization_s10.json"
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
