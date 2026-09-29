# -*- coding: utf-8 -*-
"""TIMS 집계 계약의 확인 상태와 lowering 전략별 요구 조건.

compiler가 의미 graph를 어떤 호출로 내릴 수 있는지는 이 표가 정한다. 코드가
계약을 가정하지 않도록, 전략마다 필요한 항목을 적고 그 항목이 ``CONFIRMED``일
때만 그 전략을 쓴다.

근거로 인정하는 것은 vendor schema(``schemas/*.yaml``)와 vendor system prompt의
parameter 정의(``prompts/system.yaml`` param_types)뿐이다. 저장소에는 실제 TIMS
provider가 없고(``tool_handlers``는 mock만 허용), mock 동작은 계약의 증거가 아니다.

상태

- ``CONFIRMED``: schema나 vendor parameter 정의에 문장으로 적혀 있다.
- ``OBSERVED``: 프로젝트의 라벨·예시·구현에서만 관찰된다. 계약이 아니다.
- ``UNKNOWN``: 어디에도 없다.

``verify_lowering``은 실행 계획이 의미 graph를 빠짐없이 옮겼는지(내부 일관성)만
확인한다. TIMS가 아래 항목대로 동작하는지는 확인할 수 없다. 그 외부 가정은 실행
단계마다 ``assumptions``로 남는다.

전략은 계산 책임에 따라 두 경로로 나뉜다(``PATH_*``, 2026-09-29).

- 업체 Tool에 위임(``FUSED_BUCKET_ROLLUP``): 인자가 질문의 집계 단계를 뜻한다는 항목만
  요구한다. 주 시작일·부분 구간·빈 구간·상대 날짜 기준은 ``delegates``이며 선행 조건이
  아니다. 질문이 정하지 않았다면 제공자 정의를 따르고, 정했다면 ``REQUIREMENT_ITEMS``의
  항목이 그 값으로 확인되어야 한다. 이전에는 이 네 항목의 확인과 로컬 정책과의 일치까지
  요구해서, 업체가 정상으로 제시한 호출(업체 100문항 43·98·100)이 막혔다.
- GeoFlow가 기간을 나눠 다시 계산(``RANGE_PARTITION``, ``DAILY_PARTITION``): 분해 전후가
  같은 계산이라는 근거를 모두 요구한다. 일 단위 분할은 ``day_records:<tool>``도 요구하며
  (``strategy_requires``) 어떤 실행 프로필에서도 가정하지 않는다.
"""

import re
from dataclasses import dataclass, field, replace

from geoflow import measures

CONFIRMED = "confirmed"
OBSERVED = "observed"
UNKNOWN = "unknown"
#: 테스트가 가정한 값. 기본 계약에는 없고, ``assuming()``으로 만든 계약에서만 쓰인다.
ASSUMED = "assumed"


@dataclass(frozen=True)
class ContractItem:
    key: str
    question: str
    status: str
    evidence: str
    #: 확인된 경우의 값. 의미 graph의 정의와 같은지 비교할 때 쓴다.
    value: str | None = None
    #: CONFIRMED의 출처 파일과, 그 파일에 글자 그대로 있는 문장. 테스트가 대조한다.
    #: status만 CONFIRMED로 바꾸고 근거를 달지 않으면 테스트가 실패한다.
    source: str | None = None
    quote: str | None = None


_SCHEMA = "schemas/tims.yaml get_billing_metrics"
_COMMON = "schemas/_common.yaml"
_PROMPT = "prompts/system.yaml param_types"

ITEMS = {
    item.key: item for item in (
        ContractItem(
            "inner_is_aggregation", "bucket이 있을 때 aggregation이 구간 안 집계인가",
            CONFIRMED,
            f"{_PROMPT} pt_bucket: 'pt_aggregation 형식의 파라미터가 1차 집계 방식을 "
            f"제공'; {_SCHEMA} bucket: '1차 집계 시간 구간'",
            source="prompts/system.yaml", quote="pt_aggregation 형식의 파라미터가 1차 집계 방식을 제공",
        ),
        ContractItem(
            "rollup_unweighted", "rollup은 구간별 값에 가중 없이 적용되는가",
            CONFIRMED,
            f"{_PROMPT} pt_rollup: 'bucket 단위로 값을 산출한 뒤, 그 값들에 이 집계를 "
            f"적용하여 단일 값 반환'",
            value="bucket 값마다 한 표",
            source="prompts/system.yaml",
            quote="bucket 단위로 값을 산출한 뒤, 그 값들에 이 집계를 적용하여 단일 값 반환",
        ),
        ContractItem(
            "aggregation_default", "aggregation을 생략하면 무엇인가",
            CONFIRMED, f"{_COMMON} pt_aggregation default: avg; {_PROMPT} 'avg: 평균 (기본값)'",
            value="avg", source="schemas/_common.yaml", quote="default: avg",
        ),
        ContractItem(
            "single_date", "YYYYMMDD 하나는 그 하루를 뜻하는가",
            CONFIRMED, f"{_COMMON} pt_date: '날짜 또는 날짜 범위. YYYYMMDD 또는 ...'; "
                       f"{_PROMPT} '날짜 형식은 YYYYMMDD'",
            source="schemas/_common.yaml", quote="YYYYMMDD 또는 YYYYMMDD-YYYYMMDD",
        ),
        ContractItem(
            "range_inclusive", "YYYYMMDD-YYYYMMDD의 양 끝이 포함되는가",
            OBSERVED,
            f"{_PROMPT} '시작날짜-종료날짜', 예시 20260601-20260605만 있다. 포함 여부는 "
            "문장으로 없다. 프로젝트 라벨(factor holdout 20260501-20260507)은 포함으로 "
            "적었지만 계약이 아니다",
        ),
        ContractItem(
            "bucket_week_start", "bucket=week의 주 시작 요일", UNKNOWN,
            f"{_SCHEMA}, {_PROMPT} 모두 '주 단위'라고만 적는다",
        ),
        ContractItem(
            "bucket_partial", "조회 기간 경계에서 잘린 구간의 처리", UNKNOWN,
            "schema와 parameter 정의에 없다",
        ),
        ContractItem(
            "bucket_empty", "자료가 없는 구간을 빼는지 0으로 넣는지", UNKNOWN,
            "schema와 parameter 정의에 없다",
        ),
        ContractItem(
            "null_result", "자료가 없을 때 반환값(null, 0, 오류)", UNKNOWN,
            f"{_SCHEMA} 반환은 '스칼라값'이라고만 적는다",
        ),
        ContractItem(
            "inner_avg_unit", "aggregation=avg의 분모가 되는 원시 단위", OBSERVED,
            f"{_SCHEMA} 설명의 '일 단위 택시 영업'과 metric 설명의 'revenue=1일 수익금'에서 "
            "택시·일 단위 기록으로 읽을 수 있으나 분모를 문장으로 정하지 않는다",
        ),
        ContractItem(
            "relative_date_reference", "last_week/last_month의 기준 시각과 시간대",
            UNKNOWN, f"{_PROMPT} '현재 시점을 기준으로 하는 상대 날짜'. 시간대와 경계는 없다. "
                     "this_week/this_month/this_year가 기준일까지인지 기간 끝까지인지도 없다",
        ),
        ContractItem(
            "calendar_token_period", "weekday/weekend/holiday 토큰이 어느 기간의 요일을 뜻하는가",
            UNKNOWN, f"{_COMMON} pt_date에 토큰 이름만 있다. 기간과 휴일 달력은 없다",
        ),
        ContractItem(
            "taxi_type_all_unrestricted", "taxi_type=all이 택시 유형 조건 없음과 같은가",
            CONFIRMED, f"{_COMMON} pt_taxi_type: 'all=조건 미적용', default: all",
            value="all ≡ 생략", source="schemas/_common.yaml", quote="all=조건 미적용",
        ),
        # 하루 단위 호출을 합쳐 기간 값을 만들려면(sum·max·min) aggregation이 하루 안에
        # 속하는 기록에 바로 적용되어야 한다. 기록이 여러 날에 걸치거나(자정을 넘는 trip),
        # 기간 전체에서 택시별 값을 먼저 만든 뒤 집계하면 하루 값들로 다시 만들 수 없다.
        ContractItem(
            "day_records:get_billing_metrics",
            "aggregation이 하루 안에 속하는 기록(택시·일)에 바로 적용되는가", OBSERVED,
            f"{_SCHEMA}: '일 단위 택시 영업(operation) 관련 통계값'으로 기록이 하루 단위임은 "
            "적혀 있다. 그러나 기간 집계가 그 기록에 바로 적용되는지는 없다. v2 README의 "
            "'operating_days는 분석기간 동안 택시별 운행일수를 구한 뒤 대상 택시 전체에 "
            "집계하는 metric'처럼 택시별 중간 집계가 있는 metric도 있다",
        ),
        ContractItem(
            "day_records:get_trip_metrics", "trip 기록이 하루 하나에만 속하는가", UNKNOWN,
            "schemas/tims.yaml get_trip_metrics에 날짜 귀속(자정을 넘는 trip) 규칙이 없다",
        ),
        ContractItem(
            "day_records:get_trip_count", "trip 기록이 하루 하나에만 속하는가", UNKNOWN,
            "schemas/tims.yaml get_trip_count에 날짜 귀속 규칙이 없다",
        ),
        ContractItem(
            "day_records:get_passage_count", "passage 기록이 하루 하나에만 속하는가", UNKNOWN,
            "schemas/tims.yaml get_passage_count에 날짜 귀속 규칙이 없다",
        ),
        ContractItem(
            "day_records:get_passage_metrics", "passage 기록이 하루 하나에만 속하는가", UNKNOWN,
            "schemas/tims.yaml get_passage_metrics에 날짜 귀속 규칙이 없다",
        ),
        ContractItem(
            "day_records:get_drive_metrics", "drive 기록이 하루 하나에만 속하는가", UNKNOWN,
            "schemas/tims.yaml get_drive_metrics에 날짜 귀속 규칙이 없다",
        ),
    )
}


#: 계산 책임이 누구에게 있는가. 두 경로는 검증 기준이 다르다.
#: - provider_delegated: 질문의 집계를 업체 Tool 인자로 온전히 옮겨 제공자가 계산한다.
#:   GeoFlow는 Tool 선택, 집계 단계 ↔ 인자 매핑, 인자 조합, 조건 보존, scope 출처,
#:   반환값 ↔ 답변을 검증한다. 질문이 정하지 않은 구간 정의(``delegates``)는 제공자의
#:   의미에 맡기고, 그 세부 계산을 검증했다고 주장하지 않는다.
#: - local_recomputation: GeoFlow가 기간을 나눠 여러 번 부르고 로컬에서 합친다. 분해 전후
#:   계산이 같다는 근거(날짜 경계, 빈틈·겹침, 부분 구간, 빈 결과, 측정값의 합성 가능성)가
#:   ``requires``에 모두 있어야 한다. 구간 정의는 애플리케이션 정책(``geoflow/periods.py``)이
#:   정하고 기록에 그렇게 남는다.
PATH_PROVIDER = "provider_delegated"
PATH_LOCAL = "local_recomputation"


@dataclass(frozen=True)
class Strategy:
    """lowering 전략 하나와 그 전략이 맞으려면 필요한 계약 항목."""

    name: str
    requires: tuple[str, ...]
    description: str
    path: str = PATH_LOCAL
    #: 질문이 정하지 않았을 때 이 전략이 제공자에게 맡기는 의미(계약 항목 key).
    #: 선행 조건이 아니다. 기록에 "provider_defined"로 남는다.
    delegates: tuple[str, ...] = ()


#: 구간 안 집계와 구간별 값의 집계를 bucket/aggregation/rollup 호출 하나로 옮긴다.
#: 필요한 것은 인자가 질문의 집계 단계를 뜻한다는 계약(aggregation = 구간 안 집계,
#: rollup = 구간별 값의 비가중 집계)뿐이다. 주 시작일·부분 구간·빈 구간·상대 날짜의
#: 기준은 질문이 정하지 않았다면 제공자의 정의를 따른다. 질문이 정했다면
#: ``REQUIREMENT_ITEMS``의 항목이 그 값으로 확인되어야 한다(``compiler``).
FUSED_BUCKET_ROLLUP = Strategy(
    "fused_bucket_rollup",
    ("inner_is_aggregation", "rollup_unweighted"),
    "TIMS bucket/aggregation/rollup 호출 하나(제공자 계산)",
    path=PATH_PROVIDER,
    delegates=("bucket_week_start", "bucket_partial", "bucket_empty",
               "relative_date_reference"),
)
#: 구간마다 날짜 범위로 한 번씩 호출한다. 범위 양 끝의 포함 여부가 필요하다.
RANGE_PARTITION = Strategy(
    "range_partition", ("range_inclusive",),
    "구간마다 날짜 범위 호출 후 로컬 계산",
)
#: 하루마다 한 번씩 호출하고 구간 값을 로컬에서 만든다. 구간 안 집계가 하루 값들로
#: 정확히 다시 만들어지는 경우(sum, max, min)에만 쓴다. 하루 값의 합성이 기간 값과
#: 같으려면 Tool 기록이 하루 하나에만 속해야 하므로 ``day_records:<tool>``도 요구한다
#: (``strategy_requires``). 이 항목은 어떤 실행 프로필에서도 가정하지 않는다.
DAILY_PARTITION = Strategy(
    "daily_partition", ("single_date",),
    "하루마다 호출 후 구간 값을 로컬에서 합침",
)

#: 사용자가 명시한 구간 정의(``geoflow/calendar_terms.py``) → 그것을 보장해야 하는 계약
#: 항목과, 그 항목의 확인된 값으로 표현한 같은 정의. 제공자 경로는 항목이 확인되고 값이
#: 같을 때만 사용자의 정의를 보장한다. Tool에는 이 정의를 바꾸는 인자가 없다.
REQUIREMENT_ITEMS = {
    "week_start": "bucket_week_start",
    "partial": "bucket_partial",
    "empty": "bucket_empty",
}
#: 계약 값 어휘 ↔ calendar_terms 어휘. 계약 값이 이 표에 없으면 같은 정의로 보지 않는다.
REQUIREMENT_VALUES = {
    "bucket_partial": {"clip_to_period": "include", "complete_only": "exclude"},
    "bucket_empty": {"zero_filled": "zero", "excluded": "skip"},
}


def requirement_guaranteed(contract, key, value):
    """제공자 계약이 사용자가 명시한 구간 정의 ``key=value``를 보장하는가. (보장, 이유)."""
    item_key = REQUIREMENT_ITEMS[key]
    item = contract.items.get(item_key)
    if item is None or not contract.satisfied(item_key):
        status = "없음" if item is None else item.status
        return False, f"계약 {item_key}가 확인되지 않았습니다({status})"
    provided = REQUIREMENT_VALUES.get(item_key, {}).get(item.value, item.value)
    if provided != value:
        return False, f"계약 {item_key}의 값({item.value})이 요구({value})와 다릅니다"
    return True, ""


def strategy_requires(strategy, tool_name):
    """전략이 그 Tool에서 요구하는 계약 항목. 일 단위 분할은 기록 계약도 요구한다."""
    if strategy is DAILY_PARTITION:
        return (*strategy.requires, day_records_key(tool_name))
    return strategy.requires

#: 하루 값들로 구간 값을 정확히 다시 만들 수 있는 구간 안 집계와 그 방법.
#: avg는 표본 수가, med는 원시 값이 없으면 다시 만들 수 없다.
DECOMPOSABLE_INNER = {"sum": "sum", "max": "max", "min": "min"}

#: 한 번의 계획이 부를 수 있는 일 단위 호출의 상한. 한 달(31일)의 두 배.
MAX_DAILY_CALLS = 62


@dataclass(frozen=True)
class TimsContract:
    """compiler가 참조하는 계약 상태. 테스트는 가정한 계약을 넣어 볼 수 있다.

    production pipeline은 계약을 바꿀 입구가 없다(``DEFAULT_CONTRACT`` 고정). 가정은
    ``assuming()``이 만든 계약에서만 인정되고, 그 계약은 ``allow_assumptions``가 참이다.
    """

    items: dict = field(default_factory=lambda: dict(ITEMS))
    allow_assumptions: bool = False
    #: 이 계약을 가진 provider. TIMS가 아닌 provider(reference)의 계약은 따로 만든다
    #: (``geoflow/providers.py``). 한 provider의 확인 항목을 다른 provider로 옮기지 않는다.
    provider: str = "tims"

    def status(self, key):
        return self.items[key].status

    def satisfied(self, key):
        status = self.status(key)
        return status == CONFIRMED or (status == ASSUMED and self.allow_assumptions)

    def missing(self, strategy, tool_name=None):
        """전략이 요구하는 항목 중 확인되지 않은 것. Tool을 주면 Tool별 항목도 본다."""
        requires = (strategy.requires if tool_name is None
                    else strategy_requires(strategy, tool_name))
        return tuple(key for key in requires
                     if key not in self.items or not self.satisfied(key))

    def allows(self, strategy, tool_name=None):
        return not self.missing(strategy, tool_name)

    def assuming(self, **values):
        """항목을 확인된 것으로 바꾼 계약. 테스트에서 가정을 명시할 때만 쓴다."""
        items = dict(self.items)
        for key, value in values.items():
            items[key] = replace(items[key], status=ASSUMED, value=value,
                                 evidence="테스트 가정(계약 근거 아님)")
        return TimsContract(items, allow_assumptions=True, provider=self.provider)

    def table(self):
        return [
            {"key": item.key, "question": item.question, "status": item.status,
             "evidence": item.evidence, "value": item.value}
            for item in self.items.values()
        ]


DEFAULT_CONTRACT = TimsContract()


# -- 날짜 인자의 실행 의미 -----------------------------------------------------


DATE_SINGLE = "single"
DATE_RANGE = "range"
DATE_RELATIVE = "relative"
DATE_CALENDAR = "calendar"
DATE_NONE = "none"

#: 요청 인자가 뜻하는 기간을 TIMS 계약으로 확인했는가.
SEMANTICS_CONFIRMED = "confirmed"
SEMANTICS_UNVERIFIED = "unverified"
#: 질문에 기간이 없어 인자도 없다. provider의 기본 기간은 문서에 없다.
SEMANTICS_NOT_REQUESTED = "not_requested"

_DATE_REQUIRES = {
    DATE_SINGLE: ("single_date",),
    DATE_RANGE: ("range_inclusive",),
    DATE_RELATIVE: ("relative_date_reference",),
    DATE_CALENDAR: ("calendar_token_period",),
}


def date_argument_kind(value):
    if value in (None, ""):
        return DATE_NONE
    text = str(value)
    if re.fullmatch(r"\d{8}", text):
        return DATE_SINGLE
    if re.fullmatch(r"\d{8}-\d{8}", text):
        return DATE_RANGE
    if text in ("last_week", "last_month", "last_year",
                "this_week", "this_month", "this_year"):
        return DATE_RELATIVE
    if text in ("weekday", "weekend", "holiday"):
        return DATE_CALENDAR
    return None


def date_argument_semantics(value, contract=DEFAULT_CONTRACT):
    """요청 인자 하나가 뜻하는 기간을 계약으로 확인할 수 있는가.

    요청 인자가 질문의 해석과 글자로 같다는 것(보존)과, provider가 그 인자를 그 기간으로
    읽는다는 것(실행 의미)은 다르다. 이 함수는 뒤의 것만 본다.
    """
    kind = date_argument_kind(value)
    if kind == DATE_NONE:
        return {"kind": kind, "status": SEMANTICS_NOT_REQUESTED, "requires": [],
                "missing": []}
    requires = _DATE_REQUIRES.get(kind, ())
    missing = [key for key in requires if not contract.satisfied(key)]
    if kind is None:
        missing = ["date_format"]
    if kind == DATE_RELATIVE and not missing:
        # 확인되었더라도 기준(시간대·달력)이 의미 graph의 정의와 같아야 한다.
        if contract.items["relative_date_reference"].value != "Asia/Seoul calendar":
            missing = ["relative_date_reference(value)"]
    return {"kind": kind, "status": SEMANTICS_UNVERIFIED if missing else SEMANTICS_CONFIRMED,
            "requires": list(requires), "missing": missing}


# -- 하루 단위 호출의 합성 -----------------------------------------------------

#: 하루 값들로 기간 값을 다시 만들 수 있는 집계. avg·med는 표본 수나 원시 값이 없어서
#: 안 된다. 측정값마다 더 좁아진다: 고유 대수(active_taxi_count)와 집단 비율
#: (active_taxi_ratio)은 어떤 집계로도 하루 값에서 기간 값을 만들 수 없고, 속도·공차율의
#: 합이나 운행일수의 최대·최소도 그렇다(``geoflow/measures.py``).
COMPOSABLE_REDUCERS = {"sum": "sum", "max": "max", "min": "min"}


def day_records_key(tool_name):
    return f"day_records:{tool_name}"


def daily_composition(tool_name, reducer, *, grouped_arguments=(), days=None,
                      contract=DEFAULT_CONTRACT, measure=None):
    """기간 값을 하루 단위 호출의 합성으로 정확히 만들 수 있는가. (가능 여부, 이유, 필요 항목).

    수학 조건: 집계가 sum·max·min이고, 측정값 ``measure``가 그 집계로 하루 값에서 기간 값을
    만들 수 있다(``geoflow/measures.py``). 데이터 조건: 그 Tool의 기록이 하루 하나에만 속하고
    aggregation이 그 기록에 바로 적용된다(``day_records:<tool>``). 목록을 돌려주는 호출
    (dimension·order·limit)은 항목별로 합친 뒤 다시 정렬·절단해야 하므로 다루지 않는다.
    ``measure``를 주지 않으면 측정값 조건을 보지 않는다(측정값을 모르는 호출자용).
    """
    requires = ["single_date", day_records_key(tool_name)]
    if reducer not in COMPOSABLE_REDUCERS:
        return False, f"집계 {reducer}는 하루 값들로 다시 만들 수 없습니다", requires
    if measure is not None and not measures.day_composable(measure, reducer):
        kind = measures.semantics_for(measure)
        label = measures.KIND_LABELS.get(kind.kind, kind.kind) if kind else "알 수 없는 측정값"
        return False, (f"측정값 {measure}({label})는 하루 값들을 {reducer}로 합쳐 기간 값을 "
                       "만들 수 없습니다"), requires
    if grouped_arguments:
        return False, ("목록 결과(" + ", ".join(grouped_arguments)
                       + ")는 하루 단위로 합치지 않습니다"), requires
    if days is not None and days > MAX_DAILY_CALLS:
        return False, f"하루 단위 호출 {days}번은 상한 {MAX_DAILY_CALLS}을 넘습니다", requires
    missing = [key for key in requires
               if key not in contract.items or not contract.satisfied(key)]
    if missing:
        return False, "확인되지 않은 계약: " + ", ".join(missing), requires
    return True, "", requires


# -- mock provider의 명시적 계약 ------------------------------------------------

#: 평가에 쓰는 mock의 동작. TIMS 계약이 아니며 compiler는 이것을 쓰지 않는다.
#: mock은 날짜를 해석하지 않고 ``mock_stub.yaml``에 적은 고정값(또는 인자가 일치하는
#: case의 결과)을 돌려준다. 따라서 mock 기준 정답은 "기대한 요청 인자와 같은 요청을
#: 보냈다"는 뜻일 뿐 날짜 의미의 보장이 아니며, 하루 단위로 나눈 호출의 합은 기간 호출의
#: mock 값과 비교할 수 없다.
MOCK_PROVIDER_CONTRACT = {
    "source": "mock_responses.py _fixed_metric",
    "quote": "YAML에 선언된 Tool metric 고정값을 반환한다.",
    "date_semantics": "opaque: 날짜 문자열을 해석하지 않음",
    "compositional": False,
}


def evidence_problems(contract=DEFAULT_CONTRACT, base_dir=None):
    """CONFIRMED 항목의 근거가 실제 파일에 있는지. 문제 목록(비어 있어야 한다).

    status만 CONFIRMED로 바꿔 최적화 경로를 여는 일을 막는 최소 장치다. 인용문이 파일에
    있다는 것은 근거의 존재이지, 그 문장이 전략의 의미 동등성을 보장한다는 뜻은 아니다.
    그 판단은 항목을 CONFIRMED로 올리는 사람이 한다.
    """
    from pathlib import Path

    base = Path(base_dir) if base_dir else Path(__file__).resolve().parent.parent
    problems = []
    for item in contract.items.values():
        if item.status == ASSUMED and not contract.allow_assumptions:
            problems.append(f"{item.key}: 가정 상태가 기본 계약에 섞였습니다")
        if item.status != CONFIRMED:
            continue
        if not item.source or not item.quote:
            problems.append(f"{item.key}: CONFIRMED인데 출처나 인용문이 없습니다")
            continue
        path = base / item.source
        if not path.is_file():
            problems.append(f"{item.key}: 출처 파일이 없습니다: {item.source}")
        elif item.quote not in path.read_text(encoding="utf-8"):
            problems.append(f"{item.key}: 인용문이 {item.source}에 없습니다")
    return problems
