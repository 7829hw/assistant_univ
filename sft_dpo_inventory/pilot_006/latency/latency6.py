# -*- coding: utf-8 -*-
"""pilot_006 지연 측정 도구(C8, 결정 113 D8, PROTOCOL_v4 6절). base·F·P를 **한 GPU의 한 서버**에서 순차 고정 30문항(동시 요청 1)으로 연달아 잰다.

    hfvenv/bin/python latency6.py --port P --gpu-index N --f-model F_LORA --p-model P_LORA --out-dir DIR --raw-dir DIR [--work DIR]
    hfvenv/bin/python latency6.py --test-fake --out-dir /tmp/x --raw-dir /tmp/x/raw     # GPU 없이 가짜 서버로 도구만 검증

- 서버는 미리 띄워 둔다(``serve6b.sh``, ``LORAS="F=… P=…"``, 결정 117의 17,408). 이 도구는 서버를 띄우거나 내리지 않는다.
- 셀: ``run_cell6v.py``(``pilot_006_prep/gpu``)를 ``--concurrency 1 --k 1 --only <latency_ids>``로 base(Full prompt), F(Full), P(Partial prompt) 순서로 부른다.
  고정 30문항 = ``serving_vllm_fp8/latency_ids.txt``(pilot_005와 같음). seed 규칙은 셀과 같다(회차 20261101).
- 다른 GPU 확인(지시 5.1 7·C8): 시작 전과 셀마다, 그리고 측정 중 30초마다 host ``nvidia-smi``로 **측정 GPU가 아닌 두 GPU**에 compute 프로세스가 없는지 본다.
  하나라도 있으면 측정을 멈추고(실행 중 셀 프로세스 종료) exit 3, 기록에 남긴다.
- 기록(``latency_summary.json``): 셀별 문항 모델 시간(호출 ``server_seconds`` 합) 중앙값, base 대비 비(D8 ≤ 1.5), 생성 token 중앙값,
  thinking·최종 JSON token 중앙값(원문을 Qwen3-8B tokenizer로 나눔, ``gates/compute_gates.token_parts``), 입력 token, 서버 로그의 셀 구간 prefix cache 적중률.
- ``--test-fake``: 표준 라이브러리 HTTP로 OpenAI 호환 가짜 서버(``/v1/completions``, ``/v1/models``, ``/version``)를 띄우고, 고정 응답(thinking + Full JSON)을
  token id로 돌려준다. 다른 GPU 확인은 건너뛴다(시험 표시). 도구의 흐름과 기록 형식만 검증하며 측정값은 의미가 없다.
"""
import argparse
import json
import re
import statistics
import subprocess
import sys
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/thinking_prep_001"))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_006/gates"))
PY = "/home/hwkim/sftdpo_work/hfvenv/bin/python"
RUNCELL = ROOT / "sft_dpo_inventory/pilot_006_prep/gpu/run_cell6v.py"
LAT_IDS = (ROOT / "sft_dpo_inventory/serving_vllm_fp8/latency_ids.txt").read_text(encoding="utf-8").strip()
HIT = re.compile(r"(\d\d)-(\d\d) (\d\d):(\d\d):(\d\d) .*Prefix cache hit rate: ([\d.]+)%")


def now():
    return datetime.now(ZoneInfo("Asia/Seoul")).replace(tzinfo=None)


def other_gpu_procs(gpu_index):
    rows = subprocess.run(["nvidia-smi", "--query-compute-apps=gpu_uuid,pid,process_name", "--format=csv,noheader"], capture_output=True, text=True).stdout
    me = subprocess.run(["nvidia-smi", "-i", str(gpu_index), "--query-gpu=uuid", "--format=csv,noheader"], capture_output=True, text=True).stdout.strip()
    return [r.strip() for r in rows.splitlines() if r.strip() and not r.startswith(me)]


def hit_rates(server_log, start, end):
    vals = []
    for line in Path(server_log).read_text(errors="replace").splitlines():
        m = HIT.search(line)
        if not m:
            continue
        mo, d, hh, mm, ss, v = m.groups()
        t = start.replace(month=int(mo), day=int(d), hour=int(hh), minute=int(mm), second=int(ss), microsecond=0)
        if start.replace(microsecond=0) <= t <= end:
            vals.append(float(v))
    return {"samples": len(vals), "last": vals[-1] if vals else None, "max": max(vals) if vals else None}


def fake_server(port, work):
    from transformers import AutoTokenizer
    import hf_thinking as H
    tok = AutoTokenizer.from_pretrained(H.MODEL, revision=H.REVISION)
    answer = ('<think>\n질문의 장소와 측정값을 확인한다.\n</think>\n\n{"concepts": [{"id": "speed", "concept": "AMOUNT", "subtype": "speed", "role": "MEASURE", '
              '"source": "implicit"}], "factors": {"aggregation": "avg"}}')
    ids = tok(answer, add_special_tokens=False)["input_ids"] + [tok.convert_tokens_to_ids("<|im_end|>")]

    class H_(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, obj):
            body = json.dumps(obj).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            self._send({"version": "fake"} if self.path == "/version" else {"data": [{"id": "base"}, {"id": "F"}, {"id": "P"}]})

        def do_POST(self):
            req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            time.sleep(0.02)
            self._send({"choices": [{"token_ids": ids, "prompt_token_ids": req["prompt"], "finish_reason": "stop"}]})

    srv = ThreadingHTTPServer(("127.0.0.1", port), H_)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    log = Path(work) / f"server_{port}_fake.log"
    log.write_text("", encoding="utf-8")
    (Path(work) / f"server_{port}.json").write_text(json.dumps({"precision": "fake", "kernels": "fake", "gpu_uuid": "fake", "server_log": str(log),
                                                               "log_attention_backend": [], "log_flashinfer_sampler_lines": [], "args": [],
                                                               "vllm": "fake", "lora_adapter_sha256": {}}), encoding="utf-8")
    return srv


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, default=8690)
    p.add_argument("--gpu-index", default="0")
    p.add_argument("--f-model", default="F")
    p.add_argument("--p-model", default="P")
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
    for label, model, target in (("base", "base", "full"), ("F", a.f_model, "full"), ("P", a.p_model, "partial")):
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
