# -*- coding: utf-8 -*-
"""batch006 후보에 대한 base 모델의 첫 응답 수집(HF, thinking 켬). 학습 없음. 출력은 검토 전 후보일 뿐 어떤 corpus에도 넣지 않는다.

    CUDA_VISIBLE_DEVICES=<GPU> HF_HOME=... HF_HUB_OFFLINE=1 python sft_dpo_inventory/batch006/hf_collect.py

batch005(``../batch005/hf_collect.py``)와 같다. 다른 점:
- 응답 원문(thinking 포함)은 ignore 경로 ``training/generated/batch006/raw/hf_outputs_raw.jsonl``에만 쓴다(이번 작업 지시: 응답 원문은
  커밋하지 않는다). 커밋하는 ``hf_outputs.json``에는 원문의 sha256, 길이·종료 이유, 파싱한 JSON(rejected 후보 grounding), 채점만 둔다.
- 모델·생성: Qwen/Qwen3-8B@b968826d(base, adapter 없음), ``thinking_prep_001/hf_thinking``(BF16, SDPA, ``enable_thinking=True``),
  greedy, max_new_tokens 8192, prompt 87048d0c. 첫 계획 응답 하나만 만든다(재질의·pipeline 실행 없음).
- 비교: ``thinking_prep_001/collect_traces.judge``(조건 계층 전 원응답과 초안, 참고로 조건 계층 뒤 일치). 다르면 DPO rejected 후보로 두고
  "초안과 모델 중 어느 쪽이 맞는가"를 검토 항목으로 표시한다. 조건 계층 뒤 같아지는 차이(결정 6: 운영 경로에서 뜻이 같아짐)는 따로 표시한다.
"""
import hashlib
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RAW = ROOT / "training/generated/batch006/raw/hf_outputs_raw.jsonl"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/thinking_prep_001"))


def main():
    import torch
    import collect_traces as T
    import execution_spec
    import hf_thinking as H
    from geoflow.planner import GeoFlowPlanner
    from training.data.common import check_expected_prompt
    from training.data.validation import assess, assess_t2pc

    prompt_hash = check_expected_prompt()
    checked = json.loads((HERE / "candidates_checked.json").read_text(encoding="utf-8"))
    planner = GeoFlowPlanner(client=None)
    started = time.perf_counter()
    client = H.load_client()
    load_s = time.perf_counter() - started
    device = torch.cuda.get_device_properties(0)
    runtime = {"model": H.MODEL, "revision": H.REVISION, "adapter": None, "torch": torch.__version__,
               "device": device.name, "device_uuid": f"GPU-{device.uuid}",
               "dtype": str(next(client.policy.parameters()).dtype),
               "attention": client.policy.config._attn_implementation,
               "chat_template_kwargs": client.config["chat_template_kwargs"],
               "decoding": {"do_sample": False, "max_new_tokens": H.MAX_NEW_TOKENS, "seed": 42},
               "load_seconds": round(load_s, 1), "prompt_sha256": prompt_hash,
               "code_fingerprint": execution_spec.code_fingerprint(ROOT)["sha256"],
               "judge": "thinking_prep_001/collect_traces.judge (raw output before condition layer)",
               "raw_out": str(RAW.relative_to(ROOT))}
    RAW.parent.mkdir(parents=True, exist_ok=True)
    if RAW.exists():
        raise SystemExit(f"{RAW} already exists (다시 재지 않는다)")
    rows = []
    with RAW.open("w", encoding="utf-8") as raw_out:
        for item in checked["candidates"]:
            messages = planner.messages(item["question"])
            t0 = time.perf_counter()
            result = client.generate(messages)[0]
            seconds = time.perf_counter() - t0
            raw_out.write(json.dumps({"id": item["id"], "raw_text": result["raw_text"], "raw_sha256": result["raw_sha256"]},
                                     ensure_ascii=False) + "\n")
            raw_out.flush()
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
                         "seconds": round(seconds, 2), "parse_state": verdict["parse"], "parsed": payload,
                         "matches_draft": bool(same), "grounding_diffs": verdict["raw_diffs"],
                         "matches_draft_after_condition_layer": verdict["after_condition_match"],
                         "error_tags": [] if same else verdict["error_tags"], "model_quality": model_quality,
                         "review_needed": None if same else "초안과 모델 출력 중 어느 쪽이 맞는지 사람이 판단한다"})
            print(item["id"], "match" if same else f"diff {verdict['error_tags']}", result["generated_tokens"],
                  result["done_reason"], round(seconds, 1), flush=True)
    runtime.update(peak_allocated_bytes=torch.cuda.max_memory_allocated(),
                   raw_out_sha256=hashlib.sha256(RAW.read_bytes()).hexdigest(),
                   finished_at=datetime.now(ZoneInfo("Asia/Seoul")).isoformat())
    out = {"runtime": runtime, "items": len(rows), "matches": sum(r["matches_draft"] for r in rows),
           "truncated": sum(r["done_reason"] == "length" for r in rows), "rows": rows}
    (HERE / "hf_outputs.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k != "rows"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
