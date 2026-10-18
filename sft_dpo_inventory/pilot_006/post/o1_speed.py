# -*- coding: utf-8 -*-
"""O1(결정 163 N5, 세션 4): ``g0_speed.py``의 사본. Ollama **0.40.6**에서 qwen3.8:27b 속도를 다시 재고 0.40.6 전용 27b guard 기준(중앙값 × 0.5)을 정한다.
0.40.3 기준 33.55 tok/s는 0.40.3 전용으로 남긴다. Ollama GPU(48f798cc)에서만.

    hfvenv/bin/python /abs/.../o1_speed.py --main /home/hwkim/assistant_univ

1. 결정 55 precheck(``pilot_002/ollama_gpu_guard.py precheck --version 0.40.3``: 컨테이너가 Ollama GPU를 봄, 올라간 모델 없음, 그 GPU에 다른 프로세스 없음).
2. 짧은 생성 5회(``/api/generate``, 같은 짧은 prompt, think false, temperature 0, num_predict 256, seed 1–5). 첫 호출 뒤 ``/api/ps``로
   ``size_vram == size``(PROCESSOR 100% GPU)를 확인하고 ``docker exec ollama ollama ps``도 남긴다.
3. 호출마다 eval_count / eval_duration(tok/s). 중앙값 × 0.5를 27b guard 기준으로 ``pilot_006/PLAN_DEVIATIONS.md``에 적는다(T0 시작 전).
   100% GPU가 아니면 기준을 쓰지 않고 exit 2.
모델을 직접 내리지 않는다(keep_alive 기본값). 출력: ``pilot_006_prep/gpu/g0_speed.json``.
"""
import argparse
import json
import statistics
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

HOST = "http://localhost:11434"
MODEL = "qwen3.8:27b"
UUID = "GPU-48f798cc-9437-50ac-d604-448bbad7b311"
PROMPT = "택시 운행 기록을 분석할 때 승차 지점과 하차 지점을 구분해야 하는 이유를 세 문장으로 설명해 주세요."


def now():
    return datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--main", required=True)
    a = p.parse_args()
    main_dir = Path(a.main)
    post = main_dir / "sft_dpo_inventory/pilot_006/post"
    guard = main_dir / "sft_dpo_inventory/pilot_002/ollama_gpu_guard.py"
    pre = subprocess.run([sys.executable, str(guard), "precheck", "--version", "0.40.6", "--gpu-uuid", UUID,
                          "--out", str(post / "o1_precheck.json")], capture_output=True, text=True)
    if pre.returncode != 0:
        print(pre.stdout, pre.stderr)
        raise SystemExit(1)
    version = httpx.get(f"{HOST}/api/version", timeout=10).json()["version"]
    digest = next(m["digest"] for m in httpx.get(f"{HOST}/api/tags", timeout=10).json()["models"] if m["name"] == MODEL)
    calls, gpu = [], None
    for seed in range(1, 6):
        t0 = time.perf_counter()
        r = httpx.post(f"{HOST}/api/generate", timeout=1800, json={"model": MODEL, "prompt": PROMPT, "stream": False, "think": False,
                                                                   "options": {"temperature": 0, "seed": seed, "num_predict": 256}}).json()
        rate = r["eval_count"] / (r["eval_duration"] / 1e9) if r.get("eval_duration") else None
        calls.append({"seed": seed, "eval_count": r.get("eval_count"), "eval_duration_ms": round(r.get("eval_duration", 0) / 1e6, 1),
                      "load_duration_ms": round(r.get("load_duration", 0) / 1e6, 1), "tok_s": round(rate, 2) if rate else None,
                      "wall_s": round(time.perf_counter() - t0, 2), "done_reason": r.get("done_reason")})
        if gpu is None:
            ps = httpx.get(f"{HOST}/api/ps", timeout=10).json()["models"]
            m = next((x for x in ps if x["name"] == MODEL), {})
            gpu = {"at": now(), "size": m.get("size"), "size_vram": m.get("size_vram"),
                   "gpu_100": bool(m.get("size")) and m.get("size") == m.get("size_vram"),
                   "ollama_ps": subprocess.run(["docker", "exec", "ollama", "ollama", "ps"], capture_output=True, text=True).stdout,
                   "host_gpu": subprocess.run(["nvidia-smi", "-i", UUID, "--query-compute-apps=pid,process_name,used_memory", "--format=csv,noheader"],
                                              capture_output=True, text=True).stdout.strip()}
    rates = [c["tok_s"] for c in calls if c["tok_s"]]
    med = statistics.median(rates)
    out = {"decision": "163(N5) — 126(F5) 방식, 0.40.6 전용", "model": MODEL, "digest": digest, "ollama_version": version, "gpu_uuid": UUID, "at": now(),
           "gpu_check": gpu, "calls": calls, "median_tok_s": round(med, 2), "threshold_tok_s(0.5x median)": round(0.5 * med, 2)}
    (post / "o1_speed.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    if not gpu["gpu_100"]:
        print("not 100% GPU", json.dumps(gpu, ensure_ascii=False))
        raise SystemExit(2)
    (post / "O1.md").write_text(f"# O1: Ollama {version} 27b 속도 기준(결정 163, {out['at']})\n\n"
                                f"- `{MODEL}`(digest `{digest[:12]}`), GPU `{UUID}`, 첫 호출 뒤 100% GPU: {gpu['gpu_100']}.\n"
                                f"- 짧은 생성 5회 tok/s: {', '.join(str(r) for r in rates)} → 중앙값 {med:.2f}.\n"
                                f"- **0.40.6 전용 27b guard 기준 = {0.5 * med:.2f} tok/s**. 0.40.3 기준 33.55는 0.40.3 전용으로 남긴다.\n", encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("median_tok_s", "threshold_tok_s(0.5x median)")}, ensure_ascii=False), gpu["gpu_100"])


if __name__ == "__main__":
    main()
