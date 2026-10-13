# -*- coding: utf-8 -*-
"""P0 thinking trace 수집(HF base Qwen3-8B, 결정 66·67). 학습하지 않는다.

    HF_HOME=/data/hwkim/path_repeat_001/hf-cache HF_HUB_OFFLINE=1 \
      python evaluation/partial_grounding/sft_p0/collect_p0_traces_hf.py \
        --dataset training/generated/reviewed_gold_v006_p0/sft_train.jsonl \
        --out training/generated/thinking_traces/p0_v006_hf --summary evaluation/partial_grounding/sft_p0/traces_hf
    # 모델 호출 없이 입력·요청 수만 확인
    python ... --dry-run

- 생성 방식은 기존 승인 절차 `sft_dpo_inventory/thinking_prep_001/collect_traces.py`와 같다.
  - 모델 `Qwen/Qwen3-8B@b968826d`(BF16, SDPA, `hf_thinking.load_client`), `enable_thinking=True`, max_new_tokens 8192.
  - 질문마다 greedy 1개 + sampling 8개(한 번의 generate, num_return_sequences 8).
    sampling은 temperature 0.6, top_p 0.95, top_k 20이고 seed = 20261006 + 질문 순번(데이터셋 파일 순서).
  - 질문마다 대화 상태 없이 [system, user]만 넣는다. gold를 힌트로 주지 않는다.
- 바뀌는 것: system prompt가 P0(`partial_p0.yaml`, hash `d7f4c12a`)이고 판정 대상이 P0 target이다.
  - 입력 messages가 v006 레코드와 P0 planner messages에서 같은지 확인한다.
- 원문 보존(결정 66): 표본마다 jsonl 한 줄에 다음을 남긴다.
  - 식별: item id, question, dataset version, source
  - 실행 조건: model·revision·tokenizer, prompt hash, seed, 생성 설정
  - 원문: raw_text, thinking, content(최종 응답), 생성 token id
  - 결과: parsed, 판정
- 판정(`judge`): 범주는 하나다.
  - EXACT_OR_SEMANTIC_MATCH: 조건 계층 전 원 출력이 맞다. 응답 JSON을 parser로 완성한 뒤
    `evaluate_vendor100.grounding_check`를 Full canonical gold에 대고 잰다(기존 collect_traces.judge와 같은 기준).
  - STRUCTURALLY_REPAIRABLE: 원 출력은 다르지만 운영 경로(조건 계층·compose·validate·compile)의 실행 결과와
    의미 서명(EVENT 제외)이 P0 target과 같다.
  - SEMANTIC_MISMATCH: parse되고 거부가 아닌데 운영 경로 뒤에도 다르다.
  - REFUSAL_MISMATCH: `{"unsupported": true}`인데 target은 지원 질문이다(v006 target에 unsupported 없음).
  - UNPARSEABLE: thinking이 닫히지 않음(생성 상한), 최종 응답이 비었음, JSON이 아님.
- `--resume`: 기반 장애(crash·OOM)일 때만 쓴다. 9개 표본이 다 있는 질문은 건너뛰고 남은 질문부터 같은 명세로 잇는다.
"""
import argparse
import copy
import hashlib
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/thinking_prep_001"))

import hf_thinking as H  # noqa: E402

SAMPLES = 8
BASE_SEED = 20261006
P0_PROMPT = ROOT / "evaluation/partial_grounding/prompts/partial_p0.yaml"
EXPECTED_P0_SHA = "d7f4c12a"
CATEGORIES = ("EXACT_OR_SEMANTIC_MATCH", "STRUCTURALLY_REPAIRABLE", "SEMANTIC_MISMATCH", "REFUSAL_MISMATCH", "UNPARSEABLE")


def p0_planner():
    from geoflow.planner import GeoFlowPlanner, load_planner_prompt
    planner = GeoFlowPlanner(client=None, prompt=load_planner_prompt(P0_PROMPT))
    sha = hashlib.sha256(planner.system_prompt().encode("utf-8")).hexdigest()
    if not sha.startswith(EXPECTED_P0_SHA):
        raise SystemExit(f"P0 system prompt hash {sha[:8]} != {EXPECTED_P0_SHA}")
    return planner, sha


def judge(question, content, think_closed, target_p0, target_full):
    """(판정 dict, parsed payload)."""
    import evaluate_vendor100 as EV
    import build_targets as BT
    from geoflow.grounding import complete_grounding_payload
    from geoflow.planner import parse_planner_json
    from training.data.validation import assess_t2pc
    out = {"category": None, "match_raw": False, "raw_diffs": [], "match_after_conditions": False,
           "exact_json": False, "outcome": None, "error_code": None}
    if not think_closed:
        out.update(category="UNPARSEABLE", reason="think_not_closed")
        return out, None
    if not content:
        out.update(category="UNPARSEABLE", reason="empty_content")
        return out, None
    try:
        payload = parse_planner_json(content)
    except Exception as error:  # noqa: BLE001 - JSON이 아닌 응답
        out.update(category="UNPARSEABLE", reason=f"no_json:{type(error).__name__}")
        return out, None
    if not isinstance(payload, dict):
        out.update(category="UNPARSEABLE", reason="not_object")
        return out, None
    out["exact_json"] = payload == target_p0
    if payload.get("unsupported"):
        out.update(category="REFUSAL_MISMATCH" if not target_p0.get("unsupported") else "EXACT_OR_SEMANTIC_MATCH",
                   match_raw=bool(target_p0.get("unsupported")))
        return out, payload
    try:
        same, diffs = EV.grounding_check({"gold_grounding": target_full, "gold": None},
                                         complete_grounding_payload(copy.deepcopy(payload)))
        out["match_raw"], out["raw_diffs"] = bool(same), json.loads(json.dumps(diffs, ensure_ascii=False))
    except Exception as error:  # noqa: BLE001 - 계약 밖 형태는 원 출력 불일치로 둔다
        out["raw_error"] = type(error).__name__
    try:
        a, b = assess_t2pc(payload, question), assess_t2pc(target_p0, question)
        out["match_after_conditions"] = (BT.exec_view(a) == BT.exec_view(b)
                                         and BT.strip_events(a.get("signature")) == BT.strip_events(b.get("signature")))
        out["outcome"], out["error_code"] = a.get("outcome"), a.get("error_code")
    except Exception as error:  # noqa: BLE001
        out["after_error"] = type(error).__name__
    out["category"] = ("EXACT_OR_SEMANTIC_MATCH" if out["match_raw"] else
                       "STRUCTURALLY_REPAIRABLE" if out["match_after_conditions"] else "SEMANTIC_MISMATCH")
    return out, payload


def load_records(path, planner):
    records = []
    for qi, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines()):
        if not line.strip():
            continue
        r = json.loads(line)
        messages = r["messages"][:2]
        if planner.messages(messages[1]["content"]) != messages:
            raise SystemExit(f"{r['metadata']['source_record_id']}: 레코드 입력이 P0 planner messages와 다르다")
        records.append({"qi": qi, "messages": messages, "question": messages[1]["content"],
                        "target_p0": json.loads(r["messages"][2]["content"]), "meta": r["metadata"]})
    return records


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default=str(ROOT / "training/generated/reviewed_gold_v006_p0/sft_train.jsonl"))
    ap.add_argument("--out", default=str(ROOT / "training/generated/thinking_traces/p0_v006_hf"))
    ap.add_argument("--summary", default=str(HERE / "traces_hf"))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--resume", action="store_true")
    a = ap.parse_args()
    planner, sha = p0_planner()
    records = load_records(a.dataset, planner)
    plan = {"records": len(records), "prompt_sha256": sha, "samples_per_question": 1 + SAMPLES,
            "requests_planned": len(records) * (1 + SAMPLES)}
    if a.dry_run:
        print(json.dumps(plan, ensure_ascii=False))
        return 0
    out_dir, summary_dir = Path(a.out), Path(a.summary)
    traces = out_dir / "traces.jsonl"
    done = set()
    if traces.exists():
        if not a.resume:
            raise SystemExit(f"{traces}가 이미 있다(기반 장애 뒤 이어 받을 때만 --resume)")
        counts = {}
        for line in traces.read_text(encoding="utf-8").splitlines():
            counts[json.loads(line)["item_id"]] = counts.get(json.loads(line)["item_id"], 0) + 1
        done = {k for k, v in counts.items() if v == 1 + SAMPLES}
        partial = {k for k, v in counts.items() if v != 1 + SAMPLES}
        if partial:
            raise SystemExit(f"표본이 일부만 있는 질문: {sorted(partial)}")
    out_dir.mkdir(parents=True, exist_ok=True)
    summary_dir.mkdir(parents=True, exist_ok=True)

    import torch
    import transformers
    import execution_spec
    dataset_sha = hashlib.sha256(Path(a.dataset).read_bytes()).hexdigest()
    started = time.perf_counter()
    client = H.load_client()
    device = torch.cuda.get_device_properties(0)
    settings = {"enable_thinking": True, "max_new_tokens": H.MAX_NEW_TOKENS, "greedy": {"do_sample": False},
                "sampling": {"do_sample": True, **H.SAMPLING, "num_return_sequences": SAMPLES},
                "seed_rule": f"{BASE_SEED} + question index (dataset file order)"}
    runtime = {"model": H.MODEL, "revision": H.REVISION, "tokenizer": f"{H.MODEL}@{H.REVISION}", "adapter": None,
               "torch": torch.__version__, "transformers": transformers.__version__, "device": device.name,
               "device_uuid": f"GPU-{device.uuid}", "dtype": str(next(client.policy.parameters()).dtype),
               "attention": client.policy.config._attn_implementation,
               "chat_template_kwargs": client.config["chat_template_kwargs"], "settings": settings,
               "prompt_sha256": sha, "dataset": a.dataset, "dataset_sha256": dataset_sha,
               "code_fingerprint": execution_spec.code_fingerprint(ROOT)["sha256"],
               "load_seconds": round(time.perf_counter() - started, 1), "resumed_skip": sorted(done),
               "started_at": datetime.now(ZoneInfo("Asia/Seoul")).isoformat()}
    run_name = "run.json" if not done else f"run_resume_{len(done)}.json"
    (summary_dir / run_name).write_text(json.dumps(runtime, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    with open(traces, "a", encoding="utf-8") as stream:
        for rec in records:
            meta = rec["meta"]
            sid = meta["source_record_id"]
            if sid in done:
                continue
            t0 = time.perf_counter()
            outputs = [("greedy", 0, None, r) for r in client.generate(rec["messages"])]
            seed = BASE_SEED + rec["qi"]
            outputs += [("sample", k + 1, seed, r) for k, r in enumerate(
                client.generate(rec["messages"], sample=True, num_return_sequences=SAMPLES, seed=seed))]
            seconds = time.perf_counter() - t0
            cats = []
            for kind, index, s, result in outputs:
                verdict, payload = judge(rec["question"], result["content"], result["think_closed"], rec["target_p0"],
                                         meta["target_full"])
                cats.append(verdict["category"])
                row = {"trace_id": f"{sid}:{kind}:{index}", "item_id": sid, "question_index": rec["qi"],
                       "question": rec["question"], "dataset_version": meta["dataset_version"], "source": meta["source"],
                       "model": H.MODEL, "revision": H.REVISION, "tokenizer": f"{H.MODEL}@{H.REVISION}",
                       "prompt_sha256": sha, "kind": kind, "sample_index": index, "seed": s,
                       "generation": settings["greedy"] if kind == "greedy" else settings["sampling"],
                       "max_new_tokens": H.MAX_NEW_TOKENS, "enable_thinking": True,
                       **{k: result[k] for k in ("raw_text", "raw_sha256", "thinking", "content", "think_closed",
                                                 "prompt_tokens", "generated_tokens", "done_reason", "generated_ids")},
                       "parsed": payload, "judge": verdict, "question_seconds": round(seconds, 1),
                       "collected_at": datetime.now(ZoneInfo("Asia/Seoul")).isoformat()}
                stream.write(json.dumps(row, ensure_ascii=False) + "\n")
            stream.flush()
            print(json.dumps({"qi": rec["qi"], "id": sid, "greedy": cats[0], "match_of_8": cats[1:].count(CATEGORIES[0]),
                              "truncated": sum(r[3]["done_reason"] == "length" for r in outputs),
                              "seconds": round(seconds, 1)}, ensure_ascii=False), flush=True)
    runtime.update(finished_at=datetime.now(ZoneInfo("Asia/Seoul")).isoformat(),
                   seconds=round(time.perf_counter() - started, 1), peak_allocated_bytes=torch.cuda.max_memory_allocated(),
                   traces_sha256=hashlib.sha256(traces.read_bytes()).hexdigest())
    (summary_dir / run_name).write_text(json.dumps(runtime, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("COLLECTION_DONE", json.dumps({"records": len(records), "seconds": runtime["seconds"]}), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
