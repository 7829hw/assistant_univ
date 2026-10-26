# -*- coding: utf-8 -*-
"""pilot_009 teacher 실행기(T-R·TEACH-R, 결정 228). ``pilot_006/post/tv3d/run_tv3d.py``의 사본. 스케줄러가 Ollama GPU(GPU 2, 48f798cc)에서 부른다.
결정 55 precheck(0.40.6) → 수집 + guard watch(O1 기준 33.71 tok/s) → 분석(``analyze_r9.py``).

    hfvenv/bin/python run_r9.py --main /home/hwkim/assistant_univ --job T-R|TEACH-R

- TEACH-R은 ``tr_verdict.json``의 ``passed``가 true이고 ``teachr_targets.json``이 있을 때만 시작한다(아니면 모델 호출 없이 exit 3).
- 원문 ``training/generated/pilot_009/teacher_{tr,teachr}/``, 기록 ``pilot_009/teacher/``. PID ``/home/hwkim/sftdpo_work/pids/{job}_collect.pid``.
- guard가 멈추면 원문 디렉터리를 ``ABORTED_*``로 바꾸고 exit 2(결정 55).
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
JOBS = {"T-R": ("tr", "tr_targets.json", 20261926), "TEACH-R": ("teachr", "teachr_targets.json", 20262026)}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--main", required=True)
    p.add_argument("--job", required=True, choices=sorted(JOBS))
    a = p.parse_args()
    main_dir = Path(a.main)
    rec = main_dir / "sft_dpo_inventory/pilot_009/teacher"
    tag, targets_name, seed_base = JOBS[a.job]
    targets = rec / targets_name
    if a.job == "TEACH-R":
        v = rec / "tr_verdict.json"
        passed = json.loads(v.read_text(encoding="utf-8")).get("passed") if v.exists() else None
        if passed is not True or not targets.exists():
            print(json.dumps({"job": a.job, "skip": True, "tr_passed": passed, "targets": targets.exists()}))
            raise SystemExit(3)
    guard = main_dir / "sft_dpo_inventory/pilot_002/ollama_gpu_guard.py"
    out_dir = main_dir / f"training/generated/pilot_009/teacher_{tag}"
    thr = json.loads((main_dir / "sft_dpo_inventory/pilot_006/post/o1_speed.json").read_text(encoding="utf-8"))["threshold_tok_s(0.5x median)"]
    pre = subprocess.run([sys.executable, str(guard), "precheck", "--version", "0.40.6", "--gpu-uuid", UUID, "--allow-loaded", "qwen3.8:27b",
                          "--out", str(rec / f"{tag}_gpu_precheck.json")])
    if pre.returncode != 0:
        raise SystemExit(1)
    out_dir.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.Popen([sys.executable, str(HERE / "collect_r9.py"), "--targets", str(targets), "--out", str(out_dir),
                             "--summary", str(rec / f"{tag}_summary.json"), "--seed-base", str(seed_base), "--label", a.job],
                            stdout=open(rec / f"{tag}_collect.log", "w"), stderr=subprocess.STDOUT)
    PIDS.mkdir(parents=True, exist_ok=True)
    (PIDS / f"{a.job}_collect.pid").write_text(str(proc.pid))
    for _ in range(300):
        if (out_dir / "traces.jsonl").exists() or proc.poll() is not None:
            break
        time.sleep(2)
    g = subprocess.run([sys.executable, str(guard), "watch", "--gpu-uuid", UUID, "--pid", str(proc.pid), "--rows", str(out_dir / "traces.jsonl"),
                        "--model", "qwen3.8:27b", "--min-rate", str(thr), "--out", str(rec / f"{tag}_gpu_guard.json")],
                       stdout=open(rec / f"{tag}_gpu_guard.log", "w"), stderr=subprocess.STDOUT)
    rc = proc.wait()
    (PIDS / f"{a.job}_collect.pid").unlink(missing_ok=True)
    print(json.dumps({"job": a.job, "collect_exit": rc, "guard_exit": g.returncode, "min_rate": thr}))
    if g.returncode != 0:
        if out_dir.exists():
            out_dir.rename(out_dir.with_name("ABORTED_" + out_dir.name))
        raise SystemExit(2)
    if rc != 0:
        raise SystemExit(rc)
    raise SystemExit(subprocess.run([sys.executable, str(HERE / "analyze_r9.py"), "--main", str(main_dir), "--job", a.job]).returncode)


if __name__ == "__main__":
    main()
