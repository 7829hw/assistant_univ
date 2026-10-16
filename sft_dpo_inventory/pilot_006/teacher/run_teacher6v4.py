# -*- coding: utf-8 -*-
"""v3c 확인(T0c)·TEACH 실행기(결정 149–152, 세션 2d; ``run_teacher6v3.py``의 사본). 스케줄러가 Ollama GPU에서 부른다.
결정 55 precheck → teacher 수집 + guard watch(F5 33.55) → (T0c) 판정·선택.

    hfvenv/bin/python run_teacher6v4.py --main /home/hwkim/assistant_univ --job T0c|TEACH

- T0c: 대상 ``t0v4_targets.json``(20 × 8), 원문 ``training/generated/pilot_006/teacher_t0v3c/``, 끝나면 ``analyze_t0v4.py``(L3 선택).
- TEACH: ``t0v4_verdict.json``의 ``selected``가 v3a/v3b/v3c일 때만(아니면 exit 4). 대상 ``teach3_targets.json``(245, 결정 152),
  원문 ``training/generated/pilot_006/teacher_v3/``.
- PID: 수집 프로세스 PID를 ``/home/hwkim/sftdpo_work/pids/<job>_collect.pid``에 남긴다(결정 147).
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
    p.add_argument("--job", choices=("T0c", "TEACH"), required=True)
    a = p.parse_args()
    main_dir = Path(a.main)
    rec = main_dir / "sft_dpo_inventory/pilot_006/teacher"
    if a.job == "TEACH":
        v = rec / "t0v4_verdict.json"
        sel = json.loads(v.read_text(encoding="utf-8")).get("selected") if v.exists() else None
        if sel not in ("v3a", "v3b", "v3c"):
            print(f"no variant selected ({sel}); TEACH not started")
            raise SystemExit(4)
        variant, targets, out_rel, tag, seed = sel, "teach3_targets.json", "training/generated/pilot_006/teacher_v3", "teach4", 20261816
    else:
        rule = json.loads((HERE / "t0v4_rule.json").read_text(encoding="utf-8"))
        variant, targets, out_rel, tag, seed = "v3c", "t0v4_targets.json", "training/generated/pilot_006/teacher_t0v3c", "t0v3c", rule["seed_base"]["v3c"]
    guard = main_dir / "sft_dpo_inventory/pilot_002/ollama_gpu_guard.py"
    out_dir = main_dir / out_rel
    thr = json.loads((main_dir / "sft_dpo_inventory/pilot_006_prep/gpu/g0_speed.json").read_text(encoding="utf-8"))["threshold_tok_s(0.5x median)"]
    pre = subprocess.run([sys.executable, str(guard), "precheck", "--version", "0.40.3", "--gpu-uuid", UUID, "--allow-loaded", "qwen3.8:27b",
                          "--out", str(rec / f"{tag}_gpu_precheck.json")])
    if pre.returncode != 0:
        raise SystemExit(1)
    proc = subprocess.Popen([sys.executable, str(HERE / "collect_teacher6v3.py"), "--variant", variant, "--targets", str(HERE / targets), "--out", str(out_dir),
                             "--summary", str(rec / f"{tag}_summary.json"), "--seed-base", str(seed)],
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
    print(json.dumps({"variant": variant, "collect_exit": rc, "guard_exit": g.returncode, "min_rate": thr}))
    if g.returncode != 0:
        if out_dir.exists():
            out_dir.rename(out_dir.with_name("ABORTED_" + out_dir.name))
        raise SystemExit(2)
    if rc != 0:
        raise SystemExit(rc)
    if a.job == "T0c":
        raise SystemExit(subprocess.run([sys.executable, str(HERE / "analyze_t0v4.py"), "--main", str(main_dir)]).returncode)


if __name__ == "__main__":
    main()
