# -*- coding: utf-8 -*-
"""pilot_009 C3 진단(판정 아님, PLAN_009 4절에서 결과 전에 정의). 모델 호출 없음. ``gates/spec_p9.json``의 셀을 읽는다. ``pilot_008/analysis/diag_p8.py``와 같은 방식.

    hfvenv/bin/python sft_dpo_inventory/pilot_009/analysis/diag_p9.py   # -> analysis/diag_p9.json

1. 거부 경로: refusal_dev v2 거부 90 표본의 경로 M(UNSUPPORTED_QUESTION)·P·C — P9·B2 F·P8·base.
2. 범주별 올바른 거부율(rd_metric·bucket·entity·forecast·mode·domain): arm 평균과 seed별.
3. seed 간 퍼짐: seed별 올바른 거부율의 최소·최대·표준편차(P9·P8·B2 F).
4. thinking 안 지시문 인용·"결론"류 문장: 표본 원문(첫 planner 호출)의 생각(``</think>`` 앞)에
   (a) teacher 지시 금지 절 이름(``build/teacher_filter9.json`` rule의 forbidden 전부)이 있는 비율,
   (b) ``teacher_refusal9.CONCL_LINE``("결론: …")에 맞는 줄이 있는 비율 — 셋 묶음(rdev 거부·rdev 대조·주 셋)·arm별. 원문이 없는 셀은 ``raw_missing``으로 센다.
5. 과잉 거부: 거부 아닌 문항에서 거부로 끝난 표본 — 셋·문항 유형(gold 마지막 tool)·오류 코드별, 표본이 하나라도 있는 문항 수.
6. 정답률 변화 유형: 주 셋 문항별 P9 − B2 F(seed 평균)가 0.25·0.5 이상 바뀐 문항 수를 유형(gold 마지막 tool)별로.
"""
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
P9 = HERE.parent
ROOT = P9.parents[1]
for p in (ROOT, ROOT / "sft_dpo_inventory/pilot_006/gates", ROOT / "sft_dpo_inventory/pilot_006/post"):
    sys.path.insert(0, str(p))
REFUSED = ("unsupported", "needs_clarification")
CONCL_LINE = re.compile(r"^\s*[-*]?\s*\**\s*결론\s*\**\s*[:：]\s*(.+?)\s*$", re.M)  # teacher_refusal9.CONCL_LINE와 같음(줄 단위)


def rows(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))["rows"]


def first_raw(path):
    meta = json.loads((ROOT / path).read_text(encoding="utf-8"))["meta"]
    raw = Path((meta.get("hf") or {}).get("raw_out") or "")
    out = {}
    if raw.exists():
        for line in raw.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            out.setdefault(r["id"], r.get("raw_text") or "")
        return out
    return None


def refused_of(r):
    analysis = sum(1 for x in (r.get("calls") or []) if x.get("tool") != "get_place_scope")
    return r.get("outcome") in REFUSED and analysis == 0


def main():
    import evaluate_vendor100 as EV
    spec = json.loads((P9 / "gates/spec_p9.json").read_text(encoding="utf-8"))
    sets = dict(spec["sets"])
    sets["rdev"] = spec["rdev_gold"]
    gold = {st: {i["id"]: i for i in EV.load_gold(ROOT / g)["items"]} for st, g in sets.items()}
    rmeta = json.loads((ROOT / spec["rdev_meta"]).read_text(encoding="utf-8"))
    rule = json.loads((P9 / "build/teacher_filter9.json").read_text(encoding="utf-8"))["rule"]
    forbidden = sorted({n for v in rule.values() for n in v["forbidden"]})
    arms = {"P9": {s: spec["cells"]["P9"][s] for s in spec["seeds"]}, "B2F": {s: spec["cells"]["B2F"][s] for s in spec["seeds"]},
            "P8": {s: spec["cells"]["P8"][s] for s in spec["seeds"]}, "base": {"base": spec["cells"]["base"]}}
    out = {"forbidden_section_names": forbidden, "routes": {}, "by_gap": {}, "by_gap_per_seed": {}, "seed_spread": {}, "thinking_marks": {}, "over_refusal": {}}
    for arm, by_seed in arms.items():
        routes, gaps, per_seed_gap, seed_rates = Counter(), defaultdict(list), {}, {}
        marks = defaultdict(Counter)
        over = defaultdict(Counter)
        for s, cells in by_seed.items():
            sg, vals = defaultdict(list), []
            for c in cells["rdev"]:
                raw = first_raw(c)
                for r in rows(c):
                    m = rmeta[r["id"]]
                    ref = refused_of(r)
                    grp = "rdev_refusal" if m["refusal"] else "rdev_contrast"
                    if m["refusal"]:
                        sg[m["gap"]].append(float(ref))
                        gaps[m["gap"]].append(float(ref))
                        vals.append(float(ref))
                        if ref:
                            routes["M" if r.get("error_code") == "UNSUPPORTED_QUESTION" else "C" if r.get("outcome") == "needs_clarification" else "P"] += 1
                    if raw is None:
                        marks[grp]["raw_missing"] += 1
                        continue
                    th = raw.get(r["id"], "").split("</think>")[0]
                    marks[grp]["samples"] += 1
                    marks[grp]["section_name"] += any(n in th for n in forbidden)
                    marks[grp]["conclusion_line"] += bool(CONCL_LINE.search(th))
            per_seed_gap[s] = {g: round(100 * float(np.mean(v)), 1) for g, v in sorted(sg.items())}
            seed_rates[s] = round(100 * float(np.mean(vals)), 2) if vals else None
            for st in ("selection_v2", "holdout", "valid98", "aux", "rdev"):
                for c in cells[st]:
                    raw = first_raw(c) if st in ("selection_v2", "holdout") else None
                    for r in rows(c):
                        g = gold[st][r["id"]]
                        if g.get("expected_outcome", "answered") != "answered":
                            continue
                        if st in ("selection_v2", "holdout"):
                            if raw is None:
                                marks["main"]["raw_missing"] += 1
                            else:
                                th = raw.get(r["id"], "").split("</think>")[0]
                                marks["main"]["samples"] += 1
                                marks["main"]["section_name"] += any(n in th for n in forbidden)
                                marks["main"]["conclusion_line"] += bool(CONCL_LINE.search(th))
                        if refused_of(r):
                            typ = g["gold"][-1]["tool"] if g.get("gold") else "?"
                            over["by_set"][st] += 1
                            over["by_tool"][typ] += 1
                            over["by_code"][str(r.get("error_code"))] += 1
                            over["items"][f"{st}:{r['id']}"] += 1
        out["routes"][arm] = dict(routes)
        out["by_gap"][arm] = {g: round(100 * float(np.mean(v)), 1) for g, v in sorted(gaps.items())}
        out["by_gap_per_seed"][arm] = per_seed_gap
        rates = [v for v in seed_rates.values() if v is not None]
        out["seed_spread"][arm] = {"per_seed_pct": seed_rates, "min": min(rates), "max": max(rates), "sd": round(float(np.std(rates, ddof=1)), 2) if len(rates) > 1 else None}
        out["thinking_marks"][arm] = {g: {**dict(c), **({"section_name_pct": round(100 * c["section_name"] / c["samples"], 2),
                                                          "conclusion_line_pct": round(100 * c["conclusion_line"] / c["samples"], 2)} if c["samples"] else {})}
                                      for g, c in marks.items()}
        out["over_refusal"][arm] = {k: dict(v.most_common(12)) for k, v in over.items() if k != "items"}
        out["over_refusal"][arm]["items_with_any"] = len(over["items"])
        out["over_refusal"][arm]["top_items"] = dict(over["items"].most_common(10))
    import robust_scoring
    robust_scoring.patch()
    import compute_gates as CG
    ok = {}
    for arm in ("P9", "B2F"):
        mats = []
        for s in spec["seeds"]:
            items, m, _ = CG.load_arm({st: spec["cells"][arm][s][st] for st in ("selection_v2", "holdout")}, spec["sets"], with_tokens=False)
            mats.append(m["ok"])
        ok[arm] = (items, np.vstack(mats).mean(axis=0))
    items = ok["P9"][0]
    dlt = ok["P9"][1] - ok["B2F"][1]
    typ = {}
    for it in items:
        st, i = it.split("/", 1)
        g = gold[st].get(i)
        typ[it] = (g["gold"][-1]["tool"] if g and g.get("gold") else (g or {}).get("expected_outcome", "?"))
    out["accuracy_change_by_type(P9-B2F)"] = {"gained_ge_0.25": dict(Counter(typ[items[x]] for x in range(len(items)) if dlt[x] >= 0.25)),
                                             "lost_ge_0.25": dict(Counter(typ[items[x]] for x in range(len(items)) if dlt[x] <= -0.25)),
                                             "gained_ge_0.5": dict(Counter(typ[items[x]] for x in range(len(items)) if dlt[x] >= 0.5)),
                                             "lost_ge_0.5": dict(Counter(typ[items[x]] for x in range(len(items)) if dlt[x] <= -0.5)),
                                             "mean_by_type_pp": {t: round(100 * float(np.mean([dlt[x] for x in range(len(items)) if typ[items[x]] == t])), 2)
                                                                 for t in sorted(set(typ.values()))}}
    (HERE / "diag_p9.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("routes", "by_gap", "seed_spread", "thinking_marks")}, ensure_ascii=False, indent=1)[:6000])


if __name__ == "__main__":
    main()
