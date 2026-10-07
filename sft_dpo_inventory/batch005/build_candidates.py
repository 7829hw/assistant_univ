# -*- coding: utf-8 -*-
"""batch005 후보의 현재 코드 결과와 보호 셋 겹침을 계산한다(모델 호출 없음). 승인하지 않는다(결정 45).

    python sft_dpo_inventory/batch005/build_candidates.py

- 입력: ``candidates_draft.yaml``(Claude 초안). 출력: ``candidates_checked.json``(남은 후보별 결과)와 ``excluded.json``(뺀 후보와 이유).
- 현재 코드 결과(batch004와 같다): thor ``assess``(normalize False/True), ``assess_t2pc``(조건 계층 켬, compose, validate, compile;
  기준일 2026-09-25).
- 겹침 검사(작업 지시 4: 겹치면 뺀다).
  - thor leakage: ``training.annotations.inventory.Protection.current``(보호 원본 전체: ``reserved_sources`` = evaluation/**/*.yaml,
    registry corpus·question set과 부모, root 질문·stub 파일)로 정규화 질문, id, semantic template, semantic family를 본다.
    gold_dir는 ``reviewed_gold_v004_t2pc``다(v004 manifest에는 이전 판 보호 지문이 없고, v003_t2pc valid 16문항은 결정 16-1로 학습에 들어갔다).
  - 확장 겹침: vendor 형식 보호 셋(업체 100 포함)의 정답 호출을 ``gold_grounding``으로 역산한 template·family
    (``batch004/build_candidates.extended_fingerprints``). batch004에서는 정보만 남겼지만 이번에는 지시대로 뺀다.
  - 새 선택용 셋·보조 시험 셋: 작업 지시 2에서 아직 만들지 않았다(``pilot_prep_004/sets/SURVEY.md``). 후보가 되는 문항은 모두 위 vendor 형식
    보호 셋 안에 있으므로 확장 겹침 검사가 그 범위를 덮는다.
- 학습 데이터(v004 reviewed gold 53문항)와의 겹침은 빼지 않고 정보로 남긴다.
"""
import json
import sys
from collections import Counter
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/batch004"))

from build_candidates import extended_fingerprints  # noqa: E402  (batch004와 같은 확장 지문)
from training.annotations.inventory import Protection, as_record, family_key  # noqa: E402
from training.data.canonicalize import check_shape, serialize_planner_target  # noqa: E402
from training.data.common import check_expected_prompt, read_jsonl  # noqa: E402
from training.data.split import question_key, template_key  # noqa: E402
from training.data.validation import assess, assess_t2pc, chosen_ok, t2pc_chosen_ok  # noqa: E402

GOLD_DIR = ROOT / "training/generated/reviewed_gold_v004_t2pc"


def main():
    prompt_hash = check_expected_prompt()
    document = yaml.safe_load((HERE / "candidates_draft.yaml").read_text(encoding="utf-8"))
    guard = Protection.current(GOLD_DIR)
    ext_templates, ext_families = extended_fingerprints()
    train = read_jsonl(GOLD_DIR / "sft_train.jsonl")
    train_q = {question_key(r["messages"][1]["content"]) for r in train}
    train_f = {family_key(json.loads(r["messages"][-1]["content"])) for r in train}
    train_t = {template_key(r) for r in train}
    rows, excluded = [], []
    seen_q = {}
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
        qk = question_key(item["question"])
        duplicate = seen_q.get(qk)
        seen_q.setdefault(qk, item["id"])
        row = {**{k: item[k] for k in ("id", "type", "family", "intent", "question", "rationale")},
               "draft_grounding": payload, "draft_target": target,
               "results": {"normalize_false": raw, "normalize_true": normalized, "t2pc": t2pc},
               "contract_ok": {"thor_normalize_false": chosen_ok(raw), "thor_normalize_true": chosen_ok(normalized),
                               "t2pc": t2pc_chosen_ok(t2pc)},
               "compile_ok": t2pc.get("compile_ok"),
               "leakage": {"thor_policy_reasons": reasons, "extended_overlap": extended},
               "overlap_training_info": {"question": qk in train_q, "family": family_key(payload) in train_f,
                                         "template": template_key(as_record(payload)) in train_t},
               "template_key": template_key(as_record(payload)), "family_key": family_key(payload)}
        why = list(reasons) + [f"extended_{k}" for k, v in extended.items() if v] + (
            [f"duplicate_of:{duplicate}"] if duplicate else [])
        if why:
            excluded.append({"id": item["id"], "type": item["type"], "reasons": why, "extended_sources": extended})
        else:
            rows.append(row)
    summary = {
        "prompt_hash": prompt_hash, "reference_date": document["reference_date"],
        "protection_sources": len(guard.paths), "drafted": len(document["candidates"]), "kept": len(rows),
        "excluded": len(excluded),
        "kept_by_type": dict(Counter(r["type"] for r in rows)),
        "excluded_by_reason": dict(Counter(reason for e in excluded for reason in e["reasons"])),
        "kept_families": len({r["family"] for r in rows}), "kept_intents": len({r["intent"] for r in rows}),
        "kept_semantic_families(family_key)": len({r["family_key"] for r in rows}),
        "contract_failures": [r["id"] for r in rows if not all(r["contract_ok"].values())],
        "t2pc_outcomes": dict(Counter(f"{r['results']['t2pc'].get('outcome')}:{r['results']['t2pc'].get('error_code')}"
                                      for r in rows)),
        "compile_stops": {r["id"]: r["results"]["t2pc"].get("compile_error_code") for r in rows if r["compile_ok"] is False},
        "condition_layer_changed_meaning": [r["id"] for r in rows if r["results"]["t2pc"]["condition_changed_meaning"]],
        "overlap_training_info": {k: sum(r["overlap_training_info"][k] for r in rows) for k in ("question", "family", "template")},
    }
    (HERE / "candidates_checked.json").write_text(json.dumps({"summary": summary, "candidates": rows},
                                                             ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (HERE / "excluded.json").write_text(json.dumps(excluded, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
