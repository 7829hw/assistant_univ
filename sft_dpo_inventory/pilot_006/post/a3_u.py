# -*- coding: utf-8 -*-
"""A3: P의 U(용납할 수 없는 실패) 증가를 원인 범주로 나눈다(F·base·R2와 비교, seed별). 모델 호출 없음.

    hfvenv/bin/python a3_u.py   # -> a3_u.json

범주(한 표본이 여러 범주에 들 수 있음; 우선순위 순으로 대표 범주 하나도 센다):
- structure: 첫 응답 오류 코드가 구조 코드(``compute_gates.STRUCT_CODES``·INVALID_*) — U와 겹치는지.
- repair: 계획 호출이 2회 이상(repair가 U로 끝남).
- refusal: 거부·확인 요청을 기대했는데 답함(gold expected_outcome ≠ answered).
- place_dropped: gold의 장소(get_place_scope name) 수보다 모델 첫 응답 JSON의 장소(place·scope concept) 수가 적다 — 모델이 장소를 빠뜨림(Partial 보완이 채울 수 없음).
- od_role: U2:scope_pickup/scope_dropoff(장소는 있으나 승차·하차 끝이 틀림).
- dt: U2:dimension_target.
- filter: U4·U1(조건 값 틀림/추가).
- measure_tool: U3(도구·측정 틀림).
- completion: Partial 보완 단계가 바꾼 결과가 U(``condition_corrections``·``condition_actions``가 비어 있지 않은 U 표본) — 보완 실패 후보.
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
import itemdata as I  # noqa: E402

MODELS = ("base", "R2", "F43e1", "F1016e1", "P43e1", "P1016e1")
CELLS = {"F43e1": "f43_e1", "F1016e1": "f1016_e1", "P43e1": "p43_e1", "P1016e1": "p1016_e1"}
ORDER = ("structure", "repair", "refusal", "place_dropped", "od_role", "dt", "filter", "measure_tool", "other")


def gold_places(g):
    return sum(1 for c in g.get("gold") or [] if c.get("tool") == "get_place_scope")


def model_places(content):
    try:
        j = json.loads(content)
    except Exception:  # noqa: BLE001
        return None
    cs = j.get("concepts") or []
    return sum(1 for c in cs if isinstance(c, dict) and c.get("subtype") in ("place", "scope"))


def cell_row_index():
    """학습 모델 셀의 원 행(첫 응답 content·보완 기록)."""
    idx = {}
    for m, pre in CELLS.items():
        for st in ("sel", "holdout"):
            for k in range(1, 5):
                p = ROOT / f"sft_dpo_inventory/pilot_006/cells/{pre}_{st}_s{k}.json"
                for r in json.loads(p.read_text(encoding="utf-8"))["rows"]:
                    idx[(m, st, r["id"], k)] = r
    return idx


def main():
    rows = [json.loads(l) for l in (HERE / "samples_s3.jsonl").read_text(encoding="utf-8").splitlines()]
    idx = cell_row_index()
    out = {"sets": "selection_v2(sel) + holdout; R2는 selection_v2만(holdout 셀 없음)", "models": {}}
    for m in MODELS:
        mr = [r for r in rows if r["model"] == m and r["set"] in ("sel", "holdout")]
        n = len(mr)
        U = [r for r in mr if r["U"]]
        cats, primary, by_group, compl = Counter(), Counter(), Counter(), 0
        for r in U:
            g = I.gold(r["set"])[r["id"]]
            f = r["u_flags"] or []
            raw = idx.get((m, r["set"], r["id"], r["k"]))
            content = (raw or {}).get("llm_calls", [{}])[0].get("content", "") if raw else ""
            mp = model_places(content) if raw else None
            c = {"structure": r["struct"], "repair": r["repair"], "refusal": g.get("expected_outcome") != "answered",
                 "place_dropped": mp is not None and mp < gold_places(g),
                 "od_role": any(x in f for x in ("U2:scope_pickup", "U2:scope_dropoff")), "dt": "U2:dimension_target" in f,
                 "filter": any(x.startswith(("U4", "U1")) for x in f), "measure_tool": any(x.startswith("U3") for x in f)}
            for k, v in c.items():
                if v:
                    cats[k] += 1
            primary[next((k for k in ORDER if c.get(k)), "other")] += 1
            if raw and (raw.get("condition_corrections") or raw.get("condition_actions")):
                compl += 1
            by_group["holdout" if r["set"] == "holdout" else r["id"].split("/")[0]] += 1
        out["models"][m] = {"samples": n, "U": len(U), "U_pct": round(100 * len(U) / n, 2),
                            "categories_pct_of_samples": {k: round(100 * v / n, 2) for k, v in sorted(cats.items())},
                            "primary": dict(primary), "U_with_condition_corrections_or_actions": compl if m in CELLS else None,
                            "U_by_group": dict(by_group), "U_items_top": Counter(r["id"] for r in U).most_common(8)}
    f = {k: (out["models"]["F43e1"]["primary"].get(k, 0) + out["models"]["F1016e1"]["primary"].get(k, 0)) for k in ORDER}
    p = {k: (out["models"]["P43e1"]["primary"].get(k, 0) + out["models"]["P1016e1"]["primary"].get(k, 0)) for k in ORDER}
    out["P_minus_F_primary_counts(two seeds, 1208 samples each)"] = {k: p[k] - f[k] for k in ORDER if p[k] or f[k]}
    (HERE / "a3_u.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for m, v in out["models"].items():
        print(m, v["U_pct"], v["primary"], v["U_with_condition_corrections_or_actions"], v["U_by_group"])
    print(out["P_minus_F_primary_counts(two seeds, 1208 samples each)"])


if __name__ == "__main__":
    main()
