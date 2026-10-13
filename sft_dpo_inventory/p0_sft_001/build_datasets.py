# -*- coding: utf-8 -*-
"""p0_sft_001 학습 데이터 두 arm을 만든다(결정 68). 모델 호출 없음.

    /data/hwkim/path_repeat_001/venv/py/bin/python sft_dpo_inventory/p0_sft_001/build_datasets.py

- 입력:
  - `reviewed_gold_v006_p0`(154): metadata.target_full이 Full canonical gold다.
  - `selected_traces.jsonl`(문항당 1개, select_traces.py)
  - `trace_review.json`(APPROVE_TRACE / REJECT_TRACE)
- P0 target은 Full gold에서 `build_targets.convert`로 다시 만들고, v006에 저장된 assistant와 같은지 확인한다.
- Gold-only(`gold_only/`): 154문항 모두 [P0 system, 질문] → canonical P0 JSON(답만, thinking 없음).
  - thinking 없는 답은 기존 형식 그대로다(render_records가 `<|im_start|>assistant\\n` 뒤에 JSON + EOS를 둔다).
  - 가짜 `<think>` 블록을 만들지 않는다.
- Clean-Hybrid(`clean_hybrid/`): 154문항 모두 한 번씩.
  - 승인 trace가 있는 문항: `<think>\\n{모델 thinking 원문}\\n</think>\\n\\n{canonical P0 JSON}`(metadata.format = thinking)
    - 최종 답은 Gold-only와 같은 canonical P0 JSON이다(지시 12절: reasoning 유무가 final target을 바꾸지 않음).
    - thinking 부분은 HF 원문(raw_text)의 `</think>` 앞과 바이트 단위로 같아야 한다.
  - 나머지는 Gold-only와 같은 레코드다. 거부 문항은 다른 표본으로 바꾸지 않는다.
- 문항별 가중치 없음(각 1회). 두 arm의 item ID 집합이 같아야 한다.
- 출력: 각 디렉터리에 `sft_train.jsonl`, 빈 `sft_valid.jsonl`, trainer manifest(`manifest.json`), 그리고 `dataset_manifest.json`.
  - valid는 비운다(고정 checkpoint, 결정 68).
"""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "evaluation/partial_grounding/sft_p0"))

import build_targets as BT  # noqa: E402
from training.trainer_common import p0_system_prompt  # noqa: E402

V006 = ROOT / "training/generated/reviewed_gold_v006_p0/sft_train.jsonl"
P0_PROMPT = "evaluation/partial_grounding/prompts/partial_p0.yaml"
TRACES = ROOT / "training/generated/thinking_traces/p0_v006_hf/traces.jsonl"
OUT = ROOT / "training/generated/p0_sft_001"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x.strip()]


def write(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def main():
    system = p0_system_prompt(ROOT / P0_PROMPT)
    psha = hashlib.sha256(system.encode("utf-8")).hexdigest()
    if not psha.startswith("d7f4c12a"):
        raise SystemExit(f"P0 prompt hash {psha[:8]}")
    v006 = read(V006)
    review = {x["trace_id"]: x for x in json.loads((HERE / "trace_review.json").read_text(encoding="utf-8"))["items"]}
    selected = {r["item_id"]: r for r in read(HERE / "selected_traces.jsonl")}
    raw = {r["trace_id"]: r["raw_text"] for r in read(TRACES) if r["trace_id"] in review}
    gold_rows, hybrid_rows, stats = [], [], {"reasoning": 0, "gold_fallback_rejected": 0, "gold_no_trace": 0}
    for r in v006:
        m = r["metadata"]
        q = r["messages"][1]["content"]
        if r["messages"][0]["content"] != system:
            raise SystemExit(f"{m['source_record_id']}: system prompt가 P0와 다르다")
        p0, conv = BT.convert(q, m["target_full"])
        if not conv["auto_pass"] or p0 != json.loads(r["messages"][2]["content"]):
            raise SystemExit(f"{m['source_record_id']}: Full → P0 변환이 v006과 다르다 {conv['problems']}")
        answer = json.dumps(p0, ensure_ascii=False)
        meta = {"source_record_id": m["source_record_id"], "parent_intent": m["source_record_id"], "source": m["source"],
                "dataset_version": "reviewed_gold_v006_p0", "contract": "P0", "prompt_sha256": psha, "target_p0": p0,
                "target_full": m["target_full"]}
        base = {"messages": [{"role": "system", "content": system}, {"role": "user", "content": q},
                             {"role": "assistant", "content": answer}]}
        gold_rows.append({**base, "metadata": {**meta, "arm": "gold_only", "example": "answer_only"}})
        sel = selected.get(m["source_record_id"])
        verdict = review.get(sel["trace_id"]) if sel else None
        if verdict and verdict["decision"] == "APPROVE_TRACE":
            prefix = "<think>\n" + sel["thinking"] + "\n</think>\n\n"
            if not raw[sel["trace_id"]].startswith(prefix):
                raise SystemExit(f"{sel['trace_id']}: thinking 부분이 원문과 다르다")
            hybrid_rows.append({"messages": [base["messages"][0], base["messages"][1],
                                             {"role": "assistant", "content": prefix + answer}],
                                "metadata": {**meta, "arm": "clean_hybrid", "example": "reasoning", "format": "thinking",
                                             "trace_id": sel["trace_id"], "trace_raw_sha256": sel["raw_sha256"],
                                             "trace_model": "Qwen/Qwen3-8B@b968826d9c46dd6066d109eabc6255188de91218"}})
            stats["reasoning"] += 1
        else:
            stats["gold_fallback_rejected" if verdict else "gold_no_trace"] += 1
            hybrid_rows.append({**base, "metadata": {**meta, "arm": "clean_hybrid", "example": "answer_only",
                                                     "fallback": "trace_rejected" if verdict else "no_clean_trace"}})
    ids_g = [x["metadata"]["source_record_id"] for x in gold_rows]
    ids_h = [x["metadata"]["source_record_id"] for x in hybrid_rows]
    if set(ids_g) != set(ids_h) or len(ids_g) != len(set(ids_g)) or len(ids_g) != 154:
        raise SystemExit("두 arm의 item ID 집합이 다르거나 중복·누락이 있다")
    for g, h in zip(gold_rows, hybrid_rows):
        if not h["messages"][2]["content"].endswith(g["messages"][2]["content"]):
            raise SystemExit(f"{g['metadata']['source_record_id']}: 두 arm의 최종 답이 다르다")
    manifest_all = {}
    for arm, rows in (("gold_only", gold_rows), ("clean_hybrid", hybrid_rows)):
        d = OUT / arm
        write(d / "sft_train.jsonl", rows)
        write(d / "sft_valid.jsonl", [])
        trainer_manifest = {"sft": {"prompt_hash": psha, "representation": "flat", "contract": "P0",
                                    "format": "mixed" if arm == "clean_hybrid" else "answer_only", "issues": [],
                                    "output_hashes": {"sft_train.jsonl": sha(d / "sft_train.jsonl"),
                                                      "sft_valid.jsonl": sha(d / "sft_valid.jsonl")}}}
        (d / "manifest.json").write_text(json.dumps(trainer_manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        manifest_all[arm] = {"records": len(rows), "sft_train_sha256": sha(d / "sft_train.jsonl"),
                             "manifest_sha256": sha(d / "manifest.json"),
                             "examples": {k: sum(x["metadata"]["example"] == k for x in rows) for k in ("reasoning", "answer_only")},
                             "by_source": {s: sum(x["metadata"]["source"] == s for x in rows)
                                           for s in ("v005", "augment_dt_event", "augment_od_vs_dt")}}
    doc = {"version": "p0_sft_001", "dataset_base": "reviewed_gold_v006_p0", "v006_sha256": sha(V006), "prompt_sha256": psha,
           "item_ids_identical": True, "items": 154, "hybrid": stats,
           "selected_traces_sha256": sha(HERE / "selected_traces.jsonl"), "trace_review_sha256": sha(HERE / "trace_review.json"),
           "legacy_conservative_family_overlap": 16, "arms": manifest_all}
    (HERE / "dataset_manifest.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(doc, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
