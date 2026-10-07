# -*- coding: utf-8 -*-
"""결정 37 장치 확인: GPU 2에서 다시 잰 E·B-conv와 GPU 3 기록(pilot_prep_003)을 비교한다. 모델을 부르지 않는다.

    python sft_dpo_inventory/pilot_001_analysis/device_check/compare.py

- 비교: 첫 응답(첫 계획 호출 본문)의 바이트 일치 수, thinking 길이 일치 수, grounding_ok, 보고 분류, U, 조용한 오답, 지연.
- 첫 응답이 하나라도 다르면 같은 장치(GPU 2)의 기준 셀로 E→학습 모델(PROTOCOL 쌍)과 삼자 비교를 다시 계산해 보조 기록으로 남긴다.
  확정된 PROTOCOL 판정(``pilot_001/vendor100/judgment.json``)은 바꾸지 않는다. 다시 계산한 값에는 판정 이름을 붙이지 않고,
  같은 규칙을 적용했을 때의 조건 충족 여부만 적는다.
- 결과: ``comparison.json``.
"""
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))


def _module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


C = _module("compare_cells", ROOT / "sft_dpo_inventory/baseline_conditions_001/compare_cells.py")
J = _module("judge", ROOT / "sft_dpo_inventory/pilot_001/vendor100/judge.py")
PREP = ROOT / "sft_dpo_inventory/pilot_prep_003/ollama"
V100 = ROOT / "sft_dpo_inventory/pilot_001/vendor100"
FILES = {"E@GPU3": PREP / "E.json", "B-conv@GPU3": PREP / "B-conv.json",
         "E@GPU2": HERE / "E.json", "B-conv@GPU2": HERE / "B-conv.json",
         "Ollama-SFT": V100 / "Ollama-sft.json", "Ollama-최종": V100 / "Ollama-final.json"}


def first_calls(path):
    rows = json.loads(path.read_text(encoding="utf-8"))["rows"]
    out = {}
    for row in rows:
        plans = [c for c in row.get("llm_calls") or [] if c.get("kind") == "plan"]
        first = plans[0] if plans else {}
        out[row["id"]] = {"content": first.get("content"), "thinking_chars": first.get("thinking_chars"),
                          "eval_count": first.get("eval_count"), "request_sha256": first.get("request_sha256"),
                          "calls": [(c.get("kind"), c.get("content")) for c in row.get("llm_calls") or []]}
    return out


def main():
    empty = HERE / ".empty_arm"
    empty.mkdir(exist_ok=True)
    cells = {name: C.load_cell(path, empty) for name, path in FILES.items()}
    empty.rmdir()
    latency = {n: round(J.median([(i["total_ms"] or 0) / 1000 for i in items.values()]), 2) for n, items in cells.items()}
    judgment = json.loads((V100 / "judgment.json").read_text(encoding="utf-8"))
    in_family = set(judgment["family(decision 15)"]["vendor_items_in_family"])
    out = {"device": {}, "meta": {}}
    for name in FILES:
        meta = json.loads(FILES[name].read_text(encoding="utf-8"))["meta"]
        out["meta"][name] = {"source": str(FILES[name].relative_to(ROOT)), "model_digest": meta.get("model_digest"),
                             "ollama_version": meta.get("ollama_version"), "started_at": meta.get("started_at"),
                             "code_commit": meta.get("code_commit")}
    any_diff = False
    for cell in ("E", "B-conv"):
        old, new = f"{cell}@GPU3", f"{cell}@GPU2"
        fo, fn = first_calls(FILES[old]), first_calls(FILES[new])
        keys = sorted(set(fo) & set(fn))
        differs = [k for k in keys if fo[k]["content"] != fn[k]["content"]]
        all_calls_differ = [k for k in keys if fo[k]["calls"] != fn[k]["calls"]]
        pair = J.pair(old, new, cells, latency, in_family, True)
        pair.pop("verdict", None)
        pair.pop("verdict_reasons", None)
        out["device"][cell] = {
            "items": len(keys), "first_response_byte_equal": len(keys) - len(differs), "first_response_differs": differs,
            "all_calls_equal": len(keys) - len(all_calls_differ), "any_call_differs": all_calls_differ,
            "request_equal": sum(1 for k in keys if fo[k]["request_sha256"] == fn[k]["request_sha256"]),
            "thinking_chars_equal": sum(1 for k in keys if fo[k]["thinking_chars"] == fn[k]["thinking_chars"]),
            "eval_count_equal": sum(1 for k in keys if fo[k]["eval_count"] == fn[k]["eval_count"]),
            "classes_equal": sum(1 for k in keys if cells[old][k]["report_class"] == cells[new][k]["report_class"]),
            "pair": pair}
        any_diff = any_diff or bool(differs)
    out["any_first_response_differs"] = any_diff
    # 지연만은 장치에 따라 달랐으므로, 같은 장치(GPU 2) 기준 셀에 대한 학습 모델 셀의 지연 비율을 보조로 적는다(판정 아님).
    out["latency_ratio_same_device(보조)"] = {f"{model}/{base}": round(latency[model] / latency[base], 3)
                                            for base in ("E@GPU2", "B-conv@GPU2") for model in ("Ollama-최종", "Ollama-SFT")}
    if any_diff:
        recalculated = {}
        for model in ("Ollama-최종", "Ollama-SFT"):
            p = J.pair("E@GPU2", model, cells, latency, in_family, True)
            p["same_rule_conditions(보조, 판정 아님)"] = {"worse_reasons": p.pop("verdict_reasons"), "label": p.pop("verdict")}
            recalculated[f"E@GPU2→{model}"] = p
            for a, label in (("E@GPU2", "변환 효과"), ("B-conv@GPU2", "학습 효과")):
                b = "B-conv@GPU2" if label == "변환 효과" else model
                q = J.pair(a, b, cells, latency, in_family, True)
                q.pop("verdict", None)
                q.pop("verdict_reasons", None)
                recalculated[f"삼자 {model}: {a}→{b}({label})"] = q
        out["same_device_recalculation(보조 기록, PROTOCOL 판정 아님)"] = recalculated
    (HERE / "comparison.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for cell, d in out["device"].items():
        p = d["pair"]
        print(cell, "first equal", d["first_response_byte_equal"], "/", d["items"], "all calls equal", d["all_calls_equal"],
              "think equal", d["thinking_chars_equal"], "g", p["grounding_ok"], "b/c", p["b"], p["c"], "p", p["mcnemar_p"],
              "U", p["U"], "silent", p["silent"], "lat", p["latency_median_s"], "classes equal", d["classes_equal"])
    for k, p in (out.get("same_device_recalculation(보조 기록, PROTOCOL 판정 아님)") or {}).items():
        print(k, p["grounding_ok"], "b/c", p["b"], p["c"], "p", p["mcnemar_p"], "U", p["U"], "silent", p["silent"],
              "lat", p["latency_ratio"], p.get("same_rule_conditions(보조, 판정 아님)", ""))


if __name__ == "__main__":
    main()
