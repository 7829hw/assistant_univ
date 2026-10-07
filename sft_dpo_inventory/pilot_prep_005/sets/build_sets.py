# -*- coding: utf-8 -*-
"""결정 46: 선택용 셋(결정 41)과 보조 시험 셋(결정 42)을 고정한다. 모델을 부르지 않는다.

    python sft_dpo_inventory/pilot_prep_005/sets/build_sets.py

- 후보: ``pilot_prep_004/sets/survey.json``의 선택지 1(``options.py``와 같은 규칙). SFT 쪽(오류 유형 분석·공백 유형·batch004
  근거 136문항)에 쓰인 문항의 family(같은 셋 안의 id stem·contrast 묶음)를 통째로 빼고, 조건을 통과한 문항.
  - 선택용 후보: old44·contrast·indepv2·indepv3·indepv4(154). 보조 시험 셋: at·final_v12(51, 전부).
- 조건은 지금 코드로 다시 확인한다(지문 791c4a68).
  - 장소가 mock으로 모두 풀림(``classify_providers``: mock·mock_and_reference·no_lookup).
  - 정책·모호 라벨 아님(``policy_scale.exclusion_keys``). 앞 셋과 정규화 질문 중복 없음(survey 기록).
  - 정답 grounding을 모델 응답 자리에 넣었을 때 현재 pipeline(평가와 같음: flat, 조건 계층, mock+legacy, 기준일 2026-09-25)이
    기대 결과로 끝남(``survey_sets.pipeline_check``).
  - 학습 데이터(``reviewed_gold_v005_t2pc``: v004 53 + batch005 승인 58)와 정규화 질문·거친 의미 family·thor family_key·
    thor template_key가 겹치지 않음. survey는 v004와만 대조했으므로 v005로 다시 대조한다.
  하나라도 실패하면 그 문항을 빼고 이유를 적는다.
- 선택용 셋 추출: 고정 seed(``SEED``)로 약 100문항을 층화 추출한다. 층 = 유형 칸(집계 유무 × dimension 유무 ×
  dimension_target 유무) × 정지 기대 여부. 층별 배정은 후보 비율에 비례(최대 나머지 방식), 층 안에서는 key 정렬 뒤
  ``random.Random(SEED + 층 번호).sample``.
- 출력: ``selection_items.json``, ``aux_test_items.json``(valid98_items.json과 같은 형식: 셋·경로·id·provider·기대 결과,
  질문 문장 없음), ``sets_summary.json``(유형 분포, 층별 수, 뺀 문항, sha256).
"""
import hashlib
import json
import random
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SURVEY_DIR = ROOT / "sft_dpo_inventory/pilot_prep_004/sets"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory"))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_prep_002/provider"))
sys.path.insert(0, str(SURVEY_DIR))

import classify_providers as CP  # noqa: E402
import evaluate_vendor100 as EV  # noqa: E402
from policy_scale import coarse_family, exclusion_keys, question_key  # noqa: E402
from survey_sets import MOCK_OK, pipeline_check, type_profile  # noqa: E402

SEED = 20261008
TARGET_SELECTION = 100
SELECTION_SETS = ("old44", "contrast", "indepv2", "indepv3", "indepv4")
AUX_SETS = ("at", "final_v12")
V005 = ROOT / "training/generated/reviewed_gold_v005_t2pc/sft_train.jsonl"
REFERENCE_DATE = date(2026, 9, 25)


def cell(t):
    return (f"agg={'Y' if t['aggregation'] else 'N'}|dim={'Y' if t['dimension'] else 'N'}|"
            f"dt={'Y' if t['dimension_target'] else 'N'}")


def stratum(row):
    return cell(row["type"]) + f"|stop={'Y' if row['expected_outcome'] != 'answered' else 'N'}"


def distribution(rows):
    n = len(rows) or 1
    return {"items": len(rows),
            "cells": {k: round(v / n, 3) for k, v in sorted(Counter(cell(r["type"]) for r in rows).items())},
            "집계 없음": round(sum(not r["type"]["aggregation"] for r in rows) / n, 3),
            "dimension 있음": round(sum(bool(r["type"]["dimension"]) for r in rows) / n, 3),
            "dimension_target 있음": round(sum(bool(r["type"]["dimension_target"]) for r in rows) / n, 3),
            "정지 기대": sum(r["expected_outcome"] != "answered" for r in rows),
            "by_set": dict(sorted(Counter(r["set"] for r in rows).items())),
            "measure": dict(Counter("+".join(r["type"]["measure"]) for r in rows).most_common(8))}


def allocate(groups, total):
    pool = sum(len(v) for v in groups.values())
    quota = {k: total * len(v) / pool for k, v in groups.items()}
    alloc = {k: int(q) for k, q in quota.items()}
    for k in sorted(groups, key=lambda k: (-(quota[k] - alloc[k]), k))[:total - sum(alloc.values())]:
        alloc[k] += 1
    return alloc


def main():
    from training.annotations.inventory import as_record, family_key
    from training.data.common import read_jsonl
    from training.data.split import template_key
    EV.REFERENCE_DATE = REFERENCE_DATE
    survey = json.loads((SURVEY_DIR / "survey.json").read_text(encoding="utf-8"))
    sets = survey["sets"]
    candidates = [r for r in survey["items"] if not sets[r["set"]]["user_excluded"] and r["set"] != "cli_check_v14"]
    sft_families = {r["family"] for r in candidates if r["checks"]["in_error_type_analysis"]}
    pool = [r for r in candidates if r["eligible_conditions"] and r["family"] not in sft_families]
    if (sum(r["set"] in SELECTION_SETS for r in pool), sum(r["set"] in AUX_SETS for r in pool)) != (154, 51):
        raise SystemExit("선택지 1 후보 수가 SURVEY.md(154, 51)와 다르다")
    v005 = read_jsonl(V005)
    train = {"question": {question_key(r["messages"][1]["content"]) for r in v005},
             "coarse_family": {coarse_family(json.loads(r["messages"][-1]["content"])) for r in v005},
             "thor_family_key": {family_key(json.loads(r["messages"][-1]["content"])) for r in v005},
             "thor_template_key": {template_key(r) for r in v005}}
    excluded_keys = exclusion_keys()
    documents = {}
    kept, dropped = [], []
    for r in pool:
        path = sets[r["set"]]["path"]
        if path not in documents:
            documents[path] = {i["id"]: i for i in EV.load_gold(ROOT / path)["items"]}
        item = documents[path][r["id"]]
        payload = EV.gold_grounding(item)
        cls, _ = CP.classify(payload)
        pipe = pipeline_check(item, payload)
        overlap = {"question": question_key(item["question"]) in train["question"],
                   "coarse_family": coarse_family(payload) in train["coarse_family"],
                   "thor_family_key": family_key(payload) in train["thor_family_key"],
                   "thor_template_key": template_key(as_record(payload)) in train["thor_template_key"]}
        why = ([f"place:{cls}"] if cls not in MOCK_OK else []) + (["policy_or_ambiguous"] if r["key"] in excluded_keys else []) \
            + ([f"pipeline:{pipe['category']}"] if not pipe["passed"] else []) + [f"overlap_v005:{k}" for k, v in overlap.items() if v]
        row = {"set": r["set"], "path": path, "id": r["id"], "key": r["key"], "family": r["family"], "provider": "mock",
               "place_class": cls, "expected_outcome": item.get("expected_outcome", "answered"),
               "type": type_profile(payload), "overlap_v005": overlap, "coarse_family": coarse_family(payload)}
        (dropped if why else kept).append({**row, "dropped_reasons": why} if why else row)
    sel_pool = [r for r in kept if r["set"] in SELECTION_SETS]
    aux = [r for r in kept if r["set"] in AUX_SETS]
    groups = defaultdict(list)
    for r in sorted(sel_pool, key=lambda r: (r["set"], r["id"])):
        groups[stratum(r)].append(r)
    alloc = allocate(groups, min(TARGET_SELECTION, len(sel_pool)))
    selection = []
    for index, key in enumerate(sorted(groups)):
        selection += random.Random(SEED + index).sample(groups[key], alloc[key])
    order = {name: i for i, name in enumerate(SELECTION_SETS + AUX_SETS)}
    selection.sort(key=lambda r: (order[r["set"]], r["key"]))
    aux.sort(key=lambda r: (order[r["set"]], r["key"]))
    paths = sorted({r["path"] for r in kept})
    sources = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in paths}
    common = {"decision": "46", "provider": "mock", "survey": "sft_dpo_inventory/pilot_prep_004/sets/survey.json",
              "survey_sha256": hashlib.sha256((SURVEY_DIR / "survey.json").read_bytes()).hexdigest(),
              "training_checked": str(V005.relative_to(ROOT)),
              "training_sha256": hashlib.sha256(V005.read_bytes()).hexdigest(), "labels_unchanged": True}
    files = {
        "selection_items.json": {**common, "name": "selection_v1", "use": "checkpoint selection only (decision 41); never training input",
                                 "seed": SEED, "strata": {k: {"pool": len(groups[k]), "picked": alloc[k]} for k in sorted(groups)},
                                 "sources_sha256": {p: sources[p] for p in sorted({r["path"] for r in selection})},
                                 "counts": {"items": len(selection), "by_set": dict(Counter(r["set"] for r in selection))},
                                 "items": [{k: r[k] for k in ("set", "path", "id", "provider", "place_class", "expected_outcome",
                                                               "overlap_v005")} for r in selection]},
        "aux_test_items.json": {**common, "name": "aux_test_v1",
                                "use": "reported with vendor100, never used for verdict, training, selection or annotation (decision 42)",
                                "sources_sha256": {p: sources[p] for p in sorted({r["path"] for r in aux})},
                                "counts": {"items": len(aux), "by_set": dict(Counter(r["set"] for r in aux))},
                                "items": [{k: r[k] for k in ("set", "path", "id", "provider", "place_class", "expected_outcome",
                                                              "overlap_v005")} for r in aux]},
    }
    for name, value in files.items():
        (HERE / name).write_text(json.dumps(value, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    summary = {
        "seed": SEED, "pool": {"selection_candidates": len(sel_pool), "aux": len(aux)},
        "rechecked_dropped": [{k: r[k] for k in ("set", "id", "dropped_reasons")} for r in dropped],
        "distribution": {"selection_pool": distribution(sel_pool), "selection": distribution(selection),
                         "aux_test": distribution(aux)},
        "id_overlap_between_sets": len({r["key"] for r in selection} & {r["key"] for r in aux}),
        "family_overlap_between_sets": len({r["family"] for r in selection} & {r["family"] for r in aux}),
        "coarse_family_overlap_between_sets(info only, not required by decision 46)": len(
            {r["coarse_family"] for r in selection} & {r["coarse_family"] for r in aux}),
        "sha256": {name: hashlib.sha256((HERE / name).read_bytes()).hexdigest() for name in files},
    }
    (HERE / "sets_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("pool", "rechecked_dropped", "sha256", "id_overlap_between_sets")}, ensure_ascii=False))
    for k, v in summary["distribution"].items():
        print(k, json.dumps(v, ensure_ascii=False))


if __name__ == "__main__":
    main()
