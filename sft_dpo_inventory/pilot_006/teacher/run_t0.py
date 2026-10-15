# -*- coding: utf-8 -*-
"""T0 실행기(스케줄러가 Ollama GPU에서 부른다): 결정 55 precheck → teacher 수집(표현 중립 v1, 20질문 × 8) + guard watch(F5 기준).

    hfvenv/bin/python run_t0.py --main /home/hwkim/assistant_univ

- precheck: ``ollama_gpu_guard.py precheck --version 0.40.3 --gpu-uuid 48f798cc… --allow-loaded qwen3.8:27b``(G0 뒤 연속 방식).
- guard: ``watch --min-rate <PLAN_DEVIATIONS 1번 기준>``(``pilot_006_prep/gpu/g0_speed.json``의 0.5 × 중앙값). 미달이면 수집을 멈추고 exit 2.
- 출력: 원문 ``training/generated/pilot_006/teacher_t0/traces.jsonl``(ignore), 요약 ``pilot_006/teacher/t0_summary.json``, guard 기록 ``t0_gpu_*.json``.
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
UUID = "GPU-48f798cc-9437-50ac-d604-448bbad7b311"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--main", required=True)
    a = p.parse_args()
    main_dir = Path(a.main)
    guard = main_dir / "sft_dpo_inventory/pilot_002/ollama_gpu_guard.py"
    out_dir = main_dir / "training/generated/pilot_006/teacher_t0"
    rec = main_dir / "sft_dpo_inventory/pilot_006/teacher"
    thr = json.loads((main_dir / "sft_dpo_inventory/pilot_006_prep/gpu/g0_speed.json").read_text(encoding="utf-8"))["threshold_tok_s(0.5x median)"]
    pre = subprocess.run([sys.executable, str(guard), "precheck", "--version", "0.40.3", "--gpu-uuid", UUID, "--allow-loaded", "qwen3.8:27b",
                          "--out", str(rec / "t0_gpu_precheck.json")])
    if pre.returncode != 0:
        raise SystemExit(1)
    proc = subprocess.Popen([sys.executable, str(HERE / "collect_teacher6.py"), "--targets", str(HERE / "t0_targets.json"), "--out", str(out_dir),
                             "--summary", str(rec / "t0_summary.json")], stdout=open(rec / "t0_collect.log", "w"), stderr=subprocess.STDOUT)
    for _ in range(120):
        if (out_dir / "traces.jsonl").exists() or proc.poll() is not None:
            break
        time.sleep(2)
    g = subprocess.run([sys.executable, str(guard), "watch", "--gpu-uuid", UUID, "--pid", str(proc.pid), "--rows", str(out_dir / "traces.jsonl"),
                        "--model", "qwen3.8:27b", "--min-rate", str(thr), "--out", str(rec / "t0_gpu_guard.json")],
                       stdout=open(rec / "t0_gpu_guard.log", "w"), stderr=subprocess.STDOUT)
    rc = proc.wait()
    print(json.dumps({"collect_exit": rc, "guard_exit": g.returncode, "min_rate": thr}))
    if g.returncode != 0:
        raise SystemExit(2)
    raise SystemExit(rc)


if __name__ == "__main__":
    main()
