"""dimension_target·od_role gold·계약 검토 기록(모델 호출 없음, gold 수정 없음).

판정(LABELS)은 질문 문장과 gold를 읽고 사람 기준으로 적은 검토 의견이다(사람 승인이 아니다). 근거 수치는 ab_p0_3 raw
(Full·P0·P0.3 sampling 5회)에서 계산한다.

사용: python build_review.py   (review.json, review_items.csv를 이 디렉터리에 쓴다)
"""
import collections
import csv
import json
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
AB = ROOT / "evaluation/partial_grounding/ab_p0_3"
sys.path.insert(0, str(ROOT))
ARMS = ("full", "p0", "p0_3")

#: 판정 범주: CLEAR_GOLD, AMBIGUOUS_LANGUAGE, CONTRACT_AMBIGUITY, LIKELY_GOLD_ERROR.
#: A 자연어 의미의 끝점, B od_role, C dimension_target, D 장소 scope 구조. contract_note는 문항 판정과 별개인 계약 쪽 문제.
LABELS = {
    "indepv2/n35": dict(
        label="CLEAR_GOLD", group="event_no_place",
        A="pickup. '승차 건수를 시도 단위로 비교해 제일 적은 두 곳'은 승차 지역 시도별 건수다. 생략(=both, 출발-도착 시도 짝)은 "
          "'두 곳'(장소 둘)을 답하라는 질문과 맞지 않는다.",
        B="장소 제한 없음", C="pickup", D="scope 없음",
        note="ROOT_CAUSE에서 gold_review_candidate로 표시했으나 다시 읽어 철회한다. '승차 건수'가 '이용 건수'로도 쓰이는 것은 "
             "측정값 뜻의 문제이고, 결과를 장소 둘로 답하라는 문장에서 끝점은 승차 쪽이다."),
    "indepv4/k34": dict(
        label="CLEAR_GOLD", group="intra_area", contract_note="INTRA_AREA_SERIALIZATION",
        A="grouping=dropoff('내린 구 기준'), 장소 제한=출발·도착 모두 대구('출발과 도착이 다 이뤄진')",
        B="대구: 양 끝 모두(od_role=both 하나 또는 pickup·dropoff 두 개)", C="dropoff",
        D="gold는 같은 scope를 scope_pickup·scope_dropoff 두 인자로 둔다. od_role=both 장소 하나와 Tool 호출이 같다.",
        note="모델 실패는 '출발과 도착이 다'를 dimension_target=both로 옮기거나(제한과 grouping 혼동) dimension_target 누락."),
    "contrast/c04a": dict(
        label="CLEAR_GOLD", group="intra_area", contract_note="INTRA_AREA_SERIALIZATION",
        A="장소 제한=양 끝 대구('대구 안에서 이동한'), grouping=both('읍면동 간 노선')", B="대구: both", C="both",
        D="gold 두 scope = od_role=both 하나"),
    "indepv2/n09": dict(
        label="CLEAR_GOLD", group="intra_area", contract_note="INTRA_AREA_SERIALIZATION",
        A="장소 제한=양 끝 수성구('안에서만 오간'), grouping=both('읍면동 간 노선')", B="수성구: both", C="both",
        D="gold 두 scope = od_role=both 하나"),
    "indepv4/k33": dict(
        label="CLEAR_GOLD", group="intra_area", contract_note="INTRA_AREA_SERIALIZATION",
        A="장소 제한=양 끝 중구('안에서만 움직인'), grouping=both('동에서 동으로 가는 경로'), dimension=emd", B="중구: both",
        C="both", D="gold 두 scope = od_role=both 하나"),
    "indepv2/n10": dict(
        label="CLEAR_GOLD", group="intra_area", contract_note="INTRA_AREA_SERIALIZATION",
        A="장소 제한=양 끝 부산('출발과 도착이 모두'), grouping 없음", B="부산: both", C="없음", D="gold 두 scope"),
    "indepv3/m12": dict(
        label="CLEAR_GOLD", group="intra_area", contract_note="INTRA_AREA_SERIALIZATION",
        A="장소 제한=양 끝 중구('승차와 하차가 둘 다 … 안에서'), grouping 없음", B="중구: both", C="없음", D="gold 두 scope"),
    "indepv4/k32": dict(
        label="CLEAR_GOLD", group="intra_area", contract_note="INTRA_AREA_SERIALIZATION",
        A="장소 제한=양 끝 수영구('안에서 타고 내린'), grouping 없음", B="수영구: both", C="없음", D="gold 두 scope"),
    "contrast/c04c": dict(
        label="CLEAR_GOLD", group="intra_area", contract_note="INTRA_AREA_SERIALIZATION",
        A="장소 제한=양 끝 부산('부산 안에서 이동한'), grouping 없음", B="부산: both", C="없음", D="gold 두 scope"),
    "indepv2/n05": dict(
        label="CLEAR_GOLD", group="event_same_end",
        A="dropoff('대구 안 어느 H3 셀에서 가장 많이 내렸는지')", B="대구: dropoff", C="dropoff", D="scope_dropoff 하나"),
    "indepv4/k28": dict(
        label="CLEAR_GOLD", group="event_same_end",
        A="dropoff('중구로 향한 손님들이 실제로 내린 위치를 H3 셀 기준으로')", B="중구: dropoff", C="dropoff",
        D="scope_dropoff 하나"),
    "indepv3/m03": dict(
        label="CLEAR_GOLD", group="event_same_end",
        A="dropoff('달서구에서 내린 손님이 가장 몰린 H3 셀')", B="달서구: dropoff", C="dropoff", D="scope_dropoff 하나"),
    "indepv3/m04": dict(
        label="CLEAR_GOLD", group="event_same_end",
        A="pickup('중구 가운데 택시 승차가 가장 뜸했던 동')", B="중구: pickup", C="pickup", D="scope_pickup 하나",
        note="세 arm 공통 실패의 주원인은 '가장 뜸했던'을 order=top으로 읽는 어휘 해석이다. gold의 order=bottom은 맞다."),
}


def first_payload(row):
    calls = row.get("llm_calls") or []
    text = (calls[0].get("content") or "") if calls else ""
    i, j = text.find("{"), text.rfind("}")
    try:
        payload = json.loads(text[i:j + 1])
    except ValueError:
        return None
    return payload if isinstance(payload, dict) else None


def place_pattern(payload):
    if payload is None:
        return "parse_fail"
    places = [c for c in payload.get("concepts") or [] if isinstance(c, dict)
              and c.get("subtype") in ("place", "scope") and c.get("value")]
    roles = [((c.get("attributes") or {}) if isinstance(c.get("attributes"), dict) else {}).get("od_role")
             for c in places]
    return f"{len(places)}:" + "/".join(str(r) for r in roles)


def main():
    import evaluate_vendor100 as V

    gold = {g["id"]: g for g in yaml.safe_load(open(AB / "sel154_gold.yaml"))["items"]}
    rows = collections.defaultdict(list)
    for arm in ARMS:
        for r in range(1, 6):
            for x in json.load(open(AB / "raw" / f"{arm}_sample_r{r}.json"))["rows"]:
                rows[(arm, x["id"])].append(x)
    items = []
    for item_id, label in LABELS.items():
        g = gold[item_id]
        rec = {"id": item_id, "question": g["question"], "gold_text": g["gold_text"], **label, "arms": {}}
        for arm in ARMS:
            xs = rows[(arm, item_id)]
            dt = collections.Counter()
            for x in xs:
                f = (first_payload(x) or {}).get("factors") or {}
                dt[str(f.get("dimension_target")) if isinstance(f, dict) else "?"] += 1
            rec["arms"][arm] = {
                "k": sum(x["category"] in ("match", "expected_refusal") for x in xs),
                "categories": dict(collections.Counter(x["category"] for x in xs)),
                "first_place_patterns": dict(collections.Counter(place_pattern(first_payload(x)) for x in xs)),
                "first_dimension_target": dict(dt),
                "error_codes": dict(collections.Counter(x.get("error_code") for x in xs if x.get("error_code"))),
            }
        items.append(rec)

    # grounding 비교의 표현 차이: Tool 호출은 맞았는데(match) places 차이가 od_role=both 대 pickup·dropoff 두 개뿐인 관측
    artifact = collections.Counter()
    for arm in ARMS:
        for r in range(1, 6):
            for x in json.load(open(AB / "raw" / f"{arm}_sample_r{r}.json"))["rows"]:
                diffs = x.get("grounding_diffs") or []
                if x["category"] == "match" and diffs and all(isinstance(d, list) and d[0] == "places" for d in diffs):
                    want, got = diffs[0][1], diffs[0][2]
                    if any(p[2] == "both" for p in got) and len(want) == 2 and {p[2] for p in want} == {"pickup", "dropoff"}:
                        artifact[arm] += 1
    # gold 전체에서 같은 장소가 양 끝을 거르는 문항 수(sel154)
    intra = [i for i, g in gold.items() if "$area.scope" in (g.get("gold_text") or "")]
    out = {
        "note": "사람 기준 검토 의견(승인 아님). gold는 수정하지 않았다. 근거 수치는 ab_p0_3 sampling 5회.",
        "label_counts": dict(collections.Counter(i["label"] for i in items)),
        "contract_findings": {
            "INTRA_AREA_SERIALIZATION": {
                "summary": "같은 장소가 출발·도착을 모두 거르는 질문의 표현이 셋이다: od_role=both 장소 하나, 같은 장소의 pickup·dropoff "
                           "두 개, od_role 없는 장소 하나(조건 계층이 질문의 '안에서' 등으로 보충할 때만 맞음). 앞의 둘은 Tool 호출이 같다.",
                "sel154_items": intra,
                "grounding_view_artifact_matches": dict(artifact),
                "where": "evaluate_vendor100._grounding_view가 od_role=both를 pickup·dropoff 두 장소와 같게 보지 않는다. "
                         "semantic correctness(Tool 호출 채점)에는 영향이 없고 grounding_ok·grounding_diffs에만 영향이 있다.",
            }
        },
        "items": items,
    }
    (HERE / "review.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    with open(HERE / "review_items.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "group", "label", "contract_note", "A_language", "B_od_role", "C_dimension_target",
                    "D_scope_structure", "k_full", "k_p0", "k_p0_3", "p0_3_first_place_patterns",
                    "p0_3_first_dimension_target", "note", "question"])
        for i in items:
            w.writerow([i["id"], i["group"], i["label"], i.get("contract_note", ""), i["A"], i["B"], i["C"], i["D"],
                        *(i["arms"][a]["k"] for a in ARMS),
                        json.dumps(i["arms"]["p0_3"]["first_place_patterns"], ensure_ascii=False),
                        json.dumps(i["arms"]["p0_3"]["first_dimension_target"], ensure_ascii=False),
                        i.get("note", ""), i["question"]])
    print(json.dumps({k: out[k] for k in ("label_counts",)}, ensure_ascii=False),
          json.dumps(out["contract_findings"]["INTRA_AREA_SERIALIZATION"]["grounding_view_artifact_matches"]))


if __name__ == "__main__":
    main()
