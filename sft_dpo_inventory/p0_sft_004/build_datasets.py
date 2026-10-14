# -*- coding: utf-8 -*-
"""FULL154 / JSON154 학습 파일(지시 25–33절). 모델 호출 0.

    python sft_dpo_inventory/p0_sft_004/build_datasets.py   # -> datasets/{full154,json154}.jsonl, valid_empty.jsonl, *_trainer_manifest.json

- 두 arm은 reviewed_reasoning_v001/dataset.jsonl(154)을 바이트 그대로 쓴다. 레코드·순서·문자열이 같고, 다른 것은 config의 thinking.loss_scope뿐이다.
- trainer manifest는 training.trainer_common._load_p0_records가 읽는 형식(prompt_hash, output_hashes)이다.
"""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SRC = ROOT / "sft_dpo_inventory/reviewed_reasoning_v001/dataset.jsonl"
SRC_SHA = "071ccdbee8c74694a189e861bb572975c6198da9c79b7cc93a558f531decea49"


def sha(b):
    return hashlib.sha256(b).hexdigest()


def main():
    data = SRC.read_bytes()
    if sha(data) != SRC_SHA:
        raise SystemExit("reviewed_reasoning_v001 sha256 불일치")
    rows = [json.loads(x) for x in data.decode("utf-8").splitlines() if x.strip()]
    psha = rows[0]["metadata"]["prompt_sha256"]
    out = HERE / "datasets"
    (out / "valid_empty.jsonl").write_text("", encoding="utf-8")
    doc = {"source": str(SRC.relative_to(ROOT)), "source_sha256": SRC_SHA, "records": len(rows), "arms": {}}
    for arm, scope in (("full154", "full_response"), ("json154", "json_only")):
        (out / f"{arm}.jsonl").write_bytes(data)
        manifest = {"sft": {"prompt_hash": psha, "representation": "flat", "contract": "P0", "format": "thinking", "issues": [],
                            "output_hashes": {"sft_train.jsonl": sha(data), "sft_valid.jsonl": sha(b"")}}}
        (out / f"{arm}_trainer_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        doc["arms"][arm] = {"file": f"datasets/{arm}.jsonl", "sha256": sha(data), "loss_scope": scope,
                            "config": f"training/configs/qwen3_8b_p0_sft004_{arm}.yaml"}
    doc["identical_files"] = (out / "full154.jsonl").read_bytes() == (out / "json154.jsonl").read_bytes()
    doc["answer_only_records"] = sum("<think>" not in r["messages"][2]["content"] for r in rows)
    (out / "manifest.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(doc, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
