# -*- coding: utf-8 -*-
"""H1 분석(PLAN.md 5절): 승인 70 trace의 reasoning quality tag. 승인·거부 판정은 바꾸지 않는다. 모델 호출 없음.

    HF_HOME=/data/hwkim/path_repeat_001/hf-cache HF_HUB_OFFLINE=1 python sft_dpo_inventory/p0_sft_003_prep/trace_quality_analysis.py
    # -> trace_quality_analysis.json  (coverage_analysis.json이 먼저 있어야 한다: regression 관련 trace)

- tag·wrong-value mention 정의는 PLAN 5절 그대로다(정규식, 수동 조정 없음).
- **결과 뒤 추가(사후, PLAN에 없음):** `unit_as_place_mentions`.
  - coverage 분석에서 R70-full regression 다수가 묶음 단위어(읍면동·emd·하차 구 등)를 장소·concept로 낸 구조 오류였다.
  - 그래서 승인 trace가 이런 해석을 중간에 말하는지 정규식으로 센다.
  - 사전 등록 지표가 아니므로 판정 규칙(PLAN 10절)에 넣지 않고 보조로만 보고한다.
- regression 관련 trace: coverage_analysis.json의 B 문항 related_train_ids(exact·near family, 없으면 같은 measure).
  - 비교 집단은 70개 전체다.
"""
import collections
import json
import re
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

MEASURES = ("trip_count", "fare", "revenue", "speed", "rpm", "passage_count", "vacant_ratio", "active_taxi_ratio",
            "operating_days", "active_taxi_count")
FIELD_VALUES = {
    "measure": MEASURES,
    "dimension": ("h3", "emd", "sigungu", "sido", "dayofweek", "month", "week"),
    "dimension_target": ("pickup", "dropoff", "both"),
    "od_role": ("pickup", "dropoff", "both"),
    "aggregation": ("avg", "sum", "min", "max", "med"),
    "rollup": ("avg", "sum", "min", "max", "med"),
    "bucket": ("week", "month"),
}
HEDGE = re.compile(r"\b(Wait|Hmm|maybe|not sure)\b|confus", re.I)
WAITHMM = re.compile(r"\b(Wait|Hmm)\b")
FULL_WORDS = re.compile(r"\b(role|MEASURE|SUBCOND|COND|SUPPORT|EVENT|implicit|source)\b")
CONTRAST = re.compile(r"rather than|instead of|as opposed to|\bnot\b[^.]{0,40}\bbut\b|distinguish|\bvs\.?\b", re.I)
UNIT_AS_PLACE = re.compile(
    r"(H3 cells?|cells?|townships?|districts?|provinces?|읍면동|시군구|시도|구|동)[^.\n]{0,40}\b(as (a |the )?(place|location|scope|concept)s?|"
    r"LOCATION/place|subtype (\"|')?place)|"
    r"\"subtype\":\s*\"(emd|sido|sigungu|h3)\"|subtype (\"|')?(emd|sido|sigungu|h3)(\"|')?", re.I)


def field_pattern(field, value):
    names = {"measure": r"(measure|subtype|AMOUNT/|PROPORTION/)", "od_role": r"od_role",
             "dimension": r"dimension(?!_target)", "dimension_target": r"dimension_target",
             "aggregation": r"aggregation", "rollup": r"rollup", "bucket": r"bucket"}[field]
    return re.compile(names + r"[^.\n]{0,25}?['\"]?\b" + re.escape(value) + r"\b")


def gold_values(target):
    f = target.get("factors") or {}
    cs = target.get("concepts") or []
    measure = next((c.get("subtype") for c in cs if c.get("subtype") in MEASURES), None)
    roles = {(c.get("attributes") or {}).get("od_role") for c in cs if c.get("subtype") in ("place", "scope")} - {None}
    return {"measure": {measure} if measure else set(), "dimension": {f["dimension"]} if f.get("dimension") else set(),
            "dimension_target": {f["dimension_target"]} if f.get("dimension_target") else set(),
            "od_role": roles, "aggregation": {f["aggregation"]} if f.get("aggregation") else set(),
            "rollup": {f["rollup"]} if f.get("rollup") else set(), "bucket": {f["bucket"]} if f.get("bucket") else set()}


def wrong_mentions(thinking, target):
    gv = gold_values(target)
    out = {}
    for field, values in FIELD_VALUES.items():
        if field == "od_role" and not gv["od_role"]:
            continue
        wrong = sorted(v for v in values if v not in gv[field] and field_pattern(field, v).search(thinking))
        if wrong:
            out[field] = wrong
    if re.search(r"\"unsupported\":\s*true|\bunsupported\b", thinking):
        out["unsupported"] = ["mentioned"]
    return out


def weak(thinking, target):
    f = target.get("factors") or {}
    keys = [k for k in ("dimension_target", "bucket", "aggregation", "rollup", "order") if f.get(k)]
    roles = gold_values(target)["od_role"]
    low = thinking.lower()
    missing = [k for k in keys if k not in low and str(f[k]).lower() not in low]
    if roles and "od_role" not in low and not any(r in low for r in roles):
        missing.append("od_role")
    return missing


def main():
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained("Qwen/Qwen3-8B", revision="b968826d9c46dd6066d109eabc6255188de91218")
    r70 = [json.loads(x) for x in (ROOT / "training/generated/p0_sft_002/r70/sft_train.jsonl").read_text(encoding="utf-8").splitlines()]
    traces = []
    for r in r70:
        m = r["metadata"]
        content = r["messages"][2]["content"]
        thinking = content.split("</think>", 1)[0].split("<think>", 1)[-1].strip()
        traces.append({"id": m["source_record_id"], "trace_id": m["trace_id"], "source": m["source"], "thinking": thinking,
                       "target": m["target_p0"], "chars": len(thinking),
                       "tokens": len(tok(thinking, add_special_tokens=False)["input_ids"])})
    chars = sorted(t["chars"] for t in traces)
    p75 = chars[int(0.75 * (len(chars) - 1))]
    med = statistics.median(chars)
    for t in traces:
        th = t["thinking"]
        t["wrong_mentions"] = wrong_mentions(th, t["target"])
        t["hedges"] = len(HEDGE.findall(th))
        t["wait_hmm"] = len(WAITHMM.findall(th))
        t["full_words"] = len(FULL_WORDS.findall(th))
        t["weak_missing"] = weak(th, t["target"])
        t["unit_as_place_mentions"] = len(UNIT_AS_PLACE.findall(th))
        tags = []
        if t["wrong_mentions"]:
            tags.append("SELF_CORRECTED")
        if t["hedges"] >= 4:
            tags.append("HESITANT")
        if t["chars"] >= p75:
            tags.append("VERBOSE")
        if t["full_words"] >= 3:
            tags.append("SCHEMA_BOOKKEEPING")
        if t["weak_missing"]:
            tags.append("WEAK_JUSTIFICATION")
        if CONTRAST.search(th):
            tags.append("CONTRASTIVE_REASONING")
        if not t["wrong_mentions"] and t["wait_hmm"] <= 1 and t["chars"] <= med:
            tags.append("CLEAN_DIRECT")
        t["tags"] = tags

    def rates(ts):
        n = len(ts)
        if not n:
            return {"n": 0}
        tag_c = collections.Counter(x for t in ts for x in t["tags"])
        field_c = collections.Counter(f for t in ts for f in t["wrong_mentions"])
        return {"n": n, "tags": {k: [v, round(v / n, 3)] for k, v in sorted(tag_c.items())},
                "wrong_mention_any": [sum(bool(t["wrong_mentions"]) for t in ts), round(sum(bool(t["wrong_mentions"]) for t in ts) / n, 3)],
                "wrong_mention_by_field": dict(field_c),
                "unit_as_place_any(사후)": [sum(t["unit_as_place_mentions"] > 0 for t in ts),
                                          round(sum(t["unit_as_place_mentions"] > 0 for t in ts) / n, 3)],
                "chars_median": statistics.median(t["chars"] for t in ts), "tokens_median": statistics.median(t["tokens"] for t in ts)}

    cov = json.loads((HERE / "coverage_analysis.json").read_text(encoding="utf-8"))
    by_id = {t["id"]: t for t in traces}
    related_B = sorted({i for x in cov["items"] if x["group"] == "B" for i in x["related_train_ids"]})
    related_C = sorted({i for x in cov["items"] if x["group"] == "C" for i in x["related_train_ids"]})
    # family별 길이: near family(coverage_analysis와 같은 정의) 기준
    sys.path.insert(0, str(HERE))
    import coverage_analysis as CA
    fam = collections.defaultdict(list)
    for r in r70:
        ft = CA.feats(r["metadata"]["target_full"])
        fam[CA.near_family(ft)].append(by_id[r["metadata"]["source_record_id"]]["chars"])
    family_len = sorted(({"near_family": k, "n": len(v), "chars_median": statistics.median(v)} for k, v in fam.items()),
                        key=lambda x: -x["chars_median"])
    h1_all, h1_B = rates(traces), rates([by_id[i] for i in related_B])
    def r_(d, key):
        return d["tags"].get(key, [0, 0])[1] if "tags" in d else 0
    h1_support = {
        "self_corrected_gap": round(r_(h1_B, "SELF_CORRECTED") - r_(h1_all, "SELF_CORRECTED"), 3),
        "hesitant_gap": round(r_(h1_B, "HESITANT") - r_(h1_all, "HESITANT"), 3),
        "wrong_mention_gap": round(h1_B["wrong_mention_any"][1] - h1_all["wrong_mention_any"][1], 3) if h1_B.get("n") else None}
    h1_support["condition_met(≥0.15)"] = any(v is not None and v >= 0.15 for v in h1_support.values())
    out = {"p75_chars": p75, "median_chars": med, "all_70": h1_all,
           "related_to_regression_B": {"ids": related_B, **h1_B},
           "related_to_improvement_C": {"ids": related_C, **rates([by_id[i] for i in related_C])},
           "h1_support": h1_support, "by_source": {s: rates([t for t in traces if t["source"] == s])
                                                   for s in ("v005", "augment_dt_event", "augment_od_vs_dt")},
           "family_length": family_len,
           "traces": [{k: t[k] for k in ("id", "trace_id", "source", "chars", "tokens", "tags", "wrong_mentions", "hedges",
                                          "full_words", "weak_missing", "unit_as_place_mentions")} for t in traces]}
    (HERE / "trace_quality_analysis.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("all_70", "h1_support")}, ensure_ascii=False, indent=1))
    print(json.dumps({k: v for k, v in out["related_to_regression_B"].items() if k != "ids"}, ensure_ascii=False))
    print(len(related_B), "related B traces")


if __name__ == "__main__":
    main()
