# -*- coding: utf-8 -*-
"""결정 11의 문항별 provider 선택과 pipeline 구성(평가·재채점 공통).

- provider: 문항 gold의 장소가 reference로만 풀리면 ``reference``, 그 밖에는 ``mock``
  (``../provider/classify_providers.py``의 분류 규칙).
- pipeline·채점 코드는 provider와 무관하게 같다: ``GeoFlowPipeline.create``(flat, 조건 계층 켬,
  condition_notes 끔, 기준일 2026-09-25)와 ``evaluate_vendor100.run_item``·``grounding_check``.
  - mock: ``evaluate_vendor100._executor()``(mock handler) + ``profile_for(MOCK, LEGACY)``. HF-E·pipeline_pilot_001과 같다.
  - reference: ``ToolExecutor(handlers=get_tool_handlers("reference"), provider="reference")`` + ``profile_for(REFERENCE)``.
    ``evaluation/grounding_v4/reference_check.py``와 같은 구성이다.
"""
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE.parent / "provider"))

REFERENCE_DATE = date(2026, 9, 25)


def provider_for(gold_grounding):
    import classify_providers as C
    cls, _ = C.classify(gold_grounding)
    return ("reference" if cls == "reference_only" else "mock"), cls


def make_pipeline(client, provider):
    import evaluate_vendor100 as EV
    from geoflow import providers
    from geoflow.pipeline import GeoFlowPipeline
    EV.REFERENCE_DATE = REFERENCE_DATE
    if provider == "reference":
        from build import build
        from tool_executor import ToolExecutor
        from tool_handlers import get_tool_handlers
        tools, _ = build()
        executor = ToolExecutor(tools=tools, handlers=get_tool_handlers("reference"), provider="reference")
        profile = providers.profile_for(providers.REFERENCE)
    elif provider == "mock":
        executor = EV._executor()
        profile = providers.profile_for(providers.MOCK, providers.LEGACY)
    else:
        raise ValueError(provider)
    return GeoFlowPipeline.create(
        client=client, tool_executor=executor, aggregation_grounding="flat", clock=lambda: REFERENCE_DATE,
        condition_check=True, condition_notes=False, execution_profile=profile)
