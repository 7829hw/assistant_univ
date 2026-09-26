# -*- coding: utf-8 -*-
"""구조화 집계 grounding 계약(S1)의 system prompt.

production 기본값은 flat 계약(H0)이다. 이 모듈은 설정으로 고를 수 있는 두 번째
계약을 만든다. 둘은 ``GeoFlowPlanner(aggregation_grounding=...)``와 CLI
``--aggregation-grounding``으로 명시적으로 나뉘며, 기본값은 바꾸지 않는다.

S1에서 LLM은 집계를 ``factors.aggregation_plan`` 하나에 적는다. 모양은 H2 실험의
aggregation_plan과 같고 두 가지가 다르다.

- 결과가 값이 아니라 구간(어느 주, 어느 달)인 질문을 ``result.select``로 적는다.
- 구간 안 집계가 질문에 없으면 ``unspecified``로 적고, 코드는 그것을 채우지 않고
  사용자 확인이 필요한 상태(AMBIGUOUS_INNER_AGGREGATION)로 돌려준다.

prompt는 정의(FACTOR_SPECS, operator registry)에서 만든다. 손으로 적은 목록이
어휘와 어긋나지 않게 하기 위해서다. 문장 예시는 평가 셋에 넣지 않은 개발용 문장이다.
"""

from geoflow.aggregation import BUCKET_UNITS, FLAT_KEYS, REDUCERS, SELECTIONS

FLAT = "flat"
STRUCTURED = "structured"
MODES = (FLAT, STRUCTURED)


def _options(values):
    return " | ".join(sorted(values))


PLAN_HEADING = "[집계 계획]"

PLAN_SECTION = f"""{PLAN_HEADING}
집계는 factors의 aggregation_plan 하나에 적는다. aggregation, bucket, rollup factor는
쓰지 않는다.

    "aggregation_plan": {{
      "bucket": {{"unit": "<{_options(BUCKET_UNITS)}>",
                 "reducer": "<{_options(REDUCERS)} | unspecified>"}},
      "result": {{"reducer": "<{_options(REDUCERS)}>"}}
    }}
    result는 {{"reducer": ...}}와 {{"select": "<{_options(SELECTIONS)}>"}} 중 하나다.

    원시 값 --bucket.reducer--> 구간별 값 --result.reducer--> 최종 값
    원시 값 --bucket.reducer--> 구간별 값 --result.select---> 값이 가장 큰/작은 구간
    원시 값 --result.reducer--> 최종 값                         (구간이 없을 때)

- result는 질문이 최종적으로 묻는 것이다.
  - 값을 물으면 result.reducer다.
    "월별 운행 시간 합계의 최솟값은?" → bucket={{unit: month, reducer: sum}},
    result={{reducer: min}}
  - 구간 자체를 물으면 result.select다. 답이 "어느 주", "어느 달"이다.
    "운행 시간 평균이 가장 낮았던 달은?" → bucket={{unit: month, reducer: avg}},
    result={{select: min}}
- bucket은 "주별", "주 단위로", "월마다"처럼 구간 표현이 있거나, 답이 구간일 때 넣는다.
  - bucket.reducer는 각 구간 안의 값을 먼저 모으는 방식이다. 질문에 적힌 말을
    그대로 옮긴다. "합계", "합산한", "총" → sum, "평균" → avg.
  - 질문이 구간 안의 집계를 말하지 않으면 unspecified로 적는다. 짐작해서 채우지
    않는다. "월별 운행 시간의 최솟값은?" → bucket={{unit: month, reducer: unspecified}},
    result={{reducer: min}}
- 구간이 없으면 result.reducer만 적는다.
  "평균 운행 시간은?" → {{"result": {{"reducer": "avg"}}}}
- 질문에 집계 표현이 없으면 aggregation_plan을 넣지 않는다.
- 값을 묻는지 구간을 묻는지 구분한다.
  "주별 합계의 최댓값은?" → 값 → result={{reducer: max}}
  "합계가 가장 큰 주는?"  → 구간 → result={{select: max}}
- 주, 월은 개념(concept)으로 만들지 않는다. 구간은 aggregation_plan에만 적는다.
- 구간 단위: "주", "주별", "주 단위", "매주" → week. "월", "월별", "달마다" → month.
- 구간은 aggregation_plan.bucket에만 적는다. dimension에 week나 month를 넣지 않는다.
  dimension은 지역·요일처럼 결과를 여러 줄로 나누는 기준이다.
- aggregation_plan은 factors 안에 둔다. 최상위 key로 두지 않는다.

예시
질문: "2026년 상반기 부산 법인택시의 운행 시간 합계가 가장 길었던 달은?"
"factors": {{
  "date": "20260101-20260630",
  "taxi_type": "corporate",
  "aggregation_plan": {{
    "bucket": {{"unit": "month", "reducer": "sum"}},
    "result": {{"select": "max"}}
  }}
}}"""

#: 기본 prompt 예시에 있는 flat 집계. 구조화 계약에서는 같은 뜻으로 옮긴다.
_EXAMPLE_REPLACEMENTS = (
    ('    "time": "120000-130000",\n    "aggregation": "avg",\n    "vicinity": true\n',
     '    "time": "120000-130000",\n    "aggregation_plan": {"result": {"reducer": "avg"}},\n'
     '    "vicinity": true\n'),
    ('    "time": "120000-130000",\n    "aggregation": "avg"\n  }',
     '    "time": "120000-130000",\n    "aggregation_plan": {"result": {"reducer": "avg"}}\n  }'),
)


def structured_base_prompt(base_prompt):
    """기본 prompt의 flat 집계 예시만 구조화 표기로 옮긴다. 각 조각은 한 번씩 일치해야 한다."""
    prompt = base_prompt
    for old, new in _EXAMPLE_REPLACEMENTS:
        count = prompt.count(old)
        if count != 1:
            raise ValueError(f"기본 prompt에서 {count}번 일치했다: {old[:40]!r}")
        prompt = prompt.replace(old, new)
    return prompt


def structured_factor_semantics(text):
    """조건 설명에서 flat 집계 factor를 가리키는 말을 구조화 표기로 바꾼다."""
    return text.replace("bucket과 함께 쓸 수 없다", "aggregation_plan의 bucket과 함께 쓸 수 없다")


EXCLUDED_FACTORS = frozenset(FLAT_KEYS)
