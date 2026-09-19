# -*- coding: utf-8 -*-
"""Ollama native HTTP API 접근 계층.

Tool Schema를 변환하지 않고 ``/api/chat``에 그대로 전달하며, 설치 모델과
capability 확인도 Ollama가 제공하는 ``/api/tags``·``/api/show``만 사용한다.
"""

import json
import math
import os
import re

import httpx


DEFAULT_CHAT_TIMEOUT = 120.0


_SENSITIVE_KEY_PATTERN = re.compile(
    r"(?i)(api[_-]?key|password|passwd|token|authorization|secret)"
)
_SENSITIVE_TEXT_PATTERN = re.compile(
    r"(?i)((?:api[_-]?key|password|passwd|token|authorization|secret)\s*[:=]\s*)"
    r"([^\s,;}]+)"
)


class OllamaRequestError(RuntimeError):
    """Ollama HTTP 오류의 status/model/detail을 보존하는 예외."""

    def __init__(self, *, status, model, detail):
        self.status = status
        self.model = model
        self.detail = detail
        super().__init__(
            "Ollama 요청 실패\n"
            f"status={status}\n"
            f"model={model}\n"
            f"detail={detail}"
        )


def resolve_chat_timeout(explicit=None, environ=None):
    """명시값, 환경변수, 기본값 순서로 양수 chat timeout을 확정한다."""
    if explicit is not None:
        raw_value = explicit
        source = "chat timeout"
    else:
        environment = os.environ if environ is None else environ
        raw_value = environment.get("OLLAMA_CHAT_TIMEOUT")
        if raw_value is None:
            return DEFAULT_CHAT_TIMEOUT
        source = "OLLAMA_CHAT_TIMEOUT"

    try:
        timeout = float(raw_value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"Invalid {source}: {raw_value}") from error
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError(f"Invalid {source}: {raw_value}")
    return timeout


#: ``--model-think`` 선택지. auto는 payload에 think를 넣지 않는다는 뜻이다.
THINK_CHOICES = ("auto", "on", "off")

_THINK_BY_CHOICE = {"auto": None, "on": True, "off": False}


def resolve_think(choice):
    """CLI 선택값을 ``/api/chat``의 ``think`` 값으로 바꾼다."""
    if choice is None:
        return None
    try:
        return _THINK_BY_CHOICE[choice]
    except KeyError as error:
        raise ValueError(f"Invalid think: {choice}") from error


def chat_options(base, num_predict=None):
    """기본 options에 생성 상한을 얹는다. 지정하지 않으면 그대로 둔다."""
    options = dict(base or {})
    if num_predict is not None:
        if num_predict < 1:
            raise ValueError(f"num_predict는 1 이상이어야 합니다: {num_predict}")
        options["num_predict"] = num_predict
    return options


def _redact_sensitive(value):
    """오류 body에 혹시 포함된 인증정보성 필드를 출력 전에 가린다."""
    if isinstance(value, dict):
        return {
            key: "***" if _SENSITIVE_KEY_PATTERN.search(str(key)) else _redact_sensitive(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact_sensitive(item) for item in value]
    if isinstance(value, str):
        return _SENSITIVE_TEXT_PATTERN.sub(r"\1***", value)
    return value


def _response_detail(response):
    """Ollama 오류 응답의 JSON 또는 text body를 안전한 문자열로 만든다."""
    try:
        body = response.json()
    except (ValueError, json.JSONDecodeError):
        body = None

    if body is not None:
        safe_body = _redact_sensitive(body)
        if isinstance(safe_body, dict) and safe_body.get("error"):
            detail = safe_body["error"]
            if isinstance(detail, str):
                return detail
        return json.dumps(safe_body, ensure_ascii=False)

    text = _redact_sensitive((getattr(response, "text", "") or "").strip())
    return text or "응답 body 없음"


class OllamaClient:
    """모델 선택·capability 조회·chat 요청을 담당하는 얇은 HTTP client."""

    def __init__(
        self,
        host,
        model,
        options=None,
        http_client=None,
        chat_timeout=None,
        think=None,
    ):
        self.host = host.rstrip("/")
        self.model = model
        self.options = dict(options or {})
        self._http = http_client or httpx
        self.chat_timeout = resolve_chat_timeout(chat_timeout)
        #: None이면 payload에 넣지 않고 모델 기본 동작을 따른다.
        self.think = think
        self._model_info = None

    def _check_response(self, response):
        status = getattr(response, "status_code", None)
        if status is not None and status >= 400:
            raise OllamaRequestError(
                status=status,
                model=self.model,
                detail=_response_detail(response),
            )
        return response

    def list_models(self):
        """``/api/tags``의 설치 모델 항목을 원형에 가깝게 반환한다."""
        response = self._http.get(f"{self.host}/api/tags", timeout=5.0)
        self._check_response(response)
        return response.json().get("models", [])

    def show_model(self, refresh=False):
        """선택 모델의 ``/api/show`` 결과를 조회하고 실행 중 캐시한다."""
        if self._model_info is None or refresh:
            response = self._http.post(
                f"{self.host}/api/show",
                json={"model": self.model},
                timeout=30.0,
            )
            self._check_response(response)
            self._model_info = response.json()
        return self._model_info

    def get_capabilities(self, refresh=False):
        """Ollama가 보고한 capability 문자열을 중복 없이 순서대로 반환한다."""
        capabilities = self.show_model(refresh=refresh).get("capabilities", []) or []
        return list(dict.fromkeys(str(item) for item in capabilities))

    def supports_tools(self):
        """모델 family 추측 없이 ``capabilities``의 ``tools`` 존재만 판단한다."""
        return "tools" in set(self.get_capabilities())

    def chat(self, messages, tools=None):
        """Ollama native message dict와 Tool Schema를 변환 없이 전송한다.

        ``tools=None``이면 payload에 ``tools`` key 자체를 넣지 않는다. 따라서
        native Tool Calling 미지원 모델도 일반 chat 요청을 받을 수 있다.
        ``think``도 같은 방식으로, 지정한 경우에만 payload에 넣는다.
        """
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": dict(self.options),
        }
        if tools is not None:
            payload["tools"] = tools
        if self.think is not None:
            payload["think"] = self.think

        response = self._http.post(
            f"{self.host}/api/chat",
            json=payload,
            timeout=self.chat_timeout,
        )
        self._check_response(response)
        return response.json()
