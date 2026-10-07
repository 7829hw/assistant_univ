# -*- coding: utf-8 -*-
"""batch005 승인분을 import하고 reviewed_gold_v004_t2pc와 합쳐 reviewed_gold_v005_t2pc를 만든다(결정 47). 모델을 부르지 않는다.

    python sft_dpo_inventory/pilot_prep_005/import/merge_v005.py

1. import: thor ``import_reviewed``로 파생 queue(``reviewed_queue``)와 ``decisions_005.jsonl``을 읽어
   ``training/generated/corpora/batch005_import``를 만든다. thor가 보호(``Protection.current``)·출처·prompt 고정을 검사한다.
2. 합치기: v004(SFT 53, DPO 39) + batch005 import. 결정 16·47: valid split 없이 전부 학습(train)이다.
3. 검사(thor, ``pilot_prep_003/import/merge_v004.py``와 같음): 모든 SFT 레코드에 ``Protection.current(v004).reasons``(보호
   질문·id·template·family)가 비어 있어야 한다. 결정 16-1로 명시 해제한 v003_t2pc valid 16문항만 같은 해제 조건(이전 validation
   출처를 뺀 보호로 다시 대조해 걸리지 않음)을 적용한다. 질문 중복 없음, ``check_split``(빈 valid), SFT·DPO의 target 판정
   (``target_ok``). 하나라도 실패하면 아무것도 쓰지 않고 멈춘다.
- 출력: ``training/generated/reviewed_gold_v005_t2pc`` + 기록 ``training/records/corpora/reviewed_gold_v005_t2pc``(manifest).
"""
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_prep_003/import"))

from merge_v004 import load, protection_without_old_validation  # noqa: E402
from training.annotations.inventory import Protection  # noqa: E402
from training.annotations.workflow import import_reviewed  # noqa: E402
from training.data.canonicalize import semantic_key  # noqa: E402
from training.data.common import check_expected_prompt, provenance, read_jsonl, sha256, write_jsonl, write_manifest  # noqa: E402
from training.data.split import check_split, question_key  # noqa: E402
from training.data.validation import assess, target_ok  # noqa: E402

GEN = ROOT / "training/generated"
V004 = GEN / "reviewed_gold_v004_t2pc"
V003_VALID = GEN / "reviewed_gold_v003_t2pc/sft_valid.jsonl"
QUEUE = HERE / "reviewed_queue"
DECISIONS = HERE / "decisions_005.jsonl"
IMPORT = GEN / "corpora/batch005_import"
OUT = GEN / "reviewed_gold_v005_t2pc"
RECORD = ROOT / "training/records/corpora/reviewed_gold_v005_t2pc"
VERSION = "reviewed_gold_v005_t2pc"


def main():
    if OUT.exists() or RECORD.exists():
        raise SystemExit("output already exists")
    prompt_hash = check_expected_prompt()
    if not IMPORT.exists():
        print(json.dumps({"import_reviewed": import_reviewed(QUEUE, DECISIONS, IMPORT, version="batch005_import")}))
    sft, dpo, origin = [], [], Counter()
    for name, directory in [("v004_t2pc", V004), ("batch005", IMPORT)]:
        for stage, bucket in (("sft", sft), ("dpo", dpo)):
            for record in load(directory, stage):
                record["metadata"].setdefault("corpus_origin", name)
                record["metadata"]["corpus_origin_v005"] = name
                bucket.append(record)
                origin[f"{stage}:{name}"] += 1
    protection = Protection.current(V004)
    release_guard = protection_without_old_validation()
    release_ids = {r["metadata"]["source_record_id"] for r in read_jsonl(V003_VALID)}
    if len(release_ids) != 16:
        raise SystemExit("release list must be the 16 v003_t2pc valid records")
    blocked, released, seen = [], [], {}
    for record in sft:
        meta = record["metadata"]
        question = record["messages"][1]["content"]
        payload = json.loads(record["messages"][-1]["content"])
        ids = [meta.get("parent_intent"), meta.get("family"), meta.get("source_record_id")]
        reasons = protection.reasons(question, payload, ids)
        if reasons and meta["source_record_id"] in release_ids and meta["corpus_origin_v005"] == "v004_t2pc":
            other = release_guard.reasons(question, payload, ids)
            if not other:
                released.append({"id": meta["source_record_id"], "released_reasons": sorted(set(reasons))})
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
    sources = [V004 / "corpus_manifest.json", IMPORT / "corpus_manifest.json", DECISIONS]
    info = provenance(sources, 42)
    if info["prompt_hash"] != prompt_hash:
        raise SystemExit("prompt drift")
    base = {**info, "corpus_version": VERSION, "representation": "flat", "split_policy": "decisions 16·47: all train, no valid"}
    write_manifest(OUT, "sft", sft, [], base, [])
    write_manifest(OUT, "dpo", dpo, [], base, [])
    protected = protection.manifest()
    protected.pop("fingerprints", None)
    imported = json.loads((IMPORT / "corpus_manifest.json").read_text(encoding="utf-8"))
    summary = {
        "corpus_version": VERSION, "prompt_hash": prompt_hash,
        "sources": {"v004_t2pc": str(V004.relative_to(ROOT)), "batch005": str(IMPORT.relative_to(ROOT)),
                    "batch005_queue": str(QUEUE.relative_to(ROOT)), "batch005_decisions": str(DECISIONS.relative_to(ROOT))},
        "source_sha256": {str(p.relative_to(ROOT)): sha256(p) for p in sources},
        "counts": {"sft": len(sft), "dpo": len(dpo), "by_origin": dict(origin), "sft_questions": len(seen),
                   "stop_targets(decision 14)": sum(r["metadata"].get("target_kind") == "t2pc_stop_grounding" for r in sft)},
        "batch005_import_excluded": imported.get("excluded"),
        "protection": {"checked_records": len(sft), "blocked": 0, "released(decision 16-1)": released, **protected},
        "split": "train only (decisions 16·47)",
        "output_sha256": {p.name: sha256(p) for p in sorted(OUT.iterdir())},
    }
    (OUT / "corpus_manifest.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    RECORD.mkdir(parents=True)
    (RECORD / "corpus_manifest.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (RECORD / "manifest.json").write_text((OUT / "manifest.json").read_text(encoding="utf-8"), encoding="utf-8")
    print(json.dumps(summary["counts"], ensure_ascii=False), json.dumps({"released": len(released)}))


if __name__ == "__main__":
    main()
