# -*- coding: utf-8 -*-
"""업체 100문항(assistant_univ_questions_100_v3.yaml)과 업체 정답(xlsx)으로 GeoFlow를 평가한다.

검증 층을 섞지 않는다.

- ``extract``: 업체 xlsx의 ``정답 Tool``·``비고``를 기계가 읽는 gold(``evaluation/vendor100/
  gold.yaml``)로 옮긴다. 질문 문장 대조, gold 호출의 schema 검사 등 **자료 충돌**을 따로 적는다.
  정답을 고치지 않는다.
- ``gold``(정답 grounding 기반 검증, LLM 없음): 업체 정답 호출에서 grounding을 결정적으로
  역산해 planner 자리에 넣고 composer → validator → compiler → mock 실행 → 답변을 돌린다.
  실제 Tool 호출을 업체 정답과 비교한다. "질문의 뜻이 정확히 주어졌을 때 GeoFlow가 업체 계약대로
  호출하는가"를 본다. 역산은 평가 도구이며 제품 경로에 없다.
- ``llm``(실제 LLM 포함 전체 실행): production 기본 설정(flat, condition_check 끔, mock + legacy,
  예시 검색 끔)으로 Ollama planner부터 끝까지 돌린다. 관측마다 모델을 내린다.
- ``compare``: 두 결과(변경 전·후)를 문항별로 비교한다.

``--code-root DIR``을 주면 그 디렉터리(예: 변경 전 커밋의 git worktree)의 geoflow 코드로 실행한다.
평가 규칙과 gold는 이 파일의 것을 쓴다.

mock 값은 고정값이므로 수치 정확도가 아니라 호출(Tool·인자·scope 출처)과 결과 종류, 반환값이
답변에 그대로 옮겨졌는지를 본다.

    python evaluate_vendor100.py extract
    python evaluate_vendor100.py gold --out evaluation/vendor100/results/gold_after.json
    python evaluate_vendor100.py --code-root /path/to/base-worktree gold --out .../gold_before.json
    python evaluate_vendor100.py llm --model qwen3:8b --out .../llm_after.json
    python evaluate_vendor100.py compare .../gold_before.json .../gold_after.json
"""

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent


def _code_root(argv):
    if "--code-root" in argv:
        return Path(argv[argv.index("--code-root") + 1]).resolve()
    return HERE


CODE_ROOT = _code_root(sys.argv)
if CODE_ROOT != HERE:
    # 평가 대상 코드를 바꾼다. 이 파일이 있는 저장소의 geoflow를 먼저 찾지 않게 한다.
    sys.path = [p for p in sys.path if Path(p or ".").resolve() != HERE]
sys.path.insert(0, str(CODE_ROOT))
os.environ.setdefault("ASSISTANT_TOOL_PROVIDER", "mock")

import yaml  # noqa: E402

VENDOR_DIR = HERE / "evaluation" / "vendor100"
GOLD_FILE = VENDOR_DIR / "gold.yaml"
XLSX_FILE = VENDOR_DIR / "질문 결과 및 정답 설명_100문항.xlsx"
QUESTIONS_FILE = HERE / "assistant_univ_questions_100_v3.yaml"
VARIANTS_FILE = VENDOR_DIR / "stated_variants.yaml"
REFERENCE_DATE = date(2026, 9, 25)
PROTOCOL = "vendor100_v1"
#: 평가 문항 파일(--gold). None이면 업체 gold.yaml.
GOLD_PATH = None

_CALL = re.compile(r"^\s*(\w+)\((.*)\)\s*$")
_BINDING = re.compile(r"^\$(\w+)\.scope$")


# -- extract -----------------------------------------------------------------------


def parse_calls(text):
    """``tool(k=v, ...)`` 줄들을 [{tool, args}]로. 값에 쉼표가 없다는 것은 extract가 검사한다."""
    calls = []
    for line in (text or "").strip().splitlines():
        if not line.strip() or line.strip() in ("INVALID_ARGUMENT", "UNSUPPORTED_COMBINATION"):
            continue
        match = _CALL.match(line)
        if match is None:
            raise ValueError(f"호출 형식이 아닙니다: {line!r}")
        args = {}
        for part in [item.strip() for item in match.group(2).split(",") if item.strip()]:
            key, _, value = part.partition("=")
            args[key.strip()] = _typed(value.strip())
        calls.append({"tool": match.group(1), "args": args})
    return calls


def _typed(value):
    if value in ("true", "false"):
        return value == "true"
    if re.fullmatch(r"\d+", value) and len(value) < 6:
        return int(value)
    return value


def cmd_extract(_args):
    import openpyxl
    from jsonschema import Draft202012Validator

    from build import build

    tools, _ = build()
    schemas = {tool["function"]["name"]: tool["function"]["parameters"] for tool in tools}
    sheet = openpyxl.load_workbook(XLSX_FILE).active
    # BaseLoader: YAML 1.1은 "010"을 8진수 8로 읽는다. id는 문자열로 읽는다.
    questions = {int(item["id"], 10): item["question"]
                 for item in yaml.load(QUESTIONS_FILE.read_text(encoding="utf-8"),
                                       Loader=yaml.BaseLoader)}
    items, conflicts = [], []
    for row in sheet.iter_rows(min_row=2, values_only=True):
        if row[1] is None:
            continue
        number, question, result, verdict, gold, note = (
            int(row[1]), row[2], row[3], row[4], row[5], row[6])
        calls = parse_calls(gold)
        if questions.get(number) != question:
            conflicts.append({"id": number, "kind": "question_text",
                              "detail": f"xlsx {question!r} ≠ yaml {questions.get(number)!r}"})
        for index, call in enumerate(calls):
            schema = schemas.get(call["tool"])
            if schema is None:
                conflicts.append({"id": number, "kind": "unknown_tool", "detail": call["tool"]})
                continue
            concrete = {key: ("scope:district:0000000000" if isinstance(value, str)
                              and _BINDING.match(value) else value)
                        for key, value in call["args"].items()}
            for error in Draft202012Validator(schema).iter_errors(concrete):
                conflicts.append({"id": number, "kind": "gold_schema",
                                  "detail": f"{call['tool']}[{index}]: {error.message}"})
            if (call["tool"] == "get_billing_metrics" and "scope" in call["args"]
                    and "dimension" in call["args"]):
                conflicts.append({"id": number, "kind": "gold_contract",
                                  "detail": "get_billing_metrics: scope와 dimension을 함께 씀"
                                            "(schema 설명: scope 통계에는 dimension 설정 금지)"})
        items.append({"id": f"{number:03d}", "question": question, "vendor_verdict": verdict,
                      "vendor_note": note, "vendor_result": result, "gold_text": gold,
                      "gold": calls})
    document = {
        "source": str(XLSX_FILE.relative_to(HERE)),
        "source_sha256": hashlib.sha256(XLSX_FILE.read_bytes()).hexdigest(),
        "questions_file": str(QUESTIONS_FILE.relative_to(HERE)),
        "note": "evaluate_vendor100.py extract가 xlsx에서 생성. 손으로 고치지 않는다.",
        "conflicts": conflicts,
        "items": items,
    }
    GOLD_FILE.write_text(yaml.safe_dump(document, allow_unicode=True, sort_keys=False,
                                        width=120), encoding="utf-8")
    print(f"{GOLD_FILE.relative_to(HERE)}: {len(items)}문항, 자료 충돌 {len(conflicts)}건")
    for conflict in conflicts:
        print(f"  - Q{conflict['id']:03d} {conflict['kind']}: {conflict['detail']}")
    return 0


def load_gold(path=None):
    """평가 문항. 업체 gold.yaml 또는 같은 표기의 다른 셋(``gold_text`` 줄, ``expected_outcome``)."""
    path = Path(path) if path else GOLD_FILE
    document = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.SafeLoader)
    for item in document["items"]:
        item["id"] = str(item["id"])
        item.setdefault("expected_outcome", "answered")
        item.setdefault("vendor_verdict", "-")
        if "gold" not in item:
            item["gold"] = parse_calls(item.get("gold_text") or "")
    return document


# -- 정답 grounding 역산 ---------------------------------------------------------------

_FACTOR_ARGS = ("date", "time", "taxi_type", "taxi_status", "dimension", "dimension_target",
                "order", "limit", "aggregation", "bucket", "rollup")
_SCOPE_ARGS = {"scope": None, "scope_pickup": "pickup", "scope_dropoff": "dropoff"}


def _binding_place(name, places):
    """gold의 ``$name.scope``가 가리키는 get_place_scope 호출."""
    if len(places) == 1:
        return places[0]
    order = {"pickup": 0, "dropoff": 1}
    if name in order and len(places) == 2:
        return places[order[name]]
    raise ValueError(f"${name}.scope를 정할 수 없습니다: 장소 호출 {len(places)}개")


def derive_grounding(calls):
    """업체 정답 호출 → grounding payload. 질문 문장은 보지 않는다(질문별 분기 없음)."""
    from geoflow import operator_mapping
    from geoflow.operator_registry import OPERATORS

    places = [call for call in calls if call["tool"] == "get_place_scope"]
    final = [call for call in calls if call["tool"] != "get_place_scope"][-1]
    spec = next(item for item in OPERATORS.values() if item.tool_name == final["tool"])
    args = final["args"]
    concepts, factors = [], {}
    for arg, role in _SCOPE_ARGS.items():
        value = args.get(arg)
        if value is None:
            continue
        attributes = {"od_role": role} if role else {}
        match = _BINDING.match(str(value))
        if match is None:
            concepts.append({"id": f"scope_{arg}", "concept": "LOCATION", "subtype": "scope",
                             "role": "COND", "source": "user", "value": value,
                             **({"attributes": attributes} if attributes else {})})
            continue
        place = _binding_place(match.group(1), places)["args"]
        concepts.append({"id": f"place_{arg}", "concept": "LOCATION", "subtype": "place",
                         "role": "SUBCOND", "source": "user",
                         "value": {"name": place["name"], "region": place.get("region", "")},
                         **({"attributes": attributes} if attributes else {})})
        if place.get("include_vicinity") is True:
            factors["vicinity"] = True
    if final["tool"] == "get_scope_name":
        concepts.append({"id": "place_name", "concept": "LOCATION", "subtype": "place",
                         "role": "MEASURE", "source": "implicit"})
        return {"concepts": concepts, "factors": factors}
    allowed = sorted(spec.output.allowed, key=lambda item: item[1])
    concept, subtype = (next(item for item in allowed if item[1] == args["metric"])
                        if "metric" in args else allowed[0])
    event = operator_mapping.event_subtype_for(concept, subtype)
    if event is not None:
        concepts.append({"id": "event", "concept": "EVENT", "subtype": event,
                         "role": "SUPPORT", "source": "implicit"})
    concepts.append({"id": "measure", "concept": concept.value, "subtype": subtype,
                     "role": "MEASURE", "source": "implicit"})
    for key in _FACTOR_ARGS:
        if key in args:
            factors[key] = args[key]
    return {"concepts": concepts, "factors": factors}


# -- 실행 ------------------------------------------------------------------------------


class _GoldPlanner:
    """정답 grounding을 돌려주는 planner. LLM을 부르지 않고 재질의하지 않는다."""

    def __init__(self, payload):
        self.payload = payload

    def plan(self, question):
        from geoflow.grounding import parse_grounding
        from geoflow.planner import PlannerOutput

        grounding = parse_grounding(json.loads(json.dumps(self.payload)), question)
        return PlannerOutput(grounding=grounding, raw_text=json.dumps(self.payload,
                                                                      ensure_ascii=False))

    def _no_repair(self, *args, **kwargs):
        from geoflow.errors import PlannerError
        raise PlannerError("정답 grounding은 재질의하지 않습니다.", code="REPAIR_UNSUPPORTED")

    repair = repair_planning_error = _no_repair


def _executor():
    from build import build
    from tool_executor import ToolExecutor
    from tool_handlers import get_tool_handlers

    tools, _ = build()
    return ToolExecutor(tools=tools, handlers=get_tool_handlers("mock"))


def _pipeline(planner):
    from geoflow.composer import MacroComposer
    from geoflow.pipeline import GeoFlowPipeline

    return GeoFlowPipeline(planner=planner, composer=MacroComposer(),
                           tool_executor=_executor(), clock=lambda: REFERENCE_DATE)


class _RecordingClient:
    """LLM 호출마다 소요 시간·요청 종류·원 응답을 남긴다. 호출 수와 지연을 재기 위한 것이다."""

    def __init__(self, client):
        self.client = client
        self.model = getattr(client, "model", None)
        self.calls = []

    def __getattr__(self, name):
        return getattr(self.client, name)

    def chat(self, messages, tools=None, **kwargs):
        import time
        started = time.perf_counter()
        response = self.client.chat(messages, tools=tools, **kwargs)
        message = (response or {}).get("message") or {}
        self.calls.append({
            "kind": "plan" if len(messages) <= 2 else "repair",
            "duration_ms": round((time.perf_counter() - started) * 1000, 1),
            "load_duration_ms": round(((response or {}).get("load_duration") or 0) / 1e6, 1),
            "content": message.get("content"),
            "thinking_chars": len(message.get("thinking") or ""),
        })
        return response


def _planner_trace(record):
    """모델 원 출력과 각 시도의 오류(거부된 필드·값·규칙)를 모은다."""
    error = record.get("error") or {}
    context = error.get("context") or {}
    attempts = []
    for attempt in record.get("attempts") or []:
        failure = attempt.get("error") or {}
        attempts.append({key: attempt.get(key) for key in (
            "index", "stage", "status", "error_code", "repair_kind", "repair_attempted",
            "repair_result", "reason")} | {
            "detail": failure.get("detail"),
            "raw_text": (failure.get("context") or {}).get("raw_text")})
    return {
        "raw_text": ((record.get("planner") or {}).get("raw_text")
                     or context.get("raw_text")),
        "error_stage": error.get("stage"),
        "error_detail": error.get("detail"),
        "error_context": {key: value for key, value in context.items()
                          if key not in ("raw_text",) and isinstance(value, (str, int, float,
                                                                           list, dict, bool))},
        "attempts": attempts,
        "repairs": record.get("repairs"),
        "durations": record.get("durations"),
    }


def run_item(pipeline, question):
    run = pipeline.run(question)
    record = run.to_dict()
    return {
        "planner_trace": _planner_trace(record),
        "outcome": run.outcome,
        "error_code": (record.get("error") or {}).get("code"),
        "error_user_message": (record.get("error") or {}).get("user_message"),
        # 계산하지 않은 경우 경로별 거부 이유(rejected)와 명시된 구간 정의가 여기에 남는다.
        "error_context": {key: value for key, value in
                          ((record.get("error") or {}).get("context") or {}).items()
                          if key in ("rejected", "calendar", "reason", "unconsumed")},
        "calls": [{"tool": hop["tool"], "args": hop.get("arguments") or {},
                   "result": hop.get("result")}
                  for hop in run.hop_log if hop.get("phase") == "tool"],
        "final_answer": run.final_answer,
        "grounding": record.get("grounding"),
        "lowering": (record.get("execution_plan") or {}).get("lowering") or {},
        "date_semantics": (record.get("execution_plan") or {}).get("date_semantics") or {},
        "plan_calendar": (record.get("plan") or {}).get("calendar"),
        "execution_profile": record.get("execution_profile"),
    }


# -- 채점 ------------------------------------------------------------------------------

#: schema 기본값. 생략과 같다(업체도 이런 생략을 정상으로 판정했다: 14, 15, 17, 43).
_DEFAULTS = {"taxi_type": "all", "taxi_status": "all", "dimension_target": "both",
             "aggregation": "avg", "region": "", "include_vicinity": False}
_DEFAULT_TOOLS = {"aggregation": {"get_passage_metrics", "get_trip_metrics",
                                  "get_drive_metrics", "get_billing_metrics"},
                  "dimension_target": {"get_trip_count"}}


def _normalized(tool, args):
    out = {}
    for key, value in args.items():
        if value is None:
            continue
        if key in _DEFAULTS and value == _DEFAULTS[key] and tool in _DEFAULT_TOOLS.get(
                key, {tool}):
            continue
        out[key] = value
    return out


def _place_key(args):
    return (args.get("name"), args.get("region") or "", bool(args.get("include_vicinity")))


def score(item, observed):
    """업체 정답과 실제 호출 비교. 범주 하나와 세부 판정."""
    gold = item["gold"]
    checks = {}
    calls = observed["calls"]
    expected = item.get("expected_outcome", "answered")
    if expected != "answered":
        # 답하지 않아야 하는 문항. 기대한 결과 종류로 멈췄을 때만 맞음.
        checks["expected_outcome"] = expected
        if observed["outcome"] == expected:
            return "expected_refusal", checks
        if observed["outcome"] == "answered":
            return "answered_instead_of_refusal", checks
        return "wrong_refusal_kind", checks
    if observed["outcome"] != "answered" or not calls:
        category = {"unsupported": "refused_unsupported",
                    "needs_clarification": "refused_clarification"}.get(
            observed["outcome"], "failed")
        return category, checks
    gold_places = [call for call in gold if call["tool"] == "get_place_scope"]
    gold_final = [call for call in gold if call["tool"] != "get_place_scope"][-1]
    places = [call for call in calls if call["tool"] == "get_place_scope"]
    analysis = [call for call in calls if call["tool"] != "get_place_scope"]
    checks["place_lookups_ok"] = ({_place_key(c["args"]) for c in places}
                                  == {_place_key(c["args"]) for c in gold_places})
    checks["duplicate_place_lookups"] = len(places) - len({_place_key(c["args"]) for c in places})
    checks["single_analysis_call"] = len(analysis) == 1
    final = analysis[-1] if analysis else {"tool": None, "args": {}}
    checks["tool_ok"] = final["tool"] == gold_final["tool"]
    # scope 출처: gold의 $binding은 해당 장소 조회 결과, 사용자 literal은 그대로여야 한다.
    resolved = {}
    for call in places:
        result = call.get("result")
        scope = result if isinstance(result, str) else (
            result.get("scope") if isinstance(result, dict) else None)
        resolved[_place_key(call["args"])] = scope
    want = {}
    for key, value in gold_final["args"].items():
        match = _BINDING.match(str(value))
        if match:
            place = _binding_place(match.group(1), gold_places)["args"]
            want[key] = resolved.get(_place_key(place), f"<조회 안 됨 {place.get('name')}>")
        else:
            want[key] = value
    got = _normalized(final["tool"] or "", final["args"])
    want = _normalized(gold_final["tool"], want)
    diff = sorted(set(want) | set(got))
    checks["arg_mismatches"] = [[key, want.get(key), got.get(key)] for key in diff
                                if want.get(key) != got.get(key)]
    checks["args_ok"] = not checks["arg_mismatches"]
    checks["answer_value_ok"] = _answer_has_value(observed["final_answer"], final.get("result"))
    ok = all(checks[key] for key in ("place_lookups_ok", "tool_ok", "args_ok",
                                     "single_analysis_call", "answer_value_ok"))
    return ("match" if ok else "answered_mismatch"), checks


def _number_texts(value):
    if isinstance(value, bool):
        return []
    if isinstance(value, int):
        return [f"{value:,}"]
    if isinstance(value, float):
        texts = [f"{value:,}", f"{value:,.2f}".rstrip("0").rstrip("."), f"{value:g}"]
        if value <= 1:
            texts.append(f"{value * 100:g}%")
        return texts
    if isinstance(value, str):
        match = re.fullmatch(r"(-?\d+(?:\.\d+)?)(.*)", value)
        if match:
            number = float(match.group(1)) if "." in match.group(1) else int(match.group(1))
            return [f"{t}{match.group(2)}" for t in _number_texts(number)] + [value]
    return []


_LABEL_KEYS = ("pickup", "dropoff", "sido", "sigungu", "emd", "h3", "dayofweek")


def _contains_number(answer, options):
    """숫자 표기가 다른 숫자의 일부가 아닌 채로 답변에 있는가("20"이 "2026"에 맞지 않게)."""
    return any(re.search(r"(?<![\d.,])" + re.escape(text) + r"(?![\d]|[.,]\d)", answer)
               for text in options)


def _answer_has_value(answer, result):
    """Tool 반환값이 답변에 그대로 있는가. 스칼라·{count}·목록(값과 분류 이름)·장소명 문자열.

    확인할 것이 없는 결과(None, 알 수 없는 형식)는 참이 아니다.
    """
    if answer is None or result is None:
        return False
    if isinstance(result, dict) and set(result) == {"count"}:
        result = result["count"]
    if isinstance(result, (int, float, str)) and not isinstance(result, bool):
        options = _number_texts(result)
        if options:
            return _contains_number(answer, options)
        return str(result) in answer or str(result).startswith("scope:")
    if isinstance(result, list) and result:
        for row in result:
            if not isinstance(row, dict):
                return False
            for key, value in row.items():
                if key in _LABEL_KEYS:
                    # scope 문자열은 답변에서 장소명으로 바뀐다(labeling). 이름만 대조한다.
                    if isinstance(value, str) and not value.startswith("scope:") \
                            and value not in answer:
                        return False
                elif not _contains_number(answer, _number_texts(value) or [str(value)]):
                    return False
        return True
    return False


# -- 명령 ------------------------------------------------------------------------------


def _meta(kind, extra=None):
    import subprocess

    def git(*args):
        return subprocess.run(["git", *args], cwd=CODE_ROOT, capture_output=True,
                              text=True).stdout.strip()
    return {"protocol": PROTOCOL, "kind": kind,
            "started_at": datetime.now(ZoneInfo("Asia/Seoul")).isoformat(),
            "command": " ".join(sys.argv), "code_root": str(CODE_ROOT),
            "code_commit": git("rev-parse", "HEAD"),
            "code_dirty": git("status", "--porcelain", "--", "geoflow", "prompts",
                              "schemas").splitlines(),
            # 커밋하지 않은 코드로 돌렸다면 그 변경을 특정한다(추적 파일 diff의 hash).
            "code_diff_sha256": hashlib.sha256(git(
                "diff", "HEAD", "--", "geoflow", "prompts", "schemas").encode(
                "utf-8")).hexdigest(),
            "code_untracked": {
                path: hashlib.sha256((CODE_ROOT / path).read_bytes()).hexdigest()
                for path in git("ls-files", "--others", "--exclude-standard", "--",
                                "geoflow", "prompts", "schemas").splitlines()},
            "gold_file": str(Path(GOLD_PATH or GOLD_FILE).resolve().relative_to(HERE)),
            "gold_sha256": hashlib.sha256(Path(GOLD_PATH or GOLD_FILE).read_bytes()).hexdigest(),
            "reference_date": REFERENCE_DATE.isoformat(), **(extra or {})}


def _summary(rows):
    from collections import Counter
    categories = Counter(row["category"] for row in rows)
    by_verdict = {}
    for row in rows:
        by_verdict.setdefault(row["vendor_verdict"], Counter())[row["category"]] += 1
    calls = [row["llm_calls"] for row in rows if "llm_calls" in row]
    latency = sorted((row.get("planner_trace") or {}).get("durations", {}).get("total_ms", 0)
                     for row in rows if row.get("planner_trace"))
    extra = {}
    if calls:
        extra["llm_calls"] = {"total": sum(len(c) for c in calls),
                              "plan": sum(1 for c in calls for x in c if x["kind"] == "plan"),
                              "repair": sum(1 for c in calls for x in c if x["kind"] == "repair"),
                              "llm_ms_total": round(sum(x["duration_ms"] for c in calls for x in c))}
    if latency:
        extra["total_ms"] = {"median": latency[len(latency) // 2], "sum": round(sum(latency))}
    judged = [row for row in rows if row.get("grounding_ok") is not None]
    if judged:
        extra["grounding_ok"] = {"count": sum(1 for row in judged if row["grounding_ok"]),
                                 "of": len(judged)}
    return {"items": len(rows), "categories": dict(categories), **extra,
            "by_vendor_verdict": {k: dict(v) for k, v in sorted(by_verdict.items())},
            "outcomes": dict(Counter(row["outcome"] for row in rows)),
            "error_codes": dict(Counter(row["error_code"] for row in rows if row["error_code"]))}


def gold_grounding(item):
    """문항의 정답 grounding. 명시된 것이 있으면 그것, 없으면 정답 호출에서 역산. 없으면 None."""
    if item.get("gold_grounding"):
        return json.loads(json.dumps(item["gold_grounding"], ensure_ascii=False))
    if item["gold"]:
        return derive_grounding(item["gold"])
    return None


def _grounding_view(payload):
    """grounding 비교용 정규형: 측정값, 장소(이름·지역·od_role), 사용자 scope, factor(기본값 제외)."""
    if not payload or not isinstance(payload, dict) or "concepts" not in payload:
        return None
    measure, places, scopes = None, [], []
    for concept in payload.get("concepts") or []:
        attributes = concept.get("attributes") or {}
        role = attributes.get("od_role") or concept.get("od_role")
        if concept.get("role") == "MEASURE":
            measure = (concept.get("concept"), concept.get("subtype"))
        elif concept.get("concept") == "LOCATION" and concept.get("subtype") == "place":
            value = concept.get("value") or {}
            places.append((value.get("name"), value.get("region") or "", role))
        elif concept.get("concept") == "LOCATION" and concept.get("subtype") == "scope":
            scopes.append((concept.get("value"), role))
    defaults = {"taxi_type": "all", "taxi_status": "all", "dimension_target": "both",
                "vicinity": False}
    factors = {key: value for key, value in (payload.get("factors") or {}).items()
               if value is not None and defaults.get(key, object()) != value}
    if factors.get("aggregation") == "avg" and "bucket" not in factors:
        factors.pop("aggregation")   # 한 단계 avg는 Tool 기본값과 같다(호출 채점과 같은 규칙).
    return {"measure": measure, "places": sorted(places, key=str), "scopes": sorted(scopes, key=str),
            "factors": factors}


def grounding_check(item, grounding):
    """최종 LLM grounding이 정답 grounding과 같은가. (같음 여부, 다른 항목)."""
    want = _grounding_view(gold_grounding(item))
    got = _grounding_view(grounding)
    if want is None:
        return None, []
    if got is None:
        return False, ["no_grounding"]
    diffs = []
    for key in ("measure", "places", "scopes"):
        if want[key] != got[key]:
            diffs.append([key, want[key], got[key]])
    for key in sorted(set(want["factors"]) | set(got["factors"])):
        if want["factors"].get(key) != got["factors"].get(key):
            diffs.append(["factor:" + key, want["factors"].get(key), got["factors"].get(key)])
    return not diffs, diffs


def cmd_gold(args):
    document = load_gold(GOLD_PATH)
    rows = []
    for item in document["items"]:
        if args.only and item["id"] not in args.only.split(","):
            continue
        payload = gold_grounding(item)
        if payload is None:
            rows.append({"id": item["id"], "question": item["question"],
                         "vendor_verdict": item["vendor_verdict"], "category": "no_gold_grounding",
                         "checks": {}, "outcome": None, "error_code": None, "calls": [],
                         "final_answer": None})
            continue
        observed = run_item(_pipeline(_GoldPlanner(payload)), item["question"])
        category, checks = score(item, observed)
        rows.append({"id": item["id"], "question": item["question"],
                     "vendor_verdict": item["vendor_verdict"], "gold_grounding": payload,
                     "category": category, "checks": checks, **observed})
    variants = []
    if VARIANTS_FILE.is_file() and not args.only and GOLD_PATH is None:
        for variant in yaml.safe_load(VARIANTS_FILE.read_text(encoding="utf-8"))["variants"]:
            base = next(item for item in document["items"] if item["id"] == variant["base"])
            payload = derive_grounding(base["gold"])
            observed = run_item(_pipeline(_GoldPlanner(payload)), variant["question"])
            variants.append({**variant, "observed_outcome": observed["outcome"],
                             "error_code": observed["error_code"],
                             "ok": (observed["outcome"], observed["error_code"])
                             == (variant["expected_outcome"], variant.get("expected_error")),
                             **{k: observed[k] for k in ("calls", "final_answer", "lowering",
                                                         "plan_calendar", "error_user_message")}})
    result = {"meta": _meta("gold_grounding"), "summary": _summary(rows),
              "variants": variants, "rows": rows}
    _write(args.out, result)
    _print_summary(result)
    return 0


def cmd_llm(args):
    import evaluate_prompt_ab as A
    from build import build
    from geoflow import providers, structured_grounding
    from geoflow.pipeline import GeoFlowPipeline
    from ollama_client import OllamaClient, resolve_think

    tools, _ = build()
    client = OllamaClient(args.host, args.model, {"temperature": 0},
                          chat_timeout=args.chat_timeout, think=resolve_think("auto"))
    version, digest, details = A._server_details(args.host, args.model)
    document = load_gold(GOLD_PATH)
    items = [item for item in document["items"]
             if not args.only or item["id"] in args.only.split(",")]
    out = Path(args.out)
    partial = out.with_suffix(".jsonl")
    done = {}
    if partial.is_file():
        for line in partial.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            done[row["id"]] = row
    A.unload_all_models(args.host)
    reset = A.OllamaStateReset(args.host, args.model)
    with partial.open("a", encoding="utf-8") as handle:
        for item in items:
            if item["id"] in done:
                continue
            state = reset.reset()
            recorder = _RecordingClient(client)
            pipeline = GeoFlowPipeline.create(
                client=recorder, tool_executor=_executor(),
                aggregation_grounding=structured_grounding.FLAT,
                clock=lambda: REFERENCE_DATE,
                execution_profile=providers.profile_for(providers.MOCK, providers.LEGACY))
            observed = run_item(pipeline, item["question"])
            category, checks = score(item, observed)
            grounding_ok, grounding_diffs = grounding_check(item, observed["grounding"])
            row = {"id": item["id"], "question": item["question"],
                   "vendor_verdict": item["vendor_verdict"], "category": category,
                   "checks": checks, "reset_ok": state.succeeded,
                   "grounding_ok": grounding_ok, "grounding_diffs": grounding_diffs,
                   "llm_calls": recorder.calls, **observed}
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
            handle.flush()
            done[item["id"]] = row
            print(f"{item['id']} {category} {observed['outcome']} {observed['error_code'] or ''}",
                  flush=True)
    rows = [done[item["id"]] for item in items if item["id"] in done]
    result = {"meta": _meta("llm", {"model": args.model, "model_digest": digest,
                                    "ollama_version": version, "model_details": details,
                                    "pipeline": {"aggregation_grounding": "flat",
                                                 "condition_check": False,
                                                 "provider": "mock", "tims_execution": "legacy",
                                                 "temperature": 0, "think": "auto",
                                                 "isolation": "unload_per_question"}}),
              "summary": _summary(rows), "rows": rows}
    _write(args.out, result)
    _print_summary(result)
    return 0


def cmd_replay(args):
    """기록된 LLM grounding을 이 코드(--code-root)로 다시 실행한다(planner 차이를 없앤다)."""
    source = json.loads(Path(args.source).read_text(encoding="utf-8"))
    gold = {item["id"]: item for item in load_gold(GOLD_PATH)["items"]}
    rows = []
    for row in source["rows"]:
        grounding = row.get("grounding")
        if not grounding:
            rows.append({**{k: row[k] for k in ("id", "question", "vendor_verdict")},
                         "category": row["category"], "checks": {}, "outcome": row["outcome"],
                         "error_code": row["error_code"], "calls": [], "final_answer": None,
                         "replayed": False})
            continue
        payload = {"concepts": grounding["concepts"], "factors": grounding["factors"]}
        observed = run_item(_pipeline(_GoldPlanner(payload)), row["question"])
        category, checks = score(gold[row["id"]], observed)
        rows.append({"id": row["id"], "question": row["question"],
                     "vendor_verdict": row["vendor_verdict"], "category": category,
                     "checks": checks, "replayed": True, **observed})
    result = {"meta": _meta("llm_replay", {"source": args.source}), "summary": _summary(rows),
              "rows": rows}
    _write(args.out, result)
    _print_summary(result)
    return 0


def cmd_rescore(args):
    """저장된 관측을 현재 채점 규칙으로 다시 채점한다(실행하지 않는다). 채점 규칙을 고친 뒤 쓴다."""
    path = Path(args.result)
    result = json.loads(path.read_text(encoding="utf-8"))
    gold = {item["id"]: item for item in load_gold(result["meta"].get("gold_file") or GOLD_PATH)["items"]}
    for row in result["rows"]:
        row["category"], row["checks"] = score(gold[row["id"]], row)
        if result["meta"].get("kind") in ("llm", "llm_replay"):
            row["grounding_ok"], row["grounding_diffs"] = grounding_check(
                gold[row["id"]], row.get("grounding"))
    result["summary"] = _summary(result["rows"])
    result["meta"]["rescored_at"] = datetime.now(ZoneInfo("Asia/Seoul")).isoformat()
    result["meta"]["scorer_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    _write(path, result)
    _print_summary(result)
    return 0


def cmd_compare(args):
    before = json.loads(Path(args.before).read_text(encoding="utf-8"))
    after = json.loads(Path(args.after).read_text(encoding="utf-8"))
    old = {row["id"]: row for row in before["rows"]}
    lines = [f"# 변경 전후 비교: {before['meta']['kind']}", "",
             f"- 전: `{before['meta']['code_commit'][:10]}` {before['summary']['categories']}",
             f"- 후: `{after['meta']['code_commit'][:10]}`"
             f"{' (작업 트리 변경 있음)' if after['meta']['code_dirty'] else ''} "
             f"{after['summary']['categories']}", "",
             "| 문항 | 업체 판정 | 전 | 후 | 후 오류/인자 차이 |", "|---|---|---|---|---|"]
    for row in after["rows"]:
        prior = old.get(row["id"], {})
        if prior.get("category") == row["category"] and not args.all:
            continue
        detail = row.get("error_code") or ""
        if row.get("checks", {}).get("arg_mismatches"):
            detail += " " + json.dumps(row["checks"]["arg_mismatches"], ensure_ascii=False)
        lines.append(f"| {row['id']} | {row['vendor_verdict']} | {prior.get('category')} "
                     f"({prior.get('error_code') or '-'}) | {row['category']} | {detail} |")
    text = "\n".join(lines) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    print(text)
    return 0


def _write(path, result):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=1, default=str),
                    encoding="utf-8")


def _print_summary(result):
    summary = result["summary"]
    print(json.dumps({k: summary[k] for k in ("items", "categories", "outcomes",
                                              "error_codes")}, ensure_ascii=False))
    for variant in result.get("variants") or []:
        print(f"variant {variant['id']}: {'OK' if variant['ok'] else 'FAIL'} "
              f"{variant['observed_outcome']} {variant['error_code']}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--code-root", default=None, help="평가할 코드 디렉터리(기본: 이 저장소)")
    parser.add_argument("--gold", default=None,
                        help="평가 문항 파일(기본: evaluation/vendor100/gold.yaml)")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("extract")
    gold = sub.add_parser("gold")
    gold.add_argument("--out", required=True)
    gold.add_argument("--only", default="")
    llm = sub.add_parser("llm")
    llm.add_argument("--model", required=True)
    llm.add_argument("--host", default=os.environ.get("OLLAMA_HOST", "http://localhost:11434"))
    llm.add_argument("--chat-timeout", type=float, default=300.0)
    llm.add_argument("--out", required=True)
    llm.add_argument("--only", default="")
    replay = sub.add_parser("replay")
    replay.add_argument("source")
    replay.add_argument("--out", required=True)
    rescore = sub.add_parser("rescore")
    rescore.add_argument("result")
    compare = sub.add_parser("compare")
    compare.add_argument("before")
    compare.add_argument("after")
    compare.add_argument("--out", default="")
    compare.add_argument("--all", action="store_true")
    args = parser.parse_args(argv)
    global GOLD_PATH
    GOLD_PATH = Path(args.gold).resolve() if args.gold else None
    return {"extract": cmd_extract, "gold": cmd_gold, "llm": cmd_llm, "replay": cmd_replay,
            "rescore": cmd_rescore, "compare": cmd_compare}[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
