# -*- coding: utf-8 -*-
"""질문이 **명시한** 구간 정의(주 시작 요일, 부분 구간, 빈 구간)를 읽는다.

"주별 평균 가동률"은 주가 무슨 요일에 시작하는지, 기간 경계에서 잘린 주를 넣는지, 자료가
없는 주를 어떻게 다루는지 말하지 않는다. 그런 정의는 질문의 뜻이 아니므로 의미 graph에
고정하지 않는다. 계산 경로가 정한다: 업체 Tool에 맡기면 제공자의 정의, GeoFlow가 기간을
나눠 다시 계산하면 애플리케이션 정책(``geoflow/periods.py``)이 쓰인다(``compiler``).

반대로 사용자가 "일요일부터 시작하는 주", "완전한 주만", "자료가 없는 주는 0으로"처럼
정의를 말했다면 그것은 질문의 조건이다. 어느 경로든 그 조건을 표현하거나 보장할 수 있을
때만 실행하고, 제공자 기본값으로 조용히 바꾸지 않는다.

이 모듈은 닫힌 어휘로만 읽는다. LLM grounding을 대신하지 않으며, grounding과 무관하게
질문 원문에서 항상 읽는다(조건을 조용히 잃지 않기 위해). 단서 표현은 있는데 문법으로 읽지
못하면 추측하지 않고 ``unreadable``로 남겨 합성이 확인을 요청한다.

값 어휘
- ``week_start``: monday … sunday
- ``partial``: ``include``(기간 경계에서 잘린 구간도 넣음) | ``exclude``(온전한 구간만)
  단위는 주·달·월이다. "구간"은 도로 구간과 구분되지 않아 단위로 읽지 않는다.
- ``empty``: ``zero``(자료 없는 구간을 0으로 넣음) | ``skip``(자료 없는 구간을 뺌)
"""

import re
from dataclasses import dataclass, field

WEEK_START = "week_start"
PARTIAL = "partial"
EMPTY = "empty"
KEYS = (WEEK_START, PARTIAL, EMPTY)

WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
_KOREAN_DAYS = dict(zip("월화수목금토일", WEEKDAYS))
PARTIAL_VALUES = ("include", "exclude")
EMPTY_VALUES = ("zero", "skip")

#: 답변·오류에 쓰는 이름.
LABELS = {WEEK_START: "주 시작 요일", PARTIAL: "기간 경계에서 잘린 구간", EMPTY: "자료가 없는 구간"}
VALUE_LABELS = {
    **{day: f"{korean}요일" for korean, day in _KOREAN_DAYS.items()},
    "include": "포함", "exclude": "제외(온전한 구간만)",
    "zero": "0으로 포함", "skip": "제외",
}

_DAY = r"([월화수목금토일])요일"
#: 구간 단위. "구간"은 이 도메인에서 도로 구간(edge)을 뜻하는 경우가 많아 단위로 읽지 않는다.
#: 단위 뒤에는 조사·"별"·"마다"만 온다. "주차", "주행", "주말", "월요일"을 단위로 읽지 않기 위해서다.
#: 단위 뒤의 경계(조사·"별"·"마다"·접속 조사).
_B = r"(?=$|[^가-힣]|[은는을를이가도만의별마다에로까부와과])"
_UNIT = r"(?:주|달|월)" + _B
_PATTERNS = (
    # 주 시작 요일
    (WEEK_START, re.compile(_DAY + r"\s*(?:부터|에)?\s*시작(?:하는|되는|인|한)?\s*주"
                            + _B), None),
    (WEEK_START, re.compile(r"주\s*(?:의\s*)?시작\s*(?:요일|일)?\s*(?:은|는|을|를|이|가)?\s*"
                            + _DAY), None),
    (WEEK_START, re.compile(_DAY + r"\s*(?:기준|시작)\s*(?:의\s*)?주"
                            + _B), None),
    (WEEK_START, re.compile(_DAY + r"\s*[~\-]\s*[월화수목금토일]요일\s*(?:기준\s*)?(?:의\s*)?주"
                            + _B), None),
    # 부분 구간
    (PARTIAL, re.compile(r"(?:완전한|온전한|꽉\s*찬|빠짐없는)\s*" + _UNIT + r"\s*만"), "exclude"),
    (PARTIAL, re.compile(r"(?:부분|잘린|일부)\s*" + _UNIT
                         + r"\s*(?:은|는|을|를)?\s*(?:제외|빼|뺀|버리|버린)"), "exclude"),
    (PARTIAL, re.compile(r"(?:부분|잘린|일부)\s*" + _UNIT + r"\s*(?:도|까지)?\s*(?:포함|넣)"),
     "include"),
    # 빈 구간
    (EMPTY, re.compile(r"(?:자료|데이터|기록|운행|값|영업)\s*(?:이|가)?\s*없는\s*" + _UNIT
                       + r"\s*(?:은|는|도)?\s*0\s*(?:으로|로)"), "zero"),
    (EMPTY, re.compile(r"빈\s*" + _UNIT + r"\s*(?:은|는|도)?\s*0\s*(?:으로|로)?"), "zero"),
    (EMPTY, re.compile(r"(?:자료|데이터|기록|운행|값|영업)\s*(?:이|가)?\s*없는\s*" + _UNIT
                       + r"\s*(?:은|는|을|를)?\s*(?:제외|빼|뺀|버리)"), "skip"),
    (EMPTY, re.compile(r"빈\s*" + _UNIT + r"\s*(?:은|는|을|를)?\s*(?:제외|빼|뺀|버리)"), "skip"),
)
#: 구간 정의를 말하려는 단서. 위 문법으로 읽지 못하면 unreadable이다. "이번 주 시작부터"처럼
#: 기간을 말하는 표현은 단서가 아니다.
_CUES = re.compile(
    r"주\s*(?:의\s*)?시작\s*(?:요일|일|기준)|주\s*(?:의\s*)?시작\s*(?:은|는|을|를|이|가)(?=\s|$)"
    r"|요일\s*(?:부터\s*)?시작(?:하는|되는|인|한)?\s*" + _UNIT
    + r"|요일\s*기준\s*(?:의\s*)?" + _UNIT
    + r"|(?:부분|잘린)\s*" + _UNIT + r"|빈\s*" + _UNIT
    + r"|(?:자료|데이터|기록|값)\s*(?:이|가)?\s*없는\s*" + _UNIT
    + r"|(?:완전한|온전한)\s*" + _UNIT
)


@dataclass(frozen=True)
class CalendarRequirements:
    """질문이 명시한 구간 정의. 빈 값은 "질문이 정하지 않음"이다."""

    stated: dict = field(default_factory=dict)
    #: key → 근거 표현. 답변과 기록이 쓴다.
    evidence: dict = field(default_factory=dict)
    #: 단서는 있었지만 읽지 못한 표현.
    unreadable: tuple = ()

    def __bool__(self):
        return bool(self.stated or self.unreadable)

    def get(self, key):
        return self.stated.get(key)

    def to_dict(self):
        record = {"stated": dict(self.stated), "evidence": dict(self.evidence)}
        if self.unreadable:
            record["unreadable"] = list(self.unreadable)
        return record


NONE = CalendarRequirements()


def read(question):
    """질문 원문에서 명시된 구간 정의를 읽는다. 서로 다른 값이 함께 있으면 unreadable이다."""
    text = question or ""
    found, spans = {}, []
    for key, pattern, fixed in _PATTERNS:
        for match in pattern.finditer(text):
            spans.append(match.span())
            found.setdefault(key, []).append(
                (fixed or _KOREAN_DAYS[match.group(1)], match.group(0)))
    stated, evidence, unread = {}, {}, []
    for key, items in found.items():
        if len({value for value, _ in items}) > 1:
            # "일요일 시작 … 월요일 시작"처럼 서로 다른 정의. 어느 쪽인지 고르지 않는다.
            unread.extend(phrase for _, phrase in items)
            continue
        stated[key], evidence[key] = items[0]
    unread += [match.group(0) for match in _CUES.finditer(text)
               if not any(lo <= match.start() < hi for lo, hi in spans)]
    unreadable = tuple(dict.fromkeys(unread))
    if not stated and not unreadable:
        return NONE
    return CalendarRequirements(stated=stated, evidence=evidence, unreadable=unreadable)


def describe(key, value):
    return f"{LABELS[key]} {VALUE_LABELS.get(value, value)}"
