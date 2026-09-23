# -*- coding: utf-8 -*-
"""의미가 같은 질문 묶음(paraphrase corpus)을 읽고 검증한다.

정답 label은 부모 질의에서 물려받는다. paraphrase가 label을 따로 가질 수 없게
해서, 표현만 바뀌고 뜻은 그대로라는 전제가 파일 형식에서부터 지켜지게 한다.
"""

import functools
import re
import unicodedata
from pathlib import Path

import yaml

from geoflow.compiler import compile_plan
from geoflow.types import ValueRef
from query_loader import load_queries

BASE_DIR = Path(__file__).resolve().parent
CORPUS_FILE = BASE_DIR / "evaluation" / "paraphrases.yaml"
PARENT_FILES = ("stub_query_boundary.yaml", "stub_query.yaml")

LABEL_KEYS = ("expected_concepts", "expected_macros", "expected_operators")
COHORTS = frozenset({"taxi_type", "factor_stage", "relation"})
NONE_LABEL = "NONE"

_INTENT_KEYS = frozenset({
    "intent", "cohorts", "expected_tool_args", "must_include", "must_exclude",
    "od_roles", "golden", "paraphrases", "note",
})
#: label 관련 key가 없다. paraphrase마다 정답을 바꿀 수 없게 한다.
_PARAPHRASE_KEYS = frozenset({"id", "question", "note"})

#: 장소 이름 뒤나 앞에 붙는 승하차 표지. 방향을 바꾸는 paraphrase를 막는다.
_OD_MARKERS = {
    "pickup": (r"{p}\s*에서", r"{p}\s*출발", r"출발지가\s*{p}"),
    "dropoff": (r"{p}\s*에(?!서)", r"{p}\s*으로", r"{p}\s*도착", r"도착지가\s*{p}"),
}


class CorpusError(ValueError):
    """corpus가 전제를 어겼다. 문제를 모두 모아 한 번에 알린다."""

    def __init__(self, problems):
        self.problems = list(problems)
        super().__init__("paraphrase corpus 오류:\n  - " + "\n  - ".join(self.problems))


def load_parents(files=PARENT_FILES):
    parents = {}
    for name in files:
        for item in load_queries(BASE_DIR / name):
            parents[item["id"]] = item
    return parents


def load_corpus(path=CORPUS_FILE, parents=None):
    """corpus를 읽고 검증한 intent 목록을 돌려준다."""
    document = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    parents = load_parents() if parents is None else parents
    problems = validate(document, parents)
    if problems:
        raise CorpusError(problems)
    return document["intents"]


def corpus_items(intents, parents=None, cohorts=None):
    """측정용 item. 부모 label을 물려받고 corpus 정보를 붙인다.

    여러 cohort에 속한 intent도 한 번만 나온다.
    """
    parents = load_parents() if parents is None else parents
    wanted = None if cohorts is None else set(cohorts)
    items = []
    for intent in intents:
        if wanted is not None and not wanted & set(intent["cohorts"]):
            continue
        parent = parents[intent["intent"]]
        for paraphrase in intent["paraphrases"]:
            items.append({
                "id": paraphrase["id"],
                "question": paraphrase["question"],
                **{key: list(parent.get(key) or []) for key in LABEL_KEYS},
                "intent_id": intent["intent"],
                "paraphrase_id": paraphrase["id"],
                "original_question_id": parent["id"],
                "cohorts": list(intent["cohorts"]),
                "expected_tool_args": dict(intent.get("expected_tool_args") or {}),
                "paraphrase_note": paraphrase.get("note"),
            })
    return items


def normalize_question(text):
    """중복 검사용. 공백과 문장 부호만 걷어 낸다."""
    text = unicodedata.normalize("NFC", text)
    return "".join(ch for ch in text if not ch.isspace()
                   and not unicodedata.category(ch).startswith("P"))


def od_marker_problems(question, od_roles):
    problems = []
    for place, role in od_roles.items():
        if role not in _OD_MARKERS:
            problems.append(f"알 수 없는 od_role {role!r}")
            continue
        other = "dropoff" if role == "pickup" else "pickup"
        name = re.escape(place)
        mine = any(re.search(p.format(p=name), question) for p in _OD_MARKERS[role])
        theirs = any(re.search(p.format(p=name), question) for p in _OD_MARKERS[other])
        if not mine:
            problems.append(f"{place}에 {role} 표지가 없다")
        if theirs:
            problems.append(f"{place}에 {other} 표지가 붙었다")
    return problems


def validate(document, parents):
    problems = []
    if not isinstance(document, dict) or document.get("version") != 1:
        return ["최상위는 version: 1 을 가진 mapping이어야 한다"]
    intents = document.get("intents")
    if not isinstance(intents, list) or not intents:
        return ["intents가 비어 있다"]

    seen_intents, seen_ids, seen_questions = set(), set(), {}
    for intent in intents:
        name = intent.get("intent")
        where = f"intent {name}"
        unknown = set(intent) - _INTENT_KEYS
        if unknown:
            problems.append(f"{where}: 모르는 key {sorted(unknown)}")
        if name in seen_intents:
            problems.append(f"{where}: 중복된 intent")
        seen_intents.add(name)
        parent = parents.get(name)
        if parent is None:
            problems.append(f"{where}: 부모 질의가 없다")
            continue
        cohorts = intent.get("cohorts") or []
        if not cohorts or set(cohorts) - COHORTS:
            problems.append(f"{where}: cohorts는 {sorted(COHORTS)} 중에서 하나 이상")

        unsupported = NONE_LABEL in (parent.get("expected_macros") or [])
        golden = intent.get("golden")
        if unsupported:
            if golden != {"unsupported": True}:
                problems.append(f"{where}: 지원하지 않는 부모의 golden은 unsupported여야 한다")
            if intent.get("expected_tool_args"):
                problems.append(f"{where}: 지원하지 않는 질의에 기대 Tool 인자가 있다")
        elif not isinstance(golden, dict) or "concepts" not in golden:
            problems.append(f"{where}: golden grounding이 없다")

        paraphrases = intent.get("paraphrases") or []
        if not paraphrases:
            problems.append(f"{where}: paraphrase가 없다")
        prefix = name.split("_", 1)[0]
        originals = []
        for paraphrase in paraphrases:
            pid = paraphrase.get("id")
            here = f"{where} / {pid}"
            unknown = set(paraphrase) - _PARAPHRASE_KEYS
            if unknown:
                problems.append(f"{here}: paraphrase에는 {sorted(unknown)}를 둘 수 없다 "
                                "(label은 부모에서만 물려받는다)")
            if not pid or not re.fullmatch(rf"{re.escape(prefix)}_p\d+", pid):
                problems.append(f"{here}: id는 {prefix}_p<번호> 형식이어야 한다")
            if pid in seen_ids:
                problems.append(f"{here}: 중복된 paraphrase id")
            seen_ids.add(pid)
            question = (paraphrase.get("question") or "").strip()
            if not question:
                problems.append(f"{here}: 질문이 비어 있다")
                continue
            key = normalize_question(question)
            if key in seen_questions:
                problems.append(f"{here}: {seen_questions[key]}와 같은 질문이다")
            seen_questions[key] = pid
            if pid and pid.endswith("_p0"):
                originals.append(question)
            for group in intent.get("must_include") or []:
                if not any(word in question for word in group):
                    problems.append(f"{here}: {group} 중 어느 표현도 없다")
            for word in intent.get("must_exclude") or []:
                if word in question:
                    problems.append(f"{here}: 들어가면 안 되는 표현 {word!r}이 있다")
            for issue in od_marker_problems(question, intent.get("od_roles") or {}):
                problems.append(f"{here}: {issue}")
        if originals != [parent["question"]]:
            problems.append(f"{where}: p0은 부모 원문과 같아야 한다")
    return problems


# -- expected_tool_args 해석 ------------------------------------------------


def final_tool_call(plan):
    """측정 Tool 호출과 인자. scope 참조는 그것을 만든 장소 이름으로 푼다.

    기존 채점은 macro/operator/검증만 본다. 그래서 승하차가 뒤바뀌거나 factor
    값이 틀려도 정답으로 센다. 최종 Tool 인자를 보면 그것이 드러난다.
    """
    execution = compile_plan(plan)
    step = execution.steps[-1]
    producers = {output: item for item in plan.transformations for output in item.outputs}
    concepts = {concept.id: concept for concept in plan.concepts}

    def resolve(value):
        if not isinstance(value, ValueRef):
            return value
        producer = producers.get(value.node_id)
        operator = getattr(producer, "operator", None)
        if getattr(operator, "value", operator) == "RESOLVE_PLACE_SCOPE":
            reference = producer.inputs.get("place_name")
            node = concepts.get(getattr(reference, "node_id", None))
            place = node.value if node is not None else None
            if isinstance(place, dict):
                return f"@place:{place.get('name')}"
        return f"@node:{value.node_id}"

    return step.tool_name, {key: resolve(value) for key, value in step.arguments.items()}


#: Tool schema 위치. 기본값을 읽는다.
_SCHEMA_DIR = BASE_DIR / "schemas"


@functools.lru_cache(maxsize=None)
def tool_defaults(tool_name):
    """Tool 인자의 schema 기본값. ``$ref``로 공통 정의를 가리키면 그것을 따른다.

    기본값을 명시한 것과 생략한 것은 실행 의미가 같다. 예를 들어
    ``aggregation``의 기본값은 avg이므로 "평균"을 묻고 aggregation을 생략해도
    틀리지 않다.
    """
    common = yaml.safe_load((_SCHEMA_DIR / "_common.yaml").read_text(encoding="utf-8"))
    definitions = common.get("$defs") or common
    for entry in yaml.safe_load((_SCHEMA_DIR / "tims.yaml").read_text(encoding="utf-8")):
        function = entry["function"]
        if function["name"] != tool_name:
            continue
        defaults = {}
        for key, spec in function["parameters"]["properties"].items():
            ref = spec.get("$ref", "")
            base = definitions.get(ref.rsplit("/", 1)[-1], {}) if ref else {}
            default = spec.get("default", base.get("default"))
            if default is not None:
                defaults[key] = default
        return defaults
    return {}


def tool_arg_mismatches(expected, actual, defaults=None):
    """기대한 인자와 다른 것. None은 "없어야 한다"는 뜻이다.

    schema 기본값과 같은 값은 생략한 것과 같게 본다. 양쪽 모두에 적용한다.
    """
    defaults = defaults or {}

    def effective(key, value):
        return None if value is not None and value == defaults.get(key) else value

    mismatches = []
    for key, want in expected.items():
        got = actual.get(key)
        if effective(key, want) is None:
            if effective(key, got) is not None:
                mismatches.append([key, want, got])
        elif got != want:
            mismatches.append([key, want, got])
    return mismatches
