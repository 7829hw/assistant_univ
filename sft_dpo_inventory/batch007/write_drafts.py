# -*- coding: utf-8 -*-
"""batch007 초안 28건을 쓴 스크립트(Claude, 2026-10-15). 질문·초안 gold·근거는 여기 손으로 적은 것이다. 승인이 아니다(결정 104).

    python sft_dpo_inventory/batch007/write_drafts.py  # -> candidates_draft.yaml

결정 104(AR): "실차"라는 말 없이 운행 상태를 표현한 통행량 질문과, 이와 헷갈리는 대조 질문.
의도(intent) 7개마다 같은 장소·날짜·시간·묶음 기준으로 네 질문을 만든다. 대조(variant):
- occupied:     "실차" 없이 손님·승객이 탄 택시의 통행량 = passage_count + taxi_status occupied(의도마다 표현을 바꾼다)
- vacant:       빈 택시(손님 없이 다닌 택시)의 통행량 = passage_count + taxi_status vacant
- plain:        운행 상태 없는 통행량 = passage_count(taxi_status 없음)
- trip_pickup:  손님을 태운 건수 = 승차 실차 건수 = trip_count, 장소 od_role pickup, 승차 쪽으로 묶음(dimension_target pickup)
- trip_dropoff: 손님을 내려준 건수 = 하차 실차 건수 = trip_count, 장소 od_role dropoff, 하차 쪽으로 묶음(dimension_target dropoff)
계기는 selection_v2의 indepv2/n33이지만, 질문은 n33이나 보호 셋(업체 100, selection, aux, valid98)의 문장을 보거나 바꿔 쓰지 않고 새로 썼다.
batch006(b006-05 "손님을 태운 택시의 통행량", b006-06 "빈 택시의 통행량")과 같은 표현은 피했다.
장소는 mock gazetteer에 있는 이름만 썼다(대구, 부산, 광안리, 동성로, 어린이대공원, 달서구, 수영구). 기준일 2026-09-25.
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
    C.append({"id": f"b007-{n:02d}", "type": "passage_status_paraphrase", "family": f"b007-{intent}", "intent": f"b007-{intent}-{variant}-{n:02d}",
              "variant": variant, "question": q, "rationale": why, "gold": g})


P_WHY = "통행량(지나간 양)=passage_count(EVENT passage). passage는 출발·도착이 없어 장소에 od_role을 붙이지 않는다. 묶음 기준에 dimension_target은 없다."
O_WHY = "손님·승객이 탄 상태의 택시 = 실차 상태 → taxi_status occupied. '실차'라는 말이 없어도 같다. 측정은 건수가 아니라 통행량이므로 trip_count가 아니다. "
V_WHY = "손님·승객 없이 다닌 택시 = 공차 상태 → taxi_status vacant. "
T_WHY = ("손님을 태운/내려준 '건수'=실차 운행 구간의 수=trip_count(EVENT trip). trip은 실차 구간 자체라 taxi_status를 붙이지 않는다. "
         "장소가 제한하는 끝=od_role, 묶는 끝=dimension_target. 통행량(passage_count)이 아니다.")

# ---- i1: 대구, 2026년 8월, 시군구별
f = {"date": "20260801-20260831", "dimension": "sigungu"}
P = lambda od=None: [place("origin" if od else "place", "대구", "대구", "", od)]  # noqa: E731
add(1, "i1", "occupied", "2026년 8월 한 달 동안 대구에서 손님이 타고 있던 택시의 통행량을 시군구별로 알려줘",
    "8월=20260801-20260831. 손님이 타고 있던 택시=occupied. " + O_WHY + P_WHY,
    gold(P(), "passage_count", "손님이 타고 있던 택시의 통행량", {**f, "taxi_status": "occupied"}))
add(2, "i1", "occupied", "2026년 8월 대구 시군구별로 승객이 탄 택시가 지나간 양은 얼마야?",
    "승객이 탄 택시가 지나간 양=occupied 통행량. " + O_WHY + P_WHY,
    gold(P(), "passage_count", "승객이 탄 택시가 지나간 양", {**f, "taxi_status": "occupied"}))
add(3, "i1", "vacant", "2026년 8월 대구 시군구별로 손님 없이 돌아다닌 택시의 통행량을 알려줘",
    "손님 없이 돌아다닌 택시=vacant. " + V_WHY + P_WHY,
    gold(P(), "passage_count", "손님 없이 돌아다닌 택시의 통행량", {**f, "taxi_status": "vacant"}))
add(4, "i1", "trip_pickup", "2026년 8월 대구에서 손님을 태운 건수를 승차 시군구별로 알려줘",
    "대구에서 손님을 태운=od_role pickup, 승차 시군구별=dimension sigungu + dimension_target pickup. " + T_WHY,
    gold(P("pickup"), "trip_count", "손님을 태운 건수", {**f, "dimension_target": "pickup"}))

# ---- i2: 부산, 지난주 21–23시, 시군구별
f = {"date": "last_week", "time": "210000-230000", "dimension": "sigungu"}
P = lambda od=None: [place("origin" if od == "pickup" else "destination" if od else "place", "부산", "부산", "", od)]  # noqa: E731
add(5, "i2", "occupied", "지난주 밤 9시부터 11시까지 부산 시군구별로 승객을 싣고 다닌 택시의 통행량은?",
    "밤 9–11시=210000-230000. 승객을 싣고 다닌 택시=occupied. " + O_WHY + P_WHY,
    gold(P(), "passage_count", "승객을 싣고 다닌 택시의 통행량", {**f, "taxi_status": "occupied"}))
add(6, "i2", "vacant", "지난주 밤 9시부터 11시까지 부산 시군구별로 승객이 타지 않은 택시가 지나간 양은?",
    "승객이 타지 않은 택시=vacant. " + V_WHY + P_WHY,
    gold(P(), "passage_count", "승객이 타지 않은 택시가 지나간 양", {**f, "taxi_status": "vacant"}))
add(7, "i2", "plain", "지난주 밤 9시부터 11시까지 부산 시군구별로 택시가 지나간 양은?",
    "운행 상태가 없는 통행량=passage_count만. taxi_status를 만들지 않는다. " + P_WHY,
    gold(P(), "passage_count", "택시가 지나간 양", dict(f)))
add(8, "i2", "trip_dropoff", "지난주 밤 9시부터 11시까지 부산에서 손님을 내려준 건수를 하차 시군구별로 보여줘",
    "부산에서 손님을 내려준=od_role dropoff, 하차 시군구별=dimension_target dropoff. " + T_WHY,
    gold(P("dropoff"), "trip_count", "손님을 내려준 건수", {**f, "dimension_target": "dropoff"}))

# ---- i3: 광안리 근처, 2026-09-19 21–23시, H3 + vicinity
f = {"date": "20260919", "time": "210000-230000", "dimension": "h3", "vicinity": True}
P = lambda od=None: [place("origin" if od else "place", "광안리", "광안리", "", od)]  # noqa: E731
add(9, "i3", "occupied", "2026년 9월 19일 밤 9시부터 11시까지 광안리 근처에서 손님 태운 택시들이 얼마나 지나갔는지 H3 셀별로 알려줘",
    "근처→vicinity. 지역이 발화에 없어 region 빈 값. 손님 태운 택시들이 얼마나 지나갔는지=occupied 통행량. " + O_WHY + P_WHY,
    gold(P(), "passage_count", "손님 태운 택시들이 얼마나 지나갔는지", {**f, "taxi_status": "occupied"}))
add(10, "i3", "occupied", "2026년 9월 19일 밤 9시~11시 광안리 근처 H3 셀별 승객 탑승 택시 통행량은?",
    "근처→vicinity. 승객 탑승 택시=occupied. " + O_WHY + P_WHY,
    gold(P(), "passage_count", "승객 탑승 택시 통행량", {**f, "taxi_status": "occupied"}))
add(11, "i3", "vacant", "2026년 9월 19일 밤 9시부터 11시까지 광안리 근처에서 손님을 찾아 다닌 빈 차의 통행량을 H3 셀별로 알려줘",
    "근처→vicinity. 손님을 찾아 다닌 빈 차=vacant. " + V_WHY + P_WHY,
    gold(P(), "passage_count", "손님을 찾아 다닌 빈 차의 통행량", {**f, "taxi_status": "vacant"}))
add(12, "i3", "trip_pickup", "2026년 9월 19일 밤 9시부터 11시까지 광안리 근처에서 손님을 태운 건수를 승차 H3 셀별로 알려줘",
    "광안리 근처에서 손님을 태운=od_role pickup + vicinity, 승차 H3 셀별=dimension_target pickup. " + T_WHY,
    gold(P("pickup"), "trip_count", "손님을 태운 건수", {**f, "dimension_target": "pickup"}))

# ---- i4: 대구 동성로, 2026-09-20 14–17시, H3
f = {"date": "20260920", "time": "140000-170000", "dimension": "h3"}
P = lambda od=None: [place("origin" if od == "pickup" else "destination" if od else "place", "동성로", "동성로", "대구", od)]  # noqa: E731
add(13, "i4", "occupied", "2026년 9월 20일 오후 2시부터 5시까지 대구 동성로를 손님을 태우고 지나간 택시의 양을 H3 셀별로 보여줘",
    "오후 2–5시=140000-170000. 손님을 태우고 지나간 택시의 양=occupied 통행량. " + O_WHY + P_WHY,
    gold(P(), "passage_count", "손님을 태우고 지나간 택시의 양", {**f, "taxi_status": "occupied"}))
add(14, "i4", "vacant", "2026년 9월 20일 오후 2시부터 5시까지 대구 동성로를 빈 채로 지나간 택시의 양을 H3 셀별로 보여줘",
    "빈 채로 지나간 택시=vacant. " + V_WHY + P_WHY,
    gold(P(), "passage_count", "빈 채로 지나간 택시의 양", {**f, "taxi_status": "vacant"}))
add(15, "i4", "trip_pickup", "2026년 9월 20일 오후 2시부터 5시까지 대구 동성로에서 손님을 태운 건수를 승차 H3 셀별로 보여줘",
    "동성로에서 손님을 태운=od_role pickup, 승차 H3 셀별=dimension_target pickup. " + T_WHY,
    gold(P("pickup"), "trip_count", "손님을 태운 건수", {**f, "dimension_target": "pickup"}))
add(16, "i4", "trip_dropoff", "2026년 9월 20일 오후 2시부터 5시까지 대구 동성로에서 손님을 내려준 건수를 하차 H3 셀별로 보여줘",
    "동성로에서 손님을 내려준=od_role dropoff, 하차 H3 셀별=dimension_target dropoff. " + T_WHY,
    gold(P("dropoff"), "trip_count", "손님을 내려준 건수", {**f, "dimension_target": "dropoff"}))

# ---- i5: 부산 어린이대공원 주변, 이번 달, H3 + vicinity
f = {"date": "this_month", "dimension": "h3", "vicinity": True}
P = lambda od=None: [place("origin" if od else "place", "어린이대공원", "어린이대공원", "부산", od)]  # noqa: E731
add(17, "i5", "occupied", "이번 달 부산 어린이대공원 주변을 지나간, 승객이 타고 있는 택시의 통행량을 H3 셀별로 알려줘",
    "주변→vicinity. 승객이 타고 있는 택시=occupied. " + O_WHY + P_WHY,
    gold(P(), "passage_count", "승객이 타고 있는 택시의 통행량", {**f, "taxi_status": "occupied"}))
add(18, "i5", "vacant", "이번 달 부산 어린이대공원 주변을 지나간 빈 택시 통행량을 H3 셀별로 알려줘",
    "주변→vicinity. 빈 택시=vacant. " + V_WHY + P_WHY,
    gold(P(), "passage_count", "빈 택시 통행량", {**f, "taxi_status": "vacant"}))
add(19, "i5", "plain", "이번 달 부산 어린이대공원 주변을 지나간 택시 통행량을 H3 셀별로 알려줘",
    "주변→vicinity. 운행 상태가 없는 통행량. " + P_WHY,
    gold(P(), "passage_count", "택시 통행량", dict(f)))
add(20, "i5", "trip_pickup", "이번 달 부산 어린이대공원 주변에서 승객을 태운 건수를 승차 H3 셀별로 알려줘",
    "주변에서 승객을 태운=od_role pickup + vicinity, 승차 H3 셀별=dimension_target pickup. " + T_WHY,
    gold(P("pickup"), "trip_count", "승객을 태운 건수", {**f, "dimension_target": "pickup"}))

# ---- i6: 대구 달서구, 2026-09-01–07, H3
f = {"date": "20260901-20260907", "dimension": "h3"}
P = lambda od=None: [place("destination" if od else "place", "달서구", "달서구", "대구", od)]  # noqa: E731
add(21, "i6", "occupied", "2026년 9월 1일부터 7일까지 대구 달서구에서 손님을 모시고 달린 택시의 통행량을 H3 셀별로 알려줘",
    "날짜 범위 20260901-20260907. 손님을 모시고 달린 택시=occupied. " + O_WHY + P_WHY,
    gold(P(), "passage_count", "손님을 모시고 달린 택시의 통행량", {**f, "taxi_status": "occupied"}))
add(22, "i6", "occupied", "2026년 9월 1일부터 7일까지 대구 달서구 H3 셀별로 손님 있는 택시가 지나간 양을 보여줘",
    "손님 있는 택시=occupied. " + O_WHY + P_WHY,
    gold(P(), "passage_count", "손님 있는 택시가 지나간 양", {**f, "taxi_status": "occupied"}))
add(23, "i6", "vacant", "2026년 9월 1일부터 7일까지 대구 달서구 H3 셀별로 손님 없는 택시가 지나간 양을 보여줘",
    "손님 없는 택시=vacant. " + V_WHY + P_WHY,
    gold(P(), "passage_count", "손님 없는 택시가 지나간 양", {**f, "taxi_status": "vacant"}))
add(24, "i6", "trip_dropoff", "2026년 9월 1일부터 7일까지 대구 달서구에 손님을 내려준 건수를 하차 H3 셀별로 알려줘",
    "달서구에 손님을 내려준=od_role dropoff, 하차 H3 셀별=dimension_target dropoff. " + T_WHY,
    gold(P("dropoff"), "trip_count", "손님을 내려준 건수", {**f, "dimension_target": "dropoff"}))

# ---- i7: 부산 수영구, 2026-09-24 07–09시, H3
f = {"date": "20260924", "time": "070000-090000", "dimension": "h3"}
P = lambda od=None: [place("origin" if od else "place", "수영구", "수영구", "부산", od)]  # noqa: E731
add(25, "i7", "occupied", "2026년 9월 24일 오전 7시부터 9시까지 부산 수영구에서 승객을 태운 택시가 지나간 양을 H3 셀별로 알려줘",
    "오전 7–9시=070000-090000. 승객을 태운 택시가 지나간 양=occupied 통행량('태운'이 있어도 건수가 아니다). " + O_WHY + P_WHY,
    gold(P(), "passage_count", "승객을 태운 택시가 지나간 양", {**f, "taxi_status": "occupied"}))
add(26, "i7", "vacant", "2026년 9월 24일 오전 7시부터 9시까지 부산 수영구에서 승객을 기다리며 다닌 빈 택시의 통행량을 H3 셀별로 알려줘",
    "승객을 기다리며 다닌 빈 택시=vacant. " + V_WHY + P_WHY,
    gold(P(), "passage_count", "승객을 기다리며 다닌 빈 택시의 통행량", {**f, "taxi_status": "vacant"}))
add(27, "i7", "trip_pickup", "2026년 9월 24일 오전 7시부터 9시까지 부산 수영구에서 승객을 태운 건수를 승차 H3 셀별로 알려줘",
    "수영구에서 승객을 태운=od_role pickup, 승차 H3 셀별=dimension_target pickup. 25번과 '태운'은 같지만 측정이 건수다. " + T_WHY,
    gold(P("pickup"), "trip_count", "승객을 태운 건수", {**f, "dimension_target": "pickup"}))
add(28, "i7", "plain", "2026년 9월 24일 오전 7시부터 9시까지 부산 수영구의 택시 통행량을 H3 셀별로 알려줘",
    "운행 상태가 없는 통행량. " + P_WHY,
    gold(P(), "passage_count", "택시 통행량", dict(f)))

assert len(C) == 28 and len({c["question"] for c in C}) == 28
header = """# batch007 annotation 후보 초안. Claude가 2026-10-15에 새로 썼다. 사람 검토 전이며 승인이 아니다(결정 104).
# - 결정 104: "실차"라는 말 없이 운행 상태를 표현한 통행량 질문 + 헷갈리는 대조. 의도 7개 × 4 = 28건
#   (occupied 10, vacant 7, plain 3, trip_pickup 5, trip_dropoff 3).
# - 계기는 selection_v2 indepv2/n33이지만 n33·보호 셋의 문장을 보거나 바꿔 쓰지 않았다. batch006과 같은 표현은 피했다.
# - 다음 판에서 이 데이터로 학습하면 selection_v2 결과를 n33을 넣은 것과 뺀 것 둘 다로 보고한다(결정 104).
# - 기준일: 2026-09-25(평가 harness와 같다).
"""
body = yaml.safe_dump({"reference_date": "2026-09-25", "candidates": C}, allow_unicode=True, sort_keys=False, width=200,
                      default_flow_style=None)
(__import__("pathlib").Path(__file__).resolve().parent / "candidates_draft.yaml").write_text(header + body, encoding="utf-8")
print("ok", len(C), {v: sum(c["variant"] == v for c in C) for v in ("occupied", "vacant", "plain", "trip_pickup", "trip_dropoff")})
