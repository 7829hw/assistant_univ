# -*- coding: utf-8 -*-
# [pilot_006 준비 W3 이식] 원본: geoflow/partial-grounding 커밋 ab9d215의 sft_dpo_inventory/p0_sft_004/recall.py. 본문은 원본 그대로다(아래 '이식 수정' 줄 제외).
# 원본의 경로 상수(ROOT 등)는 원 위치 기준이라 이 위치에서 바로 돌리려면 경로 인자를 확인한다. 참고값 경로(HF greedy·Ollama, 다른 장비)의 기록용 도구다.
"""학습 문항 smoke(18)·training recall(154) 생성과 판정(지시 46–49·61–64절). HF만, greedy, enable_thinking True, P0 prompt.

    HF_HOME=/data/hwkim/path_repeat_001/hf-cache HF_HUB_OFFLINE=1 /data/hwkim/path_repeat_001/venv/py/bin/python \
        sft_dpo_inventory/p0_sft_004/recall.py --model base|full154|json154 --items smoke|all --out OUT.jsonl

- 입력: reviewed_reasoning_v001의 system·user(=v006, P0 planner messages와 같은지 확인). gold는 주지 않는다.
- 생성: `hf_thinking.load_client(adapter=…)`(BF16·SDPA, max_new_tokens 8192, greedy). 평가(eval_p0_hf)와 같은 client다.
  - thinking 없이 바로 답한 응답(`<think>`·`</think>` 모두 없음)은 eval_p0_hf와 같게 thinking "" + 본문 전체로 나눈다.
- 판정: `collect_p0_traces_hf.judge`(trace 선택에 쓴 5범주). semantic correctness(train recall) = EXACT_OR_SEMANTIC_MATCH.
  - 이 값은 학습 목표 습득 진단이며 일반화 지표가 아니다.
- canonical 6 slot 확인: 최종 JSON의 dimension_target, 장소 od_role, dimension, measure concept text(b006-34: 'H3 셀' 아님).
- smoke 18(결과를 보지 않고 고정): canonical 6 + 출처별 sha256(item_id) 오름차순 앞쪽
  hf8b_r70 4, hf8b_m2 1, hf8b_m3 1, t27b_p12 3, t27b_remaining 3.
"""
import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "evaluation/partial_grounding/sft_p0"))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/thinking_prep_001"))

import hf_thinking as H  # noqa: E402

DATA = ROOT / "sft_dpo_inventory/reviewed_reasoning_v001/dataset.jsonl"
DATA_SHA = "071ccdbee8c74694a189e861bb572975c6198da9c79b7cc93a558f531decea49"
ADAPTERS = {"base": None, "full154": "/data/hwkim/p0_sft_004/checkpoints/full154", "json154": "/data/hwkim/p0_sft_004/checkpoints/json154"}
SMOKE_QUOTA = {"hf8b_r70": 4, "hf8b_m2": 1, "hf8b_m3": 1, "t27b_p12": 3, "t27b_remaining": 3}
_split = H.split_thinking


def split_answer_only(raw):
    if "<think>" not in raw and H.THINK_END not in raw:
        return "", raw.strip(), True
    return _split(raw)


H.split_thinking = split_answer_only


def records():
    data = DATA.read_bytes()
    if hashlib.sha256(data).hexdigest() != DATA_SHA:
        raise SystemExit("dataset sha256 불일치")
    return [json.loads(x) for x in data.decode("utf-8").splitlines() if x.strip()]


def smoke_ids(rows):
    ids = [r["metadata"]["source_record_id"] for r in rows if r["metadata"]["reasoning_source"] == "manual_canonical"]
    for src, n in SMOKE_QUOTA.items():
        pool = sorted((r["metadata"]["source_record_id"] for r in rows if r["metadata"]["reasoning_source"] == src),
                      key=lambda i: hashlib.sha256(i.encode()).hexdigest())
        ids += pool[:n]
    return ids


def slots(payload):
    payload = payload if isinstance(payload, dict) else {}
    f = payload.get("factors") or {}
    concepts = [c for c in payload.get("concepts") or [] if isinstance(c, dict)]
    return {"dimension_target": f.get("dimension_target"), "dimension": f.get("dimension"),
            "od_roles": sorted(str((c.get("attributes") or {}).get("od_role")) for c in concepts if c.get("subtype") in ("place", "scope")),
            "measure_texts": [c.get("text") for c in concepts if c.get("subtype") not in ("place", "scope")]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", choices=list(ADAPTERS), required=True)
    ap.add_argument("--items", choices=("smoke", "all"), required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    import collect_p0_traces_hf as C
    planner, psha = C.p0_planner()
    rows = records()
    if a.items == "smoke":
        keep = smoke_ids(rows)
        rows = sorted((r for r in rows if r["metadata"]["source_record_id"] in keep), key=lambda r: keep.index(r["metadata"]["source_record_id"]))
    if a.out.exists():
        raise SystemExit(f"{a.out}가 이미 있다")
    a.out.parent.mkdir(parents=True, exist_ok=True)
    import torch
    import transformers
    t0 = time.perf_counter()
    client = H.load_client(adapter=ADAPTERS[a.model])
    meta = {"model": a.model, "adapter": ADAPTERS[a.model], "base": f"{H.MODEL}@{H.REVISION}", "items": a.items, "n": len(rows),
            "prompt_sha256": psha, "dataset_sha256": DATA_SHA, "max_new_tokens": H.MAX_NEW_TOKENS, "greedy": True,
            "enable_thinking": client.config["chat_template_kwargs"].get("enable_thinking"),
            "torch": torch.__version__, "transformers": transformers.__version__,
            "device": torch.cuda.get_device_name(0), "dtype": str(next(client.policy.parameters()).dtype),
            "load_seconds": round(time.perf_counter() - t0, 1), "started_at": datetime.now(timezone.utc).isoformat()}
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(json.dumps({"_meta": meta}, ensure_ascii=False) + "\n")
        for r in rows:
            m = r["metadata"]
            msgs = r["messages"][:2]
            if planner.messages(msgs[1]["content"]) != msgs:
                raise SystemExit(f"{m['source_record_id']}: messages가 P0 planner와 다르다")
            s = time.perf_counter()
            res = client.generate(msgs)[0]
            verdict, payload = C.judge(msgs[1]["content"], res["content"], res["think_closed"], m["target_p0"], m["target_full"])
            row = {"item_id": m["source_record_id"], "reasoning_source": m["reasoning_source"], "canonical": m["canonical"],
                   "question": msgs[1]["content"], **{k: res[k] for k in ("raw_text", "thinking", "content", "think_closed",
                                                                           "prompt_tokens", "generated_tokens", "done_reason")},
                   "thinking_emitted": bool(res["think_closed"] and (res["thinking"] or "").strip()),
                   "thinking_chars": len(res["thinking"] or ""), "content_nonempty": bool((res["content"] or "").strip()),
                   "json_parsed": isinstance(payload, dict), "category": verdict["category"], "judge": verdict,
                   "parsed": payload, "slots": slots(payload), "gold_slots": slots(m["target_p0"]),
                   "seconds": round(time.perf_counter() - s, 1)}
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            f.flush()
            print(json.dumps({"id": row["item_id"], "cat": row["category"], "think": row["thinking_emitted"],
                              "gen": row["generated_tokens"], "sec": row["seconds"]}, ensure_ascii=False), flush=True)
    print("RECALL_DONE", a.model, a.items, flush=True)


if __name__ == "__main__":
    main()
