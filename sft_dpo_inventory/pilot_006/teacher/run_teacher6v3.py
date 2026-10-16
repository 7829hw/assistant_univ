# -*- coding: utf-8 -*-
"""T0''b·T0''a·TEACH 실행기(결정 144 K7·145 K8; 스케줄러가 Ollama GPU에서 부른다): 결정 55 precheck → teacher v3 수집 + guard watch(F5 33.55) → 판정.

    hfvenv/bin/python run_teacher6v3.py --main /home/hwkim/assistant_univ --job T0b|T0a|TEACH

- T0b/T0a: 대상 ``t0v3_targets.json``(20 × 8), 원문 ``training/generated/pilot_006/teacher_t0v3b|a/``, 끝나면 ``analyze_t0v3.py``(두 안이 모두 있으면 선택).
- TEACH: ``t0v3_verdict.json``의 ``selected``가 v3a/v3b일 때만(아니면 exit 4). 대상 ``teach3_targets.json``, 원문 ``training/generated/pilot_006/teacher_v3/``.
- PID: 수집 프로세스 PID를 ``/home/hwkim/sftdpo_work/pids/<job>.pid``에 남긴다(결정 147 K10).
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
    p.add_argument("--job", choices=("T0b", "T0a", "TEACH"), required=True)
    a = p.parse_args()
    main_dir = Path(a.main)
    rec = main_dir / "sft_dpo_inventory/pilot_006/teacher"
    if a.job == "TEACH":
        v = rec / "t0v3_verdict.json"
        sel = json.loads(v.read_text(encoding="utf-8")).get("selected") if v.exists() else None
        if sel not in ("v3a", "v3b"):
            print(f"no variant selected ({sel}); TEACH not started")
            raise SystemExit(4)
        variant, targets, out_rel, tag, seed = sel, "teach3_targets.json", "training/generated/pilot_006/teacher_v3", "teach3", 20261516
    else:
        variant = "v3b" if a.job == "T0b" else "v3a"
        rule = json.loads((HERE / "t0v3_rule.json").read_text(encoding="utf-8"))
        targets, out_rel, tag, seed = "t0v3_targets.json", f"training/generated/pilot_006/teacher_t0{variant}", f"t0{variant}", rule["seed_base"][variant]
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
    if a.job in ("T0b", "T0a"):
        raise SystemExit(subprocess.run([sys.executable, str(HERE / "analyze_t0v3.py"), "--main", str(main_dir)]).returncode)


if __name__ == "__main__":
    main()
