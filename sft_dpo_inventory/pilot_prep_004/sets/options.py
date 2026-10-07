# -*- coding: utf-8 -*-
"""결정 41·42 셋 구성이 작업 지시 2의 규칙으로는 부족할 때의 선택지별 규모. ``survey.json``만 읽는다(모델 호출 없음).

    python sft_dpo_inventory/pilot_prep_004/sets/options.py

- 규칙대로(문항 단위 결과를 분석·설계에 쓴 셋은 셋째로 뺌, v13·v14 비교 포함): 남는 셋 0.
- 선택지 1: v13·v14 비교(GeoFlow 코드·prompt 선택용 평가)는 SFT 분석·데이터 설계로 보지 않고, SFT 쪽 문항 단위 사용(오류 유형 분석·
  공백 유형·batch004 설계의 근거 136문항)은 그 문항의 family 단위로 뺀다(셋 단위가 아니라 문항 family 단위).
- 선택지 2: 선택지 1과 같은 기준을 셋 단위로 적용(SFT 쪽에 한 문항이라도 쓰인 셋은 셋째로 뺌) → at·final_v12만 남는다.
- 각 선택지에서 조건(중복·정책·정답 grounding·mock 장소·pipeline 통과·학습 데이터와 family 겹침 없음)을 통과한 문항 수와 유형 분포.
"""
import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent


def types(rows):
    n = len(rows) or 1
    return {"items": len(rows),
            "집계 없음": round(sum(not r["type"]["aggregation"] for r in rows) / n, 3),
            "dimension 있음": round(sum(bool(r["type"]["dimension"]) for r in rows) / n, 3),
            "dimension_target 있음": round(sum(bool(r["type"]["dimension_target"]) for r in rows) / n, 3),
            "정지 기대": sum(r["expected_outcome"] != "answered" for r in rows),
            "measure": dict(Counter("+".join(r["type"]["measure"]) for r in rows).most_common(6)),
            "by_set": dict(Counter(r["set"] for r in rows))}


def main():
    survey = json.loads((HERE / "survey.json").read_text(encoding="utf-8"))
    sets = survey["sets"]
    candidates = [r for r in survey["items"] if not sets[r["set"]]["user_excluded"] and r["set"] != "cli_check_v14"]
    eligible = [r for r in candidates if r["eligible_conditions"]]
    sft_families = {r["family"] for r in candidates if r["checks"]["in_error_type_analysis"]}
    sft_sets = {r["set"] for r in candidates if r["checks"]["in_error_type_analysis"]}
    opt1 = [r for r in eligible if r["family"] not in sft_families]
    opt2 = [r for r in eligible if r["set"] not in sft_sets]
    opt1_aux = [r for r in opt1 if r["set"] in ("at", "final_v12")]
    opt1_sel = [r for r in opt1 if r["set"] not in ("at", "final_v12")]
    drop = Counter()
    for r in candidates:
        c = r["checks"]
        reason = ("duplicate" if c["duplicate_of_earlier_set"] else "policy_or_ambiguous" if c["policy_or_ambiguous"]
                  else "no_gold_grounding" if not c["gold_grounding"]
                  else f"place:{c['place_class']}" if not c["mock_resolves_all_places"]
                  else f"pipeline:{c['pipeline']['category']}" if not c["pipeline"]["passed"]
                  else "training_family_overlap" if any(c["overlap_training"].values()) else None)
        if reason:
            drop[reason] += 1
    out = {
        "rule_as_written": {"sets_left": [], "reason": "모든 후보 셋이 v13 개발 비교(428)·최종(56) 또는 v14 기록에 문항 단위로 쓰였다"},
        "conditions": {"candidate_sets": sorted({r["set"] for r in candidates}), "items": len(candidates),
                       "eligible": len(eligible), "dropped_by_reason": dict(drop)},
        "option1_item_family_level": {"pool": types(opt1),
                                      "split_example": {"selection(old44·contrast·indepv2–4)": types(opt1_sel),
                                                        "aux_test(at·final_v12)": types(opt1_aux)},
                                      "excluded_sft_families": len(sft_families)},
        "option2_set_level_sft_only": {"pool": types(opt2), "sets": sorted({r["set"] for r in opt2})},
    }
    (HERE / "options.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
