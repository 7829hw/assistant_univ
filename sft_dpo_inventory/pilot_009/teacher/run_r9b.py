# -*- coding: utf-8 -*-
"""pilot_009 teacher 실행기 2판(``run_r9.py``의 사본, 그 파일은 그대로; ``PLAN_DEVIATIONS.md`` 1). 바꾼 것: precheck 뒤 **warm-up 요청 1회**.
T-R 시도 1은 첫 호출(모델 처음 올림: load 34 s, prompt 934 token에 23 s)이 28.8 tok/s로 guard(33.71)에 걸려 멈췄다(100% GPU 확인됨, ``ABORTED_*``).
O1 기록(첫 짧은 생성 14.61 tok/s, 나머지 약 67)과 같은 냉시작 현상으로 보고, 수집 전에 같은 teacher 요청(첫 문항, seed = seed_base − 1)을 한 번 보내
모델을 올린 뒤 수집한다. warm-up 응답은 trace에 넣지 않고 속도·``/api/ps``(size_vram == size)만 ``{tag}_warmup.json``에 남긴다. guard 기준·검사·통과 규칙은 그대로.
원 설명: 결정 55 precheck(0.40.6) → 수집 + guard watch(O1 기준 33.71 tok/s) → 분석(``analyze_r9.py``).

    hfvenv/bin/python run_r9b.py --main /home/hwkim/assistant_univ --job T-R|TEACH-R

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


def warmup(rec, targets, seed, tag):
    """teacher 요청 1회(첫 문항). trace가 아니다. digest가 다르면 요청하지 않음."""
    import httpx
    sys.path.insert(0, str(HERE))
    sys.path.insert(0, str(HERE.parents[2]))
    import collect_r9 as C
    import teacher_refusal9 as T
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
    warm = warmup(rec, targets, seed_base - 1, tag)
    if not warm["ok"]:
        raise SystemExit(5)
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
