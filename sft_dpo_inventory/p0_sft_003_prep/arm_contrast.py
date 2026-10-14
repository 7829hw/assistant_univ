# -*- coding: utf-8 -*-
"""결과 뒤 추가(사후) 보조 분석: R70-json과 R70-full은 데이터·coverage가 같다. 둘의 차이는 trace 문장 학습 여부뿐이다.
panel 56문항에서 두 arm의 정답 교차표와, 첫 응답 JSON의 구조 패턴(gold에 없는 aggregation, 묶음 단위어를 장소·concept로 냄,
값 없는 place)을 Base·R70-json·R70-full에서 센다. 모델 호출 없음. -> arm_contrast.json
"""
import collections
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
UNIT = re.compile(r"^(읍면동|시군구|시도|구|동|셀|H3 셀|h3|emd|sigungu|sido)$|하차 ?구|승차 ?구|동네$")
UNIT_SUBTYPES = {"emd", "sido", "sigungu", "h3", "dayofweek"}


def first_answers(path):
    out = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        if r["call"] == 0:
            text = r["raw_text"].split("</think>")[-1]
            i, j = text.find("{"), text.rfind("}")
            try:
                out[r["id"]] = json.loads(text[i:j + 1]) if i >= 0 else None
            except Exception:  # noqa: BLE001
                out[r["id"]] = None
    return out


def patterns(ans, gold_factors):
    if not isinstance(ans, dict):
        return {"unparsed": 1}
    cs = ans.get("concepts") or []
    f = ans.get("factors") or {}
    p = collections.Counter()
    if f.get("aggregation") and not gold_factors.get("aggregation"):
        p["aggregation_overinclude"] += 1
    if any(c.get("subtype") in UNIT_SUBTYPES for c in cs):
        p["unit_as_concept"] += 1
    if any(c.get("subtype") == "place" and (UNIT.search(str(c.get("text") or "")) or
                                            UNIT.search(str((c.get("value") or {}).get("name", "")) if isinstance(c.get("value"), dict) else "")) for c in cs):
        p["unit_as_place"] += 1
    if any(c.get("subtype") == "place" and not c.get("value") for c in cs):
        p["valueless_place"] += 1
    return dict(p)


def main():
    cov = json.loads((HERE / "coverage_analysis.json").read_text(encoding="utf-8"))
    items = {x["key"]: x for x in cov["items"]}
    base = {}
    for s in ("sel154", "valid98", "vendor100", "aux_test_v1"):
        for k, v in first_answers(ROOT / f"training/generated/p0_sft_001/eval_raw/base_{s}.jsonl").items():
            base[f"{s}:{k}"] = v
    ans = {"base": {k: base[k] for k in items},
           "r70_json": first_answers(ROOT / "training/generated/p0_sft_002/mechanism_raw/probe_r70_json.jsonl"),
           "r70_full": first_answers(ROOT / "training/generated/p0_sft_002/mechanism_raw/probe_r70_full.jsonl")}
    import importlib.util
    spec = importlib.util.spec_from_file_location("ca", HERE / "coverage_analysis.py")
    CA = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(CA)
    CA.EV.GOLD_PATH = ROOT / "sft_dpo_inventory/p0_sft_002/diagnostic_panel_gold.yaml"
    gold = {i["id"]: i for i in CA.EV.load_gold(CA.EV.GOLD_PATH)["items"]}
    counts = {m: collections.Counter() for m in ans}
    for m, a in ans.items():
        for k in items:
            gf = (CA.EV.gold_grounding(gold[k]) or {}).get("factors") or {}
            for name, v in patterns(a.get(k), gf).items():
                counts[m][name] += v
    ok = lambda c: c in ("match", "expected_refusal")  # noqa: E731
    cross = collections.Counter((ok(x["r70_json"]), ok(x["r70_full"])) for x in items.values())
    full_only_wrong = [k for k, x in items.items() if ok(x["r70_json"]) and not ok(x["r70_full"])]
    json_only_wrong = [k for k, x in items.items() if not ok(x["r70_json"]) and ok(x["r70_full"])]
    pat = lambda m, ks: dict(sum((collections.Counter(patterns(ans[m].get(k), (CA.EV.gold_grounding(gold[k]) or {}).get("factors") or {})) for k in ks), collections.Counter()))  # noqa: E731
    out = {"note": "사후 보조 분석(PLAN 사전 등록 아님)",
           "cross_json_full": {"both_correct": cross[(True, True)], "json_only_correct": cross[(True, False)],
                               "full_only_correct": cross[(False, True)], "both_wrong": cross[(False, False)]},
           "full_only_wrong_items": full_only_wrong, "json_only_wrong_items": json_only_wrong,
           "patterns_first_answer_56": {m: dict(c) for m, c in counts.items()},
           "patterns_in_full_only_wrong": {"r70_full": pat("r70_full", full_only_wrong), "r70_json": pat("r70_json", full_only_wrong)},
           "regression_B_also_json_correct": [k for k, x in items.items() if x["group"] == "B" and ok(x["r70_json"])]}
    (HERE / "arm_contrast.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
