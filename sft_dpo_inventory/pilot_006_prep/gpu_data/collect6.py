# -*- coding: utf-8 -*-
"""pilot_006 준비 vLLM base 수집(J1·J3·J7 Full prompt, J6 Partial prompt). 학습 없음, 필터·import 없음, 승인 아님.

    hfvenv/bin/python sft_dpo_inventory/pilot_006_prep/gpu_data/collect6.py --mode self|first --port P --inputs JSONL \
        --raw-out RAW.jsonl --out OUT.json [--samples 8] [--round-seed 20261015] [--concurrency 8] [--server-meta DIR]

- 서버: ``serve6.sh``(vLLM 0.30.0, BF16, flashinfer attention·sampler, PROTOCOL_v5와 같은 서버 인자). base(adapter 없음) 요청만 보낸다.
- 입력: 현재 planner messages(prompt 87048d0c, ``GeoFlowPlanner.messages``)를 HF ``render_prompt``(enable_thinking) id열로 ``/v1/completions``에 넘긴다
  (``serving_vllm/vllm_thinking.py``, batch007과 같음).
- ``--mode self``(J1, 결정 98 방식의 8b 자체 표본): pilot_004 8b 자체 출처(pilot_003 trace)와 같은 설정 — 문항당 **greedy 1 + 표본 8**,
  temperature 0.6, top_p 0.95, top_k 20(+ vLLM에서 min_p 0, repetition_penalty 1, presence·frequency 0; ``pilot_004/realtrip``과 같음), max_tokens 8192.
  표본 s(1..N)의 seed = ``EV.call_seed(round_seed, 문항 id, s)``. 원문만 ``--raw-out``(ignore)에 쓰고 판정·필터는 하지 않는다. ``--out``은 manifest.
- ``--mode first``(J3·J7, batch007과 같은 방식): 문항마다 greedy 첫 응답 하나. ``thinking_prep_001/collect_traces.judge``로 입력의 gold와 비교한
  결과를 ``--out``(jsonl, 원문 없이 sha256·길이·파싱한 JSON·채점)에 쓴다. gold는 승인이 아니다(초안·역산).
- vLLM은 seed로 바이트 재현되지 않는다(결정 93). 동시 요청 최대 C개(작업자마다 client 하나). 결과는 끝나는 대로 원문 파일에 한 줄씩 쓴다.
- ``--grounding-target partial``(J6): messages를 ``grounding.make_planner("partial")``(P0.3 prompt, system prompt ``8b157c9a``)로 만든다.
  그 밖(문항, 표본 수, sampling, seed 규칙)은 J1과 같다(지시 5.3: J1과 같은 sampling 설정). 기본값 full은 J1과 같다.
- 출력이 있으면 멈춘다.
"""
import argparse
import hashlib
import json
import sys
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/thinking_prep_001"))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/serving_vllm"))

SAMPLING = {"temperature": 0.6, "top_p": 0.95, "top_k": 20, "min_p": 0.0, "repetition_penalty": 1.0}
KEEP = ("raw_text", "raw_sha256", "generated_ids", "thinking", "content", "think_closed", "prompt_tokens", "generated_tokens",
        "done_reason", "finish_reason", "prompt_ids_echo_equal", "server_seconds")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--mode", choices=("self", "first"), required=True)
    p.add_argument("--port", type=int, required=True)
    p.add_argument("--inputs", required=True)
    p.add_argument("--raw-out", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--samples", type=int, default=8)
    p.add_argument("--round-seed", type=int, default=20261015)
    p.add_argument("--concurrency", type=int, default=8)
    p.add_argument("--server-meta", default="/data/hwkim/sftdpo_work/pilot_006_prep/vllm")
    p.add_argument("--label", default="")
    p.add_argument("--grounding-target", choices=("full", "partial"), default="full")
    args = p.parse_args()
    import collect_traces as T
    import evaluate_vendor100 as EV
    import execution_spec
    import grounding as GT
    from training.data.common import check_expected_prompt
    from vllm_thinking import VLLMThinkingClient

    raw_out, out = Path(args.raw_out), Path(args.out)
    if raw_out.exists() or out.exists():
        raise SystemExit(f"{raw_out} or {out} exists (다시 재지 않는다)")
    raw_out.parent.mkdir(parents=True, exist_ok=True)
    out.parent.mkdir(parents=True, exist_ok=True)
    prompt_hash = check_expected_prompt()
    planner = GT.make_planner(args.grounding_target, client=None)
    system_sha = hashlib.sha256(planner.system_prompt().encode("utf-8")).hexdigest()
    items = [json.loads(line) for line in Path(args.inputs).read_text(encoding="utf-8").splitlines() if line.strip()]
    server = json.loads((Path(args.server_meta) / f"server_{args.port}.json").read_text(encoding="utf-8"))
    jobs = []
    for item in items:
        jobs.append((item, 0))
        if args.mode == "self":
            jobs += [(item, s) for s in range(1, args.samples + 1)]
    pool = [VLLMThinkingClient(f"http://127.0.0.1:{args.port}", "base") for _ in range(args.concurrency)]
    lock = threading.Lock()
    raw_stream = raw_out.open("w", encoding="utf-8")
    started_at = datetime.now(ZoneInfo("Asia/Seoul")).isoformat()

    def run(job):
        item, s = job
        with lock:
            client = pool.pop()
        try:
            seed = None if s == 0 else EV.call_seed(args.round_seed, item["id"], s)
            t0 = time.perf_counter()
            result = client.generate(planner.messages(item["question"]), sample=s > 0, seed=seed, sampling=SAMPLING if s else None)
            secs = time.perf_counter() - t0
        finally:
            with lock:
                pool.append(client)
        row = {"trace_id": f"{item['id']}:{'greedy' if s == 0 else 'sample'}:{s}", "id": item["id"], "source": item.get("source"),
               "kind": "greedy" if s == 0 else "sample", "sample_index": s, "seed": seed,
               **{k: result[k] for k in KEEP}, "seconds": round(secs, 2)}
        with lock:
            raw_stream.write(json.dumps(row, ensure_ascii=False) + "\n")
            raw_stream.flush()
        return item, s, result, secs

    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        results = list(ex.map(run, jobs))
    wall = time.perf_counter() - t0
    raw_stream.close()
    runtime = {"label": args.label, "mode": args.mode, "engine": "vllm", "vllm": server.get("vllm"), "flashinfer": server.get("flashinfer"),
               "torch": server.get("torch"), "transformers": server.get("transformers"),
               "model": "Qwen/Qwen3-8B@b968826d9c46dd6066d109eabc6255188de91218", "adapter": None, "precision": server.get("precision"),
               "kernels": {"attention_backend(server log)": server.get("log_attention_backend"),
                           "sampler(server log)": server.get("log_flashinfer_sampler_lines")},
               "device_uuid": server.get("gpu_uuid"), "server_args": server.get("args"),
               "decoding": {"greedy_per_question": 1, "samples_per_question": args.samples if args.mode == "self" else 0,
                            "sampling": SAMPLING, "presence_penalty": 0.0, "frequency_penalty": 0.0, "max_tokens": 8192,
                            "round_seed": args.round_seed if args.mode == "self" else None, "seed_rule": "EV.call_seed(round_seed, id, s)",
                            "seed_reproducible": False,
                            "source_of_setting": "pilot_004 8b 자체 출처 = pilot_003 trace(greedy 1 + 표본 8, 0.6/0.95/20, 8192), vLLM 인자는 pilot_004/realtrip"},
               "enable_thinking": True, "grounding_target": args.grounding_target,
               "prompt": "Full(GeoFlowPlanner.messages)" if args.grounding_target == "full" else "Partial P0.3(grounding.make_planner)",
               "prompt_sha256": prompt_hash, "system_prompt_sha256": system_sha,
               "partial_fingerprint": GT.partial_fingerprint() if args.grounding_target == "partial" else None,
               "code_fingerprint": execution_spec.code_fingerprint(ROOT)["sha256"], "code_root": str(ROOT),
               "concurrency": args.concurrency, "wall_seconds": round(wall, 1), "inputs": str(args.inputs), "inputs_sha256": sha(args.inputs),
               "raw_out": str(raw_out), "raw_out_sha256": sha(raw_out), "started_at": started_at,
               "finished_at": datetime.now(ZoneInfo("Asia/Seoul")).isoformat()}
    if args.mode == "self":
        per_q = Counter(item["id"] for item, _, _, _ in results)
        manifest = {"runtime": runtime, "questions": len(items), "generations": len(results),
                    "by_source": dict(Counter(item.get("source") for item, s, _, _ in results if s == 0)),
                    "per_question_generations": sorted(set(per_q.values())),
                    "done_reason": dict(Counter(r["done_reason"] for _, _, r, _ in results)),
                    "think_closed": sum(bool(r["think_closed"]) for _, _, r, _ in results),
                    "generated_tokens_total": sum(r["generated_tokens"] for _, _, r, _ in results),
                    "note": "원문만 수집. 판정·필터·import는 다음 세션(사용자 승인 뒤)"}
        out.write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(json.dumps({k: v for k, v in manifest.items() if k != "runtime"}, ensure_ascii=False))
        return
    order = {it["id"]: n for n, it in enumerate(items)}
    rows = []
    for item, _, result, secs in sorted(results, key=lambda r: order[r[0]["id"]]):
        verdict, payload = T.judge(result["content"], item["question"], item["gold_grounding"]) if item.get("gold_grounding") else ({}, None)
        rows.append({"id": item["id"], "source": item.get("source"),
                     "question_sha256": hashlib.sha256(item["question"].encode("utf-8")).hexdigest(),
                     "raw_sha256": result["raw_sha256"], "generated_tokens": result["generated_tokens"], "done_reason": result["done_reason"],
                     "think_closed": result["think_closed"], "thinking_chars": len(result["thinking"]),
                     "prompt_ids_echo_equal": result["prompt_ids_echo_equal"], "seconds": round(secs, 2),
                     "parse_state": verdict.get("parse"), "parsed": payload, "matches_gold": bool(verdict.get("raw_match")),
                     "grounding_diffs": verdict.get("raw_diffs"), "matches_gold_after_condition_layer": verdict.get("after_condition_match"),
                     "error_tags": [] if verdict.get("raw_match") else verdict.get("error_tags"), "gold_kind": item.get("gold_kind")})
    with out.open("w", encoding="utf-8") as stream:
        stream.write(json.dumps({"runtime": runtime}, ensure_ascii=False) + "\n")
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(json.dumps({"items": len(rows), "matches_gold": sum(r["matches_gold"] for r in rows),
                      "truncated": sum(r["done_reason"] == "length" for r in rows), "wall_seconds": round(wall, 1)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
