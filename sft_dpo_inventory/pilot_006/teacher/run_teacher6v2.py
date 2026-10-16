# -*- coding: utf-8 -*-
"""T0'·TEACH 실행기(결정 131 G1·132 G2, 스케줄러가 Ollama GPU에서 부른다): 결정 55 precheck → teacher v2 수집 + guard watch(F5 기준) → (T0'만) 판정.

    hfvenv/bin/python run_teacher6v2.py --main /home/hwkim/assistant_univ --job T0v2|TEACH

- precheck: ``ollama_gpu_guard.py precheck --version 0.40.3 --gpu-uuid 48f798cc… --allow-loaded qwen3.8:27b``(연속 방식, 결정 79).
- guard: ``watch --min-rate``(F5, ``pilot_006_prep/gpu/g0_speed.json``의 0.5 × 중앙값 = 33.55). 미달이면 수집을 멈추고 exit 2(결정 55, 출력은 ``ABORTED_*``).
- T0v2: 대상 ``t0v2_targets.json``(40질문 × 8), 원문 ``training/generated/pilot_006/teacher_t0v2/``, 요약 ``t0v2_summary.json``,
  끝나면 ``analyze_t0v2.py``가 실행 전에 커밋한 규칙(``t0v2_rule.json``)으로 판정해 ``t0v2_verdict.json``을 쓴다.
- TEACH: ``t0v2_verdict.json``의 ``pass``가 참일 때만 시작(아니면 exit 4). 대상 ``teach_targets.json``, 원문 ``training/generated/pilot_006/teacher_v2/``,
  요약 ``teach_summary.json``.
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
UUID = "GPU-48f798cc-9437-50ac-d604-448bbad7b311"
JOBS = {"T0v2": ("t0v2_targets.json", "training/generated/pilot_006/teacher_t0v2", "t0v2", 20261116),
        "TEACH": ("teach_targets.json", "training/generated/pilot_006/teacher_v2", "teach", 20261216)}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--main", required=True)
    p.add_argument("--job", choices=tuple(JOBS), required=True)
    a = p.parse_args()
    main_dir = Path(a.main)
    targets, out_rel, tag, seed_base = JOBS[a.job]
    rec = main_dir / "sft_dpo_inventory/pilot_006/teacher"
    if a.job == "TEACH":
        v = rec / "t0v2_verdict.json"
        if not v.exists() or not json.loads(v.read_text(encoding="utf-8")).get("pass"):
            print("T0' not passed; TEACH not started")
            raise SystemExit(4)
    guard = main_dir / "sft_dpo_inventory/pilot_002/ollama_gpu_guard.py"
    out_dir = main_dir / out_rel
    thr = json.loads((main_dir / "sft_dpo_inventory/pilot_006_prep/gpu/g0_speed.json").read_text(encoding="utf-8"))["threshold_tok_s(0.5x median)"]
    pre = subprocess.run([sys.executable, str(guard), "precheck", "--version", "0.40.3", "--gpu-uuid", UUID, "--allow-loaded", "qwen3.8:27b",
                          "--out", str(rec / f"{tag}_gpu_precheck.json")])
    if pre.returncode != 0:
        raise SystemExit(1)
    proc = subprocess.Popen([sys.executable, str(HERE / "collect_teacher6v2.py"), "--targets", str(HERE / targets), "--out", str(out_dir),
                             "--summary", str(rec / f"{tag}_summary.json"), "--seed-base", str(seed_base)],
                            stdout=open(rec / f"{tag}_collect.log", "w"), stderr=subprocess.STDOUT)
    for _ in range(300):
        if (out_dir / "traces.jsonl").exists() or proc.poll() is not None:
            break
        time.sleep(2)
    g = subprocess.run([sys.executable, str(guard), "watch", "--gpu-uuid", UUID, "--pid", str(proc.pid), "--rows", str(out_dir / "traces.jsonl"),
                        "--model", "qwen3.8:27b", "--min-rate", str(thr), "--out", str(rec / f"{tag}_gpu_guard.json")],
                       stdout=open(rec / f"{tag}_gpu_guard.log", "w"), stderr=subprocess.STDOUT)
    rc = proc.wait()
    print(json.dumps({"collect_exit": rc, "guard_exit": g.returncode, "min_rate": thr}))
    if g.returncode != 0:
        if out_dir.exists():
            out_dir.rename(out_dir.with_name("ABORTED_" + out_dir.name))
        raise SystemExit(2)
    if rc != 0:
        raise SystemExit(rc)
    if a.job == "T0v2":
        raise SystemExit(subprocess.run([sys.executable, str(HERE / "analyze_t0v2.py"), "--main", str(main_dir)]).returncode)


if __name__ == "__main__":
    main()
