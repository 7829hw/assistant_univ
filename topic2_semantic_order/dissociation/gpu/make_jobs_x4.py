"""X4 GPU 작업 목록(PREREGISTRATION 6.2·6.3). 쌍마다 같은 GPU에서 두 학습을 연달아(pairs.json의 run_order), 이어서 두 어댑터의 최종 H-dev(k=1,
회차 seed 20261101, 동시 32, 서버 하나에 LoRA 하나 — 기존 H-dev 셀과 같은 명령)를 같은 GPU에서 잰다.
    python make_jobs_x4.py MAIN_REPO
"""
import json
import sys
from pathlib import Path

main = Path(sys.argv[1]).resolve()
D = main / "topic2_semantic_order/dissociation"
pairs = json.loads((D / "x4/train/pairs.json").read_text())
OUT = "/data/hwkim/sftdpo_work/topic2_dissociation/train"
CELLS = "{MAIN}/topic2_semantic_order/dissociation/x4/cells"
RAW = "{MAIN}/training/generated/topic2_dissociation/x4_raw"
HDEV = "{WT}/sft_dpo_inventory/ablation_012/e2/h_dev.yaml"
jobs = []
for p in pairs:
    for cid in p["run_order"]:
        ck = f"{OUT}/{cid}/checkpoint-1984"
        jobs.append({"id": f"T-{cid}", "lane": p["lane"], "kind": "train", "pair": p["pair"],
                     "config": f"topic2_semantic_order/dissociation/x4/train/configs/{cid}.yaml", "expect": f"{ck}/adapter_model.safetensors",
                     "done_marker": f"topic2_semantic_order/dissociation/gpu/done/T-{cid}.json"})
    for cid in p["run_order"]:
        ck = f"{OUT}/{cid}/checkpoint-1984"
        name = cid.replace("-", "_")
        jobs.append({"id": f"H-{cid}", "lane": p["lane"], "kind": "cells", "pair": p["pair"], "loras": f"{name}={ck}",
                     "done_marker": f"topic2_semantic_order/dissociation/gpu/done/H-{cid}.json",
                     "cells": [["--model", name, "--label", f"hdev_{cid.lower().replace('-', '_')}", "--k", "1", "--concurrency", "32",
                                "--grounding-target", "full", "--out-dir", CELLS, "--raw-dir", RAW, "--seed-base", "20261100", "--gold", HDEV, "--all-items"]]})
(D / "gpu/jobs_x4.json").write_text(json.dumps({"note": "X4 학습·평가(승인 2026-11-16, V4S sha256 0f1d0bc7…). 레인마다 쌍 순서대로.", "jobs": jobs},
                                               ensure_ascii=False, indent=1) + "\n")
print(len(jobs), [ (j["lane"], j["id"]) for j in jobs[:4]])
