# -*- coding: utf-8 -*-
"""J1 사후 manifest(세션 1b). J1(collect6.py --mode self)은 3,609 생성을 모두 마친 뒤 manifest 단계에서 실패했다:
2026-10-16 00:25–00:29 사이 바깥에서 worktree 디렉터리(/data/hwkim/sftdpo_work/pilot_006_prep/wt_*)가 지워져 상대 경로 입력 파일을 열지 못함.
큐(jobs6.sh)가 원문을 ``raw/ABORTED_self_full_raw.jsonl``로 바꿨다. 이 스크립트는 원문만 읽어 원래 manifest와 같은 항목을 만든다(모델 호출 없음).
원문 파일 이름은 바꾸지 않았다(되돌릴지는 사용자 결정).
"""
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RAW = ROOT / "training/generated/pilot_006/self_full/raw/ABORTED_self_full_raw.jsonl"
INP = ROOT / "sft_dpo_inventory/pilot_006_prep/gpu/inputs/self_questions.jsonl"
items = [json.loads(l) for l in INP.read_text(encoding="utf-8").splitlines()]
rows = [json.loads(l) for l in RAW.read_text(encoding="utf-8").splitlines()]
per = Counter(r["id"] for r in rows)
kinds = Counter((r["id"], r["sample_index"]) for r in rows)
expected = {(i["id"], s) for i in items for s in range(0, 9)}
server = json.loads(Path("/data/hwkim/sftdpo_work/pilot_006_prep/vllm/server_8600.json").read_text(encoding="utf-8")) \
    if Path("/data/hwkim/sftdpo_work/pilot_006_prep/vllm/server_8600.json").exists() else {}
manifest = {
    "posthoc": True, "incident": "생성 완료 뒤 manifest 단계 실패(바깥에서 worktree가 지워짐, FileNotFoundError). 원문은 줄 단위로 쓰여 완전하다(아래 검사).",
    "runtime": {"label": "J1_self_full", "mode": "self", "engine": "vllm 0.30.0 BF16 flashinfer", "worktree_commit": "0c6ab4dabe60bd1ef8fc1bf27e441047a3fb120b",
                "device_uuid": "GPU-2445b100-70d8-e384-3a24-0249eeefc64d", "max_model_len": 16384,
                "decoding": {"greedy_per_question": 1, "samples_per_question": 8, "sampling": {"temperature": 0.6, "top_p": 0.95, "top_k": 20,
                             "min_p": 0.0, "repetition_penalty": 1.0}, "max_tokens": 8192, "round_seed": 20261015,
                             "seed_rule": "EV.call_seed(round_seed, id, s)", "seed_reproducible": False},
                "prompt": "Full(GeoFlowPlanner.messages), 87048d0c", "concurrency": 8, "start": "2026-10-15T21:58:36+09:00", "end": "2026-10-16T00:37:26+09:00",
                "server_meta_vllm": server.get("vllm"), "inputs_sha256": hashlib.sha256(INP.read_bytes()).hexdigest(),
                "raw_out": str(RAW.relative_to(ROOT)), "raw_out_sha256": hashlib.sha256(RAW.read_bytes()).hexdigest()},
    "questions": len(items), "generations": len(rows), "complete": set(kinds) == expected and len(rows) == len(expected),
    "duplicates": sum(1 for v in kinds.values() if v > 1), "missing": len(expected - set(kinds)),
    "by_source": dict(Counter(r.get("source") for r in rows if r["sample_index"] == 0)),
    "per_question_generations": sorted(set(per.values())),
    "done_reason": dict(Counter(r["done_reason"] for r in rows)), "think_closed": sum(bool(r["think_closed"]) for r in rows),
    "generated_tokens_total": sum(r["generated_tokens"] for r in rows),
    "prompt_tokens_max": max(r["prompt_tokens"] for r in rows), "max_total_tokens(prompt+generated)": max(r["prompt_tokens"] + r["generated_tokens"] for r in rows),
    "note": "원문만 수집. 판정·필터·import는 다음 세션(사용자 승인 뒤). 결정 117: 요청이 모두 16,384 한도 안이라 학습 데이터 후보로 그대로 쓴다."}
out = ROOT / "training/generated/pilot_006/self_full/manifest.json"
out.write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print(json.dumps({k: v for k, v in manifest.items() if k != "runtime"}, ensure_ascii=False, indent=1))
