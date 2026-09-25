# -*- coding: utf-8 -*-
"""V0: 실행 직전의 계획이 질문과 맞는지만 보는 reject-only 의미 검증. 평가 전용.

H0 grounding → 기존 재질의 → 합성·operator·G1~G6·컴파일이 끝난 **최종 계획**에서
결정적으로 의미 서명(SemanticSignature)을 만든다. 검증 LLM은 질문과 그 서명만 보고
consistent / inconsistent / uncertain을 답한다.

    consistent   → H0 계획 그대로 실행
    inconsistent → 계획을 버리고 안전하게 거부 (Tool 호출 0)
    uncertain    → H0 계획 그대로 실행
    검증 실패    → H0 계획 그대로 실행 (fallback)

검증기는 개념·factor·Tool 인자·재질의 어느 것도 만들지 않는다. 그래서 V0의 최종
결과는 H0 계획 그대로이거나 계획 없음, 둘 중 하나다.

서명의 사람이 읽는 이름은 답변 formatter(geoflow.answer)의 이름표와 Tool schema의
기본값을 그대로 쓴다. 이름표가 없는 측정값 두 개만 여기서 이름을 붙인다.
"""

import json
from dataclasses import dataclass, field

import paraphrase_corpus as P
from geoflow import answer as ANSWER
from geoflow.types import FunctionalRole

# -- 서명 ------------------------------------------------------------------

#: 이름표가 geoflow.answer에 없는 측정값. 답변은 건수 문장을 따로 만들기 때문이다.
_COUNT_MEASURE_LABEL = {"passage_count": "통행량(통과 건수)", "trip_count": "실차 구간 건수"}
_SCOPE_ROLE = {"scope": "location", "scope_pickup": "pickup_location",
               "scope_dropoff": "dropoff_location"}
#: 검증기가 plan_field로 가리킬 수 있는 이름. 서명 문장의 [] 안 이름과 같다.
FIELDS = ("measure", "location", "pickup_location", "dropoff_location", "vicinity",
          "taxi_type", "date", "time", "dimension", "order", "limit",
          "bucket", "aggregation", "rollup")


@dataclass
class SemanticSignature:
    """최종 계획의 실행 의미. Tool 이름과 내부 key는 드러내지 않는다."""

    tool: str
    measure: str
    event: str | None
    locations: dict = field(default_factory=dict)  # field → {"name", "region"}
    vicinity: bool = False
    args: dict = field(default_factory=dict)       # Tool 인자 (scope 제외)
    defaults: dict = field(default_factory=dict)   # Tool schema 기본값

    def to_dict(self):
        return {"tool": self.tool, "measure": self.measure, "event": self.event,
                "locations": self.locations, "vicinity": self.vicinity,
                "args": self.args, "defaults": self.defaults}


def signature_of(plan):
    """GeoFlowPlan에서 결정적으로 만든다. 최종 Tool 호출과 그 장소 출처를 읽는다."""
    tool, args = P.final_tool_call(plan)
    concepts = {concept.id: concept for concept in plan.concepts}
    measure = next(c for c in plan.concepts if c.role == FunctionalRole.MEASURE)
    event = next((c.subtype for c in plan.concepts
                  if getattr(c.concept, "value", c.concept) == "EVENT"), None)
    places = {}
    vicinity = False
    for item in plan.transformations:
        if getattr(item.operator, "value", item.operator) != "RESOLVE_PLACE_SCOPE":
            continue
        vicinity = vicinity or bool(item.params.get("include_vicinity"))
        reference = item.inputs.get("place_name")
        node = concepts.get(getattr(reference, "node_id", None))
        if node is not None and isinstance(node.value, dict):
            places[node.value.get("name")] = {"name": node.value.get("name"),
                                              "region": node.value.get("region") or ""}
    locations = {}
    rest = {}
    for key, value in args.items():
        if key in _SCOPE_ROLE:
            name = value[len("@place:"):] if isinstance(value, str) and \
                value.startswith("@place:") else str(value)
            locations[_SCOPE_ROLE[key]] = places.get(name, {"name": name, "region": ""})
        elif key != "metric":
            rest[key] = value
    return SemanticSignature(tool=tool, measure=measure.subtype, event=event,
                             locations=locations, vicinity=vicinity, args=rest,
                             defaults=dict(P.tool_defaults(tool)))


# -- 설명형 렌더링 ----------------------------------------------------------


def _date_text(value):
    if value in ANSWER._DATE_LABEL:
        return ANSWER._DATE_LABEL[value]
    text = str(value)
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:]}"
    if len(text) == 17 and text[8] == "-":
        return f"{_date_text(text[:8])} ~ {_date_text(text[9:])}"
    return text


def _time_text(value):
    text = str(value)
    if len(text) == 13 and text[6] == "-":
        return f"{text[:2]}:{text[2:4]} ~ {text[7:9]}:{text[9:11]}"
    return text


def _reducer(value):
    return ANSWER._AGGREGATION_LABEL.get(value, str(value))


def _place_text(place):
    region = f"{place['region']} " if place.get("region") else ""
    return f"{region}{place['name']}"


def render(signature):
    """검증기가 읽는 문장. 같은 서명은 늘 같은 문장이 된다."""
    args, defaults = signature.args, signature.defaults
    measure = ANSWER._METRIC_LABEL.get(signature.measure) or _COUNT_MEASURE_LABEL.get(
        signature.measure, signature.measure)
    lines = [f"[measure] 구하는 값: {measure}"]
    labels = {"location": "조회 범위", "pickup_location": "승차(출발) 위치",
              "dropoff_location": "하차(도착) 위치"}
    for key in ("location", "pickup_location", "dropoff_location"):
        if key in signature.locations:
            lines.append(f"[{key}] {labels[key]}: {_place_text(signature.locations[key])}")
    if not signature.locations:
        lines.append("[location] 조회 범위: 지정 없음(전체 지역)")
    if signature.vicinity:
        lines.append("[vicinity] 장소 주변 영역까지 포함한다")

    def value(key, text=lambda v: str(v), none="조건 없음"):
        if key in args:
            return text(args[key])
        if key in defaults:
            return f"{text(defaults[key])} (질문이 정하지 않아 쓰는 기본값)"
        return none

    if "taxi_type" in args or "taxi_type" in defaults:
        lines.append("[taxi_type] 택시 유형: "
                     + value("taxi_type", lambda v: f"{ANSWER._TAXI_TYPE_LABEL.get(v, v)} 택시"))
    lines.append(f"[date] 기간: {value('date', _date_text, '지정 없음(전체 기간)')}")
    lines.append(f"[time] 시간대: {value('time', _time_text, '지정 없음(하루 전체)')}")
    if "dimension" in args:
        lines.append(f"[dimension] 결과를 "
                     f"{ANSWER._DIMENSION_LABEL.get(args['dimension'], args['dimension'])}로 "
                     "나눈 목록으로 보여 준다")
    else:
        lines.append("[dimension] 그룹으로 나누지 않고 값 하나를 구한다")
    if "order" in args:
        lines.append(f"[order] 값 순서: {ANSWER._ORDER_LABEL.get(args['order'], args['order'])}")
    if "limit" in args:
        lines.append(f"[limit] 보여 줄 개수: {args['limit']}")
    if "bucket" in args:
        unit = ANSWER._BUCKET_LABEL.get(args["bucket"], args["bucket"])
        lines.append(f"[bucket] 기간을 {unit} 구간으로 나눈다")
        lines.append(f"[aggregation] 각 구간 안의 원시 값을 모으는 방식: "
                     f"{value('aggregation', _reducer)}")
        lines.append(f"[rollup] 구간별 결과들을 최종 값 하나로 합치는 방식: "
                     f"{value('rollup', _reducer)}")
    elif "aggregation" in args or "aggregation" in defaults:
        lines.append(f"[aggregation] 원시 값을 모으는 방식: {value('aggregation', _reducer)}")
    else:
        lines.append("[aggregation] 해당하는 건수를 센다")
    return "\n".join(lines)


# -- 검증기 호출 ------------------------------------------------------------

CONSISTENT = "consistent"
INCONSISTENT = "inconsistent"
UNCERTAIN = "uncertain"
VERDICTS = (CONSISTENT, INCONSISTENT, UNCERTAIN)
KINDS = ("missing_constraint", "extra_constraint", "wrong_value", "wrong_relation",
         "wrong_aggregation_stage", "unsupported_collapse")
ISSUE_KEYS = ("kind", "question_evidence", "plan_field")
IGNORABLE_KEYS = frozenset({"reason", "reasoning", "explanation", "note", "notes", "thought"})

# 결과 이름. 관측 기록과 분석이 쓴다.
NOT_CALLED = "not_called"
FALLBACK = "fallback"
VERIFIER_CALL_FAILED = "VERIFIER_CALL_FAILED"
VERIFIER_INVALID_JSON = "VERIFIER_INVALID_JSON"
VERIFIER_INVALID_OUTPUT = "VERIFIER_INVALID_OUTPUT"
EVIDENCE_NOT_IN_QUESTION = "EVIDENCE_NOT_IN_QUESTION"

#: 결과를 보기 전에 고정한 정책. 명확한 불일치만 거부한다.
REJECTING_OUTCOMES = frozenset({INCONSISTENT})

#: 한 번 쓰고 고정한다. 예시·알려진 실패 질문·틀린 형태를 넣지 않는다.
SYSTEM_PROMPT = """너는 택시 데이터 분석 계획을 검토한다. 계획을 고치지 않는다. 계획이 질문과 맞는지만 판정한다.

입력은 사용자 질문과, 실행하려는 계획의 의미다. 계획의 각 항목은 [항목 이름]으로 시작한다.

다음을 확인한다.
- 질문에 있는 조건(구하는 값, 장소, 승차·하차 관계, 기간, 시간대, 택시 유형, 그룹, 순서, 개수, 집계 방식)이 계획에 같은 뜻으로 들어 있는가.
- 계획에 질문에 없는 조건이 더해지지 않았는가. 질문이 정하지 않아 기본값으로 둔 항목은 더해진 조건이 아니다.
- 구간을 나누는 계획이면, 구간 안의 집계와 구간별 결과를 합치는 최종 집계가 질문의 뜻과 같은가.
- 질문이 요구하는 답의 형태(비교, 목록, 여러 값)를 이 계획의 결과가 담을 수 있는가.

verdict:
- consistent: 질문과 계획이 맞다.
- inconsistent: 질문과 계획 사이에 분명한 불일치가 있다.
- uncertain: 분명하게 판단할 수 없다.

inconsistent이면 issues에 불일치를 하나 이상 적는다.
- kind: missing_constraint(질문의 조건이 계획에 없음) | extra_constraint(질문에 없는 조건이 계획에 있음) | wrong_value(같은 항목의 값이 다름) | wrong_relation(장소의 승차·하차 관계가 다름) | wrong_aggregation_stage(구간 안 집계와 최종 집계가 질문과 다름) | unsupported_collapse(질문이 요구하는 답의 형태를 계획의 결과가 담을 수 없음)
- question_evidence: 근거가 되는 질문의 일부를 한 글자도 바꾸지 않고 옮긴 문자열. extra_constraint일 때만 null로 둘 수 있다.
- plan_field: 해당하는 계획 항목 이름.

올바른 값을 제안하지 않는다. 출력은 JSON 객체 하나다.

    {"verdict": "<consistent|inconsistent|uncertain>", "issues": [{"kind": "<kind>", "question_evidence": "<질문의 일부 또는 null>", "plan_field": "<항목 이름>"}]}"""


def user_message(question, signature_text):
    return f"질문: {question}\n\n계획:\n{signature_text}"


class VerifierError(ValueError):
    def __init__(self, code, detail):
        super().__init__(detail)
        self.code = code
        self.detail = detail


def _field_name(value):
    """서명 문장이 항목을 [이름]으로 보여 주므로 괄호째 옮긴 것은 같은 이름으로 본다."""
    if isinstance(value, str) and len(value) > 2 and value[0] == "[" and value[-1] == "]" \
            and value[1:-1] in FIELDS:
        return value[1:-1]
    return value


def parse_verdict(payload, question):
    """검증기 출력을 확인한다. 어긋나면 VerifierError(→ fallback)."""
    if not isinstance(payload, dict):
        raise VerifierError(VERIFIER_INVALID_OUTPUT, "JSON 객체가 아니다")
    extra = sorted(set(payload) - {"verdict", "issues"} - IGNORABLE_KEYS)
    if extra:
        raise VerifierError(VERIFIER_INVALID_OUTPUT, f"모르는 key: {extra}")
    verdict = payload.get("verdict")
    if verdict not in VERDICTS:
        raise VerifierError(VERIFIER_INVALID_OUTPUT, f"verdict 값: {verdict!r}")
    issues = payload.get("issues")
    if verdict != INCONSISTENT:
        # 거부하지 않는 판정의 issues는 동작에 쓰지 않는다. 기록만 한다.
        return verdict, []
    if not isinstance(issues, list) or not issues:
        raise VerifierError(VERIFIER_INVALID_OUTPUT, "inconsistent인데 issues가 없다")
    checked = []
    for issue in issues:
        if not isinstance(issue, dict) or set(issue) != set(ISSUE_KEYS):
            raise VerifierError(VERIFIER_INVALID_OUTPUT, f"issue 형식: {issue!r}")
        if issue["kind"] not in KINDS:
            raise VerifierError(VERIFIER_INVALID_OUTPUT, f"kind 값: {issue['kind']!r}")
        issue = {**issue, "plan_field": _field_name(issue["plan_field"])}
        if issue["plan_field"] not in FIELDS:
            raise VerifierError(VERIFIER_INVALID_OUTPUT, f"plan_field 값: {issue['plan_field']!r}")
        evidence = issue["question_evidence"]
        if evidence is None:
            if issue["kind"] != "extra_constraint":
                raise VerifierError(EVIDENCE_NOT_IN_QUESTION,
                                    f"{issue['kind']}에는 질문 근거가 있어야 한다")
        elif not isinstance(evidence, str) or not evidence.strip() \
                or evidence.strip() not in question:
            raise VerifierError(EVIDENCE_NOT_IN_QUESTION, f"질문에 없는 근거: {evidence!r}")
        checked.append(dict(issue))
    return verdict, checked


def verify(chat, question, plan, *, parse_json, prompt=None):
    """검증 한 번. ``chat(messages) -> text``. 결과 dict를 돌려주고 예외를 내지 않는다."""
    signature = signature_of(plan)
    text = render(signature)
    result = {"outcome": FALLBACK, "verdict": None, "issues": [], "reason": None,
              "signature": signature.to_dict(), "signature_text": text, "raw_text": None}
    messages = [{"role": "system", "content": prompt if prompt is not None else SYSTEM_PROMPT},
                {"role": "user", "content": user_message(question, text)}]
    try:
        raw = chat(messages)
    except Exception as error:  # noqa: BLE001 - 검증기 실패는 fallback이다
        result.update(reason=VERIFIER_CALL_FAILED, detail=f"{type(error).__name__}: {error}")
        return result
    result["raw_text"] = raw
    try:
        payload = parse_json(raw or "")
    except Exception as error:  # noqa: BLE001
        result.update(reason=VERIFIER_INVALID_JSON, detail=str(error))
        return result
    try:
        verdict, issues = parse_verdict(payload, question)
    except VerifierError as error:
        result.update(reason=error.code, detail=error.detail)
        return result
    result.update(outcome=verdict, verdict=verdict, issues=issues)
    return result


def rejects(result):
    return bool(result) and result.get("outcome") in REJECTING_OUTCOMES


def message_content(body):
    message = (body.get("message") or {}) if isinstance(body, dict) else {}
    return message.get("content")


def dumps(result):
    return json.dumps(result, ensure_ascii=False, default=str)
