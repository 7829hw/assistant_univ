# -*- coding: utf-8 -*-
"""batch009 초안(Claude, 2026-10-16, pilot_006 준비 세션 2b H3). 질문·정답 호출·근거는 여기 손으로 적었다. **승인이 아니다.**

    python3 sft_dpo_inventory/batch009/write_drafts.py  # -> candidates_draft.yaml

R2(P0.3 prompt만, base) 약점 네 가지(``pilot_006_prep/analysis/r2_vs_base.json``, 지시 H3 표):
- w1 value 없는 장소(20): 답이 장소 이름인 질문(scope 이름 조회, ``get_scope_name``). R2에서 Partial이 MEASURE를 내지 않았다(ok 0%).
  family 키가 측정 없음·OD 없음·factor 없음 하나뿐이고 보호 셋 넷이 이미 그 family를 가진다(``analysis/family_key.md``) → 결정 120으로 모두 빠질 것으로 예상하고도
  쓴다(사용자가 예외를 정하면 바로 쓸 수 있게). scope id는 보호 셋과 같은 grounding(같은 scope)이 되지 않도록 mock gazetteer 안에서 고르되, 검사로 확인한다.
- w2 implicit endpoint 동사형 dimension_target(20): "승차·하차·출발·도착"이라는 말 없이 "태운·내려준·탄·내린·오른" 같은 동사로 끝을 말한다.
- w3 od_role ≠ dimension_target(10): 장소가 제한하는 끝과 묶는 끝이 다르다(예: 태운 곳 제한, 내린 곳으로 묶음).
- w4 순위 없는 dimension_target(10): 묶는 끝은 있지만 순위(order·limit)가 없다.
구조 선택: 보호 셋 넷(selection_v2, augmentation_holdout_v1, valid98, aux_test_v1)과 selection_v1이 가진 trip_count family를 피해서
(od_role 목록, dimension, dimension_target, order) 조합을 골랐다(``analysis/family_key_analysis.json``). 날짜·시간·limit·장소는 family에 들어가지 않는다.
표기는 승인된 trunk 관례를 따른다: 지역 안 OD = 장소 하나 + od_role both(``scope_pickup``·``scope_dropoff``에 같은 binding), 측정 source implicit(역산 기본값).
vicinity와 dimension을 함께 쓰는 문항은 현재 코드가 거부하므로 쓰지 않았다. 원칙: 보호 셋 문장, selection_v2 n33, aug300 문장을 보거나 바꿔 쓰지 않았다.
정답은 업체 형식 Tool 호출로 적고 grounding은 그 호출에서 역산한다(``evaluate_vendor100.derive_grounding``). 기준일 2026-09-25.
"""
from pathlib import Path

import yaml

C = []


def add(n, gap, q, calls, why):
    C.append({"id": f"b009-{n:02d}", "gap": gap, "question": q, "gold_text": "\n".join(calls), "rationale": why})


def P(name, region=None, bind="resolve"):
    return f"get_place_scope(name={name}" + (f", region={region}" if region else "") + ")"


def T(**kw):
    return "get_trip_count(" + ", ".join(f"{k}={v}" for k, v in kw.items()) + ")"


SN = "답이 장소 이름(scope 이름 조회). 측정값은 장소 이름 자체이고 수치가 없다. "
# ---- w1: value 없는 장소(scope 이름 조회)
w1 = [("scope:district:2729010100", "scope:district:2729010100 코드에 해당하는 동네 이름이 뭐야?"),
      ("scope:district:2617010100", "scope:district:2617010100은 어느 동을 가리키는 코드야?"),
      ("scope:district:2723010300", "행정구역 코드 scope:district:2723010300의 이름을 알려줘"),
      ("scope:district:2650000000", "scope:district:2650000000이라는 구역은 이름이 뭐지?"),
      ("scope:district:2722000000", "scope:district:2722000000가 어느 구인지 알려줄래?"),
      ("scope:h3:8830e1d81ffffff", "H3 셀 scope:h3:8830e1d81ffffff는 어느 지역 이름으로 불려?"),
      ("scope:h3:8830e1d89ffffff", "scope:h3:8830e1d89ffffff 셀의 이름이 궁금해"),
      ("scope:district:2723010100", "코드 scope:district:2723010100으로 적힌 곳은 무슨 동이야?"),
      ("scope:district:2623000000", "scope:district:2623000000은 어떤 구의 코드야?"),
      ("scope:district:2721000000", "scope:district:2721000000 구역 이름만 알려줘"),
      ("scope:h3:8830e1d85ffffff", "scope:h3:8830e1d85ffffff라는 셀은 어디로 표시돼?"),
      ("scope:district:2726000000", "scope:district:2726000000 코드의 구 이름을 말해줘"),
      ("scope:district:2650010400", "scope:district:2650010400에 대응하는 동 이름은?"),
      ("scope:edge:11234", "scope:edge:11234로 기록된 지점의 이름을 알려줘"),
      ("scope:gz:33212", "scope:gz:33212 구역은 이름이 어떻게 돼?"),
      ("scope:district:2723510100", "scope:district:2723510100 코드가 가리키는 동을 알려줘"),
      ("scope:district:2800000000", "scope:district:2800000000은 어느 시·도야?"),
      ("scope:h3:8830e1d87ffffff", "scope:h3:8830e1d87ffffff 셀이 속한 이름을 알려줄래?"),
      ("scope:district:2711012300", "scope:district:2711012300 코드의 동 이름 좀 찾아줘"),
      ("scope:district:1100000000", "scope:district:1100000000이 어느 시·도인지 알려줘")]
for i, (scope, q) in enumerate(w1, 1):
    add(i, "w1_valueless_place", q, [f"get_scope_name(scope={scope})"], SN + "scope id는 질문에 그대로 있다.")

DT = "실차 건수(trip_count). 장소가 제한하는 끝 = od_role, 결과를 묶는 끝 = dimension_target. "
VERB = "승차·하차·출발·도착이라는 말 없이 동사로 끝을 말한다(태운·탄·오른 = 승차 끝, 내려준·내린 = 하차 끝). "
# ---- w2: implicit endpoint 동사형 dimension_target (n, 질문, 호출, 근거)
w2 = [
    ("지난주 대구 수성구에서 손님을 태운 건수를 손님을 내려준 H3 셀별로 보여줘",
     [P("수성구", "대구"), T(scope_pickup="$pickup.scope", date="last_week", dimension="h3", dimension_target="dropoff")],
     "수성구에서 태운 = od pickup, 내려준 H3 셀별 = dt dropoff. 순위 없음."),
    ("이번 달 부산에서 손님이 내린 건수가 가장 적은 시군구 두 곳을 알려줘",
     [P("부산"), T(scope_dropoff="$dropoff.scope", date="this_month", dimension="sigungu", dimension_target="dropoff", order="bottom", limit=2)],
     "부산에서 내린 = od dropoff, 내린 시군구 기준 = dt dropoff, 가장 적은 두 곳 = bottom 2."),
    ("2026년 8월 손님이 택시에 오른 건수가 가장 많은 시도 한 곳은?",
     [T(date="20260801-20260831", dimension="sido", dimension_target="pickup", order="top", limit=1)],
     "장소 제한 없음, 택시에 오른 = 승차 끝으로 묶음(dt pickup), 가장 많은 한 곳 = top 1."),
    ("지난달 대구 동구에 손님을 내려준 건수를 손님을 태운 시도별로 세어줘",
     [P("동구", "대구"), T(scope_dropoff="$dropoff.scope", date="last_month", dimension="sido", dimension_target="pickup")],
     "동구에 내려준 = od dropoff, 태운 시도별 = dt pickup. 순위 없음."),
    ("주말 동안 부산 수영구 안에서 태우고 같은 구 안에서 내려준 건수를 내려준 읍면동별로 보여줘",
     [P("수영구", "부산"), T(scope_pickup="$area.scope", scope_dropoff="$area.scope", date="weekend", dimension="emd", dimension_target="dropoff")],
     "수영구 안에서 태우고 내려줌 = 장소 하나 + od both(trunk 관례), 내려준 읍면동별 = dt dropoff. 순위 없음."),
    ("이번 주 손님을 태운 곳과 내려준 곳을 시군구 단위로 짝지었을 때 가장 드문 짝 세 개는?",
     [T(date="this_week", dimension="sigungu", dimension_target="both", order="bottom", limit=3)],
     "장소 제한 없음, 태운 곳·내려준 곳 짝 = dt both, 가장 드문 세 개 = bottom 3."),
    ("지난주 대구 중구에서 탄 손님이 많이 내린 H3 셀 세 곳을 알려줘",
     [P("중구", "대구"), T(scope_pickup="$pickup.scope", date="last_week", dimension="h3", dimension_target="dropoff", order="top", limit=3)],
     "중구에서 탄 = od pickup, 많이 내린 셀 = dt dropoff + top 3."),
    ("2026년 9월 1일부터 15일까지 부산진구에 내린 손님들이 어느 읍면동에서 탔는지 적은 순으로 두 곳만",
     [P("부산진구", "부산"), T(scope_dropoff="$dropoff.scope", date="20260901-20260915", dimension="emd", dimension_target="pickup", order="bottom", limit=2)],
     "부산진구에 내린 = od dropoff, 어느 읍면동에서 탔는지 = dt pickup, 적은 순 두 곳 = bottom 2."),
    ("이번 달 대구 안에서 태워 대구 안에 내려준 건수를 태운 시군구 기준으로 많이 나온 네 곳",
     [P("대구"), T(scope_pickup="$area.scope", scope_dropoff="$area.scope", date="this_month", dimension="sigungu", dimension_target="pickup", order="top", limit=4)],
     "대구 안에서 태워 대구 안에 내려줌 = 장소 하나 + od both, 태운 시군구 기준 = dt pickup, 많이 나온 네 곳 = top 4."),
    ("지난달 손님을 내려준 H3 셀 가운데 건수가 가장 적은 곳 하나는?",
     [T(date="last_month", dimension="h3", dimension_target="dropoff", order="bottom", limit=1)],
     "장소 제한 없음, 내려준 셀 = dt dropoff, 가장 적은 하나 = bottom 1."),
    ("아침 7시부터 9시까지 대구 달서구에서 손님을 태워 부산에 내려준 건수를 태운 읍면동별로 나눠줘",
     [P("달서구", "대구"), P("부산"), T(scope_pickup="$pickup.scope", scope_dropoff="$dropoff.scope", time="070000-090000", dimension="emd", dimension_target="pickup")],
     "달서구에서 태움 = od pickup, 부산에 내려줌 = od dropoff, 태운 읍면동별 = dt pickup. 순위 없음."),
    ("지난주 부산 동구에서 탄 손님을 내려준 시도별 건수를 많은 것부터 두 곳",
     [P("부산 동구"), T(scope_pickup="$pickup.scope", date="last_week", dimension="sido", dimension_target="dropoff", order="top", limit=2)],
     "부산 동구에서 탄 = od pickup, 내려준 시도별 = dt dropoff, 많은 것부터 두 곳 = top 2."),
    ("2026년 8월 대구에 내린 손님이 탄 H3 셀 가운데 건수가 많은 세 곳은?",
     [P("대구"), T(scope_dropoff="$dropoff.scope", date="20260801-20260831", dimension="h3", dimension_target="pickup", order="top", limit=3)],
     "대구에 내린 = od dropoff, 탄 셀 = dt pickup, 많은 세 곳 = top 3."),
    ("이번 주 부산 안에서만 태우고 내려준 건수를 태운 곳과 내린 곳의 시군구 짝으로 보여줘",
     [P("부산"), T(scope_pickup="$area.scope", scope_dropoff="$area.scope", date="this_week", dimension="sigungu", dimension_target="both")],
     "부산 안에서만 태우고 내려줌 = 장소 하나 + od both, 태운 곳·내린 곳 짝 = dt both. 순위 없음."),
    ("지난달 손님이 오른 읍면동별 건수를 알려줘",
     [T(date="last_month", dimension="emd", dimension_target="pickup")],
     "장소 제한 없음, 손님이 오른 읍면동별 = dt pickup. 순위 없음."),
    ("주말에 대구 동구에서 태운 손님을 어느 시군구에 내려줬는지 적은 곳 세 군데",
     [P("동구", "대구"), T(scope_pickup="$pickup.scope", date="weekend", dimension="sigungu", dimension_target="dropoff", order="bottom", limit=3)],
     "동구에서 태운 = od pickup, 어느 시군구에 내려줬는지 = dt dropoff, 적은 곳 세 군데 = bottom 3."),
    ("이번 달 부산 수영구에 내려준 손님을 어느 시도에서 태웠는지 건수가 많은 곳 하나",
     [P("수영구", "부산"), T(scope_dropoff="$dropoff.scope", date="this_month", dimension="sido", dimension_target="pickup", order="top", limit=1)],
     "수영구에 내려준 = od dropoff, 어느 시도에서 태웠는지 = dt pickup, 많은 곳 하나 = top 1."),
    ("지난주 손님을 태운 셀과 내려준 셀의 짝 가운데 가장 흔한 다섯 개",
     [T(date="last_week", dimension="h3", dimension_target="both", order="top", limit=5)],
     "장소 제한 없음, 태운 셀·내려준 셀 짝 = dt both(h3), 가장 흔한 다섯 개 = top 5."),
    ("2026년 9월 대구 중구 안에서 태우고 중구 안에서 내려준 건수를 내려준 H3 셀별로 정리해줘",
     [P("중구", "대구"), T(scope_pickup="$area.scope", scope_dropoff="$area.scope", date="20260901-20260930", dimension="h3", dimension_target="dropoff")],
     "중구 안에서 태우고 내려줌 = 장소 하나 + od both, 내려준 H3 셀별 = dt dropoff. 순위 없음."),
    ("이번 주 부산진구에서 태운 손님을 대구에 내려준 건수를 내린 시군구별로 많은 순 두 곳",
     [P("부산진구", "부산"), P("대구"), T(scope_pickup="$pickup.scope", scope_dropoff="$dropoff.scope", date="this_week", dimension="sigungu",
                                         dimension_target="dropoff", order="top", limit=2)],
     "부산진구에서 태움 = od pickup, 대구에 내려줌 = od dropoff, 내린 시군구별 = dt dropoff, 많은 순 두 곳 = top 2."),
]
for i, (q, calls, why) in enumerate(w2, 21):
    add(i, "w2_implicit_endpoint_verb", q, calls, DT + VERB + why)

# ---- w3: od_role ≠ dimension_target
w3 = [
    ("지난주 대구 서구에서 승차한 실차 건수를 하차 시도별로 보여줘",
     [P("서구", "대구"), T(scope_pickup="$pickup.scope", date="last_week", dimension="sido", dimension_target="dropoff")],
     "서구 승차 = od pickup, 하차 시도별 = dt dropoff."),
    ("이번 달 부산 동구에서 하차한 실차 건수를 승차 H3 셀별로 적은 순 세 곳",
     [P("부산 동구"), T(scope_dropoff="$dropoff.scope", date="this_month", dimension="h3", dimension_target="pickup", order="bottom", limit=3)],
     "부산 동구 하차 = od dropoff, 승차 H3 셀별 = dt pickup, 적은 순 세 곳 = bottom 3."),
    ("2026년 8월 대구 수성구에서 출발한 실차 이동 건수를 출발지·도착지 시군구 짝으로 많은 순 세 개",
     [P("수성구", "대구"), T(scope_pickup="$pickup.scope", date="20260801-20260831", dimension="sigungu", dimension_target="both", order="top", limit=3)],
     "수성구 출발 = od pickup, 출발지·도착지 짝 = dt both, 많은 순 세 개 = top 3."),
    ("지난달 부산에 도착한 실차 건수를 출발·도착 읍면동 짝으로 많은 순 네 개",
     [P("부산"), T(scope_dropoff="$dropoff.scope", date="last_month", dimension="emd", dimension_target="both", order="top", limit=4)],
     "부산 도착 = od dropoff, 출발·도착 읍면동 짝 = dt both, 많은 순 네 개 = top 4."),
    ("주말 대구 달서구에서 출발해 부산에 도착한 실차 건수를 도착 H3 셀 기준으로 적은 두 곳",
     [P("달서구", "대구"), P("부산"), T(scope_pickup="$pickup.scope", scope_dropoff="$dropoff.scope", date="weekend", dimension="h3",
                                       dimension_target="dropoff", order="bottom", limit=2)],
     "달서구 출발 = od pickup, 부산 도착 = od dropoff, 도착 셀 기준 = dt dropoff, 적은 두 곳 = bottom 2."),
    ("이번 주 부산 수영구 안에서 출발·도착한 실차 건수를 출발 H3 셀별로 많은 순 세 곳",
     [P("수영구", "부산"), T(scope_pickup="$area.scope", scope_dropoff="$area.scope", date="this_week", dimension="h3", dimension_target="pickup",
                              order="top", limit=3)],
     "수영구 안에서 출발·도착 = 장소 하나 + od both, 출발 셀별 = dt pickup, 많은 순 세 곳 = top 3."),
    ("지난주 대구에서 승차해 대구에서 하차한 실차 건수를 하차 시군구별로 적은 순 두 곳",
     [P("대구"), T(scope_pickup="$area.scope", scope_dropoff="$area.scope", date="last_week", dimension="sigungu", dimension_target="dropoff",
                    order="bottom", limit=2)],
     "대구 안 승차·하차 = 장소 하나 + od both, 하차 시군구별 = dt dropoff, 적은 순 두 곳 = bottom 2."),
    ("2026년 9월 1일부터 7일까지 부산진구에서 하차한 실차 건수를 승차 시도별로 많은 순 한 곳",
     [P("부산진구", "부산"), T(scope_dropoff="$dropoff.scope", date="20260901-20260907", dimension="sido", dimension_target="pickup", order="top", limit=1)],
     "부산진구 하차 = od dropoff, 승차 시도별 = dt pickup, 많은 순 한 곳 = top 1."),
    ("이번 달 대구 동구에서 승차하고 부산에서 하차한 실차 건수를 출발·도착 시군구 짝으로 보여줘",
     [P("동구", "대구"), P("부산"), T(scope_pickup="$pickup.scope", scope_dropoff="$dropoff.scope", date="this_month", dimension="sigungu",
                                     dimension_target="both")],
     "동구 승차 = od pickup, 부산 하차 = od dropoff, 출발·도착 시군구 짝 = dt both."),
    ("지난달 부산 수영구에서 출발한 실차 건수를 도착 H3 셀별로 많은 순 두 곳",
     [P("수영구", "부산"), T(scope_pickup="$pickup.scope", date="last_month", dimension="h3", dimension_target="dropoff", order="top", limit=2)],
     "수영구 출발 = od pickup, 도착 셀별 = dt dropoff, 많은 순 두 곳 = top 2."),
]
for i, (q, calls, why) in enumerate(w3, 41):
    add(i, "w3_od_ne_dt", q, calls, DT + "장소가 제한하는 끝과 묶는 끝이 다르다. " + why)

# ---- w4: 순위 없는 dimension_target
w4 = [
    ("지난주 실차 이동을 하차 시도 기준으로 나눠 건수를 보여줘",
     [T(date="last_week", dimension="sido", dimension_target="dropoff")], "장소 제한 없음, 하차 시도 기준 = dt dropoff."),
    ("이번 달 실차 건수를 승차 시군구별로 알려줘",
     [T(date="this_month", dimension="sigungu", dimension_target="pickup")], "장소 제한 없음, 승차 시군구별 = dt pickup."),
    ("2026년 8월 실차 이동 건수를 출발 셀과 도착 셀 짝으로 정리해줘",
     [T(date="20260801-20260831", dimension="h3", dimension_target="both")], "장소 제한 없음, 출발·도착 셀 짝 = dt both(h3)."),
    ("지난달 대구 수성구에서 출발한 실차 건수를 출발 읍면동별로 보여줘",
     [P("수성구", "대구"), T(scope_pickup="$pickup.scope", date="last_month", dimension="emd", dimension_target="pickup")],
     "수성구 출발 = od pickup, 출발 읍면동별 = dt pickup."),
    ("주말 부산에 도착한 실차 건수를 도착 시군구별로 정리해줘",
     [P("부산"), T(scope_dropoff="$dropoff.scope", date="weekend", dimension="sigungu", dimension_target="dropoff")],
     "부산 도착 = od dropoff, 도착 시군구별 = dt dropoff."),
    ("이번 주 대구 중구에서 출발한 실차 건수를 출발·도착 시군구 짝으로 나눠줘",
     [P("중구", "대구"), T(scope_pickup="$pickup.scope", date="this_week", dimension="sigungu", dimension_target="both")],
     "중구 출발 = od pickup, 출발·도착 시군구 짝 = dt both."),
    ("지난주 부산 수영구 안에서 승차·하차한 실차 건수를 승차 시도별로 보여줘",
     [P("수영구", "부산"), T(scope_pickup="$area.scope", scope_dropoff="$area.scope", date="last_week", dimension="sido", dimension_target="pickup")],
     "수영구 안에서 승차·하차 = 장소 하나 + od both, 승차 시도별 = dt pickup."),
    ("2026년 9월 1일부터 15일까지 대구 달서구에 도착한 실차 건수를 출발·도착 H3 셀 짝으로 나눠줘",
     [P("달서구", "대구"), T(scope_dropoff="$dropoff.scope", date="20260901-20260915", dimension="h3", dimension_target="both")],
     "달서구 도착 = od dropoff, 출발·도착 셀 짝 = dt both."),
    ("이번 달 부산진구에서 출발해 대구에 도착한 실차 건수를 도착 읍면동별로 보여줘",
     [P("부산진구", "부산"), P("대구"), T(scope_pickup="$pickup.scope", scope_dropoff="$dropoff.scope", date="this_month", dimension="emd",
                                         dimension_target="dropoff")],
     "부산진구 출발 = od pickup, 대구 도착 = od dropoff, 도착 읍면동별 = dt dropoff."),
    ("지난달 대구 안에서 승차하고 하차한 실차 건수를 승차·하차 H3 셀 짝으로 정리해줘",
     [P("대구"), T(scope_pickup="$area.scope", scope_dropoff="$area.scope", date="last_month", dimension="h3", dimension_target="both")],
     "대구 안 승차·하차 = 장소 하나 + od both, 승차·하차 셀 짝 = dt both."),
]
for i, (q, calls, why) in enumerate(w4, 51):
    add(i, "w4_dt_no_rank", q, calls, DT + "순위·개수 제한이 없으므로 order·limit 없음. " + why)

# ---- 2차(1차 검사 뒤, ``free_structures.py``로 family·현재 코드 응답을 미리 확인한 구조에서). 1차 후보와 결과는 그대로 둔다.
R2 = "2차 후보: 1차에서 보호 넷 family·현재 코드 거부로 빠진 만큼 다시 썼다(구조는 free_structures.json의 free). "
w2b = [
    ("이번 주 손님들이 많이 내린 H3 셀 두 곳의 건수를 알려줘", [T(date="this_week", dimension="h3", dimension_target="dropoff", order="top", limit=2)],
     "장소 제한 없음, 많이 내린 셀 = dt dropoff + top 2."),
    ("2026년 8월 손님을 태운 건수가 가장 적은 읍면동 세 곳은?", [T(date="20260801-20260831", dimension="emd", dimension_target="pickup", order="bottom", limit=3)],
     "장소 제한 없음, 태운 읍면동 = dt pickup, 가장 적은 세 곳 = bottom 3."),
    ("주말에 대구 수성구에서 손님을 태운 건수가 적은 H3 셀 두 곳", [P("수성구", "대구"), T(scope_pickup="$pickup.scope", date="weekend", dimension="h3",
                                                                       dimension_target="pickup", order="bottom", limit=2)],
     "수성구에서 태운 = od pickup, 태운 셀 = dt pickup, 적은 두 곳 = bottom 2."),
    ("지난달 부산에 손님을 내려준 건수가 많은 시군구 세 곳", [P("부산"), T(scope_dropoff="$dropoff.scope", date="last_month", dimension="sigungu",
                                                             dimension_target="dropoff", order="top", limit=3)],
     "부산에 내려준 = od dropoff, 내려준 시군구 = dt dropoff, 많은 세 곳 = top 3."),
    ("이번 달 대구에 내린 손님들이 탄 셀과 내린 셀의 짝 가운데 건수가 많은 세 개", [P("대구"), T(scope_dropoff="$dropoff.scope", date="this_month", dimension="h3",
                                                                            dimension_target="both", order="top", limit=3)],
     "대구에 내린 = od dropoff, 탄 셀·내린 셀 짝 = dt both, 많은 세 개 = top 3."),
    ("지난주 대구 동구에서 손님을 태운 운행을 태운 시군구와 내려준 시군구 짝으로 묶었을 때 건수가 가장 적은 두 짝",
     [P("동구", "대구"), T(scope_pickup="$pickup.scope", date="last_week", dimension="sigungu", dimension_target="both", order="bottom", limit=2)],
     "동구에서 태운 = od pickup, 태운·내려준 시군구 짝 = dt both, 가장 적은 두 짝 = bottom 2."),
    ("이번 주 부산 수영구에 손님을 내려준 건수를 태운 읍면동과 내려준 읍면동 짝으로 보면 가장 흔한 세 짝은?",
     [P("수영구", "부산"), T(scope_dropoff="$dropoff.scope", date="this_week", dimension="emd", dimension_target="both", order="top", limit=3)],
     "수영구에 내려준 = od dropoff, 태운·내려준 읍면동 짝 = dt both, 가장 흔한 세 짝 = top 3."),
    ("지난달 대구 안에서 태워 대구 안에 내려준 건수가 많은 태운 셀 세 곳", [P("대구"), T(scope_pickup="$area.scope", scope_dropoff="$area.scope", date="last_month",
                                                                       dimension="h3", dimension_target="pickup", order="top", limit=3)],
     "대구 안에서 태워 대구 안에 내려줌 = 장소 하나 + od both, 태운 셀 = dt pickup, 많은 세 곳 = top 3."),
    ("주말 대구 수성구에서 태워 부산에 내려준 건수가 적은 태운 셀 두 곳", [P("수성구", "대구"), P("부산"), T(scope_pickup="$pickup.scope", scope_dropoff="$dropoff.scope",
                                                                                  date="weekend", dimension="h3", dimension_target="pickup", order="bottom", limit=2)],
     "수성구에서 태움 = od pickup, 부산에 내려줌 = od dropoff, 태운 셀 = dt pickup, 적은 두 곳 = bottom 2."),
    ("이번 달 손님을 내려준 건수가 가장 적은 시도 한 곳", [T(date="this_month", dimension="sido", dimension_target="dropoff", order="bottom", limit=1)],
     "장소 제한 없음, 내려준 시도 = dt dropoff, 가장 적은 한 곳 = bottom 1."),
    ("지난달 부산진구에 내려준 손님을 태운 시도 가운데 건수가 가장 적은 곳", [P("부산진구", "부산"), T(scope_dropoff="$dropoff.scope", date="last_month",
                                                                             dimension="sido", dimension_target="pickup", order="bottom", limit=1)],
     "부산진구에 내려준 = od dropoff, 태운 시도 = dt pickup, 가장 적은 곳 = bottom 1."),
    ("이번 주 대구 달서구에서 손님을 태운 건수를 태운 셀과 내려준 셀 짝으로 많은 순 세 개", [P("달서구", "대구"), T(scope_pickup="$pickup.scope", date="this_week",
                                                                                     dimension="h3", dimension_target="both", order="top", limit=3)],
     "달서구에서 태운 = od pickup, 태운 셀·내려준 셀 짝 = dt both, 많은 순 세 개 = top 3."),
]
for i, (q, calls, why) in enumerate(w2b, 61):
    add(i, "w2_implicit_endpoint_verb", q, calls, R2 + DT + VERB + why)
w3b = [
    ("이번 달 대구 동구에서 승차한 실차 건수를 하차 시도별로 적은 순 한 곳", [P("동구", "대구"), T(scope_pickup="$pickup.scope", date="this_month", dimension="sido",
                                                                         dimension_target="dropoff", order="bottom", limit=1)],
     "동구 승차 = od pickup, 하차 시도별 = dt dropoff, 적은 순 한 곳 = bottom 1."),
    ("지난주 대구 수성구에서 하차한 실차 건수를 승차 읍면동별로 보여줘", [P("수성구", "대구"), T(scope_dropoff="$dropoff.scope", date="last_week", dimension="emd",
                                                                     dimension_target="pickup")],
     "수성구 하차 = od dropoff, 승차 읍면동별 = dt pickup."),
    ("2026년 8월 부산 수영구에 도착한 실차 건수를 출발 H3 셀별로 많은 순 세 곳", [P("수영구", "부산"), T(scope_dropoff="$dropoff.scope", date="20260801-20260831",
                                                                              dimension="h3", dimension_target="pickup", order="top", limit=3)],
     "수영구 도착 = od dropoff, 출발 셀별 = dt pickup, 많은 순 세 곳 = top 3."),
    ("이번 주 부산진구에서 출발한 실차 건수를 출발·도착 시군구 짝으로 정리해줘", [P("부산진구", "부산"), T(scope_pickup="$pickup.scope", date="this_week",
                                                                              dimension="sigungu", dimension_target="both")],
     "부산진구 출발 = od pickup, 출발·도착 시군구 짝 = dt both."),
    ("지난달 대구 중구에 도착한 실차 건수를 출발·도착 시군구 짝 가운데 적은 순 두 개", [P("중구", "대구"), T(scope_dropoff="$dropoff.scope", date="last_month",
                                                                              dimension="sigungu", dimension_target="both", order="bottom", limit=2)],
     "중구 도착 = od dropoff, 출발·도착 시군구 짝 = dt both, 적은 순 두 개 = bottom 2."),
    ("주말 부산진구에서 출발해 대구에 도착한 실차 건수를 출발 H3 셀별로 많은 순 두 곳", [P("부산진구", "부산"), P("대구"), T(scope_pickup="$pickup.scope",
                                                                                         scope_dropoff="$dropoff.scope", date="weekend", dimension="h3",
                                                                                         dimension_target="pickup", order="top", limit=2)],
     "부산진구 출발 = od pickup, 대구 도착 = od dropoff, 출발 셀별 = dt pickup, 많은 순 두 곳 = top 2."),
]
for i, (q, calls, why) in enumerate(w3b, 73):
    add(i, "w3_od_ne_dt", q, calls, R2 + DT + "장소가 제한하는 끝과 묶는 끝이 다르다. " + why)
w4b = [
    ("2026년 9월 실차 건수를 하차 시군구별로 보여줘", [T(date="20260901-20260930", dimension="sigungu", dimension_target="dropoff")],
     "장소 제한 없음, 하차 시군구별 = dt dropoff."),
    ("지난주 실차 이동 건수를 출발·도착 읍면동 짝으로 정리해줘", [T(date="last_week", dimension="emd", dimension_target="both")],
     "장소 제한 없음, 출발·도착 읍면동 짝 = dt both."),
    ("이번 달 부산 수영구에 도착한 실차 건수를 도착 H3 셀별로 보여줘", [P("수영구", "부산"), T(scope_dropoff="$dropoff.scope", date="this_month", dimension="h3",
                                                                    dimension_target="dropoff")],
     "수영구 도착 = od dropoff, 도착 셀별 = dt dropoff."),
    ("지난달 부산 안에서 출발해 부산 안에 도착한 실차 건수를 출발 H3 셀별로 나눠줘", [P("부산"), T(scope_pickup="$area.scope", scope_dropoff="$area.scope",
                                                                              date="last_month", dimension="h3", dimension_target="pickup")],
     "부산 안 출발·도착 = 장소 하나 + od both, 출발 셀별 = dt pickup."),
    ("주말 대구 수성구에서 출발해 부산에 도착한 실차 건수를 출발·도착 시군구 짝으로 보여줘", [P("수성구", "대구"), P("부산"), T(scope_pickup="$pickup.scope",
                                                                                          scope_dropoff="$dropoff.scope", date="weekend", dimension="sigungu",
                                                                                          dimension_target="both")],
     "수성구 출발 = od pickup, 부산 도착 = od dropoff, 출발·도착 시군구 짝 = dt both."),
    ("이번 주 대구에서 출발한 실차 건수를 출발 시군구별로 보여줘", [P("대구"), T(scope_pickup="$pickup.scope", date="this_week", dimension="sigungu",
                                                              dimension_target="pickup")],
     "대구 출발 = od pickup, 출발 시군구별 = dt pickup."),
]
for i, (q, calls, why) in enumerate(w4b, 79):
    add(i, "w4_dt_no_rank", q, calls, R2 + DT + "순위·개수 제한이 없으므로 order·limit 없음. " + why)

if __name__ == "__main__":
    doc = {"authored_by": "Claude 2026-10-16(pilot_006 준비 세션 2b H3)", "approval": "none", "reference_date": "2026-09-25", "candidates": C}
    (Path(__file__).resolve().parent / "candidates_draft.yaml").write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False, width=160),
                                                                          encoding="utf-8")
    from collections import Counter
    print(len(C), Counter(c["gap"] for c in C))
