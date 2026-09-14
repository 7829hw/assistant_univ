# -*- coding: utf-8 -*-
"""GeoFlow 실행 파이프라인.

    Question
        ↓ planner.plan()          (LLM 1회, Tool 없음)
    template + slots
        ↓ template.instantiate()  (deterministic)
    GeoFlowPlan
        ↓ validator.validate()
    ExecutionPlan
        ↓ compiler.compile_plan()
        ↓ executor.execute_plan() (기존 ToolExecutor 재사용)
    Final Answer
"""

import time
from dataclasses import dataclass, field
from typing import Any

from agent_graph import extract_scopes

from geoflow import validator as geoflow_validator
from geoflow.answer import format_answer
from geoflow.compiler import compile_plan
from geoflow.errors import GeoFlowError
from geoflow.executor import STATUS_OK, execute_plan
from geoflow.planner import GeoFlowPlanner
from geoflow.templates import TemplateRegistry

AGENT_MODE = "geoflow"


class Stage:
    """실패 지점을 로그에서 바로 알 수 있도록 단계 이름을 고정한다."""

    PLANNER = "planner"
    TEMPLATE = "template"
    VALIDATION = "validation"
    COMPILE = "compile"
    EXECUTION = "execution"
    ANSWER = "answer"
    DONE = "done"


@dataclass
class GeoFlowRun:
    """한 질문의 GeoFlow 실행 전체 기록."""

    question: str
    agent_mode: str = AGENT_MODE
    stage: str = Stage.PLANNER
    planner: dict[str, Any] | None = None
    template: str | None = None
    slots: dict[str, Any] = field(default_factory=dict)
    plan: dict[str, Any] | None = None
    validation: dict[str, Any] | None = None
    execution_plan: dict[str, Any] | None = None
    execution: dict[str, Any] | None = None
    hop_log: list[dict[str, Any]] = field(default_factory=list)
    final_answer: str | None = None
    error: dict[str, Any] | None = None
    runtime_error: str | None = None
    cancelled: bool = False
    durations: dict[str, float] = field(default_factory=dict)

    def to_dict(self):
        return {
            "agent_mode": self.agent_mode,
            "stage": self.stage,
            "planner": self.planner,
            "template": self.template,
            "slots": dict(self.slots),
            "plan": self.plan,
            "validation": self.validation,
            "execution_plan": self.execution_plan,
            "execution": self.execution,
            "final_answer": self.final_answer,
            "error": self.error,
            "durations": dict(self.durations),
        }


class GeoFlowPipeline:
    """planner/validator/compiler/executor를 하나의 실행 경로로 묶는다."""

    def __init__(self, *, planner, templates, tool_executor):
        self.planner = planner
        self.templates = templates
        self.tool_executor = tool_executor

    @classmethod
    def create(cls, *, client, tool_executor, template_directory=None,
               planner_prompt=None, model=None):
        """CLI/Web이 동일하게 사용할 기본 구성으로 파이프라인을 만든다."""
        templates = (
            TemplateRegistry.from_directory()
            if template_directory is None
            else TemplateRegistry.from_directory(template_directory)
        )
        planner = GeoFlowPlanner(
            client=client,
            templates=templates,
            prompt=planner_prompt,
            model=model,
        )
        return cls(
            planner=planner,
            templates=templates,
            tool_executor=tool_executor,
        )

    def run(self, question, *, event_handler=None, cancel_checker=None):
        """질문 하나를 GeoFlow 경로로 실행한다."""
        run = GeoFlowRun(question=question)
        started_at = time.perf_counter()
        user_scopes = set(extract_scopes(question))

        def emit(event, **payload):
            if event_handler is not None:
                event_handler(event, payload)

        if cancel_checker is not None and cancel_checker():
            run.cancelled = True
            run.durations["total_ms"] = _elapsed(started_at)
            return run

        try:
            run.stage = Stage.PLANNER
            planner_output = self.planner.plan(question)
            run.planner = planner_output.to_dict()
            run.template = planner_output.template
            run.slots = dict(planner_output.slots)
            run.durations["planner_ms"] = planner_output.duration_ms
            emit(
                "geoflow_plan",
                template=planner_output.template,
                slots=planner_output.slots,
                duration_ms=planner_output.duration_ms,
            )

            run.stage = Stage.TEMPLATE
            template = self.templates.require(planner_output.template)
            plan = template.instantiate(question, planner_output.slots)
            run.plan = plan.to_dict()
            run.slots = dict(plan.slots)

            run.stage = Stage.VALIDATION
            report = geoflow_validator.validate(
                plan,
                available_tools=self.tool_executor.tool_names,
                user_scopes=user_scopes,
            )
            run.validation = report.to_dict()
            emit("geoflow_validation", report=run.validation)
            report.raise_if_failed()

            run.stage = Stage.COMPILE
            execution_plan = compile_plan(plan)
            run.execution_plan = execution_plan.to_dict()
            emit("geoflow_execution_plan", execution_plan=run.execution_plan)
        except GeoFlowError as error:
            return _fail(run, error, started_at)

        run.stage = Stage.EXECUTION
        execution_started_at = time.perf_counter()
        result = execute_plan(
            execution_plan,
            self.tool_executor,
            known_scopes=user_scopes,
            event_handler=event_handler,
            cancel_checker=cancel_checker,
        )
        run.durations["execution_ms"] = _elapsed(execution_started_at)
        run.execution = result.to_dict()
        run.hop_log = [dict(entry) for entry in result.trace]

        if result.status != STATUS_OK:
            run.cancelled = result.status == "CANCELLED"
            run.error = result.error
            run.runtime_error = (
                None if run.cancelled
                else (result.error or {}).get("detail", "실행에 실패했습니다.")
            )
            run.durations["total_ms"] = _elapsed(started_at)
            return run

        try:
            run.stage = Stage.ANSWER
            run.final_answer = format_answer(
                plan, result, answer=template.answer,
            )
        except GeoFlowError as error:
            return _fail(run, error, started_at)

        run.stage = Stage.DONE
        run.durations["total_ms"] = _elapsed(started_at)
        return run


def _fail(run, error, started_at):
    run.error = error.to_dict()
    run.runtime_error = f"{error.stage} 단계 실패: {error.detail}"
    run.final_answer = None
    run.durations["total_ms"] = _elapsed(started_at)
    return run


def _elapsed(started_at):
    return round((time.perf_counter() - started_at) * 1000, 3)
