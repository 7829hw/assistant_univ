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
from geoflow.executor import STATUS_CANCELLED, STATUS_OK, execute_plan
from geoflow.labeling import resolve_scope_labels
from geoflow.operator_registry import Operator
from geoflow.planner import GeoFlowPlanner
from geoflow.templates import TemplateRegistry

AGENT_MODE = "geoflow"

#: 장소 조회 실패에 한해 허용하는 재계획 횟수. 무한 재시도를 막는다.
MAX_REPAIR_ATTEMPTS = 1

#: 재계획을 시도할 operator. 그 밖의 오류는 구조화된 실패로 그대로 반환한다.
REPAIRABLE_OPERATORS = frozenset({Operator.RESOLVE_PLACE_SCOPE})

#: 재계획 호출(planner.repair) 자체가 실패한 attempt.
STATUS_REPAIR_FAILED = "repair_failed"

#: 재계획을 시도하지 않고 끝난 attempt.
STATUS_REPAIR_SKIPPED = "repair_skipped"


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
    scope_labels: dict[str, str] = field(default_factory=dict)
    attempts: list[dict[str, Any]] = field(default_factory=list)
    repair_count: int = 0
    final_answer: str | None = None
    error: dict[str, Any] | None = None
    runtime_error: str | None = None
    cancelled: bool = False
    durations: dict[str, float] = field(default_factory=dict)

    def to_dict(self):
        return {
            "agent_mode": self.agent_mode,
            "stage": self.stage,
            "repair_count": self.repair_count,
            "scope_labels": dict(self.scope_labels),
            "attempts": [dict(item) for item in self.attempts],
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
        """질문 하나를 GeoFlow 경로로 실행한다.

        장소 조회가 retryable 오류로 실패하면 한 번에 한해 Planner에게 slot
        수정을 요청한다. 수정된 slot도 template → validator → compiler 전 경로를
        다시 통과하므로 어떤 guard도 우회하지 않는다.
        """
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

        run.stage = Stage.PLANNER
        try:
            planner_output = self.planner.plan(question)
        except GeoFlowError as error:
            return _fail(run, error, started_at)

        run.durations["planner_ms"] = planner_output.duration_ms
        run.durations["execution_ms"] = 0.0

        for attempt_index in range(MAX_REPAIR_ATTEMPTS + 1):
            try:
                template, plan, execution_plan = self._prepare(
                    question, planner_output, user_scopes, run, emit,
                )
            except GeoFlowError as error:
                if attempt_index == 0:
                    return _fail(run, error, started_at)
                # 재계획이 더 나쁜 계획을 만들었으면 직전 실행 실패를 유지한다.
                run.attempts.append({
                    "index": attempt_index,
                    "template": planner_output.template,
                    "slots": dict(planner_output.slots),
                    "status": error.stage,
                    "error": error.to_dict(),
                })
                break

            run.stage = Stage.EXECUTION
            execution_started_at = time.perf_counter()
            result = execute_plan(
                execution_plan,
                self.tool_executor,
                known_scopes=user_scopes,
                event_handler=event_handler,
                cancel_checker=cancel_checker,
            )
            run.durations["execution_ms"] += _elapsed(execution_started_at)
            run.execution = result.to_dict()
            # 실패한 시도의 Tool 호출도 trace에 남긴다.
            run.hop_log.extend(dict(entry) for entry in result.trace)
            run.attempts.append({
                "index": attempt_index,
                "template": plan.template,
                "slots": dict(plan.slots),
                "status": result.status,
                "tools": [entry["tool"] for entry in result.trace],
                "error": result.error,
            })

            if result.status == STATUS_OK:
                return self._finish(
                    run, plan, template, result, started_at,
                    event_handler=event_handler,
                )

            if result.status == STATUS_CANCELLED:
                run.cancelled = True
                run.durations["total_ms"] = _elapsed(started_at)
                return run

            failure = _repairable_failure(plan, execution_plan, result)
            if failure is None or attempt_index >= MAX_REPAIR_ATTEMPTS:
                # 재계획을 아예 시도하지 않은 이유를 기록에 남긴다. 나중에
                # 로그만 보고 "재계획이 실패했다"와 구분할 수 있어야 한다.
                run.attempts.append({
                    "index": attempt_index + 1,
                    "status": STATUS_REPAIR_SKIPPED,
                    "reason": (
                        "재계획 대상이 아닌 실패"
                        if failure is None else "재계획 시도 횟수 소진"
                    ),
                })
                break

            emit("geoflow_repair", attempt=attempt_index + 1, failure=failure)
            try:
                planner_output = self.planner.repair(
                    question, planner_output, failure,
                )
            except GeoFlowError as error:
                # 재계획 자체가 실패하면 원래의 실행 실패를 그대로 보고하되,
                # 재계획이 없었던 이유는 기록에 남긴다. 재계획 결과가 검증에서
                # 탈락한 경우(status=validation 등)와 구분하기 위한 것이다.
                run.attempts.append({
                    "index": attempt_index + 1,
                    "status": STATUS_REPAIR_FAILED,
                    "error": error.to_dict(),
                })
                break
            run.repair_count += 1
            run.durations["planner_ms"] += planner_output.duration_ms

        run.error = (run.execution or {}).get("error")
        run.runtime_error = (run.error or {}).get(
            "detail", "실행에 실패했습니다.",
        )
        run.durations["total_ms"] = _elapsed(started_at)
        return run

    def _prepare(self, question, planner_output, user_scopes, run, emit):
        """planner 출력을 검증된 실행 계획까지 끌고 간다."""
        run.planner = planner_output.to_dict()
        run.template = planner_output.template
        run.slots = dict(planner_output.slots)
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
        return template, plan, execution_plan

    def _finish(self, run, plan, template, result, started_at,
                *, event_handler=None):
        # 결과 scope를 장소명으로 바꾼다. 실패해도 답변 생성은 계속한다.
        labels, label_trace = resolve_scope_labels(
            result.final_value,
            self.tool_executor,
            event_handler=event_handler,
            start_index=len(run.hop_log) + 1,
        )
        if label_trace:
            run.hop_log.extend(label_trace)
            run.scope_labels = dict(labels)

        try:
            run.stage = Stage.ANSWER
            run.final_answer = format_answer(
                plan, result, answer=template.answer, labels=labels,
            )
        except GeoFlowError as error:
            return _fail(run, error, started_at)
        run.stage = Stage.DONE
        run.durations["total_ms"] = _elapsed(started_at)
        return run


def _repairable_failure(plan, execution_plan, result):
    """장소 조회의 retryable 실패만 재계획 대상으로 인정한다."""
    error = result.error or {}
    if not (error.get("context") or {}).get("retryable"):
        return None

    step_id = error.get("step_id")
    step = next(
        (item for item in execution_plan.steps if item.id == step_id), None,
    )
    if step is None or step.operator not in REPAIRABLE_OPERATORS:
        return None

    name = step.arguments.get("name")
    slot = next(
        (
            slot_name for slot_name, value in plan.slots.items()
            if isinstance(value, dict) and value.get("name") == name
        ),
        None,
    )
    return {
        "slot": slot or "(알 수 없음)",
        "name": name,
        "region": step.arguments.get("region", ""),
        "message": error.get("user_message") or error.get("detail", ""),
        "step_id": step.id,
    }


def _fail(run, error, started_at):
    run.error = error.to_dict()
    run.runtime_error = f"{error.stage} 단계 실패: {error.detail}"
    run.final_answer = None
    run.durations["total_ms"] = _elapsed(started_at)
    return run


def _elapsed(started_at):
    return round((time.perf_counter() - started_at) * 1000, 3)
