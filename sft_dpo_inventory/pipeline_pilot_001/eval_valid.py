# -*- coding: utf-8 -*-
"""v003_t2pc valid 16문항을 HF-E와 같은 조건으로 잰다(checkpoint 선택용). 업체 100은 쓰지 않는다.

    CUDA_VISIBLE_DEVICES=2 HF_HOME=... HF_HUB_OFFLINE=1 python sft_dpo_inventory/pipeline_pilot_001/eval_valid.py \
        --label base --out RESULT.json --raw-out RAW.jsonl [--adapter CHECKPOINT_DIR]

- 모델·생성: ``thinking_prep_001/hf_thinking``(base Qwen3-8B@b968826d, ``enable_thinking=True``, greedy,
  max_new_tokens 8192, BF16·SDPA). ``--adapter``는 PEFT adapter 폴더이다. DPO checkpoint처럼 adapter가
  ``policy/`` 아래에 있으면 그것을 쓴다.
- pipeline: ``hf_eval_thinking.py``와 같은 구성(flat, 조건 계층 켬, condition_notes 끔, mock·legacy, 기준일 2026-09-25)과
  같은 ``evaluate_vendor100.run_item``.
- 채점: gold는 ``reviewed_gold_v003_t2pc/sft_valid.jsonl``의 정답 JSON이다. ``evaluate_vendor100.grounding_check``로
  최종 grounding(정규화·조건 계층·검증 뒤)을 비교한 값이 ``grounding_ok``(선택 기준)이다. 업체 정답 호출이 없으므로
  호출 단위 채점(``score``)은 하지 않는다. 첫 계획 응답 본문 JSON의 일치(``first_raw_ok``)는 참고로만 남긴다.
- valid의 합성 장소명(가람구, 솔빛시, 해온시 등)은 mock provider가 모른다. 장소 조회 실패 뒤의 장소 재질의는
  운영 경로 그대로 모델에 간다. 재질의 수를 문항마다 남긴다.
- 원문(thinking 포함)은 ``--raw-out``(저장소 밖 또는 ignore 경로)에만 저장하고, 결과에는 sha256만 남긴다.
"""
import argparse
import hashlib
import json
import sys
import time
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/thinking_prep_001"))

import evaluate_vendor100 as EV  # noqa: E402
import hf_thinking as H  # noqa: E402

CORPUS = ROOT / "training/generated/reviewed_gold_v003_t2pc"
REFERENCE_DATE = date(2026, 9, 25)
PLACE_REPAIR_PREFIX = "방금 고른 장소로 조회했으나"


def valid_items():
    from training.data.common import read_jsonl
    items = []
    for record in read_jsonl(CORPUS / "sft_valid.jsonl"):
        items.append({"id": record["metadata"]["source_record_id"], "question": record["messages"][1]["content"],
                      "gold_grounding": json.loads(record["messages"][2]["content"]), "gold": None})
    return items


def adapter_dir(path):
    if path is None:
        return None
    path = Path(path)
    if (path / "adapter_config.json").exists():
        return str(path)
    if (path / "policy/adapter_config.json").exists():
        return str(path / "policy")
    raise SystemExit(f"adapter_config.json이 없다: {path}")


def adapter_sha256(path):
    if path is None:
        return None
    for name in ("adapter_model.safetensors", "adapter_model.bin"):
        if (Path(path) / name).exists():
            return hashlib.sha256((Path(path) / name).read_bytes()).hexdigest()
    return None


def first_raw_ok(item, raw):
    from geoflow.planner import parse_planner_json
    if raw is None or not raw.get("think_closed"):
        return False
    try:
        payload = parse_planner_json(raw["content"])
    except Exception:  # noqa: BLE001 - JSON이 아닌 본문
        return False
    return bool(EV.grounding_check(item, payload)[0])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--raw-out", required=True)
    parser.add_argument("--adapter", default=None)
    args = parser.parse_args()
    if ROOT in Path(args.raw_out).resolve().parents and "generated" not in Path(args.raw_out).parts:
        raise SystemExit("--raw-out은 저장소 밖이나 ignore 경로(generated)여야 한다")

    import torch
    from geoflow import providers
    from geoflow.pipeline import GeoFlowPipeline
    from geoflow.planner import GeoFlowPlanner
    import execution_spec

    EV.REFERENCE_DATE = REFERENCE_DATE
    adapter = adapter_dir(args.adapter)
    prompt_sha = hashlib.sha256(GeoFlowPlanner(client=None).system_prompt().encode("utf-8")).hexdigest()
    started = time.perf_counter()
    client = H.load_client(adapter=adapter)
    load_seconds = time.perf_counter() - started
    device = torch.cuda.get_device_properties(0)
    items = valid_items()
    Path(args.raw_out).parent.mkdir(parents=True, exist_ok=True)
    rows = []
    with open(args.raw_out, "w", encoding="utf-8") as raw_stream:
        for item in items:
            item_started = time.perf_counter()
            client.log = []
            recorder = EV._RecordingClient(client)
            pipeline = GeoFlowPipeline.create(
                client=recorder, tool_executor=EV._executor(), aggregation_grounding="flat",
                clock=lambda: REFERENCE_DATE, condition_check=True, condition_notes=False,
                execution_profile=providers.profile_for(providers.MOCK, providers.LEGACY))
            raws, requests = [], []
            original_chat = client.chat

            def chat(messages, tools=None, **kwargs):
                requests.append((messages[-1].get("content") or "").split("\n", 1)[0] if raws else "plan")
                response = original_chat(messages, tools=tools, **kwargs)
                raws.append(client.last)
                return response
            client.chat = chat
            try:
                observed = EV.run_item(pipeline, item["question"])
            except Exception as error:  # noqa: BLE001 - evaluate_vendor100 llm과 같은 처리
                observed = EV._crashed(error)
            finally:
                client.chat = original_chat
            grounding_ok, grounding_diffs = EV.grounding_check(item, observed["grounding"])
            for index, raw in enumerate(raws):
                raw_stream.write(json.dumps({"label": args.label, "id": item["id"], "call": index, **{k: raw[k] for k in (
                    "raw_text", "raw_sha256", "generated_tokens", "done_reason", "think_closed")}},
                    ensure_ascii=False) + "\n")
            rows.append({
                "id": item["id"], "question": item["question"], "grounding_ok": bool(grounding_ok),
                "grounding_diffs": json.loads(json.dumps(grounding_diffs, ensure_ascii=False)),
                "first_raw_ok": first_raw_ok(item, raws[0] if raws else None),
                "outcome": observed["outcome"], "error_code": observed["error_code"],
                "model_calls": len(raws),
                "place_repair_calls": sum(1 for r in requests if r.startswith(PLACE_REPAIR_PREFIX)),
                "other_repair_calls": sum(1 for r in requests[1:] if not r.startswith(PLACE_REPAIR_PREFIX)),
                "generated_tokens": [r["generated_tokens"] for r in raws],
                "done_reasons": [r["done_reason"] for r in raws],
                "thinking_chars_first_plan": len(raws[0]["thinking"]) if raws else None,
                "raw_sha256": [r["raw_sha256"] for r in raws],
                "seconds": round(time.perf_counter() - item_started, 1),
                "grounding": observed["grounding"], "condition_corrections": observed.get("condition_corrections"),
                "planner_trace": observed["planner_trace"]})
            print(f"{args.label} {item['id']} ok={grounding_ok} {observed['outcome']} {observed['error_code'] or ''} "
                  f"{[r['generated_tokens'] for r in raws]}", flush=True)
    summary = {"items": len(rows), "grounding_ok": sum(r["grounding_ok"] for r in rows),
               "first_raw_ok": sum(r["first_raw_ok"] for r in rows),
               "outcomes": {}, "model_calls": sum(r["model_calls"] for r in rows),
               "place_repair_calls": sum(r["place_repair_calls"] for r in rows),
               "other_repair_calls": sum(r["other_repair_calls"] for r in rows),
               "truncated_calls": sum(d == "length" for r in rows for d in r["done_reasons"]),
               "seconds": round(sum(r["seconds"] for r in rows), 1)}
    for r in rows:
        key = f"{r['outcome']}:{r['error_code']}"
        summary["outcomes"][key] = summary["outcomes"].get(key, 0) + 1
    meta = {
        "label": args.label, "set": "reviewed_gold_v003_t2pc/sft_valid.jsonl",
        "set_sha256": hashlib.sha256((CORPUS / "sft_valid.jsonl").read_bytes()).hexdigest(),
        "model": f"hf:{H.MODEL}@{H.REVISION}", "adapter": adapter, "adapter_sha256": adapter_sha256(adapter),
        "dtype": str(next(client.policy.parameters()).dtype), "attention": client.policy.config._attn_implementation,
        "chat_template_kwargs": client.config["chat_template_kwargs"],
        "decoding": {"do_sample": False, "max_new_tokens": H.MAX_NEW_TOKENS, "seed": 42},
        "torch": torch.__version__, "device": device.name, "device_uuid": f"GPU-{device.uuid}",
        "load_seconds": round(load_seconds, 1), "peak_allocated_bytes": torch.cuda.max_memory_allocated(),
        "raw_out": str(Path(args.raw_out).resolve()),
        "raw_out_sha256": hashlib.sha256(Path(args.raw_out).read_bytes()).hexdigest(),
        "planner_prompt_sha256": prompt_sha, "code_fingerprint": execution_spec.code_fingerprint(ROOT)["sha256"],
        "reference_date": REFERENCE_DATE.isoformat(),
        "pipeline": {"aggregation_grounding": "flat", "condition_check": True, "condition_notes": False,
                     "provider": "mock", "tims_execution": "legacy", "client": "hf", "think": "on(enable_thinking=True)"},
        "scorer": "evaluate_vendor100.grounding_check(final grounding) against reviewed gold",
        "finished_at": datetime.now(ZoneInfo("Asia/Seoul")).isoformat()}
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps({"meta": meta, "summary": summary, "rows": rows}, ensure_ascii=False, indent=1)
                              + "\n", encoding="utf-8")
    print(json.dumps({"label": args.label, **summary}, ensure_ascii=False))


if __name__ == "__main__":
    main()
