# -*- coding: utf-8 -*-
"""Track B implicit-pickup 진단(PLAN.md 7절). 모델 호출 0. 기존 27B 20 trace·v006 gold·P0 prompt만 읽는다.

    python sft_dpo_inventory/p0_sft_003_teacher27b_remaining/implicit_pickup/build_analysis.py
    # -> failure_matrix.csv, analysis.json, canonical_rationale_candidates.jsonl

- slot 판정(dimension_target, place od_role)은 parsed_output과 gold를 기계적으로 비교한다.
- thinking tag와 gold 판정은 사람(Claude)이 20 trace를 읽고 정한 값을 아래 표에 적었다(REVIEW.md 근거).
"""
import collections
import csv
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
ITEMS = ["b006-05", "b006-15", "b006-20", "b006-26"]
RAW = ROOT / "training/generated/p0_sft_003_teacher27b/raw/traces.jsonl"

S, J, C, P = "SEMANTIC_UNDERSTANDING_FAILURE", "SERIALIZATION_OMISSION", "OD_ROLE_DIM_TARGET_COLLAPSE", "PROMPT_COVERAGE_GAP"
# (item, sample_index) -> (tags, 근거 요약)
TAGS = {
    ("b006-05", 0): ([S, P], "'택시를 탄 건수'를 trip_count 이름으로만 읽음. 승차 끝은 언급 없음"),
    ("b006-05", 1): ([S, P], "'pickup이나 dropoff를 특정하지 않았으니 dimension_target을 생략(both)'이라고 명시"),
    ("b006-05", 2): ([S, P], "'택시를 탄'=trip으로만 읽음. dimension_target 검토 없음"),
    ("b006-05", 3): ([S, P], "'출발·도착 표현이 없으니 생략하면 both'라고 명시. '탄'을 승차 끝으로 보지 않음"),
    ("b006-05", 4): ([S, P], "'no od_role (no specific pickup/dropoff locations)'. 승차 끝 인식 없음"),
    ("b006-15", 0): ([S, P], "prompt의 '손님을 태운 운행=trip' 규칙을 인용해 '손님을 태운'을 trip 정의로만 읽음. 부산은 장소 조건, od_role 검토 없음"),
    ("b006-15", 1): ([S, P], "'pickup·dropoff를 특정하지 않았다'며 dimension_target 생략. 부산 od_role 검토 없음"),
    ("b006-15", 2): ([S, P], "'손님을 태운=picked up passengers'라고 번역하고도 'trip 자체'라며 생략. 부산을 EXTENT(분석 범위)로 봄"),
    ("b006-15", 3): ([S, P], "'부산 od_role? from A to B가 아니므로 불필요'라고 명시. 부산을 범위로 봄"),
    ("b006-15", 4): ([S, P], "MEASURE가 장소인지 오래 고민. '손님을 태운'은 trip 정의(prompt 인용). 부산은 검색 범위"),
    ("b006-20", 0): ([S, P], "'승차가'→dimension_target pickup은 맞춤(prompt 예시 '승차가 많은 읍면동'). 대구는 region으로만 보고 od_role 검토 없음"),
    ("b006-20", 1): ([S, P], "dimension_target pickup 맞춤. 대구는 'region that modifies the scope', od_role 검토 없음"),
    ("b006-20", 2): ([S, C, P], "od_role 규칙을 인용하고도 '대구에서는 일반 범위 조건이고 승차 부분은 dimension_target이 처리한다'며 od_role 생략 — 한 승차 신호를 한 slot에만 씀"),
    ("b006-20", 3): ([S, P], "dimension_target pickup 맞춤(prompt 예시 인용). 대구는 '전체 위치 제약', od_role 검토 없음"),
    ("b006-20", 4): ([S, P], "dimension_target pickup 맞춤. 대구는 'region qualifier', od_role 검토 없음"),
    ("b006-26", 0): ([S, P], "'손님을 태운'=trip으로만 읽음. dimension_target·od_role 검토 없음"),
    ("b006-26", 1): ([S, P], "'dimension_target은 행정구역 dimension에만 쓰고 h3에는 아니다'라고 결론(prompt에 없는 제한). 수성구 od_role 검토 없음"),
    ("b006-26", 2): ([S, P], "'h3는 pickup/dropoff 구분이 없는 공간 셀'이라며 생략. 수성구 od_role 검토 없음"),
    ("b006-26", 3): ([S, P], "'태운=trip 정의'(prompt)와 '태운=승차' 사이에서 망설이다 dimension_target pickup을 넣음. 수성구 od_role 검토 없음"),
    ("b006-26", 4): ([S, P], "'태운은 pickup인지 dropoff인지 모호하다'며 생략. 수성구 od_role 검토 없음"),
}

GOLD = {
    "b006-05": {"verdict": "CLEAR_GOLD",
                "slots": {"measure": "trip_count('택시를 탄 건수')", "place restriction": "없음", "place od_role": "해당 없음",
                          "grouping dimension": "sido('시도')", "dimension_target": "pickup — '탄'은 승차 사건이고, '시도는?'은 한 끝의 시도 하나를 묻는다(both 조합으로는 시도 하나가 답이 될 수 없다)",
                          "order": "top('가장 많은')", "limit": "1('시도는?' 단수)"},
                "note": "언어상 분명하다. 다만 P0 prompt에 사건 동사(탄·태운)로 묶는 끝을 정하는 예가 없고, '손님을 태운 운행'을 trip 이름으로 드는 규칙과 겹친다."},
    "b006-15": {"verdict": "CLEAR_GOLD",
                "slots": {"measure": "trip_count('손님을 태운 건수')", "place restriction": "부산",
                          "place od_role": "pickup — '부산에서'는 '태운'(승차 사건)이 일어난 곳을 제한한다. 장소 제한의 끝이다",
                          "grouping dimension": "sigungu('구')", "dimension_target": "pickup — 묶는 끝도 '태운' 사건의 끝이다. 장소 제한과는 따로 판단해도 같은 끝이다",
                          "order": "bottom('가장 적은')", "limit": "2('두 곳')"},
                "note": "od_role은 계약(P0 '출발·도착이 드러나는 질문에서는 각 장소 개념에 od_role을 반드시')상 필수다. '부산 안의 구'라는 범위로 읽어도 승차 끝 기준이면 같은 결과지만, 계약은 od_role 없는 표현을 허용하지 않는다."},
    "b006-20": {"verdict": "CLEAR_GOLD",
                "slots": {"measure": "trip_count('승차')", "place restriction": "대구",
                          "place od_role": "pickup — '대구에서 승차'는 'A에서 출발'과 같은 꼴이다",
                          "grouping dimension": "sigungu('구')", "dimension_target": "pickup — '승차가 가장 적었던 구'(prompt 예시 '승차가 많은 읍면동'과 같은 꼴)",
                          "order": "bottom('가장 적었던')", "limit": "1('구는?' 단수)"},
                "note": "dimension_target은 prompt 예시로 덮여 27B가 5/5 맞혔다. od_role 쪽 예시는 '출발/도착' 동사뿐이라 '승차'와 이어지지 않았다."},
    "b006-26": {"verdict": "CLEAR_GOLD",
                "slots": {"measure": "trip_count('손님을 가장 적게 태운')", "place restriction": "대구 수성구",
                          "place od_role": "pickup — '수성구에서 손님을 태운'은 승차 사건의 위치 제한이다",
                          "grouping dimension": "h3('H3 셀')", "dimension_target": "pickup — 셀도 '태운' 사건의 끝 기준으로 묶는다. P0 정의는 trip을 dimension으로 나누는 모든 경우에 적용되고 h3를 빼지 않는다",
                          "order": "bottom('가장 적게')", "limit": "3('세 곳')"},
                "note": "27B는 'dimension_target은 행정구역 dimension에만'이라는 prompt에 없는 제한을 두 번 만들었다. v006에서 h3 + dimension_target 조합은 다른 문항(b006-17, b006-24)에서 27B가 맞혔다."},
}

RATIONALE = {
    "b006-05": {"measure": "trip_count", "place restriction": "없음", "od_role": "없음(장소 없음)", "grouping dimension": "sido",
                "dimension_target": "pickup", "order": "top, limit 1",
                "bridge": "'택시를 탄'은 승차 사건이므로 시도는 승차한 끝 기준으로 묶는다. '시도는?'은 한 끝의 시도 하나를 묻기 때문에 조합(both)이 아니다."},
    "b006-15": {"measure": "trip_count", "place restriction": "부산", "od_role": "pickup", "grouping dimension": "sigungu",
                "dimension_target": "pickup", "order": "bottom, limit 2",
                "bridge": "'손님을 태운'은 승차 사건이므로 구는 승차 끝 기준으로 묶는다. '부산에서'가 그 승차 위치를 제한하므로 부산의 od_role도 pickup이다. 두 판단은 따로 하지만 결론은 같은 끝이다."},
    "b006-20": {"measure": "trip_count", "place restriction": "대구", "od_role": "pickup", "grouping dimension": "sigungu",
                "dimension_target": "pickup", "order": "bottom, limit 1",
                "bridge": "'승차가 가장 적었던 구'는 승차 끝 기준으로 구를 묶는다. '대구에서 승차'는 'A에서 출발'처럼 승차 위치를 제한하므로 대구의 od_role도 pickup이다."},
    "b006-26": {"measure": "trip_count", "place restriction": "대구 수성구", "od_role": "pickup", "grouping dimension": "h3",
                "dimension_target": "pickup", "order": "bottom, limit 3",
                "bridge": "'손님을 태운'은 승차 사건이므로 H3 셀도 승차 끝 기준으로 묶는다. '수성구에서'가 그 승차 위치를 제한하므로 수성구의 od_role도 pickup이다."},
}


def place_role(payload, name_hint):
    for c in (payload or {}).get("concepts") or []:
        if isinstance(c, dict) and c.get("subtype") == "place":
            return (c.get("attributes") or {}).get("od_role")
    return None


def has_place(payload):
    return any(isinstance(c, dict) and c.get("subtype") == "place" for c in (payload or {}).get("concepts") or [])


def slot(pred, gold):
    if gold is None:
        return "na"
    return "correct" if pred == gold else "omitted" if pred is None else "wrong"


def main():
    v006 = {json.loads(x)["metadata"]["source_record_id"]: json.loads(x) for x in
            (ROOT / "training/generated/reviewed_gold_v006_p0/sft_train.jsonl").read_text(encoding="utf-8").splitlines()}
    rows = [json.loads(x) for x in RAW.read_text(encoding="utf-8").splitlines() if x.strip()]
    rows = [r for r in rows if r["item_id"] in ITEMS]
    if len(rows) != 20:
        raise SystemExit(f"trace 수 {len(rows)} != 20")
    matrix = []
    for r in sorted(rows, key=lambda r: (ITEMS.index(r["item_id"]), r["sample_index"])):
        g = json.loads(v006[r["item_id"]]["messages"][2]["content"])
        p = r["parsed_output"]
        dt = slot((p.get("factors") or {}).get("dimension_target"), (g.get("factors") or {}).get("dimension_target"))
        od = slot(place_role(p, None), place_role(g, None)) if has_place(g) else "na"
        both = "both_correct" if dt in ("correct", "na") and od in ("correct", "na") else "both_wrong" if dt != "correct" and od not in ("correct", "na") else "one_wrong"
        others_ok = {k: v for k, v in (p.get("factors") or {}).items() if k != "dimension_target"} == \
            {k: v for k, v in (g.get("factors") or {}).items() if k != "dimension_target"}
        tags, why = TAGS[(r["item_id"], r["sample_index"])]
        matrix.append({"item_id": r["item_id"], "sample_index": r["sample_index"], "kind": r["kind"], "seed": r["seed"],
                       "dimension_target": dt, "od_role": od, "combined": both, "other_factors_match": others_ok,
                       "tags": tags, "reason": why})
    with open(HERE / "failure_matrix.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(matrix[0]))
        w.writeheader()
        for m in matrix:
            w.writerow({**m, "tags": "|".join(m["tags"])})
    count = lambda key: dict(collections.Counter(m[key] for m in matrix))
    per_item = {i: {"dimension_target": dict(collections.Counter(m["dimension_target"] for m in matrix if m["item_id"] == i)),
                    "od_role": dict(collections.Counter(m["od_role"] for m in matrix if m["item_id"] == i)),
                    "tags": dict(collections.Counter(t for m in matrix if m["item_id"] == i for t in m["tags"]))} for i in ITEMS}
    prompt = (ROOT / "evaluation/partial_grounding/prompts/partial_p0.yaml").read_bytes()
    doc = {"model_calls": 0, "source_traces": str(RAW.relative_to(ROOT)),
           "source_traces_sha256": hashlib.sha256(RAW.read_bytes()).hexdigest(),
           "matrix_counts": {"dimension_target": count("dimension_target"), "od_role": count("od_role"), "combined": count("combined"),
                             "other_factors_match": sum(m["other_factors_match"] for m in matrix)},
           "tag_counts": dict(collections.Counter(t for m in matrix for t in m["tags"])),
           "per_item": per_item, "gold_review": GOLD,
           "prompt_coverage": {
               "prompt_file": "evaluation/partial_grounding/prompts/partial_p0.yaml",
               "prompt_file_sha256": hashlib.sha256(prompt).hexdigest(), "modified": False,
               "dimension_target_examples": ["'승차가 많은 읍면동', '출발 지역별' → pickup", "'하차가 많은 읍면동', '도착 지역별' → dropoff",
                                             "'승하차 노선', '출발지-도착지 조합' → both", "'A에서 출발한 실차를 도착 읍면동별로' → od_role pickup, dimension_target dropoff"],
               "od_role_examples": ["'A에서 출발' → pickup", "'B에 도착' → dropoff", "'A에서 출발하여 B에 도착'", "'C 안에서 오간' → both"],
               "conflicting_cue": "'실차', '실차 구간', '손님을 태운 운행'이 이 분석 대상을 가리키면 trip — 27B는 이 규칙을 인용해 '태운'을 끝 정보 없는 trip 이름으로 읽었다(b006-15 5/5, b006-26 다수)",
               "gaps": ["사건 동사(탄·태운·승차가)로 묶는 끝을 정하는 예가 '승차가 많은 읍면동' 하나뿐이다. '탄/태운' 예가 없다",
                        "od_role 예가 '출발/도착' 동사뿐이다. 'A에서 승차', 'A에서 손님을 태운'이 장소 제한의 끝이라는 예가 없다",
                        "dimension_target과 h3 조합 예가 없다. 27B는 '행정구역 dimension에만'이라고 추론했다(2/5)",
                        "'장소 제한 끝'과 '묶는 끝'이 같은 사건에서 동시에 정해지는 예(둘 다 pickup)가 없다. 예시는 서로 다른 끝(pickup/dropoff)뿐이다"]},
           "canonical_rationale_candidates": len(RATIONALE), "training_inclusion": False, "counted_in_coverage": False}
    (HERE / "analysis.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    with open(HERE / "canonical_rationale_candidates.jsonl", "w", encoding="utf-8") as f:
        for i in ITEMS:
            if GOLD[i]["verdict"] != "CLEAR_GOLD":
                continue
            f.write(json.dumps({"item_id": i, "question": v006[i]["messages"][1]["content"], "gold_verdict": GOLD[i]["verdict"],
                                "rationale": RATIONALE[i], "author": "Claude(사람 작성 후보)", "training_inclusion": False,
                                "counted_in_coverage": False, "replaces_teacher_trace": False,
                                "status": "CANDIDATE_ONLY(학습 포함 여부는 별도 결정)"}, ensure_ascii=False) + "\n")
    print(json.dumps({k: doc[k] for k in ("matrix_counts", "tag_counts", "per_item")}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
