# -*- coding: utf-8 -*-
"""baseline_conditions_001 셀 비교(모델 호출 없음). 모든 셀을 같은 기준으로 채점한다.

    python sft_dpo_inventory/baseline_conditions_001/compare_cells.py

- grounding_ok: 현재 ``evaluate_vendor100.grounding_check``로 최종 grounding을 다시 채점한다(기록값과 다르면 표시).
- dev-v2 분류: v4 축(``axes_rows``)과 grounding_v13 ``report.py``의 U1–U4. 보고 분류는 U가 우선이다(용납할 수 없는 실패 →
  U가 아닌 조용한 오답 → 안전한 실패(실행 실패·부당한 거부) → 정상 답변·정당한 거부).
- HF 셀(thor runner 출력)은 vendor100 결과 형식으로 바꿔(``hf/<cell>/dev.json``) 같은 경로로 읽는다.
- 한 조건만 다른 셀끼리 같은 문항 기준 전이 표를 만든다. 셀마다 한 번만 실행했으므로 작은 차이는 해석하지 않는다.
- 질문 문장은 산출물에 넣지 않는다(문항 id만).
"""
import importlib.util
import json
import statistics
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


R = _load("report_v13", ROOT / "evaluation/grounding_v13/report.py")
import evaluate_vendor100 as EV  # noqa: E402

CELLS = {
    "A": ("ollama", "522aa3b1", "auto", True, ROOT / "evaluation/grounding_v9/runs/full/q8_cur/dev.json"),
    "B": ("ollama", "522aa3b1", "off", True, HERE / "runs/B.json"),
    "C": ("ollama", "522aa3b1", "off", False, HERE / "runs/C.json"),
    "D": ("ollama", "522aa3b1", "auto", False, HERE / "runs/D.json"),
    "E": ("ollama", "87048d0c", "auto", True, HERE / "runs/E.json"),
    "F": ("ollama", "87048d0c", "off", True, HERE / "runs/F.json"),
    "HF": ("hf_thor", "522aa3b1", "off(enable_thinking=False)", False, HERE / "hf/base/dev.json"),
    "HFcc": ("hf_thor", "522aa3b1", "off(enable_thinking=False)", True, HERE / "hf/base_cc/dev.json"),
}
PAIRS = [("A", "B", "thinking (522aa3b1, 조건 계층 켬)"),
         ("B", "C", "조건 계층 (522aa3b1, think off)"),
         ("C", "HF", "실행 경로: Ollama Q4_K_M+Ollama template ↔ HF BF16+HF template (522aa3b1, thinking 끔, 조건 계층 끔)"),
         ("E", "F", "thinking (87048d0c, 조건 계층 켬)"),
         ("D", "C", "thinking (522aa3b1, 조건 계층 끔)"),
         ("A", "D", "조건 계층 (522aa3b1, think auto)"),
         ("HF", "HFcc", "조건 계층 (HF 경로)"),
         ("B", "F", "prompt·코드 522aa3b1+c1f2a08 ↔ 87048d0c+T2PC (think off, 조건 계층 켬)"),
         ("A", "E", "prompt·코드 522aa3b1+c1f2a08 ↔ 87048d0c+T2PC (think auto, 조건 계층 켬)")]


def convert_hf(cell_dir):
    """thor runner raw jsonl → vendor100 결과 형식(dev.json). 실행할 때마다 raw에서 다시 만든다."""
    raw = cell_dir / "raw" / "base_raw.jsonl"
    target = cell_dir / "dev.json"
    if not raw.is_file():
        return None
    rows = [json.loads(line) for line in raw.read_text(encoding="utf-8").splitlines() if line.strip()]
    for row in rows:
        row.pop("run", None)   # pipeline 내부 기록(크다). 채점에 쓰지 않는다
    runtime = json.loads((cell_dir / "raw" / "base_runtime.json").read_text())
    receipt = json.loads((cell_dir / "receipt.json").read_text()) if (cell_dir / "receipt.json").is_file() else {}
    target.write_text(json.dumps({"meta": {"kind": "hf_thor_runner", "gold_file": "evaluation/vendor100/gold.yaml",
                                           "runtime": runtime, "receipt": receipt, "scorer_version": EV.SCORER_VERSION},
                                  "rows": rows}, ensure_ascii=False) + "\n", encoding="utf-8")
    return target


def report_class(row, flags):
    if flags:
        return "용납할 수 없는 실패"
    if row["v4"] == "오답":
        return "조용한 오답(U 아님)"
    if row["v4"] in ("실행 실패", "부당한 거부"):
        return "안전한 실패"
    return row["v4"]


def load_cell(path, empty):
    rows, raw = R.C.load_arm(empty, None, {"dev": str(path)})
    gold = {i["id"]: i for i in EV.load_gold(None)["items"]}
    out = {}
    for key, row in rows.items():
        item_id = key.split("/", 1)[1]
        source = raw[key]
        flags = R.unacceptable(key, row, source)
        regraded, diffs = EV.grounding_check(gold[item_id], source.get("grounding"))
        plans = [c for c in source.get("llm_calls") or [] if c.get("kind") == "plan" and not c.get("failed")]
        thinking = [c.get("thinking_chars") for c in source.get("llm_calls") or [] if c.get("thinking_chars") is not None]
        try:
            layers = EV.grounding_layers(gold[item_id], source)
        except Exception as error:  # noqa: BLE001 - 현재 코드도 같은 원출력에서 미처리 예외(057, grounding.py)
            layers = {name: {"valid": False, "ok": False, "code": f"EXCEPTION:{type(error).__name__}"}
                      for name in ("raw", "normalized", "preserved")}
        out[item_id] = {"layers": {name: {"valid": layers[name].get("valid"), "ok": layers[name].get("ok")}
                                   for name in ("raw", "normalized", "preserved")},
                        "v4": row["v4"], "report_class": report_class(row, flags), "u_flags": flags,
                        "grounding_ok": bool(regraded), "grounding_ok_recorded": source.get("grounding_ok"),
                        "grounding_diff_keys": sorted({d if isinstance(d, str) else d[0] for d in diffs}),
                        "outcome": source.get("outcome"), "error_code": source.get("error_code"),
                        "total_ms": row["cost"]["total_ms"], "repair_calls": row["cost"]["repair_calls"],
                        "failed_calls": row["cost"]["failed_calls"],
                        "thinking_chars_plan": plans[0].get("thinking_chars") if plans else None,
                        "thinking_chars_all": sum(t or 0 for t in thinking) if thinking else None,
                        "eval_tokens": sum(c.get("eval_count") or 0 for c in source.get("llm_calls") or [])
                        if any(c.get("eval_count") is not None for c in source.get("llm_calls") or []) else None}
    return out


def summary(items):
    n = len(items)
    totals = sorted((i["total_ms"] or 0) / 1000 for i in items.values())
    thinking = [i["thinking_chars_plan"] for i in items.values() if i["thinking_chars_plan"] is not None]
    return {
        "items": n, "grounding_ok": sum(i["grounding_ok"] for i in items.values()),
        "grounding_ok_recorded_differs": sorted(k for k, i in items.items()
                                                if i["grounding_ok_recorded"] is not None
                                                and bool(i["grounding_ok_recorded"]) != i["grounding_ok"]),
        "v4": dict(Counter(i["v4"] for i in items.values())),
        "report_class": dict(Counter(i["report_class"] for i in items.values())),
        "u_kinds": dict(Counter(f.split(":")[0] for i in items.values() for f in {x.split(":")[0] for x in i["u_flags"]})),
        "latency_s": {"median": round(statistics.median(totals), 1) if totals else None,
                      "p90": round(totals[min(n - 1, int(0.9 * n))], 1) if totals else None,
                      "sum": round(sum(totals))},
        # 첫 응답을 현재 코드(dev-v2 HEAD)의 층별 처리로 다시 통과시킨 값(evaluate_vendor100.grounding_layers, 재질의 없음).
        # raw = 계약 그대로(정규화 끔), normalized = 자리 바로잡기, preserved = + 조건 계층(현재 코드의 조건 계층).
        "first_response_layers": {name: {"valid": sum(bool(i["layers"][name]["valid"]) for i in items.values()),
                                         "grounding_ok": sum(bool(i["layers"][name]["ok"]) for i in items.values())}
                                  for name in ("raw", "normalized", "preserved")},
        "repair_calls": sum(i["repair_calls"] for i in items.values()),
        "failed_calls": sum(i["failed_calls"] for i in items.values()),
        "thinking_chars_first_plan": {"items_with_thinking": sum(1 for t in thinking if t > 0), "of": len(thinking),
                                      "median": statistics.median(thinking) if thinking else None,
                                      "max": max(thinking) if thinking else None},
        "eval_tokens_total": sum(i["eval_tokens"] or 0 for i in items.values())
        if any(i["eval_tokens"] is not None for i in items.values()) else None,
    }


def transition(a, b):
    keys = sorted(set(a) & set(b))
    grounding = Counter(f"{'O' if a[k]['grounding_ok'] else 'X'}→{'O' if b[k]['grounding_ok'] else 'X'}" for k in keys)
    classes = Counter(f"{a[k]['report_class']}→{b[k]['report_class']}" for k in keys)
    return {"common": len(keys), "grounding_ok_transitions": dict(sorted(grounding.items())),
            "grounding_gained": [k for k in keys if not a[k]["grounding_ok"] and b[k]["grounding_ok"]],
            "grounding_lost": [k for k in keys if a[k]["grounding_ok"] and not b[k]["grounding_ok"]],
            "report_class_transitions": dict(sorted(classes.items())),
            "report_class_changed": {k: f"{a[k]['report_class']}→{b[k]['report_class']}" for k in keys
                                     if a[k]["report_class"] != b[k]["report_class"]}}


def main():
    empty = HERE / ".empty_arm"
    empty.mkdir(exist_ok=True)
    for name in ("base", "base_cc"):
        convert_hf(HERE / "hf" / name)
    thor = json.loads(__import__("subprocess").check_output(
        ["git", "show", "b3149040fb0fc57bedd1e8ff4436333f55d41e5a:training/evaluations/vendor_100_baseline_001/RESULTS.json"],
        cwd=ROOT))
    thor_base = sorted(f"{i:03d}" for i in range(1, 101) if f"{i:03d}" not in set(thor["paired"]["all_fail"]))
    cells, missing = {}, []
    for name, (path_kind, prompt, think, condition, path) in CELLS.items():
        if not Path(path).is_file():
            missing.append(name)
            continue
        cells[name] = load_cell(path, empty)
    out = {"cells": {}, "pairs": {}, "missing_cells": missing, "thor_committed_base_ids": thor_base}
    for name, items in cells.items():
        path_kind, prompt, think, condition, path = CELLS[name]
        out["cells"][name] = {"path": path_kind, "prompt": prompt, "think": think, "condition_check": condition,
                              "source": str(Path(path).relative_to(ROOT)), **summary(items)}
    for a, b, label in PAIRS:
        if a in cells and b in cells:
            out["pairs"][f"{a}→{b}"] = {"condition": label, **transition(cells[a], cells[b])}
    for name in ("HF", "HFcc"):
        if name in cells:
            mine = sorted(k for k, i in cells[name].items() if i["grounding_ok"])
            out[f"{name}_vs_thor_committed_base"] = {
                "thor_base_count": len(thor_base), "this_run_count": len(mine),
                "both": len(set(mine) & set(thor_base)),
                "thor_only": sorted(set(thor_base) - set(mine)), "this_run_only": sorted(set(mine) - set(thor_base))}
    out["items"] = cells
    target = HERE / "comparison.json"
    target.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    brief = {k: v for k, v in out.items() if k != "items"}
    print(json.dumps(brief, ensure_ascii=False, indent=1)[:20000])


if __name__ == "__main__":
    main()
