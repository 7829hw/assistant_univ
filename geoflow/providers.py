# -*- coding: utf-8 -*-
"""provider별 실행 프로필: 어떤 계약으로 무엇을 실행할 수 있는가.

실행 가능한 연산과 lowering 전략은 **선택된 provider의 계약**이 정한다. condition_check는
질문 조건의 해석·검증 옵션일 뿐이고, 켜고 끄는 것으로 provider의 기능이 생기거나 사라지지
않는다(``geoflow/pipeline.py``).

프로필
- ``mock`` + ``legacy``(기본): TIMS 계약(``tims_contract.DEFAULT_CONTRACT``, 미확인 항목은
  미확인 그대로)으로 판정하되, 기존 동작을 재현하려고 미확인 항목 일부를 **가정**하고 실행한다
  (상대 토큰·범위를 그대로 넘김, 구간별 하루 분할). 가정한 항목은 ``legacy_assumptions``와
  실행 계획의 ``date_semantics``·step ``assumptions``에 남는다.
- ``mock`` + ``strict``: 같은 TIMS 계약에서 확인된 것만 실행한다(단일 날짜, 기간 없음).
- ``reference``: 합성 데이터 위의 reference provider(``reference_provider.py``)와 그 계약
  ``REFERENCE_CONTRACT``. 계약에 적힌 것만 실행한다. 이 계약은 TIMS 계약과 별개이며 TIMS
  경로에 쓰이지 않는다.
"""

from dataclasses import dataclass, field, replace

from geoflow import tims_contract
from geoflow.compiler import DATE_POLICY_GUARANTEED, DATE_POLICY_LEGACY

MOCK = "mock"
REFERENCE = "reference"
LEGACY = "legacy"
STRICT = "strict"
TIMS_EXECUTION_MODES = (LEGACY, STRICT)

_REF_SOURCE = "reference_provider.py"


def _confirmed(key, quote, value=None):
    item = tims_contract.ITEMS[key]
    return replace(item, status=tims_contract.CONFIRMED, source=_REF_SOURCE, quote=quote,
                   value=value, evidence=f"reference 계약: {quote}")


def _not_offered(key, reason):
    item = tims_contract.ITEMS[key]
    return replace(item, status=tims_contract.UNKNOWN, source=None, quote=None, value=None,
                   evidence=f"reference provider가 제공하지 않음: {reason}")


#: reference provider의 계약. 각 확인 항목은 ``reference_provider.py`` 머리의 문장을 인용한다
#: (``tims_contract.evidence_problems``가 대조한다). TIMS의 ITEMS는 바꾸지 않는다.
REFERENCE_ITEMS = {
    **{key: _not_offered(key, "bucket/rollup을 지원하지 않음")
       for key in ("inner_is_aggregation", "rollup_unweighted", "bucket_week_start",
                   "bucket_partial", "bucket_empty")},
    "aggregation_default": _confirmed(
        "aggregation_default", "[기본 집계] aggregation을 생략하면 avg다.", "avg"),
    "single_date": _confirmed(
        "single_date", "[단일 날짜] YYYYMMDD는 service_date가 그 날짜인 레코드를 뜻한다."),
    "range_inclusive": _confirmed(
        "range_inclusive", "[범위] YYYYMMDD-YYYYMMDD는 양 끝을 포함한다.", "inclusive"),
    "null_result": _confirmed(
        "null_result", "[빈 결과] 조건에 맞는 레코드가 없으면 null을 반환한다(0으로 채우지 않는다).",
        "null"),
    "inner_avg_unit": _confirmed(
        "inner_avg_unit",
        "[평균] avg의 분모는 조건에 맞는 결측 아닌 레코드 수이며 가중치는 없다.",
        "택시·일 레코드"),
    "relative_date_reference": _not_offered(
        "relative_date_reference", "상대 토큰을 받지 않음. 호출 전에 명시 범위로 풀어야 함"),
    "calendar_token_period": _not_offered("calendar_token_period", "요일 토큰을 받지 않음"),
    "taxi_type_all_unrestricted": _confirmed(
        "taxi_type_all_unrestricted", "[택시 유형] taxi_type=all은 유형 조건 없음과 같다.",
        "all ≡ 생략"),
    "day_records:get_operation_metrics": _confirmed(
        "day_records:get_operation_metrics",
        "[기록 단위] 각 레코드는 하나의 service_date에만 속하며 aggregation은 레코드에 바로 적용된다.",
        "택시·일"),
    **{key: _not_offered(key, "이 도구를 지원하지 않음")
       for key in tims_contract.ITEMS if key.startswith("day_records:")
       and key != "day_records:get_operation_metrics"},
}
REFERENCE_CONTRACT = tims_contract.TimsContract(dict(REFERENCE_ITEMS), provider=REFERENCE)

#: legacy 모드가 TIMS 계약에서 확인 없이 가정하는 항목. 실행 기록에 그대로 남긴다.
LEGACY_TIMS_ASSUMPTIONS = (
    "relative_date_reference", "range_inclusive", "calendar_token_period",
    "day_records:<tool>(구간별 하루 분할)",
)


@dataclass(frozen=True)
class ExecutionProfile:
    provider: str
    contract: tims_contract.TimsContract
    date_policy: str
    mode: str | None = None
    synthetic: bool = False
    legacy_assumptions: tuple = ()
    description: str = ""
    notes: tuple = field(default_factory=tuple)

    def to_dict(self):
        return {"provider": self.provider, "contract": self.contract.provider,
                "mode": self.mode, "date_policy": self.date_policy,
                "synthetic": self.synthetic,
                "legacy_assumptions": list(self.legacy_assumptions),
                "description": self.description}


def profile_for(provider=MOCK, tims_execution=LEGACY):
    """provider 이름과 TIMS 실행 모드로 프로필을 만든다. 알 수 없는 조합은 거부한다."""
    if provider == MOCK:
        if tims_execution not in TIMS_EXECUTION_MODES:
            raise ValueError(f"알 수 없는 TIMS 실행 모드: {tims_execution!r}")
        if tims_execution == LEGACY:
            return ExecutionProfile(
                provider=MOCK, contract=tims_contract.DEFAULT_CONTRACT,
                date_policy=DATE_POLICY_LEGACY, mode=LEGACY,
                legacy_assumptions=LEGACY_TIMS_ASSUMPTIONS,
                description="mock(TIMS schema). 미확인 TIMS 항목을 가정하는 기존 동작(legacy)",
            )
        return ExecutionProfile(
            provider=MOCK, contract=tims_contract.DEFAULT_CONTRACT,
            date_policy=DATE_POLICY_GUARANTEED, mode=STRICT,
            description="mock(TIMS schema). 확인된 TIMS 계약만 실행(strict)",
        )
    if provider == REFERENCE:
        # reference는 자기 계약을 확인된 대로 실행한다. TIMS 가정 모드는 적용되지 않는다.
        return ExecutionProfile(
            provider=REFERENCE, contract=REFERENCE_CONTRACT,
            date_policy=DATE_POLICY_GUARANTEED, mode=None, synthetic=True,
            description="reference provider: 고정 합성 데이터를 계산(실제 교통·TIMS 데이터 아님)",
        )
    raise ValueError(f"알 수 없는 provider: {provider!r}")
