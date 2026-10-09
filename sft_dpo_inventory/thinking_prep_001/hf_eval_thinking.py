# -*- coding: utf-8 -*-
"""업체 100을 HF 모델(thinking 켬)로 평가한다. pipeline·채점은 Ollama 셀과 같은 코드(evaluate_vendor100)다.

    CUDA_VISIBLE_DEVICES=2 HF_HOME=... HF_HUB_OFFLINE=1 python sft_dpo_inventory/thinking_prep_001/hf_eval_thinking.py \
        --condition-check --out RESULT.json --raw-out RAW.jsonl [--adapter ADAPTER_DIR]

- ``pilot_prep_001/hf_eval_vendor100.py``와 같은 구성이고, 모델 호출만 thinking 켬 client(``hf_thinking``)로 바꿨다:
  ``enable_thinking=True``, greedy, max_new_tokens 8192(측정 전에 고정), BF16·SDPA.
- 응답의 thinking과 본문을 나눠 ``_RecordingClient``가 Ollama 기록과 같은 형식(content, thinking_chars, token 수,
  done_reason)으로 남긴다. 생성 상한에 걸린 응답은 done_reason=length로 planner의 잘림 처리를 받는다.
- 원문(thinking 포함)은 ``--raw-out``(저장소 밖 또는 ignore 경로)에만 저장하고, 결과 파일에는 원문 sha256만 남긴다.
- 업체 100은 평가 전용이다. 학습·checkpoint 선택·trace 선택에 쓰지 않는다.
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
sys.path.insert(0, str(HERE))

import evaluate_vendor100 as EV  # noqa: E402
import hf_thinking as H  # noqa: E402


def sampling_settings(args):
    """--do-sample이면 temperature·top_p·top_k·seed가 모두 있어야 한다. 없으면 None(greedy)."""
    values = {"temperature": args.temperature, "top_p": args.top_p, "top_k": args.top_k, "seed": args.seed}
    if not args.do_sample:
        if any(value is not None for value in values.values()) or any(getattr(args, name, None) is not None for name in ("min_p", "repetition_penalty")):
            raise SystemExit("sampling 값은 --do-sample과 함께만 쓴다")
        return None
    missing = [key for key, value in values.items() if value is None]
    if missing:
        raise SystemExit(f"--do-sample은 --temperature, --top-p, --top-k, --seed를 모두 지정해야 한다(빠짐: {missing})")
    params = {"temperature": args.temperature, "top_p": args.top_p, "top_k": args.top_k}
    # calibration_001: 명시한 값만 generate()에 더한다. 주지 않으면 이전과 같다.
    for name in ("min_p", "repetition_penalty"):
        if getattr(args, name, None) is not None:
            params[name] = getattr(args, name)
    return {"params": params, "round_seed": args.seed}


def transformers_version():
    import transformers
    return transformers.__version__


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    parser.add_argument("--raw-out", required=True)
    parser.add_argument("--adapter", default=None)
    parser.add_argument("--condition-check", action="store_true")
    parser.add_argument("--reference-date", type=date.fromisoformat, default=date(2026, 9, 25))
    parser.add_argument("--only", default="")
    # sampling(path_repeat_001 PLAN.md). 주지 않으면 이전과 같은 greedy다.
    parser.add_argument("--do-sample", action="store_true")
    parser.add_argument("--temperature", type=float, default=None)
    parser.add_argument("--top-p", type=float, default=None)
    parser.add_argument("--top-k", type=int, default=None)
    parser.add_argument("--seed", type=int, default=None, help="회차 seed. 호출 seed는 EV.call_seed(회차 seed, 문항 id, 호출 순번)")
    parser.add_argument("--min-p", type=float, default=None, help="sampling generate(min_p=...)(calibration_001, 명시할 때만)")
    parser.add_argument("--repetition-penalty", type=float, default=None, help="sampling generate(repetition_penalty=...)")
    parser.add_argument("--gold", default=None, help="평가 문항 파일(기본: 업체 gold). calibration_001은 selection_gold.yaml")
    parser.add_argument("--record-env", action="store_true", help="meta에 GPU·드라이버·소프트웨어 판을 남긴다(생성에는 영향 없음)")
    args = parser.parse_args()
    sampling = sampling_settings(args)
    if ROOT in Path(args.raw_out).resolve().parents and "generated" not in Path(args.raw_out).parts:
        raise SystemExit("--raw-out은 저장소 밖이나 ignore 경로(generated)여야 한다")

    import torch
    from geoflow import providers
    from geoflow.pipeline import GeoFlowPipeline
    from geoflow.planner import GeoFlowPlanner
    import execution_spec

    EV.REFERENCE_DATE = args.reference_date
    prompt_sha = hashlib.sha256(GeoFlowPlanner(client=None).system_prompt().encode("utf-8")).hexdigest()
    started = time.perf_counter()
    client = H.load_client(adapter=args.adapter)
    load_seconds = time.perf_counter() - started
    device = torch.cuda.get_device_properties(0)
    gold_path = Path(args.gold).resolve() if args.gold else None
    if gold_path is not None:
        EV.GOLD_PATH = gold_path     # meta의 gold_file·gold_sha256도 이 파일로 남는다
    items = [i for i in EV.load_gold(gold_path)["items"] if not args.only or i["id"] in args.only.split(",")]
    Path(args.raw_out).parent.mkdir(parents=True, exist_ok=True)
    rows = []
    with open(args.raw_out, "w", encoding="utf-8") as raw_stream:
        for item in items:
            item_started = datetime.now(ZoneInfo("Asia/Seoul"))
            client.log = []
            recorder = EV._RecordingClient(client)
            options = {"condition_notes": False} if args.condition_check else {}
            pipeline = GeoFlowPipeline.create(
                client=recorder, tool_executor=EV._executor(), aggregation_grounding="flat",
                clock=lambda: EV.REFERENCE_DATE, condition_check=args.condition_check,
                execution_profile=providers.profile_for(providers.MOCK, providers.LEGACY), **options)
            raws = []
            calls = [0]     # 문항 안 호출 순번(실패한 호출도 센다)
            original_chat = client.chat

            def chat(messages, tools=None, item_id=item["id"], **kwargs):
                seed = None
                if sampling is not None:    # repair 등 문항 안의 모든 호출에 같은 설정과 seed 규칙
                    seed = EV.call_seed(sampling["round_seed"], item_id, calls[0])
                    client.sampling_call = {"seed": seed, "params": sampling["params"]}
                calls[0] += 1
                try:
                    response = original_chat(messages, tools=tools, **kwargs)
                finally:
                    client.sampling_call = None
                raws.append(client.last if seed is None else {**client.last, "sampling_seed": seed})
                return response
            client.chat = chat
            try:
                observed = EV.run_item(pipeline, item["question"])
            except Exception as error:  # noqa: BLE001 - evaluate_vendor100 llm과 같은 처리
                observed = EV._crashed(error)
            finally:
                client.chat = original_chat
            category, checks = EV.score(item, observed)
            grounding_ok, grounding_diffs = EV.grounding_check(item, observed["grounding"])
            for index, raw in enumerate(raws):
                record = {"id": item["id"], "call": index, **{k: raw[k] for k in (
                    "raw_text", "raw_sha256", "generated_tokens", "done_reason", "think_closed")}}
                if sampling is not None:
                    record["sampling_seed"] = raw["sampling_seed"]
                raw_stream.write(json.dumps(record, ensure_ascii=False) + "\n")
            rows.append({"id": item["id"], "question": item["question"], "vendor_verdict": item["vendor_verdict"],
                         "category": category, "checks": checks, "reset_ok": None,
                         "grounding_ok": grounding_ok, "grounding_diffs": grounding_diffs,
                         "llm_calls": recorder.calls, "hf_calls": client.log,
                         "started_at": item_started.isoformat(),
                         "finished_at": datetime.now(ZoneInfo("Asia/Seoul")).isoformat(), **observed})
            print(f"{item['id']} {category} {observed['outcome']} {observed['error_code'] or ''} "
                  f"{[c['generated_tokens'] for c in client.log]}", flush=True)
    meta = EV._meta("llm", {
        "model": f"hf:{H.MODEL}@{H.REVISION}" + (f"+{args.adapter}" if args.adapter else ""),
        "model_digest": None, "ollama_version": None,
        "hf": {"model": H.MODEL, "revision": H.REVISION, "adapter": args.adapter,
               "dtype": str(next(client.policy.parameters()).dtype), "attention": client.policy.config._attn_implementation,
               "chat_template_kwargs": client.config["chat_template_kwargs"],
               "decoding": ({"do_sample": False, "max_new_tokens": H.MAX_NEW_TOKENS, "seed": 42} if sampling is None else
                            {"do_sample": True, **sampling["params"], "max_new_tokens": H.MAX_NEW_TOKENS,
                             "round_seed": sampling["round_seed"], "seed_rule": EV.SEED_RULE,
                             "seed_application": "torch.manual_seed·cuda.manual_seed_all 직전 설정, 호출마다"}),
               "torch": torch.__version__, "cuda": torch.version.cuda, "device": device.name,
               "device_uuid": f"GPU-{device.uuid}", "load_seconds": round(load_seconds, 1),
               "peak_allocated_bytes": torch.cuda.max_memory_allocated(),
               "raw_out": str(Path(args.raw_out).resolve()),
               "raw_out_sha256": hashlib.sha256(Path(args.raw_out).read_bytes()).hexdigest(),
               **({"environment": {**EV.environment_record(), "transformers": transformers_version(),
                                   "cudnn": torch.backends.cudnn.version()}} if args.record_env else {})},
        "planner_prompt_sha256": prompt_sha, "code_fingerprint": execution_spec.code_fingerprint(ROOT)["sha256"],
        "pipeline": {"aggregation_grounding": "flat", "condition_check": args.condition_check, "condition_notes": False,
                     "normalize_grounding": True, "semantic_reinterpretation": True, "provider": "mock",
                     "tims_execution": "legacy", "client": "hf", "think": "on(enable_thinking=True)",
                     "isolation": "process_local_model_kept_loaded(no conversation state)"},
        "item_order": [i["id"] for i in items], "finished_at": datetime.now(ZoneInfo("Asia/Seoul")).isoformat(),
        "scorer_version": EV.SCORER_VERSION})
    result = {"meta": meta, "summary": EV._summary(rows), "rows": rows}
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    truncated = sum(1 for r in rows for c in r["hf_calls"] if c["done_reason"] == "length")
    print(json.dumps({"items": len(rows), "grounding_ok": sum(bool(r["grounding_ok"]) for r in rows),
                      "truncated_calls": truncated, "categories": result["summary"]["categories"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
