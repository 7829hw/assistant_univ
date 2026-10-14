# -*- coding: utf-8 -*-
"""실차 대조 묶음 8b 표본 수집(결정 98, AM). vLLM BF16 base(flashinfer)로 문항당 32표본. 학습하지 않는다.

    hfvenv/bin/python sft_dpo_inventory/pilot_004/realtrip/collect_vllm.py --ports 8300,8301,8302 --concurrency 8

- 대상(``targets.json``): 승인된 batch006 실차 대조 묶음(결정 66·80, 24문항) 가운데 pilot_003 HF trace(greedy 1 + 표본 8, ``pilot_003/traces/batch006/summary.json``)
  에서 정답 표본이 없는 문항.
- 입력: corpus 레코드(``training/generated/pilot_003/trace_inputs/batch006``)의 system·user. 현재 planner messages와 같은지 확인한다.
  HF와 같은 ``render_prompt``(enable_thinking) id열을 ``/v1/completions``에 직접 넘긴다(``serving_vllm/vllm_thinking.py``).
- 생성: temperature 0.6, top_p 0.95, top_k 20, min_p 0, repetition_penalty 1, presence·frequency 0, max_tokens 8192(calibration_001과 같음).
  표본 s(1..32)의 요청 seed = ``EV.call_seed(20261014, 문항 id, s)``. vLLM은 seed로 재현되지 않는다(결정 93) — 원문을 모두 ignore 경로에 둔다.
  요청은 서버들에 돌아가며 나누고, 서버마다 동시 요청 최대 C개다.
- 판정: ``thinking_prep_001/collect_traces.judge``(조건 계층 전 원 출력의 JSON을 reviewed gold와 ``grounding_check``). 후보 형식도 같다
  (SFT = 정답 표본, 같은 원문은 하나로; DPO = 같은 문항의 (정답, 오답) 쌍).
- 출력: trace 원문 ``training/generated/thinking_traces/realtrip_vllm/traces.jsonl``(ignore), 요약 ``realtrip/summary.json``·``candidates.json``.
"""
import argparse
import hashlib
import json
import sys
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/thinking_prep_001"))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/serving_vllm"))

CORPUS = ROOT / "training/generated/pilot_003/trace_inputs/batch006/sft_train.jsonl"
P3_SUMMARY = ROOT / "sft_dpo_inventory/pilot_003/traces/batch006/summary.json"
B6_CHECKED = ROOT / "sft_dpo_inventory/batch006/candidates_checked.json"
OUT = ROOT / "training/generated/thinking_traces/realtrip_vllm"
SAMPLES = 32
ROUND_SEED = 20261014
SAMPLING = {"temperature": 0.6, "top_p": 0.95, "top_k": 20, "min_p": 0.0, "repetition_penalty": 1.0}


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def targets():
    p3 = json.loads(P3_SUMMARY.read_text(encoding="utf-8"))
    no_correct = set(p3["summary"]["no_correct_sample"])
    per_q = {q["source_record_id"]: q for q in p3["questions"]}
    variant = {c["id"]: c["variant"] for c in json.loads(B6_CHECKED.read_text(encoding="utf-8"))["candidates"] if c.get("variant")}
    records = {r["metadata"]["source_record_id"]: r for r in read(CORPUS)}
    rows = []
    for sid in sorted(records):
        q = per_q[sid]
        rows.append({"source_record_id": sid, "variant": variant.get(sid), "approved_contrast": sid in variant,
                     "pilot003_hf_greedy_correct": q["greedy_correct"], "pilot003_hf_correct_samples_of_8": q["correct_samples_of_8"],
                     "target": sid in variant and sid in no_correct,
                     "reason": ("pilot_003 HF trace(greedy 1 + 표본 8)에서 정답 0" if sid in no_correct else
                                f"pilot_003 HF 정답 있음(greedy {q['greedy_correct']}, 표본 {q['correct_samples_of_8']}/8)")})
    return rows, records


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--ports", required=True)
    p.add_argument("--concurrency", type=int, default=8)
    args = p.parse_args()
    import evaluate_vendor100 as EV
    from collect_traces import judge
    from geoflow.planner import GeoFlowPlanner
    from training.data.common import check_expected_prompt
    from vllm_thinking import VLLMThinkingClient
    if OUT.exists():
        raise SystemExit(f"{OUT} exists")
    OUT.mkdir(parents=True)
    prompt_hash = check_expected_prompt()
    rows, records = targets()
    (HERE / "targets.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    tgt = [r["source_record_id"] for r in rows if r["target"]]
    planner = GeoFlowPlanner(client=None)
    ports = [int(x) for x in args.ports.split(",")]
    clients = {port: [VLLMThinkingClient(f"http://127.0.0.1:{port}", "base") for _ in range(args.concurrency)] for port in ports}
    pools = {port: list(cs) for port, cs in clients.items()}
    lock = threading.Lock()
    jobs = []
    for qi, sid in enumerate(tgt):
        messages = records[sid]["messages"][:2]
        if planner.messages(messages[1]["content"]) != messages:
            raise SystemExit(f"{sid}: corpus 입력이 현재 planner messages와 다르다")
        for s in range(1, SAMPLES + 1):
            jobs.append((sid, s, ports[len(jobs) % len(ports)]))

    def run(job):
        sid, s, port = job
        with lock:
            client = pools[port].pop()
        try:
            seed = EV.call_seed(ROUND_SEED, sid, s)
            t0 = time.perf_counter()
            result = client.generate(records[sid]["messages"][:2], sample=True, seed=seed, sampling=SAMPLING)
            return sid, s, port, seed, result, time.perf_counter() - t0
        finally:
            with lock:
                pools[port].append(client)

    started = time.perf_counter()
    # 서버마다 executor 하나(작업자 C개): 한 서버에 동시 요청이 C개를 넘지 않는다.
    executors = {port: ThreadPoolExecutor(max_workers=args.concurrency) for port in ports}
    futures = [executors[job[2]].submit(run, job) for job in jobs]
    results = [f.result() for f in futures]
    for ex in executors.values():
        ex.shutdown()
    wall = time.perf_counter() - started
    by_q = {sid: [] for sid in tgt}
    with open(OUT / "traces.jsonl", "w", encoding="utf-8") as stream:
        for sid, s, port, seed, result, secs in sorted(results, key=lambda r: (r[0], r[1])):
            gold = json.loads(records[sid]["messages"][-1]["content"])
            verdict, payload = judge(result["content"], records[sid]["messages"][1]["content"], gold)
            row = {"trace_id": f"{sid}:vllm:{s}", "source_record_id": sid, "kind": "vllm_sample", "sample_index": s, "seed": seed,
                   "server_port": port, **{k: result[k] for k in ("raw_text", "raw_sha256", "generated_ids", "thinking", "content",
                                                                  "think_closed", "prompt_tokens", "generated_tokens", "done_reason",
                                                                  "finish_reason", "prompt_ids_echo_equal")},
                   "seconds": round(secs, 2), "parsed": payload, "verdict": verdict}
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
            by_q[sid].append(row)
    questions, sft_c, dpo_c = [], [], []
    for sid in tgt:
        judged = by_q[sid]
        uniq = {}
        for kind in (True, False):
            seen, lst = set(), []
            for r in judged:
                if r["verdict"]["raw_match"] == kind and r["raw_sha256"] not in seen:
                    seen.add(r["raw_sha256"])
                    lst.append(r)
            uniq[kind] = lst
        questions.append({"source_record_id": sid, "samples": len(judged), "correct_samples": sum(r["verdict"]["raw_match"] for r in judged),
                          "correct_only_after_condition_layer": sum(1 for r in judged if not r["verdict"]["raw_match"]
                                                                    and r["verdict"]["after_condition_match"]),
                          "unique_correct": len(uniq[True]), "unique_wrong": len(uniq[False]),
                          "truncated": sum(r["done_reason"] == "length" for r in judged),
                          "echo_mismatch": sum(r["prompt_ids_echo_equal"] is False for r in judged),
                          "error_tags": dict(Counter(t for r in judged if not r["verdict"]["raw_match"] for t in r["verdict"]["error_tags"]))})
        for r in uniq[True]:
            sft_c.append({"trace_id": r["trace_id"], "source_record_id": sid, "raw_sha256": r["raw_sha256"],
                          "generated_tokens": r["generated_tokens"], "prompt_tokens": r["prompt_tokens"], "v003_flags": []})
        for c in uniq[True]:
            for w in uniq[False]:
                dpo_c.append({"chosen": c["trace_id"], "rejected": w["trace_id"], "source_record_id": sid,
                              "rejected_error_tags": w["verdict"]["error_tags"], "rejected_grounding_diffs": w["verdict"]["raw_diffs"],
                              "rejected_parse": w["verdict"]["parse"],
                              "rejected_correct_after_condition_layer": w["verdict"]["after_condition_match"],
                              "v003_flags": {"sft": [], "dpo": []}})
    tp = OUT / "traces.jsonl"
    summary = {"corpus": str(CORPUS.relative_to(ROOT)), "corpus_file_sha256": sha256(CORPUS), "prompt_sha256": prompt_hash,
               "model": "vllm 0.30.0 BF16 Qwen/Qwen3-8B@b968826d (flashinfer)", "enable_thinking": True, "max_new_tokens": 8192,
               "samples_per_question": SAMPLES, "sampling": SAMPLING, "seed_rule": f"EV.call_seed({ROUND_SEED}, id, sample_index)",
               "seed_reproducible": False, "servers": ports, "concurrency_per_server": args.concurrency,
               "judgment": "evaluate_vendor100.grounding_check on raw model output (before condition layer)",
               "questions": len(questions), "pass_at_32": sum(q["correct_samples"] > 0 for q in questions),
               "no_correct_sample": [q["source_record_id"] for q in questions if q["correct_samples"] == 0],
               "sft_candidates": len(sft_c), "dpo_candidate_pairs": len(dpo_c),
               "truncated_generations": sum(q["truncated"] for q in questions), "echo_mismatch": sum(q["echo_mismatch"] for q in questions),
               "traces_path": str(tp.resolve()), "traces_sha256": sha256(tp), "wall_seconds": round(wall, 1),
               "reasoning_text_human_reviewed": False}
    (HERE / "summary.json").write_text(json.dumps({"summary": summary, "questions": questions}, ensure_ascii=False, indent=1) + "\n",
                                       encoding="utf-8")
    (HERE / "candidates.json").write_text(json.dumps({"sft": sft_c, "dpo": dpo_c}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    for q in questions:
        print(q["source_record_id"], q["correct_samples"], q["unique_correct"], q["unique_wrong"], q["truncated"])


if __name__ == "__main__":
    main()
