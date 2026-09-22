# -*- coding: utf-8 -*-
"""GeoFlow 단계별 오류 계약.

``user_message``는 사용자에게 보여도 되는 설명이고, ``detail``은 디버깅용
내부 정보다. 두 값을 분리해 두어야 CLI/Web이 노출 범위를 스스로 정할 수 있다.
"""


class GeoFlowError(Exception):
    """GeoFlow 단계에서 발생한 오류의 공통 기반."""

    stage = "geoflow"
    default_user_message = "질문을 실행 가능한 분석 계획으로 변환하지 못했습니다."

    def __init__(self, detail, *, user_message=None, code=None, context=None):
        self.detail = str(detail)
        self.user_message = user_message or self.default_user_message
        self.code = code or type(self).__name__
        self.context = dict(context or {})
        super().__init__(self.detail)

    def to_dict(self):
        """평가 로그에 그대로 기록할 수 있는 구조로 만든다."""
        return {
            "stage": self.stage,
            "code": self.code,
            "detail": self.detail,
            "user_message": self.user_message,
            "context": self.context,
        }


class TemplateError(GeoFlowError):
    """Template 정의 자체 또는 slot 채우기 실패."""

    stage = "template"
    default_user_message = "질문에 맞는 분석 template을 구성하지 못했습니다."


class PlannerError(GeoFlowError):
    """Planner LLM 출력이 계약을 만족하지 못함."""

    stage = "planner"
    default_user_message = "질문을 분석 계획으로 해석하지 못했습니다."


class ValidationError(GeoFlowError):
    """GeoFlow Plan 정적 검증 실패."""

    stage = "validation"
    default_user_message = "생성된 분석 계획이 안전 규칙을 만족하지 않습니다."

    def __init__(self, detail, *, rule=None, **kwargs):
        self.rule = rule
        context = dict(kwargs.pop("context", None) or {})
        if rule:
            context.setdefault("rule", rule)
        super().__init__(detail, code=rule or "VALIDATION", context=context, **kwargs)


class CompilerError(GeoFlowError):
    """GeoFlow Plan을 실행 계획으로 변환하지 못함."""

    stage = "compiler"
    default_user_message = "분석 계획을 실행 순서로 변환하지 못했습니다."


class ExecutionError(GeoFlowError):
    """실행 계획 수행 중 복구 불가능한 오류."""

    stage = "execution"
    default_user_message = "분석 계획을 실행하지 못했습니다."


class MacroError(GeoFlowError):
    """Macro 정의 자체가 계약을 만족하지 못함."""

    stage = "macro"
    default_user_message = "분석 조각(macro) 정의를 읽지 못했습니다."


class CompositionError(GeoFlowError):
    """Grounding 결과를 하나의 GeoFlow Graph로 합성하지 못함."""

    stage = "composition"
    default_user_message = "질문을 실행 가능한 분석 그래프로 구성하지 못했습니다."
