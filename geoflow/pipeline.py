# -*- coding: utf-8 -*-
"""GeoFlow 실행 파이프라인.

    Question
        ↓ planner.plan()           (LLM 1회, Tool 없음)
    Grounding (concepts + factors)
        ↓ composer.compose()       (macro retrieval + IO-port composition,
                                    operator mapping 포함, deterministic)
    GeoFlowPlan
        ↓ validator.validate()     (G1~G6)
        ↓ compiler.compile_plan()
    ExecutionPlan
        ↓ executor.execute_plan()  (기존 ToolExecutor 재사용)
    Final Answer

질문 유형을 고르는 단계는 없다. Planner는 개념만 밝히고, 어떤 조각을 어떻게
이어 붙일지는 composer가, 어떤 Tool을 부를지는 operator mapping이 정한다.
"""

import time
from dataclasses import dataclass, field
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Any

from agent_graph import extract_scopes

from geoflow import conditions, structured_grounding
from geoflow import validator as geoflow_validator
from geoflow.answer import format_answer
from geoflow import providers
from geoflow.compiler import compile_plan
from geoflow.composer import MacroComposer
from geoflow.errors import GeoFlowError
from geoflow.executor import STATUS_CANCELLED, STATUS_OK, execute_plan
from geoflow.labeling import resolve_scope_labels
from geoflow.macros import MacroLibrary
from geoflow.operator_registry import Operator
from geoflow.planner import GeoFlowPlanner
from geoflow.repair import decide as decide_repair
from geoflow.types import CoreConcept, Subtype

AGENT_MODE = "geoflow"

#: 장소 조회 실패에 한해 허용하는 재계획 횟수. 무한 재시도를 막는다.
MAX_REPAIR_ATTEMPTS = 1

#: 재계획을 시도할 operator. 그 밖의 오류는 구조화된 실패로 그대로 반환한다.
REPAIRABLE_OPERATORS = frozenset({Operator.RESOLVE_PLACE_SCOPE})

#: 재계획 호출(planner.repair) 자체가 실패한 attempt.
STATUS_REPAIR_FAILED = "repair_failed"

#: 재계획을 시도하지 않고 끝난 attempt.
STATUS_REPAIR_SKIPPED = "repair_skipped"

#: 계획을 만들지 못해 끝난 attempt. 실행에 이르지 못했다는 뜻이다.
STATUS_PLANNING_FAILED = "planning_failed"


OUTCOME_ANSWERED = "answered"
OUTCOME_NEEDS_CLARIFICATION = "needs_clarification"
OUTCOME_UNSUPPORTED = "unsupported"
OUTCOME_FAILED = "failed"
OUTCOME_CANCELLED = "cancelled"

#: 질문을 이해했지만 현재 도구·계약으로 정확히 계산할 수 없어 멈춘 경우.
UNSUPPORTED_CODES = frozenset({
    "UNSUPPORTED_QUESTION", "UNSUPPORTED_MEASURE", "NO_MACRO", "NO_OPERATOR",
    "UNCONSUMED_CONDITION", "UNSUPPORTED_AGGREGATION", "UNSUPPORTED_GROUPED_MEASURE",
    "UNSUPPORTED_AGGREGATION_COMBINATION", "UNVERIFIED_TIMS_CONTRACT",
    "UNSUPPORTED_PARTITION_SIZE", "UNSUPPORTED_PERIOD_FOR_GROUPING", "UNRESOLVED_PERIOD",
    "DATE_EXPRESSION_UNSUPPORTED", "DATE_MULTIPLE_UNSUPPORTED",
    "TAXI_TYPE_EXPRESSION_UNSUPPORTED", "DATE_EXECUTION_UNVERIFIED",
    "UNSUPPORTED_BY_PROVIDER",
})

SERVICE_TIMEZONE = ZoneInfo("Asia/Seoul")


def seoul_today():
    return datetime.now(SERVICE_TIMEZONE).date()


class Stage:
    """실패 지점을 로그에서 바로 알 수 있도록 단계 이름을 고정한다."""

    PLANNER = "planner"
    COMPOSITION = "composition"
    #: 하위 호환. 기록을 읽는 쪽이 아직 쓰고 있을 수 있어 남겨 둔다.
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
    #: 적용된 macro를 이어 붙인 서명. 기존 기록/CLI가 읽던 key를 유지한다.
    template: str | None = None
    applied_macros: list[str] = field(default_factory=list)
    grounding: dict[str, Any] | None = None
    slots: dict[str, Any] = field(default_factory=dict)
    plan: dict[str, Any] | None = None
    validation: dict[str, Any] | None = None
    execution_plan: dict[str, Any] | None = None
    execution: dict[str, Any] | None = None
    hop_log: list[dict[str, Any]] = field(default_factory=list)
    scope_labels: dict[str, str] = field(default_factory=dict)
    #: 조건 보존 기능의 기록(원문 근거 → 해석 → 보정)과 실행 인자까지의 추적.
    condition_audit: dict[str, Any] | None = None
    condition_trace: list[dict[str, Any]] | None = None
    #: 조건별 검증 범위(질문 해석 / 요청 인자 / provider 계약). 전체 완료로 적지 않는다.
    verification: dict[str, Any] | None = None
    #: 실행 계약을 정한 provider 프로필(provider, 계약, TIMS 가정 모드, 합성 데이터 여부).
    execution_profile: dict[str, Any] | None = None
    #: 질문–graph 예시 검색 기록(예시 id·점수·순서·prompt 절 hash). 검색을 끄면 None.
    retrieval: dict[str, Any] | None = None
    attempts: list[dict[str, Any]] = field(default_factory=list)
    repair_count: int = 0
    #: 재계획 종류별 시도/성공 횟수. 계획 단계와 실행 단계를 구분해 센다.
    repairs: dict[str, Any] = field(default_factory=dict)
    final_answer: str | None = None
    error: dict[str, Any] | None = None
    runtime_error: str | None = None
    cancelled: bool = False
    durations: dict[str, float] = field(default_factory=dict)

    @property
    def outcome(self):
        """결과 종류. 답을 냈는지, 사용자 확인이 필요한지, 지원 범위 밖인지를 가른다.

        확인 필요는 오류 context의 ``needs_clarification``에서만 온다. 질문이 여러
        집계를 허용해 계획을 정할 수 없는 경우이며, 지원하지 않는 계산과 구분한다.
        """
        if self.cancelled:
            return OUTCOME_CANCELLED
        if self.final_answer is not None:
            return OUTCOME_ANSWERED
        error = self.error or {}
        if (error.get("context") or {}).get("needs_clarification"):
            return OUTCOME_NEEDS_CLARIFICATION
        if error.get("code") in UNSUPPORTED_CODES:
            return OUTCOME_UNSUPPORTED
        return OUTCOME_FAILED

    def to_dict(self):
        return {
            "agent_mode": self.agent_mode,
            "outcome": self.outcome,
            "stage": self.stage,
            "repair_count": self.repair_count,
            "repairs": dict(self.repairs),
            "scope_labels": dict(self.scope_labels),
            "condition_audit": self.condition_audit,
            "condition_trace": self.condition_trace,
            "verification": self.verification,
            "execution_profile": self.execution_profile,
            "retrieval": self.retrieval,
            "attempts": [dict(item) for item in self.attempts],
            "planner": self.planner,
            "template": self.template,
            "applied_macros": list(self.applied_macros),
            "grounding": self.grounding,
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
    """planner/composer/validator/compiler/executor를 한 경로로 묶는다."""

    def __init__(self, *, planner, composer, tool_executor, clock=None,
                 execution_profile=None):
        self.planner = planner
        self.composer = composer
        self.tool_executor = tool_executor
        #: 실행 계약. 기본은 mock + legacy(기존 동작). condition_check와 무관하다.
        self.execution_profile = execution_profile or providers.profile_for()
        declared = getattr(tool_executor, "provider", None)
        if declared is not None and declared != self.execution_profile.provider:
            raise GeoFlowError(
                f"Tool provider({declared})와 실행 프로필({self.execution_profile.provider})이 "
                "다릅니다.",
                code="PROVIDER_PROFILE_MISMATCH",
            )
        #: 상대 기간을 날짜로 풀 기준일. 기간을 로컬에서 구간으로 나눌 때만 쓴다.
        #: 서비스 사용자의 "지난달"은 한국 달력 기준으로 푼다(설계 선택이며 TIMS
        #: 계약이 아니다). 테스트는 고정 날짜를 넣는다.
        self.clock = clock or seoul_today

    @classmethod
    def create(cls, *, client, tool_executor, macro_directory=None,
               planner_prompt=None, model=None,
               aggregation_grounding=structured_grounding.FLAT, clock=None,
               condition_check=False, execution_profile=None, example_selector=None):
        """CLI/Web이 동일하게 사용할 기본 구성으로 파이프라인을 만든다.

        ``example_selector``(geoflow/retrieval.py)는 structured grounding에 검토된 예시를 문맥으로
        붙인다. 예시는 prompt에만 들어가고 조합·검증·실행은 현재 질문의 grounding만 쓴다.
        """
        library = (
            MacroLibrary.from_directory()
            if macro_directory is None
            else MacroLibrary.from_directory(macro_directory)
        )
        planner = GeoFlowPlanner(
            client=client,
            prompt=planner_prompt,
            model=model,
            aggregation_grounding=aggregation_grounding,
            condition_check=condition_check,
            clock=clock,
            example_selector=example_selector,
        )
        return cls(
            planner=planner,
            composer=MacroComposer(library),
            tool_executor=tool_executor,
            clock=clock,
            execution_profile=execution_profile,
        )

    def run(self, question, *, event_handler=None, cancel_checker=None):
        """질문 하나를 GeoFlow 경로로 실행한다.

        장소 조회가 retryable 오류로 실패하면 한 번에 한해 Planner에게 장소
        개념의 값 수정을 요청한다. 수정된 grounding도 composer → validator →
        compiler 전 경로를 다시 통과하므로 어떤 guard도 우회하지 않는다.
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
            run.retrieval = _retrieval_record(self.planner, question)
            return _fail(run, error, started_at)
        run.retrieval = _retrieval_record(self.planner, question)

        run.durations["planner_ms"] = planner_output.duration_ms
        run.durations["execution_ms"] = 0.0
        # 계획 단계와 실행 단계가 재계획 한 번을 나눠 쓴다. 두 단계가 각각
        # 한 번씩 쓰면 전체적으로 두 번 다시 묻게 되어, "한 질문에 재계획은
        # 최대 한 번"이라는 성질이 깨진다.
        repairs_used = 0

        attempt_index = 0
        while True:
            try:
                plan, execution_plan = self._prepare(
                    question, planner_output, user_scopes, run, emit,
                )
            except GeoFlowError as error:
                decision = decide_repair(error)
                exhausted = repairs_used >= MAX_REPAIR_ATTEMPTS
                attempted = bool(decision.repairable) and not exhausted
                record = _planning_attempt(
                    attempt_index, error, decision,
                    attempted=attempted, exhausted=exhausted,
                )
                run.attempts.append(record)

                if run.execution is not None:
                    # 이미 실행한 적이 있으면 직전 실행 실패를 그대로 보고한다.
                    break
                if not attempted:
                    return _fail(run, error, started_at)

                emit(
                    "geoflow_repair",
                    attempt=attempt_index + 1,
                    failure={
                        "stage": error.stage,
                        "code": error.code,
                        "kind": decision.kind,
                        "message": error.user_message,
                    },
                )
                # 시도 자체를 먼저 센다. 재질의가 실패해도 시도는 있었다.
                _count_repair(run, decision.kind, ok=False)
                try:
                    planner_output = self.planner.repair_planning_error(
                        question, planner_output,
                        error=error, decision=decision,
                    )
                except GeoFlowError as repair_error:
                    record["repair_result"] = STATUS_REPAIR_FAILED
                    record["repair_error"] = repair_error.to_dict()
                    return _fail(run, error, started_at)

                record["repair_result"] = STATUS_OK
                repairs_used += 1
                run.repair_count += 1
                _count_repair(run, decision.kind, ok=True, attempted=False)
                run.durations["planner_ms"] += planner_output.duration_ms
                attempt_index += 1
                continue

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
                "applied_macros": list(plan.applied_macros),
                "slots": dict(plan.slots),
                "status": result.status,
                "tools": [entry["tool"] for entry in result.trace],
                "error": result.error,
            })

            if result.status == STATUS_OK:
                return self._finish(
                    run, plan, result, started_at,
                    event_handler=event_handler,
                    execution_plan=execution_plan,
                )

            if result.status == STATUS_CANCELLED:
                run.cancelled = True
                run.durations["total_ms"] = _elapsed(started_at)
                return run

            failure = _repairable_failure(plan, execution_plan, result)
            if failure is None or repairs_used >= MAX_REPAIR_ATTEMPTS:
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
            _count_repair(run, "place_value", ok=False)
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
            repairs_used += 1
            _count_repair(run, "place_value", ok=True, attempted=False)
            run.durations["planner_ms"] += planner_output.duration_ms
            attempt_index += 1

        run.error = (run.execution or {}).get("error")
        run.runtime_error = (run.error or {}).get(
            "detail", "실행에 실패했습니다.",
        )
        run.durations["total_ms"] = _elapsed(started_at)
        return run

    def _prepare(self, question, planner_output, user_scopes, run, emit):
        """planner 출력을 검증된 실행 계획까지 끌고 간다."""
        run.planner = planner_output.to_dict()
        run.grounding = planner_output.grounding.to_dict()
        run.condition_audit = planner_output.grounding.condition_audit

        run.stage = Stage.COMPOSITION
        plan = self.composer.compose(planner_output.grounding)
        run.plan = plan.to_dict()
        run.template = plan.template
        run.applied_macros = list(plan.applied_macros)
        run.slots = dict(plan.slots)
        emit(
            "geoflow_plan",
            template=plan.template,
            applied_macros=list(plan.applied_macros),
            slots=plan.slots,
            duration_ms=planner_output.duration_ms,
        )

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
        # 실행 계약과 기간 정책은 provider 프로필이 정한다. condition_check는 해석 옵션이다.
        profile = self.execution_profile
        run.execution_profile = profile.to_dict()
        execution_plan = compile_plan(
            plan, reference_date=self.clock(), contract=profile.contract,
            date_policy=profile.date_policy,
        )
        run.execution_plan = execution_plan.to_dict()
        run.condition_trace = conditions.trace(
            plan, execution_plan, planner_output.grounding.condition_audit,
        )
        run.verification = conditions.verification(
            planner_output.grounding.condition_audit, execution_plan, profile.contract,
        )
        emit("geoflow_execution_plan", execution_plan=run.execution_plan)
        return plan, execution_plan

    def _finish(self, run, plan, result, started_at,
                *, event_handler=None, execution_plan=None):
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
            # 답변 표현은 최종 concept에서 정해진다(geoflow/answer.py).
            run.final_answer = format_answer(
                plan, result, labels=labels, execution_plan=execution_plan,
            )
            note = conditions.describe_for_answer(
                run.condition_audit, run.verification, execution_plan,
            )
            if note:
                run.final_answer = f"{run.final_answer}\n{note}"
            environment = describe_environment(self.execution_profile, execution_plan)
            if environment:
                run.final_answer = f"{run.final_answer}\n{environment}"
        except GeoFlowError as error:
            return _fail(run, error, started_at)
        run.stage = Stage.DONE
        run.durations["total_ms"] = _elapsed(started_at)
        return run


def describe_environment(profile, execution_plan):
    """합성 데이터 provider의 답에 계산 환경과 요청 기간을 밝힌다. 기본 mock 답은 그대로다."""
    if profile is None or not profile.synthetic:
        return ""
    lines = [f"- 계산 환경: {profile.provider} provider — 고정 합성 데이터로 계산한 값이며 "
             "실제 교통 데이터나 TIMS 결과가 아닙니다."]
    requested = []
    for record in (getattr(execution_plan, "date_semantics", {}) or {}).values():
        if record.get("request"):
            text = ", ".join(record["request"])
            if record.get("value") != text:
                text += f"(질문 기간 {record['value']}"
                if record.get("reference_date"):
                    text += f", 기준일 {record['reference_date']} Asia/Seoul"
                text += ")"
            requested.append(text)
    for detail in (getattr(execution_plan, "periods", {}) or {}).values():
        text = detail["resolved"]
        if detail.get("period") != text:
            text += f"(질문 기간 {detail['period']}"
            if detail.get("reference_date"):
                text += f", 기준일 {detail['reference_date']} Asia/Seoul"
            text += ")"
        requested.append(text)
    if requested:
        lines.append("- 적용 기간: " + "; ".join(requested)
                     + " — 양 끝 포함, 영업일(service_date) 기준")
    lines.append("- 계산 의미: 레코드 = 택시 한 대의 영업일 하루 매출(원). 평균의 분모는 조건에 맞는 "
                 "레코드 수(결측 제외), 주는 월요일 시작이며 기간 경계에서 잘립니다.")
    return "\n".join(lines)


def _retrieval_record(planner, question):
    record = getattr(planner, "retrieval_record", None)
    return record(question) if record is not None else None


def _planning_attempt(index, error, decision, *, attempted, exhausted):
    """계획을 만들지 못한 시도를 기록으로 남긴다.

    기존 attempt 기록의 key는 그대로 두고 선택 항목만 덧붙인다. 실행에
    이르지 못했으므로 tools/slots는 비어 있다.
    """
    return {
        "index": index,
        "stage": error.stage,
        "status": STATUS_PLANNING_FAILED,
        "error_code": error.code,
        "error": error.to_dict(),
        "repairable": bool(decision.repairable),
        "repair_kind": decision.kind,
        "repair_reason": decision.reason,
        "repair_attempted": attempted,
        "repair_result": None,
        "reason": (
            "재계획 시도 횟수 소진" if exhausted and decision.repairable
            else None if attempted else decision.reason
        ),
    }


def _count_repair(run, kind, *, ok, attempted=True):
    """재계획 종류별 시도/성공 횟수를 센다."""
    counters = run.repairs.setdefault(
        kind or "unknown", {"attempted": 0, "succeeded": 0},
    )
    if attempted:
        counters["attempted"] += 1
    if ok:
        counters["succeeded"] += 1


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
    concept = next(
        (
            node.id for node in plan.concepts
            if node.concept == CoreConcept.LOCATION
            and node.subtype == Subtype.PLACE
            and isinstance(node.value, dict)
            and node.value.get("name") == name
        ),
        None,
    )
    return {
        "concept": concept or "(알 수 없음)",
        "name": name,
        "region": step.arguments.get("region", ""),
        "message": error.get("user_message") or error.get("detail", ""),
        "step_id": step.id,
    }


def _fail(run, error, started_at):
    run.error = error.to_dict()
    if (error.context or {}).get("needs_clarification"):
        # 실패가 아니라 사용자에게 되물어야 하는 상태다.
        run.runtime_error = f"확인 필요: {error.user_message}"
    else:
        run.runtime_error = f"{error.stage} 단계 실패: {error.detail}"
    run.final_answer = None
    run.durations["total_ms"] = _elapsed(started_at)
    return run


def _elapsed(started_at):
    return round((time.perf_counter() - started_at) * 1000, 3)
