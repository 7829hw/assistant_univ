# -*- coding: utf-8 -*-
"""P0 SFT 보강 초안(batch006, Claude, 2026-10-13). 질문·Full 초안 gold·근거는 여기 손으로 적었다. 승인이 아니다(결정 45).

    python sft_dpo_inventory/batch006/write_drafts.py   # -> candidates_draft.yaml

- Gap A: 사건 표현형 dimension_target("승차가 가장 많은", "내린 곳", "탄 위치")
- Gap B: 장소 제한(od_role)과 grouping 끝(dimension_target)이 다른 경우
- Gap C: scope 역조회(답이 될 장소 concept 유지)
- gold는 Full contract로 적고 P0 target은 결정적 변환기로 만든다(따로 적지 않는다).
- 구조(측정값·od_role·dimension·dimension_target·order 조합)는 보호 family와 겹치지 않는 조합에서 골랐다. 문장은 평가셋 문장을
  따르지 않고 새로 썼다. 장소는 mock 실행기가 아는 이름만 쓴다. 한 장소가 양 끝을 거르면 장소 하나 od_role=both(결정 47).
- pair가 같은 후보는 끝점 하나만 바꾼 최소 대조쌍이다.
"""
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent


def place(pid, text, name, region, od=None):
    c = {"id": pid, "text": text, "concept": "LOCATION", "subtype": "place", "role": "SUBCOND", "source": "user",
         "value": {"name": name, "region": region}}
    if od:
        c["attributes"] = {"od_role": od}
    return c


def trips(places, mtext, factors):
    cs = list(places) + [
        {"id": "trip", "concept": "EVENT", "subtype": "trip", "role": "SUPPORT", "source": "implicit"},
        {"id": "measure", "text": mtext, "concept": "AMOUNT", "subtype": "trip_count", "role": "MEASURE",
         "source": "implicit"}]
    return {"concepts": cs, "factors": factors}


def scope_name(text, scope):
    return {"concepts": [
        {"id": "scope", "text": text, "concept": "LOCATION", "subtype": "scope", "role": "COND", "source": "user",
         "value": scope},
        {"id": "answer", "concept": "LOCATION", "subtype": "place", "role": "MEASURE", "source": "implicit"}],
        "factors": {}}


C = []


def add(gap, pair, q, why, g):
    C.append({"id": f"b006-{len(C) + 1:02d}", "gap": gap, "pair": pair, "question": q, "rationale": why, "gold": g})


def grp(dim, dt, order=None, limit=None, **extra):
    f = {"dimension": dim, "dimension_target": dt, **extra}
    if order:
        f.update(order=order, limit=limit)
    return f


# ---- Gap A: 사건 표현형 dimension_target (26)
add("A", "a1", "지난주 손님을 태운 위치를 H3 셀 단위로 나눠서 보여줘",
    "손님을 태운 위치=승차 끝으로 묶음 → dimension_target pickup. 장소 제한 없음.",
    trips([], "손님을 태운", grp("h3", "pickup", date="last_week")))
add("A", "a1", "지난주 손님을 내려준 위치를 H3 셀 단위로 나눠서 보여줘",
    "a1 대조: 내려준 위치=하차 끝 → dropoff.",
    trips([], "손님을 내려준", grp("h3", "dropoff", date="last_week")))
add("A", "a2", "이번 달 하차가 가장 많이 몰린 H3 셀 다섯 개는?",
    "하차가 몰린 셀=하차 끝 기준 묶음. 가장 많이 다섯=top 5.",
    trips([], "하차", grp("h3", "dropoff", "top", 5, date="this_month")))
add("A", "a2", "이번 달 승차가 가장 드물었던 H3 셀 다섯 개는?",
    "a2 대조(끝점·방향): 승차가 드문 셀=승차 끝, bottom 5.",
    trips([], "승차", grp("h3", "pickup", "bottom", 5, date="this_month")))
add("A", "a3", "지난달 택시를 탄 건수가 가장 많은 시도는?",
    "택시를 탄 건수의 시도=승차 끝 시도. 하나=limit 1.",
    trips([], "택시를 탄 건수", grp("sido", "pickup", "top", 1, date="last_month")))
add("A", "a3", "지난달 택시에서 내린 건수가 가장 많은 시도는?",
    "a3 대조: 내린 건수의 시도=하차 끝.",
    trips([], "택시에서 내린 건수", grp("sido", "dropoff", "top", 1, date="last_month")))
add("A", None, "2026년 8월 실차 하차가 가장 적었던 시도 두 곳은?",
    "하차가 적은 시도=하차 끝, bottom 2. 8월=20260801-20260831.",
    trips([], "실차 하차", grp("sido", "dropoff", "bottom", 2, date="20260801-20260831")))
add("A", None, "지난주 실차가 가장 적게 출발한 읍면동 세 곳은?",
    "출발한 읍면동=승차 끝 기준. bottom 3.",
    trips([], "실차", grp("emd", "pickup", "bottom", 3, date="last_week")))
add("A", None, "지난주 어디서 타서 어디서 내렸는지를 동 단위 짝으로 묶었을 때 가장 드문 세 가지는?",
    "탄 곳과 내린 곳의 짝=승차지-하차지 조합 → dimension_target both. 동 단위=emd. bottom 3.",
    trips([], "실차", grp("emd", "both", "bottom", 3, date="last_week")))
add("A", "a4", "이번 주 실차가 출발한 곳을 시군구 단위로 나눠 건수를 보여줘",
    "출발한 곳을 단위로 나눔=승차 끝 grouping, 순위 없음.",
    trips([], "건수", grp("sigungu", "pickup", date="this_week")))
add("A", "a4", "이번 주 실차가 도착한 곳을 시군구 단위로 나눠 건수를 보여줘",
    "a4 대조: 도착한 곳=하차 끝.",
    trips([], "건수", grp("sigungu", "dropoff", date="this_week")))
add("A", "a5", "지난달 대구 수성구에서 손님이 탄 위치를 H3 셀로 나눠 실차 건수를 보여줘",
    "수성구에서 탄=장소 pickup 제한. 탄 위치로 나눔=grouping pickup(같은 끝).",
    trips([place("area", "대구 수성구", "수성구", "대구", "pickup")], "실차 건수", grp("h3", "pickup", date="last_month")))
add("A", None, "이번 주 부산 수영구에서 승차가 가장 뜸했던 H3 셀 두 곳은?",
    "수영구에서 승차=pickup 제한, 승차가 뜸한 셀=pickup grouping, 뜸했던=bottom.",
    trips([place("area", "부산 수영구", "수영구", "부산", "pickup")], "승차", grp("h3", "pickup", "bottom", 2, date="this_week")))
add("A", None, "지난주 대구에서 실차가 출발한 곳을 구 단위로 나눠 보여줘",
    "대구에서 출발=pickup 제한, 출발한 곳을 구로 나눔=pickup grouping(sigungu).",
    trips([place("area", "대구", "대구", "", "pickup")], "실차", grp("sigungu", "pickup", date="last_week")))
add("A", "a6", "2026년 8월 부산에서 손님을 태운 건수가 가장 적은 구 두 곳은?",
    "부산에서 태움=pickup 제한, 태운 건수의 구=pickup grouping, bottom 2.",
    trips([place("area", "부산", "부산", "", "pickup")], "손님을 태운 건수", grp("sigungu", "pickup", "bottom", 2, date="20260801-20260831")))
add("A", None, "지난달 대구 달서구에 도착한 실차가 정확히 어디서 끝났는지 H3 셀 단위로 보여줘",
    "달서구에 도착=dropoff 제한, 끝난 곳=dropoff grouping(h3).",
    trips([place("area", "대구 달서구", "달서구", "대구", "dropoff")], "실차", grp("h3", "dropoff", date="last_month")))
add("A", None, "이번 달 부산 부산진구로 들어온 손님들이 내린 곳 중 가장 한산한 H3 셀 세 개는?",
    "부산진구로 들어온=dropoff 제한, 내린 곳=dropoff grouping, 한산한=bottom 3.",
    trips([place("area", "부산 부산진구", "부산진구", "부산", "dropoff")], "손님", grp("h3", "dropoff", "bottom", 3, date="this_month")))
add("A", None, "지난주 부산에 도착한 실차가 가장 많이 끝난 구 세 곳은?",
    "부산에 도착=dropoff 제한, 끝난 구=dropoff grouping(sigungu), top 3.",
    trips([place("area", "부산", "부산", "", "dropoff")], "실차", grp("sigungu", "dropoff", "top", 3, date="last_week")))
add("A", "a7", "지난달 대구에서 하차가 가장 적었던 구는?",
    "대구에서 하차=dropoff 제한, 하차가 적은 구=dropoff grouping, bottom 1.",
    trips([place("area", "대구", "대구", "", "dropoff")], "하차", grp("sigungu", "dropoff", "bottom", 1, date="last_month")))
add("A", "a7", "지난달 대구에서 승차가 가장 적었던 구는?",
    "a7 대조: 대구에서 승차=pickup 제한, 승차가 적은 구=pickup grouping.",
    trips([place("area", "대구", "대구", "", "pickup")], "승차", grp("sigungu", "pickup", "bottom", 1, date="last_month")))
add("A", None, "지난달 손님이 탄 셀과 내린 셀을 짝지었을 때 가장 흔한 조합 세 개는?",
    "탄 셀과 내린 셀의 짝=조합 grouping both(h3). top 3.",
    trips([], "실차", grp("h3", "both", "top", 3, date="last_month")))
add("A", None, "지난주 동대구역으로 온 실차들이 어느 셀에서 출발해 어느 셀에서 끝났는지 짝으로 보면 가장 많은 두 가지는?",
    "동대구역으로 온=dropoff 제한. 출발 셀과 끝 셀의 짝=both grouping(h3). top 2.",
    trips([place("area", "동대구역", "동대구역", "", "dropoff")], "실차", grp("h3", "both", "top", 2, date="last_week")))
add("A", None, "2026년 9월 1일 하루 동안 실차가 어느 동에서 시작됐는지 건수로 보여줘",
    "시작된 동=승차 끝 grouping(emd), 순위 없음. 날짜 20260901.",
    trips([], "건수", grp("emd", "pickup", date="20260901")))
add("A", "a8", "2026년 9월 1일부터 7일까지 손님을 태운 H3 셀 중 가장 적었던 세 곳은?",
    "손님을 태운 셀=pickup grouping, bottom 3. (초안 수정: get_trip_count는 taxi_type을 받지 않아 개인택시 조건을 뺐다)",
    trips([], "손님을 태운", grp("h3", "pickup", "bottom", 3, date="20260901-20260907")))
add("A", "a8", "2026년 9월 1일부터 7일까지 손님을 내려준 H3 셀 중 가장 적었던 세 곳은?",
    "a8 대조: 내려준 셀=dropoff grouping.",
    trips([], "손님을 내려준", grp("h3", "dropoff", "bottom", 3, date="20260901-20260907")))
add("A", None, "이번 달 대구 수성구에서 손님을 태운 곳 가운데 실차가 가장 적게 시작된 H3 셀 세 곳은?",
    "수성구에서 태움=pickup 제한, 시작된 셀=pickup grouping, bottom 3.",
    trips([place("area", "대구 수성구", "수성구", "대구", "pickup")], "실차", grp("h3", "pickup", "bottom", 3, date="this_month")))

# ---- Gap B: od_role ≠ dimension_target (17)
add("B", "b1", "지난달 동성로에서 손님을 태운 택시가 손님을 내려준 위치를 H3 셀로 나눠 보여줘",
    "동성로에서 태움=pickup 제한. 내려준 위치로 나눔=dropoff grouping. 두 축이 다르다.",
    trips([place("area", "동성로", "동성로", "", "pickup")], "택시", grp("h3", "dropoff", date="last_month")))
add("B", "b1", "지난달 동성로에서 내린 손님들이 어느 H3 셀에서 탔는지, 가장 많은 다섯 곳은?",
    "b1 대조: 동성로에서 내림=dropoff 제한, 탄 셀=pickup grouping. top 5.",
    trips([place("area", "동성로", "동성로", "", "dropoff")], "손님", grp("h3", "pickup", "top", 5, date="last_month")))
add("B", "b2", "이번 주 동대구역에서 출발한 실차가 가장 많이 도착한 H3 셀 세 개는?",
    "동대구역에서 출발=pickup 제한, 도착한 셀=dropoff grouping, top 3.",
    trips([place("area", "동대구역", "동대구역", "", "pickup")], "실차", grp("h3", "dropoff", "top", 3, date="this_week")))
add("B", "b2", "이번 주 동대구역에 도착한 실차가 출발한 곳 중 가장 드문 H3 셀 세 개는?",
    "b2 대조: 동대구역에 도착=dropoff 제한, 출발한 곳=pickup grouping, bottom 3.",
    trips([place("area", "동대구역", "동대구역", "", "dropoff")], "실차", grp("h3", "pickup", "bottom", 3, date="this_week")))
add("B", "b3", "2026년 8월 대구에서 출발한 실차가 내린 시도 중 가장 적은 두 곳은?",
    "대구에서 출발=pickup 제한, 내린 시도=dropoff grouping(sido), bottom 2.",
    trips([place("area", "대구", "대구", "", "pickup")], "실차", grp("sido", "dropoff", "bottom", 2, date="20260801-20260831")))
add("B", "b3", "2026년 8월 부산에 도착한 실차가 어느 시도에서 출발했는지 가장 많은 세 곳은?",
    "b3 대조: 부산에 도착=dropoff 제한, 출발한 시도=pickup grouping, top 3.",
    trips([place("area", "부산", "부산", "", "dropoff")], "실차", grp("sido", "pickup", "top", 3, date="20260801-20260831")))
add("B", None, "지난달 대구로 들어온 실차를 출발한 시도 기준으로 나눠 보여줘",
    "대구로 들어온=dropoff 제한, 출발한 시도=pickup grouping, 순위 없음.",
    trips([place("area", "대구", "대구", "", "dropoff")], "실차", grp("sido", "pickup", date="last_month")))
add("B", None, "지난달 대구 수성구에서 탄 손님들이 내린 곳 중 가장 드문 H3 셀 두 곳은?",
    "수성구에서 탄=pickup 제한, 내린 곳=dropoff grouping, bottom 2.",
    trips([place("area", "대구 수성구", "수성구", "대구", "pickup")], "손님", grp("h3", "dropoff", "bottom", 2, date="last_month")))
add("B", None, "지난주 대구 중구에 도착한 실차가 어느 구에서 출발했는지 구 단위로 보여줘",
    "중구에 도착=dropoff 제한, 출발한 구=pickup grouping(sigungu).",
    trips([place("area", "대구 중구", "중구", "대구", "dropoff")], "실차", grp("sigungu", "pickup", date="last_week")))
add("B", "b4", "이번 달 부산 수영구에서 내린 손님들이 탄 동을 기준으로 실차 건수를 나눠 줘",
    "수영구에서 내림=dropoff 제한, 탄 동=pickup grouping(emd).",
    trips([place("area", "부산 수영구", "수영구", "부산", "dropoff")], "실차 건수", grp("emd", "pickup", date="this_month")))
add("B", "b4", "이번 달 부산 수영구에서 탄 손님들이 내린 셀을 기준으로 실차 건수를 나눠 줘",
    "b4 대조(끝점 교대, 단위는 h3): 수영구에서 탐=pickup 제한, 내린 셀=dropoff grouping.",
    trips([place("area", "부산 수영구", "수영구", "부산", "pickup")], "실차 건수", grp("h3", "dropoff", date="this_month")))
add("B", None, "이번 주 대구 중구 안에서만 오간 실차를 도착한 H3 셀 기준으로 나눠 보여줘",
    "중구 안에서만 오감=양 끝 제한(od_role both, 결정 47). 도착한 셀=dropoff grouping.",
    trips([place("area", "대구 중구", "중구", "대구", "both")], "실차", grp("h3", "dropoff", date="this_week")))
add("B", None, "지난달 부산진구 안에서 출발과 도착이 모두 이뤄진 운행 중 출발이 가장 많았던 H3 셀 세 개는?",
    "출발·도착 모두 부산진구 안=both 제한. 출발이 많은 셀=pickup grouping, top 3.",
    trips([place("area", "부산진구", "부산진구", "", "both")], "운행", grp("h3", "pickup", "top", 3, date="last_month")))
add("B", "b5", "지난주 대구에서 출발해 부산에 도착한 실차를 출발 지점의 H3 셀로 나눠 보여줘",
    "대구=pickup 제한, 부산=dropoff 제한. 출발 지점 셀=pickup grouping.",
    trips([place("origin", "대구", "대구", "", "pickup"), place("destination", "부산", "부산", "", "dropoff")], "실차",
          grp("h3", "pickup", date="last_week")))
add("B", "b5", "지난주 대구에서 출발해 부산에 도착한 실차가 끝난 곳을 H3 셀 기준으로 볼 때 가장 많은 다섯 곳은?",
    "b5 대조: 같은 제한, 끝난 곳=dropoff grouping, top 5.",
    trips([place("origin", "대구", "대구", "", "pickup"), place("destination", "부산", "부산", "", "dropoff")], "실차",
          grp("h3", "dropoff", "top", 5, date="last_week")))
add("B", "b6", "지난달 부산 광안리에서 태운 손님을 내려준 위치 중 가장 많은 H3 셀 세 개는?",
    "광안리에서 태움=pickup 제한, 내려준 위치=dropoff grouping. (초안 수정: 법인택시 조건은 get_trip_count가 받지 않아 뺐다)",
    trips([place("area", "광안리", "광안리", "부산", "pickup")], "손님", grp("h3", "dropoff", "top", 3, date="last_month")))
add("B", "b6", "지난달 부산 광안리에 내려준 손님을 태웠던 위치 중 가장 많은 H3 셀 세 개는?",
    "b6 대조: 광안리에 내려줌=dropoff 제한, 태웠던 위치=pickup grouping.",
    trips([place("area", "광안리", "광안리", "부산", "dropoff")], "손님", grp("h3", "pickup", "top", 3, date="last_month")))

# ---- Gap C: scope 역조회 (10)
for text, q in [
        ("scope:district:2726000000", "scope:district:2726000000은 어느 구를 가리켜?"),
        ("scope:edge:11234", "scope:edge:11234가 무슨 장소인지 알려줘"),
        ("scope:district:2729010100", "보고서에 scope:district:2729010100이라고 적혀 있는데 어느 동이야?"),
        ("scope:gz:33212", "scope:gz:33212는 어디야?"),
        ("scope:district:2650000000", "scope:district:2650000000의 지역 이름은?"),
        ("scope:district:2623000000", "scope:district:2623000000이 가리키는 곳 이름 좀 알려줘"),
        ("scope:edge:1742", "scope:edge:1742는 어떤 거리야?"),
        ("scope:district:2723510100", "scope:district:2723510100은 무슨 동이지?"),
        ("scope:district:2700000000", "scope:district:2700000000이 어느 시도인지 알려 줘"),
        ("scope:district:2650010400", "집계 결과에 나온 scope:district:2650010400이 어디인지 이름으로 알려줘")]:
    add("C", None, q, "질문의 scope id=사용자 scope(COND). 구하려는 값=장소 이름 → 값 없는 place(MEASURE)를 남긴다.",
        scope_name(text, text))


def main():
    doc = {"batch": "b006", "reference_date": "2026-09-25", "author": "Claude 초안(승인 아님, 결정 45)", "candidates": C}
    (HERE / "candidates_draft.yaml").write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8")
    from collections import Counter
    print(len(C), Counter(c["gap"] for c in C))


if __name__ == "__main__":
    main()
