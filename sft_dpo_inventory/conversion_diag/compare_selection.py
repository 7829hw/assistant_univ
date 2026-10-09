# -*- coding: utf-8 -*-
"""selection_v1 Ollama 진단 셀과 HF 기록을 비교한다(작업 지시 3, 판정 규칙 없음). 모델 호출 없음.

    python sft_dpo_inventory/conversion_diag/compare_selection.py

- Ollama 셀: ``pilot_002/aux_test/compare_aux.py``와 같은 분류 코드(``axes_rows``의 v4 축, ``grounding_v13/report.unacceptable``의
  U1–U4, ``compare_cells.report_class``). grounding_ok는 현재 ``grounding_check``로 다시 채점한다.
- HF 셀(``eval_set.py`` 출력): 호출 기록이 없어 U·조용한 오답은 셀 수 없다. grounding_ok, 결과 분류, 생성 상한, 루프(결정 40-D)만.
- 결정 62(D)의 세 가지 오류 건수(셀마다, 최종 grounding 기준):
  1. dimension_target 누락: gold grounding에 dimension_target이 있는데 최종 grounding에 없음.
  2. 출발·도착 역할 추가·변경: gold와 장소별 od_role이 다름. gold가 같은 장소를 pickup·dropoff 두 개로 적고(옛 표기) 모델이
     그 장소 하나에 both를 적은 경우는 "표기 차이"로 따로 센다.
  3. 실차 통행량 오독: gold가 passage_count + taxi_status occupied인데 측정값을 trip_count로 읽음.
- 한 조건만 다른 쌍의 문항 단위 전이(얻음·잃음 목록, U·조용한 오답의 새로 생김·사라짐).
- 결과: ``selection_comparison.json``. 질문 문장은 넣지 않는다.
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
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_prep_004/loop_filter"))
spec = importlib.util.spec_from_file_location("compare_cells", ROOT / "sft_dpo_inventory/baseline_conditions_001/compare_cells.py")
C = importlib.util.module_from_spec(spec)
spec.loader.exec_module(C)
import evaluate_vendor100 as EV  # noqa: E402
from apply_filter import is_loop, loop_metrics, split_think  # noqa: E402

GOLD = HERE / "selection_gold.yaml"
SEL = ROOT / "sft_dpo_inventory/pilot_002/selection/runs"
HF_CELLS = {"HF-base": ROOT / "sft_dpo_inventory/pilot_prep_005/sets/runs/selection_base.json",
            "HF-final": SEL / "sel_dpo_step144.json"}
OLLAMA_CELLS = {name: HERE / "selection" / f"{name}.json" for name in ("E", "c", "B-conv", "d", "b", "a", "Ollama-final", "e")}
DESC = {"E": "공식 qwen3:8b Q4_K_M + 공식 TEMPLATE", "c": "공식 qwen3:8b Q4_K_M + HF 형식 TEMPLATE",
        "B-conv": "직접 변환 base Q4_K_M + HF 형식 TEMPLATE", "d": "직접 변환 base Q8_0 + HF 형식 TEMPLATE",
        "b": "공식 qwen3:8b + adapter + HF 형식 TEMPLATE(만들지 못함)", "a": "공식 qwen3:8b + adapter + 공식 TEMPLATE(만들지 못함)",
        "Ollama-final": "pilot_002 최종 병합 Q4_K_M + HF 형식 TEMPLATE", "e": "pilot_002 최종 병합 Q8_0 + HF 형식 TEMPLATE",
        "HF-base": "HF BF16 base(HF-E 조건, 기준값 82)", "HF-final": "HF BF16 + pilot_002 최종 adapter(DPO 144, 80)"}
PAIRS = [("E", "c", "TEMPLATE 효과"), ("c", "B-conv", "변환 효과"),
         ("B-conv", "d", "양자화 수준(base)"), ("Ollama-final", "e", "양자화 수준(학습 모델)"),
         ("c", "b", "학습 효과: 공식 가중치 + HF TEMPLATE"), ("E", "a", "학습 효과: 공식 가중치 + 공식 TEMPLATE"),
         ("B-conv", "Ollama-final", "학습 효과: 직접 변환 Q4_K_M"), ("d", "e", "학습 효과: 직접 변환 Q8_0"),
         ("HF-base", "HF-final", "학습 효과: HF BF16"),
         ("HF-base", "d", "참고: HF BF16 ↔ Ollama Q8_0(같은 원본, TEMPLATE 렌더링 같음)"),
         ("HF-final", "e", "참고: HF BF16 ↔ Ollama Q8_0(학습 모델)")]
U_CLASS, SILENT = "용납할 수 없는 실패", "조용한 오답(U 아님)"


def view(g):
    if not g:
        return None
    cs = g.get("concepts") or []
    places = sorted(((c.get("value") or {}).get("name", "") if isinstance(c.get("value"), dict) else str(c.get("value")),
                     (c.get("attributes") or {}).get("od_role") or "-")
                    for c in cs if c.get("concept") == "LOCATION" and c.get("role") != "MEASURE")
    measure = next((c.get("subtype") for c in cs if c.get("role") == "MEASURE"), None)
    return {"measure": measure, "places": places, "factors": g.get("factors") or {}}


def norm(name):
    return name.replace(" ", "")


def decision_d(gold_item, grounding):
    gv, mv = view(EV.gold_grounding(gold_item)), view(grounding)
    out = {"dt_missing": False, "role_error": False, "role_notation": False, "occupied_misread": False}
    if gv is None or mv is None:
        return out
    if gv["factors"].get("dimension_target") and not mv["factors"].get("dimension_target"):
        out["dt_missing"] = True
    # 역할은 장소 이름 표기(region 붙임 등)와 무관하게 역할 목록으로 비교한다.
    g = sorted(r for _, r in gv["places"])
    m = sorted(r for _, r in mv["places"])
    if g != m and mv["places"]:
        names = Counter(norm(n) for n, _ in gv["places"])
        old_pair = any(c >= 2 and {r for n2, r in gv["places"] if norm(n2) == n} == {"pickup", "dropoff"} for n, c in names.items())
        if old_pair and sorted([r for r in g if r not in ("pickup", "dropoff")] + ["both"]) == m:
            out["role_notation"] = True
        elif len(m) == len(g) or any(r not in g for r in m):
            out["role_error"] = True
    if gv["measure"] == "passage_count" and gv["factors"].get("taxi_status") == "occupied" and mv["measure"] == "trip_count":
        out["occupied_misread"] = True
    return out


def load_hf(path, gold):
    res = json.loads(path.read_text(encoding="utf-8"))
    raw = Path(res["meta"]["raw_out"])
    loops = Counter()
    if raw.exists():
        for line in raw.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            m = loop_metrics(split_think(r["raw_text"])[0])
            if (is_loop(m) if m else ["empty_thinking"]):
                loops[r["id"]] += 1
    out = {}
    for r in res["rows"]:
        regraded, _ = EV.grounding_check(gold[r["id"]], r.get("grounding"))
        out[r["id"]] = {"grounding_ok": bool(regraded), "report_class": None, "seconds": r["seconds"],
                        "outcome": f"{r['outcome']}:{r['error_code']}", "vendor_style": r["vendor_style_category"],
                        "truncated": sum(d == "length" for d in r["done_reasons"]), "loop_calls": loops.get(r["id"], 0),
                        "thinking_first": r.get("thinking_chars_first_plan"), "calls": r["model_calls"],
                        **decision_d(gold[r["id"]], r.get("grounding"))}
    return out, res["meta"]


def load_ollama(path, gold):
    meta, rows = EV.axes_rows(str(path))
    source = {r["id"]: r for r in json.loads(path.read_text(encoding="utf-8"))["rows"]}
    out = {}
    for row in rows:
        key, src = row["id"], source[row["id"]]
        flags = C.R.unacceptable(key, row, src)
        regraded, _ = EV.grounding_check(gold[key], src.get("grounding"))
        calls = src.get("llm_calls") or []
        out[key] = {"grounding_ok": bool(regraded), "grounding_ok_recorded": src.get("grounding_ok"),
                    "report_class": C.report_class(row, flags), "u_flags": flags, "v4": row["v4"],
                    "seconds": (row["cost"]["total_ms"] or 0) / 1000,
                    "outcome": f"{src.get('outcome')}:{src.get('error_code')}", "vendor_style": src.get("category"),
                    "truncated": sum((c.get("done_reason") == "length") for c in calls), "loop_calls": None,
                    "thinking_first": next((c.get("thinking_chars") for c in calls if c.get("kind") == "plan"), None),
                    "calls": len(calls), **decision_d(gold[key], src.get("grounding"))}
    return out, meta


def summary(items, meta, path):
    classes = Counter(i["report_class"] for i in items.values()) if all(i["report_class"] for i in items.values()) else None
    th = [i["thinking_first"] for i in items.values() if i["thinking_first"] is not None]
    return {"source": str(path.relative_to(ROOT)), "items": len(items),
            "grounding_ok": sum(i["grounding_ok"] for i in items.values()),
            "report_class": dict(classes) if classes else "기록 형식에 없음(HF eval_set 출력)",
            "U": classes.get(U_CLASS, 0) if classes else None, "silent": classes.get(SILENT, 0) if classes else None,
            "U_items": sorted(k for k, i in items.items() if i["report_class"] == U_CLASS),
            "silent_items": sorted(k for k, i in items.items() if i["report_class"] == SILENT),
            "outcomes": dict(Counter(i["outcome"] for i in items.values())),
            "latency_median_s": round(statistics.median(i["seconds"] for i in items.values()), 2),
            "latency_p90_s": round(sorted(i["seconds"] for i in items.values())[int(0.9 * (len(items) - 1))], 2),
            "model_calls": sum(i["calls"] for i in items.values()),
            "truncated_calls": sum(i["truncated"] for i in items.values()),
            "truncated_items": sorted(k for k, i in items.items() if i["truncated"]),
            "loop_calls": (sum(i["loop_calls"] for i in items.values())
                           if all(i["loop_calls"] is not None for i in items.values()) else "기록 없음(thinking 원문 미저장)"),
            "first_plan_thinking_chars_median": statistics.median(th) if th else None,
            "decision_d": {k: sorted(i for i, v in items.items() if v[k])
                           for k in ("dt_missing", "role_error", "role_notation", "occupied_misread")},
            "model": meta.get("model"), "adapter": meta.get("adapter"), "ollama_version": meta.get("ollama_version")}


def pair(A, B):
    keys = sorted(set(A) & set(B))
    gained = [k for k in keys if not A[k]["grounding_ok"] and B[k]["grounding_ok"]]
    lost = [k for k in keys if A[k]["grounding_ok"] and not B[k]["grounding_ok"]]
    out = {"common": len(keys), "grounding_ok": [sum(A[k]["grounding_ok"] for k in keys), sum(B[k]["grounding_ok"] for k in keys)],
           "b_gained": len(gained), "c_lost": len(lost), "gained": gained, "lost": lost,
           "outcome_changed": sum(A[k]["outcome"] != B[k]["outcome"] for k in keys)}
    if all(A[k]["report_class"] and B[k]["report_class"] for k in keys):
        for name, cls in (("U", U_CLASS), ("silent", SILENT)):
            a = {k for k in keys if A[k]["report_class"] == cls}
            b = {k for k in keys if B[k]["report_class"] == cls}
            out[name] = [len(a), len(b)]
            out[f"{name}_new"], out[f"{name}_gone"] = sorted(b - a), sorted(a - b)
    for key in ("dt_missing", "role_error", "occupied_misread"):
        out[key] = [sum(A[k][key] for k in keys), sum(B[k][key] for k in keys)]
    la = statistics.median(A[k]["seconds"] for k in keys)
    lb = statistics.median(B[k]["seconds"] for k in keys)
    out["latency_median_s"] = [round(la, 2), round(lb, 2)]
    return out


def main():
    gold = {i["id"]: i for i in EV.load_gold(GOLD)["items"]}
    cells, out = {}, {"note": "진단용. 판정 규칙 없음(작업 지시 3). 셀마다 한 번 측정.", "cells": {}, "pairs": {}}
    for name, path in HF_CELLS.items():
        items, meta = load_hf(path, gold)
        cells[name] = items
        out["cells"][name] = {"desc": DESC[name], **summary(items, meta, path)}
    for name, path in OLLAMA_CELLS.items():
        if not path.exists():
            out["cells"][name] = {"desc": DESC[name], "measured": False}
            continue
        items, meta = load_ollama(path, gold)
        cells[name] = items
        out["cells"][name] = {"desc": DESC[name], **summary(items, meta, path)}
        out["cells"][name]["grounding_ok_recorded_differs"] = sorted(
            k for k, i in items.items() if i["grounding_ok_recorded"] is not None and bool(i["grounding_ok_recorded"]) != i["grounding_ok"])
    for a, b, label in PAIRS:
        if a in cells and b in cells:
            out["pairs"][label] = {"pair": f"{a}→{b}", **pair(cells[a], cells[b])}
        else:
            out["pairs"][label] = {"pair": f"{a}→{b}", "skipped": "셀 없음(" + ", ".join(x for x in (a, b) if x not in cells) + ")"}
    out["items"] = {name: items for name, items in cells.items()}
    (HERE / "selection_comparison.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for name, c in out["cells"].items():
        if c.get("measured") is False:
            print(name, "not measured")
            continue
        print(name, c["grounding_ok"], "U", c["U"], "silent", c["silent"], "lat", c["latency_median_s"], "trunc", c["truncated_calls"],
              "loops", c["loop_calls"], {k: len(v) for k, v in c["decision_d"].items()})
    for label, p in out["pairs"].items():
        print(label, p["pair"], p.get("skipped") or (p["grounding_ok"], "b", p["b_gained"], "c", p["c_lost"], "U", p.get("U"),
                                                      "silent", p.get("silent")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
