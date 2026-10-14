# -*- coding: utf-8 -*-
"""G4 31문항 teacher 생성(IMPORT_AND_TEACHER_PLAN.md). 판정은 하지 않는다(raw를 먼저 freeze).

    python sft_dpo_inventory/p0_sft_003_teacher27b/teacher_generate.py --speed-threshold X
    # -> training/generated/p0_sft_003_teacher27b/raw/traces.jsonl, generation/generation_summary.json

- 대상: p0_sft_003_recovery/teacher27b_manifest.json의 순서(item_index 0–30). sha256·순서 hash를 확인한다.
- 문항당 greedy 1(temperature 0) + sampling 4(0.6/0.95/20, seed = 2026101500 + 10 × item_index + sample_index).
- `think: true`, P0 prompt(d7f4c12a), gold 미제공, num_predict 미지정, 호출마다 keep_alive 0(결정 80).
- guard: 호출 중 size_vram == size, tok/s ≥ --speed-threshold(compatibility 중앙값의 0.5), GPU compute 프로세스 수 ≤ 1(Ollama runner).
  어기면 중단하고 원문 파일을 ABORTED_로 바꾼다.
- 이어 받기(기반 장애만): --resume이면 끝난 (item, sample)을 건너뛴다.
- 다른 대상 batch(예: p0_sft_003_teacher27b_remaining)는 --manifest·--manifest-sha·--order-sha·--n-items·--raw-dir·--summary-dir·
  --seed-base·--batch로 지정한다. 기본값은 31문항 batch와 같다(기록 경로만 바뀌고 생성 방식은 같다).
"""
import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "evaluation/partial_grounding/sft_p0"))

import ollama_call as O  # noqa: E402

MANIFEST = ROOT / "sft_dpo_inventory/p0_sft_003_recovery/teacher27b_manifest.json"
MANIFEST_SHA = "65a016e0a71905e45443e31c54a6ae59285f950fa33cac4905129766f5c07f38"
ORDER_SHA = "9850b727f361c8691b1c18295a1463e3d5fdbce35a49f0585834d85985d5a599"
RAW = ROOT / "training/generated/p0_sft_003_teacher27b/raw"
SEED_BASE = 2026101500
SAMPLING = {"temperature": 0.6, "top_p": 0.95, "top_k": 20}


def gpu_apps():
    out = subprocess.run(["nvidia-smi", "--query-compute-apps=pid", "--format=csv,noheader"], capture_output=True, text=True).stdout
    return len([x for x in out.splitlines() if x.strip()])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--speed-threshold", type=float, required=True)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--manifest", type=Path, default=MANIFEST)
    ap.add_argument("--manifest-sha", default=MANIFEST_SHA)
    ap.add_argument("--order-sha", default=ORDER_SHA)
    ap.add_argument("--n-items", type=int, default=31)
    ap.add_argument("--raw-dir", type=Path, default=RAW)
    ap.add_argument("--summary-dir", type=Path, default=HERE / "generation")
    ap.add_argument("--seed-base", type=int, default=SEED_BASE)
    ap.add_argument("--batch", default="p0_sft_003_teacher27b/m1_p12")
    a = ap.parse_args()
    import collect_p0_traces_hf as C
    from geoflow.planner import parse_planner_json
    if hashlib.sha256(a.manifest.read_bytes()).hexdigest() != a.manifest_sha:
        raise SystemExit("manifest sha256 불일치")
    man = json.loads(a.manifest.read_text(encoding="utf-8"))["items"]
    ids = [x["item_id"] for x in man]
    if hashlib.sha256("\n".join(ids).encode()).hexdigest() != a.order_sha or len(ids) != a.n_items:
        raise SystemExit("manifest 순서 hash 불일치")
    tags = {m["name"]: m["digest"] for m in __import__("httpx").get(f"{O.HOST}/api/tags", timeout=10).json()["models"]}
    if tags.get(O.MODEL) != O.EXPECTED_DIGEST:
        raise SystemExit(f"digest 불일치: {tags.get(O.MODEL)}")
    version = __import__("httpx").get(f"{O.HOST}/api/version", timeout=10).json()["version"]
    planner, sha = C.p0_planner()
    a.raw_dir.mkdir(parents=True, exist_ok=True)
    path = a.raw_dir / "traces.jsonl"
    done = set()
    if path.exists():
        if not a.resume:
            raise SystemExit("원문이 이미 있다(기반 장애 뒤에만 --resume)")
        done = {(json.loads(x)["item_id"], json.loads(x)["sample_index"]) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()}
    started = datetime.now(timezone.utc).isoformat()
    calls = 0
    with open(path, "a", encoding="utf-8") as f:
        for idx, x in enumerate(man):
            q = x["question"]
            msgs = planner.messages(q)
            for k in range(5):
                if (x["item_id"], k) in done:
                    continue
                if gpu_apps() > 1:
                    raise SystemExit("GPU에 다른 compute 프로세스가 있다")
                opts = {"temperature": 0} if k == 0 else {**SAMPLING, "seed": a.seed_base + 10 * idx + k}
                res = O.chat(msgs, opts)
                calls += 1
                try:
                    parsed = parse_planner_json(res["content"]) if res["content"] else None
                except Exception as error:  # noqa: BLE001 - 판정은 G5에서 한다. 여기서는 기록만
                    parsed = {"_parse_error": type(error).__name__}
                row = {"trace_id": f"{x['item_id']}:27b:{'greedy' if k == 0 else 'sample'}:{k}", "item_id": x["item_id"], "item_index": idx,
                       "sample_index": k, "kind": "greedy" if k == 0 else "sample", "mode": "greedy" if k == 0 else "sampling", "question": q,
                       "missing_class": x.get("missing_class"), "group": x.get("group"),
                       "teacher_model": O.MODEL, "teacher_digest": O.EXPECTED_DIGEST, "ollama_version": version,
                       "prompt_sha256": sha, "generation_batch": a.batch,
                       "seed": opts.get("seed"), "options": opts, "think": True, "keep_alive": 0,
                       "thinking_chars": len(res["thinking"]), **res, "parsed_output": parsed, "at": datetime.now(timezone.utc).isoformat()}
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
                f.flush()
                bad = []
                if not res["guard"]["gpu_full"]:
                    bad.append("gpu_not_full")
                if res["tok_per_s"] is not None and res["tok_per_s"] < a.speed_threshold:
                    bad.append(f"slow {res['tok_per_s']}")
                if res["http_status"] != 200 or res["error"]:
                    bad.append(f"http {res['http_status']} {res['error']}")
                print(json.dumps({"i": idx, "k": k, "id": x["item_id"], "done": res["done_reason"], "eval": res["eval_count"],
                                  "tps": res["tok_per_s"], "bad": bad}, ensure_ascii=False), flush=True)
                if bad:
                    f.close()
                    path.rename(a.raw_dir / "ABORTED_traces.jsonl")
                    raise SystemExit(f"guard 중단: {bad}")
    summary = {"started_at": started, "finished_at": datetime.now(timezone.utc).isoformat(), "calls_this_run": calls,
               "manifest": str(a.manifest.resolve().relative_to(ROOT)), "manifest_sha256": a.manifest_sha, "order_sha256": a.order_sha,
               "seed_base": a.seed_base, "generation_batch": a.batch, "model": O.MODEL, "digest": O.EXPECTED_DIGEST,
               "ollama_version": version, "prompt_sha256": sha, "speed_threshold": a.speed_threshold,
               "traces_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
               "total_lines": sum(1 for _ in path.read_text(encoding="utf-8").splitlines())}
    a.summary_dir.mkdir(parents=True, exist_ok=True)
    (a.summary_dir / "generation_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("GENERATION_DONE", json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
