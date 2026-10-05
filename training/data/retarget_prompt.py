"""Rebuild an archived reviewed corpus with the current production prompt (labels, splits and metadata unchanged).

    python -m training.data.retarget_prompt \
      --archive training/records/corpora/reviewed_gold_v003 \
      --version reviewed_gold_v003_t2pc \
      --output training/generated/reviewed_gold_v003_t2pc \
      --records training/records/corpora/reviewed_gold_v003_t2pc

- thor의 v003 archive(``dataset_index.json``)는 system prompt를 522aa3b1 hash marker로 보관한다. 이 도구는 archive
  hash를 확인한 뒤 marker 자리에 현재 production prompt(기대값 87048d0c)를 넣는다. 그 밖의 바이트(질문, target, split,
  metadata)는 바꾸지 않는다. 승인을 새로 만들지 않고, 레코드를 빼거나 고치지 않는다.
- 출력(``--output``, ignored): SFT·DPO JSONL과 trainer가 읽는 ``manifest.json``.
- 기록(``--records``, 커밋 대상): manifest, T2PC 경로 판정 표시(``review_flags.json``). 표시는 처분이 아니다.
  - SFT: compile에서 멈춤(mock·legacy), 조건 계층이 의미를 바꿈.
  - DPO: 조건 계층을 거치면 rejected가 chosen과 같아짐, constraint rejected가 T2PC 경로에서 계약을 통과함(실행 가능).
- thor의 ``assess``(조건 계층 없음) 판정이 archive 기록과 같은지도 확인한다.
"""
import argparse
import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from training.data.canonicalize import SCHEMA_VERSION
from training.data.common import (EXPECTED_PROMPT_SHA256, check_expected_prompt, coverage, production_prompt,
                                  provenance, read_jsonl, sha256, write_jsonl)
from training.data.validation import assess, assess_t2pc, t2pc_chosen_ok
from training.pilot import audit

STAGES = ("sft", "dpo")
SPLITS = ("train", "valid")
_QUALITY_KEYS = ("parse_ok", "compose_ok", "validation_ok", "error_code", "outcome")


def _question(record, stage):
    messages = record["messages"] if stage == "sft" else record["prompt"]
    return next(m["content"] for m in messages if m["role"] == "user")


def _same_quality(recorded, current):
    if not recorded:
        return None
    return (all(recorded.get(k) == current.get(k) for k in _QUALITY_KEYS)
            and sorted(recorded.get("validation_codes") or []) == sorted(current.get("validation_codes") or []))


def _brief(result):
    keys = ("parse_ok", "compose_ok", "validation_ok", "validation_codes", "error_code", "outcome", "compile_ok",
            "compile_error_code", "condition_actions", "condition_changed_meaning", "condition_changed_outcome")
    return {k: result.get(k) for k in keys}


def retarget(archive, version):
    """archive의 레코드에 현재 prompt를 넣은 (datasets, flags, archive_manifest)."""
    archive = Path(archive)
    corpus = json.loads((archive / "corpus_manifest.json").read_text(encoding="utf-8"))
    for name in ("dataset_index.json", "manifest.json"):
        if sha256(archive / name) != corpus["output_hashes"][name]:
            raise ValueError(f"Archive drift: {name}")
    old_hash = corpus["prompt_hash"]
    new_hash = check_expected_prompt()
    prompt = production_prompt()
    index = json.loads((archive / "dataset_index.json").read_text(encoding="utf-8"))
    datasets = {stage: {} for stage in STAGES}
    flags = {"sft": [], "dpo": []}
    for stage in STAGES:
        for split in SPLITS:
            records = copy.deepcopy(index[f"{stage}_{split}"])
            for position, record in enumerate(records):
                messages = record["messages"] if stage == "sft" else record["prompt"]
                if messages[0]["content"] != {"production_prompt_sha256": old_hash}:
                    raise ValueError("Prompt marker mismatch")
                messages[0]["content"] = prompt
                question = _question(record, stage)
                meta = record["metadata"]
                base = {"split": split, "position": position, "source_record_id": meta.get("source_record_id"),
                        "batch_item_ids": meta.get("batch_item_ids") or [], "corpus_version": meta.get("corpus_version")}
                if stage == "sft":
                    target = json.loads(record["messages"][-1]["content"])
                    thor_view = assess(target, question)
                    t2pc = assess_t2pc(target, question)
                    marks = []
                    if t2pc.get("compile_ok") is False:
                        marks.append(f"compile_stop:{t2pc['compile_error_code']}")
                    if t2pc["condition_changed_meaning"]:
                        marks.append("condition_layer_changed_meaning")
                    if not t2pc_chosen_ok(t2pc):
                        marks.append("t2pc_contract_failure")
                    flags["sft"].append({**base, "marks": marks, "thor_assess_reproduced":
                                         _same_quality(meta.get("chosen_quality"), thor_view),
                                         "t2pc": _brief(t2pc)})
                else:
                    chosen = json.loads(record["chosen"][0]["content"])
                    rejected = json.loads(record["rejected"][0]["content"])
                    c_thor, r_thor = assess(chosen, question), assess(rejected, question)
                    c_t2pc, r_t2pc = assess_t2pc(chosen, question), assess_t2pc(rejected, question)
                    marks = []
                    if c_t2pc["signature"] is not None and c_t2pc["signature"] == r_t2pc["signature"]:
                        marks.append("t2pc_rejected_equals_chosen")
                    if meta.get("negative_category") == "constraint" and t2pc_chosen_ok(r_t2pc):
                        marks.append("t2pc_constraint_rejected_passes_contract")
                    if c_t2pc.get("compile_ok") is False:
                        marks.append(f"chosen_compile_stop:{c_t2pc['compile_error_code']}")
                    flags["dpo"].append({**base, "negative_type": meta.get("negative_type"),
                                         "negative_category": meta.get("negative_category"), "marks": marks,
                                         "thor_assess_reproduced": {
                                             "chosen": _same_quality(meta.get("chosen_quality"), c_thor),
                                             "rejected": _same_quality(meta.get("rejected_quality"), r_thor)},
                                         "t2pc": {"chosen": _brief(c_t2pc), "rejected": _brief(r_t2pc)}})
            datasets[stage][split] = records
    audit(datasets["sft"], datasets["dpo"])
    return datasets, flags, corpus, new_hash


def write(datasets, flags, corpus, prompt_hash, *, archive, version, output, records_dir):
    output, records_dir = Path(output), Path(records_dir)
    if output.exists():
        raise ValueError(f"Output already exists: {output}")
    output.mkdir(parents=True)
    for stage in STAGES:
        for split in SPLITS:
            write_jsonl(output / f"{stage}_{split}.jsonl", datasets[stage][split])
    info = provenance([Path(archive) / "dataset_index.json", Path(archive) / "corpus_manifest.json"], corpus["seed"])
    if info["prompt_hash"] != prompt_hash or prompt_hash != EXPECTED_PROMPT_SHA256:
        raise ValueError("Prompt hash changed during build")
    manifest = {}
    for stage in STAGES:
        train, valid = datasets[stage]["train"], datasets[stage]["valid"]
        manifest[stage] = {
            **info, "corpus_version": version, "parent_corpus": corpus["corpus_version"],
            "parent_corpus_manifest_hash": sha256(Path(archive) / "corpus_manifest.json"),
            "parent_prompt_hash": corpus["prompt_hash"], "split_policy": "Inherited unchanged from " + corpus["corpus_version"],
            "label_policy": "Labels, splits and metadata byte-identical to the archive; only the system prompt changed",
            "individual_human_record_inspection_claimed": False, "representation": "flat",
            "output_schema_version": SCHEMA_VERSION, "train_count": len(train), "validation_count": len(valid),
            "coverage": coverage(train + valid), "issues": [],
            "output_hashes": {f"{stage}_{split}.jsonl": sha256(output / f"{stage}_{split}.jsonl") for split in SPLITS}}
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    records_dir.mkdir(parents=True, exist_ok=True)
    summary = {
        "sft": {mark: sum(1 for f in flags["sft"] if any(m.startswith(mark) for m in f["marks"]))
                for mark in ("compile_stop", "condition_layer_changed_meaning", "t2pc_contract_failure")},
        "dpo": {mark: sum(1 for f in flags["dpo"] if any(m.startswith(mark) for m in f["marks"]))
                for mark in ("t2pc_rejected_equals_chosen", "t2pc_constraint_rejected_passes_contract",
                             "chosen_compile_stop")},
        "thor_assess_reproduced": {
            "sft": sum(bool(f["thor_assess_reproduced"]) for f in flags["sft"]),
            "dpo_chosen": sum(bool(f["thor_assess_reproduced"]["chosen"]) for f in flags["dpo"]),
            "dpo_rejected": sum(bool(f["thor_assess_reproduced"]["rejected"]) for f in flags["dpo"])}}
    (records_dir / "review_flags.json").write_text(json.dumps(
        {"note": "표시는 처분이 아니다. 빼거나 고치지 않았다. 처분은 사람 검토(batch004 시트)로 넘긴다.",
         "summary": summary, **flags}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (records_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                                                encoding="utf-8")
    receipt = {"generated_at": datetime.now(timezone.utc).isoformat(), "archive": str(archive),
               "version": version, "prompt_hash": prompt_hash, "parent_prompt_hash": corpus["prompt_hash"],
               "counts": {f"{s}_{p}": len(datasets[s][p]) for s in STAGES for p in SPLITS},
               "output_hashes": {name: sha256(output / name) for name in sorted(p.name for p in output.iterdir())},
               "review_flags_sha256": sha256(records_dir / "review_flags.json"), "summary": summary}
    (records_dir / "build_receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=1) + "\n",
                                                    encoding="utf-8")
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--records", required=True)
    args = parser.parse_args(argv)
    datasets, flags, corpus, prompt_hash = retarget(args.archive, args.version)
    receipt = write(datasets, flags, corpus, prompt_hash, archive=args.archive, version=args.version,
                    output=args.output, records_dir=args.records)
    print(json.dumps(receipt, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
