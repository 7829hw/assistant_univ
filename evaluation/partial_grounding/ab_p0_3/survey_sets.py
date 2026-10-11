# -*- coding: utf-8 -*-
"""P0.3 판정용 셋 후보 조사(사용자 2026-10-11 지시 8·9절). 모델을 부르지 않는다. 질문 문장·정답 내용은 출력하지 않고 수만 센다.

    python evaluation/partial_grounding/ab_p0_3/survey_sets.py --out evaluation/partial_grounding/ab_p0_3/survey_sets.json

정답 grounding(`evaluate_vendor100.gold_grounding`)의 factor로 센다.
- OD 문항: place에 attributes.od_role이 있거나 factor dimension_target이 있음.
- dimension_target 문항: factor dimension_target이 있음(값 pickup/dropoff/both).
- bucket 문항: factor bucket이 있음.
selection_pool_rest는 결정 46의 선택용 후보(154) 중 selection_v1에 뽑히지 않은 문항이다(build_sets.py와 같은 후보 규칙).
"""
import argparse
import collections
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory"))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_prep_004/sets"))
import evaluate_vendor100 as EV  # noqa: E402

SETS = ROOT / "sft_dpo_inventory/pilot_prep_005/sets"
SURVEY = ROOT / "sft_dpo_inventory/pilot_prep_004/sets/survey.json"


def profile(item):
    payload = EV.gold_grounding(item) or {}
    factors = payload.get("factors") or {}
    od = any((c.get("attributes") or {}).get("od_role") for c in payload.get("concepts") or [])
    return {"expected": item.get("expected_outcome", "answered"), "has_gold_grounding": bool(payload),
            "od": od or "dimension_target" in factors, "dimension_target": factors.get("dimension_target"),
            "bucket": factors.get("bucket"), "dimension": factors.get("dimension")}


def summarize(profiles):
    c = collections.Counter
    return {"items": len(profiles),
            "expected": dict(c(p["expected"] for p in profiles)),
            "no_gold_grounding": sum(not p["has_gold_grounding"] for p in profiles),
            "od": sum(bool(p["od"]) for p in profiles),
            "dimension_target": dict(c(p["dimension_target"] for p in profiles if p["dimension_target"])),
            "dimension_target_items": sum(bool(p["dimension_target"]) for p in profiles),
            "bucket": dict(c(p["bucket"] for p in profiles if p["bucket"])),
            "bucket_items": sum(bool(p["bucket"]) for p in profiles),
            "dimension_items": sum(bool(p["dimension"]) for p in profiles)}


def load(path):
    return {str(i["id"]): i for i in EV.load_gold(ROOT / path)["items"]}


def from_refs(refs):
    docs, out = {}, []
    for ref in refs:
        docs.setdefault(ref["path"], load(ref["path"]))
        out.append(profile(docs[ref["path"]][str(ref["id"])]))
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    result = {}
    result["vendor100"] = summarize([profile(i) for i in EV.load_gold(ROOT / "evaluation/vendor100/gold.yaml")["items"]])
    result["valid98"] = summarize([profile(i) for i in EV.load_gold(
        ROOT / "sft_dpo_inventory/pilot_001_analysis/decision43/valid98_gold.yaml")["items"]])
    sel = json.loads((SETS / "selection_items.json").read_text(encoding="utf-8"))
    aux = json.loads((SETS / "aux_test_items.json").read_text(encoding="utf-8"))
    result["selection_v1"] = summarize(from_refs(sel["items"]))
    result["aux_test_v1"] = summarize(from_refs(aux["items"]))
    # 결정 46 선택용 후보 154 재구성: build_sets.py의 후보 규칙(survey 조건 통과, SFT family 제외, 선택용 셋) 중 v005 재확인 전 단계.
    survey = json.loads(SURVEY.read_text(encoding="utf-8"))
    sets = survey["sets"]
    candidates = [r for r in survey["items"] if not sets[r["set"]]["user_excluded"] and r["set"] != "cli_check_v14"]
    sft_families = {r["family"] for r in candidates if r["checks"]["in_error_type_analysis"]}
    pool = [r for r in candidates if r["eligible_conditions"] and r["family"] not in sft_families
            and r["set"] in ("old44", "contrast", "indepv2", "indepv3", "indepv4")]
    picked = {(r["set"], str(r["id"])) for r in sel["items"]}
    rest = [{"set": r["set"], "path": sets[r["set"]]["path"], "id": str(r["id"])} for r in pool
            if (r["set"], str(r["id"])) not in picked]
    result["selection_pool_rest"] = summarize(from_refs(rest))
    result["selection_pool_rest"]["pool"] = len(pool)
    result["selection_pool_rest"]["by_set"] = dict(collections.Counter(r["set"] for r in rest))
    result["selection_pool_rest"]["ids"] = [f"{r['set']}/{r['id']}" for r in rest]
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for name, s in result.items():
        print(name, {k: v for k, v in s.items() if k != "ids"})


if __name__ == "__main__":
    main()
