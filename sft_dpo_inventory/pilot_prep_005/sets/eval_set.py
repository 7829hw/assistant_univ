# -*- coding: utf-8 -*-
"""선택용 셋·보조 시험 셋(결정 41·42·46)을 HF-E 조건으로 잰다. 업체 100은 쓰지 않는다.

    CUDA_VISIBLE_DEVICES=N HF_HOME=... HF_HUB_OFFLINE=1 python sft_dpo_inventory/pilot_prep_005/sets/eval_set.py \
        --items sft_dpo_inventory/pilot_prep_005/sets/selection_items.json --label base --out RESULT.json --raw-out RAW.jsonl \
        [--adapter CHECKPOINT_DIR]

``pilot_001/valid98/eval_valid98.py``와 같다. 다른 것은 문항 목록을 ``--items``로 받는 것뿐이다(그 파일의 원본 sha256을 대조).
- 모델·생성: ``thinking_prep_001/hf_thinking``(base Qwen3-8B@b968826d, ``enable_thinking=True``, greedy, max_new_tokens 8192,
  BF16·SDPA). ``--adapter``는 PEFT adapter 폴더(DPO checkpoint는 ``policy/``).
- pipeline: ``pilot_prep_002/valid_eval/provider_eval.make_pipeline``(flat, 조건 계층 켬, condition_notes 끔, 기준일 2026-09-25),
  provider mock.
- 채점: 최종 grounding을 정답 grounding(``evaluate_vendor100.gold_grounding``)과 ``grounding_check``로 비교한 ``grounding_ok``.
  참고로 업체 100과 같은 호출 단위 채점(``score``) 범주도 남긴다.
- 원문은 ``--raw-out``에 저장하고, 결과에는 sha256만 남긴다. 질문 문장은 결과에 넣지 않는다.
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
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/thinking_prep_001"))
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_prep_002/valid_eval"))

import evaluate_vendor100 as EV  # noqa: E402
import hf_thinking as H  # noqa: E402
import provider_eval as P  # noqa: E402

REFERENCE_DATE = date(2026, 9, 25)
PLACE_REPAIR_PREFIX = "방금 고른 장소로 조회했으나"


def valid_items(items_path):
    spec = json.loads(Path(items_path).read_text(encoding="utf-8"))
    for path, digest in spec["sources_sha256"].items():
        if hashlib.sha256((ROOT / path).read_bytes()).hexdigest() != digest:
            raise SystemExit(f"valid source changed: {path}")
    documents = {}
    items = []
    for ref in spec["items"]:
        if ref["path"] not in documents:
            documents[ref["path"]] = {i["id"]: i for i in EV.load_gold(ROOT / ref["path"])["items"]}
        item = dict(documents[ref["path"]][ref["id"]])
        item["valid_id"] = f"{ref['set']}/{ref['id']}"
        items.append(item)
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
    parser.add_argument("--items", required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--raw-out", required=True)
    parser.add_argument("--adapter", default=None)
    args = parser.parse_args()
    if ROOT in Path(args.raw_out).resolve().parents and "generated" not in Path(args.raw_out).parts:
        raise SystemExit("--raw-out은 저장소 밖이나 ignore 경로(generated)여야 한다")

    import torch
    from geoflow.planner import GeoFlowPlanner
    import execution_spec

    EV.REFERENCE_DATE = REFERENCE_DATE
    adapter = adapter_dir(args.adapter)
    prompt_sha = hashlib.sha256(GeoFlowPlanner(client=None).system_prompt().encode("utf-8")).hexdigest()
    started = time.perf_counter()
    client = H.load_client(adapter=adapter)
    load_seconds = time.perf_counter() - started
    device = torch.cuda.get_device_properties(0)
    items = valid_items(args.items)
    Path(args.raw_out).parent.mkdir(parents=True, exist_ok=True)
    rows = []
    with open(args.raw_out, "w", encoding="utf-8") as raw_stream:
        for item in items:
            item_started = time.perf_counter()
            client.log = []
            recorder = EV._RecordingClient(client)
            provider, provider_class = "mock", None
            pipeline = P.make_pipeline(recorder, provider)
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
            category, checks = EV.score(item, observed)
            for index, raw in enumerate(raws):
                raw_stream.write(json.dumps({"label": args.label, "id": item["valid_id"], "call": index, **{k: raw[k] for k in (
                    "raw_text", "raw_sha256", "generated_tokens", "done_reason", "think_closed")}},
                    ensure_ascii=False) + "\n")
            rows.append({
                "id": item["valid_id"], "provider": provider, "grounding_ok": bool(grounding_ok),
                "vendor_style_category": category, "expected_outcome": item.get("expected_outcome", "answered"),
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
            print(f"{args.label} {item['valid_id']} ok={grounding_ok} {observed['outcome']} {observed['error_code'] or ''} "
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
        "label": args.label, "set": str(Path(args.items).resolve().relative_to(ROOT)),
        "set_sha256": hashlib.sha256(Path(args.items).read_bytes()).hexdigest(),
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
        "scorer": "evaluate_vendor100.grounding_check(final grounding) against gold derived from gold calls",
        "finished_at": datetime.now(ZoneInfo("Asia/Seoul")).isoformat()}
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps({"meta": meta, "summary": summary, "rows": rows}, ensure_ascii=False, indent=1)
                              + "\n", encoding="utf-8")
    print(json.dumps({"label": args.label, **summary}, ensure_ascii=False))


if __name__ == "__main__":
    main()
