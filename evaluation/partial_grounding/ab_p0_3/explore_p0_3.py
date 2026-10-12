"""결과를 본 뒤의 탐색 분석(사후 정의, gate 판정에 쓰지 않음): dt·bucket·refusal 부분집합 세부.

PLAN.md의 부분집합(gold factor 존재로 고정)은 그대로 쓰고, 그 안에서 결과를 본 뒤 정한 세부 패턴을 센다.
- dt: 최종 dimension_target 누락·잘못된 값, 첫 응답 dimension_target 누락, 첫 응답 dimension에 pickup/dropoff/both,
  첫 응답에서 dimension_target 없이 gold 값과 같은 od_role만 둔 관측(od_role 대체), dt가 아닌 문항에 생긴 dimension_target.
- bucket: 최종 bucket 누락·잘못된 값, 첫 응답 dimension=week/month(따로), aggregation_spec·dimension 차이.
- refusal: 거부 문항 10개의 문항별 결과(sampling 5회 + greedy).

사용: python explore_p0_3.py --out explore_p0_3.json
"""
import argparse
import collections
import json
import os

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
ARMS = ("full", "p0", "p0_3")
ROUNDS = range(1, 6)
OD = {"pickup", "dropoff", "both"}


def first_payload(row):
    calls = row.get("llm_calls") or []
    if not calls or calls[0].get("kind", "plan") != "plan":
        return None
    text = calls[0].get("content") or ""
    i, j = text.find("{"), text.rfind("}")
    if i < 0 or j < i:
        return None
    try:
        return json.loads(text[i:j + 1])
    except ValueError:
        return None


def od_roles(payload):
    out = set()
    for c in payload.get("concepts") or []:
        if isinstance(c, dict) and isinstance(c.get("attributes"), dict):
            v = c["attributes"].get("od_role")
            if isinstance(v, str):
                out.add(v)
    return out


def gold_factor(item, name):
    text = item.get("gold_text") or ""
    key = f"{name}="
    if key not in text:
        return None
    return text.split(key, 1)[1].split(",")[0].split(")")[0].strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    items = {it["id"]: it for it in yaml.safe_load(open(os.path.join(HERE, "sel154_gold.yaml")))["items"]}
    analysis = json.load(open(os.path.join(HERE, "analysis.json")))
    dt_ids = set(analysis["subsets"]["dt"]["ids"])
    bucket_ids = set(analysis["subsets"]["bucket"]["ids"])
    refusal_ids = analysis["subsets"]["refusal"]["ids"]

    dt = {arm: collections.Counter() for arm in ARMS}
    dt_items = {arm: collections.Counter() for arm in ARMS}
    bucket = {arm: collections.Counter() for arm in ARMS}
    refusal = {i: {"expected": items[i].get("expected_outcome"), **{arm: [] for arm in ARMS}} for i in refusal_ids}
    for arm in ARMS:
        cells = [f"{arm}_sample_r{r}" for r in ROUNDS] + [f"{arm}_greedy"]
        for cell in cells:
            sampling = "sample" in cell
            for row in json.load(open(os.path.join(HERE, "raw", f"{cell}.json")))["rows"]:
                rid = row["id"]
                if rid in refusal:
                    refusal[rid][arm].append(("g:" if not sampling else "") + row["category"])
                if not sampling:
                    continue
                diffs = {d[0]: d[1:] for d in row.get("grounding_diffs") or []}
                fp = first_payload(row)
                ff = (fp or {}).get("factors") or {}
                if not isinstance(ff, dict):
                    ff = {}
                if rid in dt_ids:
                    gv = gold_factor(items[rid], "dimension_target")
                    c = dt[arm]
                    c["observations"] += 1
                    c["correct"] += row["category"] in ("match", "expected_refusal")
                    d = diffs.get("factor:dimension_target")
                    if d and d[1] is None:
                        c["final_omitted"] += 1
                        dt_items[arm][rid] += 1
                    elif d:
                        c["final_wrong_value"] += 1
                    if fp is not None:
                        c["first_parsed"] += 1
                        if not ff.get("dimension_target"):
                            c["first_omitted"] += 1
                            if gv in od_roles(fp):
                                c["first_omitted_od_role_same_value"] += 1
                        if ff.get("dimension") in OD:
                            c["first_dimension_is_od_value"] += 1
                    if d and "places" in diffs:
                        c["dt_and_places_diff"] += 1
                else:
                    d = diffs.get("factor:dimension_target")
                    if d and d[0] is None:
                        dt[arm]["spurious_on_non_dt"] += 1
                if rid in bucket_ids:
                    c = bucket[arm]
                    c["observations"] += 1
                    c["correct"] += row["category"] in ("match", "expected_refusal")
                    d = diffs.get("factor:bucket")
                    if d and d[1] is None:
                        c["final_bucket_omitted"] += 1
                    elif d:
                        c["final_bucket_wrong"] += 1
                    if "factor:aggregation_spec" in diffs:
                        c["aggregation_spec_diff"] += 1
                    if "factor:dimension" in diffs:
                        c["dimension_diff"] += 1
                    if ff.get("dimension") == "week":
                        c["first_dimension_week"] += 1
                    if ff.get("dimension") == "month":
                        c["first_dimension_month"] += 1
                    if fp is not None and not ff.get("bucket"):
                        c["first_bucket_omitted"] += 1
    res = {
        "note": "사후 탐색. 부분집합은 PLAN 고정, 세부 패턴은 결과를 본 뒤 정했다. gate 판정에 쓰지 않는다.",
        "dt": {arm: dict(dt[arm]) for arm in ARMS},
        "dt_final_omitted_items": {arm: dict(dt_items[arm].most_common()) for arm in ARMS},
        "bucket": {arm: dict(bucket[arm]) for arm in ARMS},
        "refusal_items": {i: {k: (collections.Counter(v) if isinstance(v, list) else v) for k, v in r.items()}
                          for i, r in refusal.items()},
    }
    json.dump(res, open(a.out, "w"), ensure_ascii=False, indent=1)
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
