# -*- coding: utf-8 -*-
"""batch007 후보에 대한 base 모델의 첫 응답 수집(vLLM BF16, thinking 켬, 결정 104). 학습 없음. 출력은 검토 전 후보일 뿐 어떤 corpus에도 넣지 않는다.

    hfvenv/bin/python sft_dpo_inventory/batch007/vllm_collect.py --port 8700 --concurrency 8

batch006(``../batch006/hf_collect.py``)와 같은 방법이고 생성 경로만 vLLM이다.
- 서버: ``serve_b7.sh``(vLLM 0.30.0, BF16, flashinfer attention·sampler, PROTOCOL_v5와 같은 서버 인자). base(adapter 없음) 요청만 보낸다.
- 입력: 현재 planner messages(prompt 87048d0c)를 HF ``render_prompt``(enable_thinking) id열로 ``/v1/completions``에 직접 넘긴다(``serving_vllm/vllm_thinking.py``).
- 생성: **greedy**(temperature 0, batch006과 같음), max_tokens 8192. 첫 계획 응답 하나만(재질의·pipeline 실행 없음). 동시 요청 최대 C개.
  vLLM은 바이트 재현을 보장하지 않는다(결정 93) — 원문은 ignore 경로 ``training/generated/batch007/raw/vllm_outputs_raw.jsonl``에만 둔다.
- 비교: ``thinking_prep_001/collect_traces.judge``(조건 계층 전 원응답과 초안, 참고로 조건 계층 뒤 일치). 다르면 DPO rejected 후보로 두고
  "초안과 모델 중 어느 쪽이 맞는가"를 검토 항목으로 표시한다.
- 출력(커밋): ``vllm_outputs.json``(원문 sha256, 길이·종료 이유, 파싱한 JSON, 채점). 형식은 batch006 ``hf_outputs.json``과 같다.
"""
import argparse
import hashlib
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RAW = ROOT / "training/generated/batch007/raw/vllm_outputs_raw.jsonl"
SERVER_META = Path("/data/hwkim/sftdpo_work/batch007/vllm")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/thinking_prep_001"))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/serving_vllm"))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--port", type=int, required=True)
    p.add_argument("--concurrency", type=int, default=8)
    args = p.parse_args()
    import collect_traces as T
    import execution_spec
    from geoflow.planner import GeoFlowPlanner
    from training.data.common import check_expected_prompt
    from training.data.validation import assess, assess_t2pc
    from vllm_thinking import VLLMThinkingClient

    prompt_hash = check_expected_prompt()
    checked = json.loads((HERE / "candidates_checked.json").read_text(encoding="utf-8"))
    planner = GeoFlowPlanner(client=None)
    RAW.parent.mkdir(parents=True, exist_ok=True)
    if RAW.exists():
        raise SystemExit(f"{RAW} already exists (다시 재지 않는다)")
    server = json.loads((SERVER_META / f"server_{args.port}.json").read_text(encoding="utf-8"))
    clients = [VLLMThinkingClient(f"http://127.0.0.1:{args.port}", "base") for _ in range(args.concurrency)]
    started_at = datetime.now(ZoneInfo("Asia/Seoul")).isoformat()

    def run(job):
        i, item = job
        client = clients[i % args.concurrency]
        t0 = time.perf_counter()
        return item, client.generate(planner.messages(item["question"])), time.perf_counter() - t0

    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        # 작업자 C개가 각자 client 하나만 쓰도록 문항을 i % C로 나눈다(같은 client를 두 스레드가 동시에 쓰지 않음).
        shards = [[(i, it) for i, it in enumerate(checked["candidates"]) if i % args.concurrency == w] for w in range(args.concurrency)]
        results = [r for fut in [ex.submit(lambda s: [run(j) for j in s], sh) for sh in shards] for r in fut.result()]
    wall = time.perf_counter() - t0
    order = {c["id"]: n for n, c in enumerate(checked["candidates"])}
    results.sort(key=lambda r: order[r[0]["id"]])
    rows = []
    with RAW.open("w", encoding="utf-8") as raw_out:
        for item, result, seconds in results:
            raw_out.write(json.dumps({"id": item["id"], "raw_text": result["raw_text"], "raw_sha256": result["raw_sha256"]},
                                     ensure_ascii=False) + "\n")
            verdict, payload = T.judge(result["content"], item["question"], item["draft_grounding"])
            model_quality = None
            if payload is not None and verdict["parse"] == "ok":
                model_quality = {"thor_normalize_false": assess(payload, item["question"], normalize=False),
                                 "t2pc": {k: v for k, v in assess_t2pc(payload, item["question"]).items() if k != "signature"}}
            same = verdict["raw_match"]
            rows.append({"id": item["id"], "variant": item["variant"],
                         "question_sha256": hashlib.sha256(item["question"].encode("utf-8")).hexdigest(),
                         "raw_sha256": result["raw_sha256"],
                         "generated_tokens": result["generated_tokens"], "done_reason": result["done_reason"],
                         "think_closed": result["think_closed"], "thinking_chars": len(result["thinking"]),
                         "prompt_ids_echo_equal": result["prompt_ids_echo_equal"],
                         "seconds": round(seconds, 2), "parse_state": verdict["parse"], "parsed": payload,
                         "matches_draft": bool(same), "grounding_diffs": verdict["raw_diffs"],
                         "matches_draft_after_condition_layer": verdict["after_condition_match"],
                         "error_tags": [] if same else verdict["error_tags"], "model_quality": model_quality,
                         "review_needed": None if same else "초안과 모델 출력 중 어느 쪽이 맞는지 사람이 판단한다"})
            print(item["id"], "match" if same else f"diff {verdict['error_tags']}", result["generated_tokens"], result["done_reason"], flush=True)
    runtime = {"engine": "vllm", "vllm": server.get("vllm"), "flashinfer": server.get("flashinfer"), "torch": server.get("torch"),
               "model": "Qwen/Qwen3-8B@b968826d9c46dd6066d109eabc6255188de91218", "adapter": None, "precision": server.get("precision"),
               "kernels": {"attention_backend(server log)": server.get("log_attention_backend"),
                           "sampler(server log)": server.get("log_flashinfer_sampler_lines")},
               "device_uuid": server.get("gpu_uuid"), "server_args": server.get("args"),
               "decoding": {"greedy": True, "temperature": 0.0, "max_tokens": 8192, "seed": None, "seed_reproducible": False},
               "enable_thinking": True, "concurrency": args.concurrency, "wall_seconds": round(wall, 1),
               "prompt_sha256": prompt_hash, "code_fingerprint": execution_spec.code_fingerprint(ROOT)["sha256"],
               "judge": "thinking_prep_001/collect_traces.judge (raw output before condition layer)",
               "raw_out": str(RAW.relative_to(ROOT)), "raw_out_sha256": hashlib.sha256(RAW.read_bytes()).hexdigest(),
               "started_at": started_at, "finished_at": datetime.now(ZoneInfo("Asia/Seoul")).isoformat()}
    out = {"runtime": runtime, "items": len(rows), "matches": sum(r["matches_draft"] for r in rows),
           "truncated": sum(r["done_reason"] == "length" for r in rows), "rows": rows}
    (HERE / "vllm_outputs.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k != "rows"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
