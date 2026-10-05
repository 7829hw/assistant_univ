# -*- coding: utf-8 -*-
"""batch004 후보에 대한 base 모델의 첫 응답 수집(GPU 2, HF). 학습 없음. 출력은 검토 전 후보일 뿐 어떤 corpus에도 넣지 않는다.

    CUDA_VISIBLE_DEVICES=2 HF_HOME=... HF_HUB_OFFLINE=1 python sft_dpo_inventory/batch004/hf_collect.py

- 모델: Qwen/Qwen3-8B@b968826d(base, adapter 없음). thor ``training.inference.HFClient``: BF16, SDPA(transformers 기본),
  greedy(do_sample=False), max_new_tokens 1024, seed 42, chat template ``enable_thinking=False``.
- 입력: 현재 planner의 ``messages(question)``(system prompt 87048d0c). 첫 응답 원문만 저장한다(재질의 없음).
- 비교: 초안 gold와 ``evaluate_vendor100.grounding_check``(최종 grounding 비교와 같은 함수). 다르면 DPO rejected 후보로 두고
  ``grounding_diffs``와 오류 유형 태그를 붙인다. 초안이 틀리고 모델이 맞을 수도 있으므로 검토 항목으로 둔다.
"""
import hashlib
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

MODEL = "Qwen/Qwen3-8B"
REVISION = "b968826d9c46dd6066d109eabc6255188de91218"


def tags_for(diffs, parse_state):
    if parse_state != "ok":
        return [parse_state]
    out = []
    for diff in diffs:
        key = diff if isinstance(diff, str) else diff[0]
        out.append({"measure": "measure_confusion", "places": "place_or_od_role", "scopes": "scope",
                    "no_grounding": "no_grounding"}.get(key, key.replace("factor:", "factor_")))
    return sorted(set(out))


def main():
    import torch
    import evaluate_vendor100 as EV
    from geoflow.planner import GeoFlowPlanner, parse_planner_json
    from training.data.common import check_expected_prompt
    from training.data.validation import assess, assess_t2pc
    from training.inference import HFClient

    prompt_hash = check_expected_prompt()
    checked = json.loads((HERE / "candidates_checked.json").read_text(encoding="utf-8"))
    planner = GeoFlowPlanner(client=None)
    started = time.perf_counter()
    client = HFClient(MODEL, revision=REVISION, max_new_tokens=1024, seed=42)
    load_s = time.perf_counter() - started
    device = torch.cuda.get_device_properties(0) if torch.cuda.is_available() else None
    runtime = {"model": MODEL, "revision": REVISION, "adapter": None, "torch": torch.__version__,
               "cuda": torch.version.cuda, "device": device.name if device else None,
               "device_uuid": f"GPU-{device.uuid}" if device else None,
               "dtype": str(next(client.policy.parameters()).dtype),
               "attention": client.policy.config._attn_implementation,
               "chat_template_kwargs": client.config["chat_template_kwargs"],
               "decoding": {"do_sample": False, "max_new_tokens": 1024, "seed": 42}, "load_seconds": round(load_s, 1),
               "prompt_sha256": prompt_hash}
    rows = []
    for item in checked["candidates"]:
        messages = planner.messages(item["question"])
        t0 = time.perf_counter()
        response = client.chat(messages)
        seconds = time.perf_counter() - t0
        raw = response["message"]["content"]
        try:
            payload = parse_planner_json(raw)
            parse_state = "unsupported" if payload.get("unsupported") else "ok"
        except Exception:  # noqa: BLE001 - JSON이 아닌 출력
            payload, parse_state = None, "not_json"
        gold_item = {"gold_grounding": item["draft_grounding"], "gold": None}
        if parse_state == "ok":
            same, diffs = EV.grounding_check(gold_item, payload)
        else:
            same, diffs = False, [parse_state]
        model_quality = None
        if payload is not None and parse_state == "ok":
            model_quality = {"thor_normalize_false": assess(payload, item["question"], normalize=False),
                             "t2pc": {k: v for k, v in assess_t2pc(payload, item["question"]).items() if k != "signature"}}
        rows.append({"id": item["id"], "type": item["type"], "question_sha256": hashlib.sha256(
                         item["question"].encode("utf-8")).hexdigest(),
                     "raw_text": raw, "seconds": round(seconds, 2), "parse_state": parse_state,
                     "matches_draft": bool(same), "grounding_diffs": diffs,
                     "error_tags": [] if same else tags_for(diffs, parse_state),
                     "model_quality": model_quality,
                     "review_needed": None if same else "초안과 모델 출력 중 어느 쪽이 맞는지 사람이 판단한다"})
        print(item["id"], "match" if same else f"diff {tags_for(diffs, parse_state)}", round(seconds, 1), flush=True)
    runtime.update(peak_allocated_bytes=torch.cuda.max_memory_allocated() if torch.cuda.is_available() else None)
    out = {"runtime": runtime, "items": len(rows), "matches": sum(r["matches_draft"] for r in rows), "rows": rows}
    (HERE / "hf_outputs.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k != "rows"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
