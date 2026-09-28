# -*- coding: utf-8 -*-
"""측정값마다 어떤 집계가 의미를 갖는지의 단일 기준.

TIMS Tool은 ``aggregation``(기록을 하나로 모으는 방식)을 받지만, 그 집계가 모든 측정값에
같은 뜻으로 성립하지는 않는다. 속도의 합계나 비율의 합계는 뜻이 없고, 고유 대수(활성택시
대수)는 하루 값들을 더해도 기간 전체의 고유 대수가 되지 않는다. 이 모듈은 그 차이를
측정값 subtype마다 적는다.

두 가지를 정한다.

1. ``undefined``: 이 측정값에 적용하면 뜻이 정해지지 않는 집계. Tool 인자(aggregation)로도,
   구간별 값의 로컬 집계(REDUCE_GROUPS)로도 쓰지 않는다. composer가 합성 전에 거부한다.
2. ``day_composable``: 하루 단위 호출 값들을 이 집계로 합치면 기간 호출과 같은 값이 되는
   집계. 비어 있으면 하루 단위 분할(daily partition, 한 단계 기간의 일 단위 합성)을 쓰지
   않는다. 이 집합은 수학적 필요조건이다. 실제로 쓰려면 Tool 기록이 하루 하나에만 속한다는
   계약(``tims_contract`` ``day_records:<tool>``)도 필요하다.

근거는 vendor schema(``schemas/tims.yaml``), vendor system prompt(``prompts/system.yaml``),
vendor v2 README(이 저장소 README의 업체 절)의 문장이다. 문장이 없는 것은 정의하지 않는다
(``undefined``에 넣거나 ``day_composable``에서 뺀다).
"""

from dataclasses import dataclass

from geoflow.types import Subtype

#: 기록마다 값이 있는 양. 합계가 뜻을 갖는다(요금, 수익금).
EXTENSIVE_VALUE = "extensive_value"
#: 기록마다 값이 있지만 합계가 뜻이 없는 양(속도, RPM).
INTENSIVE_VALUE = "intensive_value"
#: 사건 수. Tool 결과가 곧 합이다(통행량, 실차 구간 건수).
EVENT_COUNT = "event_count"
#: 기록(drive)마다 계산된 비율(공차율).
RECORD_RATIO = "record_ratio"
#: 고유 대상 수(활성택시 대수). 겹치는 대상 때문에 더할 수 없다.
DISTINCT_COUNT = "distinct_count"
#: 집단 비율(가동률 = 활성택시 / 등록된 전체 택시).
POPULATION_RATIO = "population_ratio"
#: 택시별로 기간 안에서 센 뒤 택시 전체에 집계한 값(운행일수).
PER_TAXI_PERIOD_COUNT = "per_taxi_period_count"

_ALL = frozenset({"sum", "max", "min"})


@dataclass(frozen=True)
class MeasureSemantics:
    subtype: str
    kind: str
    #: 뜻이 정해지지 않는 집계(구간 안·한 단계 aggregation과 구간별 값의 집계 모두).
    undefined: frozenset
    #: 하루 값들을 이 집계로 합치면 기간 값과 같아지는 집계.
    day_composable: frozenset
    evidence: str


MEASURES = {
    item.subtype: item for item in (
        MeasureSemantics(
            Subtype.SPEED, INTENSIVE_VALUE, frozenset({"sum"}), frozenset({"max", "min"}),
            "schemas/tims.yaml get_passage_metrics: 'speed=속도'. 속도의 합은 뜻이 없다",
        ),
        MeasureSemantics(
            Subtype.RPM, INTENSIVE_VALUE, frozenset({"sum"}), frozenset({"max", "min"}),
            "schemas/tims.yaml get_passage_metrics: 'rpm=분당 회전 속도'",
        ),
        MeasureSemantics(
            Subtype.FARE, EXTENSIVE_VALUE, frozenset(), _ALL,
            "schemas/tims.yaml get_trip_metrics: 'fare=택시 요금'. trip 기록마다 요금이 있다",
        ),
        MeasureSemantics(
            Subtype.REVENUE, EXTENSIVE_VALUE, frozenset(), _ALL,
            "schemas/tims.yaml get_billing_metrics: 'revenue=1일 수익금'. 택시·일 기록의 금액",
        ),
        MeasureSemantics(
            Subtype.PASSAGE_COUNT, EVENT_COUNT, frozenset(), frozenset({"sum"}),
            "schemas/tims.yaml get_passage_count: 'passage 개수(택시 통행량)'",
        ),
        MeasureSemantics(
            Subtype.TRIP_COUNT, EVENT_COUNT, frozenset(), frozenset({"sum"}),
            "schemas/tims.yaml get_trip_count: '실차 구간(trip) 건수'",
        ),
        MeasureSemantics(
            Subtype.VACANT_RATIO, RECORD_RATIO, frozenset({"sum"}), frozenset({"max", "min"}),
            "prompts/system.yaml: 'drive ... 공차 비율율 제공'. drive마다의 비율이며 합은 뜻이 없다",
        ),
        MeasureSemantics(
            # 하루 단위 정의("1일 기준으로 영업 행위를 한 택시")만 있다. 여러 날에 걸친 기간에서
            # aggregation이 날마다의 대수를 모으는지, 기간 안 고유 택시를 세는지는 없다.
            # 날마다의 고유 대수를 더하면 택시·일이 되어 고유 대수가 아니다.
            Subtype.ACTIVE_TAXI_COUNT, DISTINCT_COUNT, frozenset({"sum"}), frozenset(),
            "prompts/system.yaml: '활성택시: 1일 기준으로 영업 행위를 한 택시'. 기간 집계는 정의 없음",
        ),
        MeasureSemantics(
            Subtype.ACTIVE_TAXI_RATIO, POPULATION_RATIO, frozenset({"sum"}), frozenset(),
            "prompts/system.yaml: '가동률(운행룰): {활성택시} / {등록된 전체 택시}'. 비율의 합은 "
            "뜻이 없고, 하루 비율들로 기간 비율을 만드는 방법은 정의 없음",
        ),
        MeasureSemantics(
            # 택시마다 기간 안의 운행일수를 센 뒤 aggregation으로 택시 전체를 모은다. 하루
            # 값(택시마다 0 또는 1)의 합은 기간 합과 같지만, 최대·최소는 같지 않다.
            Subtype.OPERATING_DAYS, PER_TAXI_PERIOD_COUNT, frozenset(), frozenset({"sum"}),
            "README(업체 v2): 'operating_days는 분석기간 동안 택시별 운행일수를 구한 뒤 대상 "
            "택시 전체에 집계하는 metric'",
        ),
    )
}

KIND_LABELS = {
    EXTENSIVE_VALUE: "기록마다 값이 있는 양",
    INTENSIVE_VALUE: "합계가 뜻이 없는 양",
    EVENT_COUNT: "사건 수",
    RECORD_RATIO: "기록마다의 비율",
    DISTINCT_COUNT: "고유 대수",
    POPULATION_RATIO: "집단 비율",
    PER_TAXI_PERIOD_COUNT: "택시별 기간 집계",
}


def semantics_for(subtype):
    """측정값의 집계 의미. 측정값이 아니면(장소명 등) None."""
    return MEASURES.get(subtype)


def undefined_reducers(subtype):
    item = MEASURES.get(subtype)
    return item.undefined if item is not None else frozenset()


def day_composable(subtype, reducer):
    """하루 값들을 ``reducer``로 합쳐 기간 값을 정확히 만들 수 있는가. 모르는 측정값은 아니다."""
    item = MEASURES.get(subtype)
    return item is not None and reducer in item.day_composable
