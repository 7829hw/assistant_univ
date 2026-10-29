# -*- coding: utf-8 -*-
"""pilot_010 선택 단계 GPU 작업 표 1부(결정 248·249, 지시 2.2 우선 1·2). scheduler12(세 장, Ollama GPU = GPU 2 48f798cc)가 읽는다.
``make_jobs_prep10.py``와 같은 방식(그 파일은 그대로). 학습·평가(우선 3·4)는 변형 빌드·PLAN_S 고정 뒤 ``make_jobs_S2.py``(새 스케줄러 실행, 그 커밋의 worktree).

    python3 make_jobs_S1.py   # -> gpu/jobs_S1.json, gpu/seeds_S1.json

| 우선 | ID | 작업 | 조건 |
| 1 | T-C2 | 근접 대조 지시 2판 확인(20 × 8, ``teacher/run_c10b.py --job T-C2``, warm-up 1회) | P1 커밋(스케줄러 시작 커밋) |
| 2 | TEACH-Cv2 | 본 수집(``teachc_targets.json`` 250 × 8, ``run_c10b.py --job TEACH-C``) | T-C2 ok, ``ready/TEACH-Cv2.json``(T-C2 통과 판정 뒤 만듦) |

- 작업 ID ``TEACH-Cv2``: 준비 세션의 ``ready/TEACH-C.skip``(T-C 불통과 기록, 그대로 둠)과 겹치지 않게 새 ID를 쓴다. 지시의 TEACH-C와 같은 작업이다.
- 실행기는 ``tc2_verdict.json``의 ``passed``가 true일 때만 TEACH-C를 시작한다(아니면 모델 호출 없이 exit 3).
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = "/data/hwkim/sftdpo_work/runtime/envs/hf/bin/python"
CHK = "bash {MAIN}/sft_dpo_inventory/pilot_010/gpu_data/check_ready.sh {ID} && "


def job(id_, kind, est, prio, cmd, deps, ready_id=None):
    full = (CHK.replace("{ID}", ready_id) + cmd) if ready_id else cmd
    return {"id": id_, "type": "raw", "kind": kind, "server": "ollama", "est": est, "prio": prio, "deps": deps, "cmd": ["bash", "-c", full], "outputs": []}


jobs = [
    job("T-C2", "teacher_contrast_check_TC2", 40, 1, f"{PY} {{WT}}/sft_dpo_inventory/pilot_010/teacher_data/run_c10b.py --main {{MAIN}} --job T-C2", []),
    job("TEACH-Cv2", "teacher_contrast_collect_v2", 470, 2, f"{PY} {{WT}}/sft_dpo_inventory/pilot_010/teacher_data/run_c10b.py --main {{MAIN}} --job TEACH-C",
        ["T-C2", "ready:TEACH-Cv2"], "TEACH-Cv2"),
]
(HERE / "jobs_S1.json").write_text(json.dumps({"jobs": jobs}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
seeds = {"T-C2": {"seed_base": 20271031, "rule": "seed_base + 1000 × 질문 순번 + 표본 번호, temperature 0.6", "warmup_seed": 20271030, "read_seed": 20271032},
         "TEACH-C": {"seed_base": 20272027, "rule": "같음", "warmup_seed": 20272026, "read_seed": 20272028}}
(HERE / "seeds_S1.json").write_text(json.dumps(seeds, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print([(j["prio"], j["id"], j["deps"]) for j in jobs])
