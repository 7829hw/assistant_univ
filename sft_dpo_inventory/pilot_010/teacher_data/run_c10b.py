# -*- coding: utf-8 -*-
"""pilot_010 teacher 실행기 2판(T-C2·TEACH-C, 결정 248·249). ``run_c10.py``(그대로; 그 자체가 ``pilot_009/teacher/run_r9b.py``의 사본)의 사본: 결정 55 precheck(0.40.6) → warm-up 요청 1회(trace 아님)
→ 수집(``collect_c10.py``) + guard watch(O1 기준 33.71 tok/s) → 분석(``analyze_c10.py``). 바꾼 것(run_c10 대비): 지시·검사(``teacher_contrast10b``), 수집기 ``collect_c10b.py``, 분석 ``analyze_c10b.py``, T-C2 판정 파일 ``tc2_verdict.json``. run_r9b 대비: 지시·검사, 경로(pilot_010),
끝난 뒤 ``/api/ps``가 빌 때까지 기다림(모델을 내리지 않음, keep_alive가 끝나기를 기다리기만; 결과를 ``{tag}_ps_after.json``에 기록).

    hfvenv/bin/python run_c10b.py --main /home/hwkim/assistant_univ --job T-C2|TEACH-C

- TEACH-C는 ``tc2_verdict.json``의 ``passed``가 true이고 ``teachc_targets.json``이 있을 때만 시작한다(아니면 모델 호출 없이 exit 3).
- 원문 ``training/generated/pilot_010/teacher_{tc2,teachc}/``, 기록 ``pilot_010/teacher/``. PID ``/data/hwkim/sftdpo_work/pids/{job}_collect.pid``.
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
PIDS = Path("/data/hwkim/sftdpo_work/pids")
JOBS = {"T-C2": ("tc2", "tc2_targets.json", 20271031), "TEACH-C": ("teachc", "teachc_targets.json", 20272027)}


def warmup(rec, targets, seed, tag):
    """teacher 요청 1회(첫 문항). trace가 아니다. digest가 다르면 요청하지 않음."""
    import httpx
    sys.path.insert(0, str(HERE))
    sys.path.insert(0, str(HERE.parents[2]))
    import collect_c10b as C
    import teacher_contrast10b as T
    from ollama_client import OllamaClient
    info = next(m for m in httpx.get(f"{C.HOST}/api/tags", timeout=10).json()["models"] if m["name"] == C.MODEL)
    out = {"model": C.MODEL, "digest": info["digest"], "seed": seed, "use": "warm-up only, not a trace"}
    if info["digest"] != C.DIGEST:
        out.update(ok=False, error="model digest differs")
    else:
        t = json.loads(Path(targets).read_text(encoding="utf-8"))[0]
        r = OllamaClient(C.HOST, C.MODEL, {"temperature": C.TEMPERATURE, "seed": seed}, chat_timeout=1800.0, think=True).chat(T.messages(t))
        ps = httpx.get(f"{C.HOST}/api/ps", timeout=10).json().get("models") or []
        m = next((x for x in ps if x.get("name") == C.MODEL), {})
        ev, ed = r.get("eval_count"), r.get("eval_duration")
        out.update(target=t["id"], eval_count=ev, eval_tok_s=round(ev / (ed / 1e9), 2) if ev and ed else None,
                   load_duration_ms=round((r.get("load_duration") or 0) / 1e6, 1), prompt_eval_count=r.get("prompt_eval_count"),
                   prompt_eval_duration_ms=round((r.get("prompt_eval_duration") or 0) / 1e6, 1), size=m.get("size"), size_vram=m.get("size_vram"),
                   gpu_100=bool(m) and m.get("size") == m.get("size_vram"), ok=bool(m) and m.get("size") == m.get("size_vram"))
    (rec / f"{tag}_warmup.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False))
    return out


def wait_ps_empty(rec, tag, limit_s=3600):
    """수집이 끝난 뒤 /api/ps가 빌 때까지 기다린다(모델을 내리지 않음). 결과를 기록."""
    import httpx
    t0, seen = time.time(), None
    while time.time() - t0 < limit_s:
        try:
            seen = httpx.get("http://localhost:11434/api/ps", timeout=10).json().get("models") or []
        except Exception as error:  # noqa: BLE001
            seen = [f"error:{type(error).__name__}"]
        if not seen:
            break
        time.sleep(30)
    out = {"empty": not seen, "waited_s": round(time.time() - t0, 1), "last": [m.get("name") if isinstance(m, dict) else m for m in (seen or [])]}
    (rec / f"{tag}_ps_after.json").write_text(json.dumps(out, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False))
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--main", required=True)
    p.add_argument("--job", required=True, choices=sorted(JOBS))
    a = p.parse_args()
    main_dir = Path(a.main)
    rec = main_dir / "sft_dpo_inventory/pilot_010/teacher"
    tag, targets_name, seed_base = JOBS[a.job]
    targets = rec / targets_name
    if a.job == "TEACH-C":
        v = rec / "tc2_verdict.json"
        passed = json.loads(v.read_text(encoding="utf-8")).get("passed") if v.exists() else None
        if passed is not True or not targets.exists():
            print(json.dumps({"job": a.job, "skip": True, "tr_passed": passed, "targets": targets.exists()}))
            raise SystemExit(3)
    guard = HERE.parents[2] / "sft_dpo_inventory/pilot_002/ollama_gpu_guard.py"
    out_dir = main_dir / f"training/generated/pilot_010/teacher_{tag}"
    thr = json.loads((main_dir / "sft_dpo_inventory/pilot_006/post/o1_speed.json").read_text(encoding="utf-8"))["threshold_tok_s(0.5x median)"]
    pre = subprocess.run([sys.executable, str(guard), "precheck", "--version", "0.40.6", "--gpu-uuid", UUID, "--allow-loaded", "qwen3.8:27b",
                          "--out", str(rec / f"{tag}_gpu_precheck.json")])
    if pre.returncode != 0:
        raise SystemExit(1)
    warm = warmup(rec, targets, seed_base - 1, tag)
    if not warm["ok"]:
        raise SystemExit(5)
    out_dir.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.Popen([sys.executable, str(HERE / "collect_c10b.py"), "--targets", str(targets), "--out", str(out_dir),
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
    wait_ps_empty(rec, tag)
    print(json.dumps({"job": a.job, "collect_exit": rc, "guard_exit": g.returncode, "min_rate": thr}))
    if g.returncode != 0:
        if out_dir.exists():
            out_dir.rename(out_dir.with_name("ABORTED_" + out_dir.name))
        raise SystemExit(2)
    if rc != 0:
        raise SystemExit(rc)
    raise SystemExit(subprocess.run([sys.executable, str(HERE / "analyze_c10b.py"), "--main", str(main_dir), "--job", a.job]).returncode)


if __name__ == "__main__":
    main()
