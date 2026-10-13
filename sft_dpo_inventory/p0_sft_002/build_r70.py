# -*- coding: utf-8 -*-
"""R70 데이터(PLAN.md 2절). 모델 호출 없음.

    python sft_dpo_inventory/p0_sft_002/build_r70.py   # -> training/generated/p0_sft_002/r70/, r70_dataset_manifest.json

- 입력: p0_sft_001 Clean-Hybrid 학습 데이터에서 `metadata.example == "reasoning"`인 레코드(trace_review 승인 70)를 원래 순서대로 쓴다.
  - 새 trace를 만들지 않는다.
  - STRUCTURALLY_REPAIRABLE·답만 있는 84문항은 쓰지 않는다.
- 레코드는 바꾸지 않는다. system·user·assistant(`<think>\\n{승인 thinking}\\n</think>\\n\\n{canonical P0 JSON}`)·metadata를 그대로 둔다.
- 두 arm(R70-json, R70-full)은 이 한 파일을 같이 쓴다. 다른 것은 config의 `thinking.loss_scope`뿐이다.
- 확인:
  - 70 item ID가 trace_review 승인 목록과 같다.
  - 최종 답 = metadata.target_p0
  - thinking = selected_traces의 thinking 원문
"""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SRC = ROOT / "training/generated/p0_sft_001/clean_hybrid/sft_train.jsonl"
OUT = ROOT / "training/generated/p0_sft_002/r70"


def sha(b):
    return hashlib.sha256(b).hexdigest()


def main():
    import sys
    sys.path.insert(0, str(ROOT))
    from training.data import thinking
    rows = [json.loads(x) for x in SRC.read_text(encoding="utf-8").splitlines() if x.strip()]
    r70 = [r for r in rows if r["metadata"].get("example") == "reasoning"]
    review = json.loads((ROOT / "sft_dpo_inventory/p0_sft_001/trace_review.json").read_text(encoding="utf-8"))
    approved = {x["item_id"]: x["trace_id"] for x in review["items"] if x["decision"] == "APPROVE_TRACE"}
    selected = {json.loads(x)["trace_id"]: json.loads(x) for x in
                (ROOT / "sft_dpo_inventory/p0_sft_001/selected_traces.jsonl").read_text(encoding="utf-8").splitlines()}
    if len(r70) != 70 or {r["metadata"]["source_record_id"] for r in r70} != set(approved):
        raise SystemExit("R70이 승인 70과 다르다")
    think_h, target_h, ids = [], [], []
    for r in r70:
        m = r["metadata"]
        content = r["messages"][2]["content"]
        reasoning, answer = thinking.split_response(content)
        th = selected[m["trace_id"]]["thinking"]
        if m["trace_id"] != approved[m["source_record_id"]] or reasoning != "<think>\n" + th + "\n</think>\n\n":
            raise SystemExit(f"{m['source_record_id']}: thinking이 승인 trace와 다르다")
        if thinking.response_json(content) != m["target_p0"]:
            raise SystemExit(f"{m['source_record_id']}: 답이 canonical target과 다르다")
        ids.append(m["source_record_id"])
        think_h.append(sha(th.encode("utf-8")))
        target_h.append(sha(json.dumps(m["target_p0"], ensure_ascii=False, sort_keys=True).encode("utf-8")))
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "sft_train.jsonl", "w", encoding="utf-8") as f:
        for r in r70:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    (OUT / "sft_valid.jsonl").write_text("", encoding="utf-8")
    psha = r70[0]["metadata"]["prompt_sha256"]
    manifest = {"sft": {"prompt_hash": psha, "representation": "flat", "contract": "P0", "format": "thinking", "issues": [],
                        "output_hashes": {"sft_train.jsonl": sha((OUT / "sft_train.jsonl").read_bytes()),
                                          "sft_valid.jsonl": sha((OUT / "sft_valid.jsonl").read_bytes())}}}
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    doc = {"version": "p0_sft_002/r70", "source": str(SRC.relative_to(ROOT)), "source_sha256": sha(SRC.read_bytes()),
           "records": len(r70), "sft_train_sha256": manifest["sft"]["output_hashes"]["sft_train.jsonl"],
           "manifest_sha256": sha((OUT / "manifest.json").read_bytes()), "prompt_sha256": psha,
           "item_ids": ids, "item_ids_sha256": sha("\n".join(ids).encode()),
           "thinking_sha256_concat": sha("".join(think_h).encode()), "target_sha256_concat": sha("".join(target_h).encode()),
           "by_source": {s: sum(r["metadata"]["source"] == s for r in r70) for s in ("v005", "augment_dt_event", "augment_od_vs_dt")},
           "arms": {"r70_json": {"data": "training/generated/p0_sft_002/r70", "loss_scope": "json_only"},
                    "r70_full": {"data": "training/generated/p0_sft_002/r70", "loss_scope": "full_response"}},
           "note": "두 arm이 같은 파일을 쓴다. item ID·thinking·최종 P0 JSON·레코드 순서가 같고, 다른 것은 loss_scope뿐이다."}
    (HERE / "r70_dataset_manifest.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: doc[k] for k in ("records", "sft_train_sha256", "item_ids_sha256", "by_source")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
