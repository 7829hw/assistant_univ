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
- ``weekday``, ``weekend``, ``holiday``는 연속 기간이 아니므로 나누지 않는다.
- 기간이 없으면 나눌 범위를 알 수 없으므로 거부한다.

구간 경계는 이 모듈의 설계 선택이다. TIMS의 ``bucket=week`` 경계는 schema에
적혀 있지 않다. 그래서 여기서 나눈 구간은 답변과 trace에 그대로 드러낸다.

- week: 월요일에 시작하는 7일. 기간의 처음과 끝에서 잘린다.
- month: 달력의 달. 기간의 처음과 끝에서 잘린다.
"""

from datetime import date, timedelta

from geoflow.errors import CompilerError

_FORMAT = "%Y%m%d"
RELATIVE_PERIODS = frozenset({"last_week", "last_month", "last_year"})
NON_CONTIGUOUS_PERIODS = frozenset({"weekday", "weekend", "holiday"})

#: 구간 경계 정의. 답변과 기록에 남는다.
BOUNDARY_RULES = {
    "week": "월요일 시작 7일, 기간 경계에서 잘림",
    "month": "달력 월, 기간 경계에서 잘림",
}


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


def resolve_period(period, *, reference_date=None):
    """기간을 ``(시작일, 종료일)``로 푼다. 둘 다 포함한다."""
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
        return _relative(period, reference_date)
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


def _relative(period, reference):
    if period == "last_week":
        this_monday = reference - timedelta(days=reference.weekday())
        start = this_monday - timedelta(days=7)
        return start, start + timedelta(days=6)
    if period == "last_month":
        end = reference.replace(day=1) - timedelta(days=1)
        return end.replace(day=1), end
    start = date(reference.year - 1, 1, 1)
    return start, date(reference.year - 1, 12, 31)


def partition(start, end, unit):
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
            natural_start = cursor - timedelta(days=cursor.weekday())
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
