# [pilot_006 준비 W3 이식] 원본: geoflow/partial-grounding 커밋 ab9d215의 evaluation/partial_grounding/ab_p0_3/root_cause.py. 본문은 원본 그대로다(아래 '이식 수정' 줄 제외).
# 원본의 경로 상수(ROOT 등)는 원 위치 기준이라 이 위치에서 바로 돌리려면 경로 인자를 확인한다. 참고값 경로(HF greedy·Ollama, 다른 장비)의 기록용 도구다.
"""P0.3 실패 원인 분석(사후 진단, gate 판정에 쓰지 않음). 기존 raw만 읽고 모델을 부르지 않는다.

- 기록에는 thinking 원문이 없다(evaluate_vendor100.py는 thinking_chars만 남긴다). thinking 분석은 길이와 첫 응답 구조로 대신한다.
- 질문 표현 유형(EXPRESSION)은 결과를 본 뒤 질문 문장만 읽고 정한 분류다.
- gold, prompt, 판정 정의는 바꾸지 않는다.

사용: python root_cause.py --out root_cause.json --csv root_cause_items.csv
"""
import argparse
import collections
import csv
import json
import math
import os
import statistics

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
ARMS = ("full", "p0", "p0_3")
ROUNDS = range(1, 6)
OD = {"pickup", "dropoff", "both"}
CORRECT = {"match", "expected_refusal"}
SCOPE_LOOKUP = ("indepv2/n40", "indepv4/k21")

#: 질문 표현 유형(사후 분류, 서로 겹치지 않게 주 유형 하나).
#: explicit: 끝점 단어가 그룹 단위를 직접 꾸민다("승차 동네", "내린 구 기준"). "승차 지역별"과 같은 꼴.
#: event: 끝점이 사건·측정 표현 안에 있고 그룹 단위는 따로 나온다("승차가 많은 읍면동", "내린 위치를 H3 셀 기준으로").
#: cross_end: 장소는 한쪽 끝(pickup)으로 제한하고 결과는 다른 끝(dropoff)으로 묶는다.
#: both: 출발-도착 짝(노선·경로·짝)으로 묶는다.
EXPRESSION = {
    "indepv3/m09": "explicit", "indepv4/k34": "explicit",
    "old44/g12": "event", "contrast/c01a": "event", "contrast/c01b": "event", "indepv2/n06": "event",
    "indepv2/n34": "event", "indepv2/n35": "event", "indepv3/m03": "event", "indepv3/m04": "event",
    "indepv4/k27": "event", "indepv4/k28": "event", "indepv2/n05": "event",
    "indepv4/k26": "cross_end", "indepv3/m02": "cross_end",
    "contrast/c04b": "both", "contrast/c04a": "both", "indepv2/n09": "both", "indepv4/k33": "both",
    "indepv3/m05": "both",
}

#: dt 실패 관측 분류(사용자 지시 3절 A–F, 진단용). G는 dt는 맞고 다른 요소가 틀린 관측(지시에 없는 보조 범주).
FAILURE_CLASSES = {
    "A": "dimension_target 완전 누락(첫 응답에 od_role도 없음)",
    "B": "od_role만 출력하고 dimension_target 누락",
    "C": "dimension에 pickup/dropoff/both",
    "D": "잘못된 dimension_target 값",
    "E": "최종 grounding 없음(measure·place 등에서 막혀 dt까지 못 감)",
    "F": "grounding은 맞지만 downstream에서 실패",
    "G": "dimension_target은 맞고 다른 grounding 요소가 틀림",
}


def first_payload(row):
    calls = row.get("llm_calls") or []
    if not calls or calls[0].get("kind", "plan") != "plan":
        return None
    text = calls[0].get("content") or ""
    i, j = text.find("{"), text.rfind("}")
    if i < 0 or j < i:
        return None
    try:
        payload = json.loads(text[i:j + 1])
    except ValueError:
        return None
    return payload if isinstance(payload, dict) else None


def factors(payload):
    f = (payload or {}).get("factors")
    return f if isinstance(f, dict) else {}


def concepts(payload):
    return [c for c in (payload or {}).get("concepts") or [] if isinstance(c, dict)]


def od_roles(payload):
    out = set()
    for c in concepts(payload):
        attrs = c.get("attributes")
        if isinstance(attrs, dict) and isinstance(attrs.get("od_role"), str):
            out.add(attrs["od_role"])
    return out


def gold_value(item, name):
    text = item.get("gold_text") or ""
    key = f"{name}="
    if key not in text:
        return None
    return text.split(key, 1)[1].split(",")[0].split(")")[0].strip()


def gold_od(item):
    text = item.get("gold_text") or ""
    return sorted(r for r in ("pickup", "dropoff") if f"scope_{r}=" in text)


def diffs_of(row):
    out, flags = {}, set()
    for d in row.get("grounding_diffs") or []:
        if isinstance(d, (list, tuple)):
            out[d[0]] = list(d[1:])
        else:
            flags.add(d)
    return out, flags


def thinking_chars(row):
    return sum(c.get("thinking_chars") or 0 for c in row.get("llm_calls") or [])


def first_thinking_chars(row):
    calls = row.get("llm_calls") or []
    return (calls[0].get("thinking_chars") or 0) if calls else 0


def observe(row, item):
    """관측 하나의 dt 관련 요약."""
    fp = first_payload(row)
    ff = factors(fp)
    d, flags = diffs_of(row)
    dt_diff = d.get("factor:dimension_target")
    return {
        "category": row["category"],
        "correct": row["category"] in CORRECT,
        "grounding_ok": bool(row.get("grounding_ok")),
        "no_grounding": "no_grounding" in flags,
        "first_parsed": fp is not None,
        "first_dt": ff.get("dimension_target"),
        "first_dimension": ff.get("dimension"),
        "first_bucket": ff.get("bucket"),
        "first_od_roles": sorted(od_roles(fp)),
        "first_subtypes": [c.get("subtype") for c in concepts(fp)],
        "first_has_trip_event": any(c.get("subtype") in ("trip", "passage") for c in concepts(fp)),
        "final_dt_omitted": bool(dt_diff) and dt_diff[1] is None,
        "final_dt_wrong": bool(dt_diff) and dt_diff[1] is not None and dt_diff[0] is not None,
        "final_dt_spurious": bool(dt_diff) and dt_diff[0] is None,
        "final_dimension_diff": "factor:dimension" in d,
        "diff_keys": sorted(d) + sorted(flags),
        "error_code": row.get("error_code"),
        "thinking_chars": thinking_chars(row),
        "first_thinking_chars": first_thinking_chars(row),
        "eval_count": sum(c.get("eval_count") or 0 for c in row.get("llm_calls") or []),
        "repair_calls": sum(1 for c in row.get("llm_calls") or [] if c.get("kind") == "repair"),
    }


def classify_failure(o):
    if o["correct"]:
        return None
    if o["first_dimension"] in OD:
        return "C"
    if o["no_grounding"]:
        return "E"
    if o["final_dt_omitted"]:
        return "B" if o["first_od_roles"] else "A"
    if o["final_dt_wrong"]:
        return "D"
    if o["grounding_ok"]:
        return "F"
    return "G"


def dt_pattern(o):
    """첫 응답의 dt 출력 꼴(문항 표의 output pattern)."""
    if not o["first_parsed"]:
        return "parse_fail"
    if o["first_dimension"] in OD:
        return f"dimension={o['first_dimension']}"
    if o["first_dt"]:
        return f"dt={o['first_dt']}"
    return "dt없음+od_role" if o["first_od_roles"] else "dt없음"


def stability(k):
    return "stable_correct" if k >= 4 else ("unstable" if k >= 2 else "stable_wrong")


def greedy_vs_sampling(greedy_correct, k):
    if greedy_correct and k <= 1:
        return "greedy_only"
    if not greedy_correct and k >= 4:
        return "sampling_only"
    if not greedy_correct and k <= 1:
        return "both_stable_wrong"
    if greedy_correct and k >= 4:
        return "both_stable_correct"
    return "mixed"


def rate(n, d):
    return round(n / d, 4) if d else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--csv", required=True)
    a = ap.parse_args()
    items = {it["id"]: it for it in yaml.safe_load(open(os.path.join(HERE, "sel154_gold.yaml")))["items"]}
    analysis = json.load(open(os.path.join(HERE, "analysis.json")))
    dt_ids = analysis["subsets"]["dt"]["ids"]
    assert set(dt_ids) == set(EXPRESSION), "dt 부분집합과 표현 분류가 다르다"
    order = list(items)

    obs = {arm: collections.defaultdict(list) for arm in ARMS}       # sampling 관측(회차 순)
    greedy = {arm: {} for arm in ARMS}
    round_acc = {arm: [] for arm in ARMS}
    for arm in ARMS:
        for r in ROUNDS:
            rows = json.load(open(os.path.join(HERE, "raw", f"{arm}_sample_r{r}.json")))["rows"]
            round_acc[arm].append(sum(x["category"] in CORRECT for x in rows) / len(rows))
            for x in rows:
                obs[arm][x["id"]].append(observe(x, items[x["id"]]))
        for x in json.load(open(os.path.join(HERE, "raw", f"{arm}_greedy.json")))["rows"]:
            greedy[arm][x["id"]] = observe(x, items[x["id"]])
    k = {arm: {i: sum(o["correct"] for o in obs[arm][i]) for i in order} for arm in ARMS}

    # 3. dt 문항 표와 실패 분류
    dt_table, failure_counts, failure_items = [], {arm: collections.Counter() for arm in ARMS}, \
        {arm: collections.defaultdict(collections.Counter) for arm in ARMS}
    for i in dt_ids:
        it = items[i]
        rec = {"id": i, "question": it["question"], "expression": EXPRESSION[i],
               "gold_dimension": gold_value(it, "dimension"), "gold_dimension_target": gold_value(it, "dimension_target"),
               "gold_od_scopes": gold_od(it)}
        for arm in ARMS:
            rec[f"k_{arm}"] = k[arm][i]
            rec[f"greedy_{arm}"] = greedy[arm][i]["category"]
            rec[f"pattern_{arm}"] = dict(collections.Counter(dt_pattern(o) for o in obs[arm][i]))
            rec[f"final_dt_omitted_{arm}"] = sum(o["final_dt_omitted"] for o in obs[arm][i])
            classes = collections.Counter(classify_failure(o) for o in obs[arm][i] if not o["correct"])
            rec[f"failure_{arm}"] = dict(classes)
            failure_counts[arm].update(classes)
            for c, n in classes.items():
                failure_items[arm][c][i] += n
        dt_table.append(rec)

    # 4. 질문 표현 유형별
    by_type = {}
    for t in ("explicit", "event", "cross_end", "both"):
        ids = [i for i in dt_ids if EXPRESSION[i] == t]
        by_type[t] = {"items": ids, "n_items": len(ids)}
        for arm in ARMS:
            O = [o for i in ids for o in obs[arm][i]]
            by_type[t][arm] = {
                "correct": rate(sum(o["correct"] for o in O), len(O)),
                "dt_omitted": rate(sum(o["final_dt_omitted"] for o in O), len(O)),
                "od_role_only_first": rate(sum(o["first_parsed"] and not o["first_dt"] and bool(o["first_od_roles"])
                                               and o["first_dimension"] not in OD for o in O), len(O)),
                "first_dimension_od_value": rate(sum(o["first_dimension"] in OD for o in O), len(O)),
                "final_dimension_diff": rate(sum(o["final_dimension_diff"] for o in O), len(O)),
            }
    # 겹치는 보조 묶음: gold에 od_role scope가 있는 문항(사용자 유형 3)
    cross = {}
    for name, sel in (("od_scope_and_grouping_same_end",
                       lambda i: gold_od(items[i]) and gold_value(items[i], "dimension_target") in gold_od(items[i])
                       and EXPRESSION[i] != "both"),
                      ("od_scope_and_grouping_other_end",
                       lambda i: gold_od(items[i]) and gold_value(items[i], "dimension_target") not in gold_od(items[i])
                       and EXPRESSION[i] != "both"),
                      ("no_od_scope", lambda i: not gold_od(items[i]))):
        ids = [i for i in dt_ids if sel(i)]
        cross[name] = {"items": ids}
        for arm in ARMS:
            O = [o for i in ids for o in obs[arm][i]]
            cross[name][arm] = {"correct": rate(sum(o["correct"] for o in O), len(O)),
                                "dt_omitted": rate(sum(o["final_dt_omitted"] for o in O), len(O)),
                                "od_role_only_first": rate(sum(o["first_parsed"] and not o["first_dt"]
                                                               and bool(o["first_od_roles"]) for o in O), len(O))}

    # 5·6. thinking 대체 지표(길이)와 첫 응답 구조
    thinking = {}
    for arm in ARMS:
        O = [o for i in dt_ids for o in obs[arm][i]]
        om = [o["first_thinking_chars"] for o in O if o["final_dt_omitted"]]
        ok = [o["first_thinking_chars"] for o in O if o["first_dt"]]
        allo = [o["first_thinking_chars"] for i in order for o in obs[arm][i]]
        thinking[arm] = {
            "median_first_thinking_chars_all_items": statistics.median(allo),
            "median_first_thinking_chars_dt_items": statistics.median([o["first_thinking_chars"] for o in O]),
            "dt_omitted_obs": {"n": len(om), "median": statistics.median(om) if om else None},
            "dt_present_first_obs": {"n": len(ok), "median": statistics.median(ok) if ok else None},
            "trip_event_concept_rate_dt_items": rate(sum(o["first_has_trip_event"] for o in O), len(O)),
            "dt_present_first_rate_dt_items": rate(sum(bool(o["first_dt"]) for o in O), len(O)),
        }
    # Full: trip 사건 concept 유무와 dt 출력(관측이 적어 참고만)
    scaffold = {}
    for arm in ARMS:
        O = [o for i in dt_ids for o in obs[arm][i]]
        with_trip = [o for o in O if o["first_has_trip_event"]]
        without = [o for o in O if not o["first_has_trip_event"]]
        scaffold[arm] = {"with_trip_event": {"n": len(with_trip),
                                             "dt_present_first": rate(sum(bool(o["first_dt"]) for o in with_trip),
                                                                      len(with_trip))},
                         "without_trip_event": {"n": len(without),
                                                "dt_present_first": rate(sum(bool(o["first_dt"]) for o in without),
                                                                         len(without))}}

    # 7. sampling instability
    def transitions(ids, a1, a2):
        m = collections.Counter((stability(k[a1][i]), stability(k[a2][i])) for i in ids)
        return {f"{x}->{y}": n for (x, y), n in sorted(m.items())}

    def instability(ids, arm):
        n = len(ids)
        var = sum((k[arm][i] / 5) * (1 - k[arm][i] / 5) for i in ids)
        return {"stability_counts": dict(collections.Counter(stability(k[arm][i]) for i in ids)),
                "mean_item_bernoulli_variance": round(var / n, 4),
                "expected_round_sd_pp": round(100 * math.sqrt(var) / n, 2)}

    sampling = {}
    for name, ids in (("all", order), ("dt", dt_ids)):
        sampling[name] = {arm: instability(ids, arm) for arm in ARMS}
        sampling[name]["transitions_full_to_p0_3"] = transitions(ids, "full", "p0_3")
        sampling[name]["transitions_p0_to_p0_3"] = transitions(ids, "p0", "p0_3")
    for arm in ARMS:
        sampling["all"][arm]["round_accuracy_pp"] = [round(100 * x, 1) for x in round_acc[arm]]
        sampling["all"][arm]["observed_round_sd_pp"] = round(100 * statistics.stdev(round_acc[arm]), 2)
    # dt 누락의 문항 내 일관성: 5회 중 몇 번 누락했나
    omission_consistency = {arm: dict(collections.Counter(
        sum(o["final_dt_omitted"] for o in obs[arm][i]) for i in dt_ids)) for arm in ARMS}

    # 8. greedy vs sampling
    gvs = {}
    for name, ids in (("all", order), ("dt", dt_ids)):
        gvs[name] = {}
        for arm in ARMS:
            cls = collections.defaultdict(list)
            for i in ids:
                cls[greedy_vs_sampling(greedy[arm][i]["correct"], k[arm][i])].append(i)
            gvs[name][arm] = {c: {"n": len(v), "items": v if c != "both_stable_correct" and c != "mixed" else None}
                              for c, v in sorted(cls.items())}
            gvs[name][arm]["greedy_accuracy"] = rate(sum(greedy[arm][i]["correct"] for i in ids), len(ids))
            gvs[name][arm]["sampling_accuracy"] = rate(sum(k[arm][i] for i in ids), 5 * len(ids))

    # 9. gold sanity 후보(dt 문항, P0.3 ≤ 1/5이고 Full ≤ 1/5)
    sanity = []
    for i in dt_ids:
        if k["p0_3"][i] <= 1 and k["full"][i] <= 1:
            diffs = {arm: dict(collections.Counter(key for o in obs[arm][i] if not o["correct"] for key in o["diff_keys"]))
                     for arm in ARMS}
            sanity.append({"id": i, "question": items[i]["question"], "gold": items[i]["gold_text"],
                           **{f"k_{arm}": k[arm][i] for arm in ARMS},
                           **{f"greedy_{arm}": greedy[arm][i]["category"] for arm in ARMS},
                           "failing_diff_keys": diffs})

    # 10. scope 역조회
    scope = {}
    for i in SCOPE_LOOKUP:
        scope[i] = {"question": items[i]["question"], "gold": items[i]["gold_text"]}
        for arm in ARMS:
            scope[i][arm] = [{"category": o["category"], "first_subtypes": o["first_subtypes"],
                              "error_code": o["error_code"], "repair_calls": o["repair_calls"],
                              "first_thinking_chars": o["first_thinking_chars"], "diff_keys": o["diff_keys"]}
                             for o in obs[arm][i]] + [{"greedy": greedy[arm][i]["category"],
                                                       "first_subtypes": greedy[arm][i]["first_subtypes"],
                                                       "error_code": greedy[arm][i]["error_code"]}]

    # 11. P0.3 누락 43건의 원인 묶음(겹침 허용)
    sanity_ids = {s["id"] for s in sanity}
    om_obs = [(i, o) for i in dt_ids for o in obs["p0_3"][i] if o["final_dt_omitted"]]
    om_item = {i: sum(o["final_dt_omitted"] for o in obs["p0_3"][i]) for i in dt_ids}
    full_om = {i: sum(o["final_dt_omitted"] for o in obs["full"][i]) for i in dt_ids}
    p0_om = {i: sum(o["final_dt_omitted"] for o in obs["p0"][i]) for i in dt_ids}
    buckets = collections.Counter()
    bucket_items = collections.defaultdict(set)
    for i, o in om_obs:
        tags = []
        if 1 <= om_item[i] <= 4:
            tags.append("sampling_instability(같은 문항에서 dt를 낸 회차도 있음)")
        if om_item[i] == 5:
            tags.append("deterministic(5/5 누락)")
        if o["first_od_roles"]:
            tags.append("semantic_distinction(끝점을 od_role로만 씀)")
        else:
            tags.append("unclear(od_role도 dt도 없음, thinking 미기록)")
        if i in sanity_ids or full_om[i] >= 3:
            tags.append("ambiguity_candidate(Full도 실패·누락)")
        if p0_om[i] > full_om[i]:
            tags.append("scaffold_loss_candidate(P0 누락 > Full 누락)")
        if om_item[i] > p0_om[i]:
            tags.append("partial_rules_excess(P0.3 누락 > P0 누락)")
        for t in tags:
            buckets[t] += 1
            bucket_items[t].add(i)
    excess = {"p0_3_minus_p0_omissions_total": sum(om_item.values()) - sum(p0_om.values()),
              "per_item": {i: {"full": full_om[i], "p0": p0_om[i], "p0_3": om_item[i]} for i in dt_ids}}

    res = {
        "note": "사후 진단. 모델 호출 없이 기존 raw만 읽었다. thinking 원문은 기록되지 않아 길이만 쓴다. gate 판정에 쓰지 않는다.",
        "failure_classes": FAILURE_CLASSES,
        "dt_items": dt_table,
        "dt_failure_counts": {arm: dict(sorted(failure_counts[arm].items())) for arm in ARMS},
        "dt_failure_items": {arm: {c: dict(v) for c, v in sorted(failure_items[arm].items())} for arm in ARMS},
        "expression_types": by_type,
        "od_scope_cross_cut": cross,
        "thinking_proxy": thinking,
        "trip_event_scaffold": scaffold,
        "sampling_instability": sampling,
        "dt_omission_consistency": omission_consistency,
        "greedy_vs_sampling": gvs,
        "gold_sanity_candidates": sanity,
        "scope_lookup": scope,
        "p0_3_omission_buckets": {"n_omissions": len(om_obs), "counts": dict(buckets),
                                  "items": {t: sorted(v) for t, v in bucket_items.items()}},
        "omission_excess": excess,
    }
    json.dump(res, open(a.out, "w"), ensure_ascii=False, indent=1)

    with open(a.csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "in_dt", "expression", "gold_dimension", "gold_dimension_target", "gold_od_scopes",
                    "k_full", "k_p0", "k_p0_3", "greedy_full", "greedy_p0", "greedy_p0_3",
                    "stability_full", "stability_p0", "stability_p0_3", "gvs_p0_3",
                    "dt_omitted_full", "dt_omitted_p0", "dt_omitted_p0_3",
                    "pattern_full", "pattern_p0", "pattern_p0_3", "failure_p0_3", "gold_review_candidate", "question"])
        dt_rec = {r["id"]: r for r in dt_table}
        for i in order:
            r = dt_rec.get(i)
            w.writerow([i, int(r is not None), EXPRESSION.get(i, ""),
                        r["gold_dimension"] if r else "", r["gold_dimension_target"] if r else "",
                        "+".join(r["gold_od_scopes"]) if r else "",
                        k["full"][i], k["p0"][i], k["p0_3"][i],
                        greedy["full"][i]["category"], greedy["p0"][i]["category"], greedy["p0_3"][i]["category"],
                        stability(k["full"][i]), stability(k["p0"][i]), stability(k["p0_3"][i]),
                        greedy_vs_sampling(greedy["p0_3"][i]["correct"], k["p0_3"][i]),
                        r["final_dt_omitted_full"] if r else "", r["final_dt_omitted_p0"] if r else "",
                        r["final_dt_omitted_p0_3"] if r else "",
                        json.dumps(r["pattern_full"], ensure_ascii=False) if r else "",
                        json.dumps(r["pattern_p0"], ensure_ascii=False) if r else "",
                        json.dumps(r["pattern_p0_3"], ensure_ascii=False) if r else "",
                        json.dumps(r["failure_p0_3"], ensure_ascii=False) if r else "",
                        int(i in sanity_ids), items[i]["question"]])
    summary = {key: res[key] for key in ("dt_failure_counts", "p0_3_omission_buckets", "omission_excess")}
    print(json.dumps(summary, ensure_ascii=False, indent=1)[:6000])


if __name__ == "__main__":
    main()
