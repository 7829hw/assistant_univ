"""X1·X2·X3 GPU 작업 목록과 reader 목록 만들기(CPU). 어댑터가 기존 H-dev 셀을 만든 바로 그 어댑터인지 sha256으로 대조한다.

    python make_jobs.py MAIN_REPO
출력: dissociation/gpu/jobs.json, dissociation/x12/readers_*.json, dissociation/gpu/adapters.json
"""
import contextlib
import hashlib
import importlib.util
import io
import json
import sys
from pathlib import Path

main = Path(sys.argv[1]).resolve()
D = main / "topic2_semantic_order/dissociation"
W = "/data/hwkim/sftdpo_work"
spec = importlib.util.spec_from_file_location("fdc", D / "fare_dissociation_check.py")
fdc = importlib.util.module_from_spec(spec)
argv, sys.argv = sys.argv, ["x", str(main)]
with contextlib.redirect_stdout(io.StringIO()):
    spec.loader.exec_module(fdc)
sys.argv = argv


def run_dir(arm, s, r):
    if arm == "A":
        if r == 1:
            return f"{W}/{'ablation_011' if s in ('o1102', 'o211102') else 'ablation_013'}/train/A0-{s}"
        if s == "o2026131" and r == 2:
            return f"{W}/topic2_semantic_order/train/A0-o2026131-r2"
        return f"{W}/topic2_semantic_order_repro/train/A0-{s}-r{r}"
    if r == 1:
        return f"{W}/topic2_semantic_order/train/B-{s}"
    if s == "o2026131" and r == 2:
        return f"{W}/topic2_semantic_order/train/B-o2026131-r2"
    return f"{W}/topic2_semantic_order_repro/train/B-{s}-r{r}"


def sha(p):
    return hashlib.sha256(Path(p, "adapter_model.safetensors").read_bytes()).hexdigest()


adapters, finals, mids = [], [], []
for run in fdc.RUNS:
    label = f"{run[0]}-{run[1]}-r{run[2]}"
    d = run_dir(*run)
    final = f"{d}/checkpoint-1984"
    cell = json.loads((main / fdc.cell_path(*run)).read_text(encoding="utf-8"))
    meta = cell["meta"].get("vllm", {}).get("server_meta") or {}
    rec = list((meta.get("lora_adapter_sha256") or {}).values())
    h = sha(final)
    adapters.append({"run": label, "final": final, "sha256": h, "cell_server_lora_sha256": rec, "match": h in rec})
    finals.append({"name": label, "path": final, "run": label})
    for ck in (496, 992, 1488):
        p = f"{d}/checkpoint-{ck}"
        mids.append({"name": f"{label}@{ck}", "path": p, "run": label, "sha256": sha(p)})
bad = [a for a in adapters if not a["match"]]
(D / "gpu").mkdir(exist_ok=True)
(D / "gpu/adapters.json").write_text(json.dumps({"finals": adapters, "intermediate": mids}, ensure_ascii=False, indent=1) + "\n")
if bad:
    raise SystemExit(f"어댑터 sha256이 셀 서버 기록과 다름: {[a['run'] for a in bad]}")
(D / "x12").mkdir(exist_ok=True)
(D / "x12/readers_final18.json").write_text(json.dumps(finals, indent=1) + "\n")
(D / "x12/readers_mid54.json").write_text(json.dumps(mids, indent=1) + "\n")
(D / "x12/readers_base.json").write_text(json.dumps([{"name": "base", "path": None, "run": None}], indent=1) + "\n")

WP = "{MAIN}/training/generated/topic2_dissociation/writer_prefixes.jsonl"
PI = "{MAIN}/training/generated/topic2_dissociation/prompt_ids_147.jsonl"
RAWX = "{MAIN}/training/generated/topic2_dissociation/x12"
jobs = [{"id": "X1-self-final18", "lane": "g0", "kind": "x12", "done_marker": "topic2_semantic_order/dissociation/gpu/done/X1-self-final18.json",
         "args": ["--readers", "{MAIN}/topic2_semantic_order/dissociation/x12/readers_final18.json", "--writers", WP, "--prompt-ids", PI,
                  "--pairs", "self", "--out", f"{RAWX}/x1_self_final18.jsonl"]}]
# X3: 18 어댑터 × 탐침 a·b(k=1, 회차 seed 20261101), base 탐침 a·b × k=1·2(20261101·02). 서버 하나에 LoRA 하나(원래 H-dev 셀과 같은 구성).
CELLS = "{MAIN}/topic2_semantic_order/dissociation/x3/cells"
RAW3 = "{MAIN}/training/generated/topic2_dissociation/x3_raw"
GOLD = {p: f"{{WT}}/topic2_semantic_order/dissociation/probes/hdev147_probe_{p}.yaml" for p in "ab"}


def cell(model, label, k, probe):
    return ["--model", model, "--label", label, "--k", str(k), "--concurrency", "32", "--grounding-target", "full", "--out-dir", CELLS,
            "--raw-dir", RAW3, "--seed-base", "20261100", "--gold", GOLD[probe], "--all-items"]


lanes = ["g1", "g2"]
for n, run in enumerate(fdc.RUNS):
    label = f"{run[0]}-{run[1]}-r{run[2]}"
    name = label.replace("-", "_")
    final = run_dir(*run) + "/checkpoint-1984"
    tag = label.lower().replace("-", "_")
    jobs.append({"id": f"X3-{label}", "lane": lanes[n % 2], "kind": "cells", "loras": f"{name}={final}",
                 "done_marker": f"topic2_semantic_order/dissociation/gpu/done/X3-{label}.json",
                 "cells": [cell(name, f"x3{p}_{tag}", 1, p) for p in "ab"]})
jobs.append({"id": "X3-base", "lane": "g2", "kind": "cells", "loras": f"{finals[0]['name'].replace('-', '_')}={finals[0]['path']}",
             "done_marker": "topic2_semantic_order/dissociation/gpu/done/X3-base.json",
             "cells": [cell("base", f"x3{p}_base", k, p) for p in "ab" for k in (1, 2)]})
(D / "gpu/jobs.json").write_text(json.dumps({"note": "X1·X2·X3 GPU 작업(PREREGISTRATION 3·5절). X2·중간 체크포인트는 AUC 게이트 뒤 jobs_x2.json으로 따로.",
                                             "jobs": jobs}, ensure_ascii=False, indent=1) + "\n")
print(json.dumps({"finals_match": len(adapters) - len(bad), "mids": len(mids), "jobs": len(jobs)}))
