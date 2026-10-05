# -*- coding: utf-8 -*-
"""thor reviewed gold v003을 dev-v2의 현재 보호 대상(evaluation/ 등)과 다시 대조한다. 모델 호출 없음.

    python sft_dpo_inventory/leakage_recheck.py --thor-root THOR_WORKTREE

- thor의 보호 로직(training.annotations.inventory.Protection: 정규화 질문, id, semantic template, semantic family)을
  thor worktree에서 import해 그대로 쓴다. 보호 원본 목록(training.data.common.reserved_sources)은 dev-v2 root 기준으로 읽는다.
- dev-v2의 geoflow.aggregation에는 thor가 추가한 ``to_flat``이 없다. thor의 정의를 이 프로세스 메모리에만 주입한다
  (파일 수정 없음). structured source를 flat으로 바꿀 때만 쓰인다.
- (a) thor 구현 그대로: 문항의 ``golden``/``grounding``만 template·family 지문을 만든다. vendor100 형식 셋(``gold`` 호출,
  ``gold_grounding``)은 질문·id만 보호된다.
  (b) 확장 대조: vendor100 형식 문항(``gold``·``gold_text``·``gold_grounding``)은 ``evaluate_vendor100.load_gold``·``gold_grounding``으로 정답 grounding을 만들어 같은 지문을 계산한다.
  (b)는 이 조사의 추가 대조이며 thor 정책의 일부가 아니다.
- 학습 자료를 만들거나 옮기지 않는다. 산출물에는 질문 문장 없이 id·사유·출처 경로만 남긴다.
"""
import argparse
import copy
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from _common import CORPORA, ROOT, thor_json, write_output


def to_flat(spec):
    """thor geoflow/aggregation.py의 to_flat(b314904)과 같은 정의."""
    from geoflow.aggregation import UNSPECIFIED, from_flat
    factors = {}
    if spec.inner not in (None, UNSPECIFIED):
        factors["aggregation"] = spec.inner
    if spec.bucket:
        factors["bucket"] = spec.bucket
        if spec.select:
            factors.update(rollup=spec.select, answer="bucket")
        elif spec.outer:
            factors["rollup"] = spec.outer
    after = from_flat(factors)
    if (after.bucket, after.inner, after.outer, after.select) != (spec.bucket, spec.inner, spec.outer, spec.select):
        raise ValueError("Aggregation spec cannot be represented losslessly as flat factors.")
    return factors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--thor-root", required=True)
    args = parser.parse_args()
    sys.path.append(str(Path(args.thor_root).resolve()))   # dev-v2 root가 앞에 있어 geoflow는 dev-v2의 것이다.

    import yaml
    from geoflow import aggregation
    aggregation.to_flat = to_flat
    import training.data.common as TC
    import training.annotations.inventory as INV
    TC.ROOT = INV.ROOT = ROOT
    import paraphrase_corpus as P
    import evaluate_vendor100 as EV

    sources = sorted(TC.reserved_sources())
    per_source = {}
    for path in sources:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        if isinstance(document, dict) and "intents" in document:
            document = copy.deepcopy(document)
            P.expand_aggregation(document)
        plain = INV.Protection()
        plain.visit(document)
        extended = INV.Protection()
        extended.visit(document)
        items = None
        if isinstance(document, dict) and isinstance(document.get("items"), list) and any(
                isinstance(i, dict) and ({"gold", "gold_text", "gold_grounding"} & set(i)) for i in document["items"]):
            items = EV.load_gold(path)["items"]   # gold_text 줄 표기도 정답 호출로 읽는다
        derived = 0
        for item in items or []:
            if isinstance(item, dict):
                try:
                    payload = EV.gold_grounding(item)
                except Exception:  # noqa: BLE001 - 정답 호출이 없는 문항
                    payload = None
                if payload:
                    extended.add(payload=payload)
                    derived += 1
        per_source[path.relative_to(ROOT).as_posix()] = (plain, extended, derived)

    index = thor_json(f"{CORPORA}/reviewed_gold_v003/dataset_index.json")
    records = [(split, r) for split in ("sft_train", "sft_valid") for r in index[split]]
    hits = []
    for split, record in records:
        meta = record["metadata"]
        question = record["messages"][1]["content"]
        payload = json.loads(record["messages"][-1]["content"])
        ids = [meta.get(k) for k in ("source_record_id", "parent_intent", "family")]
        for source, (plain, extended, _) in per_source.items():
            a = plain.reasons(question, payload, ids)
            b = extended.reasons(question, payload, ids)
            if a or b:
                hits.append({"id": meta["source_record_id"], "batch_item_ids": meta.get("batch_item_ids"),
                             "split": split, "corpus_version": meta.get("corpus_version"), "source": source,
                             "thor_policy_reasons": a, "extended_reasons": b})

    by_record = defaultdict(lambda: {"thor": set(), "extended": set(), "sources": set()})
    for hit in hits:
        entry = by_record[(hit["id"], hit["split"])]
        entry["thor"].update(hit["thor_policy_reasons"])
        entry["extended"].update(hit["extended_reasons"])
        entry["sources"].add(hit["source"])
    new_paths = {"evaluation/grounding_v10/heldout_questions.yaml",
                 "evaluation/grounding_v10/status_contrast_questions.yaml",
                 "evaluation/grounding_v12/final_questions.yaml",
                 "evaluation/grounding_v12/measure_contrast_questions.yaml",
                 "evaluation/grounding_v13/cli_check_questions.yaml",
                 "evaluation/grounding_v14/cli_check_gold.yaml"}
    summary = {
        "reserved_sources": len(sources),
        "sources_added_after_thor_base": sorted(new_paths & set(per_source)),
        "vendor_format_items_with_derived_gold": {s: v[2] for s, v in per_source.items() if v[2]},
        "sft_records": len(records),
        "records_hit_thor_policy": sum(1 for v in by_record.values() if v["thor"]),
        "records_hit_extended_only": sum(1 for v in by_record.values() if v["extended"] and not v["thor"]),
        "thor_policy_reason_counts": dict(Counter(r for v in by_record.values() for r in v["thor"])),
        "extended_reason_counts": dict(Counter(r for v in by_record.values() for r in v["extended"])),
        "records_hit_by_sources_added_after_thor_base": sorted(
            f"{k[0]} ({k[1]})" for k, v in by_record.items() if v["sources"] & new_paths),
        "per_record": {f"{k[0]} ({k[1]})": {"thor": sorted(v["thor"]), "extended": sorted(v["extended"]),
                                            "sources": sorted(v["sources"])} for k, v in by_record.items()},
    }
    path, digest = write_output("leakage_recheck_v003.json", {"summary": summary, "hits": hits})
    print(json.dumps({k: v for k, v in summary.items() if k != "per_record"}, ensure_ascii=False, indent=1))
    print(f"\nwrote {path} sha256={digest}")


if __name__ == "__main__":
    main()
