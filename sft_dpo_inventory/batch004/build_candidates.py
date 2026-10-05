# -*- coding: utf-8 -*-
"""batch004 후보의 현재 코드 결과와 보호 셋 겹침을 계산한다(모델 호출 없음). 승인하지 않는다.

    python sft_dpo_inventory/batch004/build_candidates.py

- 입력: ``candidates_draft.yaml``(Claude 초안). 출력: ``candidates_checked.json``(후보별 결과)와 ``excluded.json``.
- 결과: thor ``assess``(normalize False/True), ``assess_t2pc``(조건 계층 켬, compose, validate, compile; 기준일 2026-09-25).
- 겹침(thor 정책, 제외): ``training.annotations.inventory.Protection.current``(보호 원본·v003 보호 이력)에 v003_t2pc
  validation family를 더해 정규화 질문, id, semantic template, semantic family를 본다.
- 겹침(확장 대조, 정보만): vendor 형식 평가 셋의 정답 호출을 ``gold_grounding``으로 역산한 template·family. thor 정책이
  보지 않는 범위다(sft_dpo_inventory/README.md 3.5절). 제외하지 않고 사람 검토 항목으로 남긴다.
"""
import json
import sys
from collections import Counter
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

from training.annotations.inventory import Protection, as_record, family_key  # noqa: E402
from training.data.canonicalize import check_shape, serialize_planner_target  # noqa: E402
from training.data.common import check_expected_prompt, read_jsonl, reserved_sources  # noqa: E402
from training.data.split import question_key, template_key  # noqa: E402
from training.data.validation import assess, assess_t2pc, chosen_ok, t2pc_chosen_ok  # noqa: E402

V003 = ROOT / "training/records/corpora/reviewed_gold_v003"
V003_T2PC_VALID = ROOT / "training/generated/reviewed_gold_v003_t2pc/sft_valid.jsonl"


#: thor Protection.current의 gold_dir. v003_t2pc 생성 디렉터리(ignored)에 v003 보호 이력(corpus_manifest.json)을 둔다.
#: 그러면 v003 보호 지문과 v003_t2pc validation(이전 validation family)이 함께 보호된다. 검토 결과를 가져올 때
#: (workflow import-reviewed) 같은 경로로 다시 계산해 보호 원본이 바뀌지 않았는지 확인한다.
GOLD_DIR = ROOT / "training/generated/reviewed_gold_v003_t2pc"


def protection():
    import shutil
    history = GOLD_DIR / "corpus_manifest.json"
    if not history.exists():
        shutil.copyfile(V003 / "corpus_manifest.json", history)
    elif history.read_bytes() != (V003 / "corpus_manifest.json").read_bytes():
        raise SystemExit("보호 이력 사본이 v003 corpus_manifest.json과 다르다")
    return Protection.current(GOLD_DIR), len(read_jsonl(V003_T2PC_VALID))


def extended_fingerprints():
    """vendor 형식 셋의 정답 호출 역산 grounding으로 만든 template·family(정보용)."""
    import evaluate_vendor100 as EV
    templates, families = {}, {}
    for path in sorted(reserved_sources()):
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not (isinstance(document, dict) and isinstance(document.get("items"), list)
                and any(isinstance(i, dict) and {"gold", "gold_text", "gold_grounding"} & set(i)
                        for i in document["items"])):
            continue
        for item in EV.load_gold(path)["items"]:
            try:
                payload = EV.gold_grounding(item)
            except Exception:  # noqa: BLE001 - 정답 호출이 없는 문항
                payload = None
            if not payload:
                continue
            name = path.relative_to(ROOT).as_posix()
            templates.setdefault(template_key(as_record(payload)), set()).add(name)
            families.setdefault(family_key(payload), set()).add(name)
    return templates, families


def main():
    prompt_hash = check_expected_prompt()
    document = yaml.safe_load((HERE / "candidates_draft.yaml").read_text(encoding="utf-8"))
    guard, added = protection()
    ext_templates, ext_families = extended_fingerprints()
    rows, excluded = [], []
    for item in document["candidates"]:
        gold = item["gold"]
        check_shape(gold)
        target = serialize_planner_target(gold)
        payload = json.loads(target)
        raw = assess(payload, item["question"], normalize=False)
        normalized = assess(payload, item["question"], normalize=True)
        t2pc = assess_t2pc(payload, item["question"])
        t2pc.pop("signature", None)
        reasons = guard.reasons(item["question"], payload, [item["id"], item["intent"], item["family"]])
        extended = {"template": sorted(ext_templates.get(template_key(as_record(payload)), ())),
                    "family": sorted(ext_families.get(family_key(payload), ()))}
        row = {**{k: item[k] for k in ("id", "type", "family", "intent", "question", "rationale")},
               "draft_grounding": payload, "draft_target": target,
               "results": {"normalize_false": raw, "normalize_true": normalized, "t2pc": t2pc},
               "contract_ok": {"thor_normalize_false": chosen_ok(raw), "thor_normalize_true": chosen_ok(normalized),
                               "t2pc": t2pc_chosen_ok(t2pc)},
               "compile_ok": t2pc.get("compile_ok"),
               "leakage": {"thor_policy_reasons": reasons, "extended_overlap_info_only": extended},
               "template_key": template_key(as_record(payload)), "family_key": family_key(payload)}
        if reasons:
            excluded.append({"id": item["id"], "type": item["type"], "reasons": reasons})
        else:
            rows.append(row)
    summary = {
        "prompt_hash": prompt_hash, "reference_date": document["reference_date"],
        "protection_sources": len(guard.paths), "v003_t2pc_valid_records_added": added,
        "drafted": len(document["candidates"]), "kept": len(rows), "excluded": len(excluded),
        "kept_by_type": dict(Counter(r["type"] for r in rows)),
        "excluded_by_reason": dict(Counter(reason for e in excluded for reason in e["reasons"])),
        "kept_families": len({r["family"] for r in rows}), "kept_intents": len({r["intent"] for r in rows}),
        "contract_failures": [r["id"] for r in rows if not all(r["contract_ok"].values())],
        "compile_stops": {r["id"]: r["results"]["t2pc"].get("compile_error_code") for r in rows
                          if r["compile_ok"] is False},
        "condition_layer_changed_meaning": [r["id"] for r in rows if r["results"]["t2pc"]["condition_changed_meaning"]],
        "extended_overlap_info_only": {"template": sum(bool(r["leakage"]["extended_overlap_info_only"]["template"])
                                                       for r in rows),
                                       "family": sum(bool(r["leakage"]["extended_overlap_info_only"]["family"])
                                                     for r in rows)},
    }
    (HERE / "candidates_checked.json").write_text(json.dumps({"summary": summary, "candidates": rows},
                                                             ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (HERE / "excluded.json").write_text(json.dumps(excluded, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
