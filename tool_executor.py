# -*- coding: utf-8 -*-
"""YAML Tool Schema 검증과 Provider 실행을 담당하는 경량 Executor."""

from jsonschema import Draft202012Validator


RETRYABLE_BY_ERROR_CODE = {
    "INVALID_ARGUMENT": True,
    "NOT_FOUND": True,
    "UNSUPPORTED_COMBINATION": True,
    "TOOL_ERROR": False,
}
SUPPORTED_ERROR_CODES = frozenset(RETRYABLE_BY_ERROR_CODE)


def _error_result(error_code, message, *, retryable=None):
    if retryable is None:
        retryable = RETRYABLE_BY_ERROR_CODE[error_code]
    return {
        "status": "ERROR",
        "error_code": error_code,
        "message": message,
        "retryable": retryable,
    }


def invalid_argument_result(message):
    """Agent 정책 검증에서도 Executor와 동일한 오류 계약을 사용한다."""
    return _error_result("INVALID_ARGUMENT", message)


def _validation_message(error):
    """jsonschema 오류를 다음 model hop에서 수정하기 쉬운 문장으로 정리한다."""
    path = ".".join(str(item) for item in error.absolute_path)

    if error.validator == "required" and isinstance(error.instance, dict):
        missing = [
            name for name in error.validator_value
            if name not in error.instance
        ]
        if missing:
            return f"필수 파라미터 {missing[0]!r}가 없습니다."

    if error.validator == "additionalProperties" and isinstance(error.instance, dict):
        allowed = set((error.schema.get("properties") or {}).keys())
        unknown = sorted(set(error.instance) - allowed)
        if unknown:
            return f"허용되지 않은 파라미터입니다: {', '.join(unknown)}"

    if path:
        return f"파라미터 {path!r}: {error.message}"
    return f"Tool arguments: {error.message}"


class ToolExecutor:
    """YAML Tool 목록으로 허용 범위를 제한하고 Handler를 실행한다."""

    def __init__(self, *, tools, handlers):
        self._handlers = dict(handlers)
        self._validators = {}

        for tool in tools:
            function = tool.get("function") or {}
            name = function.get("name")
            parameters = function.get("parameters")
            if not isinstance(name, str) or not isinstance(parameters, dict):
                raise ValueError("Tool definition에 name 또는 parameters가 없습니다.")
            if name in self._validators:
                raise ValueError(f"중복 Tool definition입니다: {name}")
            self._validators[name] = Draft202012Validator(parameters)

    @property
    def tool_names(self):
        return tuple(self._validators)

    def execute(self, tool_name, arguments):
        """검증 성공 시 Provider 결과를 원형 그대로 반환한다."""
        validator = self._validators.get(tool_name)
        if validator is None:
            return _error_result(
                "INVALID_ARGUMENT",
                f"사용할 수 없는 Tool입니다: {tool_name}",
            )

        validation_errors = sorted(
            validator.iter_errors(arguments),
            key=lambda error: (
                tuple(str(item) for item in error.absolute_path),
                error.message,
            ),
        )
        if validation_errors:
            return _error_result(
                "INVALID_ARGUMENT",
                _validation_message(validation_errors[0]),
            )

        handler = self._handlers.get(tool_name)
        if handler is None:
            return _error_result(
                "TOOL_ERROR",
                f"Tool Provider가 등록되지 않았습니다: {tool_name}",
            )

        try:
            result = handler(arguments)
        except Exception as error:
            return _error_result(
                "TOOL_ERROR",
                f"Tool 실행에 실패했습니다: {error}",
            )

        if not isinstance(result, dict) or result.get("status") != "ERROR":
            return result

        normalized = dict(result)
        error_code = normalized.get("error_code")
        if error_code not in SUPPORTED_ERROR_CODES:
            error_code = "TOOL_ERROR"
            normalized["error_code"] = error_code
        normalized.setdefault("message", "Tool 실행 오류")
        normalized.setdefault(
            "retryable",
            RETRYABLE_BY_ERROR_CODE[error_code],
        )
        return normalized
