# -*- coding: utf-8 -*-
"""(pilot_005) 표본 하나를 동시 요청으로 잰다(결정 93·105). pilot_004/run_cell4.py의 사본이고 서버 기록·원문 위치만 pilot_005로 바꿨다.

    hfvenv/bin/python sft_dpo_inventory/serving_vllm_fp8/run_cell.py --port 8200 --model base --label vllm-bf16-base --k 1 \
        --concurrency 8 [--only IDS] [--out-dir runs]

- 문항을 C개 묶음으로 나눠(문항 순서의 i % C) ``serving_vllm/vllm_eval_thinking.py`` 프로세스 C개를 동시에 돌린다(묶음 안은 순차).
  그래서 서버에 들어가는 동시 요청은 최대 C개다. pipeline·채점·seed 규칙(회차 20261100+k, ``EV.call_seed``)은 순차 측정과 같다.
- 끝나면 묶음 결과를 문항 순서대로 합쳐 ``<out>/<label>_s<k>.json``(원문은 ignore 경로 ``<label>_s<k>_raw.jsonl``)로 쓰고 묶음 파일은 지운다.
- meta에 더하는 것: 동시 요청 수, 묶음, 서버 기록(정밀도·커널·로그에서 찾은 attention backend·sampler), 그 시간 동안의 서버 요청 로그 요약
  (요청 수, seed를 뺀 SamplingParams 종류와 수, LoRA 이름별 수). 요청 로그 원문은 저장소 밖에 있다.
- 출력이 있으면 멈춘다.
"""
import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
GOLD = "sft_dpo_inventory/conversion_diag/selection_gold.yaml"
IDS = ROOT / "sft_dpo_inventory/pilot_003/selection/selection_v2_ids.txt"
RAW = ROOT / "training/generated/pilot_005/raw"
WORK = Path("/data/hwkim/sftdpo_work/pilot_005/vllm")
PY = "/home/hwkim/sftdpo_work/hfvenv/bin/python"
SAMPLING = ["--do-sample", "--temperature", "0.6", "--top-p", "0.95", "--top-k", "20", "--min-p", "0", "--repetition-penalty", "1"]
LOG_TIME = re.compile(r"(\d\d)-(\d\d) (\d\d):(\d\d):(\d\d) \[request_logger")


def request_log_summary(server_log, start, end):
    """서버 로그에서 [start, end] 동안 들어온 completions 요청의 SamplingParams(seed 제외)와 LoRA를 센다."""
    params, loras, n = Counter(), Counter(), 0
    for line in Path(server_log).read_text(errors="replace").splitlines():
        m = LOG_TIME.search(line)
        if not m or "Received request cmpl-" not in line:
            continue
        mo, d, hh, mm, ss = map(int, m.groups())
        t = start.replace(month=mo, day=d, hour=hh, minute=mm, second=ss, microsecond=0)
        if not (start.replace(microsecond=0) <= t <= end):
            continue
        n += 1
        sp = re.search(r"params: SamplingParams\((.*?)\), lora_request", line)
        body = re.sub(r"seed=\d+, ", "seed=<call seed>, ", sp.group(1)) if sp else "unparsed"
        params[body] += 1
        lr = re.search(r"lora_name='([^']+)'", line)
        loras[lr.group(1) if lr else "None(base)"] += 1
    return {"requests": n, "sampling_params(seed masked)": dict(params), "lora": dict(loras)}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--port", type=int, required=True)
    p.add_argument("--model", required=True, help="서버 모델 이름(base 또는 LoRA 이름)")
    p.add_argument("--label", required=True)
    p.add_argument("--k", type=int, required=True)
    p.add_argument("--concurrency", type=int, required=True)
    p.add_argument("--only", default=None)
    p.add_argument("--out-dir", required=True)
    p.add_argument("--gold", default=GOLD, help="평가 문항 파일(기본 selection_v2의 selection_gold). --only를 주지 않으면 selection_v2 id 목록")
    p.add_argument("--all-items", action="store_true", help="--only 없이 gold의 모든 문항(업체 100·aux·valid98 셀)")
    args = p.parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    RAW.mkdir(parents=True, exist_ok=True)
    final = out_dir / f"{args.label}_s{args.k}.json"
    final_raw = RAW / f"{args.label}_s{args.k}_raw.jsonl"
    if final.exists() or final_raw.exists():
        raise SystemExit(f"{final} exists")
    if args.all_items:
        import evaluate_vendor100 as EV0
        ids = [i["id"] for i in EV0.load_gold(ROOT / args.gold)["items"]]
    else:
        ids = args.only.split(",") if args.only else IDS.read_text(encoding="utf-8").strip().split(",")
    shards = [ids[i::args.concurrency] for i in range(args.concurrency)]
    shards = [s for s in shards if s]
    server_meta = WORK / f"server_{args.port}.json"
    start = datetime.now(ZoneInfo("Asia/Seoul")).replace(tzinfo=None)
    t0 = time.perf_counter()
    procs = []
    for j, shard in enumerate(shards):
        sp = out_dir / f".{args.label}_s{args.k}_part{j}"
        cmd = [PY, str(ROOT / "sft_dpo_inventory/serving_vllm/vllm_eval_thinking.py"), "--base-url", f"http://127.0.0.1:{args.port}",
               "--served-model", args.model, "--gold", args.gold, "--only", ",".join(shard), "--condition-check", *SAMPLING,
               "--seed", str(20261100 + args.k), "--server-meta", str(server_meta), "--out", f"{sp}.json", "--raw-out", str(RAW / f".{sp.name}_raw.jsonl")]
        procs.append((sp, subprocess.Popen(cmd, cwd=ROOT, stdout=open(f"{sp}.log", "w"), stderr=subprocess.STDOUT)))
    codes = [pr.wait() for _, pr in procs]
    wall = time.perf_counter() - t0
    end = datetime.now(ZoneInfo("Asia/Seoul")).replace(tzinfo=None)
    if any(codes):
        raise SystemExit(f"shard failed: {codes} (part logs in {out_dir})")
    parts = [json.loads(Path(f"{sp}.json").read_text(encoding="utf-8")) for sp, _ in procs]
    rows = {r["id"]: r for d in parts for r in d["rows"]}
    if sorted(rows) != sorted(ids):
        raise SystemExit("merged items differ from requested items")
    import evaluate_vendor100 as EV
    merged_rows = [rows[i] for i in ids]
    with open(final_raw, "w", encoding="utf-8") as out:
        raws = {}
        for sp, _ in procs:
            for line in (RAW / f".{sp.name}_raw.jsonl").read_text(encoding="utf-8").splitlines():
                raws.setdefault(json.loads(line)["id"], []).append(line)
        for i in ids:
            for line in raws.get(i, []):
                out.write(line + "\n")
    meta = parts[0]["meta"]
    meta["item_order"] = ids
    meta["hf"]["raw_out"] = str(final_raw.resolve())
    meta["hf"]["raw_out_sha256"] = hashlib.sha256(final_raw.read_bytes()).hexdigest()
    sm = json.loads(server_meta.read_text(encoding="utf-8"))
    meta["vllm"]["concurrency"] = {"max_concurrent_requests": len(shards), "method": "items split i % C into C processes, sequential within a process",
                                   "shards": [len(s) for s in shards], "wall_seconds": round(wall, 1)}
    meta["vllm"]["kernels"] = {"precision": sm.get("precision"), "kernels": sm.get("kernels"),
                               "attention_backend(server log)": sm.get("log_attention_backend"),
                               "sampler(server log)": [l.split("] ", 1)[-1] for l in sm.get("log_flashinfer_sampler_lines", []) if "sampling" in l]}
    meta["vllm"]["request_log"] = request_log_summary(sm["server_log"], start, end)
    meta["vllm"]["wall_seconds"] = round(wall, 1)
    result = {"meta": meta, "summary": EV._summary(merged_rows), "rows": merged_rows}
    final.write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    log = out_dir / f"{args.label}_s{args.k}.log"
    with open(log, "w", encoding="utf-8") as lg:
        for sp, _ in procs:
            lg.write(Path(f"{sp}.log").read_text(encoding="utf-8"))
        lg.write(json.dumps({"items": len(merged_rows), "grounding_ok": sum(bool(r["grounding_ok"]) for r in merged_rows),
                             "concurrency": len(shards), "wall_seconds": round(wall, 1), "request_log": meta["vllm"]["request_log"]},
                            ensure_ascii=False) + "\n")
    for sp, _ in procs:
        for f in (Path(f"{sp}.json"), Path(f"{sp}.log"), RAW / f".{sp.name}_raw.jsonl"):
            f.unlink(missing_ok=True)
    print(log.read_text(encoding="utf-8").splitlines()[-1])


if __name__ == "__main__":
    main()
