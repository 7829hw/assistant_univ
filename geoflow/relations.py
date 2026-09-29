# -*- coding: utf-8 -*-
"""질문의 관계를 닫힌 어휘와 문형으로 읽어 LLM grounding과 대조한다(조건 계층의 일부).

읽는 것

- 장소의 출발·도착 역할(od_role): 장소 뒤의 **조사 + 서술어**로 정한다. 조사 하나로 정하지
  않는다. "부산에서 하차가 많은"의 부산은 하차가 일어난 곳(dropoff), "수성구에서 출발한"의
  수성구는 출발지(pickup), "초량동으로 들어온"은 도착지다. "X에서 Y로/까지"는 X 출발·Y 도착,
  "X 안에서 … 노선/이동"은 같은 장소가 출발·도착 두 역할을 맡는다(개념을 둘로 나누고 조회는
  한 번 한다, ``executor.REUSABLE_LOOKUPS``).
- 그룹 기준(dimension)과 그 적용 위치(dimension_target): 단위 말(읍면동·시군구·시도·H3·요일)과
  그 단위에 붙은 승차·하차 말. 장소의 역할을 정한 말은 따로 떼어 본다("수성구에서 **출발**한
  실차의 **도착** 읍면동"은 출발지로 거르고 도착지로 묶는다). "간", "노선", "OD", "승하차"는
  출발·도착 조합(both)이다.
- 순위 방향(order)과 개수(limit): 상위·하위, 많은·적은, 높은·낮은 같은 말. 측정값의 집계어
  (최대·최소·최댓값·최솟값)는 순위 방향이 아니므로 뺀다.
- 집계 단계(aggregation, rollup): 집계어의 종류와 자리. 구간(주별·월별)이 있으면 앞의 집계어가
  구간 안(aggregation), 뒤의 집계어가 구간 사이(rollup)다. 집계어가 하나뿐이면 측정값 뒤의 말은
  rollup이고 구간 안 집계는 질문에 없다(없는 집계를 만들어 넣지 않는다).
- 답의 대상: "수입 합계가 가장 큰 주는?"처럼 값이 아니라 구간(주·달)을 묻는 질문. Tool은 구간별
  대표값 하나만 돌려주므로 답할 수 없다(``BUCKET_SELECTION_UNSUPPORTED``). 지역·요일을 묻는 순위는
  dimension으로 답할 수 있으므로 여기에 들지 않는다.

LLM 값과의 관계(``settle``)

| 질문 근거 | LLM 값 없음 | LLM 값 같음 | LLM 값 다름 |
|---|---|---|---|
| 분명함(clear): 한 가지로만 읽힘 | 채움(filled) | 확인(confirmed) | 바로잡음(corrected) |
| 서로 어긋남(conflicting) | 확인 요청 | 확인 요청 | 확인 요청 |
| 없음(none) | 그대로 | 그대로 | 그대로 |

"분명함"은 규칙 하나가 한 값만 내고 반대 표현이 없다는 뜻이다. 집계는 예외가 하나 있다. 질문에
집계어도 집계 단서도 없는데 LLM이 적은 집계는 근거가 없으므로 지운다(removed_no_evidence). 모든
기록은 근거 표현(evidence: 원문 조각과 위치), 변경 전후 값, 적용 이유(basis)를 남긴다.

한계: 어휘와 문형은 닫혀 있다. 목록 밖 표현은 "없음"이 되어 LLM 값을 그대로 둔다. 이 모듈은 질문
원문과 grounding만 본다(문항 id·정답을 보지 않는다).
"""

import copy
import re

from geoflow.errors import PlannerError

CLEAR = "clear"
CONFLICTING = "conflicting"
NONE = "none"

#: scope 문자열. 안의 글자(h3 등)는 단위 말이 아니다.
_SCOPE_LITERAL = re.compile(r"scope:[A-Za-z0-9_:.-]+")


def _error(code, message, *, clarify=None, context=None, raw_text=""):
    return PlannerError(
        message, user_message=message, code=code,
        context={"raw_text": raw_text, "condition_error": True,
                 **({"needs_clarification": True, "clarify": clarify} if clarify else {}),
                 **(context or {})},
    )


def _evidence(match, offset=0):
    return {"text": match.group(0).strip(), "start": match.start() + offset}


def settle(record, llm_value, reading, *, default=None):
    """읽은 값(reading = (strength, value, evidence))과 LLM 값으로 처리를 정한다. 값을 돌려준다.

    ``default``는 생략했을 때 Tool이 쓰는 값이다. LLM이 비운 자리를 질문이 그 값으로 말하면 뜻이
    같으므로 바꾸지 않고 confirmed_equivalent로 적는다(예: "평균 요금"의 aggregation 생략).
    """
    strength, value, evidence = reading
    record.update(llm_value=llm_value, evidence=evidence, strength=strength)
    if strength == CLEAR:
        record["value"] = value
        if llm_value is None and default is not None and value == default:
            record.update(action="confirmed_equivalent", basis="question_expression_equals_default")
            return None
        if llm_value == value:
            record.update(action="confirmed", basis="question_expression")
        elif llm_value is None:
            record.update(action="filled", basis="question_expression")
        else:
            record.update(action="corrected", basis="question_expression_over_llm_value")
        return value
    record.update(value=llm_value, action="none",
                  basis="no_expression" if strength == NONE else "conflicting_expressions")
    return llm_value


# -- 장소의 출발·도착 역할 ----------------------------------------------------------

#: 조사와 서술어 사이에 낱말 하나까지 끼어들 수 있다("대구에서 택시를 탄", "부산에서 가장 하차가").
_W = r"(?:[^\s?]+\s+)?"
_FROM = r"(?:에서|부터)"
_TO = r"(?:으로|로|까지|에)"
#: 장소 뒤 문형 → 역할. 위에서부터 처음 맞는 것 하나. 서술어가 역할을 정하고, 이동 동사는 조사의
#: 방향(에서/부터 ↔ 으로/로/까지/에)으로 정한다.
_ROLE_RULES = (
    ("pickup", "noun_origin", rf"^\s*(?:출발|발)(?:지|하는|한|해|하여|인)?(?=\s|$)"),
    ("dropoff", "noun_destination", rf"^\s*(?:도착|착)(?:지|하는|한|해|하여|인)?(?=\s|$)"),
    ("pickup", "from_boarding", rf"^\s*{_FROM}\s*{_W}(?:출발|승차|탑승|타고|탄(?=\s))"),
    ("dropoff", "from_alighting", rf"^\s*에서\s*{_W}(?:하차|내린|내려|내리|도착)"),
    ("pickup", "from_leaving", rf"^\s*{_FROM}\s*{_W}(?:나간|나온|나가|떠난|이동|간(?=\s)|가는)"),
    ("dropoff", "to_arriving",
     rf"^\s*{_TO}\s*{_W}(?:들어|도착|이동|향|가는|간(?=\s)|온(?=\s)|오는|하차|내린|내려|출발)"),
    ("dropoff", "genitive_alighting", rf"^\s*의\s*{_W}(?:하차|도착)"),
    ("pickup", "genitive_boarding", rf"^\s*의\s*{_W}(?:승차|탑승|출발)"),
)
#: "X 안에서", "X 내", "X 내부" + 이동·노선 문맥 → 같은 장소가 출발·도착 둘 다.
_WITHIN = re.compile(r"^\s*(?:안에서|내에서|내부에서|안|내부|내)(?:의|에서)?(?=\s|$)")
_ROUTE_CONTEXT = re.compile(r"노선|\bOD\b|간\s|간의|이동|오간|오고\s*간")
#: "X에서 Y로/까지"의 X. 서술어 없이 출발 조사만 있고 다음 장소가 도착으로 읽힐 때.
#: 조사 뒤에 다음 장소의 지역명 같은 낱말 하나("신천동에서 부산 초량동까지")까지는 괜찮다.
_BARE_FROM = re.compile(rf"^\s*{_FROM}\s*(?:(?!출발|도착|승차|하차|이동)[^\s?]+\s*)?$")
_PAIR_TO = re.compile(r"^\s*(?:으로|로|까지)")


def _place_names(concept):
    """장소 개념의 조회 이름. 단위 말("읍면동")을 이름으로 적은 것은 장소가 아니므로 비운다."""
    from geoflow.grounding import NON_PLACE_WORDS

    value = concept.get("value")
    if isinstance(value, dict):
        name = (value.get("name") or "").strip()
        region = (value.get("region") or "").strip()
        if name in NON_PLACE_WORDS:
            name = ""
        return [name] if name else ([region.split()[-1]] if region else [])
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _occurrences(question, name):
    """name이 질문에 낱말 머리로 나타나는 위치들. "달서구" 안의 "서구"는 세지 않는다."""
    spots = []
    for match in re.finditer(re.escape(name), question):
        before = question[match.start() - 1] if match.start() else " "
        if re.match(r"[가-힣A-Za-z0-9]", before) and not name.startswith("scope:"):
            continue
        spots.append((match.start(), match.end()))
    return spots


def location_concepts(concepts):
    return [item for item in concepts or [] if isinstance(item, dict)
            and item.get("concept") == "LOCATION"
            and item.get("subtype") in ("place", "scope", "vicinity_scope")
            and item.get("source") == "user"]


def _with_region(question, concept, spots):
    """장소 이름 바로 앞에 그 region이 있으면 mention을 region부터로 넓힌다("부산 초량동")."""
    value = concept.get("value")
    region = (value.get("region") or "").strip() if isinstance(value, dict) else ""
    if not region:
        return spots
    widened = []
    for start, end in spots:
        head = question[:start].rstrip()
        if head.endswith(region):
            start = len(head) - len(region)
        widened.append((start, end))
    return widened


def _mentions(concepts, question):
    """LOCATION 개념 → 질문 속 (start, end) 목록. 같은 이름의 개념이 여럿이면 차례로 나눠 준다."""
    by_name = {}
    for concept in location_concepts(concepts):
        names = _place_names(concept)
        if names:
            by_name.setdefault(names[0], []).append(concept)
    spans = {}
    for name, group in by_name.items():
        spots = _with_region(question, group[0], _occurrences(question, name))
        if len(group) > 1 and len(spots) >= len(group):
            for concept, spot in zip(group, spots):
                spans[id(concept)] = [spot]
        else:
            for concept in group:
                spans[id(concept)] = list(spots)
    return spans


def _read_window(window, question):
    """장소 뒤 조각 하나의 역할. (역할, 규칙, 근거 match) 또는 None."""
    within = _WITHIN.match(window)
    if within:
        if _ROUTE_CONTEXT.search(question):
            return "within", "within_route", within
        # 이동 문맥이 없으면 "안에서"는 "에서"와 같다("부산 안에서 승차가 많은").
        window = "에서" + window[within.end():]
    for role, rule, pattern in _ROLE_RULES:
        match = re.match(pattern, window)
        if match:
            return role, rule, match
    return None


def read_place_roles(concepts, question):
    """장소 개념마다 (strength, 역할, 근거). 역할은 pickup | dropoff | within."""
    spans = _mentions(concepts, question)
    starts = sorted(start for spots in spans.values() for start, _ in spots)
    readings = {}
    windows = {}
    for concept in location_concepts(concepts):
        found = []
        for start, end in spans.get(id(concept), []):
            following = [s for s in starts if s > start]
            window = question[end:following[0] if following else len(question)]
            windows.setdefault(id(concept), []).append((end, window))
            read = _read_window(window, question)
            if read:
                role, rule, match = read
                found.append((role, rule, {"text": question[start:end] + match.group(0).rstrip(),
                                           "start": start, "rule": rule,
                                           "consumed": (end + match.start(), end + match.end())}))
        readings[id(concept)] = found
    # "X에서 Y로/까지": X 뒤에 출발 조사만 있고, 바로 다음 장소가 도착 조사로 시작한다.
    ordered = sorted(((spots[0][0], concept) for concept in location_concepts(concepts)
                      for spots in [spans.get(id(concept)) or []] if spots), key=lambda x: x[0])
    for (_, first), (_, second) in zip(ordered, ordered[1:]):
        first_window = (windows.get(id(first)) or [(0, "")])[0][1]
        second_window = (windows.get(id(second)) or [(0, "")])[0][1]
        if _BARE_FROM.match(first_window) and not readings[id(first)]:
            pair = _PAIR_TO.match(second_window)
            second_roles = {role for role, _, _ in readings[id(second)]}
            if pair or second_roles == {"dropoff"}:
                start = spans[id(first)][0][0]
                readings[id(first)].append(("pickup", "pair_origin", {
                    "text": question[start:spans[id(second)][0][1]].strip(), "start": start,
                    "rule": "pair_origin", "consumed": None}))
                if not second_roles:
                    readings[id(second)].append(("dropoff", "pair_destination", {
                        "text": question[spans[id(second)][0][0]:spans[id(second)][0][1]]
                        + pair.group(0), "start": spans[id(second)][0][0],
                        "rule": "pair_destination", "consumed": None}))
    result = {}
    for concept in location_concepts(concepts):
        found = readings[id(concept)]
        roles = {role for role, _, _ in found}
        evidence = [item for _, _, item in found]
        if not roles:
            result[id(concept)] = (NONE, None, [])
        elif roles == {"pickup", "dropoff"} or "within" in roles:
            # 한 장소가 출발 서술어와 도착 서술어를 모두 받았다("부산에서 출발해 부산에 도착한").
            result[id(concept)] = (CLEAR, "within", evidence)
        else:
            (role,) = roles
            result[id(concept)] = (CLEAR, role, evidence)
    return result


def reconcile_place_roles(concepts, question):
    """장소의 od_role을 질문 문형으로 정한다. (새 개념 목록, 기록 목록, 소비된 조각)."""
    readings = read_place_roles(concepts, question)
    fixed, records, consumed = [], [], []
    by_value = {}
    for concept in concepts:
        if isinstance(concept, dict) and id(concept) in readings:
            by_value.setdefault(_value_key(concept), []).append(concept)
    handled = set()
    for concept in concepts:
        if not (isinstance(concept, dict) and id(concept) in readings):
            fixed.append(concept)
            continue
        if id(concept) in handled:
            continue
        strength, role, evidence = readings[id(concept)]
        consumed += [item["consumed"] for item in evidence if item.get("consumed")]
        llm_role = _od_role(concept)
        record = {"slot": "od_role", "concept": concept.get("id"),
                  "place": _place_names(concept)[:1]}
        if strength == CLEAR and role == "within":
            siblings = [item for item in by_value[_value_key(concept)] if id(item) not in handled]
            llm_roles = sorted(filter(None, (_od_role(item) for item in siblings)))
            record.update(llm_value=llm_roles or None, value=["dropoff", "pickup"],
                          evidence=evidence, strength=strength)
            if llm_roles == ["dropoff", "pickup"] and len(siblings) == 2:
                record.update(action="confirmed", basis="question_expression")
                fixed += siblings
            else:
                record.update(action="filled" if not llm_roles else "corrected",
                              basis="same_place_both_ends" if not llm_roles
                              else "question_expression_over_llm_value")
                pickup = _with_role(siblings[0], "pickup")
                if len(siblings) >= 2:
                    dropoff = _with_role(siblings[1], "dropoff")
                    extra = siblings[2:]
                else:
                    dropoff = _with_role(siblings[0], "dropoff",
                                         new_id=_fresh_id(concepts, f"{concept.get('id')}_dropoff"))
                    extra = []
                    record["added"] = dropoff["id"]
                fixed += [pickup, dropoff, *extra]
            handled.update(id(item) for item in siblings)
            records.append(record)
            continue
        value = settle(record, llm_role, (strength, role, evidence))
        fixed.append(_with_role(concept, value) if value != llm_role else concept)
        handled.add(id(concept))
        records.append(record)
    return fixed, records, consumed


def drop_unstated_roles(concepts, question):
    """출발·도착 서술어가 없는 장소의 od_role을 지운다. (새 개념 목록, 기록 목록)."""
    readings = read_place_roles(concepts, question)
    fixed, records = [], []
    for concept in concepts:
        if isinstance(concept, dict) and id(concept) in readings and _od_role(concept):
            strength, _, evidence = readings[id(concept)]
            record = {"slot": "od_role", "concept": concept.get("id"),
                      "place": _place_names(concept)[:1], "llm_value": _od_role(concept),
                      "evidence": evidence, "strength": strength}
            if strength == NONE:
                record.update(value=None, action="removed_no_evidence",
                              basis="role_without_od_expression")
                fixed.append(_with_role(concept, None))
            else:
                record.update(value=_od_role(concept), action="none", basis="od_expression_present")
                fixed.append(concept)
            records.append(record)
            continue
        fixed.append(concept)
    return fixed, records


def has_bucket_expression(question):
    return bool(_BUCKET.search(question))


def _value_key(concept):
    value = concept.get("value")
    if isinstance(value, dict):
        return ("place", (value.get("name") or "").strip(), (value.get("region") or "").strip())
    return ("scope", value)


def _od_role(concept):
    return (concept.get("attributes") or {}).get("od_role") or concept.get("od_role")


def _with_role(concept, role, new_id=None):
    item = copy.deepcopy(concept)
    item.pop("od_role", None)
    attributes = dict(item.get("attributes") or {})
    if role is None:
        attributes.pop("od_role", None)
    else:
        attributes["od_role"] = role
    item["attributes"] = attributes
    if new_id:
        item["id"] = new_id
    return item


def _fresh_id(concepts, base):
    taken = {item.get("id") for item in concepts if isinstance(item, dict)}
    candidate, index = base, 2
    while candidate in taken:
        candidate, index = f"{base}{index}", index + 1
    return candidate


# -- 그룹 기준과 적용 위치 ----------------------------------------------------------

_UNITS = (
    ("emd", r"읍면동"),
    ("sigungu", r"시군구"),
    ("sido", r"시도(?=\s|별|간|중|가운데|의|은|는|이|가|를|$)"),
    ("h3", r"H3|h3|(?<![가-힣])셀|격자"),
    ("dayofweek", r"요일"),
)
_PAIR_TARGET = re.compile(r"(?:읍면동|시군구|시도|H3|h3|셀|지역)\s*간|노선|\bOD\b|승하차")
_PICKUP_SIDE = re.compile(r"승차|탑승|출발")
_DROPOFF_SIDE = re.compile(r"(?<!승)하차|도착|들어온|내린")
#: 장소 역할에 쓰인 말 가운데 그룹 기준으로도 이어 읽는 말(사건 명사). 이동 동사(출발·도착)는 뺀다.
_EVENT_SIDE = {"pickup": re.compile(r"승차|탑승"), "dropoff": re.compile(r"(?<!승)하차|내린")}


def _mask(question, spans):
    chars = list(question)
    for start, end in spans:
        for index in range(start, min(end, len(chars))):
            chars[index] = " "
    return "".join(chars)


def _place_spans(concepts, question):
    spans = []
    for spots in _mentions(concepts, question).values():
        spans += spots
    spans += [(m.start(), m.end()) for m in _SCOPE_LITERAL.finditer(question)]
    return spans


def mask_places(concepts, question):
    """장소 이름과 scope 문자열을 같은 길이의 공백으로 가린다("중앙로동"의 "중앙"은 집계어가 아니다)."""
    return _mask(question, _place_spans(concepts, question))


def read_dimension(concepts, question):
    text = _mask(question, _place_spans(concepts, question))
    found = [(name, m) for name, pattern in _UNITS for m in re.finditer(pattern, text)]
    names = {name for name, _ in found}
    evidence = [_evidence(m) for _, m in found]
    if len(names) == 1:
        return CLEAR, next(iter(names)), evidence
    return (CONFLICTING if names else NONE), None, evidence


def read_dimension_target(concepts, question, consumed):
    """그룹 기준을 출발·도착 어느 끝에 적용하는가. consumed = 장소 역할에 쓰인 조각."""
    text = _mask(question, _place_spans(concepts, question))
    pair = [_evidence(m) for m in _PAIR_TARGET.finditer(text)]
    free = _mask(text, consumed)
    pickup = [_evidence(m) for m in _PICKUP_SIDE.finditer(free)]
    dropoff = [_evidence(m) for m in _DROPOFF_SIDE.finditer(free)]
    if pair and (pickup or dropoff) and not (pickup and dropoff):
        return CONFLICTING, None, pair + pickup + dropoff
    if pair or (pickup and dropoff):
        return CLEAR, "both", pair + pickup + dropoff
    if pickup or dropoff:
        return CLEAR, "pickup" if pickup else "dropoff", pickup + dropoff
    # 그룹 쪽에 따로 말이 없으면, 장소 역할을 정한 사건 명사(승차·하차)를 이어 읽는다.
    # "부산에서 하차가 많은 읍면동" = 부산에서 일어난 하차를 하차 읍면동별로 센다.
    inherited = {side: [_evidence(m) for start, end in consumed
                        for m in pattern.finditer(question[start:end])]
                 for side, pattern in _EVENT_SIDE.items()}
    sides = [side for side, items in inherited.items() if items]
    if len(sides) == 1:
        return CLEAR, sides[0], inherited[sides[0]]
    return NONE, None, []


# -- 순위 방향과 개수 ---------------------------------------------------------------

#: 측정값의 집계어. 순위 방향 말과 겹치는 조각("가장 큰 값")을 먼저 가린다.
_AGGREGATION_WORDS = (
    ("sum", r"합계|합산|총합|총량|(?<![가-힣])총(?=\s*[가-힣])|모두\s*더한|더한\s*값|"
            r"(?<![가-힣])합(?=[은이을의]|\s|$)"),
    ("avg", r"평균"),
    ("med", r"중간값|중앙값|중위수|중위값"),
    ("max", r"최댓값|최대값|최대(?!한)|최고치|최고|가장\s*(?:큰|높은|많은)\s*값"),
    ("min", r"최솟값|최소값|최소(?!한)|최저치|최저|가장\s*(?:작은|적은|낮은)\s*값"),
)
_AGGREGATION_CUES = re.compile(r"평균|합|총|중간|중앙|최대|최소|최고|최저|최댓|최솟|누적|더한|더해")
_TOP = re.compile(r"상위|많은|많이|높은|큰(?=\s)|최다")
_BOTTOM = re.compile(r"하위|적은|적게|낮은|작은")
_COUNT = re.compile(r"(?:상위|하위)\s*(\d+)|(\d+)\s*(?:곳|개|위|군데)")


def _aggregation_spans(text):
    """(종류, match) 목록. 겹치면 앞에서 먼저 맞은 긴 것을 쓴다."""
    found = sorted(((name, m) for name, pattern in _AGGREGATION_WORDS
                    for m in re.finditer(pattern, text)),
                   key=lambda item: (item[1].start(), -(item[1].end() - item[1].start())))
    kept, last_end = [], -1
    for name, match in found:
        if match.start() >= last_end:
            kept.append((name, match))
            last_end = match.end()
    return kept


def read_order(question):
    text = _mask(question, [(m.start(), m.end()) for _, m in _aggregation_spans(question)])
    top = [_evidence(m) for m in _TOP.finditer(text)]
    bottom = [_evidence(m) for m in _BOTTOM.finditer(text)]
    if top and bottom:
        return CONFLICTING, None, top + bottom
    if top or bottom:
        return CLEAR, "top" if top else "bottom", top + bottom
    return NONE, None, []


def read_limit(question):
    counts = [(int(m.group(1) or m.group(2)), m) for m in _COUNT.finditer(question)]
    values = {value for value, _ in counts}
    if len(values) == 1:
        return CLEAR, next(iter(values)), [_evidence(m) for _, m in counts]
    if values:
        return CONFLICTING, None, [_evidence(m) for _, m in counts]
    single = re.search(r"(?:가장|제일)", question)
    if single:
        return CLEAR, 1, [_evidence(single)]
    return NONE, None, []


# -- 집계 단계와 답의 대상 ------------------------------------------------------------

_BUCKET = re.compile(r"주별|월별|달별|주\s*단위|월\s*단위|달\s*단위|매주|매월|매달|주마다|달마다|월마다|"
                     r"각\s*주|각\s*달|각\s*월")
_BUCKET_ANSWER = re.compile(
    r"(?:가장|제일)\s*(?:[^\s?]+\s+)?(?:큰|많은|높은|작은|적은|낮은)\s*(?:주|달|월)(?=\s*(?:[은는이가]|\?|$))"
    r"|어느\s*(?:주|달|월)")


def read_answer_target(question):
    match = _BUCKET_ANSWER.search(question)
    if match:
        return CLEAR, "bucket", [_evidence(match)]
    return NONE, "value", []


def read_stages(question, measure_position):
    """구간 질문의 (aggregation 읽기, rollup 읽기). 각각 (strength, value, evidence)."""
    bucket = _BUCKET.search(question)
    words = _aggregation_spans(question)
    none = (NONE, None, [])
    if not bucket:
        return none, none
    if len(words) == 2:
        (inner, m1), (outer, m2) = words
        return (CLEAR, inner, [_evidence(m1)]), (CLEAR, outer, [_evidence(m2)])
    if len(words) == 1 and measure_position is not None:
        name, match = words[0]
        if match.start() > measure_position and match.start() > bucket.start():
            # 측정값 뒤의 말 하나는 구간 사이 집계다. 구간 안 집계는 질문에 없다.
            if _AGGREGATION_CUES.search(_mask(question, [(match.start(), match.end())])):
                return none, (CLEAR, name, [_evidence(match)])
            return (CLEAR, None, [{"text": "", "start": None, "note": "inner_not_stated"}]), \
                (CLEAR, name, [_evidence(match)])
        if bucket.start() < match.start() < measure_position:
            return (CLEAR, name, [_evidence(match)]), none
    return none, none


def read_flat_aggregation(question, *, grouped_by_dimension):
    """구간 없는 질문의 집계. 집계어가 한 종류면 그것, 없고 단서도 없으면 '없음이 분명'."""
    words = _aggregation_spans(question)
    names = {name for name, _ in words}
    if len(names) == 1:
        return CLEAR, next(iter(names)), [_evidence(m) for _, m in words]
    if names:
        return CONFLICTING if not grouped_by_dimension else NONE, None, \
            [_evidence(m) for _, m in words]
    if _AGGREGATION_CUES.search(question):
        return NONE, None, []
    return CLEAR, None, [{"text": "", "start": None, "note": "no_aggregation_word"}]
