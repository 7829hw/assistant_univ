# -*- coding: utf-8 -*-
"""실행 adapter에서 사용할 Tool handler mapping을 선택한다."""

import os

from mock_responses import MOCK_HANDLERS


TOOL_PROVIDER_ENV = "ASSISTANT_TOOL_PROVIDER"
DEFAULT_TOOL_PROVIDER = "mock"


def get_tool_handlers(provider=None):
    """현재 Provider 설정에 해당하는 handler mapping을 반환한다.

    지원하지 않는 값을 Mock으로 fallback하지 않아 실제 데이터로 오인할
    가능성을 차단한다.
    """
    selected = (
        os.environ.get(TOOL_PROVIDER_ENV, DEFAULT_TOOL_PROVIDER)
        if provider is None
        else provider
    )
    if selected != "mock":
        raise ValueError(f"Unsupported tool provider: {selected}")
    return MOCK_HANDLERS
