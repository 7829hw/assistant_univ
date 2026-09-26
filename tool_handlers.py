# -*- coding: utf-8 -*-
"""실행 adapter에서 사용할 Tool handler mapping을 선택한다."""

import os

from mock_responses import MOCK_HANDLERS


TOOL_PROVIDER_ENV = "ASSISTANT_TOOL_PROVIDER"
DEFAULT_TOOL_PROVIDER = "mock"


def get_tool_handlers(provider=None):
    """현재 Provider 설정에 해당하는 handler mapping을 반환한다.

    지원하지 않는 값을 Mock으로 fallback하지 않아 실제 데이터로 오인할
    가능성을 차단한다. ``reference``는 합성 데이터를 실제로 집계하는 provider다
    (``reference_provider.py``).
    """
    selected = (
        os.environ.get(TOOL_PROVIDER_ENV, DEFAULT_TOOL_PROVIDER)
        if provider is None
        else provider
    )
    if selected == "mock":
        # 호출하는 쪽이 사전을 바꿔도 다른 실행에 새지 않도록 사본을 준다.
        return dict(MOCK_HANDLERS)
    if selected == "reference":
        # 합성 데이터 위의 계산기. 지원하지 않는 도구도 mock으로 넘기지 않는다.
        from reference_provider import reference_handlers
        return reference_handlers()
    raise ValueError(f"Unsupported tool provider: {selected}")


def selected_provider(provider=None):
    """handler 선택과 같은 규칙으로 provider 이름을 돌려준다."""
    return os.environ.get(TOOL_PROVIDER_ENV, DEFAULT_TOOL_PROVIDER) if provider is None else provider
