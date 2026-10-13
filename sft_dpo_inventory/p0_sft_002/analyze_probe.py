# -*- coding: utf-8 -*-
"""mechanism probe 분석과 gate(PLAN.md 6·7절, 결과 전에 고정). 모델 호출 없음.

    python sft_dpo_inventory/p0_sft_002/analyze_probe.py   # -> mechanism_probe/analysis.json

- Base(p0_sft_001 결과 재사용), R70-json, R70-full을 diagnostic panel 56문항에서 같은 함수(analyze_checkpoints.summarize)로 잰다.
- 주 지표: `<think>` emission rate. 함께: thinking_chars 중앙값, 첫 token `{` 비율, semantic correctness, malformed JSON, 생성 token.
- gate(practical threshold, 통계 gate 아님):
  - PASS: R70-full emission ≥ 0.80, R70-full − R70-json ≥ 0.50, R70-full thinking_chars 중앙값 > 0
  - PARTIAL: R70-full − R70-json ≥ 0.20, 그리고 PASS 아님
  - FAIL: 그 밖(R70-full도 thinking이 거의 없음)
"""
import collections
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
spec = importlib.util.spec_from_file_location("ac", HERE / "analyze_checkpoints.py")
AC = importlib.util.module_from_spec(spec)
spec.loader.exec_module(AC)
RAW = ROOT / "training/generated/p0_sft_002/mechanism_raw"


def main():
    panel = json.loads((HERE / "diagnostic_panel.json").read_text(encoding="utf-8"))
    AC.P.V.GOLD_PATH = HERE / "diagnostic_panel_gold.yaml"
    gold = {i["id"]: i for i in AC.P.V.load_gold(AC.P.V.GOLD_PATH)["items"]}
    strata = collections.defaultdict(list)
    for p in panel["items"]:
        strata[p["stratum"]].append(p["key"])
    diag = json.loads((HERE / "checkpoint_diagnostic.json").read_text(encoding="utf-8"))
    out = {"runs": {"base": diag["runs"]["base"]}}
    for arm in ("json", "full"):
        f = HERE / "mechanism_probe" / f"r70_{arm}.json"
        if not f.is_file():
            continue
        rows = {r["id"]: r for r in json.loads(f.read_text(encoding="utf-8"))["rows"]}
        raws = AC.first_calls(RAW / f"probe_r70_{arm}.jsonl")
        views = {}
        for key, item in gold.items():
            v = AC.P.item_view(item, rows[key])
            v.update(AC.V98.extra_view(item, rows[key]))
            v["malformed_first"] = v["first_error"] in AC.V98.MALFORMED
            views[key] = v
        s = AC.summarize(views, {k: AC.think_view(raws[k]) for k in gold}, strata)
        s["json_first_token_rate"] = round(s["first_token"].get("json", 0) / s["n"], 3)
        out["runs"][f"r70_{arm}"] = s
    if {"r70_json", "r70_full"} <= set(out["runs"]):
        j, f = out["runs"]["r70_json"], out["runs"]["r70_full"]
        gap = f["think_emission_rate"] - j["think_emission_rate"]
        verdict = ("PASS" if f["think_emission_rate"] >= 0.8 and gap >= 0.5 and f["thinking_chars_median"] > 0
                   else "PARTIAL" if gap >= 0.2 else "FAIL")
        out["gate"] = {"full_emission": f["think_emission_rate"], "json_emission": j["think_emission_rate"],
                       "gap": round(gap, 3), "full_thinking_median": f["thinking_chars_median"], "verdict": verdict}
    (HERE / "mechanism_probe" / "analysis.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(out.get("gate"), ensure_ascii=False))
    for k, v in out["runs"].items():
        print(k, {x: v.get(x) for x in ("correct", "think_emission_rate", "first_token", "thinking_chars_median",
                                         "generated_tokens_median", "malformed_first", "structural_first_response", "by_stratum")})


if __name__ == "__main__":
    main()
