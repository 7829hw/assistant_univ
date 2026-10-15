# -*- coding: utf-8 -*-
"""W7a: 300문항 v2 train·holdout(결정 106 적용 273문항, 제외·축소 뺌)의 semantics 초안. 모델 호출 없음. **초안이고 승인이 아니다.**

    hfvenv/bin/python sft_dpo_inventory/pilot_006_prep/aug300_review/draft_semantics.py

- 뜻(measure subtype, 장소·scope 값, od_role, dimension, dimension_target, bucket/rollup, aggregation, order/limit, vicinity, 조건 factor)은
  업체 형식 정답 호출(execution 층)에서 역산한다(``evaluate_vendor100.derive_grounding``, 질문을 읽지 않음).
- 질문 span(text)만 규칙으로 붙인다(Claude 초안):
  - 장소: 값의 이름(없으면 "지역 이름")이 질문에 있으면 그 문자열. scope: scope id 문자열.
  - 측정값: subtype별 표현 목록에서 질문에 있는 가장 긴 것(``MEASURE_WORDS``). 못 찾으면 비우고 ``span_missing``으로 표시한다.
- 초안마다 검증 사슬(``grounding.validation.validate_semantics``, execution 층과의 일치 포함)을 돌린다. 통과도 승인이 아니다.
- holdout 문항도 같은 방법으로 쓴다(모델 출력을 보지 않는다. J2 셀은 봉인).
출력: ``semantics_draft.jsonl``(canonical 레코드, status=draft), ``semantics_draft_summary.json``.
"""
import collections
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))

from grounding.canonical import record, semantics_from_full  # noqa: E402
from grounding.validation import validate_semantics  # noqa: E402
from training.data.common import read_jsonl, sha256  # noqa: E402

AUG = ROOT / "sft_dpo_inventory/pilot_006_prep/aug300/augmentation_300.jsonl"
MEASURE_WORDS = {
    "passage_count": ["통행 건수", "통행량", "통행했", "통행", "지나간"],
    "trip_count": ["실차 이동 건수", "이동 건수", "승차 건수", "하차 건수", "실차 건수", "건수", "승차", "하차"],
    "speed": ["속도"], "rpm": ["RPM"], "fare": ["요금"], "revenue": ["총 수입", "총수입", "수입", "매출"],
    "vacant_ratio": ["공차율"], "active_taxi_ratio": ["가동률"], "active_taxi_count": ["활성택시 대수", "활성 택시 대수", "활성택시"],
    "operating_days": ["운행 일수", "운행일수"],
    "place": ["지역·장소명", "장소 이름", "장소명", "지역명", "지역 이름", "이름"],
}


def add_spans(payload, question):
    flags = []
    for concept in payload["concepts"]:
        if concept.get("concept") == "EVENT":
            continue
        if concept.get("role") == "MEASURE":
            words = sorted((w for w in MEASURE_WORDS.get(concept["subtype"], []) if w in question), key=len, reverse=True)
            if words:
                concept["text"] = words[0]
            else:
                flags.append(f"span_missing:measure:{concept['subtype']}")
            continue
        value = concept.get("value")
        if concept.get("subtype") == "scope" and isinstance(value, str):
            if value in question:
                concept["text"] = value
            else:
                flags.append("span_missing:scope")
        elif isinstance(value, dict):
            name, region = value.get("name", ""), value.get("region", "")
            for cand in (f"{region} {name}".strip(), name):
                if cand and cand in question:
                    concept["text"] = cand
                    break
            else:
                flags.append(f"span_missing:place:{name}")
    return payload, flags


def main():
    import evaluate_vendor100 as EV
    items = [i for i in read_jsonl(AUG) if i["status"] in ("train", "holdout")]
    out, summary_flags = [], collections.Counter()
    for item in items:
        payload, flags = add_spans(EV.derive_grounding(item["gold"]), item["question"])
        sem = semantics_from_full(payload)
        rec = record(item["id"], item["question"], "aug300_v2", semantics=sem, execution=item["gold"],
                     execution_source="vendor_gold_calls(xlsx 정답 Tool)", status=f"draft(승인 아님, {item['status']})",
                     provenance={"file": str(AUG.relative_to(ROOT)), "status_d1": item["status"], "family_id": item["family_id"],
                                 "semantic_type": item["semantic_type"], "risk_tags": item["risk_tags"],
                                 "drafted_by": "Claude 규칙 초안(2026-10-15): 뜻은 정답 호출 역산, span만 규칙"})
        rec["draft_flags"] = flags
        rec["validation"] = validate_semantics(sem, item["question"], item["gold"])
        summary_flags.update(f.split(":")[0] + ":" + f.split(":")[1] for f in flags)
        out.append(rec)
    with open(HERE / "semantics_draft.jsonl", "w", encoding="utf-8") as stream:
        for rec in out:
            stream.write(json.dumps(rec, ensure_ascii=False) + "\n")
    by_status = collections.defaultdict(collections.Counter)
    for rec in out:
        st = rec["provenance"]["status_d1"]
        by_status[st]["items"] += 1
        by_status[st]["chain_ok"] += rec["validation"]["ok"]
        by_status[st]["execution_match"] += bool(rec["validation"]["execution_match"])
        by_status[st]["full_answered_in_mock"] += rec["validation"]["full_answered"]
        by_status[st]["span_flags"] += bool(rec["draft_flags"])
    summary = {"items": len(out), "by_status": {k: dict(v) for k, v in by_status.items()},
               "chain_fail_ids": [r["id"] for r in out if not r["validation"]["ok"]],
               "chain_fail_detail": {r["id"]: {k: r["validation"][k] for k in ("assess_same", "mock_same", "execution_match", "full_answered")}
                                     for r in out if not r["validation"]["ok"]},
               "span_flags": dict(summary_flags), "span_flag_ids": {r["id"]: r["draft_flags"] for r in out if r["draft_flags"]},
               "input_sha256": sha256(AUG), "approval": "none (draft; validator PASS is not approval)"}
    (HERE / "semantics_draft_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k not in ("span_flag_ids",)}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
