# -*- coding: utf-8 -*-
"""thor 업체 100 기준선(Base)과 dev-v2 harness의 qwen3:8b 기록을 같은 문항에서 비교한다. 기존 기록만 읽는다(새 측정 없음).

    python sft_dpo_inventory/vendor_compare.py

- thor: training/evaluations/vendor_100_baseline_001/RESULTS.json. 문항별 원응답(ignored raw)은 저장소에 없다. Base의
  "vendor grounding semantic match" 문항 집합은 커밋된 목록으로 복원한다. 세 arm 중 하나라도 맞은 문항 = all_fail의 여집합이고,
  base_to_sft 개선 0·sft_to_dpo 개선 2(SFT 실패 문항)·Base 35건이 그 여집합 크기와 같으면 Base 집합 = 여집합이다.
- dev-v2: 같은 지표(evaluate_vendor100.grounding_check, 최종 grounding)를 기록한 qwen3:8b + prompt 522aa3b1 기록.
  기록에 저장된 grounding_ok와, 현재 코드로 다시 계산한 값을 함께 본다. 첫 응답(llm_calls[0])에 같은 비교를 적용한
  값도 센다(정규화·조건 계층·재질의 전의 단계 보기). 원인을 정하지 않는다.
- 질문 문장은 산출물에 넣지 않는다.
"""
import json
from collections import Counter

from _common import ROOT, thor_json, write_output

import evaluate_vendor100 as EV
from geoflow.planner import parse_planner_json

THOR_DIR = "training/evaluations/vendor_100_baseline_001"
DEV_RECORDS = [
    "evaluation/grounding_v9/runs/full/q8_cur/dev.json",
    "evaluation/grounding_v11/runs/rerun_code/q8_cur/D/dev.json",
]


def thor_sets():
    results = thor_json(f"{THOR_DIR}/RESULTS.json")
    ids = [f"{i:03d}" for i in range(1, 101)]
    out = {}
    for metric, paired_key in (("vendor_grounding_semantic_match", "paired"),
                               ("mock_semantic_match", "paired_vendor_mock_semantics")):
        paired = results[paired_key]
        union = [i for i in ids if i not in set(paired["all_fail"])]
        base_count = results["metrics"]["base"][metric]["count"]
        derivable = not paired["base_to_sft_improvements"] and len(union) == base_count
        out[metric] = {"base_count": base_count, "union_count": len(union),
                       "base_set_derivable": derivable, "base_ids": union if derivable else None}
    return out, results


def first_response_ok(item, row):
    calls = [c for c in row.get("llm_calls") or [] if c.get("kind") == "plan"]
    if not calls:
        return None
    try:
        payload = parse_planner_json(calls[0].get("content") or "")
    except Exception:  # noqa: BLE001
        return False
    if payload.get("unsupported"):
        return False
    ok, _ = EV.grounding_check(item, payload)
    return ok


def main():
    sets, results = thor_sets()
    gold = {item["id"]: item for item in EV.load_gold(ROOT / "evaluation/vendor100/gold.yaml")["items"]}
    thor_base = set(sets["vendor_grounding_semantic_match"]["base_ids"] or [])
    comparisons = {}
    for path in DEV_RECORDS:
        document = json.loads((ROOT / path).read_text(encoding="utf-8"))
        meta = document["meta"]
        rows = {r["id"]: r for r in document["rows"]}
        recorded = {i for i, r in rows.items() if r.get("grounding_ok")}
        recomputed = {i for i, r in rows.items() if EV.grounding_check(gold[i], r.get("grounding"))[0]}
        first = {i for i, r in rows.items() if first_response_ok(gold[i], r)}
        condition_changed = {i for i, r in rows.items() if r.get("condition_corrections")}
        repaired = {i for i, r in rows.items()
                    if any(c.get("kind") != "plan" for c in r.get("llm_calls") or [])}

        def table(dev_set):
            ids = sorted(gold)
            return {"both_match": len([i for i in ids if i in thor_base and i in dev_set]),
                    "thor_only": sorted(i for i in ids if i in thor_base and i not in dev_set),
                    "dev_only_count": len([i for i in ids if i not in thor_base and i in dev_set]),
                    "neither": len([i for i in ids if i not in thor_base and i not in dev_set])}

        dev_only = sorted(i for i in recorded if i not in thor_base)
        comparisons[path] = {
            "meta": {k: meta.get(k) for k in ("model", "model_digest", "planner_prompt_sha256", "code_commit",
                                              "reference_date", "scorer_version", "ollama_version")}
            | {"pipeline": meta.get("pipeline"), "model_details": meta.get("model_details")},
            "grounding_ok_recorded": len(recorded), "grounding_ok_recomputed_current_code": len(recomputed),
            "recorded_equals_recomputed": recorded == recomputed,
            "first_response_grounding_match": len(first),
            "vs_thor_base_final": table(recorded),
            "vs_thor_base_first_response": table(first),
            "dev_only_items": {
                "count": len(dev_only),
                "first_response_already_matched": len([i for i in dev_only if i in first]),
                "condition_layer_corrected_or_filled": len([i for i in dev_only if i in condition_changed]),
                "repair_call_made": len([i for i in dev_only if i in repaired]),
            },
            "condition_corrections_by_factor": dict(Counter(c["condition"] + ":" + c["action"]
                                                            for r in rows.values()
                                                            for c in r.get("condition_corrections") or [])),
        }
    thor_runtime = results["runtime"]["base"]
    out = {
        "thor": {"sets": sets, "metric_definitions": "REPORT.md: vendor grounding semantic match = 기존 evaluator의 "
                 "measure/place/scope/factor/aggregation IR 비교, 최종 grounding 기준",
                 "runtime_base": {k: thor_runtime.get(k) for k in ("torch", "cuda", "device", "attention")},
                 "effective_generation_config": {k: thor_runtime.get("effective_generation_config", {}).get(k)
                                                 for k in ("max_new_tokens", "do_sample", "num_beams",
                                                           "repetition_penalty")}},
        "dev_v2": comparisons,
    }
    path, digest = write_output("vendor_compare.json", out)
    print(json.dumps(out, ensure_ascii=False, indent=1))
    print(f"\nwrote {path} sha256={digest}")


if __name__ == "__main__":
    main()
