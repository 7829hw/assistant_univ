# -*- coding: utf-8 -*-
"""quality_gate_v1: teacher trace risk flag와 ranking(결정 75·76). 자동 승인기가 아니다. 모델 호출 없음.

고정: 2026-10-14, 27B 결과 전. 설계 뒤 기존 trace에 한 번 replay하고(`--replay`) 결과를 기록한다. 규칙은 바꾸지 않는다.

원칙(high precision):
- 문장 근거 flag는 thinking의 **결론 구간(마지막 30% 글자)**에서만 찾는다. 중간에 말했다가 고친 오판은 잡지 않는다.
- 구조 flag는 trace 자신의 최종 응답 JSON을 본다.
- 묶음 단위어가 나왔다는 것만으로는 flag하지 않는다. concept·place로 만든다는 명시적 문장이나, 실제 JSON 구조가 있을 때만 건다.
- 묶음 단위 vocabulary는 ontology(`geoflow.factors`의 dimension 허용값)를 쓴다. 자연어 표현은 고정 목록이다.

flag:
- GROUPING_UNIT_AS_CONCEPT
  - (구조) 응답 concept의 subtype이 dimension 허용값(h3·sido·sigungu·emd·dayofweek) 또는 "dimension"
  - (문장) 결론 구간에 "<단위> … as a concept" / "subtype '<단위>'"
- GROUPING_UNIT_AS_PLACE
  - (구조) 응답 place concept의 text 또는 value.name이 묶음 단위어 자체(읍면동, 시군구, 시도, 구, 동, 셀, H3 셀, 하차 구, 승차 구 등)
  - (문장) 결론 구간에 "<단위> … as (a) place/location/SUBCOND"
- HALLUCINATED_SCHEMA_RULE
  - (구조) 응답 factors에 answer: "bucket"이 있는데 bucket이 없음
  - (문장) 결론 구간에 "answer (is|should be) bucket because"
- UNRETRACTED_WRONG_AGGREGATION: 결론 구간에서 "aggregation is/would be/should be <값>"이라고 말한 마지막 위치 뒤에 철회 표현이 없고, 응답 factors.aggregation이 그 값과 다름(없음 포함)
  - 철회 표현: not needed, no need, not required, omit, isn't necessary, shouldn't include, don't include, not include
- OD_ROLE_DIM_TARGET_CONFUSION(구조)
  - factors.dimension이 pickup·dropoff·both
  - dimension_target이 있는데 dimension이 없음
  - od_role이 place·scope가 아닌 concept에 붙음
- CONCLUDED_UNSUPPORTED: 결론 구간에 unsupported 결론 문장("is unsupported", "return {"unsupported": true}", "should be unsupported", "the answer is unsupported")이 있는데 응답이 unsupported가 아님
- REASONING_FINAL_CONFLICT: thinking에 적은 마지막 JSON 초안(`"factors"`를 가진 객체)과 응답 factors가 다름(answer: value는 무시)

ranking(문항 안 정답 후보, 작을수록 앞):
1. flag 수
2. thinking 길이(글자)
3. 명시적 번복 수("Wait"·"Hmm")
4. 표본 순서(greedy 먼저, 그다음 sample index)

`--replay`: 기존 사람 판정 trace(R70 승인 70·거부 21, M2 승인 10·거부 6, M3 승인 3·거부 1)에 적용해 quality_gate_v1_replay.json을 쓴다.
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

FLAGS = ("GROUPING_UNIT_AS_CONCEPT", "GROUPING_UNIT_AS_PLACE", "HALLUCINATED_SCHEMA_RULE", "UNRETRACTED_WRONG_AGGREGATION",
         "OD_ROLE_DIM_TARGET_CONFUSION", "CONCLUDED_UNSUPPORTED", "REASONING_FINAL_CONFLICT")
CONCLUSION_FRACTION = 0.3


def dimension_values():
    """ontology source of truth: geoflow.factors.FACTOR_SPECS["dimension"].values."""
    from geoflow.factors import FACTOR_SPECS
    return set(FACTOR_SPECS["dimension"].values)


DIM_VALUES = dimension_values()
UNIT_WORDS = {"읍면동", "시군구", "시도", "구", "동", "셀", "H3 셀", "h3 셀", "H3셀", "요일", "하차 구", "승차 구", "하차구", "승차구",
              "동네", "읍면동별", "시군구별", "시도별"}
UNIT_EN = r"(H3 cells?|cells?|districts?|townships?|provinces?|sigungu|sido|emd|h3|si-gun-gu|읍면동|시군구|시도)"
RE_CONCEPT = re.compile(UNIT_EN + r"[^.\n]{0,40}\bas (a |an |the )?(separate )?concepts?\b|subtype\W{0,3}(emd|sido|sigungu|h3|dimension)\b", re.I)
RE_PLACE = re.compile(UNIT_EN + r"[^.\n]{0,40}\bas (a |an |the )?(place|location|SUBCOND)s?\b", re.I)
RE_ANSWER_RULE = re.compile(r"answer (is|should be|would be|must be)\W{0,3}bucket\W{0,3}because", re.I)
RE_AGG = re.compile(r"aggregation (is|would be|should be|=|:)\s*\W?(sum|avg|min|max|med|count)\b", re.I)
RE_RETRACT = re.compile(r"not needed|no need|not required|omit|isn'?t necessary|shouldn'?t include|don'?t include|not include", re.I)
RE_UNSUP = re.compile(r"is unsupported|return\s*\{\s*\"unsupported\"\s*:\s*true|should be unsupported|the answer is unsupported|"
                      r"answer should be \{\"unsupported\"", re.I)


def parse_json(text):
    i, j = text.find("{"), text.rfind("}")
    if i < 0 or j < i:
        return None
    try:
        return json.loads(text[i:j + 1])
    except Exception:  # noqa: BLE001
        return None


def last_factor_draft(thinking):
    """thinking 안의 마지막 JSON 초안 중 factors를 가진 것."""
    out = None
    for m in re.finditer(r"\{", thinking):
        depth = 0
        for k in range(m.start(), min(len(thinking), m.start() + 4000)):
            ch = thinking[k]
            depth += ch == "{"
            depth -= ch == "}"
            if depth == 0:
                try:
                    obj = json.loads(thinking[m.start():k + 1])
                except Exception:  # noqa: BLE001
                    obj = None
                if isinstance(obj, dict) and isinstance(obj.get("factors"), dict):
                    out = obj
                break
    return out


def norm_factors(f):
    f = dict(f or {})
    if f.get("answer") == "value":
        f.pop("answer")
    return f


def flags(thinking, content):
    thinking = thinking or ""
    tail = thinking[int(len(thinking) * (1 - CONCLUSION_FRACTION)):]
    out = parse_json(content or "")
    found = set()
    concepts = (out or {}).get("concepts") or [] if isinstance(out, dict) else []
    factors = (out or {}).get("factors") or {} if isinstance(out, dict) else {}
    # A
    if any(isinstance(c, dict) and (c.get("subtype") in DIM_VALUES or c.get("subtype") == "dimension") for c in concepts) \
            or RE_CONCEPT.search(tail):
        found.add("GROUPING_UNIT_AS_CONCEPT")
    # B
    def unit_name(c):
        v = c.get("value")
        name = v.get("name") if isinstance(v, dict) else None
        return (str(c.get("text") or "").strip() in UNIT_WORDS) or (name is not None and str(name).strip() in UNIT_WORDS)
    if any(isinstance(c, dict) and c.get("subtype") == "place" and unit_name(c) for c in concepts) or RE_PLACE.search(tail):
        found.add("GROUPING_UNIT_AS_PLACE")
    # C
    if (factors.get("answer") == "bucket" and not factors.get("bucket")) or RE_ANSWER_RULE.search(tail):
        found.add("HALLUCINATED_SCHEMA_RULE")
    # D
    aggs = list(RE_AGG.finditer(tail))
    if aggs:
        last = aggs[-1]
        said = last.group(2).lower()
        if not RE_RETRACT.search(tail[last.end():]) and (factors.get("aggregation") or "").lower() != said:
            found.add("UNRETRACTED_WRONG_AGGREGATION")
    # E
    if factors.get("dimension") in ("pickup", "dropoff", "both") or (factors.get("dimension_target") and not factors.get("dimension")) \
            or any(isinstance(c, dict) and (c.get("attributes") or {}).get("od_role") and c.get("subtype") not in ("place", "scope")
                   for c in concepts):
        found.add("OD_ROLE_DIM_TARGET_CONFUSION")
    # F
    if RE_UNSUP.search(tail) and not (isinstance(out, dict) and out.get("unsupported")):
        found.add("CONCLUDED_UNSUPPORTED")
    # G
    draft = last_factor_draft(thinking)
    if draft is not None and isinstance(out, dict) and norm_factors(draft.get("factors")) != norm_factors(factors):
        found.add("REASONING_FINAL_CONFLICT")
    return sorted(found)


def rank_key(thinking, content, kind, sample_index):
    fl = flags(thinking, content)
    hedges = len(re.findall(r"\b(Wait|Hmm)\b", thinking or ""))
    return (len(fl), len(thinking or ""), hedges, 0 if kind == "greedy" else 1, sample_index or 0)


def replay():
    import collections
    sets = []
    sel = {json.loads(x)["trace_id"]: json.loads(x) for x in
           (ROOT / "sft_dpo_inventory/p0_sft_001/selected_traces.jsonl").read_text(encoding="utf-8").splitlines()}
    for x in json.loads((ROOT / "sft_dpo_inventory/p0_sft_001/trace_review.json").read_text(encoding="utf-8"))["items"]:
        t = sel[x["trace_id"]]
        sets.append(("R70", x["trace_id"], x["decision"], t["thinking"], t["content"], x.get("reason_code")))
    raw2 = {json.loads(x)["trace_id"]: json.loads(x) for x in
            (ROOT / "training/generated/p0_sft_003_recovery/m2_raw/traces.jsonl").read_text(encoding="utf-8").splitlines()}
    for item, r in json.loads((ROOT / "sft_dpo_inventory/p0_sft_003_recovery/m2_review.json").read_text(encoding="utf-8"))["items"].items():
        if r["decision"]:
            t = raw2[r["trace_id"]]
            sets.append(("M2", r["trace_id"], r["decision"], t["thinking"], t["content"], ";".join(r["quality_tags"])))
    m3 = json.loads((ROOT / "sft_dpo_inventory/p0_sft_003_recovery/m3_recovery.json").read_text(encoding="utf-8"))
    raw1 = {}
    for line in (ROOT / "training/generated/thinking_traces/p0_v006_hf/traces.jsonl").read_text(encoding="utf-8").splitlines():
        t = json.loads(line)
        if t["item_id"] in m3["review"]:
            raw1[t["trace_id"]] = t
    for item, r in m3["review"].items():
        t = raw1[r["trace_id"]]
        sets.append(("M3", r["trace_id"], r["decision"], t["thinking"], t["content"], ";".join(r["quality_tags"])))
    rows = [{"set": s, "trace_id": tid, "human": d, "human_reason": why, "flags": flags(th, ct)} for s, tid, d, th, ct, why in sets]
    approved = [r for r in rows if r["human"] == "APPROVE_TRACE"]
    rejected = [r for r in rows if r["human"] == "REJECT_TRACE"]
    per_flag = {}
    for f in FLAGS:
        a = sum(f in r["flags"] for r in approved)
        rj = sum(f in r["flags"] for r in rejected)
        per_flag[f] = {"approved_hits": a, "rejected_hits": rj, "precision": round(rj / (a + rj), 3) if a + rj else None}
    any_a = sum(bool(r["flags"]) for r in approved)
    any_r = sum(bool(r["flags"]) for r in rejected)
    summary = {"approved": len(approved), "rejected": len(rejected), "approved_flagged": any_a, "rejected_flagged": any_r,
               "precision_any": round(any_r / (any_a + any_r), 3) if any_a + any_r else None,
               "recall_any": round(any_r / len(rejected), 3) if rejected else None, "per_flag": per_flag,
               "by_set": {s: {"approved": sum(r["set"] == s and r["human"] == "APPROVE_TRACE" for r in rows),
                              "approved_flagged": sum(r["set"] == s and r["human"] == "APPROVE_TRACE" and bool(r["flags"]) for r in rows),
                              "rejected": sum(r["set"] == s and r["human"] == "REJECT_TRACE" for r in rows),
                              "rejected_flagged": sum(r["set"] == s and r["human"] == "REJECT_TRACE" and bool(r["flags"]) for r in rows)}
                          for s in ("R70", "M2", "M3")},
               "false_positives": [{"trace_id": r["trace_id"], "flags": r["flags"]} for r in approved if r["flags"]],
               "false_negatives": [{"trace_id": r["trace_id"], "human_reason": r["human_reason"]} for r in rejected if not r["flags"]],
               "rejected_reason_vs_flag": dict(collections.Counter(f"{r['human_reason']} -> {'flagged' if r['flags'] else 'missed'}"
                                                                   for r in rejected))}
    (HERE / "quality_gate_v1_replay.json").write_text(json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False, indent=1) + "\n",
                                                      encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    if "--replay" in sys.argv:
        replay()
