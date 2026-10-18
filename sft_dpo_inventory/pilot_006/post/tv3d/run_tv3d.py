# -*- coding: utf-8 -*-
"""T-v3d 실행기(``teacher/run_teacher6v4.py``의 사본; 결정 164). 스케줄러가 Ollama GPU에서 부른다.
결정 55 precheck(0.40.6) → 수집 + guard watch(O1 기준 0.5 × 중앙값) → 분석(``analyze_tv3d.py``).

    hfvenv/bin/python run_tv3d.py --main /home/hwkim/assistant_univ

원문 ``training/generated/pilot_006/teacher_tv3d/``(학습에 쓰지 않음). 기록은 ``post/tv3d/``. PID ``/home/hwkim/sftdpo_work/pids/T-v3d_collect.pid``.
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
UUID = "GPU-48f798cc-9437-50ac-d604-448bbad7b311"
PIDS = Path("/home/hwkim/sftdpo_work/pids")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--main", required=True)
    a = p.parse_args()
    main_dir = Path(a.main)
    rec = main_dir / "sft_dpo_inventory/pilot_006/post/tv3d"
    rule = json.loads((HERE / "tv3d_rule.json").read_text(encoding="utf-8"))
    guard = main_dir / "sft_dpo_inventory/pilot_002/ollama_gpu_guard.py"
    out_dir = main_dir / "training/generated/pilot_006/teacher_tv3d"
    thr = json.loads((main_dir / "sft_dpo_inventory/pilot_006/post/o1_speed.json").read_text(encoding="utf-8"))["threshold_tok_s(0.5x median)"]
    pre = subprocess.run([sys.executable, str(guard), "precheck", "--version", "0.40.6", "--gpu-uuid", UUID, "--allow-loaded", "qwen3.8:27b",
                          "--out", str(rec / "tv3d_gpu_precheck.json")])
    if pre.returncode != 0:
        raise SystemExit(1)
    proc = subprocess.Popen([sys.executable, str(HERE / "collect_tv3d.py"), "--targets", str(HERE / "tv3d_targets.json"), "--out", str(out_dir),
                             "--summary", str(rec / "tv3d_summary.json"), "--seed-base", str(rule["seed_base"])],
                            stdout=open(rec / "tv3d_collect.log", "w"), stderr=subprocess.STDOUT)
    PIDS.mkdir(parents=True, exist_ok=True)
    (PIDS / "T-v3d_collect.pid").write_text(str(proc.pid))
    for _ in range(300):
        if (out_dir / "traces.jsonl").exists() or proc.poll() is not None:
            break
        time.sleep(2)
    g = subprocess.run([sys.executable, str(guard), "watch", "--gpu-uuid", UUID, "--pid", str(proc.pid), "--rows", str(out_dir / "traces.jsonl"),
                        "--model", "qwen3.8:27b", "--min-rate", str(thr), "--out", str(rec / "tv3d_gpu_guard.json")],
                       stdout=open(rec / "tv3d_gpu_guard.log", "w"), stderr=subprocess.STDOUT)
    rc = proc.wait()
    (PIDS / "T-v3d_collect.pid").unlink(missing_ok=True)
    print(json.dumps({"variant": "v3d", "collect_exit": rc, "guard_exit": g.returncode, "min_rate": thr}))
    if g.returncode != 0:
        if out_dir.exists():
            out_dir.rename(out_dir.with_name("ABORTED_" + out_dir.name))
        raise SystemExit(2)
    if rc != 0:
        raise SystemExit(rc)
    raise SystemExit(subprocess.run([sys.executable, str(HERE / "analyze_tv3d.py"), "--main", str(main_dir)]).returncode)


if __name__ == "__main__":
    main()
