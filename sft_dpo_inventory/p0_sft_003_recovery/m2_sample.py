# -*- coding: utf-8 -*-
"""M2 21문항 Qwen3-8B 추가 sampling(PLAN.md 2절). sampling만, greedy 없음.

    HF_HOME=/data/hwkim/path_repeat_001/hf-cache HF_HUB_OFFLINE=1 python sft_dpo_inventory/p0_sft_003_recovery/m2_sample.py
    # -> training/generated/p0_sft_003_recovery/m2_raw/traces.jsonl, m2_sampling_plan.json, m2_raw/run.json

- 생성은 `evaluation/partial_grounding/sft_p0/collect_p0_traces_hf.py`와 같다.
  - hf_thinking client, P0 messages 확인, 같은 judge
  - 문항당 한 번의 generate(num_return_sequences 8, sampling 0.6/0.95/20, max_new_tokens 8192)
- seed = 2026101400 + m2_index(m2_index = 대상 ID 정렬 순서).
- 이미 원문 파일이 있으면 멈춘다(덮어쓰지 않음).
"""
import hashlib
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "evaluation/partial_grounding/sft_p0"))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/thinking_prep_001"))

import collect_p0_traces_hf as C  # noqa: E402
import hf_thinking as H  # noqa: E402

M2 = sorted(["ann-f78087861d0826ae8a7f", "ann-29dcb56f51da6d6a361f", "b004-18", "b004-22", "b004-40", "b005-33", "b005-34",
             "b005-54", "b005-58", "b005-04", "b005-36", "b005-41", "b006-02", "b006-04", "b006-08", "b006-13", "b006-14",
             "b006-18", "b006-19", "b006-28", "b006-34"])
SEED_BASE = 2026101400
SAMPLES = 8
OUT = ROOT / "training/generated/p0_sft_003_recovery/m2_raw"


def main():
    planner, sha = C.p0_planner()
    records = {r["meta"]["source_record_id"]: r for r in
               C.load_records(ROOT / "training/generated/reviewed_gold_v006_p0/sft_train.jsonl", planner)}
    plan = {"items": [{"m2_index": i, "item_id": iid, "seed": SEED_BASE + i} for i, iid in enumerate(M2)],
            "samples_per_item": SAMPLES, "calls_planned": SAMPLES * len(M2), "prompt_sha256": sha,
            "model": f"{H.MODEL}@{H.REVISION}", "sampling": {**H.SAMPLING, "num_return_sequences": SAMPLES},
            "max_new_tokens": H.MAX_NEW_TOKENS, "enable_thinking": True, "greedy": False}
    (HERE / "m2_sampling_plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    if len(M2) != 21 or set(M2) - set(records):
        raise SystemExit("M2 대상이 21이 아니거나 v006에 없다")
    OUT.mkdir(parents=True, exist_ok=True)
    traces = OUT / "traces.jsonl"
    if traces.exists():
        raise SystemExit(f"{traces}가 이미 있다")
    import torch
    t0 = time.perf_counter()
    client = H.load_client()
    device = torch.cuda.get_device_properties(0)
    run = {"started_at": datetime.now(ZoneInfo("Asia/Seoul")).isoformat(), "device": device.name, "device_uuid": f"GPU-{device.uuid}",
           "dtype": str(next(client.policy.parameters()).dtype), "attention": client.policy.config._attn_implementation,
           "torch": torch.__version__, "load_seconds": round(time.perf_counter() - t0, 1)}
    with open(traces, "w", encoding="utf-8") as stream:
        for p in plan["items"]:
            rec = records[p["item_id"]]
            q0 = time.perf_counter()
            outs = client.generate(rec["messages"], sample=True, num_return_sequences=SAMPLES, seed=p["seed"])
            secs = time.perf_counter() - q0
            for k, result in enumerate(outs, 1):
                verdict, payload = C.judge(rec["question"], result["content"], result["think_closed"], rec["target_p0"],
                                           rec["meta"]["target_full"])
                stream.write(json.dumps({
                    "trace_id": f"{p['item_id']}:m2sample:{k}", "item_id": p["item_id"], "m2_index": p["m2_index"],
                    "generation_batch": "p0_sft_003_recovery/m2", "question": rec["question"],
                    "teacher_model": H.MODEL, "teacher_revision": H.REVISION, "tokenizer": f"{H.MODEL}@{H.REVISION}",
                    "prompt_sha256": sha, "batch_seed": p["seed"], "sample_index": k, "generation": plan["sampling"],
                    "max_new_tokens": H.MAX_NEW_TOKENS, "enable_thinking": True,
                    **{x: result[x] for x in ("raw_text", "raw_sha256", "thinking", "content", "think_closed", "prompt_tokens",
                                              "generated_tokens", "done_reason", "generated_ids")},
                    "thinking_chars": len(result["thinking"]), "parsed": payload, "judge": verdict,
                    "question_seconds": round(secs, 1)}, ensure_ascii=False) + "\n")
            stream.flush()
            print(json.dumps({"i": p["m2_index"], "id": p["item_id"], "exact": sum(1 for _ in [0])}), flush=True)
    run.update(finished_at=datetime.now(ZoneInfo("Asia/Seoul")).isoformat(), seconds=round(time.perf_counter() - t0, 1),
               traces_sha256=hashlib.sha256(traces.read_bytes()).hexdigest())
    (OUT / "run.json").write_text(json.dumps(run, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("M2_DONE", flush=True)


if __name__ == "__main__":
    main()
