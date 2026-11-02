# -*- coding: utf-8 -*-
"""ablation_011 과잉 거부 몰림 교차표(결정 261, PLAN_A11 6절 5). 진단, 판정 아님. 모델 호출 없음.

거부가 아닌 문항(``expected_outcome: answered``)의 표본마다 정답 호출로 칸을 정하고, 칸마다 거부 표본 수 / 표본 수를 센다.
refused = ``compute_p9.sample_values``(결과 unsupported·needs_clarification이고 분석 tool 실행 없음; pilot_010 선택 도구와 같음).

- tool: 정답 호출 중 ``get_place_scope``가 아닌 첫 호출의 tool(없으면 ``none``).
- 시간 단위(그 분석 호출 인자): ``bucket``이 있으면 ``bucket:<값>``(``rollup``이 있으면 ``+rollup``). 없으면 ``date``로
  일(YYYYMMDD 하나·yesterday·today), 주(7일 범위·last_week·this_week), 월(한 달 1일–말일 범위·last_month·this_month), 연(1월 1일–12월 31일·this_year·last_year),
  기간(그 밖의 범위), 요일유형(weekend·weekday·holiday), 없음(date 없음), 기타(그 밖의 값).
- 지역 유형(정답 ``get_place_scope``의 ``name``): POI(``include_vicinity`` true이거나 POI_NAMES), 시도(SIDO, 특별시·광역시·특별자치시·도·특별자치도 붙어도 됨),
  시군구(구·군·시로 끝남), 읍면동(동·읍·면·가로 끝남), POI(그 밖), 없음(장소 호출 없음). 장소 호출이 둘 이상이면 가장 좁은 것(POI > 읍면동 > 시군구 > 시도).
  POI_NAMES = 광안리·동성로·동대구역·어린이대공원(E1·client_test_10000 정답의 장소명 22종 중 접미사로는 읍면동·시군구처럼 보이는 POI; ``리``는 읍면동 접미사로 쓰지 않음).

    runtime/envs/hf/bin/python sft_dpo_inventory/ablation_011/analysis/xtab_a11.py --existing   # -> analysis/xtab_existing.json (client_test_10000·pilot_010 S 셀)
    (새 셀은 analyze_a11.py가 ``xtab``을 불러 쓴다)
"""
import argparse
import calendar
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
for p in (ROOT, ROOT / "sft_dpo_inventory/pilot_009/gates"):
    sys.path.insert(0, str(p))

SIDO = {"서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종", "경기", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주",
        "충청북", "충청남", "전라북", "전라남", "경상북", "경상남"}
SIDO_SUFFIX = ("특별자치시", "특별자치도", "특별시", "광역시", "도")
POI_NAMES = {"광안리", "동성로", "동대구역", "어린이대공원"}
RANK = {"없음": 0, "시도": 1, "시군구": 2, "읍면동": 3, "POI": 4}


def region_one(args):
    name = (args.get("name") or "").strip()
    if args.get("include_vicinity") is True or name in POI_NAMES:
        return "POI"
    base = name
    for s in SIDO_SUFFIX:
        if base.endswith(s) and base[: -len(s)] in SIDO:
            base = base[: -len(s)]
            break
    if base in SIDO:
        return "시도"
    if name.endswith(("구", "군", "시")):
        return "시군구"
    if name.endswith(("동", "읍", "면", "가")):
        return "읍면동"
    return "POI"


def region_type(calls):
    rs = [region_one(c.get("args") or {}) for c in calls if c.get("tool") == "get_place_scope"]
    return max(rs, key=RANK.get) if rs else "없음"


def _ymd(s):
    return date(int(s[:4]), int(s[4:6]), int(s[6:8]))


def time_unit(args):
    if args.get("bucket"):
        return f"bucket:{args['bucket']}" + ("+rollup" if args.get("rollup") else "")
    d = args.get("date")
    if d is None:
        return "없음"
    d = str(d)
    if re.fullmatch(r"\d{8}", d) or d in ("yesterday", "today"):
        return "일"
    if d in ("last_week", "this_week"):
        return "주"
    if d in ("last_month", "this_month"):
        return "월"
    if d in ("last_year", "this_year"):
        return "연"
    if d in ("weekend", "weekday", "holiday"):
        return "요일유형"
    m = re.fullmatch(r"(\d{8})-(\d{8})", d)
    if m:
        a, b = _ymd(m.group(1)), _ymd(m.group(2))
        n = (b - a).days + 1
        if n == 7:
            return "주"
        if a.day == 1 and a.year == b.year and a.month == b.month and b.day == calendar.monthrange(b.year, b.month)[1]:
            return "월"
        if a.month == 1 and a.day == 1 and b.month == 12 and b.day == 31 and a.year == b.year:
            return "연"
        return "기간"
    return "기타"


def classify(calls):
    calls = calls or []
    an = next((c for c in calls if c.get("tool") != "get_place_scope"), None)
    tool = an["tool"] if an else "none"
    return tool, time_unit((an or {}).get("args") or {}), region_type(calls)


def xtab(cells_by_set, gold_by_set):
    """cells_by_set: {set: [cell 경로(ROOT 기준)]}, gold_by_set: {set: {id: item}} → {"cells": {(tool, time, region): [refused, n]}, "axes": ...}."""
    import compute_p9 as C9
    tab = defaultdict(lambda: [0, 0])
    for st, cells in cells_by_set.items():
        for c in cells:
            for i, v in C9.sample_values(c).items():
                it = gold_by_set[st][i]
                if it.get("expected_outcome", "answered") != "answered":
                    continue
                k = classify(it.get("gold"))
                tab[k][0] += int(v["refused"])
                tab[k][1] += 1
    return summarize(tab)


def summarize(tab):
    axes = {}
    for ax, name in enumerate(("tool", "time", "region")):
        agg = defaultdict(lambda: [0, 0])
        for k, (r, n) in tab.items():
            agg[k[ax]][0] += r
            agg[k[ax]][1] += n
        axes[name] = {a: {"refused": r, "samples": n, "pct": round(100 * r / n, 2) if n else None} for a, (r, n) in sorted(agg.items(), key=lambda x: -x[1][0])}
    tot_r, tot_n = sum(v[0] for v in tab.values()), sum(v[1] for v in tab.values())
    cells = [{"tool": k[0], "time": k[1], "region": k[2], "refused": r, "samples": n, "pct": round(100 * r / n, 2) if n else None,
              "share_of_refused_pct": round(100 * r / tot_r, 2) if tot_r else None} for k, (r, n) in sorted(tab.items(), key=lambda x: (-x[1][0], -x[1][1]))]
    return {"refused": tot_r, "samples": tot_n, "pct": round(100 * tot_r / tot_n, 3) if tot_n else None, "axes": axes, "cells": cells}


def gold_map(path):
    import evaluate_vendor100 as EV
    return {i["id"]: i for i in EV.load_gold(ROOT / path)["items"]}


def existing():
    out = {"note": "진단, 판정 아님. 기존 셀(새 측정 아님).", "definition": __doc__.split("    runtime/")[0].strip()}
    ct = "sft_dpo_inventory/client_test_10000"
    g10k = {"ct": gold_map(f"{ct}/qa_test_10000.yaml")}
    for s in ("o43", "o1016", "o7"):
        out[f"client10k_V4_{s}"] = xtab({"ct": [f"{ct}/cells/ct10k_v4_{s}_c{c}_s1.json" for c in range(1, 6)]}, g10k)
    out["client10k_V4_3seed"] = xtab({"ct": [f"{ct}/cells/ct10k_v4_{s}_c{c}_s1.json" for s in ("o43", "o1016", "o7") for c in range(1, 6)]}, g10k)
    out["client10k_base_k1-3"] = xtab({"ct": [f"{ct}/cells/ct10k_base_c{c}_s{k}.json" for k in (1, 2, 3) for c in range(1, 6)]}, g10k)
    spec = json.loads((ROOT / "sft_dpo_inventory/pilot_010/gates/spec_s10.json").read_text(encoding="utf-8"))
    sets = dict(spec["sets"], rdev=spec["rdev_gold"])
    gold = {st: gold_map(p) for st, p in sets.items()}
    for arm in ("V4", "V8", "B2F", "P9"):
        cells = defaultdict(list)
        for s, by in spec["cells"].get(arm, {}).items():
            for st in sets:
                cells[st] += by[st]
        out[f"pilot010_{arm}"] = xtab(cells, gold)
    out["pilot010_base"] = xtab({st: spec["cells"]["base"][st] for st in sets}, gold)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--existing", action="store_true")
    ap.add_argument("--out", default=str(HERE / "xtab_existing.json"))
    a = ap.parse_args()
    if a.existing:
        res = existing()
        Path(a.out).write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        for k, v in res.items():
            if isinstance(v, dict) and "pct" in v:
                print(k, v["refused"], v["samples"], v["pct"], "| tool", {t: (x["refused"], x["pct"]) for t, x in list(v["axes"]["tool"].items())[:3]},
                      "| time", {t: (x["refused"], x["pct"]) for t, x in list(v["axes"]["time"].items())[:3]},
                      "| region", {t: (x["refused"], x["pct"]) for t, x in list(v["axes"]["region"].items())[:3]})


if __name__ == "__main__":
    main()
