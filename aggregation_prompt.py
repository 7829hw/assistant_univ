# -*- coding: utf-8 -*-
"""H2 arm의 system prompt. production prompt에서 집계 계약 부분만 바꾼다. 평가 전용.

바꾸는 곳은 다섯 군데다. 각 조각은 production 문자열과 정확히 한 번 일치해야
하고, 그렇지 않으면 멈춘다. 나머지는 byte 단위로 같다.

1. [사용 가능한 factor]의 aggregation·bucket·rollup 줄
2. [조건이 뜻하는 것]의 aggregation·bucket·rollup 설명과, dimension 설명의 bucket
3. 두 단계 집계 설명 단락 → [집계 계획]
4. [짝을 이루는 factor]의 bucket·rollup 줄
5. 예시 2·3의 "aggregation": "avg"

잘못된 형태를 보여 주는 예시는 넣지 않는다. production에 있던 두 긍정 예시
문장을 같은 뜻으로 옮기기만 한다.
"""

PLAN_SECTION = '''[집계 계획]
집계 방식은 factors의 aggregation_plan 하나에 적는다.

    "aggregation_plan": {
      "bucket": {"unit": "<month | week>", "reducer": "<avg | max | med | min | sum | unspecified>"},
      "result": {"reducer": "<avg | max | med | min | sum>"}
    }

    원시 값 --bucket.reducer--> 구간별 값 --result.reducer--> 최종 값   (구간이 있을 때)
    원시 값 --result.reducer--> 최종 값                                  (구간이 없을 때)

- result.reducer는 질문이 최종적으로 구하는 값의 집계 방식이다. 구간이 있든
  없든 최종 집계는 늘 result.reducer에 적는다.
- bucket은 질문에 "주 단위로", "월 단위로" 같은 구간 표현이 있을 때 넣는다.
  - unit은 구간 단위다.
  - reducer는 각 구간 안의 값을 먼저 하나로 모으는 방식이다. 질문이 구간
    안의 집계를 따로 말하지 않으면 unspecified로 적는다.
  - bucket을 넣으면 result도 함께 넣는다.
- 질문에 집계 표현이 없으면 aggregation_plan을 넣지 않는다.
  - "월 단위로 나눈 영업시간의 합은?" → bucket.unit=month, bucket.reducer=unspecified, result.reducer=sum
  - "평균 영업시간은?" → result.reducer=avg (bucket은 넣지 않는다)
'''

REPLACEMENTS = (
    # 1. 사용 가능한 factor
    ("- aggregation: avg | max | med | min | sum\n- bucket: month | week\n- date:",
     "- aggregation_plan: 아래 [집계 계획]의 형식\n- date:"),
    ("- rollup: avg | max | med | min | sum\n- taxi_status: all",
     "- taxi_status: all"),
    # 2. 조건이 뜻하는 것
    ("- aggregation: avg | max | med | min | sum 중 하나\n"
     "    원시 값을 하나로 모으는 1차 집계 방식. bucket이 있으면 각 구간 안에서 적용되고, "
     "없으면 전체에 적용된다. 질문에 집계 표현이 없으면 넣지 않는다.\n"
     "- bucket: month | week 중 하나\n"
     "    분석 기간을 나누는 시간 구간. 지정하면 구간마다 값을 먼저 구한 뒤 rollup으로 합친다. "
     "자료가 일 단위이므로 day는 없다.\n",
     "- aggregation_plan: 아래 [집계 계획]의 형식\n"
     "    질문의 집계 방식. 구간 단위는 month | week이며, 자료가 일 단위이므로 day는 없다.\n"),
    ("그룹별 분포를 얻는다. bucket과 함께 쓸 수 없다.",
     "그룹별 분포를 얻는다. aggregation_plan의 bucket과 함께 쓸 수 없다."),
    ("- rollup: avg | max | med | min | sum 중 하나\n"
     "    bucket별로 나온 값들을 하나로 합치는 2차 집계 방식. 집계 **방식**이지 시간 단위가 "
     "아니다. bucket과 짝으로만 쓴다.\n",
     ""),
    # 3. 두 단계 설명
    ("구간을 나누는 질문에서는 집계가 두 단계다.\n\n"
     "    원시 값 --aggregation--> 구간별 값 --rollup--> 최종 값\n\n"
     '- 질문에 "주 단위로", "월 단위로" 같은 구간 표현이 있으면, 함께 나온 집계어는\n'
     "  구간별 값들을 합치는 rollup이다.\n"
     '  - "월 단위로 나눈 영업시간의 합은?" → bucket=month, rollup=sum\n'
     "- 구간 표현이 없으면 집계어는 aggregation이다.\n"
     '  - "평균 영업시간은?" → aggregation=avg (bucket과 rollup은 넣지 않는다)\n'
     "- rollup에 week나 month 같은 시간 단위를 넣지 않는다. rollup은 합치는\n"
     "  방식이다.\n",
     PLAN_SECTION),
    # 4. 짝을 이루는 factor
    ("- bucket를 넣으면 rollup도 함께 넣습니다. 주·월 단위로 1차 집계하려면 그 결과를 "
     "합치는 방법도 필요합니다.\n", ""),
    # prompt의 마지막 줄이라 뒤에 줄바꿈이 없다. 앞 줄의 줄바꿈과 함께 뺀다.
    ("\n- rollup를 넣으면 bucket도 함께 넣습니다. 1차 집계 결과를 합치려면 어떤 단위로 "
     "나눌지도 필요합니다.", ""),
    # 5. 예시 2·3
    ('    "time": "120000-130000",\n    "aggregation": "avg",\n    "vicinity": true\n',
     '    "time": "120000-130000",\n    "aggregation_plan": {"result": {"reducer": "avg"}},\n'
     '    "vicinity": true\n'),
    ('    "time": "120000-130000",\n    "aggregation": "avg"\n  }',
     '    "time": "120000-130000",\n    "aggregation_plan": {"result": {"reducer": "avg"}}\n  }'),
)


def h2_prompt(production):
    """production prompt에서 집계 계약만 바꾼 H2 prompt."""
    prompt = production
    for old, new in REPLACEMENTS:
        count = prompt.count(old)
        if count != 1:
            raise ValueError(f"production prompt에서 {count}번 일치했다: {old[:40]!r}")
        prompt = prompt.replace(old, new)
    return prompt
