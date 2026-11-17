# -*- coding: utf-8 -*-
"""pilot_010 판정 단계 작업 표(PLAN_J 8절) — 학습 5개. 평가 작업은 도구 커밋 뒤 ``make_jobs_j_eval.py``가 같은 파일에 더한다(스케줄러는 20초마다 다시 읽어 새 id만 더함).

- 바퀴 1 = o101·o523·o2029(prio 1–3), 바퀴 2 = o31·o20271027(prio 4–5, ``not_after`` 2026-11-20T05:00+09:00 = 보고 마감 7시간 전, 결정 267 D6).
- 명령 = ``train_b7b.py --config configs_j/J-V4-o<seed>.yaml``(worktree 안, 상대 경로). 학습 실패는 스케줄러가 같은 config로 한 번 다시(``-retry``).

    python3 sft_dpo_inventory/pilot_010/gpu/make_jobs_j.py   # -> gpu/J/jobs_j.json
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = "/data/hwkim/sftdpo_work/runtime/envs/hf/bin/python"
ROUND1 = (101, 523, 2029)
ROUND2 = (31, 20271027)
NOT_AFTER_R2 = "2026-11-20T05:00:00+09:00"


def train_jobs():
    jobs = []
    for i, s in enumerate(ROUND1 + ROUND2, start=1):
        j = {"id": f"T-J-V4-o{s}", "type": "raw", "kind": f"train_j_V4-o{s}", "server": "train", "est": 195, "prio": i, "deps": [],
             "round": 1 if s in ROUND1 else 2,
             "cmd": [PY, "{WT}/sft_dpo_inventory/pilot_007/train/train_b7b.py", "--config", f"{{WT}}/sft_dpo_inventory/pilot_010/train/configs_j/J-V4-o{s}.yaml"]}
        if s in ROUND2:
            j["not_after"] = NOT_AFTER_R2
        jobs.append(j)
    return jobs


def main():
    out = HERE / "J/jobs_j.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    body = {"note": "pilot_010 판정 단계(결정 267, PLAN_J). 학습 5개; 평가 작업은 make_jobs_j_eval.py가 더함.", "jobs": train_jobs()}
    out.write_text(json.dumps(body, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps([(j["prio"], j["id"], j.get("not_after")) for j in body["jobs"]]))


if __name__ == "__main__":
    main()
