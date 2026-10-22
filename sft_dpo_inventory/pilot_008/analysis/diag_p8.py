# -*- coding: utf-8 -*-
"""pilot_008 C3 진단(판정 아님). 모델 호출 없음. ``gates/spec_p8.json``의 셀을 읽는다.

    hfvenv/bin/python sft_dpo_inventory/pilot_008/analysis/diag_p8.py   # -> analysis/diag_p8.json

1. 거부 경로: refusal_dev 거부 문항 표본의 경로 M(UNSUPPORTED_QUESTION)·P·C — P8·B2 F·base. 모델 거부 출력이 생겼는지(원문 응답 JSON에 unsupported).
2. 범주별 올바른 거부율(rd_metric·bucket·entity·forecast·mode·domain).
3. 과잉 거부: 거부 아닌 문항 중 P8에서 거부로 끝난 표본이 있는 문항 — 셋·문항 유형(gold 마지막 tool)·오류 코드별, B2 F와 비교.
4. S-1·S-2 기여(가능한 만큼): RC6 S-1 표본이 있던 batch011 범주(지표·도메인 밖)와 S-2만 있던 범주(묶음·개별·예측·교통수단)의 refusal_dev 올바른 거부율 변화(P8 − B2 F);
   P8 거부 표본의 thinking에 S-2 근거 문형의 말("택시 운행 기록", "계약", "묶을 수 있는 단위" 등)이 나타나는 비율(S-2 흔적), base·B2 F와 비교.
5. 정답률 변화 유형: 주 셋 문항별 P8 − B2 F(seed 평균)가 ±0.5 이상 바뀐 문항 수를 유형(gold 마지막 tool)별로.
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
P8 = HERE.parent
ROOT = P8.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_006/gates"))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_006/post"))
REFUSED = ("unsupported", "needs_clarification")
S2_MARKS = ("택시 운행 기록", "묶을 수 있는 단위", "기간을 묶을", "개별 차량", "아직 오지 않은", "다른 교통수단", "분석 범위 밖", "다룰 수 있는 값")
S1_GAPS = {"metric", "domain"}


def rows(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))["rows"]


def first_thinking(path):
    meta = json.loads((ROOT / path).read_text(encoding="utf-8"))["meta"]
    raw = Path((meta.get("hf") or {}).get("raw_out") or "")
    out = {}
    if raw.exists():
        for line in raw.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            out.setdefault(r["id"], r.get("raw_text") or "")
    return out


def main():
    import evaluate_vendor100 as EV
    spec = json.loads((P8 / "gates/spec_p8.json").read_text(encoding="utf-8"))
    sets = dict(spec["sets"])
    sets["rdev"] = spec["rdev_gold"]
    gold = {st: {i["id"]: i for i in EV.load_gold(ROOT / g)["items"]} for st, g in sets.items()}
    rmeta = json.loads((ROOT / spec["rdev_meta"]).read_text(encoding="utf-8"))
    groups = {"P8": [spec["cells"]["P8"][s] for s in spec["seeds"]], "B2F": [spec["cells"]["B2F"][s] for s in spec["seeds"]], "base": [spec["cells"]["base"]]}
    out = {"routes": {}, "by_gap": {}, "s2_trace_in_thinking": {}, "over_refusal": {}, "model_refusal_output": {}}
    for arm, cl in groups.items():
        routes, gap_vals, s2 = Counter(), defaultdict(list), Counter()
        over = defaultdict(Counter)
        mr = Counter()
        for cells in cl:
            for c in cells["rdev"]:
                th = first_thinking(c)
                for r in rows(c):
                    m = rmeta[r["id"]]
                    analysis = sum(1 for x in (r.get("calls") or []) if x.get("tool") != "get_place_scope")
                    refused = r.get("outcome") in REFUSED and analysis == 0
                    if m["refusal"]:
                        gap_vals[m["gap"].replace("rd_", "")].append(float(refused))
                        if refused:
                            routes["M" if r.get("error_code") == "UNSUPPORTED_QUESTION" else "C" if r.get("outcome") == "needs_clarification" else "P"] += 1
                            t = th.get(r["id"], "").split("</think>")[0]
                            s2["refusal_samples"] += 1
                            s2["with_s2_marks"] += any(k in t for k in S2_MARKS)
                        tail = th.get(r["id"], "").split("</think>")[-1]
                        mr["refusal_items_samples"] += 1
                        mr["unsupported_in_output"] += '"unsupported"' in tail
            for st in ("selection_v2", "holdout", "valid98", "aux", "rdev"):
                for c in cells[st]:
                    for r in rows(c):
                        g = gold[st][r["id"]]
                        if g.get("expected_outcome", "answered") != "answered":
                            continue
                        analysis = sum(1 for x in (r.get("calls") or []) if x.get("tool") != "get_place_scope")
                        if r.get("outcome") in REFUSED and analysis == 0:
                            typ = g["gold"][-1]["tool"] if g.get("gold") else "?"
                            over["by_set"][st] += 1
                            over["by_tool"][typ] += 1
                            over["by_code"][str(r.get("error_code"))] += 1
                            over["items"][f"{st}:{r['id']}"] += 1
        out["routes"][arm] = dict(routes)
        out["by_gap"][arm] = {g: round(100 * float(np.mean(v)), 1) for g, v in sorted(gap_vals.items())}
        out["s2_trace_in_thinking"][arm] = dict(s2)
        out["model_refusal_output"][arm] = dict(mr)
        out["over_refusal"][arm] = {k: dict(v.most_common(12)) for k, v in over.items() if k != "items"}
        out["over_refusal"][arm]["items_with_any"] = len(over["items"])
    d = {g: round(out["by_gap"]["P8"].get(g, 0) - out["by_gap"]["B2F"].get(g, 0), 1) for g in out["by_gap"]["P8"]}
    out["s1_vs_s2_categories"] = {"P8_minus_B2F_pp_by_gap": d,
                                  "s1_categories_mean": round(float(np.mean([d[g] for g in d if g in S1_GAPS])), 1),
                                  "s2_only_categories_mean": round(float(np.mean([d[g] for g in d if g not in S1_GAPS])), 1),
                                  "note": "RC6 S-1 표본은 batch011 지표(1질문)·도메인 밖(4질문)에서만 생김; 나머지 범주는 S-2만"}
    # 5. 정답률 변화 유형(주 셋)
    import robust_scoring
    robust_scoring.patch()
    import compute_gates as CG
    ok = {}
    for arm in ("P8", "B2F"):
        mats = []
        for s in spec["seeds"]:
            items, m, _ = CG.load_arm({st: spec["cells"][arm][s][st] for st in ("selection_v2", "holdout")}, spec["sets"], with_tokens=False)
            mats.append(m["ok"])
        ok[arm] = (items, np.vstack(mats).mean(axis=0))
    items = ok["P8"][0]
    dlt = ok["P8"][1] - ok["B2F"][1]
    typ = {}
    for it in items:
        st, i = it.split(":", 1) if ":" in it else ("selection_v2", it)
        g = gold.get(st, gold["selection_v2"]).get(i) or gold["holdout"].get(i) or gold["selection_v2"].get(i)
        typ[it] = (g["gold"][-1]["tool"] if g and g.get("gold") else (g or {}).get("expected_outcome", "?"))
    out["accuracy_change_by_type"] = {"gained_ge_0.5": dict(Counter(typ[items[x]] for x in range(len(items)) if dlt[x] >= 0.5)),
                                      "lost_ge_0.5": dict(Counter(typ[items[x]] for x in range(len(items)) if dlt[x] <= -0.5)),
                                      "mean_by_type_pp": {t: round(100 * float(np.mean([dlt[x] for x in range(len(items)) if typ[items[x]] == t])), 2) for t in sorted(set(typ.values()))}}
    (HERE / "diag_p8.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1)[:5000])


if __name__ == "__main__":
    main()
