# -*- coding: utf-8 -*-
"""Prompt 변형의 grounding 정확도를 모델 상태를 비운 채 짝지어 잰다.

측정 protocol: ``isolated_state_v1``

이전 harness는 같은 질문을 두 변형으로 인접 호출했다. Ollama는 요청 사이에
서버 상태를 남기므로, 앞 요청이 뒤 요청의 결과를 바꿨다. 두 번째로 실행된
변형만 반복해서 무너졌고, 변형별로 몰아서 돌려도 앞선 요청 순서 전체에
결과가 좌우됐다. 그 상태에서 얻은 A/B 차이는 prompt의 효과라고 말할 수 없다.

그래서 관측 하나하나를 새 모델 상태에서 시작한다.

    reset → 검증 → 변형 A 관측 → 기록
    reset → 검증 → 변형 B 관측 → 기록

reset은 Ollama 0.33.2에서 실측으로 확인한 방법을 쓴다.

1. ``POST /api/generate {"model": M, "keep_alive": 0}``는 ``done_reason:
   "unload"``를 돌려주며 모델을 내린다. 이미 내려가 있어도 같은 응답이다.
2. ``/api/ps``에 모델이 없으면 runner가 내려간 것이다.
3. 관측의 첫 호출이 ``load_duration``을 크게 보고하면 새 runner가 가중치를
   다시 올린 것이다. 새 runner에는 이전 요청의 KV 상태가 있을 수 없다.
   (warm 호출은 약 1ms, cold 호출은 약 2.6~3.2초였다.)

``prompt_eval_count``는 같은 prompt를 warm으로 다시 보내도 줄지 않아 prefix
재사용의 증거가 되지 못한다. 기록만 하고 판정에는 쓰지 않는다.

관측 하나 안에서는 첫 호출과 재질의가 같은 runner를 쓴다. 제품이 실제로
그렇게 동작하므로 관측의 일부다. 격리하는 것은 관측과 관측 사이다.

이 측정은 매 호출에 모델 적재 시간이 들어가므로 latency는 참고값이다.
운영 latency는 warm 상태에서 따로 잰다.

사용법:
    python evaluate_prompt_ab.py run --arms T0,T0 --queries b05,b10 --repetitions 10 --label self_t0
    python evaluate_prompt_ab.py run --arms D_PRE,T0 --queries @boundary,q27 --repetitions 5 --label full
    python evaluate_prompt_ab.py analyze evaluation/prompt_ab/<run>
    python evaluate_prompt_ab.py floor <run> <run> ...
"""

import argparse
import dataclasses
import functools
import hashlib
import json
import math
import os
import subprocess
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import httpx

import evaluate_planner as E
import paraphrase_corpus
from paraphrase_corpus import final_tool_call, tool_arg_mismatches, tool_defaults
from geoflow import factors as F
from geoflow import planner as planner_module
from geoflow.composer import MacroComposer
from geoflow.errors import GeoFlowError
from geoflow.grounding import OD_ROLE, parse_grounding
from geoflow.macros import MacroLibrary
from geoflow.planner import GeoFlowPlanner, parse_planner_json
from geoflow.repair import RepairKind
from geoflow.repair import decide as decide_repair
from geoflow.types import CoreConcept, subtype_allowed
from ollama_client import OllamaClient
from query_loader import load_queries

PROTOCOL = "isolated_state_v1"
BASE_DIR = Path(__file__).resolve().parent
RESULT_DIR = BASE_DIR / "evaluation" / "prompt_ab"
DEFAULT_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
DEFAULT_MODEL = "qwen3:8b"
QUERY_FILES = ("stub_query_boundary.yaml", "stub_query.yaml")

#: 첫 호출이 이보다 짧게 모델을 올렸다면 이미 올라가 있던 runner를 쓴 것이다.
#: 실측 cold 약 2600ms, warm 약 1ms라 경계가 넓다.
COLD_LOAD_MIN_MS = 500.0

#: 이 수 이상 무효 관측이 나오면 측정을 멈춘다. 조용히 계속하지 않는다.
DEFAULT_MAX_INVALID = 0

VALID = "valid"
INVALID = "invalid_measurement"


class BenchmarkAborted(RuntimeError):
    """측정을 계속하면 오염된 관측이 섞이는 경우."""


# -- 모델 상태 초기화 ------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class ResetResult:
    attempted: bool
    succeeded: bool
    duration_ms: float
    detail: str
    loaded_after: tuple = ()


class OllamaStateReset:
    """관측 전에 모델을 내려 이전 요청의 서버 상태를 없앤다."""

    def __init__(self, host, model, *, http=httpx, timeout=10.0,
                 poll_interval=0.1, sleep=time.sleep, clock=time.perf_counter):
        self.host = host.rstrip("/")
        self.model = model
        self._http = http
        self._timeout = timeout
        self._poll_interval = poll_interval
        self._sleep = sleep
        self._clock = clock

    def loaded_models(self):
        response = self._http.get(f"{self.host}/api/ps", timeout=5.0)
        if response.status_code >= 400:
            raise RuntimeError(f"/api/ps HTTP {response.status_code}")
        return tuple(
            item.get("name") or item.get("model") or ""
            for item in (response.json().get("models") or [])
        )

    def reset(self):
        started = self._clock()

        def done(succeeded, detail, loaded=()):
            return ResetResult(
                attempted=True, succeeded=succeeded,
                duration_ms=round((self._clock() - started) * 1000, 3),
                detail=detail, loaded_after=tuple(loaded),
            )

        try:
            response = self._http.post(
                f"{self.host}/api/generate",
                json={"model": self.model, "keep_alive": 0},
                timeout=30.0,
            )
        except Exception as error:  # noqa: BLE001 - 실패 사유로 기록한다
            return done(False, f"unload 요청 실패: {type(error).__name__}: {error}")
        if response.status_code >= 400:
            return done(False, f"unload HTTP {response.status_code}")
        try:
            reason = response.json().get("done_reason")
        except ValueError:
            return done(False, "unload 응답이 JSON이 아니다")
        if reason != "unload":
            return done(False, f"unload 응답의 done_reason이 {reason!r}")

        # 응답만 믿지 않고 실제로 내려갔는지 본다.
        deadline = started + self._timeout
        while True:
            try:
                loaded = self.loaded_models()
            except Exception as error:  # noqa: BLE001
                return done(False, f"/api/ps 확인 실패: {type(error).__name__}: {error}")
            if self.model not in loaded:
                return done(True, "unloaded", loaded)
            if self._clock() >= deadline:
                return done(False, "제한 시간 안에 모델이 내려가지 않았다", loaded)
            self._sleep(self._poll_interval)


# -- 호출 기록 -------------------------------------------------------------


class RecordingClient:
    """관측 하나의 모든 LLM 호출 응답을 원문 그대로 남긴다.

    오류 context에 원문이 실리지 않는 거부 경로가 있다(예: INVALID_FACTOR).
    그래서 오류가 아니라 client에서 받는다. 관측마다 새로 만들므로 이전 관측의
    기록이 섞이지 않는다.
    """

    def __init__(self, client):
        self._client = client
        self.model = getattr(client, "model", None)
        self.phase = "initial"
        self.calls = []

    def chat(self, messages, tools=None):
        started = time.perf_counter()
        entry = {"phase": self.phase, "index": len(self.calls)}
        try:
            body = self._client.chat(messages, tools=tools)
        except Exception as error:  # noqa: BLE001
            entry.update(error=f"{type(error).__name__}: {error}",
                         elapsed_ms=round((time.perf_counter() - started) * 1000, 3))
            self.calls.append(entry)
            raise
        message = (body.get("message") or {}) if isinstance(body, dict) else {}
        entry.update(
            content=message.get("content"),
            done_reason=body.get("done_reason") if isinstance(body, dict) else None,
            load_duration_ms=_ns_to_ms(body, "load_duration"),
            prompt_eval_count=body.get("prompt_eval_count") if isinstance(body, dict) else None,
            eval_count=body.get("eval_count") if isinstance(body, dict) else None,
            total_duration_ms=_ns_to_ms(body, "total_duration"),
            elapsed_ms=round((time.perf_counter() - started) * 1000, 3),
        )
        self.calls.append(entry)
        return body


def _ns_to_ms(body, key):
    if not isinstance(body, dict) or body.get(key) is None:
        return None
    return round(body[key] / 1e6, 3)


# -- 변형 ------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class PromptVariant:
    """LLM이 보는 계약 하나. system prompt만이 아니라 재질의 문구까지다.

    50fae72는 system prompt에 factor 의미 절을 더하면서 factor 재질의 문구와
    그 안의 허용값 렌더링도 바꿨다. system prompt만 갈아 끼우면 이전 commit의
    재질의 경로를 재현하지 못한다.
    """

    name: str
    prompt: str
    note: str
    #: 재질의 종류별 문구 교체. 비어 있으면 현재 코드의 문구를 쓴다.
    repair_templates: dict = dataclasses.field(default_factory=dict)
    #: factor 재질의의 {allowed} 렌더링. "semantics"는 현재(의미 포함),
    #: "values"는 87ca968(허용값만).
    allowed_renderer: str = "semantics"

    @property
    def sha256(self):
        return hashlib.sha256(self.prompt.encode("utf-8")).hexdigest()

    @functools.cached_property
    def repair_sha256(self):
        """대표 factor 재질의 문구를 실제 경로로 렌더링한 hash."""
        return hashlib.sha256(render_factor_repair(self).encode("utf-8")).hexdigest()


class _StubClient:
    model = "prompt-builder"


def _production_prompt():
    return GeoFlowPlanner(client=_StubClient()).system_prompt()


def _prompt_with_meaning(factor, meaning):
    """factor 설명 하나만 바꾼 prompt. 제품 상태는 반드시 되돌린다."""
    original = F.FACTOR_SPECS[factor]
    F.FACTOR_SPECS[factor] = dataclasses.replace(original, meaning=meaning)
    try:
        return _production_prompt()
    finally:
        F.FACTOR_SPECS[factor] = original


#: 이름은 특정 계약 하나를 가리킨다. 제품 prompt가 바뀌면 T0는 검증에서
#: 걸린다. 그때는 T0를 고치지 말고 새 이름을 붙인다. 같은 이름이 다른 prompt를
#: 가리키면 이력 결과를 잘못 읽게 된다. 값은 각 commit의 git worktree에서
#: 직접 렌더링해 얻었다.
PINNED_SHA256 = {
    "C": "a4db7f29955beeb7e83d3ec454b3d58b4024b80a9093a7184126cd2fb2489228",
    "D_PRE": "64bbceb4e171085f38de782ceb413b3ee814c9df8c7f9576479a9324e123d45d",
    "T0": "f268b2b28feb8b29211a0128798f9bb89d08a491184eaa3df9675cb7e139a02e",
    "T1": "71dcbaf681fcd8c6bc58a9d203f625a7f8b797964ca3a90979b7f49317dde64a",
    "T2": "3523abc587d303e48c0ba4812c2d507eda9e2077668f9cf249ae74ec7ad8e355",
    # 50fae72 factorial. S = system 의미 절, R = factor 재질의 의미.
    "F00": "a4db7f29955beeb7e83d3ec454b3d58b4024b80a9093a7184126cd2fb2489228",
    "F10": "64bbceb4e171085f38de782ceb413b3ee814c9df8c7f9576479a9324e123d45d",
    "F01": "a4db7f29955beeb7e83d3ec454b3d58b4024b80a9093a7184126cd2fb2489228",
    "F11": "64bbceb4e171085f38de782ceb413b3ee814c9df8c7f9576479a9324e123d45d",
}
PINNED_REPAIR_SHA256 = {
    "C": "a5d9baa0bbbf73d1adb43f6a389dd8cef024bfee78c51d9fcc3ade518ed12850",
    "D_PRE": "5af4c744a448f008fa9e1fa92848f4b08e24870bcd156852e4c71369e80e67c4",
    "T0": "5af4c744a448f008fa9e1fa92848f4b08e24870bcd156852e4c71369e80e67c4",
    "T1": "5af4c744a448f008fa9e1fa92848f4b08e24870bcd156852e4c71369e80e67c4",
    "T2": "5af4c744a448f008fa9e1fa92848f4b08e24870bcd156852e4c71369e80e67c4",
    "F00": "a5d9baa0bbbf73d1adb43f6a389dd8cef024bfee78c51d9fcc3ade518ed12850",
    "F10": "a5d9baa0bbbf73d1adb43f6a389dd8cef024bfee78c51d9fcc3ade518ed12850",
    "F01": "5af4c744a448f008fa9e1fa92848f4b08e24870bcd156852e4c71369e80e67c4",
    "F11": "5af4c744a448f008fa9e1fa92848f4b08e24870bcd156852e4c71369e80e67c4",
}

VARIANT_DIR = RESULT_DIR / "variants"

#: 0ccabc3 문구를 조각으로 나눈 것. T1/T2는 이 조각을 빼거나 바꾼다.
#:   (a) 일반 분류    "…조건이며 개념이 아니다."
#:   (b) 금지 지시    "…별도 개념 node로 만들지 않고 이 조건으로만 적는다."
#:   (c) 긍정 예시    "예: … → EVENT/operation + AMOUNT/hours + taxi_type=corporate"
#:   (d) 부정 literal "(OBJECT/corporate, OBJECT/taxi_type으로 적지 않는다)"
#: 0ccabc3에 들어간 문구 그대로. production이 바뀌어도 T0는 이 문구를 가리킨다.
TAXI_MEANING_T0 = (
    '택시 영업 유형을 제한하는 조건이며 개념이 아니다. "개인택시", "법인택시"는\n'
    "    별도 개념 node로 만들지 않고 이 조건으로만 적는다.\n"
    '    예: "법인택시의 평균 운행시간" → EVENT/operation + AMOUNT/hours +\n'
    "    taxi_type=corporate (OBJECT/corporate, OBJECT/taxi_type으로 적지 않는다)"
)
#: T1은 (d)만 뺀다. 틀린 형태를 글자 그대로 보여 준 것의 효과를 본다.
TAXI_MEANING_T1 = (
    '택시 영업 유형을 제한하는 조건이며 개념이 아니다. "개인택시", "법인택시"는\n'
    "    별도 개념 node로 만들지 않고 이 조건으로만 적는다.\n"
    '    예: "법인택시의 평균 운행시간" → EVENT/operation + AMOUNT/hours +\n'
    "    taxi_type=corporate"
)
#: T2는 (a)(b)(d)를 모두 빼고 taxi_type이 어디에 무엇으로 적히는지만 말한다.
#: "개념" "조건" 같은 일반 분류어를 쓰지 않아 다른 구조로 번지지 않게 한다.
#: 예시 질문은 T0와 같게 두어 예시 선택의 차이를 섞지 않는다.
TAXI_MEANING_T2 = (
    "개인택시·법인택시 여부는 factors의 taxi_type에 적는다. 개인택시는 private,\n"
    "    법인택시는 corporate다.\n"
    '    예: "법인택시의 평균 운행시간" → "factors": {"taxi_type": "corporate"}'
)


def _d_pre_prompt():
    """50fae72의 system prompt. production이 바뀌어도 이 계약을 가리킨다."""
    return _prompt_with_meaning("taxi_type", "택시 유형 조건.")


def _repair_r0():
    """87ca968의 factor 재질의: 옛 문구 + 허용값만 렌더링."""
    template = (VARIANT_DIR / "87ca968_factor_repair_instruction.txt").read_text(
        encoding="utf-8",
    )
    return {"repair_templates": {RepairKind.FACTOR_COMPLETION: template},
            "allowed_renderer": "values"}


def _factorial(system_semantics, repair_semantics):
    """50fae72가 한 번에 바꾼 두 축을 따로 켠다.

    S: system prompt의 [조건이 뜻하는 것] 절. R: factor 재질의에 의미를 싣는 것.
    나머지 계약(기본 prompt, 다른 재질의, taxi_type 정의)은 네 arm이 같다.
    """
    prompt = _d_pre_prompt()
    if not system_semantics:
        prompt = E._without_semantics(prompt)
    contract = {"prompt": prompt}
    if not repair_semantics:
        contract.update(_repair_r0())
    return contract


def _c_variant():
    """87ca968: factor 의미 절이 없고, 재질의는 허용값만 보여 준다."""
    template = (VARIANT_DIR / "87ca968_factor_repair_instruction.txt").read_text(
        encoding="utf-8",
    )
    return {
        "prompt": E._without_semantics(_production_prompt()),
        "repair_templates": {RepairKind.FACTOR_COMPLETION: template},
        "allowed_renderer": "values",
    }


_BUILDERS = {
    "C": (_c_variant, "87ca968 (factor 의미 절 이전)"),
    # 0ccabc3~1의 production. git worktree로 만든 prompt와 hash가 같음을 확인했다.
    "D_PRE": (lambda: {"prompt": _prompt_with_meaning("taxi_type", "택시 유형 조건.")},
              "50fae72 = 0ccabc3~1 production (taxi_type 구분 이전)"),
    # production이 바뀌어도 0ccabc3의 계약을 가리키도록 문구를 직접 넣는다.
    "T0": (lambda: {"prompt": _prompt_with_meaning("taxi_type", TAXI_MEANING_T0)},
           "0ccabc3 (taxi_type 구분 문구)"),
    "T1": (lambda: {"prompt": _prompt_with_meaning("taxi_type", TAXI_MEANING_T1)},
           "T0에서 부정 literal 예시만 뺌"),
    "T2": (lambda: {"prompt": _prompt_with_meaning("taxi_type", TAXI_MEANING_T2)},
           "taxi_type 위치와 값만 긍정문으로"),
    # 고정하지 않는다. 그때그때의 production을 뜻한다.
    "PRODUCTION": (lambda: {"prompt": _production_prompt()}, "실행 시점의 production"),
    "F00": (lambda: _factorial(False, False), "S0 R0 = 87ca968의 factor 계약"),
    "F10": (lambda: _factorial(True, False), "S1 R0 = system 의미 절만"),
    "F01": (lambda: _factorial(False, True), "S0 R1 = 재질의 의미만"),
    "F11": (lambda: _factorial(True, True), "S1 R1 = 50fae72의 factor 계약"),
}


def build_variant(name, *, pinned=None, pinned_repair=None):
    if name not in _BUILDERS:
        raise KeyError(f"모르는 prompt 변형: {name} (가능: {', '.join(sorted(_BUILDERS))})")
    builder, note = _BUILDERS[name]
    variant = PromptVariant(name=name, note=note, **builder())
    checks = (
        ("system prompt", variant.sha256,
         (PINNED_SHA256 if pinned is None else pinned).get(name)),
        ("factor 재질의 문구", None,
         (PINNED_REPAIR_SHA256 if pinned_repair is None else pinned_repair).get(name)),
    )
    for what, actual, expected in checks:
        if expected is None:
            continue
        actual = variant.repair_sha256 if actual is None else actual
        if actual != expected:
            raise BenchmarkAborted(
                f"prompt 변형 {name}의 {what} hash가 고정값과 다르다: "
                f"{actual[:16]} != {expected[:16]}. "
                "계약이 바뀌었다면 이 이름을 고치지 말고 새 변형을 추가한다."
            )
    return variant


class FixedPromptPlanner(GeoFlowPlanner):
    """확정한 계약만 쓰는 측정용 Planner. 재질의도 같은 계약을 쓴다."""

    def __init__(self, *, client, variant=None, prompt=None):
        super().__init__(client=client)
        if variant is None:
            variant = PromptVariant(name="ad-hoc", prompt=prompt, note="")
        self.variant = variant
        self._fixed_prompt = variant.prompt
        if variant.repair_templates:
            self.repair_instructions = {**self.repair_instructions,
                                        **variant.repair_templates}

    def system_prompt(self):
        return self._fixed_prompt

    def variant_repair_values(self, decision):
        """재질의 문구의 자리 채움 중 변형이 다르게 정하는 것."""
        if (self.variant.allowed_renderer == "values"
                and decision.kind == RepairKind.FACTOR_COMPLETION):
            return {"allowed": "\n  ".join(
                F.describe_factor(name) for name in decision.allowed_additions
            )}
        return {}

    def _ask_patch(self, question, previous, decision, *, message, extra=None):
        merged = {**self.variant_repair_values(decision), **(extra or {})}
        return super()._ask_patch(question, previous, decision, message=message,
                                  extra=merged or None)

    def plan(self, question):
        _set_phase(self.client, "initial")
        return super().plan(question)

    def repair_planning_error(self, question, previous, *, error, decision):
        _set_phase(self.client, "repair")
        return super().repair_planning_error(
            question, previous, error=error, decision=decision,
        )


@functools.lru_cache(maxsize=1)
def _canonical_factor_repair():
    """hash용 대표 재질의 상황: bucket만 있고 rollup이 빠졌다."""
    grounding = parse_grounding({"concepts": [
        {"id": "op", "concept": "EVENT", "subtype": "operation", "role": "SUPPORT",
         "source": "implicit"},
        {"id": "r", "concept": "AMOUNT", "subtype": "revenue", "role": "MEASURE",
         "source": "implicit"},
    ], "factors": {"bucket": "month", "aggregation": "max"}}, "q")
    try:
        MacroComposer(MacroLibrary.from_directory()).compose(grounding)
    except GeoFlowError as error:
        return decide_repair(error), error.user_message or error.detail
    raise RuntimeError("대표 재질의 상황이 합성에 성공해 버렸다")


def render_factor_repair(variant):
    """Planner가 실제로 보낼 factor 재질의 문구. _ask_patch와 같은 경로다."""
    decision, message = _canonical_factor_repair()
    planner = FixedPromptPlanner(client=_StubClient(), variant=variant)
    return planner_module._fill_instruction(
        planner.repair_instructions[decision.kind],
        {**planner_module._instruction_values(decision, message),
         **planner.variant_repair_values(decision)},
    )


def _set_phase(client, phase):
    if isinstance(client, RecordingClient):
        client.phase = phase


# -- 관측 ------------------------------------------------------------------


def arm_order(query_index, repetition, arms):
    """관측 순서. 난수 없이 질문·반복마다 한 칸씩 돌린다.

    arm이 둘이면 번갈아 가며 먼저 실행된다.
    """
    arms = list(arms)
    shift = (query_index + repetition) % len(arms)
    return arms[shift:] + arms[:shift]


class RecordingComposer:
    """관측 하나에서 마지막으로 합성에 성공한 plan을 남긴다.

    재질의가 있으면 합성을 두 번 부르므로 마지막 것이 최종 plan이다.
    """

    def __init__(self, composer):
        self._composer = composer
        self.last_plan = None

    def compose(self, grounding):
        plan = self._composer.compose(grounding)
        self.last_plan = plan
        return plan


# -- 오류 분류 (v2) --------------------------------------------------------
#
# 첫 grounding에서 무엇이 잘못됐는지(initial_issues)와 최종적으로 어떻게
# 끝났는지(final_category)를 나눈다. 재질의로 고쳐진 실패는 최종 결과에서는
# 보이지 않지만 첫 grounding에는 남는다.

_TIME_UNITS = frozenset({"week", "month", "day", "hour"})
_TAXI_SUBTYPES = frozenset({"taxi_type", "private", "corporate"})
#: 개념에 붙어야 하는 속성. factor 자리에 오면 관계를 잘못 옮긴 것이다.
_CONCEPT_ATTRIBUTES = frozenset({OD_ROLE})
_VALUELESS_CODES = frozenset({"VALUELESS_CONCEPT", "MISSING_CONCEPT_VALUE", "INVALID_PLACE"})
_RELATION_CODES = frozenset({"AMBIGUOUS_LOCATION_RELATION", "MISSING_RELATION_QUALIFIER"})


_TAXI_WORDS_KO = ("개인", "법인", "택시")


def _is_taxi_concept(concept):
    """택시 유형에서 나온 개념 node인가. OBJECT/private, OBJECT/taxi_type 등."""
    if concept.get("subtype") in _TAXI_SUBTYPES:
        return True
    if concept.get("concept") == "OBJECT":
        surface = f"{concept.get('value')} {concept.get('text')}"
        return any(word in surface for word in _TAXI_WORDS_KO)
    return False


def _correct_taxi_factor(record, factors):
    """taxi_type factor를 맞게 적었는가. 기대값이 없으면 적었는지만 본다."""
    value = factors.get("taxi_type")
    if not value:
        return False
    expected = record.get("expected_tool_args") or {}
    return "taxi_type" not in expected or expected["taxi_type"] == value


def _initial_payload(record):
    try:
        payload = parse_planner_json(record.get("raw_text") or "")
    except Exception:  # noqa: BLE001
        return None
    return payload if isinstance(payload, dict) else None


def initial_issues(record):
    """첫 grounding 응답에 있던 문제. 여러 개일 수 있다."""
    issues = []
    refusal_expected = E.NO_TEMPLATE_LABEL in (record.get("expected_macros") or [])
    payload = _initial_payload(record)
    if payload is not None and not payload.get("unsupported"):
        factors = payload.get("factors") if isinstance(payload.get("factors"), dict) else {}
        if factors.get("rollup") in _TIME_UNITS:
            issues.append("bucket_as_rollup")
        if "bucket" in factors and "rollup" not in factors:
            issues.append("missing_rollup")
        if "rollup" in factors and "bucket" not in factors:
            issues.append("rollup_without_bucket")
        for key in factors:
            if key in _CONCEPT_ATTRIBUTES:
                issues.append("relation_attribute_as_factor")
            elif key not in F.FACTOR_SPECS:
                issues.append("invalid_factor")
        concepts = payload.get("concepts") if isinstance(payload.get("concepts"), list) else []
        for concept in concepts:
            if not isinstance(concept, dict):
                continue
            subtype = concept.get("subtype")
            if _is_taxi_concept(concept):
                issues.append("taxi_type_as_concept")
                # factor는 맞게 적고 개념 node를 덧붙인 경우. factor를 모르는 것이
                # 아니라 불필요한 개념을 억제하지 못한 것이다.
                if _correct_taxi_factor(record, factors):
                    issues.append("correct_factor_plus_spurious_concept")
                continue
            try:
                core = CoreConcept(concept.get("concept"))
            except ValueError:
                issues.append("invalid_subtype")
                continue
            if not subtype_allowed(core, subtype):
                issues.append("invalid_subtype")
    code = record.get("initial_error") or record.get("status")
    if code in _VALUELESS_CODES:
        issues.append("valueless_location")
    elif code == "UNGROUNDED_SCOPE":
        issues.append("fabricated_scope")
    elif code in _RELATION_CODES and not refusal_expected:
        issues.append("relation_missing")
    elif code == "DUPLICATE_CONCEPT_ID":
        issues.append("duplicate_concept_id")
    elif code == "INVALID_FACTOR" and "bucket_as_rollup" not in issues:
        issues.append("invalid_factor")
    return list(dict.fromkeys(issues))


def final_category(record):
    """최종 결과 하나. 정답이어도 인자가 틀리면 wrong_arguments다."""
    if record.get("measurement") == INVALID:
        return "invalid_measurement"
    if E.NO_TEMPLATE_LABEL in (record.get("expected_macros") or []):
        return "unsupported_correct" if record.get("correct") else "unsupported_incorrect"
    if record.get("correct"):
        return "wrong_arguments" if record.get("arg_mismatches") else "correct"
    if record.get("timeout"):
        return "other:timeout"
    status = record.get("status") or ""
    detail = record.get("error") or ""
    if status == "INVALID_SUBTYPE":
        issues = initial_issues(record)
        if "correct_factor_plus_spurious_concept" in issues:
            return "correct_factor_plus_spurious_concept"
        if "taxi_type_as_concept" in issues or any(word in detail for word in _TAXI_WORDS):
            return "taxi_type_as_concept"
        return "invalid_subtype"
    if status == "INVALID_FACTOR":
        rollup_unit = any(f"'{unit}'" in detail for unit in _TIME_UNITS)
        return "bucket_as_rollup" if "rollup" in detail and rollup_unit else "invalid_factor"
    if status == "UNKNOWN_FACTOR":
        return ("relation_attribute_as_factor"
                if any(key in detail for key in _CONCEPT_ATTRIBUTES) else "invalid_factor")
    if status == "INVALID_FACTOR_COMBINATION":
        factors = record.get("factors_after_repair") or record.get("factors") or {}
        if "bucket" in factors and "rollup" not in factors:
            return "missing_rollup"
        if "rollup" in factors and "bucket" not in factors:
            return "rollup_without_bucket"
        return "other:invalid_factor_combination"
    if status in _VALUELESS_CODES:
        return "valueless_location"
    if status == "UNGROUNDED_SCOPE":
        return "fabricated_scope"
    if status in _RELATION_CODES:
        return "relation_missing"
    if status == "DUPLICATE_CONCEPT_ID":
        return "duplicate_concept_id"
    if status in E.REFUSAL_CODES:
        return "refused_supported"
    return f"other:{status.lower() or 'unknown'}"


#: corpus item이 record에 넘겨주는 정보.
_CORPUS_KEYS = ("intent_id", "paraphrase_id", "original_question_id", "cohorts",
                "paraphrase_note", "census_source", "census_aliases")


def observe(item, *, arm, variant, repetition, position, pair_index,
            reset, client, composer, context=None):
    """새 모델 상태에서 관측 하나를 만든다. 매번 새 dict를 돌려준다."""
    base = {
        "protocol": PROTOCOL,
        **dict(context or {}),
        "id": item["id"],
        "question": item["question"],
        "repeat_index": repetition,
        "pair_index": pair_index,
        "arm": arm,
        "variant": variant.name,
        "prompt_sha256": variant.sha256,
        "repair_contract_sha256": variant.repair_sha256,
        "execution_order": position,
        **{key: item[key] for key in _CORPUS_KEYS if key in item},
        "expected_tool_args": dict(item.get("expected_tool_args") or {}),
    }
    outcome = reset.reset()
    base.update(
        reset_attempted=outcome.attempted,
        reset_succeeded=outcome.succeeded,
        reset_duration_ms=outcome.duration_ms,
        reset_detail=outcome.detail,
        loaded_models_after_reset=list(outcome.loaded_after),
    )
    if not outcome.succeeded:
        # 오염된 상태에서 부르지 않는다. 결과가 있어도 비교할 수 없다.
        return {**base, "measurement": INVALID, "invalid_reason": "reset_failed",
                "correct": None, "status": "RESET_FAILED", "llm_calls": [],
                "raw_text": "", "planner_calls": 0,
                "category": "invalid_measurement",
                "final_category": "invalid_measurement", "initial_issues": [],
                "strict_correct": None}

    recorder = RecordingClient(client)
    planner = FixedPromptPlanner(client=recorder, variant=variant)
    plans = RecordingComposer(composer)
    record = E.evaluate_once(
        planner, plans, item, attempt=repetition, variant=variant.name,
        system_prompt_chars=len(variant.prompt),
    )
    record.update(base)
    record["expected_macros"] = list(item.get("expected_macros") or [])

    record["final_tool"], record["final_tool_args"] = None, None
    record["tool_call_error"] = None
    if plans.last_plan is not None:
        try:
            record["final_tool"], record["final_tool_args"] = final_tool_call(plans.last_plan)
        except Exception as error:  # noqa: BLE001 - 측정 결과로 남긴다
            record["tool_call_error"] = f"{type(error).__name__}: {error}"
    if record["final_tool_args"] is None:
        record["arg_mismatches"] = None
    else:
        record["arg_mismatches"] = tool_arg_mismatches(
            record["expected_tool_args"], record["final_tool_args"],
            tool_defaults(record["final_tool"]),
        )

    calls = [dict(call) for call in recorder.calls]
    initial = [call for call in calls if call["phase"] == "initial"]
    record["llm_calls"] = calls
    record["planner_calls"] = len(calls)
    # 원문은 오류 경로와 무관하게 client가 받은 것을 쓴다.
    record["raw_text"] = (initial[-1].get("content") or "").strip() if initial else ""
    record["repair_raw_texts"] = [
        (call.get("content") or "") for call in calls if call["phase"] == "repair"
    ]

    first_load = calls[0].get("load_duration_ms") if calls else None
    record["cold_load_ms"] = first_load
    if first_load is None:
        record["cold_load_verified"] = None
    else:
        record["cold_load_verified"] = first_load >= COLD_LOAD_MIN_MS

    if record["cold_load_verified"] is False:
        record["measurement"] = INVALID
        record["invalid_reason"] = "reset_not_effective"
    else:
        record["measurement"] = VALID
        record["invalid_reason"] = None
    record["canonical_grounding"] = canonical_grounding(record["raw_text"])
    record["category"] = error_category(record)
    payload = _initial_payload(record) or {}
    factors = payload.get("factors") if isinstance(payload.get("factors"), dict) else {}
    record["initial_taxi_type_factor"] = factors.get("taxi_type")
    record["initial_issues"] = initial_issues(record)
    record["final_category"] = final_category(record)
    # 기존 correct는 macro/operator/검증만 본다. strict는 최종 Tool 인자까지 본다.
    record["strict_correct"] = (
        None if record["measurement"] == INVALID
        else record["final_category"] in ("correct", "unsupported_correct")
    )
    return record


# -- 실행 ------------------------------------------------------------------


def select_queries(spec, files=QUERY_FILES):
    """``@boundary``는 경계 평가셋 전체, 나머지는 id 접두어다."""
    pools = {path: list(load_queries(BASE_DIR / path)) for path in files}
    chosen, seen = [], set()
    for token in [part.strip() for part in spec.split(",") if part.strip()]:
        if token == "@boundary":
            matched = pools["stub_query_boundary.yaml"]
        else:
            matched = [item for items in pools.values() for item in items
                       if item["id"].startswith(token)]
            if not matched:
                raise KeyError(f"질의를 찾지 못했다: {token}")
            matched = matched[:1]
        for item in matched:
            if item["id"] not in seen:
                seen.add(item["id"])
                chosen.append(item)
    return chosen


def expected_keys(query_ids, repetitions, arm_labels):
    return {(qid, rep, arm) for qid in query_ids
            for rep in range(1, repetitions + 1) for arm in arm_labels}


def run_protocol(items, arms, *, repetitions, reset, client, composer,
                 run_dir, meta, max_invalid=DEFAULT_MAX_INVALID, log=print,
                 min_arms=2):
    """관측을 모두 실행한다. 이미 있는 결과는 덮어쓰지 않는다.

    ``arms``는 ``[(arm_label, PromptVariant), ...]`` 두 개다. 같은 변형을
    두 번 넣으면 자기 자신과의 비교가 된다. 비교가 아니라 실패 집계(census)는
    ``min_arms=1``로 한 arm만 돌린다.
    """
    labels = [label for label, _ in arms]
    if len(arms) < min_arms or len(set(labels)) != len(labels):
        raise ValueError(f"arm은 이름이 서로 다른 {min_arms}개 이상이어야 한다")
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=False)
    _write_exclusive(run_dir / "meta.json", meta)

    invalid = 0
    written = 0
    status = {"completed": False, "observations": 0, "invalid": 0,
              "aborted_reason": None}
    path = run_dir / "observations.jsonl"
    started = time.perf_counter()
    try:
        # "x": 같은 파일에 두 프로세스가 쓰는 사고를 막는다.
        with open(path, "x", encoding="utf-8") as handle:
            for repetition in range(1, repetitions + 1):
                for index, item in enumerate(items):
                    for position, (label, variant) in enumerate(
                        arm_order(index, repetition, arms), start=1,
                    ):
                        record = observe(
                            item, arm=label, variant=variant,
                            repetition=repetition, position=position,
                            pair_index=index, reset=reset, client=client,
                            composer=composer,
                            context={"run_id": meta.get("run_id"),
                                     "model": meta.get("model")},
                        )
                        handle.write(json.dumps(record, ensure_ascii=False,
                                                default=str) + "\n")
                        handle.flush()
                        os.fsync(handle.fileno())
                        written += 1
                        if record["measurement"] == INVALID:
                            invalid += 1
                            log(f"[무효] {item['id']} rep{repetition} {label}: "
                                f"{record['invalid_reason']} ({record.get('reset_detail')})")
                            if invalid > max_invalid:
                                raise BenchmarkAborted(
                                    f"무효 관측 {invalid}건이 허용치 {max_invalid}를 넘었다"
                                )
                    log(f"[rep {repetition}] {item['id']:<40} "
                        f"{time.perf_counter() - started:7.0f}s")
        status["completed"] = True
    except BenchmarkAborted as error:
        status["aborted_reason"] = str(error)
        raise
    finally:
        status["observations"] = written
        status["invalid"] = invalid
        _write_exclusive(run_dir / "run_status.json", status)
    return path


def _write_exclusive(path, data):
    with open(path, "x", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


# -- 불러오기와 무결성 --------------------------------------------------------


@dataclasses.dataclass
class IntegrityReport:
    truncated_lines: list
    duplicate_keys: list
    missing_keys: list
    unexpected_keys: list
    invalid_observations: int
    completed: bool

    @property
    def clean(self):
        return not (self.truncated_lines or self.duplicate_keys
                    or self.missing_keys or self.unexpected_keys) and self.completed


def load_run(run_dir):
    """기록과 무결성 보고를 함께 돌려준다. 문제를 조용히 넘기지 않는다."""
    run_dir = Path(run_dir)
    meta = json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))
    status_path = run_dir / "run_status.json"
    status = (json.loads(status_path.read_text(encoding="utf-8"))
              if status_path.exists() else {"completed": False})
    rows, truncated, seen, duplicates = [], [], set(), []
    raw = (run_dir / "observations.jsonl").read_bytes().split(b"\n")
    for number, line in enumerate(raw, start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            truncated.append(number)
            continue
        key = (record.get("id"), record.get("repeat_index"), record.get("arm"))
        if key in seen:
            duplicates.append(key)
            continue
        seen.add(key)
        rows.append(record)
    want = expected_keys(meta["query_ids"], meta["repetitions"],
                         [arm["label"] for arm in meta["arms"]])
    report = IntegrityReport(
        truncated_lines=truncated,
        duplicate_keys=sorted(duplicates, key=str),
        missing_keys=sorted(want - seen, key=str),
        unexpected_keys=sorted(seen - want, key=str),
        invalid_observations=sum(1 for row in rows if row.get("measurement") != VALID),
        completed=bool(status.get("completed")),
    )
    return meta, rows, report


# -- 비교 ------------------------------------------------------------------

#: 출력 안에서만 쓰는 이름과 질문에서 옮긴 표현. 의미가 아니라 표기다.
#: 단, id의 역할은 "중복되지 않는다"는 제약 하나이므로 그 사실은 남긴다.
_LABEL_KEYS = ("id", "text")


def canonical_grounding(raw_text):
    """표기 차이만 걷어 낸 grounding. 읽을 수 없으면 ``None``."""
    if not raw_text:
        return None
    try:
        payload = parse_planner_json(raw_text)
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(payload, dict):
        return None
    result = dict(payload)
    concepts = payload.get("concepts")
    if isinstance(concepts, list):
        ids = [item.get("id") for item in concepts if isinstance(item, dict)]
        stripped = [
            {key: value for key, value in item.items() if key not in _LABEL_KEYS}
            if isinstance(item, dict) else item
            for item in concepts
        ]
        result["concepts"] = sorted(
            stripped, key=lambda item: json.dumps(item, sort_keys=True,
                                                  ensure_ascii=False),
        )
        result["_ids_unique"] = len(ids) == len(set(ids))
    return json.dumps(result, sort_keys=True, ensure_ascii=False)


def behavior_key(record):
    return (record.get("status"), tuple(record.get("macros") or ()),
            tuple(record.get("operators") or ()), bool(record.get("validated")),
            bool(record.get("correct")))


_TAXI_WORDS = ("taxi_type", "private", "corporate")


def error_category(record):
    if record.get("measurement") == INVALID:
        return "invalid_measurement"
    if record.get("correct"):
        return "correct"
    if record.get("timeout"):
        return "timeout"
    status = record.get("status") or ""
    detail = record.get("error") or ""
    if status == "INVALID_SUBTYPE":
        if any(word in detail for word in _TAXI_WORDS):
            return "taxi_type_as_concept"
        return "invalid_subtype"
    table = {
        "INVALID_FACTOR": "invalid_factor",
        "INVALID_FACTOR_COMBINATION": "invalid_factor_combination",
        "VALUELESS_CONCEPT": "valueless_concept",
        "MISSING_CONCEPT_VALUE": "valueless_concept",
        "UNGROUNDED_SCOPE": "fabricated_scope",
        "AMBIGUOUS_LOCATION_RELATION": "relation_failure",
        "MISSING_RELATION_QUALIFIER": "relation_failure",
        "DUPLICATE_CONCEPT_ID": "duplicate_concept_id",
        "PLANNER_CALL_FAILED": "transport",
        "CLIENT_ERROR": "transport",
        "OK": "wrong_plan",
        "VALIDATION_FAILED": "wrong_plan",
    }
    if status in table:
        return table[status]
    if status in E.REFUSAL_CODES:
        return "unsupported"
    return status.lower() or "unknown"


def mcnemar_exact(b, c):
    """불일치 쌍 b, c에 대한 양측 exact McNemar p값."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def pairs(rows, arm_a, arm_b):
    """두 arm 모두 유효한 관측만 짝으로 만든다."""
    grouped = defaultdict(dict)
    for row in rows:
        grouped[(row["id"], row["repeat_index"])][row["arm"]] = row
    result = []
    for key in sorted(grouped):
        group = grouped[key]
        if arm_a in group and arm_b in group and all(
            group[arm].get("measurement") == VALID for arm in (arm_a, arm_b)
        ):
            result.append((key, group[arm_a], group[arm_b]))
    return result


def summarize(meta, rows, report, pair=None):
    labels = [arm["label"] for arm in meta["arms"]]
    arm_a, arm_b = pair or labels[:2]
    labels = [arm_a, arm_b]
    matched = pairs(rows, arm_a, arm_b)
    valid = [row for row in rows if row.get("measurement") == VALID]

    table = Counter((bool(a["correct"]), bool(b["correct"])) for _, a, b in matched)
    only_a, only_b = table[(True, False)], table[(False, True)]

    agreement = {
        "raw_equal": sum(1 for _, a, b in matched
                         if a.get("raw_text") == b.get("raw_text")),
        "semantic_equal": sum(1 for _, a, b in matched if _semantic_equal(a, b)),
        "behavior_equal": sum(1 for _, a, b in matched
                              if behavior_key(a) == behavior_key(b)),
        "correct_equal": sum(1 for _, a, b in matched
                             if bool(a["correct"]) == bool(b["correct"])),
        "category_equal": sum(1 for _, a, b in matched
                              if a.get("category") == b.get("category")),
    }

    per_query = defaultdict(lambda: {arm_a: 0, arm_b: 0, "pairs": 0})
    for (qid, _), a, b in matched:
        per_query[qid]["pairs"] += 1
        per_query[qid][arm_a] += bool(a["correct"])
        per_query[qid][arm_b] += bool(b["correct"])
    a_wins = sum(1 for q in per_query.values() if q[arm_a] > q[arm_b])
    b_wins = sum(1 for q in per_query.values() if q[arm_b] > q[arm_a])

    by_arm = {}
    for label in labels:
        mine = [row for row in valid if row["arm"] == label]
        by_arm[label] = {
            "variant": next((row["variant"] for row in mine), None),
            "valid": len(mine),
            "correct": sum(1 for row in mine if row.get("correct")),
            "categories": dict(Counter(row["category"] for row in mine
                                       if row["category"] != "correct")),
            "factor_as_concept": sum(1 for row in mine
                                     if row["category"] == "taxi_type_as_concept"),
            "timeouts": sum(1 for row in mine if row.get("timeout")),
            "repairs_attempted": sum(1 for row in mine if row.get("repair_attempted")),
            "repairs_succeeded": sum(1 for row in mine if row.get("repair_succeeded")),
            "cold_initial_planner_ms_p50": _percentile(
                [row["initial_planner_ms"] for row in mine if row.get("initial_planner_ms")],
                0.5),
        }

    n = len(matched)
    return {
        "protocol": meta.get("protocol"),
        "run_id": meta.get("run_id"),
        "arms": [arm for label in labels for arm in meta["arms"] if arm["label"] == label],
        "integrity": dataclasses.asdict(report) | {"clean": report.clean},
        "observations": len(rows),
        "valid_observations": len(valid),
        "pairs": n,
        "paired": {
            "both_correct": table[(True, True)],
            f"{arm_a}_only": only_a,
            f"{arm_b}_only": only_b,
            "both_wrong": table[(False, False)],
            "discordant": only_a + only_b,
            "discordance_rate": _rate(only_a + only_b, n),
            "mcnemar_exact_p": round(mcnemar_exact(only_a, only_b), 4),
        },
        "agreement": {key: {"count": value, "rate": _rate(value, n)}
                      for key, value in agreement.items()},
        "per_query": {qid: dict(value) for qid, value in sorted(per_query.items())},
        "query_level": {
            f"{arm_a}_better": a_wins,
            f"{arm_b}_better": b_wins,
            "tied": len(per_query) - a_wins - b_wins,
            "sign_test_p": round(mcnemar_exact(a_wins, b_wins), 4),
        },
        "by_arm": by_arm,
        "note": ("같은 질문을 반복한 관측이라 독립 표본이 아니다. 관측 단위 McNemar는 "
                 "참고값이고, 질문 단위 부호 검정과 자기 일치율을 함께 본다. "
                 "latency는 매 관측 cold load를 포함하므로 운영 지표가 아니다."),
    }


def _semantic_equal(a, b):
    left, right = a.get("canonical_grounding"), b.get("canonical_grounding")
    if left is None or right is None:
        # 읽을 수 없는 응답끼리는 원문이 같을 때만 같다고 본다.
        return left is None and right is None and a.get("raw_text") == b.get("raw_text")
    return left == right


def _rate(count, total):
    return round(count / total, 4) if total else None


def _percentile(values, q):
    if not values:
        return None
    values = sorted(values)
    return values[min(int(round(q * (len(values) - 1))), len(values) - 1)]


# -- paraphrase corpus 분석 -------------------------------------------------
#
# paraphrase는 같은 의도를 다른 표현으로 물은 것이라 서로 독립이 아니다.
# 그래서 두 층으로 센다. paraphrase 층은 관측 수를 그대로 보여 주고, 판정은
# intent 층에서 한다. 한 intent 안에서 어느 쪽이 더 많이 맞혔는지를 세고,
# 부호 검정도 intent 수로 한다.


#: 분석 시점의 채점 규칙. 관측 파일에는 관측 당시의 채점이 들어 있다.
#: tool_args_schema_defaults_v1: schema 기본값과 같은 인자는 생략한 것과 같게 본다.
#: v2: 택시 유형 개념 node 중 factor는 맞게 적은 경우를
#:     correct_factor_plus_spurious_concept로 따로 센다. strict 판정은 같다.
#: v3: factor factorial용 단계별 지표(첫 응답·최종의 factor 실패)를 더한다.
#:     strict 판정은 같다.
SCORING_VERSION = "tool_args_schema_defaults_v3"


def rescore(record):
    """관측 원본에서 채점만 다시 한다. 관측 파일은 바꾸지 않는다."""
    record = dict(record)
    if record.get("measurement") != VALID:
        return record
    if record.get("final_tool_args") is not None:
        record["arg_mismatches"] = tool_arg_mismatches(
            record.get("expected_tool_args") or {}, record["final_tool_args"],
            tool_defaults(record.get("final_tool")),
        )
    record["initial_issues"] = initial_issues(record)
    record["final_category"] = final_category(record)
    record["strict_correct"] = record["final_category"] in ("correct", "unsupported_correct")
    return record


def _in_cohort(row, cohort):
    return cohort is None or cohort in (row.get("cohorts") or [])


def analyze_intents(rows, arm_a, arm_b, *, cohort=None, metric="strict_correct",
                    rescored=True):
    rows = [rescore(row) for row in rows] if rescored else list(rows)
    matched = [
        (key, a, b) for key, a, b in pairs(rows, arm_a, arm_b)
        if _in_cohort(a, cohort)
    ]
    ok = lambda row: bool(row.get(metric))  # noqa: E731
    table = Counter((ok(a), ok(b)) for _, a, b in matched)

    per_intent = defaultdict(lambda: {arm_a: 0, arm_b: 0, "paraphrases": 0})
    for _, a, b in matched:
        entry = per_intent[a["intent_id"]]
        entry["paraphrases"] += 1
        entry[arm_a] += ok(a)
        entry[arm_b] += ok(b)
    a_better = sorted(i for i, v in per_intent.items() if v[arm_a] > v[arm_b])
    b_better = sorted(i for i, v in per_intent.items() if v[arm_b] > v[arm_a])

    def arm_stats(label, side):
        mine = [pair[side] for pair in matched]
        taxi = [row for row in mine
                if (row.get("expected_tool_args") or {}).get("taxi_type")]
        control = [row for row in mine
                   if "taxi_type" in (row.get("expected_tool_args") or {})
                   and row["expected_tool_args"]["taxi_type"] is None]
        repairs = Counter(str(row.get("repair_kind")) for row in mine
                          if row.get("repair_attempted"))
        return {
            "observations": len(mine),
            metric: sum(ok(row) for row in mine),
            "legacy_correct": sum(bool(row.get("correct")) for row in mine),
            "final_categories": dict(Counter(row["final_category"] for row in mine)),
            "initial_issues": dict(Counter(issue for row in mine
                                           for issue in row.get("initial_issues") or [])),
            "repairs_attempted": sum(repairs.values()),
            "repairs_succeeded": sum(1 for row in mine if row.get("repair_succeeded")),
            "repairs_by_kind": dict(repairs),
            "planner_calls": sum(row.get("planner_calls") or 0 for row in mine),
            "taxi_type_rows": len(taxi),
            "taxi_type_factor_initial": sum(1 for row in taxi
                                            if row.get("initial_taxi_type_factor")),
            "taxi_type_factor_correct_initial": sum(
                1 for row in taxi
                if row.get("initial_taxi_type_factor") == row["expected_tool_args"]["taxi_type"]),
            "taxi_type_as_concept_initial": sum(
                1 for row in taxi if "taxi_type_as_concept" in (row.get("initial_issues") or [])),
            "spurious_concept_with_correct_factor": sum(
                1 for row in taxi
                if "correct_factor_plus_spurious_concept" in (row.get("initial_issues") or [])),
            # 택시 유형을 말하지 않은 질문에 조건이나 개념을 지어냈는가.
            "control_rows": len(control),
            "control_taxi_factor_added": sum(
                1 for row in control
                if row.get("initial_taxi_type_factor") not in (None, "all")),
            "control_taxi_concept_added": sum(
                1 for row in control
                if "taxi_type_as_concept" in (row.get("initial_issues") or [])),
        }

    return {
        "cohort": cohort,
        "arms": [arm_a, arm_b],
        "metric": metric,
        "scoring": SCORING_VERSION if rescored else "as_observed",
        "paraphrase_level": {
            "pairs": len(matched),
            "both": table[(True, True)],
            f"{arm_a}_only": table[(True, False)],
            f"{arm_b}_only": table[(False, True)],
            "neither": table[(False, False)],
        },
        "intent_level": {
            "intents": len(per_intent),
            f"{arm_a}_better": a_better,
            f"{arm_b}_better": b_better,
            "tied": sorted(set(per_intent) - set(a_better) - set(b_better)),
            "sign_test_p": round(mcnemar_exact(len(a_better), len(b_better)), 4),
        },
        "per_intent": {key: dict(value) for key, value in sorted(per_intent.items())},
        "by_arm": {arm_a: arm_stats(arm_a, 1), arm_b: arm_stats(arm_b, 2)},
        "per_paraphrase": [
            {
                "paraphrase_id": a["paraphrase_id"],
                "intent_id": a["intent_id"],
                "question": a["question"],
                **{label: {
                    "strict": row.get("strict_correct"),
                    "final": row["final_category"],
                    "initial_issues": row.get("initial_issues") or [],
                    "taxi_type_factor": row.get("initial_taxi_type_factor"),
                    "repair": row.get("repair_kind") if row.get("repair_attempted") else None,
                    "arg_mismatches": row.get("arg_mismatches"),
                } for label, row in ((arm_a, a), (arm_b, b))},
            }
            for _, a, b in matched
        ],
        "note": ("paraphrase는 같은 intent 안에서 독립이 아니다. 판정은 intent 층의 "
                 "승패로 하고, paraphrase 층 수치는 관측 규모를 보여 줄 뿐이다."),
    }


# -- factor 단계 지표와 2x2 factorial --------------------------------------
#
# 50fae72는 system prompt의 의미 절(S)과 factor 재질의의 의미(R)를 한 번에
# 바꿨다. 두 축을 따로 켠 네 arm으로 각 변경의 효과를 가른다. 격리 상태에서는
# 같은 system prompt + 같은 질문이면 첫 응답이 글자까지 같으므로, S가 같은 두
# arm(F00/F01, F10/F11)은 첫 응답을 공유하고 재질의만 다르다. 그래서 R의 효과는
# 같은 재질의 대상 위에서 깨끗하게 잰다.

FACTORIAL_ARMS = {"F00": (0, 0), "F10": (1, 0), "F01": (0, 1), "F11": (1, 1)}

#: grounding factor 이름과 Tool 인자 이름이 같은 것. 첫 응답을 기대 인자와 바로
#: 비교할 수 있다.
_FACTOR_ARG_KEYS = paraphrase_corpus.FACTOR_KEYS + ("taxi_type",)


def _factor_error(key, got):
    if key == "rollup":
        return "missing_rollup" if got is None else "wrong_rollup_value"
    if key == "dimension":
        return "missing_dimension" if got is None else "invalid_dimension"
    if key == "aggregation":
        return "wrong_aggregation"
    if key == "taxi_type":
        return "taxi_type_missing" if got is None else "wrong_tool_args"
    return "wrong_tool_args"


def initial_factor_errors(record):
    """재질의 전 첫 grounding의 factor가 기대와 어떻게 다른가."""
    payload = _initial_payload(record) or {}
    if payload.get("unsupported"):
        return []
    factors = payload.get("factors") if isinstance(payload.get("factors"), dict) else {}
    expected = {key: value for key, value in (record.get("expected_tool_args") or {}).items()
                if key in _FACTOR_ARG_KEYS}
    tool = record.get("final_tool") or _expected_tool(record)
    errors = [issue for issue in record.get("initial_issues") or []
              if issue in ("missing_rollup", "bucket_as_rollup", "rollup_without_bucket")]
    for key, _, got in tool_arg_mismatches(expected, factors, tool_defaults(tool)):
        errors.append(_factor_error(key, got))
    return list(dict.fromkeys(errors))


def final_factor_errors(record):
    """최종 결과의 factor 실패. 정답이면 비어 있다."""
    if record.get("strict_correct"):
        return []
    errors = []
    category = record.get("final_category")
    if category in ("missing_rollup", "bucket_as_rollup", "rollup_without_bucket"):
        errors.append(category)
    detail = record.get("error") or ""
    if record.get("status") in ("INVALID_FACTOR", "INVALID_PARAM_VALUE") and "dimension" in detail:
        errors.append("invalid_dimension")
    for key, _, got in record.get("arg_mismatches") or []:
        errors.append(_factor_error(key, got))
    return list(dict.fromkeys(errors))


def _expected_tool(record):
    from geoflow.operator_registry import get_operator
    operators = record.get("expected_operators") or []
    return get_operator(operators[-1]).tool_name if operators else None


def _factor_repair(row):
    return row.get("repair_attempted") and row.get("repair_kind") == "factor_completion"


def factorial_stats(rows, arm):
    mine = [row for row in rows if row["arm"] == arm]
    repair = [row for row in mine if _factor_repair(row)]
    return {
        "observations": len(mine),
        "strict_correct": sum(bool(row["strict_correct"]) for row in mine),
        # 재질의 없이 처음부터 맞힌 것. system 의미 절의 효과는 여기서 본다.
        "correct_without_repair": sum(1 for row in mine
                                      if row["strict_correct"] and not row.get("repair_attempted")),
        "initial_factor_clean": sum(1 for row in mine if not row["initial_factor_errors"]),
        "initial_factor_errors": dict(Counter(e for row in mine
                                              for e in row["initial_factor_errors"])),
        "final_factor_errors": dict(Counter(e for row in mine
                                            for e in row["final_factor_errors"])),
        "final_categories": dict(Counter(row["final_category"] for row in mine)),
        "factor_repair_needed": len(repair),
        "factor_repair_succeeded": sum(bool(row.get("repair_succeeded")) for row in repair),
        "factor_repair_final_correct": sum(bool(row["strict_correct"]) for row in repair),
        "factor_repair_errors": dict(Counter(str(row.get("repair_error")) for row in repair
                                             if not row.get("repair_succeeded"))),
        "llm_calls": sum(row.get("planner_calls") or 0 for row in mine),
    }


def _shared_initial(rows, arm_a, arm_b):
    """두 arm의 첫 응답이 같은 관측 수. S가 같으면 전부 같아야 한다."""
    matched = pairs(rows, arm_a, arm_b)
    return sum(1 for _, a, b in matched if a.get("raw_text") == b.get("raw_text")), len(matched)


def _repair_subset(rows, base, treated):
    """base arm에서 factor 재질의가 필요했던 paraphrase 위에서 두 arm을 비교한다.

    S가 같아 첫 응답이 같으면 재질의 대상도 같다. 재질의가 필요 없어진 경우는
    이 비교에 넣지 않는다. 그것은 R이 아니라 S의 효과다.
    """
    needed = {row["id"] for row in rows if row["arm"] == base and _factor_repair(row)}
    result = {"needed": len(needed)}
    for arm in (base, treated):
        mine = [row for row in rows if row["arm"] == arm and row["id"] in needed]
        result[arm] = {
            "attempted": sum(1 for row in mine if _factor_repair(row)),
            "succeeded": sum(bool(row.get("repair_succeeded")) for row in mine),
            "final_correct": sum(bool(row["strict_correct"]) for row in mine),
            "repair_errors": dict(Counter(str(row.get("repair_error")) for row in mine
                                          if _factor_repair(row) and not row.get("repair_succeeded"))),
        }
    return result


def _with_factor_errors(rows, rescored=True):
    rows = [rescore(row) for row in rows] if rescored else [dict(row) for row in rows]
    for row in rows:
        row["initial_factor_errors"] = initial_factor_errors(row)
        row["final_factor_errors"] = final_factor_errors(row)
    return rows


def analyze_factorial(rows, arms=None, rescored=True):
    arms = arms or FACTORIAL_ARMS
    rows = _with_factor_errors(rows, rescored)
    by_level = {level: name for name, level in arms.items()}
    f00, f10, f01, f11 = (by_level[(0, 0)], by_level[(1, 0)], by_level[(0, 1)],
                          by_level[(1, 1)])
    stats = {name: factorial_stats(rows, name) for name in (f00, f10, f01, f11)}

    def effect(metric):
        value = {name: stats[name][metric] for name in stats}
        return {
            "S_given_R0": value[f10] - value[f00],
            "S_given_R1": value[f11] - value[f01],
            "R_given_S0": value[f01] - value[f00],
            "R_given_S1": value[f11] - value[f10],
            "interaction": (value[f11] - value[f10]) - (value[f01] - value[f00]),
        }

    return {
        "scoring": SCORING_VERSION if rescored else "as_observed",
        "arms": {name: list(level) for name, level in arms.items()},
        "stats": stats,
        "effects": {metric: effect(metric) for metric in
                    ("strict_correct", "correct_without_repair", "initial_factor_clean",
                     "factor_repair_needed", "llm_calls")},
        "shared_initial": {f"{f00}/{f01}": _shared_initial(rows, f00, f01),
                           f"{f10}/{f11}": _shared_initial(rows, f10, f11)},
        "repair_subset": {"S0": _repair_subset(rows, f00, f01),
                          "S1": _repair_subset(rows, f10, f11)},
        "intent_level": {
            f"{a}:{b}": analyze_intents(rows, a, b, rescored=False)["intent_level"]
            for a, b in ((f00, f10), (f00, f01), (f10, f11), (f01, f11), (f00, f11))
        },
        "note": ("paraphrase는 같은 intent 안에서 독립이 아니다. 효과 크기는 관측 수 "
                 "차이로 보여 주고, 판정은 intent 층 승패와 단계별 지표로 한다."),
    }


# -- 후보 선택과 holdout 판정 (결과 전에 고정) --------------------------------
#
# development 결과를 보기 전에 규칙을 코드로 정한다. 같은 정확도라면 LLM이 보는
# 의미 설명이 적은 계약을 고른다. 크기 순서가 곧 단순함 순서다.
#   F00 (11336 + 473) < F01 (11336 + 540) < F10 (12595 + 473) < F11 (12595 + 540)

def contract_size(name):
    variant = build_variant(name)
    return len(variant.prompt) + len(render_factor_repair(variant))


def _repair_rate(stats):
    needed = stats["factor_repair_needed"]
    return 1.0 if needed == 0 else stats["factor_repair_succeeded"] / needed


def candidate_ranking(result):
    """좋은 순서로 arm 이름. 앞 기준이 같을 때만 다음 기준을 본다.

    1. strict 정답 (많을수록)
    2. 첫 응답의 factor 실패 수 (적을수록)
    3. factor 재질의 성공률 (높을수록)
    4. LLM 호출 수 (적을수록)
    5. LLM이 보는 계약 크기 (작을수록) — 단순한 계약 우선
    """
    def key(name):
        stats = result["stats"][name]
        return (-stats["strict_correct"],
                sum(stats["initial_factor_errors"].values()),
                -_repair_rate(stats),
                stats["llm_calls"],
                contract_size(name))
    return sorted(result["stats"], key=key)


def holdout_arms(ranking):
    """holdout에서 비교할 두 arm. 후보와 현재 production(F11)을 맞붙인다.

    후보가 F11이면 다음 순위와 맞붙여, development 우세가 새 의도에서도 유지되는지 본다.
    """
    candidate = ranking[0]
    if candidate == "F11":
        return candidate, ranking[1]
    return candidate, "F11"


#: 후보별 결정. §15.
DECISIONS = {
    "F11": "A: 50fae72 유지",
    "F10": "B: 재질의 의미 제거",
    "F01": "C: system 의미 절 제거, 재질의 때만 의미 제공",
    "F00": "D: 50fae72의 LLM 노출 되돌림 (FactorSpec.meaning은 유지)",
}
KEEP_PRODUCTION = "E: current production 유지, 효과 불확실로 기록"


def holdout_summary(rows, candidate, other, rescored=True):
    """holdout 두 arm의 단계별 지표와 intent 층 승패."""
    rows = _with_factor_errors(rows, rescored)
    return {
        "scoring": SCORING_VERSION if rescored else "as_observed",
        "arms": [candidate, other],
        "stats": {name: factorial_stats(rows, name) for name in (candidate, other)},
        "intent_level": analyze_intents(rows, candidate, other, rescored=False)["intent_level"],
    }


def holdout_decision(summary, candidate, other):
    """holdout 결과로 최종 결정.

    후보를 채택하려면 셋 모두를 만족해야 한다. strict가 비교 arm 이상, intent 층에서
    진 intent가 이긴 intent보다 많지 않음, 최종 factor 실패가 늘지 않음.
    후보가 F11이면 "채택"은 현재 상태 유지(A)이고, 못 미치면 E다. 어느 쪽이든
    production은 그대로다.
    """
    mine, theirs = summary["stats"][candidate], summary["stats"][other]
    level = summary["intent_level"]
    holds = (mine["strict_correct"] >= theirs["strict_correct"]
             and len(level[f"{candidate}_better"]) >= len(level[f"{other}_better"])
             and sum(mine["final_factor_errors"].values())
             <= sum(theirs["final_factor_errors"].values()))
    return DECISIONS[candidate] if holds else KEEP_PRODUCTION


def print_factorial_report(result, out=sys.stdout):
    w = lambda text="": print(text, file=out)  # noqa: E731
    names = list(result["stats"])
    w(f"== 2x2 factorial  채점={result['scoring']} ==")
    keys = ("observations", "strict_correct", "correct_without_repair", "initial_factor_clean",
            "factor_repair_needed", "factor_repair_succeeded", "factor_repair_final_correct",
            "llm_calls")
    w(f"  {'':<30}" + "".join(f"{n:>8}" for n in names))
    for key in keys:
        w(f"  {key:<30}" + "".join(f"{result['stats'][n][key]:>8}" for n in names))
    for key in ("initial_factor_errors", "final_factor_errors", "factor_repair_errors"):
        w(f"  {key}:")
        for n in names:
            w(f"      {n}: {result['stats'][n][key]}")
    w("  효과 (관측 수 차이):")
    for metric, values in result["effects"].items():
        w(f"      {metric:<24} " + "  ".join(f"{k}={v:+d}" for k, v in values.items()))
    w(f"  첫 응답 공유: {result['shared_initial']}")
    w(f"  재질의 대상 위 비교: {result['repair_subset']}")
    for pair, level in result["intent_level"].items():
        a, b = pair.split(":")
        w(f"  intent {pair}: {a} 우세 {level[f'{a}_better']}, {b} 우세 {level[f'{b}_better']}, "
          f"같음 {len(level['tied'])}, p={level['sign_test_p']}")


def print_intent_report(result, out=sys.stdout):
    a, b = result["arms"]
    w = lambda text="": print(text, file=out)  # noqa: E731
    p, i = result["paraphrase_level"], result["intent_level"]
    w(f"== {a} vs {b}  cohort={result['cohort'] or '전체'}  기준={result['metric']} "
      f"채점={result['scoring']} ==")
    w(f"  paraphrase 층: 짝 {p['pairs']} | both {p['both']} | {a}만 {p[f'{a}_only']} | "
      f"{b}만 {p[f'{b}_only']} | 둘 다 틀림 {p['neither']}")
    w(f"  intent 층: {i['intents']}개 중 {a} 우세 {len(i[f'{a}_better'])} "
      f"{i[f'{a}_better']}, {b} 우세 {len(i[f'{b}_better'])} {i[f'{b}_better']}, "
      f"같음 {len(i['tied'])}, 부호검정 p={i['sign_test_p']}")
    for intent, value in result["per_intent"].items():
        flag = " *" if value[a] != value[b] else ""
        w(f"    {intent:<38} {a} {value[a]}/{value['paraphrases']}  "
          f"{b} {value[b]}/{value['paraphrases']}{flag}")
    for label in (a, b):
        stats = result["by_arm"][label]
        w(f"  [{label}] strict {stats[result['metric']]}/{stats['observations']} "
          f"(기존 채점 {stats['legacy_correct']}), 재질의 {stats['repairs_attempted']}회 "
          f"성공 {stats['repairs_succeeded']} {stats['repairs_by_kind']}, "
          f"LLM 호출 {stats['planner_calls']}")
        w(f"      최종: {stats['final_categories']}")
        w(f"      첫 grounding 문제: {stats['initial_issues']}")
        if stats["taxi_type_rows"]:
            w(f"      taxi_type 질의 {stats['taxi_type_rows']}개: factor 맞게 적음 "
              f"{stats['taxi_type_factor_correct_initial']}, 개념 node "
              f"{stats['taxi_type_as_concept_initial']} (그중 factor도 맞게 적은 것 "
              f"{stats['spurious_concept_with_correct_factor']})")
        if stats["control_rows"]:
            w(f"      택시 유형이 없는 대조 질의 {stats['control_rows']}개: factor 지어냄 "
              f"{stats['control_taxi_factor_added']}, 개념 지어냄 "
              f"{stats['control_taxi_concept_added']}")


# -- 출력 ------------------------------------------------------------------


def print_summary(summary, out=sys.stdout):
    a, b = [arm["label"] for arm in summary["arms"]]
    va, vb = [arm["variant"] for arm in summary["arms"]]
    w = lambda text="": print(text, file=out)  # noqa: E731
    integrity = summary["integrity"]
    w(f"run {summary['run_id']}  protocol={summary['protocol']}  "
      f"arms {a}={va} / {b}={vb}")
    w(f"관측 {summary['observations']} (유효 {summary['valid_observations']}), "
      f"짝 {summary['pairs']}, 무결성 clean={integrity['clean']}")
    for key in ("truncated_lines", "duplicate_keys", "missing_keys", "unexpected_keys"):
        if integrity[key]:
            w(f"  !! {key}: {integrity[key][:5]}")
    p = summary["paired"]
    w("\n== paired outcome ==")
    w(f"  both correct {p['both_correct']} | {a} only {p[f'{a}_only']} | "
      f"{b} only {p[f'{b}_only']} | both wrong {p['both_wrong']}")
    w(f"  불일치 {p['discordant']} ({p['discordance_rate']}), "
      f"exact McNemar p={p['mcnemar_exact_p']}")
    w("\n== 일치율 (짝 기준) ==")
    for key, value in summary["agreement"].items():
        w(f"  {key:<15} {value['count']:>4}  {value['rate']}")
    w("\n== 질문별 정답 ==")
    for qid, value in summary["per_query"].items():
        flag = " *" if value[a] != value[b] else ""
        w(f"  {qid:<40} {a} {value[a]}/{value['pairs']}  "
          f"{b} {value[b]}/{value['pairs']}{flag}")
    q = summary["query_level"]
    w(f"  질문 단위: {a} 우세 {q[f'{a}_better']}, {b} 우세 {q[f'{b}_better']}, "
      f"같음 {q['tied']}, 부호검정 p={q['sign_test_p']}")
    w("\n== arm별 ==")
    for label, value in summary["by_arm"].items():
        w(f"  {label} ({value['variant']}): 정답 {value['correct']}/{value['valid']}, "
          f"factor_as_concept {value['factor_as_concept']}, timeout {value['timeouts']}, "
          f"재질의 {value['repairs_attempted']}/{value['repairs_succeeded']}성공")
        w(f"      실패: {value['categories']}")


def print_floor(summaries, out=sys.stdout):
    print("run                                     arms              짝  불일치율  "
          "행동불일치  의미불일치  원문불일치", file=out)
    for summary in summaries:
        arms = "/".join(arm["variant"] for arm in summary["arms"])
        agreement = summary["agreement"]
        miss = lambda key: (None if agreement[key]["rate"] is None  # noqa: E731
                            else round(1 - agreement[key]["rate"], 4))
        print(f"{summary['run_id']:<40}{arms:<18}{summary['pairs']:>4}  "
              f"{summary['paired']['discordance_rate']!s:<9} "
              f"{miss('behavior_equal')!s:<11} {miss('semantic_equal')!s:<11} "
              f"{miss('raw_equal')!s}", file=out)


# -- CLI -------------------------------------------------------------------


def _git_state():
    def git(*args):
        return subprocess.run(["git", *args], cwd=BASE_DIR, capture_output=True,
                              text=True).stdout.strip()
    return {
        "commit": git("rev-parse", "HEAD"),
        "dirty_paths": git("status", "--porcelain", "--", "geoflow", "prompts",
                           "schemas", "geoflow_macros", "evaluate_planner.py",
                           "evaluate_prompt_ab.py").splitlines(),
    }


def _server_info(host, model):
    version = httpx.get(f"{host}/api/version", timeout=5.0).json().get("version")
    digest = None
    for item in httpx.get(f"{host}/api/tags", timeout=5.0).json().get("models", []):
        if item.get("name") == model:
            digest = item.get("digest")
    if digest is None:
        raise BenchmarkAborted(f"설치된 모델에 {model}이 없다")
    return version, digest


def arm_labels(names):
    """변형 이름이 서로 다르면 그대로 쓰고, 같으면(자기 비교) A, B, ...로 붙인다."""
    if len(set(names)) == len(names):
        return list(names)
    return [chr(ord("A") + index) for index in range(len(names))]


def cmd_run(args):
    variants = [build_variant(name) for name in args.arms.split(",")]
    if len(variants) < 2:
        raise SystemExit("--arms에는 변형을 둘 이상 쉼표로 적는다 (같은 이름 두 번이면 자기 비교)")
    labels = arm_labels([variant.name for variant in variants])
    corpus = None
    if args.corpus:
        # 쉼표로 여러 corpus를 합칠 수 있다. id가 겹치면 합치지 않는다.
        paths = [Path(part) for part in args.corpus.split(",") if part]
        cohorts = args.cohorts.split(",") if args.cohorts else None
        items = []
        for corpus_path in paths:
            items += paraphrase_corpus.load_corpus_items(corpus_path, cohorts=cohorts)
        if len({item["id"] for item in items}) != len(items):
            raise SystemExit("여러 corpus에 같은 paraphrase id가 있다")
        if args.factor_subset:
            items = paraphrase_corpus.factor_subset(items)
        corpus = {
            "path": ",".join(str(path) for path in paths),
            "sha256": hashlib.sha256(b"".join(path.read_bytes() for path in paths)).hexdigest(),
            "files": [{"path": str(path),
                       "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                      for path in paths],
            "cohorts": cohorts,
            "factor_subset": bool(args.factor_subset),
            "intents": sorted({item["intent_id"] for item in items}),
        }
    elif args.queries:
        items = select_queries(args.queries)
    else:
        raise SystemExit("--queries 또는 --corpus가 필요하다")
    version, digest = _server_info(args.host, args.model)
    run_id = f"{E._now_local().strftime('%Y%m%d_%H%M%S')}_{args.label}"
    meta = {
        "protocol": PROTOCOL,
        "run_id": run_id,
        "created_at": E._now_local().isoformat(),
        "git": _git_state(),
        "host": args.host,
        "model": args.model,
        "model_digest": digest,
        "ollama_version": version,
        "options": {"temperature": 0},
        "chat_timeout": args.chat_timeout,
        "model_reset": {
            "method": "POST /api/generate {model, keep_alive: 0} 후 /api/ps에서 모델이 "
                      "사라졌는지 확인, 관측 첫 호출의 load_duration으로 cold load 확인",
            "cold_load_min_ms": COLD_LOAD_MIN_MS,
            "max_invalid": args.max_invalid,
        },
        "order_rule": "arm 목록을 (query_index + repetition) % arm 수만큼 돌린 순서",
        "arms": [{"label": label, "variant": variant.name, "note": variant.note,
                  "prompt_sha256": variant.sha256, "prompt_chars": len(variant.prompt),
                  "repair_contract_sha256": variant.repair_sha256}
                 for label, variant in zip(labels, variants)],
        "corpus": corpus,
        "query_ids": [item["id"] for item in items],
        "repetitions": args.repetitions,
        "expected_observations": len(items) * args.repetitions * len(variants),
    }
    client = OllamaClient(args.host, args.model, {"temperature": 0},
                          chat_timeout=args.chat_timeout)
    reset = OllamaStateReset(args.host, args.model)
    composer = MacroComposer(MacroLibrary.from_directory())
    run_dir = Path(args.out) / run_id
    print(f"[setup] {run_id}: {len(items)} queries x {args.repetitions} x {len(variants)} = "
          f"{meta['expected_observations']} observations", flush=True)
    for arm in meta["arms"]:
        print(f"[prompt] {arm['label']}={arm['variant']} "
              f"sha256={arm['prompt_sha256'][:16]} chars={arm['prompt_chars']} "
              f"repair={arm['repair_contract_sha256'][:16]}", flush=True)
    run_protocol(items, list(zip(labels, variants)), repetitions=args.repetitions,
                 reset=reset, client=client, composer=composer, run_dir=run_dir,
                 meta=meta, max_invalid=args.max_invalid,
                 log=lambda text: print(text, flush=True))
    if len(variants) == 2 and corpus is None:
        cmd_analyze(argparse.Namespace(run_dir=run_dir, allow_incomplete=False))
    else:
        print(f"분석: python evaluate_prompt_ab.py analyze-corpus {run_dir} "
              f"--pairs {labels[0]}:{labels[1]}", flush=True)
    print("PROMPT AB DONE", flush=True)


#: census가 한 번에 모으는 평가셋. 사람이 검토한 것 전체다.
CENSUS_QUERY_FILES = ("stub_query.yaml", "stub_query_boundary.yaml")
CENSUS_CORPORA = ("evaluation/paraphrases.yaml", "evaluation/paraphrases_holdout.yaml",
                  "evaluation/paraphrases_factor_holdout.yaml")


def census_items(query_files=CENSUS_QUERY_FILES, corpora=CENSUS_CORPORA, base=BASE_DIR):
    """여러 평가셋을 합쳐 같은 질문은 한 번만 남긴다.

    같은 질문이 여러 곳에 있으면 corpus 쪽 item을 쓴다. intent와 Tool 인자 라벨이
    있기 때문이다. 버린 쪽은 ``census_aliases``로 남긴다. 라벨이 서로 다르면
    어느 쪽으로 채점할지 정할 수 없으므로 멈춘다.
    """
    sources = []
    for path in corpora:
        for item in paraphrase_corpus.load_corpus_items(Path(base) / path):
            sources.append((path, item))
    for path in query_files:
        for item in load_queries(Path(base) / path):
            sources.append((path, {**item, "intent_id": item["id"]}))
    chosen, order = {}, []
    for path, item in sources:
        question = item["question"].strip()
        alias = {"source": path, "id": item["id"], "intent_id": item["intent_id"]}
        if question not in chosen:
            chosen[question] = {**item, "census_source": path, "census_aliases": []}
            order.append(question)
            continue
        kept = chosen[question]
        for key in ("expected_macros", "expected_operators"):
            if list(kept.get(key) or []) != list(item.get(key) or []):
                raise ValueError(f"같은 질문의 라벨이 다르다: {question!r} ({key})")
        kept["census_aliases"].append(alias)
    items = [chosen[question] for question in order]
    if len({item["id"] for item in items}) != len(items):
        raise ValueError("census item id가 겹친다")
    return items


def cmd_census(args):
    """current production 한 arm으로 사람이 검토한 평가셋 전체를 한 번씩 잰다."""
    variant = build_variant("PRODUCTION")
    items = census_items()
    version, digest = _server_info(args.host, args.model)
    run_id = f"{E._now_local().strftime('%Y%m%d_%H%M%S')}_{args.label}"
    files = [*CENSUS_CORPORA, *CENSUS_QUERY_FILES]
    meta = {
        "protocol": PROTOCOL,
        "purpose": "failure census. variant 비교가 아니다",
        "run_id": run_id,
        "created_at": E._now_local().isoformat(),
        "git": _git_state(),
        "host": args.host,
        "model": args.model,
        "model_digest": digest,
        "ollama_version": version,
        "options": {"temperature": 0},
        "chat_timeout": args.chat_timeout,
        "model_reset": {
            "method": "POST /api/generate {model, keep_alive: 0} 후 /api/ps에서 모델이 "
                      "사라졌는지 확인, 관측 첫 호출의 load_duration으로 cold load 확인",
            "cold_load_min_ms": COLD_LOAD_MIN_MS,
            "max_invalid": args.max_invalid,
        },
        "order_rule": "census_items 순서. 한 arm, 한 번",
        "arms": [{"label": "A", "variant": variant.name, "note": variant.note,
                  "prompt_sha256": variant.sha256, "prompt_chars": len(variant.prompt),
                  "repair_contract_sha256": variant.repair_sha256}],
        "corpus": {
            "files": [{"path": path,
                       "sha256": hashlib.sha256((BASE_DIR / path).read_bytes()).hexdigest()}
                      for path in files],
            "unique_questions": len(items),
            "source_items": len(items) + sum(len(item["census_aliases"]) for item in items),
        },
        "query_ids": [item["id"] for item in items],
        "repetitions": 1,
        "expected_observations": len(items),
    }
    client = OllamaClient(args.host, args.model, {"temperature": 0},
                          chat_timeout=args.chat_timeout)
    reset = OllamaStateReset(args.host, args.model)
    composer = MacroComposer(MacroLibrary.from_directory())
    run_dir = Path(args.out) / run_id
    print(f"[setup] {run_id}: {len(items)} unique questions x 1 x PRODUCTION "
          f"sha256={variant.sha256[:16]} repair={variant.repair_sha256[:16]}", flush=True)
    run_protocol(items, [("A", variant)], repetitions=1, reset=reset, client=client,
                 composer=composer, run_dir=run_dir, meta=meta,
                 max_invalid=args.max_invalid, log=lambda text: print(text, flush=True),
                 min_arms=1)
    print(f"CENSUS DONE {run_dir}", flush=True)


def cmd_analyze_factorial(args):
    meta, rows, report = load_run(args.run_dir)
    if not report.clean and not args.allow_incomplete:
        raise SystemExit(f"무결성 문제로 분석하지 않는다: {dataclasses.asdict(report)}")
    result = analyze_factorial(rows, rescored=not args.as_observed)
    print_factorial_report(result)
    path = Path(args.run_dir) / "factorial_summary.json"
    if path.exists():
        path = Path(args.run_dir) / f"factorial_summary.{int(time.time())}.json"
    _write_exclusive(path, {"run_id": meta.get("run_id"),
                            "integrity": dataclasses.asdict(report) | {"clean": report.clean},
                            "result": result})
    return result


def cmd_analyze_corpus(args):
    meta, rows, report = load_run(args.run_dir)
    if not report.clean and not args.allow_incomplete:
        raise SystemExit(f"무결성 문제로 분석하지 않는다: {dataclasses.asdict(report)}")
    cohorts = args.cohorts.split(",") if args.cohorts else [None]
    results = []
    for pair in args.pairs.split(","):
        arm_a, arm_b = pair.split(":")
        for cohort in cohorts:
            result = analyze_intents(rows, arm_a, arm_b, cohort=cohort or None,
                                     rescored=not args.as_observed)
            print_intent_report(result)
            print()
            results.append(result)
    path = Path(args.run_dir) / "intent_summary.json"
    if path.exists():
        path = Path(args.run_dir) / f"intent_summary.{int(time.time())}.json"
    _write_exclusive(path, {"run_id": meta.get("run_id"),
                            "integrity": dataclasses.asdict(report) | {"clean": report.clean},
                            "results": results})
    return results


def cmd_analyze(args):
    meta, rows, report = load_run(args.run_dir)
    if not report.clean and not args.allow_incomplete:
        raise SystemExit(
            f"무결성 문제로 분석하지 않는다: {dataclasses.asdict(report)}. "
            "알고서 보려면 --allow-incomplete"
        )
    summary = summarize(meta, rows, report)
    path = Path(args.run_dir) / "summary.json"
    if path.exists():
        path = Path(args.run_dir) / f"summary.{int(time.time())}.json"
    _write_exclusive(path, summary)
    print_summary(summary)
    return summary


def cmd_floor(args):
    summaries = []
    for run_dir in args.run_dirs:
        meta, rows, report = load_run(run_dir)
        if not report.clean:
            raise SystemExit(f"{run_dir}: 무결성 문제가 있어 비교하지 않는다")
        summaries.append(summarize(meta, rows, report))
    print_floor(summaries)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run")
    run.add_argument("--arms", required=True)
    run.add_argument("--queries")
    run.add_argument("--corpus", help="paraphrase corpus. 주면 --queries 대신 쓴다")
    run.add_argument("--cohorts", help="corpus에서 고를 cohort, 쉼표로")
    run.add_argument("--factor-subset", action="store_true",
                     help="factor 관련 Tool 인자를 기대하는 intent만 쓴다")
    run.add_argument("--repetitions", type=int, default=5)
    run.add_argument("--label", required=True)
    run.add_argument("--host", default=DEFAULT_HOST)
    run.add_argument("--model", default=DEFAULT_MODEL)
    run.add_argument("--chat-timeout", type=float, default=300)
    run.add_argument("--max-invalid", type=int, default=DEFAULT_MAX_INVALID)
    run.add_argument("--out", default=str(RESULT_DIR))
    run.set_defaults(func=cmd_run)
    analyze = sub.add_parser("analyze")
    analyze.add_argument("run_dir")
    analyze.add_argument("--allow-incomplete", action="store_true")
    analyze.set_defaults(func=cmd_analyze)
    corpus = sub.add_parser("analyze-corpus")
    corpus.add_argument("run_dir")
    corpus.add_argument("--pairs", required=True, help="예: C:D_PRE,D_PRE:T0")
    corpus.add_argument("--cohorts", help="cohort별로 나눠 본다, 쉼표로")
    corpus.add_argument("--allow-incomplete", action="store_true")
    corpus.add_argument("--as-observed", action="store_true",
                        help="다시 채점하지 않고 관측 당시의 채점을 쓴다")
    corpus.set_defaults(func=cmd_analyze_corpus)
    factorial = sub.add_parser("analyze-factorial")
    factorial.add_argument("run_dir")
    factorial.add_argument("--allow-incomplete", action="store_true")
    factorial.add_argument("--as-observed", action="store_true")
    factorial.set_defaults(func=cmd_analyze_factorial)
    census = sub.add_parser("census")
    census.add_argument("--label", required=True)
    census.add_argument("--host", default=DEFAULT_HOST)
    census.add_argument("--model", default=DEFAULT_MODEL)
    census.add_argument("--chat-timeout", type=float, default=300)
    census.add_argument("--max-invalid", type=int, default=DEFAULT_MAX_INVALID)
    census.add_argument("--out", default=str(RESULT_DIR))
    census.set_defaults(func=cmd_census)
    floor = sub.add_parser("floor")
    floor.add_argument("run_dirs", nargs="+")
    floor.set_defaults(func=cmd_floor)
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
