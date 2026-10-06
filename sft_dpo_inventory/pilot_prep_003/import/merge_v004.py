# -*- coding: utf-8 -*-
"""reviewed_gold_v003_t2pc와 batch004 승인분을 합친 reviewed_gold_v004_t2pc를 만든다(결정 13·14·16). 모델을 부르지 않는다.

    python sft_dpo_inventory/pilot_prep_003/import/merge_v004.py

- 입력(고치지 않는다):
  - ``training/generated/reviewed_gold_v003_t2pc``: SFT train 19 + valid 16, DPO train·valid.
  - ``training/generated/corpora/batch004_import_a``: queue A import(정지 후보 제외 14 gold, 9쌍).
  - ``training/generated/corpora/batch004_import_b``: queue B import(결정 14 정지 target 4 gold, 2쌍).
- 결정 16: valid split 없이 전부 학습(train)으로 둔다. v003_t2pc valid 16문항도 학습으로 옮긴다.
- 결정 13: v003의 compile 정지 SFT 17건은 포함한다. v003 DPO 표시 4건(``batch004/review/v003_flag_items.jsonl``,
  rejected=chosen 3 + constraint 실행 가능 1)은 뺀다. 같은 source_record_id와 chosen·rejected 내용으로 찾는다.
- 결정 16-1: thor 보호는 이전 판의 validation family를 풀지 않는다. v003_t2pc valid 16문항은 사용자가 명시 해제했다.
  해제는 아래 ``RELEASED``(그 16개 source_record_id)에만, 이전 validation 출처(``reviewed_gold_v003_t2pc/sft_valid.jsonl``과
  판 이력 지문)를 뺀 보호 대조를 통과할 때만 적용한다. 그 밖의 레코드는 thor 보호를 그대로 적용한다.
- 검사(thor): 모든 레코드에 ``Protection.current(...).reasons``(보호 질문·id·template·family)가 비어 있어야 하고,
  질문 중복이 없어야 한다(같은 질문이면 gold 의미가 같아야 하나로 합침). ``check_split``(빈 valid), 각 SFT·DPO 레코드의
  target 판정(``target_ok``: chosen_ok 또는 결정 14 정지 target의 같은 정지). 하나라도 실패하면 아무것도 쓰지 않고 멈춘다.
- 출력: ``training/generated/reviewed_gold_v004_t2pc``(ignored) + 기록 ``training/records/corpora/reviewed_gold_v004_t2pc``
  (manifest, 출처별 수, 제외 목록, 보호 대조 결과. 학습 레코드 자체는 ignored 경로에만 둔다).
"""
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))

from training.annotations.inventory import Protection  # noqa: E402
from training.data.canonicalize import canonical_json, semantic_key  # noqa: E402
from training.data.common import (check_expected_prompt, provenance, read_jsonl, sha256, write_jsonl,  # noqa: E402
                                  write_manifest)
from training.data.split import check_split, question_key  # noqa: E402
from training.data.validation import assess, target_ok  # noqa: E402

GEN = ROOT / "training/generated"
V003 = GEN / "reviewed_gold_v003_t2pc"
IMPORTS = {"batch004_a": GEN / "corpora/batch004_import_a", "batch004_b": GEN / "corpora/batch004_import_b"}
FLAGS = ROOT / "sft_dpo_inventory/batch004/review/v003_flag_items.jsonl"
OUT = GEN / "reviewed_gold_v004_t2pc"
RECORD = ROOT / "training/records/corpora/reviewed_gold_v004_t2pc"
VERSION = "reviewed_gold_v004_t2pc"
#: 결정 16-1: 명시 해제한 v003_t2pc valid 16문항(이전 판 validation 보호만 푼다).
RELEASED_FILE = V003 / "sft_valid.jsonl"


def released_ids():
    return {r["metadata"]["source_record_id"] for r in read_jsonl(RELEASED_FILE)}


def protection_without_old_validation():
    """Protection.current와 같은 출처에서 이전 판 validation(gold_dir의 sft_valid, 판 이력 지문)만 뺀 보호."""
    import tempfile
    with tempfile.TemporaryDirectory(prefix="v004_release_check_") as empty:
        (Path(empty) / "sft_valid.jsonl").write_text("", encoding="utf-8")
        return Protection.current(empty)


def load(directory, stage):
    return [r for split in ("train", "valid") for r in read_jsonl(directory / f"{stage}_{split}.jsonl")]


def pair_key(record):
    return (record["metadata"]["source_record_id"], canonical_json(json.loads(record["chosen"][0]["content"])),
            canonical_json(json.loads(record["rejected"][0]["content"])))


def main():
    if OUT.exists() or RECORD.exists():
        raise SystemExit("output already exists")
    prompt_hash = check_expected_prompt()
    sft, dpo, origin = [], [], Counter()
    for name, directory in [("v003_t2pc", V003), *IMPORTS.items()]:
        for record in load(directory, "sft"):
            record["metadata"]["corpus_origin"] = name
            sft.append(record)
            origin[f"sft:{name}"] += 1
        for record in load(directory, "dpo"):
            record["metadata"]["corpus_origin"] = name
            dpo.append(record)
            origin[f"dpo:{name}"] += 1
    flagged = []
    for row in read_jsonl(FLAGS):
        if row["kind"].startswith("dpo_"):
            flagged.append((row["source_record_id"], canonical_json(row["chosen"]), canonical_json(row["rejected"]),
                            row["item_id"], row["kind"]))
    keys = {pair_key(r): r for r in dpo if r["metadata"]["corpus_origin"] == "v003_t2pc"}
    excluded = []
    for sid, chosen, rejected, item_id, kind in flagged:
        match = keys.get((sid, chosen, rejected))
        if match is None:
            raise SystemExit(f"flagged v003 DPO pair not found by content: {item_id}")
        excluded.append({"item_id": item_id, "kind": kind, "source_record_id": sid, "reason": "decision 13 (decision 6)"})
        dpo.remove(match)

    # thor 보호 대조와 질문 중복.
    protection = Protection.current(V003)
    release_guard = protection_without_old_validation()
    release_ids = released_ids()
    if len(release_ids) != 16:
        raise SystemExit("release list must be the 16 v003_t2pc valid records")
    blocked, released, seen = [], [], {}
    for record in sft:
        meta = record["metadata"]
        question = record["messages"][1]["content"]
        payload = json.loads(record["messages"][-1]["content"])
        reasons = protection.reasons(question, payload, [meta.get("parent_intent"), meta.get("family"),
                                                          meta.get("source_record_id")])
        if reasons and meta["source_record_id"] in release_ids and meta["corpus_origin"] == "v003_t2pc":
            other = release_guard.reasons(question, payload, [meta.get("parent_intent"), meta.get("family"),
                                                              meta.get("source_record_id")])
            if not other:
                released.append({"id": meta["source_record_id"], "released_reasons": sorted(set(reasons))})
                meta["protection_release"] = "decision 16-1: old v003_t2pc validation family released by user"
                reasons = []
            else:
                reasons = reasons + [f"after_release_check:{x}" for x in other]
        if reasons:
            blocked.append({"id": meta["source_record_id"], "reasons": sorted(set(reasons))})
        key = question_key(question)
        if key in seen:
            raise SystemExit(f"duplicate question across sources: {meta['source_record_id']} / {seen[key]}")
        seen[key] = meta["source_record_id"]
        if not target_ok(assess(payload, question), meta):
            raise SystemExit(f"target check failed: {meta['source_record_id']}")
    for record in dpo:
        question = record["prompt"][1]["content"]
        if question_key(question) not in seen:
            raise SystemExit(f"DPO pair without SFT gold: {record['metadata']['source_record_id']}")
        chosen = json.loads(record["chosen"][0]["content"])
        rejected = json.loads(record["rejected"][0]["content"])
        if semantic_key(chosen, infer_events=True) == semantic_key(rejected, infer_events=True):
            raise SystemExit("chosen/rejected identical")
        if not target_ok(assess(chosen, question), record["metadata"]):
            raise SystemExit(f"DPO chosen target check failed: {record['metadata']['source_record_id']}")
    if blocked:
        print(json.dumps({"protection_blocked": blocked}, ensure_ascii=False, indent=1))
        raise SystemExit("protection check failed; nothing written")
    check_split(sft, [])

    OUT.mkdir(parents=True)
    write_jsonl(OUT / "sft_train.jsonl", sft)
    write_jsonl(OUT / "sft_valid.jsonl", [])
    write_jsonl(OUT / "dpo_train.jsonl", dpo)
    write_jsonl(OUT / "dpo_valid.jsonl", [])
    sources = [V003 / "manifest.json"] + [d / "corpus_manifest.json" for d in IMPORTS.values()] + [FLAGS]
    info = provenance(sources, 42)
    if info["prompt_hash"] != prompt_hash:
        raise SystemExit("prompt drift")
    base = {**info, "corpus_version": VERSION, "representation": "flat", "split_policy": "decision 16: all train, no valid"}
    write_manifest(OUT, "sft", sft, [], base, [])
    write_manifest(OUT, "dpo", dpo, [], base, [])
    protected = protection.manifest()
    protected.pop("fingerprints", None)
    summary = {
        "corpus_version": VERSION, "prompt_hash": prompt_hash,
        "sources": {"v003_t2pc": str(V003.relative_to(ROOT)), **{k: str(v.relative_to(ROOT)) for k, v in IMPORTS.items()}},
        "source_manifest_sha256": {str(p.relative_to(ROOT)): sha256(p) for p in sources},
        "counts": {"sft": len(sft), "dpo": len(dpo), "by_origin": dict(origin),
                   "sft_questions": len(seen), "stop_targets(decision 14)": sum(
                       r["metadata"].get("target_kind") == "t2pc_stop_grounding" for r in sft)},
        "excluded_v003_dpo_flags": excluded,
        "protection": {"checked_records": len(sft), "blocked": 0, "released(decision 16-1)": released, **protected},
        "split": "train only (decision 16)",
        "output_sha256": {p.name: sha256(p) for p in sorted(OUT.iterdir())},
    }
    (OUT / "corpus_manifest.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    RECORD.mkdir(parents=True)
    (RECORD / "corpus_manifest.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (RECORD / "manifest.json").write_text((OUT / "manifest.json").read_text(encoding="utf-8"), encoding="utf-8")
    print(json.dumps(summary["counts"], ensure_ascii=False), json.dumps(excluded, ensure_ascii=False))


if __name__ == "__main__":
    main()
