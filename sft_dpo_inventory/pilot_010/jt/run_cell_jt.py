# -*- coding: utf-8 -*-
"""pilot_010 JT(결정 271, PLAN_JT 3절) 교사 27B 셀 실행기: ``pilot_006_prep/gpu_data/run_cell6x_g1.py``(그대로 둠)의 사본(규칙 15).
바꾼 것(묶음·회차 seed·합치기·meta 형식은 같음):
(1) client = ``pilot_010/jt/vllm_eval_jt.py``(27B tokenizer·chat template). (2) ``--cond s|g1``: S = temperature 0.6(학생 주 측정), G1 = 0.2(JG 확정 조건);
    top-p 0.95·top-k 20·min-p 0·repetition penalty 1·회차 seed = seed_base + k는 둘 다 같다. ``--greedy`` 없음.
(3) ``--ports A[,B]``: 서버 두 벌에 나눠 보낸다. 문항 i → 묶음 i % C → 서버 (i % C) % len(ports). C가 짝수면 문항 i는 서버 i % 2(PLAN_JT 3절 나누는 규칙).
    서버마다 동시 요청은 C / len(ports). 묶음 j는 그 서버의 ``server_<port>.json``을 client에 넘기고, 요청 로그 요약은 서버마다 따로 적는다.
(4) ``--reference-date``(주면 client에 넘김: PF2 = 2026-10-26; 주지 않으면 client 기본값 = 원본 H-final 셀과 같음).
원 설명: pilot_010 JG(결정 270) 대체 조건 G1 실행기: ``run_cell6x.py``(그대로 둠)의 사본(규칙 15). 바꾼 것 하나: sampling temperature 0.6 → 0.2(top-p 0.95·top-k 20·min-p 0·repetition penalty 1·회차 seed 규칙은 같음). smoke에서 G0를 버릴 때만 쓴다.
원 설명: (세션 4) ``run_cell6w.py``의 사본. 고친 것 하나: ``--greedy``에서 ``--seed``도 넘기지 않는다(평가 도구는 seed도 sampling 값으로 보고 --do-sample 없이 주면 멈춤 — 6w greedy 작업이 모두 이 이유로 실패). 6w 설명: ``run_cell6v.py``의 사본. 더한 것: ``--seed-base``(sampling 회차 seed = seed_base + k, 기본 20261100 = 6v와 같음),
``--greedy``(sampling 인자 없이 temperature 0, 진단용 — 판정에 쓰지 않음). 그 밖은 6v와 같다.
원래 설명: (pilot_006 준비 J2·J4·J5) pilot_005/run_cell5v.py의 사본이다. 다른 것: 서버 기록·원문 위치를 인자로 받는다(``--work``, ``--raw-dir``),
``--grounding-target partial``이면 평가 client를 ``vllm_eval_partial6.py``로 바꾼다(J5). ``--sealed``(J2 봉인)이면 화면과 로그 끝 요약 줄에 정답률을 쓰지 않는다(items·wall만). 평가 client는 ``pilot_005/vllm_eval_thinking5.py`` 그대로.
표본 하나를 동시 요청으로 잰다.

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
ROOT = HERE.parents[2]
EVAL = HERE / "vllm_eval_jt.py"
sys.path.insert(0, str(ROOT))
GOLD = "sft_dpo_inventory/conversion_diag/selection_gold.yaml"
IDS = ROOT / "sft_dpo_inventory/pilot_003/selection/selection_v2_ids.txt"
PY = "/data/hwkim/sftdpo_work/runtime/envs/hf/bin/python"
TEMPERATURE = {"s": "0.6", "g1": "0.2"}


def sampling(cond):
    return ["--do-sample", "--temperature", TEMPERATURE[cond], "--top-p", "0.95", "--top-k", "20", "--min-p", "0", "--repetition-penalty", "1"]
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
    p.add_argument("--ports", required=True, help="서버 port 목록(쉼표), 예: 8700,8701")
    p.add_argument("--cond", choices=("s", "g1"), required=True)
    p.add_argument("--reference-date", default=None)
    p.add_argument("--seed-base", type=int, default=20261100)
    p.add_argument("--model", required=True, help="서버 모델 이름(base 또는 LoRA 이름)")
    p.add_argument("--label", required=True)
    p.add_argument("--k", type=int, required=True)
    p.add_argument("--concurrency", type=int, required=True)
    p.add_argument("--only", default=None)
    p.add_argument("--out-dir", required=True)
    p.add_argument("--gold", default=GOLD, help="평가 문항 파일(기본 selection_v2의 selection_gold). --only를 주지 않으면 selection_v2 id 목록")
    p.add_argument("--all-items", action="store_true", help="--only 없이 gold의 모든 문항(업체 100·aux·valid98 셀)")
    p.add_argument("--raw-dir", required=True)
    p.add_argument("--work", default="/data/hwkim/sftdpo_work/pilot_006_prep/vllm")
    p.add_argument("--sealed", action="store_true", help="정답률을 화면·요약 줄에 쓰지 않는다(J2 봉인)")
    args = p.parse_args()
    RAW, WORK = Path(args.raw_dir), Path(args.work)
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
    ports = [int(x) for x in args.ports.split(",")]
    start = datetime.now(ZoneInfo("Asia/Seoul")).replace(tzinfo=None)
    t0 = time.perf_counter()
    procs = []
    for j, shard in enumerate(shards):
        sp = out_dir / f".{args.label}_s{args.k}_part{j}"
        port = ports[j % len(ports)]
        cmd = [PY, str(EVAL), "--base-url", f"http://127.0.0.1:{port}",
               "--served-model", args.model, "--gold", args.gold, "--only", ",".join(shard), "--condition-check", *sampling(args.cond),
               "--seed", str(args.seed_base + args.k), "--server-meta", str(WORK / f"server_{port}.json"),
               *(["--reference-date", args.reference_date] if args.reference_date else []), "--out", f"{sp}.json", "--raw-out", str(RAW / f".{sp.name}_raw.jsonl")]
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
    sms = {p_: json.loads((WORK / f"server_{p_}.json").read_text(encoding="utf-8")) for p_ in ports}
    sm = sms[ports[0]]
    meta["vllm"]["concurrency"] = {"max_concurrent_requests": len(shards), "method": "items split i % C into C processes, sequential within a process; shard j -> server ports[j % len(ports)]",
                                   "shards": [len(s) for s in shards], "ports": ports, "shard_port": [ports[j % len(ports)] for j in range(len(shards))],
                                   "per_server_concurrency": {str(p_): sum(1 for j in range(len(shards)) if ports[j % len(ports)] == p_) for p_ in ports},
                                   "wall_seconds": round(wall, 1)}
    meta["vllm"]["servers"] = {str(p_): {k: v.get(k) for k in ("gpu_index", "gpu_uuid", "args", "log_attention_backend", "vllm", "server_log")} for p_, v in sms.items()}
    meta["jt"] = {"decision": 271, "plan": "sft_dpo_inventory/pilot_010/PLAN_JT.md", "cond": args.cond, "temperature": TEMPERATURE[args.cond],
                  "label": "교사 참고 측정(판정 아님); Qwen/Qwen3.8-27B BF16 (vLLM), Ollama qwen3.8:27b(Q4_K_M, aaee06c3)와 다른 빌드"}
    meta["vllm"]["kernels"] = {"precision": sm.get("precision"), "kernels": sm.get("kernels"),
                               "attention_backend(server log)": sm.get("log_attention_backend"),
                               "sampler(server log)": [l.split("] ", 1)[-1] for l in sm.get("log_flashinfer_sampler_lines", []) if "sampling" in l]}
    meta["vllm"]["request_log"] = {str(p_): request_log_summary(v["server_log"], start, end) for p_, v in sms.items()}
    meta["vllm"]["wall_seconds"] = round(wall, 1)
    result = {"meta": meta, "summary": EV._summary(merged_rows), "rows": merged_rows}
    final.write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    log = out_dir / f"{args.label}_s{args.k}.log"
    with open(log, "w", encoding="utf-8") as lg:
        for sp, _ in procs:
            lg.write(Path(f"{sp}.log").read_text(encoding="utf-8"))
        tail = {"items": len(merged_rows), "concurrency": len(shards), "wall_seconds": round(wall, 1), "request_log": meta["vllm"]["request_log"]}
        if not args.sealed:
            tail = {"items": len(merged_rows), "grounding_ok": sum(bool(r["grounding_ok"]) for r in merged_rows), **tail}
        lg.write(json.dumps(tail, ensure_ascii=False) + "\n")
    for sp, _ in procs:
        for f in (Path(f"{sp}.json"), Path(f"{sp}.log"), RAW / f".{sp.name}_raw.jsonl"):
            f.unlink(missing_ok=True)
    print(log.read_text(encoding="utf-8").splitlines()[-1])


if __name__ == "__main__":
    main()
