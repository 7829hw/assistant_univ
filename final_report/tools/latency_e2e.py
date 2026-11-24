# -*- coding: utf-8 -*-
"""최종 결과보고서 자체시험: 질의 입력 → 최종 응답 출력 End-to-End 응답시간 측정(새 파일, 기존 평가 코드는 고치지 않고 import만 한다).

    # 초기 환경(HF transformers BF16, 프로세스 안 모델)
    CUDA_VISIBLE_DEVICES=3 HF_HOME=... HF_HUB_OFFLINE=1 python final_report/tools/latency_e2e.py --backend hf --label A_hf_bf16_base ...
    # 최적화 환경(vLLM 서버, 이미 떠 있는 서버에 동시 1 요청)
    python final_report/tools/latency_e2e.py --backend vllm --base-url http://127.0.0.1:8810 --served-model V4_o101 --label E_vllm_fp8_fi_v4 ...

- pipeline·채점·seed 규칙은 기존 하네스(``thinking_prep_001/hf_eval_thinking.py``, ``pilot_005/vllm_eval_thinking5.py``)와 같은 코드
  (``evaluate_vendor100``의 ``GeoFlowPipeline`` 구성, ``EV.run_item``, ``EV.call_seed``)를 쓴다.
- 구분해 재는 것:
  * ``load_seconds``: 모델 적재(HF: 프로세스 안 적재, vLLM: client 준비만. 서버 기동 시간은 실행기 로그에 따로 남김).
  * 워밍업: ``--warmup-ids`` 문항을 같은 경로로 먼저 돌리고 결과는 ``warmup``에만 남긴다(본 측정에 넣지 않음).
  * 문항별 ``e2e_ms``: 질문 문자열을 pipeline에 넣은 순간부터 최종 응답(``final_answer`` 또는 사용자 오류 메시지)이 나올 때까지(perf_counter).
    pipeline 생성·LLM 호출(재질의 포함)·정규화·조건 계층·도구 실행(mock TIMS)·답변 작성까지 포함, 채점은 제외.
  * ``model_ms``: 그 안의 LLM 호출 시간 합(``_RecordingClient`` duration_ms), ``non_model_ms`` = e2e − model.
- 정상 여부: ``system_ok`` = 예외 없음 ∧ 모델 호출 실패 없음 ∧ 생성 상한 잘림 없음 ∧ e2e ≤ ``--timeout-s``(측정 전 고정, 기본 120 s).
  타임아웃은 요청을 끊지 않고 기록만 한다(분류 기준). 정답 여부(category, grounding_ok)는 참고로 남긴다.
"""
import argparse
import hashlib
import json
import os
import platform
import sys
import time
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
for p in (ROOT, ROOT / "sft_dpo_inventory/thinking_prep_001", ROOT / "sft_dpo_inventory/serving_vllm"):
    sys.path.insert(0, str(p))

import evaluate_vendor100 as EV  # noqa: E402
import hf_thinking as H  # noqa: E402

KST = ZoneInfo("Asia/Seoul")


def now():
    return datetime.now(KST).isoformat()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--backend", choices=("hf", "vllm"), required=True)
    ap.add_argument("--label", required=True)
    ap.add_argument("--base-url")
    ap.add_argument("--served-model")
    ap.add_argument("--adapter", default=None)
    ap.add_argument("--gold", default="sft_dpo_inventory/conversion_diag/selection_gold.yaml")
    ap.add_argument("--ids-file", default="sft_dpo_inventory/serving_vllm_fp8/latency_ids.txt")
    ap.add_argument("--warmup-ids", required=True)
    ap.add_argument("--seed", type=int, default=20261101)
    ap.add_argument("--timeout-s", type=float, default=120.0)
    ap.add_argument("--server-meta", default=None)
    ap.add_argument("--out", required=True)
    ap.add_argument("--raw-out", required=True)
    args = ap.parse_args()
    if Path(args.out).exists():
        raise SystemExit(f"output exists: {args.out}")

    from geoflow import providers
    from geoflow.pipeline import GeoFlowPipeline
    from geoflow.planner import GeoFlowPlanner

    EV.REFERENCE_DATE = date(2026, 9, 25)
    gold_path = (ROOT / args.gold).resolve()
    EV.GOLD_PATH = gold_path
    gold = {i["id"]: i for i in EV.load_gold(gold_path)["items"]}
    ids = (ROOT / args.ids_file).read_text(encoding="utf-8").strip().split(",")
    warm = [x for x in args.warmup_ids.split(",") if x]
    assert not set(ids) & set(warm), "warmup ids overlap measured ids"
    prompt_sha = hashlib.sha256(GeoFlowPlanner(client=None).system_prompt().encode("utf-8")).hexdigest()
    params = {"temperature": 0.6, "top_p": 0.95, "top_k": 20, "min_p": 0.0, "repetition_penalty": 1.0}

    started_all = now()
    t = time.perf_counter()
    if args.backend == "hf":
        client = H.load_client(adapter=args.adapter)
    else:
        from vllm_thinking import VLLMThinkingClient
        client = VLLMThinkingClient(args.base_url, args.served_model)
    load_seconds = time.perf_counter() - t

    def run_one(item_id, raw_stream, phase):
        item = gold[item_id]
        client.log = []
        recorder = EV._RecordingClient(client)
        raws, calls = [], [0]
        original_chat = client.chat

        def chat(messages, tools=None, **kw):
            seed = EV.call_seed(args.seed, item_id, calls[0])
            client.sampling_call = {"seed": seed, "params": params}
            calls[0] += 1
            try:
                return original_chat(messages, tools=tools, **kw)
            finally:
                client.sampling_call = None
                if client.last is not None:
                    raws.append({**client.last, "sampling_seed": seed})
        client.chat = chat
        started_at = now()
        t0 = time.perf_counter()
        try:
            pipeline = GeoFlowPipeline.create(
                client=recorder, tool_executor=EV._executor(), aggregation_grounding="flat",
                clock=lambda: EV.REFERENCE_DATE, condition_check=True,
                execution_profile=providers.profile_for(providers.MOCK, providers.LEGACY), condition_notes=False)
            observed = EV.run_item(pipeline, item["question"])
        except Exception as error:  # noqa: BLE001
            observed = EV._crashed(error)
        finally:
            client.chat = original_chat
        e2e_ms = (time.perf_counter() - t0) * 1000
        finished_at = now()
        category, _checks = EV.score(item, observed)
        grounding_ok, _ = EV.grounding_check(item, observed["grounding"])
        model_ms = sum(c.get("duration_ms") or 0 for c in recorder.calls)
        failed_calls = sum(1 for c in recorder.calls if c.get("failed"))
        truncated = sum(1 for r in client.log if r.get("done_reason") == "length")
        gen = [r.get("generated_tokens") for r in client.log]
        for i, r in enumerate(raws):
            raw_stream.write(json.dumps({"phase": phase, "id": item_id, "call": i, "raw_text": r.get("raw_text"),
                                         "raw_sha256": r.get("raw_sha256"), "sampling_seed": r.get("sampling_seed")},
                                        ensure_ascii=False) + "\n")
        crashed = observed.get("error_code") == "UNHANDLED_EXCEPTION"
        timeout = e2e_ms > args.timeout_s * 1000
        row = {"phase": phase, "id": item_id, "question": item["question"], "started_at": started_at, "finished_at": finished_at,
               "e2e_ms": round(e2e_ms, 1), "model_ms": round(model_ms, 1), "non_model_ms": round(e2e_ms - model_ms, 1),
               "llm_calls": len(recorder.calls), "failed_calls": failed_calls, "truncated_calls": truncated,
               "generated_tokens": gen, "prompt_tokens": [r.get("prompt_tokens") or r.get("prompt_eval_count") for r in recorder.calls],
               "outcome": observed["outcome"], "error_code": observed["error_code"], "crashed": crashed, "timeout": timeout,
               "system_ok": (not crashed) and failed_calls == 0 and truncated == 0 and not timeout,
               "final_answer_present": bool(observed.get("final_answer") or observed.get("error_user_message")),
               "category": category, "grounding_ok": grounding_ok,
               "exception": (observed.get("planner_trace") or {}).get("exception") if crashed else None}
        print(f"[{phase}] {item_id} e2e={row['e2e_ms']:.0f}ms model={row['model_ms']:.0f}ms ok={row['system_ok']} "
              f"{observed['outcome']} {observed['error_code'] or ''} gen={gen}", flush=True)
        return row

    Path(args.raw_out).parent.mkdir(parents=True, exist_ok=True)
    warm_rows, rows = [], []
    with open(args.raw_out, "w", encoding="utf-8") as raw_stream:
        tw = time.perf_counter()
        for i in warm:
            warm_rows.append(run_one(i, raw_stream, "warmup"))
        warm_seconds = time.perf_counter() - tw
        tm = time.perf_counter()
        for i in ids:
            rows.append(run_one(i, raw_stream, "measure"))
        measure_seconds = time.perf_counter() - tm

    env = {"python": platform.python_version(), "host": platform.node(), "CUDA_VISIBLE_DEVICES": os.environ.get("CUDA_VISIBLE_DEVICES"),
           "PYTORCH_CUDA_ALLOC_CONF": os.environ.get("PYTORCH_CUDA_ALLOC_CONF")}
    if args.backend == "hf":
        import torch
        import transformers
        p = torch.cuda.get_device_properties(0)
        env.update(torch=torch.__version__, torch_cuda=torch.version.cuda, transformers=transformers.__version__,
                   gpu_name=p.name, gpu_uuid="GPU-" + str(p.uuid), dtype="bfloat16", attention="sdpa")
    meta = {"label": args.label, "backend": args.backend, "base_url": args.base_url, "served_model": args.served_model,
            "adapter": args.adapter, "gold": args.gold, "gold_sha256": hashlib.sha256(gold_path.read_bytes()).hexdigest(),
            "ids_file": args.ids_file, "warmup_ids": warm, "round_seed": args.seed, "sampling": params,
            "max_new_tokens": H.MAX_NEW_TOKENS, "timeout_s": args.timeout_s, "planner_prompt_sha256": prompt_sha,
            "pipeline": {"aggregation_grounding": "flat", "condition_check": True, "provider": "mock", "tims_execution": "legacy",
                         "think": "on(enable_thinking=True)", "concurrency": 1},
            "server_meta": json.loads(Path(args.server_meta).read_text()) if args.server_meta else None,
            "env": env, "started_at": started_all, "finished_at": now(), "argv": sys.argv,
            "load_seconds": round(load_seconds, 3), "warmup_seconds": round(warm_seconds, 3), "measure_seconds": round(measure_seconds, 3)}
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps({"meta": meta, "warmup": warm_rows, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    e = [r["e2e_ms"] for r in rows]
    print(json.dumps({"label": args.label, "items": len(rows), "e2e_mean_ms": round(sum(e) / len(e), 1),
                      "system_ok": sum(r["system_ok"] for r in rows)}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
