# -*- coding: utf-8 -*-
"""기간 해석과 시간 구간 분할. 로컬 분해(lowering)에만 쓴다.

TIMS가 구간별 집계를 한 호출로 처리하지 못할 때, compiler는 기간을 명시 날짜
구간으로 나눠 구간마다 호출한다. 그러려면 기간을 날짜로 알아야 한다.

- ``YYYYMMDD``, ``YYYYMMDD-YYYYMMDD``는 그대로 읽는다.
- ``last_week``, ``last_month``, ``last_year``는 **기준일이 주어질 때만** 푼다.
  기준일 없이 풀면 서버의 해석과 다를 수 있는 날짜를 조용히 지어내게 된다.
  - last_week: 기준일이 속한 주(월요일 시작) 바로 앞 주
  - last_month: 기준일이 속한 달 바로 앞 달
  - last_year: 기준일이 속한 해 바로 앞 해
- ``this_week``, ``this_month``, ``this_year``도 기준일이 있을 때만 푼다. 아직 오지
  않은 날은 자료가 없으므로 기간의 시작일부터 기준일까지로 둔다.
  - this_week: 기준일이 속한 주의 월요일부터 기준일까지
  - this_month: 기준일이 속한 달의 1일부터 기준일까지
  - this_year: 기준일이 속한 해의 1월 1일부터 기준일까지

상대 기간을 날짜로 푸는 위 규칙(월요일 시작, 기준일까지 포함, 기준일은 Asia/Seoul
달력 날짜)은 **이 애플리케이션의 정책**이다. vendor schema·system prompt는 토큰 이름과
"현재 시점을 기준으로 하는 상대 날짜"라는 설명만 적고, 주 시작 요일·기준일 포함 여부·
시간대를 정하지 않는다(``tims_contract`` ``relative_date_reference``: UNKNOWN). 그래서
토큰을 그대로 TIMS에 넘기는 호출(legacy)에서는 TIMS가 정한 기간이 쓰이고, 이 규칙은
기간을 로컬에서 나눌 때와 조건 기록(interpreted_range)에만 쓰인다.
- ``weekday``, ``weekend``, ``holiday``는 연속 기간이 아니므로 나누지 않는다.
- 기간이 없으면 나눌 범위를 알 수 없으므로 거부한다.

구간 경계는 이 모듈의 설계 선택(애플리케이션 정책)이며 **GeoFlow가 기간을 나눠 다시
계산할 때만** 쓰인다. TIMS의 ``bucket=week`` 경계는 schema에 적혀 있지 않고, 업체 Tool에
구간 계산을 맡긴 호출에는 이 정책이 적용되지 않는다(제공자의 정의를 따른다). 그래서 여기서
나눈 구간은 답변과 trace에 그대로 드러낸다.

- week: 월요일에 시작하는 7일. 기간의 처음과 끝에서 잘린다.
- month: 달력의 달. 기간의 처음과 끝에서 잘린다.

질문이 주 시작 요일을 명시하면(``geoflow/calendar_terms.py``) 월요일 대신 그 요일을 쓴다.
last_week·this_week도 같은 요일로 푼다.
"""

from datetime import date, timedelta

from geoflow.errors import CompilerError

_FORMAT = "%Y%m%d"
RELATIVE_PERIODS = frozenset({
    "last_week", "last_month", "last_year", "this_week", "this_month", "this_year",
})
NON_CONTIGUOUS_PERIODS = frozenset({"weekday", "weekend", "holiday"})

#: 상대 기간 토큰의 로컬 해석 규칙(애플리케이션 정책, TIMS 계약 아님). 기록에 남는다.
RELATIVE_PERIOD_POLICY = {
    "last_week": "기준일이 속한 주(월요일 시작) 바로 앞 주의 월요일부터 일요일까지",
    "last_month": "기준일이 속한 달 바로 앞 달의 1일부터 말일까지",
    "last_year": "기준일이 속한 해 바로 앞 해의 1월 1일부터 12월 31일까지",
    "this_week": "기준일이 속한 주(월요일 시작)의 월요일부터 기준일까지",
    "this_month": "기준일이 속한 달의 1일부터 기준일까지",
    "this_year": "기준일이 속한 해의 1월 1일부터 기준일까지",
}
#: 위 규칙의 출처. TIMS 계약이 아니라는 표시다.
RELATIVE_PERIOD_POLICY_SOURCE = "application_policy"

#: 구간 경계 정의(애플리케이션 정책의 기본값). 답변과 기록에 남는다.
BOUNDARY_RULES = {
    "week": "월요일 시작 7일, 기간 경계에서 잘림",
    "month": "달력 월, 기간 경계에서 잘림",
}
DEFAULT_WEEK_START = "monday"
_WEEKDAY_INDEX = {name: index for index, name in enumerate(
    ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"))}
_WEEKDAY_KOREAN = dict(zip(_WEEKDAY_INDEX, "월화수목금토일"))


def boundary_rule(unit, week_start=DEFAULT_WEEK_START, *, partial="include"):
    """구간 경계를 사람이 읽는 문장으로. 기본값이면 ``BOUNDARY_RULES``와 같다."""
    if unit == "week":
        head = f"{_WEEKDAY_KOREAN[week_start]}요일 시작 7일"
    else:
        head = "달력 월"
    tail = ("기간 경계에서 잘린 구간 제외" if partial == "exclude"
            else "기간 경계에서 잘림")
    return f"{head}, {tail}"


def _week_offset(day, week_start):
    """``day``가 속한 주(``week_start`` 시작)의 첫날까지 며칠 앞인가."""
    return (day.weekday() - _WEEKDAY_INDEX[week_start]) % 7


def _text(day):
    return day.strftime(_FORMAT)


def _parse_day(text, period):
    try:
        return date(int(text[:4]), int(text[4:6]), int(text[6:8]))
    except ValueError as error:
        raise CompilerError(
            f"기간의 날짜가 올바르지 않습니다: {period!r}",
            code="INVALID_PERIOD",
            user_message="질문의 기간을 해석하지 못했습니다.",
            context={"period": period},
        ) from error


def resolve_period(period, *, reference_date=None, week_start=DEFAULT_WEEK_START):
    """기간을 ``(시작일, 종료일)``로 푼다. 둘 다 포함한다.

    ``week_start``는 last_week·this_week의 주 시작 요일이다(애플리케이션 정책 기본 월요일).
    """
    if period in (None, ""):
        raise CompilerError(
            "구간으로 나눌 기간이 없습니다.",
            code="UNRESOLVED_PERIOD",
            user_message=(
                "주·월 단위로 나눠 계산하려면 기간이 필요합니다. "
                "예: '지난달', '20260801-20260831'."
            ),
            context={"period": period},
        )
    if period in NON_CONTIGUOUS_PERIODS:
        raise CompilerError(
            f"연속 기간이 아니어서 구간으로 나눌 수 없습니다: {period}",
            code="UNSUPPORTED_PERIOD_FOR_GROUPING",
            user_message="평일·주말·휴일 조건은 주·월 구간으로 나눠 계산할 수 없습니다.",
            context={"period": period},
        )
    if period in RELATIVE_PERIODS:
        if reference_date is None:
            raise CompilerError(
                f"상대 기간 {period}를 풀 기준일이 없습니다.",
                code="UNRESOLVED_PERIOD",
                user_message="기준일을 알 수 없어 상대 기간을 날짜로 바꾸지 못했습니다.",
                context={"period": period},
            )
        return _relative(period, reference_date, week_start)
    head, _, tail = str(period).partition("-")
    start = _parse_day(head, period)
    end = _parse_day(tail, period) if tail else start
    if end < start:
        raise CompilerError(
            f"기간의 끝이 시작보다 앞입니다: {period}",
            code="INVALID_PERIOD",
            user_message="질문의 기간을 해석하지 못했습니다.",
            context={"period": period},
        )
    return start, end


def _relative(period, reference, week_start=DEFAULT_WEEK_START):
    week_begin = reference - timedelta(days=_week_offset(reference, week_start))
    if period == "last_week":
        start = week_begin - timedelta(days=7)
        return start, start + timedelta(days=6)
    if period == "last_month":
        end = reference.replace(day=1) - timedelta(days=1)
        return end.replace(day=1), end
    if period == "this_week":
        return week_begin, reference
    if period == "this_month":
        return reference.replace(day=1), reference
    if period == "this_year":
        return date(reference.year, 1, 1), reference
    start = date(reference.year - 1, 1, 1)
    return start, date(reference.year - 1, 12, 31)


def partition(start, end, unit, *, week_start=DEFAULT_WEEK_START):
    """``[start, end]``를 unit 구간으로 나눈다. 빈틈과 겹침이 없다."""
    if unit not in BOUNDARY_RULES:
        raise CompilerError(
            f"알 수 없는 구간 단위입니다: {unit!r}",
            code="UNSUPPORTED_BUCKET",
            context={"bucket": unit},
        )
    groups = []
    cursor = start
    while cursor <= end:
        if unit == "week":
            natural_start = cursor - timedelta(days=_week_offset(cursor, week_start))
            natural_end = natural_start + timedelta(days=6)
        else:
            natural_start = cursor.replace(day=1)
            following = (natural_start + timedelta(days=32)).replace(day=1)
            natural_end = following - timedelta(days=1)
        stop = min(natural_end, end)
        groups.append({
            "unit": unit,
            "start": _text(cursor),
            "end": _text(stop),
            "label": f"{_text(cursor)}-{_text(stop)}",
            # 기간 경계에서 잘린 구간인지. 부분 구간의 합계는 작게 나온다.
            "complete": cursor == natural_start and stop == natural_end,
        })
        cursor = stop + timedelta(days=1)
    return groups


def days_of(group):
    """구간 하나를 하루 단위로 편다. 일 단위 호출에 쓴다."""
    start, end = _parse_day(group["start"], group["label"]), _parse_day(
        group["end"], group["label"])
    days = []
    while start <= end:
        days.append({"start": _text(start), "end": _text(start)})
        start += timedelta(days=1)
    return days


def date_argument(group):
    """구간 하나를 TIMS pt_date 인자로 쓴다."""
    return f"{group['start']}-{group['end']}"


def describe_period(start, end):
    return f"{_text(start)}-{_text(end)}"
