# -*- coding: utf-8 -*-
"""최종 판정 지연 창(결정 214 V4): ``pilot_006/latency/latency6.py``(고정본, 그대로 둠)의 사본 — base → 후보(F) 두 셀만 순차로 잰다(P 셀 없음).
고정 30문항(``serving_vllm_fp8/latency_ids.txt``, PROTOCOL_v4 6절, protected_final_v1 아님), 동시 1, 한 서버·한 GPU, 측정 중 30초마다 다른 두 GPU가 비었는지 확인.
나머지(셀 실행기 ``run_cell6v.py``, 요약 ``latency_summary.json``, 지연 비 = 문항 모델 시간 중앙값 / base)는 latency6과 같다.

    hfvenv/bin/python latency_final.py --port P --gpu-index I --f-model <후보 LoRA 이름> --out-dir D --raw-dir R --label-prefix latF
"""
import argparse
import json
import statistics
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "pilot_006/latency"))
from latency6 import LAT_IDS, PY, ROOT, RUNCELL, fake_server, hit_rates, now, other_gpu_procs  # noqa: E402,F401


def main():  # latency6.main 사본, P 셀만 뺌
    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, default=8690)
    p.add_argument("--gpu-index", default="0")
    p.add_argument("--f-model", default="F")
    p.add_argument("--out-dir", required=True)
    p.add_argument("--raw-dir", required=True)
    p.add_argument("--work", default="/data/hwkim/sftdpo_work/pilot_006_prep/vllm")
    p.add_argument("--label-prefix", default="lat6")
    p.add_argument("--test-fake", action="store_true")
    a = p.parse_args()
    out_dir, raw_dir, work = Path(a.out_dir), Path(a.raw_dir), Path(a.work)
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)
    if a.test_fake:
        work = out_dir / "work"
        work.mkdir(exist_ok=True)
        fake_server(a.port, work)
    record = {"started": now().isoformat(), "test_fake": a.test_fake, "gpu_index": a.gpu_index, "port": a.port, "ids": LAT_IDS.split(","), "cells": {}}
    if not a.test_fake and other_gpu_procs(a.gpu_index):
        record["stopped"] = {"at": "before start", "other_gpu_processes": other_gpu_procs(a.gpu_index)}
        (out_dir / "latency_summary.json").write_text(json.dumps(record, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        raise SystemExit(3)
    server = json.loads((work / f"server_{a.port}.json").read_text(encoding="utf-8"))
    for label, model, target in (("base", "base", "full"), ("F", a.f_model, "full")):  # 최종 판정: base → 후보(F)만
        start = now()
        cmd = [PY, str(RUNCELL), "--port", str(a.port), "--model", model, "--label", f"{a.label_prefix}-{label}", "--k", "1", "--concurrency", "1",
               "--only", LAT_IDS, "--grounding-target", target, "--out-dir", str(out_dir), "--raw-dir", str(raw_dir), "--work", str(work)]
        proc = subprocess.Popen(cmd, cwd=str(ROOT), stdout=open(out_dir / f"{a.label_prefix}-{label}.stdout", "w"), stderr=subprocess.STDOUT)
        violation = None
        while proc.poll() is None:
            time.sleep(5 if a.test_fake else 30)
            if not a.test_fake and other_gpu_procs(a.gpu_index):
                violation = other_gpu_procs(a.gpu_index)
                proc.terminate()
                break
        rc = proc.wait()
        end = now()
        if violation or rc != 0:
            record["stopped"] = {"at": label, "exit": rc, "other_gpu_processes": violation}
            break
        cell = json.loads((out_dir / f"{a.label_prefix}-{label}_s1.json").read_text(encoding="utf-8"))
        import compute_gates as CG
        parts = CG.token_parts(None, cell["meta"])
        secs = [sum(c["server_seconds"] for c in r["hf_calls"]) for r in cell["rows"]]
        record["cells"][label] = {"model": model, "grounding_target": target, "items": len(cell["rows"]),
                                  "median_model_seconds": round(statistics.median(secs), 3),
                                  "median_generated_tokens": statistics.median(sum(c["generated_tokens"] for c in r["hf_calls"]) for r in cell["rows"]),
                                  "median_input_tokens": statistics.median(r["hf_calls"][0]["prompt_tokens"] for r in cell["rows"] if r["hf_calls"]),
                                  "median_thinking_tokens": statistics.median(v["thinking"] for v in parts.values()) if parts else None,
                                  "median_json_tokens": statistics.median(v["json"] for v in parts.values()) if parts else None,
                                  "prefix_cache_hit_rate(server log)": hit_rates(server["server_log"], start, end), "start": start.isoformat(), "end": end.isoformat()}
    if "base" in record["cells"]:
        b = record["cells"]["base"]["median_model_seconds"]
        record["ratio_vs_base"] = {k: round(v["median_model_seconds"] / b, 3) for k, v in record["cells"].items() if k != "base"}
        record["d8_pass(≤1.5)"] = {k: v <= 1.5 for k, v in record["ratio_vs_base"].items()}
    record["finished"] = now().isoformat()
    (out_dir / "latency_summary.json").write_text(json.dumps(record, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: record[k] for k in ("cells", "ratio_vs_base") if k in record}, ensure_ascii=False, indent=1))
    raise SystemExit(0 if "stopped" not in record else 3)


if __name__ == "__main__":
    main()
