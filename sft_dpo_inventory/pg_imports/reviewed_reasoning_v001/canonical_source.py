# -*- coding: utf-8 -*-
"""final-6 canonical rationale 원문과 사람 검토(사람 작성, 모델 호출 0). build_canonical.py가 읽는다.

- reasoning_source = manual_canonical, teacher_model = null. 27B·8B trace로 표시하지 않는다.
- thinking 언어는 학습 데이터의 다른 148 trace(영어 thinking, 질문 표현은 한국어 인용)와 맞췄다.
- 형식: 해당되는 semantic slot만 한 줄씩 + 1–3문장 설명. 장문 reasoning을 흉내 내지 않는다.
"""

GOLD_REVIEW = {
    "b006-05": ("CLEAR_GOLD",
                "'택시를 탄 건수'는 승차 사건 건수(trip_count). '시도는?'은 한 끝의 시도 하나를 묻고 '탄'이 승차 끝을 정한다 → dimension_target pickup. "
                "장소 제한 없음. order top·limit 1. gold와 일치"),
    "b006-15": ("CLEAR_GOLD",
                "'부산에서 손님을 태운'의 '에서'는 승차 위치 제한 → 부산 od_role pickup. 구(sigungu)는 '태운' 사건 끝으로 묶음 → dimension_target pickup. "
                "두 slot은 따로 판단해도 같은 끝. bottom 2. gold와 일치"),
    "b006-20": ("CLEAR_GOLD",
                "'대구에서 승차'는 'A에서 출발'과 같은 꼴 → 대구 od_role pickup. '승차가 가장 적었던 구' → sigungu·pickup. bottom 1. gold와 일치"),
    "b006-26": ("CLEAR_GOLD",
                "'대구 수성구에서 손님을 … 태운' → 수성구(region 대구) od_role pickup. 'H3 셀' → h3, '태운' 사건 끝 → dimension_target pickup "
                "(P0 정의는 trip을 나누는 모든 dimension에 적용). bottom 3. gold와 일치"),
    "b006-19": ("CLEAR_GOLD",
                "'대구에서 하차'의 '에서'는 하차 위치 제한 → 대구 od_role dropoff. '하차가 가장 적었던 구' → sigungu·dropoff. bottom 1. "
                "b006-20과 대칭이지만 질문 표현(하차)에서 직접 읽음. gold와 일치"),
    "b006-34": ("CLEAR_GOLD",
                "'대구 수성구에서 탄 손님들' → 수성구 od_role pickup(장소 제한 끝). '내린 곳 중 … H3 셀' → h3·dimension_target dropoff(묶는 끝). "
                "'가장 드문 … 두 곳' → bottom 2. measure는 그 손님들의 실차 건수(trip_count, text '손님'). 'H3 셀'은 dimension이지 concept·measure text가 아니다. gold와 일치"),
}

RATIONALE = {
    "b006-05": """measure: trip_count — '택시를 탄 건수' counts taxi rides, i.e. trips.
place restriction: none.
grouping dimension: sido — '시도'.
dimension_target: pickup — '탄' is the boarding event, so each ride is counted at the sido where it was boarded.
order / limit: top, 1 — '가장 많은 … 시도는?' asks for one sido.

'택시를 탄' does not only name the trip; it also says which end of the trip is grouped. Because one sido is asked for, the grouping cannot be an origin–destination pair, and there is no place concept, so no od_role.""",
    "b006-15": """measure: trip_count — '손님을 태운 건수' counts trips, so no taxi_status is added.
place restriction: 부산 (name 부산, region "").
place od_role: pickup — '부산에서 손님을 태운': 부산 is where the passengers were picked up.
grouping dimension: sigungu — '구'.
dimension_target: pickup — the districts are compared by the boarding event '태운', so trips are grouped at their pickup end.
order / limit: bottom, 2 — '가장 적은 구 두 곳'.

The place od_role and the dimension_target are two separate decisions: 부산 restricts where the pickup happened, and the districts are grouped by where the pickup happened. Here both point to pickup.""",
    "b006-20": """measure: trip_count — '승차' counts boardings, one per trip.
place restriction: 대구 (name 대구, region "").
place od_role: pickup — '대구에서 승차' has the same shape as 'A에서 출발'; 대구 restricts the boarding end.
grouping dimension: sigungu — '구'.
dimension_target: pickup — '승차가 가장 적었던 구' ranks districts by boardings.
order / limit: bottom, 1 — '가장 적었던 구는?'.

대구 is not only a search area: '에서' attaches to the boarding, so the place gets od_role pickup, and the grouping end is decided separately from the same word '승차'.""",
    "b006-26": """measure: trip_count — '손님을 … 태운' counts pickups, one per trip.
place restriction: 대구 수성구 (name 수성구, region 대구).
place od_role: pickup — '대구 수성구에서 손님을 태운': the pickups happened in 수성구.
grouping dimension: h3 — 'H3 셀'.
dimension_target: pickup — the cells are compared by how many passengers were picked up there; dimension_target applies to h3 cells just as to districts.
order / limit: bottom, 3 — '가장 적게 태운 … 세 곳'.

수성구 restricts the pickup end, and the H3 cells are also grouped at the pickup end; these are two separate decisions that happen to agree.""",
    "b006-19": """measure: trip_count — '하차' counts alightings, one per trip.
place restriction: 대구 (name 대구, region "").
place od_role: dropoff — '대구에서 하차': passengers got off in 대구, so 대구 restricts the dropoff end of the trip.
grouping dimension: sigungu — '구'.
dimension_target: dropoff — '하차가 가장 적었던 구' ranks districts by where passengers got off.
order / limit: bottom, 1 — '가장 적었던 구는?'.

The event word here is '하차' (getting off), not a pickup word. It decides both the place restriction (대구 limits the dropoff end) and, separately, the grouping end (districts grouped by dropoff).""",
    "b006-34": """measure: trip_count — the rides of '손님들' are counted; the measure text is what is counted ('손님'), not the grouping unit.
place restriction: 대구 수성구 (name 수성구, region 대구).
place od_role: pickup — '대구 수성구에서 탄 손님들': these passengers boarded in 수성구.
grouping dimension: h3 — 'H3 셀' is the unit the results are split into. It is a dimension factor, not a concept, and not the text of the measure.
dimension_target: dropoff — '내린 곳 중': the cells are where those passengers got off.
order / limit: bottom, 2 — '가장 드문 … 두 곳'.

The two ends differ: od_role pickup restricts where the trips started, and dimension_target dropoff groups them by where they ended.""",
}

REVIEW_CHECKS = ("질문 표현 근거", "gold와 의미 충돌 없음", "없는 ontology 규칙 없음", "od_role·dimension_target 구분",
                 "묶음 단위어를 concept로 만들지 않음", "장문 reasoning 아님")
CANONICAL_REASON = {
    "b006-05": "implicit endpoint(pickup, 장소 없음): 27B P1/P2 batch 5/5 dimension_target 생략",
    "b006-15": "implicit endpoint(pickup): 27B 5/5 dimension_target·od_role 생략",
    "b006-20": "implicit endpoint(pickup): 27B 5/5 od_role 생략",
    "b006-26": "implicit endpoint(pickup, h3): 27B 5/5 od_role 생략, 4/5 dimension_target 생략",
    "b006-19": "implicit endpoint(dropoff): 27B remaining batch 5/5 od_role 생략",
    "b006-34": "27B top-1이 'H3 셀'을 measure text로 써서 거부(reasoning-final 충돌), 규칙상 대체 없음",
}
REVIEW = {i: ("APPROVE_CANONICAL", list(REVIEW_CHECKS), note) for i, note in {
    "b006-05": "slot이 질문 표현('탄', '시도는?', '가장 많은')에서 나온다. 장소가 없어 od_role 없음을 명시",
    "b006-15": "od_role(부산에서 → 승차 위치)과 dimension_target(태운 → 묶는 끝)을 따로 결정한다고 적음. taxi_status를 넣지 않는 이유를 P0 규칙 범위 안에서만 씀",
    "b006-20": "'A에서 출발' 예시와의 대응만 사용. 새 규칙 없음",
    "b006-26": "h3에도 dimension_target이 적용됨을 P0 정의('trip을 dimension으로 나누면') 범위에서 씀",
    "b006-19": "pickup 문장 치환이 아니라 '하차' 표현에서 두 slot을 각각 읽음",
    "b006-34": "'H3 셀'이 dimension이고 concept·measure text가 아님을 명시. measure text '손님'은 gold와 같음",
}.items()}
