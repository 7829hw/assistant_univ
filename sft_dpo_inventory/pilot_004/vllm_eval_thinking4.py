# -*- coding: utf-8 -*-
"""(pilot_004 업체 100 단계 전용) vLLM 서버로 평가한다. ``serving_vllm/vllm_eval_thinking.py``의 사본이고, 업체 100·aux_test_v1 gold를 막던
검사(결정 89 범위)만 뺐다. pilot_004 작업 7(중단 규칙 통과 뒤 업체 100·aux_test_v1·valid98 셀)에서만 쓴다. 나머지는 원본과 같다.

    hfvenv/bin/python sft_dpo_inventory/serving_vllm/vllm_eval_thinking.py --base-url http://127.0.0.1:8100 --served-model base \
        --gold sft_dpo_inventory/conversion_diag/selection_gold.yaml --only IDS --condition-check \
        --do-sample --temperature 0.6 --top-p 0.95 --top-k 20 --min-p 0 --repetition-penalty 1 --seed 20261101 \
        --out RESULT.json --raw-out RAW.jsonl

- pipeline·채점·seed 규칙(``EV.call_seed``)·기록 형식은 hf_eval_thinking과 같다. ``hf_calls`` 자리에 vLLM 호출 기록(``vllm_calls``와 같은 내용)을 둔다.
- 원문(thinking 포함)은 ``--raw-out``(ignore 경로)에만 쓴다.
- 업체 100과 aux_test_v1은 쓰지 않는다(결정 89). gold가 그 둘이면 멈춘다.
"""
import argparse
import hashlib
import json
import sys
import time
import urllib.request
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/thinking_prep_001"))
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/serving_vllm"))

import evaluate_vendor100 as EV  # noqa: E402
import hf_eval_thinking as HE  # noqa: E402  (sampling_settings)
import hf_thinking as H  # noqa: E402
from vllm_thinking import VLLMThinkingClient  # noqa: E402

FORBIDDEN = set()   # 원본은 업체 100·aux_test_v1을 막았다(결정 89). 이 사본은 pilot_004 작업 7 전용


def server_info(base_url):
    out = {}
    for path in ("/version", "/v1/models"):
        try:
            with urllib.request.urlopen(base_url.rstrip("/") + path, timeout=30) as r:
                out[path] = json.loads(r.read().decode("utf-8"))
        except Exception as error:  # noqa: BLE001
            out[path] = f"error: {error}"
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--served-model", required=True, help="서버의 모델 이름(base 또는 LoRA 이름)")
    parser.add_argument("--label", default=None)
    parser.add_argument("--out", required=True)
    parser.add_argument("--raw-out", required=True)
    parser.add_argument("--condition-check", action="store_true")
    parser.add_argument("--reference-date", type=date.fromisoformat, default=date(2026, 9, 25))
    parser.add_argument("--only", default="")
    parser.add_argument("--do-sample", action="store_true")
    parser.add_argument("--temperature", type=float, default=None)
    parser.add_argument("--top-p", type=float, default=None)
    parser.add_argument("--top-k", type=int, default=None)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--min-p", type=float, default=None)
    parser.add_argument("--repetition-penalty", type=float, default=None)
    parser.add_argument("--gold", required=True)
    parser.add_argument("--server-meta", default=None, help="서버 실행 기록 JSON(GPU, 인자, adapter sha256)")
    args = parser.parse_args()
    if str(Path(args.gold).resolve().relative_to(ROOT)) in FORBIDDEN:
        raise SystemExit("업체 100·aux_test_v1은 이 작업에서 쓰지 않는다(결정 89)")
    sampling = HE.sampling_settings(args)
    if ROOT in Path(args.raw_out).resolve().parents and "generated" not in Path(args.raw_out).parts:
        raise SystemExit("--raw-out은 저장소 밖이나 ignore 경로(generated)여야 한다")

    from geoflow import providers
    from geoflow.pipeline import GeoFlowPipeline
    from geoflow.planner import GeoFlowPlanner
    import execution_spec

    EV.REFERENCE_DATE = args.reference_date
    prompt_sha = hashlib.sha256(GeoFlowPlanner(client=None).system_prompt().encode("utf-8")).hexdigest()
    client = VLLMThinkingClient(args.base_url, args.served_model)
    gold_path = Path(args.gold).resolve()
    EV.GOLD_PATH = gold_path
    items = [i for i in EV.load_gold(gold_path)["items"] if not args.only or i["id"] in args.only.split(",")]
    Path(args.raw_out).parent.mkdir(parents=True, exist_ok=True)
    rows = []
    started_all = time.perf_counter()
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
            calls = [0]
            original_chat = client.chat

            def chat(messages, tools=None, item_id=item["id"], **kwargs):
                seed = None
                if sampling is not None:
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
            except Exception as error:  # noqa: BLE001
                observed = EV._crashed(error)
            finally:
                client.chat = original_chat
            category, checks = EV.score(item, observed)
            grounding_ok, grounding_diffs = EV.grounding_check(item, observed["grounding"])
            for index, raw in enumerate(raws):
                record = {"id": item["id"], "call": index, **{k: raw[k] for k in (
                    "raw_text", "raw_sha256", "generated_tokens", "done_reason", "think_closed", "finish_reason")}}
                if sampling is not None:
                    record["sampling_seed"] = raw["sampling_seed"]
                raw_stream.write(json.dumps(record, ensure_ascii=False) + "\n")
            rows.append({"id": item["id"], "question": item["question"], "vendor_verdict": item.get("vendor_verdict"),
                         "category": category, "checks": checks, "reset_ok": None,
                         "grounding_ok": grounding_ok, "grounding_diffs": grounding_diffs,
                         "llm_calls": recorder.calls, "hf_calls": client.log,
                         "started_at": item_started.isoformat(),
                         "finished_at": datetime.now(ZoneInfo("Asia/Seoul")).isoformat(), **observed})
            print(f"{item['id']} {category} {observed['outcome']} {observed['error_code'] or ''} "
                  f"{[c['generated_tokens'] for c in client.log]}", flush=True)
    wall = time.perf_counter() - started_all
    request_example = client.last["request"] if client.last else None
    meta = EV._meta("llm", {
        "model": f"vllm:{args.served_model}", "model_digest": None, "ollama_version": None,
        "hf": {"model": H.MODEL, "revision": H.REVISION, "adapter": None,
               "decoding": ({"do_sample": False, "max_new_tokens": H.MAX_NEW_TOKENS} if sampling is None else
                            {"do_sample": True, **sampling["params"], "max_new_tokens": H.MAX_NEW_TOKENS,
                             "round_seed": sampling["round_seed"], "seed_rule": EV.SEED_RULE,
                             "seed_application": "vLLM 요청 seed(호출마다)"}),
               "raw_out": str(Path(args.raw_out).resolve()),
               "raw_out_sha256": hashlib.sha256(Path(args.raw_out).read_bytes()).hexdigest()},
        "vllm": {"base_url": args.base_url, "served_model": args.served_model, "server": server_info(args.base_url),
                 "server_meta": json.loads(Path(args.server_meta).read_text(encoding="utf-8")) if args.server_meta else None,
                 "request_example(no prompt)": request_example, "wall_seconds": round(wall, 1),
                 "input": "HF render_prompt + 같은 tokenizer의 token id열을 /v1/completions prompt로 직접 넘김"},
        "planner_prompt_sha256": prompt_sha, "code_fingerprint": execution_spec.code_fingerprint(ROOT)["sha256"],
        "pipeline": {"aggregation_grounding": "flat", "condition_check": args.condition_check, "condition_notes": False,
                     "normalize_grounding": True, "semantic_reinterpretation": True, "provider": "mock",
                     "tims_execution": "legacy", "client": "vllm", "think": "on(enable_thinking=True)",
                     "isolation": "server_kept_loaded(no conversation state), one request at a time"},
        "item_order": [i["id"] for i in items], "finished_at": datetime.now(ZoneInfo("Asia/Seoul")).isoformat(),
        "scorer_version": EV.SCORER_VERSION})
    result = {"meta": meta, "summary": EV._summary(rows), "rows": rows}
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"items": len(rows), "grounding_ok": sum(bool(r["grounding_ok"]) for r in rows),
                      "truncated_calls": sum(1 for r in rows for c in r["hf_calls"] if c["done_reason"] == "length"),
                      "echo_mismatch_calls": sum(1 for r in rows for c in r["hf_calls"] if c["prompt_ids_echo_equal"] is False),
                      "wall_seconds": round(wall, 1)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
