"""격리 확인 실험 분석(RUN_PLAN.md 4절, 모델 호출 없음). 판정 기준은 AUDIT.md 4절 그대로다.

    python evaluation/partial_grounding/resident_isolation/analyze.py   # -> result.json

같은 문항·같은 seed끼리 비교한다.
- 사전 판정 항목(AUDIT 4절): 첫 계획 응답 원문(content)과 thinking 길이가 같은가 → `first_same`.
- 보조: 모든 호출의 응답·thinking 원문, 최종 grounding, 채점 범주, error code, Tool 호출(이름·인자).
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PAIRS = [("B", "Bp"), ("C", "Cp"), ("B", "A"), ("C", "A"), ("Bp", "A"), ("Cp", "A"), ("B", "C")]


def load(cell):
    path = HERE / "raw" / f"{cell}.json"
    if not path.exists():
        return None
    return {r["id"]: r for r in json.loads(path.read_text(encoding="utf-8"))["rows"]}


def view(row):
    calls = row.get("llm_calls") or []
    first = calls[0] if calls else {}
    return {
        "first_content": first.get("content"), "first_thinking_chars": first.get("thinking_chars"),
        "all_content": [c.get("content") for c in calls], "all_thinking": [c.get("thinking") for c in calls],
        "grounding": json.dumps(row.get("grounding"), ensure_ascii=False, sort_keys=True),
        "category": row.get("category"), "error_code": row.get("error_code"),
        "tool_calls": json.dumps([[c.get("tool"), c.get("args")] for c in row.get("calls") or []],
                                 ensure_ascii=False, sort_keys=True),
        "reset_ok": row.get("reset_ok"),
    }


def compare(a, b):
    out = {"items": 0, "first_same": 0, "all_content_same": 0, "all_thinking_same": 0, "grounding_same": 0,
           "category_same": 0, "error_code_same": 0, "tool_calls_same": 0, "differs": {}}
    for item in a:
        if item not in b:
            continue
        x, y = view(a[item]), view(b[item])
        out["items"] += 1
        first = x["first_content"] == y["first_content"] and x["first_thinking_chars"] == y["first_thinking_chars"]
        checks = {"first_same": first, "all_content_same": x["all_content"] == y["all_content"],
                  "all_thinking_same": x["all_thinking"] == y["all_thinking"],
                  "grounding_same": x["grounding"] == y["grounding"], "category_same": x["category"] == y["category"],
                  "error_code_same": x["error_code"] == y["error_code"], "tool_calls_same": x["tool_calls"] == y["tool_calls"]}
        for k, v in checks.items():
            out[k] += v
        if not all(checks.values()):
            out["differs"][item] = {k: v for k, v in checks.items() if not v} | {
                "category": [x["category"], y["category"]], "error_code": [x["error_code"], y["error_code"]]}
    return out


def main():
    result = {"note": "판정 기준은 AUDIT.md 4절. first_same이 사전 판정 항목이다."}
    for mode in ("greedy", "sample"):
        cells = {c: load(f"{c}_{mode}") for c in ("A", "B", "Bp", "C", "Cp")}
        result[mode] = {"cells_present": [c for c, v in cells.items() if v is not None],
                        "pairs": {f"{x}_vs_{y}": compare(cells[x], cells[y]) for x, y in PAIRS
                                  if cells[x] is not None and cells[y] is not None},
                        "reset_ok": {c: [r.get("reset_ok") for r in v.values()].count(True) for c, v in cells.items() if v},
                        "categories": {c: sorted(r["category"] for r in v.values()) for c, v in cells.items() if v}}
    g, s = result["greedy"]["pairs"], result["sample"]["pairs"]

    def n(p, key):
        return p.get(key, {}).get("first_same")
    bb = (n(g, "B_vs_Bp"), n(s, "B_vs_Bp"))
    ba = (n(g, "B_vs_A"), n(s, "B_vs_A"))
    if bb == (10, 10):
        verdict = "1: 문항 격리 성립" + (" + 2: 이전 unload_per_question 기록과 직접 비교 가능" if ba == (10, 10)
                                      else " (3: B ≠ A, 이전 기록과는 따로 비교)")
    else:
        verdict = "4: B ≠ B' — resident_isolated를 쓰지 않는다(보고하고 멈춤)"
    result["verdict"] = {"B_vs_Bp_first_same(greedy,sample)": bb, "B_vs_A_first_same(greedy,sample)": ba,
                         "C_vs_Cp_first_same(greedy,sample)": (n(g, "C_vs_Cp"), n(s, "C_vs_Cp")), "rule": verdict}
    residency = HERE / "resident" / "residency.json"
    warm = HERE / "resident" / "warmup.json"
    if residency.exists():
        r = json.loads(residency.read_text(encoding="utf-8"))
        result["residency"] = {k: r.get(k) for k in ("model_loaded_at_start", "unload_events", "reload_events",
                                                      "container_restart", "runner_pids_seen", "polls", "started_at",
                                                      "finished_at", "ok")}
    if warm.exists():
        w = json.loads(warm.read_text(encoding="utf-8"))
        result["warmup"] = {"calls": len(w.get("calls", [])), "rates": [c.get("tok_s") for c in w.get("calls", [])],
                            "model_loaded_at": w.get("model_loaded_at"), "ok": w.get("ok")}
    (HERE / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"verdict": result["verdict"], "residency": result.get("residency"), "warmup": result.get("warmup")},
                     ensure_ascii=False, indent=1))
    for mode in ("greedy", "sample"):
        for k, v in result[mode]["pairs"].items():
            print(mode, k, {kk: vv for kk, vv in v.items() if kk != "differs"})


if __name__ == "__main__":
    main()
