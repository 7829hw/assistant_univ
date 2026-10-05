# -*- coding: utf-8 -*-
"""질문의 날짜·택시 유형·장소 조건을 원문 근거와 함께 보존한다(선택 기능).

``GeoFlowPlanner(condition_check=True)``일 때만 쓰인다. 기본 동작은 바뀌지 않는다.
LLM이 적은 grounding(payload)을 검증하기 전에, 질문 원문을 **닫힌 어휘와 문법**으로
읽어 조건을 다시 정한다.

    질문의 근거 표현 → 해석된 조건 → (의미 graph의 적용 대상 → 실행 인자 → 답변)

역할 분담

- 날짜: 해석을 코드로 옮긴다. 지원 표현을 찾으면 그 값이 date가 된다. LLM이 적은 값과
  다르면 질문 표현을 따르고(conflict → corrected) LLM 값과 근거를 기록한다. 상대 날짜의
  절대 범위는 주입된 기준일(Asia/Seoul 날짜)로만 계산한다. 이 해석은 **기록**이다. 실제
  요청 인자와 그 provider 의미는 compiler의 date 정책이 정한다(condition_check 경로는
  계약으로 확인된 기간만 실행, ``geoflow/compiler.py`` DATE_POLICY_GUARANTEED).
- 택시 유형: "개인(용)택시", "법인(용)택시", "회사택시", "전체/모든 택시"를 찾는다.
  부정·여러 유형은 지원하지 않는다. all은 생략과 실행 의미가 같고, 명시 여부는 stated에 남긴다.
- 장소: LLM이 적은 장소명이 질문에 문자열 근거가 있는지 본다.
- 관계(``geoflow/relations.py``, grounding_v2): 장소의 출발·도착 역할, 그룹 기준과 적용 위치, 순위 방향과
  개수, 집계 단계, 답의 대상(값인가 구간인가), 측정값과 암묵 사건. 근거가 분명한 누락은 채우고 충돌은
  바로잡으며, 반대 표현이 함께 있으면 확인을 요청하고, 읽지 못하면 LLM 값을 둔다. 근거 없는 집계·역할은 지운다.

조건 상태(``STATUS_*``): interpreted / conflict / ambiguous / unverifiable / absent /
unsupported. 규칙이 읽지 못했다는 것만으로 부재를 확정하지 않는다. LLM 값은 그 근거 표현이
질문에 없고 조건 단서도 없을 때만 지운다. 단서가 남으면 보류(held)하고 검증된 값으로 적지 않는다.

한계(검증하지 않는 것)

- 문자열이 질문에 있다는 것은 해석이 맞다는 보장이 아니다. 단서 어휘는 닫혀 있어, 목록 밖
  표현이 단서도 남기지 않으면 부재로 판정된다.
- 장소 누락, 장소의 지역 의미, 닫힌 문형 밖의 출발/도착 관계는 검증하지 않는다(``NOT_CHECKED``).
- 평가 라벨을 쓰지 않는다. 이 모듈은 질문 원문과 기준일만 본다.

지원 날짜 표현(이 밖은 "해석 불가"로 두고 LLM 값을 바꾸지 않는다)

    명시   YYYYMMDD, YYYYMMDD-YYYYMMDD, YYYY년 M월 D일, YYYY년 M월 D일부터 (M월) D일까지,
           YYYY년 M월, YYYY년 M월부터 (YYYY년) M월까지, YYYY년 M월과 M월(연속),
           YYYY년 상반기/하반기, YYYY년
    상대   지난주/저번 주 → last_week, 지난달/저번 달 → last_month, 작년/지난해 → last_year,
           이번 주/금주 → this_week, 이번 달/이달 → this_month, 올해/금년 → this_year,
           어제/오늘 → 기준일로 계산한 YYYYMMDD ("전주"는 지명과 겹쳐 쓰지 않는다), 주말/평일/주중/휴일/공휴일 → pt_date 토큰
    미지원 최근·지난 N일/주/개월/달/년, 최근 한 달, 일주일, 그저께, 지난·이번 주말, 분기,
           연휴, 추석·설날 등 명절, 단독 "최근"
    모호   연도 없는 월·일("8월", "8월 3일")
"""

import calendar
import copy
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from geoflow.errors import PlannerError
from geoflow.periods import _relative as resolve_relative

SERVICE_TIMEZONE = ZoneInfo("Asia/Seoul")

SUPPORTED = "supported"
AMBIGUOUS = "ambiguous"
UNSUPPORTED = "unsupported"

#: pt_date 상대 토큰. TIMS의 해석은 계약에 없다(tims_contract relative_date_reference).
RELATIVE_TOKENS = {"last_week", "last_month", "last_year",
                   "this_week", "this_month", "this_year"}
CALENDAR_TOKENS = {"weekday", "weekend", "holiday"}


def seoul_date(instant):
    """시각을 Asia/Seoul 날짜로 바꾼다. naive 시각은 받지 않는다."""
    if instant.tzinfo is None:
        raise ValueError("시간대가 없는 시각은 기준 시각으로 쓸 수 없습니다.")
    return instant.astimezone(SERVICE_TIMEZONE).date()


@dataclass(frozen=True)
class Mention:
    kind: str          # date | taxi_type
    text: str          # 질문에 있던 표현
    status: str        # supported | ambiguous | unsupported
    value: str | None = None
    meaning: str = ""  # 구조화된 상대 의미 또는 해석 설명
    start: int = 0

    def to_dict(self):
        return {"kind": self.kind, "text": self.text, "status": self.status,
                "value": self.value, "meaning": self.meaning}


def _d(year, month, day):
    return date(int(year), int(month), int(day))


def _text(day):
    return day.strftime("%Y%m%d")


def _month_range(year, month):
    last = calendar.monthrange(int(year), int(month))[1]
    return _d(year, month, 1), _d(year, month, last)


def _range(start, end):
    return _text(start) if start == end else f"{_text(start)}-{_text(end)}"


# 순서가 중요하다. 먼저 걸린 표현의 글자는 뒤 패턴이 다시 쓰지 않는다.
_UNSUPPORTED_DATE = (
    r"(최근|지난)\s*(\d+|한|두|세|네|일)\s*(일|주일|주|개월|달|년)",
    r"최근\s*일주일|일주일\s*동안|일주일간",
    r"지난\s*주말|저번\s*주말|이번\s*주말",
    r"그저께|그제|엊그제",
    r"\d\s*분기|분기|연휴|추석|설날|명절|크리스마스|성탄절|방학|휴가철",
    r"최근",
)
_RELATIVE_DATE = (
    (r"지난\s*주|저번\s*주", "last_week", "직전 달력 주(월~일)"),
    (r"지난\s*달|저번\s*달|전월|지난\s*월", "last_month", "직전 달력 월"),
    (r"작년|지난\s*해|전년", "last_year", "직전 달력 연도"),
    (r"이번\s*주|금주", "this_week", "기준일이 속한 달력 주(월요일부터 기준일까지)"),
    (r"이번\s*달|이달|금월", "this_month", "기준일이 속한 달력 월(1일부터 기준일까지)"),
    (r"올해|금년|이번\s*(해|년)", "this_year", "기준일이 속한 달력 연도(1월 1일부터 기준일까지)"),
    (r"어제", "yesterday", "기준일 하루 전"),
    (r"오늘", "today", "기준일"),
    (r"주말", "weekend", "주말(pt_date 토큰)"),
    (r"평일|주중", "weekday", "평일(pt_date 토큰)"),
    (r"공휴일|휴일", "holiday", "휴일(pt_date 토큰)"),
)
_Y, _M, _D = r"(\d{4})\s*년", r"(\d{1,2})\s*월", r"(\d{1,2})\s*일"
_UNTIL = r"\s*(?:부터|에서|~|-)\s*"


def _explicit_patterns():
    return (
        (r"(?<!\d)(\d{8})\s*[-~]\s*(\d{8})(?!\d)",
         lambda m: (_d(m[1][:4], m[1][4:6], m[1][6:]), _d(m[2][:4], m[2][4:6], m[2][6:]))),
        (rf"{_Y}\s*{_M}\s*{_D}{_UNTIL}(?:(\d{{4}})\s*년\s*)?(?:(\d{{1,2}})\s*월\s*)?{_D}\s*(?:까지)?",
         lambda m: (_d(m[1], m[2], m[3]), _d(m[4] or m[1], m[5] or m[2], m[6]))),
        (rf"{_Y}\s*{_M}{_UNTIL}(?:(\d{{4}})\s*년\s*)?{_M}\s*(?:까지)?",
         lambda m: (_month_range(m[1], m[2])[0], _month_range(m[3] or m[1], m[4])[1])),
        (rf"{_Y}\s*{_M}\s*{_D}", lambda m: (_d(m[1], m[2], m[3]),) * 2),
        (rf"{_Y}\s*{_M}\s*(?:과|와|및|,)\s*{_M}", "months_pair"),
        (rf"{_Y}\s*{_M}", lambda m: _month_range(m[1], m[2])),
        (rf"{_Y}\s*(상반기|하반기)",
         lambda m: (_d(m[1], 1, 1), _d(m[1], 6, 30)) if m[2] == "상반기"
         else (_d(m[1], 7, 1), _d(m[1], 12, 31))),
        (r"(?<!\d)(\d{8})(?!\d)", lambda m: (_d(m[1][:4], m[1][4:6], m[1][6:]),) * 2),
        (rf"{_Y}(?!\s*\d)", lambda m: (_d(m[1], 1, 1), _d(m[1], 12, 31))),
    )


_YEARLESS = r"(?<![\d년])\s?(\d{1,2})\s*월(?:\s*(\d{1,2})\s*일)?(?!\s*(별|마다|단위))"

#: 지원 문법으로 읽지 못해도 날짜를 말하고 있을 수 있는 단서. 단서가 남아 있으면 LLM
#: 값을 지우지 않는다. "월별", "주 단위"는 구간 표현이지 기간이 아니므로 넣지 않는다.
_DATE_CUES = (r"\d+\s*(년|월|일)|(?<!\d)\d{1,2}\s*[/.]\s*\d{1,2}(?!\d)|지난|저번|작년|올해|금년|이번|최근|어제|오늘|그제|주말|평일|주중"
              r"|휴일|연휴|분기|반기|추석|설날|명절|\d{8}"
              # 달력 안의 위치를 말하는 말. 읽은 표현 옆에 남으면("지난주 금요일", "지난달 말")
              # 읽은 부분만으로 기간을 정하면 뜻이 바뀐다.
              r"|[월화수목금토일]요일|초순|중순|하순|월초|월말|연초|연말|말일|첫\s*주|마지막\s*주"
              r"|(?:^|\s)(?:초|말)(?=\s|$|에|부터|까지|의)")


#: 사용자 scope 문자열("scope:district:2726000000"). 안의 숫자는 날짜가 아니다.
_SCOPE_LITERAL = re.compile(r"scope:[A-Za-z0-9_:.-]+")


def _mask_scopes(question):
    """scope 문자열을 같은 길이의 공백으로 가린다. 위치(start)는 그대로 둔다."""
    return _SCOPE_LITERAL.sub(lambda match: " " * len(match.group(0)), question)


def scan_dates(question, *, reference_date):
    """질문에서 날짜 표현을 찾는다. 결과: (mentions, 남은 단서 여부)."""
    question = _mask_scopes(question)
    taken = [False] * len(question)
    mentions = []

    def claim(match):
        if any(taken[match.start():match.end()]):
            return False
        for index in range(match.start(), match.end()):
            taken[index] = True
        return True

    for pattern in _UNSUPPORTED_DATE:
        for match in re.finditer(pattern, question):
            if claim(match):
                mentions.append(Mention("date", match.group(0), UNSUPPORTED,
                                        meaning="지원하지 않는 상대 기간", start=match.start()))
    for pattern, handler in _explicit_patterns():
        for match in re.finditer(pattern, question):
            if any(taken[match.start():match.end()]):
                continue
            if handler == "months_pair":
                year, first, second = match[1], int(match[2]), int(match[3])
                claim(match)
                if second == first + 1:
                    start, end = _month_range(year, first)[0], _month_range(year, second)[1]
                    mentions.append(Mention("date", match.group(0), SUPPORTED,
                                            _range(start, end), "연속한 두 달", match.start()))
                else:
                    mentions.append(Mention("date", match.group(0), UNSUPPORTED,
                                            meaning="연속하지 않은 여러 기간", start=match.start()))
                continue
            try:
                start, end = handler(match)
            except ValueError:
                claim(match)
                mentions.append(Mention("date", match.group(0), UNSUPPORTED,
                                        meaning="존재하지 않는 날짜", start=match.start()))
                continue
            claim(match)
            status = SUPPORTED if start <= end else UNSUPPORTED
            mentions.append(Mention("date", match.group(0), status,
                                    _range(start, end) if status == SUPPORTED else None,
                                    "명시 날짜", match.start()))
    for pattern, token, meaning in _RELATIVE_DATE:
        for match in re.finditer(pattern, question):
            if not claim(match):
                continue
            if token in ("yesterday", "today"):
                day = reference_date - timedelta(days=1 if token == "yesterday" else 0)
                value = _text(day)
            else:
                value = token
            mentions.append(Mention("date", match.group(0), SUPPORTED, value,
                                    f"{token}: {meaning}", match.start()))
    for match in re.finditer(_YEARLESS, question):
        if any(taken[match.start(1):match.end()]):
            continue
        claim(match)
        mentions.append(Mention("date", match.group(0).strip(), AMBIGUOUS,
                                meaning="연도가 없는 날짜", start=match.start()))
    residue = "".join(ch if not used else " " for ch, used in zip(question, taken))
    cues_left = bool(re.search(_DATE_CUES, residue))
    return sorted(mentions, key=lambda item: item.start), cues_left


#: 유형과 "택시" 사이에 운행 상태 단어가 올 수 있다("법인 실차 택시", "개인 대기영업 택시").
_STATUS_BETWEEN = r"(?:(?:실차|공차|빈\s*차|대기\s*영업)\s*)?"
_TAXI = (
    (r"개인(용)?\s*" + _STATUS_BETWEEN + r"택시", "private"),
    (r"(법인|회사)(용)?\s*" + _STATUS_BETWEEN + r"택시", "corporate"),
    (r"(전체|모든)\s*택시|택시\s*전체", "all"),
)
_NEGATION = r"제외|빼고|말고|아닌|이외|외에"
#: 지원 어휘로 읽지 못해도 택시 유형을 말하고 있을 수 있는 단서. 남아 있으면 LLM 값을
#: 지우지 않는다(q18 "개인용 택시" 관측에서 어휘가 좁아 맞는 값을 지운 적이 있다).
_TAXI_CUES = r"개인|법인|회사|영업용|자가용|사업용|전체|모든"


def scan_taxi_types(question):
    mentions = []
    for pattern, value in _TAXI:
        for match in re.finditer(pattern, question):
            mentions.append(Mention("taxi_type", match.group(0), SUPPORTED, value,
                                    start=match.start()))
    return sorted(mentions, key=lambda item: item.start)


# -- 판정 ------------------------------------------------------------------


def _error(code, message, *, clarify=None, context=None, raw_text=""):
    return PlannerError(
        message, user_message=message, code=code,
        context={"raw_text": raw_text, "condition_error": True,
                 **({"needs_clarification": True, "clarify": clarify} if clarify else {}),
                 **(context or {})},
    )


def _interpreted_range(value, reference_date):
    """기록용 해석 범위. 상대 토큰은 기준일로 푼 값이며 TIMS의 해석이라는 보장은 없다."""
    if value in RELATIVE_TOKENS:
        start, end = resolve_relative(value, reference_date)
        return _range(start, end)
    if value in CALENDAR_TOKENS:
        return None
    return value


# -- 조건 상태 -------------------------------------------------------------------
#
# 규칙이 질문에서 표현을 찾지 못했다는 것은 조건이 없다는 증거가 아니다. 그래서 상태를
# 나눈다. 지우는 것은 "LLM 값의 근거 표현이 질문에 없고, 그 조건을 말하는 단서도 없을
# 때"뿐이다. 단서는 있는데 읽지 못하면 LLM 값을 그대로 두되(보류) 검증된 값으로 적지 않는다.

#: 질문 표현을 지원 문법으로 읽고 값이 정해졌다(LLM 값과 같거나 LLM 값이 없었다).
STATUS_INTERPRETED = "interpreted"
#: 질문 표현으로 정한 값과 LLM 값이 다르다. 질문 표현을 따른다(보정).
STATUS_CONFLICT = "conflict"
#: 표현은 찾았지만 뜻이 하나로 정해지지 않는다(연도 없음, 명시·상대 충돌). 확인 요청.
STATUS_AMBIGUOUS = "ambiguous"
#: 조건을 말하는 단서가 있지만 지원 문법으로 읽지 못했다. 판정하지 않는다(보류).
STATUS_UNVERIFIABLE = "unverifiable"
#: 조건 표현도 단서도 없다. LLM 값이 있었다면 근거가 없어 지운다.
STATUS_ABSENT = "absent"
#: 표현을 찾았지만 지원하지 않는 계산이다(최근 N일, 여러 기간, 유형 제외).
STATUS_UNSUPPORTED = "unsupported"

VERIFIED_STATUSES = frozenset({STATUS_INTERPRETED, STATUS_CONFLICT, STATUS_ABSENT})

_RELATIVE_ANCHORS = {
    "last_week": r"지난|저번|전주|주", "last_month": r"지난|저번|전월|달|월",
    "last_year": r"작년|지난|전년|해|년",
    "this_week": r"이번|금주|주", "this_month": r"이번|이달|금월|달|월",
    "this_year": r"올해|금년|이번|해|년",
    "weekday": r"평일|주중", "weekend": r"주말", "holiday": r"휴일",
}


def _date_value_anchors(value):
    """LLM이 적은 기간 값의 근거가 될 수 있는 질문 표현(연도·월 숫자, 상대어)."""
    if value in _RELATIVE_ANCHORS:
        return [_RELATIVE_ANCHORS[value]]
    anchors = []
    for part in re.findall(r"\d{8}", str(value)):
        month, day = int(part[4:6]), int(part[6:])
        anchors += [part, part[:4], rf"(?<!\d){month}\s*월",
                    # 숫자 표기("9/24", "9.24")처럼 월과 일이 숫자로 나란히 있는 경우
                    rf"(?<!\d)0?{month}\s*[/.\-]\s*0?{day}(?!\d)"]
    return anchors or [re.escape(str(value))]


def _has_anchor(question, anchors):
    return any(re.search(anchor, question) for anchor in anchors)


def reconcile_date(factors, question, reference_date, raw_text=""):
    llm_value = factors.get("date")
    mentions, cues_left = scan_dates(question, reference_date=reference_date)
    record = {"mentions": [m.to_dict() for m in mentions], "llm_value": llm_value,
              "unparsed_cues": cues_left}
    unsupported = [m for m in mentions if m.status == UNSUPPORTED]
    ambiguous = [m for m in mentions if m.status == AMBIGUOUS]
    supported = [m for m in mentions if m.status == SUPPORTED]
    if unsupported:
        record.update(status=STATUS_UNSUPPORTED, action="unsupported",
                      basis="unsupported_expression")
        raise _error("DATE_EXPRESSION_UNSUPPORTED",
                     f"지원하지 않는 기간 표현입니다: {', '.join(m.text for m in unsupported)}",
                     context={"date": record}, raw_text=raw_text)
    if ambiguous:
        record.update(status=STATUS_AMBIGUOUS, action="clarify", basis="yearless_date")
        raise _error("DATE_AMBIGUOUS",
                     f"기간을 확정할 수 없습니다(연도 없음): {', '.join(m.text for m in ambiguous)}",
                     clarify="date", context={"date": record}, raw_text=raw_text)
    values = {m.value for m in supported}
    if len(values) > 1:
        kinds = {"relative" if (m.value in RELATIVE_TOKENS | CALENDAR_TOKENS
                                or "yesterday" in m.meaning or "today" in m.meaning)
                 else "explicit" for m in supported}
        if kinds == {"relative", "explicit"}:
            record.update(status=STATUS_AMBIGUOUS, action="clarify",
                          basis="relative_and_explicit")
            raise _error("DATE_CONFLICT",
                         "질문의 명시 날짜와 상대 기간 표현이 함께 있어 기간을 정할 수 없습니다: "
                         + ", ".join(m.text for m in supported),
                         clarify="date", context={"date": record}, raw_text=raw_text)
        record.update(status=STATUS_UNSUPPORTED, action="unsupported",
                      basis="multiple_periods")
        raise _error("DATE_MULTIPLE_UNSUPPORTED",
                     "여러 기간을 비교하는 질문은 지원하지 않습니다: "
                     + ", ".join(m.text for m in supported),
                     context={"date": record}, raw_text=raw_text)
    if values and cues_left:
        # 읽은 표현 밖에도 날짜 단서가 남았다("지난달 15일"). 읽은 부분만으로 기간을 정하면
        # 뜻을 바꿀 수 있으므로 판정하지 않는다.
        (partial,) = values
        record.update(status=STATUS_UNVERIFIABLE, value=llm_value, action="held",
                      basis="unparsed_date_cue_beside_expression",
                      partial_interpretation=partial, interpreted_range=None)
    elif values:
        (value,) = values
        record.update(
            value=value,
            status=STATUS_INTERPRETED if llm_value in (None, value) else STATUS_CONFLICT,
            action="confirmed" if llm_value == value else ("corrected" if llm_value else "filled"),
            basis="question_expression" if llm_value in (None, value)
            else "question_expression_over_llm_value",
            interpreted_range=_interpreted_range(value, reference_date))
        factors["date"] = value
    elif llm_value and not cues_left and not _has_anchor(question, _date_value_anchors(llm_value)):
        record.update(value=None, status=STATUS_ABSENT, action="removed_no_evidence",
                      basis="llm_value_has_no_anchor_and_no_date_cue")
        factors.pop("date", None)
    elif llm_value:
        record.update(value=llm_value, status=STATUS_UNVERIFIABLE, action="held",
                      basis="unparsed_date_cue" if cues_left else "llm_value_anchor_unparsed",
                      interpreted_range=None)
    elif cues_left:
        # LLM도 값을 내지 않았고 규칙도 읽지 못했다. 기간이 빠졌을 수 있다.
        record.update(value=None, status=STATUS_UNVERIFIABLE, action="flagged",
                      basis="unparsed_date_cue_without_value")
    else:
        record.update(value=None, status=STATUS_ABSENT, action="none",
                      basis="no_value_no_cue")
    return record


_TAXI_ANCHORS = {"private": r"개인", "corporate": r"법인|회사"}

#: 운행 상태(taxi_status). 상태 단어 뒤에 (택시 유형 단어와) "택시" 또는 "통행량"이 올 때만 조건이다.
#: "공차율"은 측정값(vacant_ratio), "실차 구간", "실차 중", "실차의"는 trip 개체를 가리키므로
#: 조건으로 읽지 않는다(아래 단서로만 남는다).
_STATUS_WORDS = {"occupied": r"실차", "vacant": r"공차|빈\s*차", "stationary": r"대기\s*영업"}
_STATUS_TAIL = r"(?=\s*(?:(?:개인|법인|회사)(?:용)?\s*)?(?:택시|통행량|차량\s*통행))"
_STATUS = tuple((rf"(?:{word}){_STATUS_TAIL}", value) for value, word in _STATUS_WORDS.items())
_STATUS_CUES = r"실차|공차|빈\s*차|대기\s*영업"


def scan_taxi_status(question):
    mentions = []
    for pattern, value in _STATUS:
        for match in re.finditer(pattern, question):
            mentions.append(Mention("taxi_status", match.group(0), SUPPORTED, value,
                                    start=match.start()))
    return sorted(mentions, key=lambda item: item.start)


def reconcile_taxi_status(factors, question, raw_text="", concepts=None):
    """운행 상태를 질문 표현으로 정한다. 규칙은 택시 유형과 같다(근거 없는 값만 지우고, 단서가
    남으면 보류). 상태 조건을 받는 Tool은 통행량(get_passage_count)뿐이므로, 다른 측정값에 붙으면
    합성 단계가 반영할 수 없는 조건으로 멈춘다(조용히 버리지 않는다).

    근거 어휘가 없다고 지우는 것은 그 조건을 받을 수 있는 Tool이 없는 측정값일 때뿐이다(Tool 계약,
    ``consumable``). 받을 수 있으면 어휘 밖 표현("손님을 태운")일 수 있으므로 보류한다.
    """
    llm_value = factors.get("taxi_status")
    mentions = scan_taxi_status(question)
    record = {"mentions": [m.to_dict() for m in mentions], "llm_value": llm_value}
    values = {m.value for m in mentions}
    if len(values) > 1:
        record.update(status=STATUS_UNSUPPORTED, action="unsupported", basis="multiple_statuses")
        raise _error("TAXI_STATUS_EXPRESSION_UNSUPPORTED",
                     "여러 운행 상태를 함께 묻는 질문은 지원하지 않습니다: "
                     + ", ".join(m.text for m in mentions),
                     context={"taxi_status": record}, raw_text=raw_text)
    if mentions and re.search(_NEGATION, question):
        record.update(status=STATUS_UNSUPPORTED, action="unsupported", basis="negation")
        raise _error("TAXI_STATUS_EXPRESSION_UNSUPPORTED",
                     "운행 상태를 제외하는 표현은 지원하지 않습니다.",
                     context={"taxi_status": record}, raw_text=raw_text)
    cue = bool(re.search(_STATUS_CUES, question))
    if values and llm_value is None and next(iter(values)) == fixed_by_measure(concepts, "taxi_status"):
        # 질문의 상태 표현이 측정값의 정의(예: 실차 구간)를 다시 말한 것이다. 별도 조건으로 채우지 않는다.
        record.update(value=None, status=STATUS_ABSENT, action="not_filled",
                      basis="value_fixed_by_measure_definition")
    elif values:
        (value,) = values
        record.update(value=value, status=STATUS_INTERPRETED if llm_value in (None, value)
                      else STATUS_CONFLICT,
                      action="confirmed" if llm_value == value else (
                          "corrected" if llm_value not in (None, "all") else "filled"),
                      basis="question_expression" if llm_value in (None, value)
                      else "question_expression_over_llm_value")
        factors["taxi_status"] = value
    elif llm_value not in (None, "all") and not cue and consumable(concepts, "taxi_status"):
        record.update(value=llm_value, status=STATUS_UNVERIFIABLE, action="held",
                      basis="unlisted_expression_possible_on_consuming_measure")
    elif llm_value not in (None, "all") and not cue:
        record.update(value=None, status=STATUS_ABSENT, action="removed_no_evidence",
                      basis="llm_value_has_no_status_cue")
        factors.pop("taxi_status", None)
    elif llm_value not in (None, "all"):
        record.update(value=llm_value, status=STATUS_UNVERIFIABLE, action="held",
                      basis="unparsed_status_cue")
    else:
        record.update(value=llm_value, status=STATUS_ABSENT, action="none",
                      basis="status_word_not_a_condition" if cue else "no_value_no_cue")
    return record


def reconcile_taxi_type(factors, question, raw_text="", concepts=None):
    llm_value = factors.get("taxi_type")
    mentions = scan_taxi_types(question)
    record = {"mentions": [m.to_dict() for m in mentions], "llm_value": llm_value}
    if mentions and re.search(_NEGATION, question):
        record.update(status=STATUS_UNSUPPORTED, action="unsupported", basis="negation")
        raise _error("TAXI_TYPE_EXPRESSION_UNSUPPORTED",
                     "택시 유형을 제외하는 표현은 지원하지 않습니다.",
                     context={"taxi_type": record}, raw_text=raw_text)
    values = {m.value for m in mentions}
    if len(values) > 1:
        record.update(status=STATUS_UNSUPPORTED, action="unsupported", basis="multiple_types")
        raise _error("TAXI_TYPE_EXPRESSION_UNSUPPORTED",
                     "여러 택시 유형을 함께 묻는 질문은 지원하지 않습니다: "
                     + ", ".join(m.text for m in mentions),
                     context={"taxi_type": record}, raw_text=raw_text)
    cue = bool(re.search(_TAXI_CUES, question))
    if values and llm_value is None and next(iter(values)) == fixed_by_measure(concepts, "taxi_type"):
        record.update(value=None, stated="fixed_by_measure", status=STATUS_ABSENT, action="not_filled",
                      basis="value_fixed_by_measure_definition")
    elif values:
        (value,) = values
        # "전체 택시"(all)와 LLM의 생략은 실행 의미가 같다(계약 taxi_type_all_unrestricted).
        # 값은 질문 표현대로 all로 두고, 사용자가 명시했다는 사실을 stated에 남긴다.
        same = llm_value == value or (value == "all" and llm_value is None)
        record.update(value=value, stated=f"explicit_{value}",
                      status=STATUS_INTERPRETED if same or llm_value is None else STATUS_CONFLICT,
                      action="confirmed" if llm_value == value else (
                          "confirmed_equivalent" if same else
                          "corrected" if llm_value else "filled"),
                      basis="question_expression" if same or llm_value is None
                      else "question_expression_over_llm_value")
        factors["taxi_type"] = value
    elif llm_value in _TAXI_ANCHORS and not cue and not re.search(
            _TAXI_ANCHORS[llm_value], question) and consumable(concepts, "taxi_type"):
        # 받을 수 있는 Tool이 있으면 어휘 밖 표현일 수 있다. 지우지 않고 보류한다.
        record.update(value=llm_value, stated="unverifiable", status=STATUS_UNVERIFIABLE,
                      action="held", basis="unlisted_expression_possible_on_consuming_measure")
    elif llm_value in _TAXI_ANCHORS and not cue and not re.search(
            _TAXI_ANCHORS[llm_value], question):
        record.update(value=None, stated="not_stated", status=STATUS_ABSENT,
                      action="removed_no_evidence",
                      basis="llm_value_has_no_anchor_and_no_type_cue")
        factors.pop("taxi_type", None)
    elif llm_value in _TAXI_ANCHORS:
        # 단서는 있지만 지원 어휘로 읽지 못했다. 판정하지 않고 LLM 값을 둔다(검증 안 됨).
        record.update(value=llm_value, stated="unverifiable", status=STATUS_UNVERIFIABLE,
                      action="held", basis="unparsed_type_cue")
    elif cue:
        # 유형을 말하는 듯한 단서가 있는데 값이 없다. 빠졌을 수 있으므로 없음으로 확정하지 않는다.
        record.update(value=llm_value, stated="unverifiable", status=STATUS_UNVERIFIABLE,
                      action="flagged", basis="unparsed_type_cue_without_value")
    else:
        record.update(value=llm_value, stated="not_stated", status=STATUS_ABSENT, action="none",
                      basis="no_value_no_cue" if llm_value is None
                      else "llm_all_equivalent_to_unstated")
    return record


def _measure(concepts):
    if not isinstance(concepts or [], list):
        return None      # concepts가 list가 아니다. 판정하지 않고 grounding 계약(MISSING_CONCEPTS)에 맡긴다
    return next((item for item in concepts or []
                 if isinstance(item, dict) and item.get("role") == "MEASURE"), None)


def consumable(concepts, factor):
    """grounding의 측정값을 만들 수 있는 operator 가운데 ``factor``를 인자로 받는 것이 있는가.

    Tool 계약(operator registry)만 본다. 측정값이 없거나 registry가 모르는 측정값이면 True로 둔다
    (판정할 근거가 없으면 지우지 않는다).
    """
    from geoflow import operator_mapping
    from geoflow.types import CoreConcept

    measure = _measure(concepts)
    if measure is None or not isinstance(measure.get("subtype"), str):
        # 문자열이 아닌 subtype은 어느 operator도 만들지 않는다(registry 조회에 넣지 않는다).
        return True
    try:
        candidates = operator_mapping.candidates_for(CoreConcept(measure.get("concept")),
                                                     measure.get("subtype"))
    except ValueError:
        return True
    return not candidates or any(factor in spec.params for spec in candidates)


def fixed_by_measure(concepts, factor):
    """grounding의 측정값을 만드는 operator들이 정의로 고정한 ``factor`` 값. 모두 같은 값일 때만 돌려준다.

    조건 계층의 채움 권한: 질문 표현으로 조건을 채우는 것은 그 값이 측정값을 실제로 제한할 때다. 측정값의 정의가
    이미 그 값이면(operator 계약 ``inherent_conditions``) 채워도 제한이 늘지 않고, Tool 계약에 없는 조건만 하나
    더 생겨 합성이 멈춘다. 이 경우 채우지 않고 근거를 기록한다. 모델이 적은 값은 지우지 않는다.
    """
    from geoflow import operator_mapping
    from geoflow.types import CoreConcept

    measure = _measure(concepts)
    if measure is None or not isinstance(measure.get("subtype"), str):
        # 문자열이 아닌 subtype은 어느 operator도 만들지 않는다(registry 조회에 넣지 않는다).
        return None
    try:
        candidates = operator_mapping.candidates_for(CoreConcept(measure.get("concept")),
                                                     measure.get("subtype"))
    except ValueError:
        return None
    values = {spec.inherent_conditions.get(factor) for spec in candidates}
    return next(iter(values)) if candidates and len(values) == 1 else None


def _compact(text):
    return re.sub(r"\s+", "", text or "")


def check_places(concepts, question, raw_text=""):
    """장소명이 질문에 근거가 있는지 본다. 이름 정규화(대구시→대구)는 허용한다.

    이름이 질문에 있다는 것은 문자열 근거일 뿐이다. 어느 지역을 뜻하는지(서구가 어느
    도시의 서구인지), 질문의 다른 장소가 빠지지 않았는지, 출발/도착 관계가 맞는지는 보지
    않는다(``semantics``·``completeness`` 참고).
    """
    compact = _compact(question)
    records = []
    if not isinstance(concepts or [], list):
        return records   # concepts가 list가 아니다. grounding 계약이 거부한다
    for item in concepts or []:
        if not isinstance(item, dict) or item.get("concept") != "LOCATION":
            continue
        if item.get("subtype") != "place" or item.get("source") != "user":
            continue
        value = item.get("value")
        name = value.get("name") if isinstance(value, dict) else value
        text = item.get("text") or ""
        if not isinstance(name, str) or not name.strip():
            continue
        record = {"id": item.get("id"), "text": text, "lookup_name": name,
                  "region": (value or {}).get("region", "") if isinstance(value, dict) else "",
                  "od_role": ((item.get("attributes") or {}).get("od_role")
                              if isinstance(item.get("attributes") or {}, dict) else None) or item.get("od_role"),
                  "semantics": "name_evidence_only"}
        if _compact(name) in compact:
            record["evidence"] = "exact"
        elif text and _compact(text) in compact and (
                _compact(name) in _compact(text) or _compact(text) in _compact(name)):
            record["evidence"] = "normalized"
        else:
            raise _error("PLACE_NOT_IN_QUESTION",
                         f"질문에서 장소 '{name}'의 근거를 찾지 못했습니다.",
                         clarify="place", context={"place": record}, raw_text=raw_text)
        records.append(record)
    return records


#: 조건 계층이 확인하지 않는 것. 검증 요약(``verification``)이 그대로 옮긴다.
NOT_CHECKED = (
    "place_completeness: 질문의 장소가 모두 출력되었는지(누락 탐지 없음)",
    "place_semantics: 장소명이 뜻하는 지역(동명 지역 구분)",
    "od_semantics: 출발/도착 관계(모델 grounding의 몫, 보존만 함)",
    "unsupported_grammar: 지원 문법 밖의 날짜·유형 표현(보류로 둠)",
)


#: 조건 계층이 값을 정할 수 있는 factor. 그 밖의 factor와 개념 구조는 바꾸지 않는다(끝에서 확인).
OWNED_FACTORS = ("date", "taxi_type", "taxi_status")


def reconcile_payload(payload, question, *, reference_date, raw_text="", structured=False):
    """명시된 조건(날짜·택시 유형·운행 상태)을 질문 원문의 근거로 보존하고 장소 이름의 근거를 확인한다.

    (새 payload, 감사 기록). 바꿀 수 있는 것은 ``OWNED_FACTORS``뿐이다. 개념 구조, 측정값, 장소 역할,
    그룹·순위·집계는 모델 grounding의 몫이므로 읽지도 바꾸지도 않는다(끝에서 확인한다).

    grounding_v3(2026-09-30) 정리: grounding_v1·v2에서 더했던 질문 재해석(측정값·사건·출발/도착 역할·
    그룹 적용 위치·순위·개수·집계 단계·답의 대상)을 없앴다. 닫힌 어휘로 "분명하다"고 판정해 모델의 맞는
    grounding을 덮어쓰는 일이 처음 보는 문장에서 생겼기 때문이다(evaluation/grounding_v3/analysis.md).
    남긴 규칙은 값이 닫힌 enum이고 질문에 그 값을 가리키는 말이 **있을 때만** 쓰는 조건 보존이다.
    ``structured``는 호환을 위해 받는다(집계를 다루지 않으므로 쓰지 않는다).
    """
    if reference_date is None:
        raise ValueError("조건 해석에는 기준일이 필요합니다.")
    if payload.get("factors") and not isinstance(payload.get("factors"), dict):
        # factors가 object가 아니다. 조건 계층이 읽을 형식이 아니므로 바꾸지 않고 그대로 넘겨 grounding
        # 계약(INVALID_FACTORS)이 거부하게 한다. 비우거나 채우면 잘못된 출력이 유효한 grounding이 된다.
        return copy.deepcopy(payload), {"reference_date": reference_date.isoformat(),
                                        "timezone": str(SERVICE_TIMEZONE),
                                        "skipped": "factors_not_object", "corrections": [], "held": []}
    fixed = copy.deepcopy(payload)
    factors = fixed.get("factors")
    if not isinstance(factors, dict):
        factors = {}
        fixed["factors"] = factors
    audit = {
        "reference_date": reference_date.isoformat(),
        "timezone": str(SERVICE_TIMEZONE),
        "date": reconcile_date(factors, question, reference_date, raw_text),
        "taxi_type": reconcile_taxi_type(factors, question, raw_text, fixed.get("concepts")),
        "taxi_status": reconcile_taxi_status(factors, question, raw_text, fixed.get("concepts")),
        "places": check_places(fixed.get("concepts"), question, raw_text),
        "place_completeness": "unchecked",
        "not_checked": list(NOT_CHECKED),
    }
    before = {key: value for key, value in (payload.get("factors") or {}).items()
              if key not in OWNED_FACTORS}
    after = {key: value for key, value in factors.items() if key not in OWNED_FACTORS}
    if before != after or fixed.get("concepts") != payload.get("concepts"):
        raise AssertionError("조건 보정이 소유한 factor 밖을 바꿨습니다.")
    audit["corrections"] = [
        {"condition": key, "from": audit[key]["llm_value"], "to": audit[key].get("value"),
         "action": audit[key]["action"], "basis": audit[key]["basis"],
         "evidence": [{"text": m.get("text")} for m in audit[key].get("mentions") or []
                      if isinstance(m, dict)]}
        for key in OWNED_FACTORS
        if audit[key]["action"] in ("corrected", "filled", "removed_no_evidence")
    ]
    audit["held"] = [
        {"condition": key, "value": audit[key].get("value"), "action": audit[key]["action"],
         "basis": audit[key]["basis"]}
        for key in OWNED_FACTORS
        if audit[key]["status"] == STATUS_UNVERIFIABLE
    ]
    return fixed, audit


def reference_now():
    """기본 기준일(Asia/Seoul 오늘)."""
    return seoul_date(datetime.now(SERVICE_TIMEZONE))


# -- 의미 graph → 실행 인자 추적 ---------------------------------------------


def trace(plan, execution_plan, audit):
    """조건마다 적용된 의미 단계와 실행 인자를 잇는다. 사라진 조건이 있으면 멈춘다.

    compiler의 verify_lowering이 인자 보존을 이미 보지만, 이 추적은 "질문의 근거 표현"
    에서 출발해 실제 호출까지 이어지는지를 본다(부록 F의 trace와 같은 목적). 기간은
    요청 인자가 해석과 같다는 것(보존)과, provider가 그 인자를 그 기간으로 읽는다는 것
    (``date_semantics``의 provider 상태)을 따로 적는다.
    """
    from geoflow.errors import CompilerError

    if audit is None:
        return None
    steps_by_transformation = {}
    for step in execution_plan.steps:
        for covered in step.covers:
            steps_by_transformation.setdefault(covered, []).append(step)
    date_semantics = getattr(execution_plan, "date_semantics", {}) or {}
    rows = []
    for key in ("date", "taxi_type"):
        record = audit.get(key) or {}
        value = record.get("value")
        if value is None or (key == "taxi_type" and value == "all"):
            continue
        applied = [t.id for t in plan.transformations if t.params.get(key) == value]
        calls = []
        for transformation_id in applied:
            lowered = date_semantics.get(transformation_id) or {}
            for step in steps_by_transformation.get(transformation_id, []):
                if step.is_local:
                    continue
                calls.append({"step": step.id, "argument": step.arguments.get(key),
                              "partition": step.group is not None,
                              "lowering": lowered.get("lowering") if key == "date" else None,
                              "allowed": (lowered.get("request") if key == "date" and lowered
                                          else [value])})
        lost = not applied or any(
            call["argument"] is None
            or (not call["partition"] and call["argument"] not in call["allowed"])
            for call in calls)
        if lost:
            raise CompilerError(
                f"질문의 {key} 조건({value})이 실행 인자까지 전달되지 않았습니다.",
                code="CONDITION_LOST", user_message="질문의 조건이 계산에 반영되지 않았습니다.",
                context={"condition": key, "value": value, "applied_to": applied,
                         "calls": calls},
            )
        row = {"condition": key,
               "text": [m["text"] for m in record.get("mentions") or []],
               "value": value, "status": record.get("status"), "action": record.get("action"),
               "interpreted_range": record.get("interpreted_range"),
               "applied_to": applied, "calls": calls}
        if key == "date":
            row["provider"] = sorted({
                (date_semantics.get(t) or {}).get("provider", "partition") for t in applied})
        rows.append(row)
    for place in audit.get("places") or []:
        applied = [t.id for t in plan.transformations
                   if any(ref.node_id == place["id"] for ref in t.inputs.values())]
        calls = [{"step": step.id, "argument": step.arguments.get("name")}
                 for transformation_id in applied
                 for step in steps_by_transformation.get(transformation_id, [])
                 if not step.is_local]
        rows.append({"condition": "place", "text": place.get("text"),
                     "value": place.get("lookup_name"), "od_role": place.get("od_role"),
                     "evidence": place.get("evidence"), "semantics": place.get("semantics"),
                     "history": place.get("history", []),
                     "applied_to": applied, "calls": calls})
    return rows


def verification(audit, execution_plan, contract=None):
    """조건별로 무엇을 확인했고 무엇을 확인하지 못했는지. 전체 완료로 적지 않는다.

    세 층을 나눈다: 질문 해석(interpretation), 요청 인자(request), provider가 그 인자를
    같은 뜻으로 읽는다는 계약(provider). provider 층은 실행 프로필의 계약(``contract``,
    기본 TIMS)으로 판정한다. 장소 누락은 탐지하지 않으므로 ``complete``는 언제나 거짓이다.
    """
    if audit is None:
        return None
    from geoflow import tims_contract

    contract = contract or tims_contract.DEFAULT_CONTRACT
    date_records = list((getattr(execution_plan, "date_semantics", {}) or {}).values())
    grouped_steps = [step for step in execution_plan.tool_steps if step.group is not None]
    grouped_dates = [step.arguments.get("date") for step in grouped_steps]
    date_audit = audit.get("date") or {}
    if date_records:
        providers = sorted({item["provider"] for item in date_records})
        requests = sorted({arg for item in date_records for arg in item["request"]})
    else:
        providers, requests = [], []
    if grouped_dates:
        # 구간별 호출은 인자 하나하나의 의미와, 그 전략의 가정(범위 계약, 하루 합성의
        # 기록 계약)이 모두 계약으로 확인되어야 확인이다.
        providers = sorted(set(providers) | {
            tims_contract.SEMANTICS_CONFIRMED
            if tims_contract.date_argument_semantics(step.arguments.get("date"), contract)[
                "status"] == tims_contract.SEMANTICS_CONFIRMED
            and all(key in contract.items and contract.satisfied(key)
                    for key in step.assumptions)
            else tims_contract.SEMANTICS_UNVERIFIED
            for step in grouped_steps})
        requests = sorted(set(requests) | set(grouped_dates))
    if date_audit.get("value") is None and not requests:
        providers = [tims_contract.SEMANTICS_NOT_REQUESTED]
    taxi = audit.get("taxi_type") or {}
    rows = {
        "date": {"interpretation": date_audit.get("status"), "action": date_audit.get("action"),
                 "basis": date_audit.get("basis"),
                 "interpreted_range": date_audit.get("interpreted_range"),
                 "request": requests, "provider": providers},
        "taxi_type": {"interpretation": taxi.get("status"), "action": taxi.get("action"),
                      "basis": taxi.get("basis"), "stated": taxi.get("stated"),
                      "request": sorted({step.arguments.get("taxi_type")
                                         for step in execution_plan.tool_steps
                                         if step.arguments.get("taxi_type")}),
                      # enum 값과 all≡생략(taxi_type_all_unrestricted)을 계약으로 본다.
                      "provider": [tims_contract.SEMANTICS_CONFIRMED
                                   if contract.satisfied("taxi_type_all_unrestricted")
                                   else tims_contract.SEMANTICS_UNVERIFIED]},
        "place": {"interpretation": "name_evidence_only",
                  "names": [p.get("lookup_name") for p in audit.get("places") or []],
                  "completeness": audit.get("place_completeness", "unchecked"),
                  "provider": ["unverified"]},
    }
    verified = [key for key in ("date", "taxi_type")
                if rows[key]["interpretation"] in VERIFIED_STATUSES
                and all(p in (tims_contract.SEMANTICS_CONFIRMED,
                              tims_contract.SEMANTICS_NOT_REQUESTED)
                        for p in rows[key]["provider"])]
    unverified = [key for key in ("date", "taxi_type") if key not in verified]
    return {"conditions": rows, "verified": verified, "contract": contract.provider,
            "unverified": unverified + ["place"],
            "not_checked": list(audit.get("not_checked") or NOT_CHECKED),
            "complete": False}


def describe_for_answer(audit, verification_summary=None, execution_plan=None):
    """답변에 붙일 적용 조건과 검증 범위. 확인한 것과 확인하지 못한 것을 함께 적는다."""
    if audit is None:
        return ""
    parts = []
    date_record = audit.get("date") or {}
    value = date_record.get("value")
    lowered = list((getattr(execution_plan, "date_semantics", {}) or {}).values())
    if value:
        texts = ", ".join(m["text"] for m in date_record.get("mentions") or [])
        text = f"기간 '{texts}' → {value}" if texts else f"기간 {value}"
        if date_record.get("interpreted_range") and date_record["interpreted_range"] != value:
            text += (f" = {date_record['interpreted_range']}(기준일 {audit['reference_date']}, "
                     f"{audit['timezone']})")
        for item in lowered:
            if item.get("lowering") == "daily_composition":
                text += f", 하루 단위 조회 {len(item['request'])}회를 합성"
            elif item.get("lowering") == "explicit_range":
                text += f", 명시 범위 {item['request'][0]}로 조회"
        if date_record.get("status") == STATUS_UNVERIFIABLE:
            text += " [질문 표현을 현재 문법으로 검증하지 못한 LLM 값]"
        if date_record.get("action") == "corrected":
            text += f" [LLM 값 {date_record.get('llm_value')}을 질문 표현으로 바로잡음]"
        parts.append(text)
    taxi = audit.get("taxi_type") or {}
    if taxi.get("value") in ("private", "corporate", "all"):
        texts = ", ".join(m["text"] for m in taxi.get("mentions") or [])
        text = f"택시 유형 '{texts}' → {taxi['value']}" if texts else f"택시 유형 {taxi['value']}"
        if taxi.get("action") in ("corrected", "filled"):
            text += " [질문 표현으로 보완]"
        if taxi.get("status") == STATUS_UNVERIFIABLE:
            text += " [질문 표현을 현재 문법으로 검증하지 못한 LLM 값]"
        parts.append(text)
    for place in audit.get("places") or []:
        text = f"장소 '{place.get('text') or place['lookup_name']}'(조회명 {place['lookup_name']}"
        if place.get("od_role"):
            text += f", {place['od_role']}"
        text += ")"
        if place.get("history"):
            text += " [조회 실패 후 이름 수정]"
        parts.append(text)
    removed = [c for c in audit.get("corrections") or [] if c["action"] == "removed_no_evidence"]
    for item in removed:
        parts.append(f"{item['condition']} {item['from']}은 질문에 근거가 없어 적용하지 않음")
    lines = ["- 적용 조건: " + " · ".join(parts)] if parts else []
    if verification_summary is not None:
        names = {"date": "기간", "taxi_type": "택시 유형"}
        verified = [names[key] for key in verification_summary["verified"]]
        pending = [names[key] for key in verification_summary["unverified"] if key in names]
        owner = verification_summary.get("contract", "tims")
        source = "TIMS 문서 계약" if owner == "tims" else f"{owner} provider 계약"
        scope = (f"질문 표현과 {source}으로 확인: " + ", ".join(verified)) if verified else ""
        rest = "장소는 이름 근거만 확인(지역 의미·누락은 미검증)"
        if pending:
            rest = "미검증: " + ", ".join(pending) + " · " + rest
        lines.append("- 검증 범위: " + " · ".join(item for item in (scope, rest) if item))
    return "\n".join(lines)
