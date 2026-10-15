# -*- coding: utf-8 -*-
"""Partial Grounding planner(``grounding_target: partial``). ``GeoFlowPlanner``를 고치지 않고 하위 클래스로 completion을 넣는다.

원본: ``geoflow/partial-grounding`` 커밋 ``ab9d215``의 ``geoflow/planner.py``(``_validate_payload``·``_parse``의 completion)와
``geoflow/grounding.py``(``parse_grounding`` 첫머리의 completion). 원본은 두 곳에서 completion을 불렀다(멱등).
여기서는 조건 대조(``conditions.reconcile_payload``) 전에 한 번 부르고, 이후 parse는 채워진 payload를 받으므로 원본과 같다.
계획 요청과 재질의 응답은 모두 ``_ask`` → ``_validate_payload``를 지난다.
"""
from geoflow.planner import GeoFlowPlanner

from grounding.completion import complete_grounding_payload


class PartialPlanner(GeoFlowPlanner):
    """LLM 응답의 생략된 구조 필드(concept·role·source·id)를 채운 뒤 기존 검증을 그대로 거친다."""

    def _validate_payload(self, payload, text, question):
        completion = []
        payload = complete_grounding_payload(payload, completion)
        grounding = super()._validate_payload(payload, text, question)
        if completion:
            grounding.normalizations = [*completion, *grounding.normalizations]
        return grounding
