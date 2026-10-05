"""Lossless aggregation spec -> production flat factors (training-side serialization only).

thor 브랜치는 이 함수를 production ``geoflow/aggregation.py``에 ``to_flat``으로 추가했다(b314904). 실행 의미 코드
(``execution_spec.SEMANTIC_CODE``) 지문을 바꾸지 않으려고 같은 정의를 training 쪽에 둔다. planner 추론에는 쓰지 않는다.
"""
from geoflow.aggregation import UNSPECIFIED, from_flat


def to_flat(spec):
    """Losslessly project an aggregation spec to the production flat contract.

    This is serialization only; it never chooses an unspecified reducer.
    Used by offline annotation conversion and evaluation, not planner inference.
    """
    factors = {}
    if spec.inner not in (None, UNSPECIFIED):
        factors["aggregation"] = spec.inner
    if spec.bucket:
        factors["bucket"] = spec.bucket
        if spec.select:
            factors.update(rollup=spec.select, answer="bucket")
        elif spec.outer:
            factors["rollup"] = spec.outer
    after = from_flat(factors)
    if (after.bucket, after.inner, after.outer, after.select) != (spec.bucket, spec.inner, spec.outer, spec.select):
        raise ValueError("Aggregation spec cannot be represented losslessly as flat factors.")
    return factors
