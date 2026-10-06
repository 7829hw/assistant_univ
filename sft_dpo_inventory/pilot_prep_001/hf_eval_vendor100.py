# -*- coding: utf-8 -*-
"""업체 100을 HF 모델(base 또는 base + LoRA adapter)로 평가한다. 모델 호출만 HF로 바꾸고 나머지는 Ollama 셀과 같은 코드다.

    CUDA_VISIBLE_DEVICES=2 HF_HOME=... HF_HUB_OFFLINE=1 python sft_dpo_inventory/pilot_prep_001/hf_eval_vendor100.py \
        --condition-check --out RESULT.json [--adapter ADAPTER_DIR]

- 같은 코드: ``evaluate_vendor100``의 pipeline 구성(``GeoFlowPipeline.create``, 조건 계층, 재질의 정책, mock·legacy 실행,
  기준일 고정)과 ``run_item``·``score``·``grounding_check``·``_RecordingClient``·``_crashed``를 그대로 import해 쓴다.
  결과 파일 형식도 ``evaluate_vendor100.py llm``과 같아서 ``axes_rows``·비교 스크립트가 그대로 읽는다.
- 모델 호출: thor ``training.inference.HFClient``(BF16, transformers 기본 SDPA, chat template ``enable_thinking=False``,
  greedy, max_new_tokens 1024, seed 42). 응답에 prompt·생성 token 수와 ``done_reason``(생성 상한이면 length)을 붙여
  planner의 잘림 처리(OUTPUT_TRUNCATED 재시도)가 Ollama 경로와 같게 동작하게 한다.
- ``--adapter``를 주면 같은 방식으로 base + adapter를 평가한다. adapter의 training_provenance prompt hash가 현재 prompt와
  다르면 HFClient가 멈춘다.
- 업체 100은 평가 전용이다. 이 결과를 학습, checkpoint 선택, annotation 후보에 쓰지 않는다.
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

import evaluate_vendor100 as EV  # noqa: E402

MODEL = "Qwen/Qwen3-8B"
REVISION = "b968826d9c46dd6066d109eabc6255188de91218"


def counted_client(base_cls):
    class Counted(base_cls):
        """HFClient 응답에 token 수와 done_reason을 붙인다(생성 자체는 HFClient 그대로)."""

        def chat(self, messages, tools=None, **kwargs):
            import torch
            from training.trainer_common import render_prompt
            text = render_prompt(self.tokenizer, messages, self.config)
            inputs = self.tokenizer(text, return_tensors="pt", add_special_tokens=False).to(self.policy.device)
            with torch.inference_mode():
                outputs = self.policy.generate(**inputs, max_new_tokens=self.max_new_tokens, do_sample=False,
                                               use_cache=True, pad_token_id=self.tokenizer.pad_token_id)
            generated = outputs[0][inputs.input_ids.shape[1]:]
            content = self.tokenizer.decode(generated, skip_special_tokens=True)
            ended = bool(len(generated)) and int(generated[-1]) in {self.tokenizer.eos_token_id,
                                                                     self.tokenizer.convert_tokens_to_ids("<|im_end|>")}
            return {"message": {"content": content}, "prompt_eval_count": int(inputs.input_ids.shape[1]),
                    "eval_count": int(len(generated)),
                    "done_reason": "stop" if ended or len(generated) < self.max_new_tokens else "length"}
    return Counted


def adapter_identity(adapter):
    if not adapter:
        return None
    path = Path(adapter)
    return {name: hashlib.sha256((path / name).read_bytes()).hexdigest()
            for name in ("adapter_config.json", "adapter_model.safetensors") if (path / name).exists()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    parser.add_argument("--adapter", default=None)
    parser.add_argument("--revision", default=REVISION)
    parser.add_argument("--condition-check", action="store_true")
    parser.add_argument("--reference-date", type=date.fromisoformat, default=date(2026, 9, 25))
    parser.add_argument("--max-new-tokens", type=int, default=1024)
    parser.add_argument("--only", default="")
    args = parser.parse_args()

    import torch
    from build import build  # noqa: F401 - evaluate_vendor100._executor가 쓴다
    from geoflow import providers
    from geoflow.pipeline import GeoFlowPipeline
    from geoflow.planner import GeoFlowPlanner
    from training.inference import HFClient
    import execution_spec

    EV.REFERENCE_DATE = args.reference_date
    prompt_sha = hashlib.sha256(GeoFlowPlanner(client=None).system_prompt().encode("utf-8")).hexdigest()
    started = time.perf_counter()
    client = counted_client(HFClient)(MODEL, adapter=args.adapter, revision=args.revision,
                                      max_new_tokens=args.max_new_tokens, seed=42)
    load_seconds = time.perf_counter() - started
    device = torch.cuda.get_device_properties(0)
    document = EV.load_gold(None)
    items = [i for i in document["items"] if not args.only or i["id"] in args.only.split(",")]
    rows = []
    for item in items:
        item_started = datetime.now(ZoneInfo("Asia/Seoul"))
        recorder = EV._RecordingClient(client)
        options = {"condition_notes": False} if args.condition_check else {}
        pipeline = GeoFlowPipeline.create(
            client=recorder, tool_executor=EV._executor(), aggregation_grounding="flat",
            clock=lambda: EV.REFERENCE_DATE, condition_check=args.condition_check,
            execution_profile=providers.profile_for(providers.MOCK, providers.LEGACY), **options)
        try:
            observed = EV.run_item(pipeline, item["question"])
        except Exception as error:  # noqa: BLE001 - evaluate_vendor100 llm과 같은 처리
            observed = EV._crashed(error)
        category, checks = EV.score(item, observed)
        grounding_ok, grounding_diffs = EV.grounding_check(item, observed["grounding"])
        rows.append({"id": item["id"], "question": item["question"], "vendor_verdict": item["vendor_verdict"],
                     "category": category, "checks": checks, "reset_ok": None,
                     "grounding_ok": grounding_ok, "grounding_diffs": grounding_diffs,
                     "llm_calls": recorder.calls, "started_at": item_started.isoformat(),
                     "finished_at": datetime.now(ZoneInfo("Asia/Seoul")).isoformat(), **observed})
        print(f"{item['id']} {category} {observed['outcome']} {observed['error_code'] or ''}", flush=True)
    meta = EV._meta("llm", {
        "model": f"hf:{MODEL}@{args.revision}" + (f"+{args.adapter}" if args.adapter else ""),
        "model_digest": None, "ollama_version": None,
        "hf": {"model": MODEL, "revision": args.revision, "adapter": args.adapter,
               "adapter_sha256": adapter_identity(args.adapter), "dtype": str(next(client.policy.parameters()).dtype),
               "attention": client.policy.config._attn_implementation,
               "chat_template_kwargs": client.config["chat_template_kwargs"],
               "decoding": {"do_sample": False, "max_new_tokens": args.max_new_tokens, "seed": 42},
               "torch": torch.__version__, "cuda": torch.version.cuda, "device": device.name,
               "device_uuid": f"GPU-{device.uuid}", "load_seconds": round(load_seconds, 1),
               "peak_allocated_bytes": torch.cuda.max_memory_allocated()},
        "planner_prompt_sha256": prompt_sha,
        "code_fingerprint": execution_spec.code_fingerprint(ROOT)["sha256"],
        "pipeline": {"aggregation_grounding": "flat", "condition_check": args.condition_check,
                     "condition_notes": False, "normalize_grounding": True, "semantic_reinterpretation": True,
                     "provider": "mock", "tims_execution": "legacy", "client": "hf", "think": "off(enable_thinking=False)",
                     "isolation": "process_local_model_kept_loaded(no conversation state)"},
        "reference_date_override": args.reference_date.isoformat(),
        "item_order": [i["id"] for i in items], "finished_at": datetime.now(ZoneInfo("Asia/Seoul")).isoformat(),
        "scorer_version": EV.SCORER_VERSION})
    result = {"meta": meta, "summary": EV._summary(rows), "rows": rows}
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"items": len(rows), "grounding_ok": sum(bool(r["grounding_ok"]) for r in rows),
                      "categories": result["summary"]["categories"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
