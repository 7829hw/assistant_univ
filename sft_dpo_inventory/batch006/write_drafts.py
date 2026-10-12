# -*- coding: utf-8 -*-
"""batch006 초안 28건을 쓴 스크립트(Claude, 2026-10-12). 질문·초안 gold·근거는 여기 손으로 적은 것이다. 승인이 아니다.

    python sft_dpo_inventory/batch006/write_drafts.py  # -> candidates_draft.yaml

결정 66(H): "실차 통행량" 대조 묶음. 의도(intent) 7개마다 같은 장소·날짜·시간·묶음 기준으로 네 가지 대조를 만든다.
- occupied: 실차 통행량 = passage_count + taxi_status occupied
- vacant:   공차 통행량 = passage_count + taxi_status vacant
- plain:    상태 없는 통행량 = passage_count(taxi_status 없음)
- trip:     실차 건수 = trip_count(실차 = 승객을 태운 구간 자체이므로 taxi_status를 붙이지 않는다)
근거: 학습 데이터(reviewed_gold_v005_t2pc)에 passage_count + occupied 정답이 0개이고, "실차"가 든 질문의 정답은 trip_count뿐이다
(``../selection_decline/PASSAGE_STATUS.md`` 2절). valid98 h30에서 HF-base가 실차 통행량을 trip_count로 읽었다.
업체 100과 selection 셋의 문항에서 파생하지 않았다(그 문장을 보거나 바꿔 쓰지 않았다).
"""
import yaml

EV = {"trip_count": "trip", "passage_count": "passage"}


def place(pid, text, name, region, od=None):
    c = {"id": pid, "text": text, "concept": "LOCATION", "subtype": "place", "role": "SUBCOND", "source": "user",
         "value": {"name": name, "region": region}}
    if od:
        c["attributes"] = {"od_role": od}
    return c


def gold(places, meas, mtext, factors):
    ev = EV[meas]
    cs = list(places) + [{"id": ev, "concept": "EVENT", "subtype": ev, "role": "SUPPORT", "source": "implicit"},
                         {"id": "measure", "text": mtext, "concept": "AMOUNT", "subtype": meas, "role": "MEASURE",
                          "source": "implicit"}]
    return {"concepts": cs, "factors": factors}


C = []


def add(n, intent, variant, q, why, g):
    C.append({"id": f"b006-{n:02d}", "type": "passage_status_contrast", "family": f"b006-{intent}", "intent": f"b006-{intent}-{variant}",
              "variant": variant, "question": q, "rationale": why, "gold": g})


P_WHY = "통행량=passage_count(EVENT passage). passage는 출발·도착이 없어 장소에 od_role을 붙이지 않는다. 묶음 기준에 dimension_target은 없다."
T_WHY = "실차 건수=trip_count(EVENT trip). 실차는 trip 자체라 taxi_status를 붙이지 않는다. 장소가 제한하는 끝=od_role, 묶는 끝=dimension_target."

# ---- i1: 대구, 2026-09-03, 시군구별
f = {"date": "20260903", "dimension": "sigungu"}
add(1, "i1", "occupied", "2026년 9월 3일 대구의 시군구별 실차 통행량을 알려줘",
    "실차 통행량=passage_count + taxi_status occupied. " + P_WHY,
    gold([place("place", "대구", "대구", "")], "passage_count", "실차 통행량", {**f, "taxi_status": "occupied"}))
add(2, "i1", "vacant", "2026년 9월 3일 대구의 시군구별 공차 통행량을 알려줘",
    "공차 통행량=passage_count + taxi_status vacant. " + P_WHY,
    gold([place("place", "대구", "대구", "")], "passage_count", "공차 통행량", {**f, "taxi_status": "vacant"}))
add(3, "i1", "plain", "2026년 9월 3일 대구의 시군구별 택시 통행량을 알려줘",
    "운행 상태가 없는 통행량=passage_count만. taxi_status를 만들지 않는다. " + P_WHY,
    gold([place("place", "대구", "대구", "")], "passage_count", "택시 통행량", dict(f)))
add(4, "i1", "trip", "2026년 9월 3일 대구에서 출발한 실차 건수를 출발 시군구별로 알려줘",
    "대구에서 출발=od_role pickup, 출발 시군구별=dimension sigungu, dimension_target pickup. " + T_WHY,
    gold([place("origin", "대구", "대구", "", "pickup")], "trip_count", "실차 건수",
         {**f, "dimension_target": "pickup"}))

# ---- i2: 부산, 이번 달, 시군구별
f = {"date": "this_month", "dimension": "sigungu"}
add(5, "i2", "occupied", "이번 달 부산 시군구별로 손님을 태운 택시의 통행량은?",
    "손님을 태운 택시의 통행량=실차 통행량(passage_count + occupied). " + P_WHY,
    gold([place("place", "부산", "부산", "")], "passage_count", "손님을 태운 택시의 통행량", {**f, "taxi_status": "occupied"}))
add(6, "i2", "vacant", "이번 달 부산 시군구별로 빈 택시의 통행량은?",
    "빈 택시의 통행량=공차 통행량(passage_count + vacant). " + P_WHY,
    gold([place("place", "부산", "부산", "")], "passage_count", "빈 택시의 통행량", {**f, "taxi_status": "vacant"}))
add(7, "i2", "plain", "이번 달 부산 시군구별 택시 통행량은?",
    "상태 없는 통행량. " + P_WHY,
    gold([place("place", "부산", "부산", "")], "passage_count", "택시 통행량", dict(f)))
add(8, "i2", "trip", "이번 달 부산 안에서 출발해 부산 안에서 도착한 실차 건수를 도착 시군구별로 보여줘",
    "출발·도착 모두 부산 안=od_role both(장소 하나), 도착 시군구별=dimension_target dropoff. " + T_WHY,
    gold([place("area", "부산", "부산", "", "both")], "trip_count", "실차 건수", {**f, "dimension_target": "dropoff"}))

# ---- i3: 대구 동성로, 지난주 18–20시, H3 셀별
f = {"date": "last_week", "time": "180000-200000", "dimension": "h3"}
add(9, "i3", "occupied", "지난주 오후 6시부터 8시까지 대구 동성로의 H3 셀별 실차 통행량은?",
    "실차 통행량=passage_count + occupied. 시간 180000-200000. " + P_WHY,
    gold([place("place", "동성로", "동성로", "대구")], "passage_count", "실차 통행량", {**f, "taxi_status": "occupied"}))
add(10, "i3", "vacant", "지난주 오후 6시부터 8시까지 대구 동성로의 H3 셀별 공차 통행량은?",
    "공차 통행량=passage_count + vacant. " + P_WHY,
    gold([place("place", "동성로", "동성로", "대구")], "passage_count", "공차 통행량", {**f, "taxi_status": "vacant"}))
add(11, "i3", "plain", "지난주 오후 6시부터 8시까지 대구 동성로를 지나간 택시 통행량을 H3 셀별로 알려줘",
    "지나간 택시 통행량=passage_count, 상태 없음. " + P_WHY,
    gold([place("place", "동성로", "동성로", "대구")], "passage_count", "택시 통행량", dict(f)))
add(12, "i3", "trip", "지난주 오후 6시부터 8시까지 대구 동성로에서 출발한 실차 건수를 출발 H3 셀별로 알려줘",
    "동성로에서 출발=pickup, 출발 H3 셀별=dimension h3, dimension_target pickup. " + T_WHY,
    gold([place("origin", "동성로", "동성로", "대구", "pickup")], "trip_count", "실차 건수",
         {**f, "dimension_target": "pickup"}))

# ---- i4: 부산 광안리 주변, 2026-08-15 20–22시, H3 셀별 + vicinity
f = {"date": "20260815", "time": "200000-220000", "dimension": "h3", "vicinity": True}
add(13, "i4", "occupied", "2026년 8월 15일 오후 8시부터 10시까지 부산 광안리 주변 H3 셀별 실차 통행량은?",
    "주변→vicinity. 실차 통행량=passage_count + occupied. " + P_WHY,
    gold([place("place", "광안리", "광안리", "부산")], "passage_count", "실차 통행량", {**f, "taxi_status": "occupied"}))
add(14, "i4", "vacant", "2026년 8월 15일 오후 8시부터 10시까지 부산 광안리 주변 H3 셀별 공차 통행량은?",
    "주변→vicinity. 공차 통행량=passage_count + vacant. " + P_WHY,
    gold([place("place", "광안리", "광안리", "부산")], "passage_count", "공차 통행량", {**f, "taxi_status": "vacant"}))
add(15, "i4", "plain", "2026년 8월 15일 오후 8시부터 10시까지 부산 광안리 주변 H3 셀별 통행량은?",
    "주변→vicinity. 상태 없는 통행량. " + P_WHY,
    gold([place("place", "광안리", "광안리", "부산")], "passage_count", "통행량", dict(f)))
add(16, "i4", "trip", "2026년 8월 15일 오후 8시부터 10시까지 부산 광안리 주변에 도착한 실차 건수를 출발 H3 셀별로 보여줘",
    "광안리 주변에 도착=dropoff + vicinity, 출발 H3 셀별=dimension_target pickup. " + T_WHY,
    gold([place("destination", "광안리", "광안리", "부산", "dropoff")], "trip_count", "실차 건수",
         {**f, "dimension_target": "pickup"}))

# ---- i5: 동대구역 근처, 2026-09-21, H3 셀별 + vicinity
f = {"date": "20260921", "dimension": "h3", "vicinity": True}
add(17, "i5", "occupied", "2026년 9월 21일 동대구역 근처의 실차 통행량을 H3 셀별로 보여줘",
    "근처→vicinity. 지역이 발화에 없어 region 빈 값. 실차 통행량=passage_count + occupied. " + P_WHY,
    gold([place("place", "동대구역", "동대구역", "")], "passage_count", "실차 통행량", {**f, "taxi_status": "occupied"}))
add(18, "i5", "vacant", "2026년 9월 21일 동대구역 근처의 공차 통행량을 H3 셀별로 보여줘",
    "근처→vicinity. 공차 통행량=passage_count + vacant. " + P_WHY,
    gold([place("place", "동대구역", "동대구역", "")], "passage_count", "공차 통행량", {**f, "taxi_status": "vacant"}))
add(19, "i5", "plain", "2026년 9월 21일 동대구역 근처의 택시 통행량을 H3 셀별로 보여줘",
    "근처→vicinity. 상태 없는 통행량. " + P_WHY,
    gold([place("place", "동대구역", "동대구역", "")], "passage_count", "택시 통행량", dict(f)))
add(20, "i5", "trip", "2026년 9월 21일 동대구역 근처에서 승객을 태운 실차 건수를 승차 H3 셀별로 보여줘",
    "동대구역 근처에서 승객을 태움=pickup + vicinity, 승차 H3 셀별=dimension_target pickup. " + T_WHY,
    gold([place("origin", "동대구역", "동대구역", "", "pickup")], "trip_count", "실차 건수",
         {**f, "dimension_target": "pickup"}))

# ---- i6: 부산 부산진구, 2026년 7월, H3 셀별
f = {"date": "20260701-20260731", "dimension": "h3"}
add(21, "i6", "occupied", "2026년 7월 부산 부산진구의 H3 셀별 실차 통행량을 알려줘",
    "7월=20260701-20260731. 실차 통행량=passage_count + occupied. " + P_WHY,
    gold([place("place", "부산진구", "부산진구", "부산")], "passage_count", "실차 통행량", {**f, "taxi_status": "occupied"}))
add(22, "i6", "vacant", "2026년 7월 부산 부산진구의 H3 셀별 공차 통행량을 알려줘",
    "공차 통행량=passage_count + vacant. " + P_WHY,
    gold([place("place", "부산진구", "부산진구", "부산")], "passage_count", "공차 통행량", {**f, "taxi_status": "vacant"}))
add(23, "i6", "plain", "2026년 7월 부산 부산진구의 H3 셀별 택시 통행량을 알려줘",
    "상태 없는 통행량. " + P_WHY,
    gold([place("place", "부산진구", "부산진구", "부산")], "passage_count", "택시 통행량", dict(f)))
add(24, "i6", "trip", "2026년 7월 부산 부산진구 안에서만 오간 실차 건수를 도착 H3 셀별로 알려줘",
    "안에서만 오간=od_role both, 도착 H3 셀별=dimension_target dropoff. " + T_WHY,
    gold([place("area", "부산진구", "부산진구", "부산", "both")], "trip_count", "실차 건수",
         {**f, "dimension_target": "dropoff"}))

# ---- i7: 대구 수성구, 2026-09-12~14 오전 7–9시, H3 셀별
f = {"date": "20260912-20260914", "time": "070000-090000", "dimension": "h3"}
add(25, "i7", "occupied", "2026년 9월 12일부터 14일까지 오전 7시부터 9시 사이 대구 수성구의 실차 통행량을 H3 셀별로 알려줘",
    "날짜 범위 20260912-20260914, 시간 070000-090000. 실차 통행량=passage_count + occupied. " + P_WHY,
    gold([place("place", "수성구", "수성구", "대구")], "passage_count", "실차 통행량", {**f, "taxi_status": "occupied"}))
add(26, "i7", "vacant", "2026년 9월 12일부터 14일까지 오전 7시부터 9시 사이 대구 수성구의 빈 차 통행량을 H3 셀별로 알려줘",
    "빈 차 통행량=공차 통행량(passage_count + vacant). " + P_WHY,
    gold([place("place", "수성구", "수성구", "대구")], "passage_count", "빈 차 통행량", {**f, "taxi_status": "vacant"}))
add(27, "i7", "plain", "2026년 9월 12일부터 14일까지 오전 7시부터 9시 사이 대구 수성구의 택시 통행량을 H3 셀별로 알려줘",
    "상태 없는 통행량. " + P_WHY,
    gold([place("place", "수성구", "수성구", "대구")], "passage_count", "택시 통행량", dict(f)))
add(28, "i7", "trip", "2026년 9월 12일부터 14일까지 오전 7시부터 9시 사이 대구 수성구에 도착한 실차 건수를 도착 H3 셀별로 알려줘",
    "수성구에 도착=dropoff, 도착 H3 셀별=dimension_target dropoff. " + T_WHY,
    gold([place("destination", "수성구", "수성구", "대구", "dropoff")], "trip_count", "실차 건수",
         {**f, "dimension_target": "dropoff"}))

assert len(C) == 28
header = """# batch006 annotation 후보 초안. Claude가 2026-10-12에 새로 썼다. 사람 검토 전이며 승인이 아니다(결정 66·77).
# - 결정 66: "실차 통행량" 대조 묶음. 의도 7개 × 네 대조(occupied, vacant, plain, trip) = 28건.
# - 근거: 학습 데이터에 passage_count + occupied 정답이 0개, valid98 h30의 오독(selection_decline/PASSAGE_STATUS.md).
#   업체 100과 selection 셋의 문항 문장을 보거나 바꿔 쓰지 않았다.
# - 묶음 기준은 보호 셋 family와 겹치지 않는 것만 골랐다(시군구, H3, H3+근처). family 겹침 확인에는 보호 셋 정답의 라벨 조합만 썼다.
#   묶음 없는 통행량, 읍면동별 통행량, 순위가 붙은 통행량은 보호 family라 쓰지 않았다. 요일별·집계 통행량은 현재 계약에서 멈춰 쓰지 않았다.
# - D1–D4(evaluation/real_data/decisions.md)에 걸리는 질문(수입 기준 요일 순위, 운행일 지표, 기간 활성 택시 수, 지역 없는 동명 구)은 만들지 않았다.
# - 기준일: 2026-09-25(평가 harness와 같다).
"""
body = yaml.safe_dump({"reference_date": "2026-09-25", "candidates": C}, allow_unicode=True, sort_keys=False, width=200,
                      default_flow_style=None)
(__import__("pathlib").Path(__file__).resolve().parent / "candidates_draft.yaml").write_text(header + body, encoding="utf-8")
print("ok", len(C))
