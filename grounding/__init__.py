# -*- coding: utf-8 -*-
"""pilot_006 grounding 표현 계층(결정 111). Full 경로(``geoflow/``, ``prompts/``)는 바꾸지 않고, Partial 경로를 설정 뒤에 둔다.

- ``grounding_target``: ``full``(기본값) 또는 ``partial``. ``full``이면 이 패키지의 Partial 코드는 불리지 않는다.
- 이 패키지는 ``execution_spec.SEMANTIC_CODE`` 밖이다. 그래서 Full 경로 지문(``791c4a68``)이 바뀌지 않는다.
  Partial 경로의 실행 의미는 trunk 지문 + 이 패키지(``partial_fingerprint``)로 기록한다.
"""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
GROUNDING_TARGETS = ("full", "partial")
DEFAULT_GROUNDING_TARGET = "full"
#: Partial prompt(P0.3). partial-grounding ab9d215 ``evaluation/partial_grounding/prompts/partial_p0_3.yaml``의 바이트 복사본.
PARTIAL_PROMPT = HERE / "prompts/partial_p0_3.yaml"
PARTIAL_PROMPT_FILE_SHA256 = "596634843af7c4d00b05a9d65a864cbb3e1215f7d3ce45ee390615bef5220b10"
#: Partial 실행 경로를 정하는 파일(``partial_fingerprint``).
PARTIAL_PATH_FILES = ("completion.py", "partial_planner.py", "prompts/partial_p0_3.yaml")


def check_target(target):
    if target not in GROUNDING_TARGETS:
        raise ValueError(f"grounding_target must be one of {GROUNDING_TARGETS}: {target!r}")
    return target


def planner_class(target=DEFAULT_GROUNDING_TARGET):
    """``grounding_target``에 맞는 planner 클래스."""
    from geoflow.planner import GeoFlowPlanner
    if check_target(target) == "full":
        return GeoFlowPlanner
    from grounding.partial_planner import PartialPlanner
    return PartialPlanner


def planner_prompt(target=DEFAULT_GROUNDING_TARGET):
    """``grounding_target``의 planner prompt 텍스트. full이면 None(GeoFlowPlanner 기본 prompt)."""
    if check_target(target) == "full":
        return None
    from geoflow.planner import load_planner_prompt
    if hashlib.sha256(PARTIAL_PROMPT.read_bytes()).hexdigest() != PARTIAL_PROMPT_FILE_SHA256:
        raise ValueError("Partial prompt file drift")
    return load_planner_prompt(PARTIAL_PROMPT)


def make_planner(target=DEFAULT_GROUNDING_TARGET, **kwargs):
    """``GeoFlowPlanner(**kwargs)`` 또는 Partial planner(+ P0.3 prompt)."""
    prompt = planner_prompt(target)
    if prompt is not None and "prompt" not in kwargs:
        kwargs["prompt"] = prompt
    return planner_class(target)(**kwargs)


def partial_fingerprint():
    """Partial 실행 경로 추가 코드의 지문(completion, planner, P0.3 prompt). Full 지문과 함께 기록한다."""
    files = [HERE / name for name in PARTIAL_PATH_FILES]
    listing = [(p.relative_to(HERE.parent).as_posix(), hashlib.sha256(p.read_bytes()).hexdigest()) for p in files]
    return hashlib.sha256(json.dumps(listing, ensure_ascii=False).encode("utf-8")).hexdigest()


def make_pipeline(target=DEFAULT_GROUNDING_TARGET, **create_kwargs):
    """``GeoFlowPipeline.create(**create_kwargs)``. partial이면 planner를 ``PartialPlanner``로 바꾼다.

    ``create``는 planner를 ``GeoFlowPlanner``로 만든다. ``PartialPlanner``는 상태를 더하지 않는 하위 클래스라서
    만들어진 planner 객체의 클래스만 바꾼다(생성 인자는 그대로). ``planner_prompt``를 주지 않으면 partial은 P0.3 prompt를 쓴다.
    """
    from geoflow.pipeline import GeoFlowPipeline
    if check_target(target) == "partial" and create_kwargs.get("planner_prompt") is None:
        create_kwargs["planner_prompt"] = planner_prompt("partial")
    pipeline = GeoFlowPipeline.create(**create_kwargs)
    if target == "partial":
        pipeline.planner.__class__ = planner_class("partial")
    return pipeline
