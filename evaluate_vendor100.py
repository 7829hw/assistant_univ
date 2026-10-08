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
- ``report``: 두 결과를 같은 최종 채점기로 다시 채점해 결과 분류(정상 답변·오답·정당한 거부·부당한 거부·
  실행 실패·미실행)와 분모·합계, grounding 정확도의 포함·제외, 호출·지연·timeout·재시도를 표로 낸다.

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

#: 채점 규칙의 판. 바꾸면 이전 결과를 ``rescore``/``report``로 다시 채점하고 변경 이력에 적는다.
#: - v1(2026-09-29 grounding_v1 사전 등록): Tool·인자·장소 조회 집합·단일 분석 호출·답변 값.
#: - v2(2026-09-29 grounding_v2): v1 + 장소 조회 **횟수**가 정답과 같아야 한다. 같은 장소를 두 번
#:   조회하면 v1은 집합 비교라 맞음으로 셌다(업체 정답 093·095는 한 번 조회한 scope를 출발·도착에
#:   함께 쓴다). 조건을 완화한 것이 아니라 더한 것이다.
#: - v3(2026-09-30 grounding_v4): 문항이 ``expected_error``(허용 오류 코드 목록)를 적었으면, 기대한 결과 종류로
#:   멈췄더라도 그 코드일 때만 정당한 거부다. 적지 않은 문항은 v2와 같다. grounding 비교는 집계를 표현 방식(flat
#:   factor, 구조화 aggregation_plan)과 무관한 집계 IR(bucket·inner·outer·select)로 비교한다.
SCORER_VERSION = "v3"


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
#: 모델 적재 방식. 앞의 것이 기본값이다(grounding_v1부터의 평가 조건).
MODEL_STATES = ("unload_per_question", "keep_loaded")


def order_items(items, order):
    """문항 순서를 정한다. file은 파일 순서 그대로다."""
    import random
    items = list(items)
    if order == "file":
        return items
    if order == "reverse":
        return items[::-1]
    if order.startswith("shuffle:"):
        rng = random.Random(int(order.split(":", 1)[1]))
        rng.shuffle(items)
        return items
    raise SystemExit(f"알 수 없는 --order: {order}")


def _execution_spec_module():
    """실행 명세 부품은 이 저장소(harness) 것을 쓴다(--code-root의 다른 판이 아니라)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("_harness_execution_spec", HERE / "execution_spec.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_partial_rows(partial, spec, spec_sha, *, model_state, new_session=False):
    """이어 실행할 기존 행과 이번 세션 번호. 같은 실험으로 합칠 수 없으면 멈춘다.

    - 기존 행마다 실행 명세 hash(run_spec_sha256)가 있어야 하고 지금 명세와 같아야 한다. 명세가 없는 이전 형식 행은
      조건을 확인할 수 없으므로 이어 붙이지 않는다(읽기·채점은 그대로 된다).
    - unload_per_question: 문항마다 모델을 내리므로 문항끼리 서버 상태가 이어지지 않는다. 명세가 같으면 새 세션
      번호로 이어 붙인다.
    - keep_loaded: 앞선 처리 이력이 출력에 영향을 준다(grounding_v14). 중단 전 서버 상태는 복원할 수 없고, 이전
      요청을 다시 보내도 같은 상태가 된다고 가정하지 않는다. 기본은 거부한다. new_session=True면 나머지를 별도
      세션으로 기록하고 run을 "순수 연속 아님"으로 표시한다.
    """
    done = {}
    if not partial.is_file():
        return done, 1
    sidecar = partial.with_suffix(".spec.json")
    previous_spec = json.loads(sidecar.read_text(encoding="utf-8")) if sidecar.is_file() else None
    sessions = set()
    for line in partial.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if row.get("run_spec_sha256") is None:
            raise SystemExit(f"{partial}: 실행 명세가 없는 이전 형식 행({row.get('id')})이라 조건을 확인할 수 없다. "
                             "새 --out으로 시작한다.")
        if row["run_spec_sha256"] != spec_sha:
            differences = (_execution_spec_module().spec_differences(previous_spec, spec)
                           if previous_spec else ["(명세 파일 없음)"])
            raise SystemExit(f"{partial}: 기존 행의 실행 명세가 지금과 다르다(다른 항목: {', '.join(differences)}). "
                             "새 --out으로 시작한다.")
        sessions.add(row.get("session", 1))
        done[row["id"]] = row
    if done and model_state == "keep_loaded" and not new_session:
        raise SystemExit(f"{partial}: keep_loaded run은 이어 실행하지 않는다. 중단 전 서버 상태를 복원할 수 없어 나머지가 "
                         "같은 연속 실행이 아니다. 새 --out으로 다시 시작하거나, 나머지를 별도 세션으로 기록하려면 "
                         "--resume-new-session을 쓴다(순수 연속 실행으로 표시하지 않는다).")
    return done, (max(sessions) + 1) if sessions else 1


def run_settings(args):
    """결과에 영향을 주는 실행 조건. 행마다 남기고, 이어 실행할 때 같은지 확인한다."""
    return {"reference_date": args.reference_date.isoformat(), "model_state": args.model_state,
            "order": args.order}


#: 호출 seed 규칙(path_repeat_001 PLAN.md 3절). HF 경로(hf_eval_thinking.py)도 이 함수를 쓴다.
SEED_RULE = 'int.from_bytes(sha256(f"{round_seed}:{item_id}:{call_index}").digest()[:4], "big") & 0x7FFFFFFF'


def call_seed(round_seed, item_id, call_index):
    """회차 seed·문항 id·문항 안 호출 순번(0 = 첫 plan, 1부터 repair 등)으로 정한 호출 seed."""
    digest = hashlib.sha256(f"{round_seed}:{item_id}:{call_index}".encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") & 0x7FFFFFFF


def sampling_settings(args):
    """``--temperature/--top-p/--top-k/--seed``. 하나도 주지 않으면 None(기존 temperature 0 요청 그대로)."""
    values = {"temperature": getattr(args, "temperature", None), "top_p": getattr(args, "top_p", None),
              "top_k": getattr(args, "top_k", None), "seed": getattr(args, "seed", None)}
    if all(value is None for value in values.values()):
        return None
    missing = [key for key, value in values.items() if value is None]
    if missing:
        raise SystemExit(f"sampling은 --temperature, --top-p, --top-k, --seed를 모두 지정해야 한다(빠짐: {missing})")
    if getattr(args, "replay_from", None):
        raise SystemExit("sampling과 --replay-from은 함께 쓰지 않는다")
    return {"temperature": values["temperature"], "top_p": values["top_p"], "top_k": values["top_k"],
            "round_seed": values["seed"], "seed_rule": SEED_RULE}


class _SeededClient:
    """sampling 요청: 호출마다 PLAN 3절 규칙의 seed를 options에 넣는다. 실패한 호출도 순번을 쓴다."""

    def __init__(self, client, sampling, item_id):
        self.client = client
        self.model = getattr(client, "model", None)
        self.sampling = sampling
        self.item_id = item_id
        self.calls = 0

    def __getattr__(self, name):
        return getattr(self.client, name)

    def chat(self, messages, tools=None, **kwargs):
        seed = call_seed(self.sampling["round_seed"], self.item_id, self.calls)
        self.calls += 1
        self.client.options = {"temperature": self.sampling["temperature"], "top_p": self.sampling["top_p"],
                               "top_k": self.sampling["top_k"], "seed": seed}
        response = self.client.chat(messages, tools=tools, **kwargs)
        if isinstance(response, dict):
            response = {**response, "sampling_seed": seed}
        return response


def environment_record(host=None):
    """``--record-env``: 실행 장치와 소프트웨어 판. 생성에는 영향을 주지 않는다."""
    import platform
    import subprocess

    def run(*command):
        try:
            return subprocess.run(command, capture_output=True, text=True, timeout=30).stdout.strip()
        except (OSError, subprocess.SubprocessError) as error:
            return f"error: {type(error).__name__}: {error}"
    gpus = []
    for line in run("nvidia-smi", "--query-gpu=name,uuid,driver_version", "--format=csv,noheader").splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) == 3:
            gpus.append({"name": parts[0], "uuid": parts[1], "driver": parts[2]})
    record = {"host_gpus": gpus, "python": platform.python_version(), "hostname": platform.node()}
    if host is not None:
        record["ollama_container_gpus"] = run("docker", "exec", "ollama", "nvidia-smi", "-L").splitlines()
    return record


def run_spec(args, *, digest, version, prompt_sha, items):
    """결과에 영향을 주는 조건 전체(실행 명세). 같은 run으로 합칠 수 있는지는 이 명세의 hash로 정한다."""
    module = _execution_spec_module()
    gold = Path(GOLD_PATH or GOLD_FILE)
    replay = Path(args.replay_from) if args.replay_from else None
    sampling = sampling_settings(args)
    spec = {
        "model": args.model, "model_digest": digest, "ollama_version": version,
        "planner_prompt_sha256": prompt_sha,
        "code_fingerprint": module.code_fingerprint(CODE_ROOT)["sha256"],
        "gold_sha256": hashlib.sha256(gold.read_bytes()).hexdigest(),
        "items": [item["id"] for item in items],     # 선택 문항(--only)과 순서(--order)를 함께 고정한다
        "options": {"condition_check": args.condition_check, "condition_notes": args.condition_notes,
                    "normalize_grounding": not args.no_normalize, "semantic_reinterpretation": not args.no_semantic,
                    "aggregation_grounding": args.aggregation_grounding, "chat_timeout_s": args.chat_timeout,
                    "temperature": 0, "think": getattr(args, "model_think", "auto"), "provider": "mock",
                    "tims_execution": "legacy"},
        "run_settings": run_settings(args),
        "replay_from_sha256": hashlib.sha256(replay.read_bytes()).hexdigest() if replay else None,
    }
    if sampling is not None:     # 지정하지 않으면 명세(와 그 hash)는 이전과 같다
        spec["options"]["temperature"] = sampling["temperature"]
        spec["options"]["sampling"] = sampling
    return spec


def _measurement(calls):
    """문항의 측정 종류: live(모든 호출이 실제 모델), replayed(모두 기록 재적용), mixed."""
    replayed = [bool(call.get("replayed")) for call in calls if not call.get("failed")]
    if not replayed or not any(replayed):
        return "live"
    return "replayed" if all(replayed) else "mixed"


def _continuity(rows, model_state):
    """run의 세션 구성과 측정 종류. 순수 연속 실측은 keep_loaded·한 세션·기록 재적용 없음일 때뿐이다."""
    from collections import Counter
    sessions = Counter(row.get("session", 1) for row in rows)
    kinds = Counter(row.get("measurement", "live") for row in rows)
    return {"sessions": [{"session": key, "items": sessions[key]} for key in sorted(sessions)],
            "measurement": dict(kinds),
            "pure_live": set(kinds) <= {"live"},
            "pure_continuous": model_state == "keep_loaded" and len(sessions) == 1 and set(kinds) <= {"live"}}
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
        request_sha = _request_sha(messages)
        try:
            response = self.client.chat(messages, tools=tools, **kwargs)
        except Exception as error:
            # timeout 등으로 실패한 호출도 센다. planner가 다시 부르면 다음 호출로 따로 남는다.
            self.calls.append({
                "kind": "plan" if len(messages) <= 2 else "repair", "failed": True,
                "error": f"{type(error).__name__}: {error}"[:300],
                "duration_ms": round((time.perf_counter() - started) * 1000, 1)})
            raise
        message = (response or {}).get("message") or {}
        self.calls.append({
            "kind": "plan" if len(messages) <= 2 else "repair",
            # 요청 전체(system prompt·첫 응답·재질의 문구)의 hash. 기록 응답을 다시 넣을 때 같은 요청인지 본다.
            "request_sha256": request_sha,
            "replayed": bool((response or {}).get("replayed")),
            "duration_ms": round((time.perf_counter() - started) * 1000, 1),
            "load_duration_ms": round(((response or {}).get("load_duration") or 0) / 1e6, 1),
            "content": message.get("content"),
            "thinking_chars": len(message.get("thinking") or ""),
            # 생성 길이와 끝난 이유(length면 생성 상한에서 잘림). 이전 기록에는 없다.
            "prompt_eval_count": (response or {}).get("prompt_eval_count"),
            "eval_count": (response or {}).get("eval_count"),
            "done_reason": (response or {}).get("done_reason"),
        })
        if (response or {}).get("sampling_seed") is not None:     # sampling run에만 있다(_SeededClient)
            self.calls[-1]["sampling_seed"] = response["sampling_seed"]
        return response


class _ReplayClient:
    """기록된 계획 응답을 다시 돌려준다. 시스템 prompt hash와 질문이 같을 때만. 그 밖(재질의 등)은
    실제 모델을 부른다. prompt를 바꾸지 않은 후보(코드 규칙)를 모델 호출 없이 비교하려는 것이다.
    planner가 결정적(temperature 0)이라는 전제는 B0가 이전 run과 grounding 100개가 같았던 것으로 확인했다.
    """

    def __init__(self, client, cache, before_live=None):
        self.client = client
        self.model = getattr(client, "model", None)
        self.cache = cache
        self.hits = 0
        #: 문항 안에서 처음 실제 모델을 부르기 직전에 한 번 부른다(격리: 재질의도 모델을 내린 상태에서 시작한다).
        self.before_live = before_live

    def __getattr__(self, name):
        return getattr(self.client, name)

    def chat(self, messages, tools=None, **kwargs):
        if len(messages) == 2 and messages[0]["role"] == "system":
            key = (hashlib.sha256(messages[0]["content"].encode("utf-8")).hexdigest(),
                   messages[1]["content"])
            if key in self.cache:
                self.hits += 1
                return {"message": {"content": self.cache[key]}, "done_reason": "stop",
                        "load_duration": 0, "replayed": True}
        if self.before_live is not None:
            hook, self.before_live = self.before_live, None
            hook()
        return self.client.chat(messages, tools=tools, **kwargs)


def load_replay_cache(path):
    """이전 llm 결과의 첫 계획 응답 → {(prompt sha, 질문): 응답}."""
    result = json.loads(Path(path).read_text(encoding="utf-8"))
    sha = result["meta"].get("planner_prompt_sha256")
    if not sha:
        raise ValueError(f"{path}: meta.planner_prompt_sha256이 없어 재생할 수 없습니다")
    cache = {}
    for row in result["rows"]:
        plans = [call for call in row.get("llm_calls") or []
                 if call["kind"] == "plan" and not call.get("failed")]
        if plans:
            cache[(sha, row["question"])] = plans[0]["content"]
    return cache


def _planner_trace(record):
    """모델 원 출력과 각 시도의 오류(거부된 필드·값·규칙)를 모은다."""
    error = record.get("error") or {}
    context = error.get("context") or {}
    attempts = []
    for attempt in record.get("attempts") or []:
        failure = attempt.get("error") or {}
        attempts.append({key: attempt.get(key) for key in (
            "index", "stage", "status", "error_code", "repair_kind", "repair_attempted",
            "repair_result", "reason", "repair_raw_text", "repaired_factors", "correction")} | {
            "detail": failure.get("detail"),
            "raw_text": (failure.get("context") or {}).get("raw_text"),
            # 재질의가 실패했으면 그 이유(범위 위반·형식 오류·질문에 없음)를 남긴다.
            "repair_error": {key: (attempt.get("repair_error") or {}).get(key)
                             for key in ("code", "detail")} if attempt.get("repair_error") else None})
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
        # 조건 계층이 모델 출력에서 바꾼 것(근거 표현·전후 값·이유). 보정 전후 grounding 차이의 기록이다.
        "condition_corrections": (record.get("condition_audit") or {}).get("corrections"),
        # 조건 계층이 소유한 조건마다의 판정(채움·확인·보존·삭제·측정값 정의로 채우지 않음)과 근거. 바꾸지 않은 판정도 남긴다.
        "condition_actions": {
            key: {field: (value or {}).get(field) for field in ("llm_value", "value", "action", "basis")}
            for key, value in (record.get("condition_audit") or {}).items()
            if key in ("date", "taxi_type", "taxi_status") and isinstance(value, dict)},
        "lowering": (record.get("execution_plan") or {}).get("lowering") or {},
        "date_semantics": (record.get("execution_plan") or {}).get("date_semantics") or {},
        "plan_calendar": (record.get("plan") or {}).get("calendar"),
        "execution_profile": record.get("execution_profile"),
    }


def _crashed(error):
    """평가 대상 코드가 GeoFlowError가 아닌 예외로 멈춘 문항. run_item과 같은 key를 갖는 실패 기록."""
    import traceback
    return {"planner_trace": {"exception": f"{type(error).__name__}: {error}"[:500],
                              "traceback_tail": traceback.format_exc().splitlines()[-6:]},
            "outcome": "failed", "error_code": "UNHANDLED_EXCEPTION",
            "error_user_message": None, "error_context": {}, "calls": [], "final_answer": None,
            "grounding": None, "condition_corrections": None, "condition_actions": {},
            "lowering": {}, "date_semantics": {}, "plan_calendar": None, "execution_profile": None}


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
        allowed = item.get("expected_error")
        if observed["outcome"] == expected and allowed:
            allowed = [allowed] if isinstance(allowed, str) else list(allowed)
            checks["expected_error"] = allowed
            checks["refusal_reason_ok"] = observed.get("error_code") in allowed
            return ("expected_refusal" if checks["refusal_reason_ok"]
                    else "wrong_refusal_reason"), checks
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
    checks["place_lookup_count_ok"] = len(places) == len(gold_places)
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
    ok = all(checks[key] for key in ("place_lookups_ok", "place_lookup_count_ok", "tool_ok",
                                     "args_ok", "single_analysis_call", "answer_value_ok"))
    return ("match" if ok else "answered_mismatch"), checks


#: 축을 나눈 채점(grounding_v9). v3 범주는 그대로 두고 따로 계산한다. 저장된 관측만으로 계산하며 모델을 부르지 않는다.
#: - 의미(semantic): 최종 분석 호출의 Tool·인자·답변 값. 정답 장소는 이 run의 조회가 아니라 정답 조회를 같은
#:   실행기에 넣어 얻은 scope와 비교한다. 이름·지역 표기가 달라도 제공자가 같은 scope로 풀면 같은 장소다.
#:   주변 포함(include_vicinity)은 scope 값에 드러나지 않으므로 그 scope를 만든 조회의 값이 정답과 같아야 한다.
#:   분석 호출에 쓴 scope는 이 run의 성공한 조회 결과여야 한다(출처). 분석 호출은 하나여야 한다.
#: - 경로(path): 장소 조회를 쓰임(최종 호출이 쓴 scope)·실패(오류 반환, 쓸 수 없음)·중복(앞과 같은 조회)·
#:   폐기(성공했지만 최종 호출이 쓰지 않음)로 나눈다. 분석 호출의 오류, 정답보다 많은 조회도 센다.
#: - 실패한 조회를 무시하는 것이 아니다. 잘못된 장소의 scope가 최종 호출에 들어가면 의미 축에서 틀리고,
#:   쓰이지 않고 버려졌으면 의미는 맞되 경로 축에 남는다.
SEMANTIC_SCORER_VERSION = "v4-axes"


def _gold_scopes(gold_places):
    """정답 장소 조회를 실행기에 넣은 결과(scope 또는 None). 모델 출력과 무관하다."""
    executor = _gold_scopes.executor = getattr(_gold_scopes, "executor", None) or _executor()
    out = []
    for call in gold_places:
        result = executor.execute("get_place_scope", call["args"])
        out.append(result if isinstance(result, str) else None)
    return out


def _lookup_scope(call):
    result = call.get("result")
    if isinstance(result, str):
        return result
    if isinstance(result, dict) and isinstance(result.get("scope"), str):
        return result["scope"]
    return None


def execution_path(item, observed):
    """실행 경로의 장소 조회·분석 호출 분류. 의미 정확과 따로 본다."""
    calls = observed.get("calls") or []
    places = [call for call in calls if call["tool"] == "get_place_scope"]
    analysis = [call for call in calls if call["tool"] != "get_place_scope"]
    final_args = (analysis[-1]["args"] if analysis else {}) or {}
    used_scopes = {value for value in final_args.values() if isinstance(value, str)
                   and value.startswith("scope:")}
    seen, kinds = set(), []
    for call in places:
        key = _place_key(call["args"])
        scope = _lookup_scope(call)
        if scope is None:
            error = call.get("result") if isinstance(call.get("result"), dict) else {}
            kinds.append("failed:" + str(error.get("error_code") or "ERROR"))
        elif key in seen:
            kinds.append("duplicate")
        elif scope in used_scopes:
            kinds.append("used")
        else:
            kinds.append("discarded")
        seen.add(key)
    gold_places = [call for call in item.get("gold") or [] if call["tool"] == "get_place_scope"]
    analysis_errors = [call["tool"] for call in analysis
                       if isinstance(call.get("result"), dict) and call["result"].get("status") == "ERROR"]
    path = {
        "lookups": len(places), "gold_lookups": len(gold_places), "lookup_kinds": kinds,
        "failed_lookups": sum(1 for kind in kinds if kind.startswith("failed")),
        "duplicate_lookups": kinds.count("duplicate"),
        "discarded_lookups": kinds.count("discarded"),
        "extra_lookups": max(0, len(places) - len(gold_places)),
        "analysis_calls": len(analysis), "analysis_errors": analysis_errors,
    }
    path["clean"] = (path["lookups"] == path["gold_lookups"] and not path["failed_lookups"]
                     and not path["duplicate_lookups"] and not path["discarded_lookups"]
                     and len(analysis) <= 1 and not analysis_errors)
    return path


def score_semantic(item, observed):
    """최종 질문 의미·조건·scope 출처·답변 값. (범주, 세부). 범주 이름은 v3와 같다(정상 답변 = match)."""
    expected = item.get("expected_outcome", "answered")
    if expected != "answered" or observed.get("outcome") != "answered" or not observed.get("calls"):
        # 답하지 않는 결과의 판정은 v3와 같다.
        return score(item, observed)
    gold = item["gold"]
    calls = observed["calls"]
    checks = {}
    gold_places = [call for call in gold if call["tool"] == "get_place_scope"]
    gold_final = [call for call in gold if call["tool"] != "get_place_scope"][-1]
    places = [call for call in calls if call["tool"] == "get_place_scope"]
    analysis = [call for call in calls if call["tool"] != "get_place_scope"]
    checks["single_analysis_call"] = len(analysis) == 1
    final = analysis[-1] if analysis else {"tool": None, "args": {}}
    checks["tool_ok"] = final["tool"] == gold_final["tool"]
    gold_scope = _gold_scopes(gold_places)
    # 이 run에서 성공한 조회: scope → 그 scope를 만든 조회 인자들
    produced = {}
    for call in places:
        scope = _lookup_scope(call)
        if scope is not None:
            produced.setdefault(scope, []).append(call["args"])
    want, vicinity = {}, {}
    for key, value in gold_final["args"].items():
        match = _BINDING.match(str(value))
        if match:
            place = _binding_place(match.group(1), gold_places)
            scope = gold_scope[gold_places.index(place)]
            want[key] = scope if scope is not None else f"<정답 조회 실패 {place['args'].get('name')}>"
            vicinity[key] = bool(place["args"].get("include_vicinity"))
        else:
            want[key] = value
    got = _normalized(final["tool"] or "", final["args"])
    want = _normalized(gold_final["tool"], want)
    checks["arg_mismatches"] = [[key, want.get(key), got.get(key)] for key in sorted(set(want) | set(got))
                                if want.get(key) != got.get(key)]
    checks["args_ok"] = not checks["arg_mismatches"]
    # scope 출처와 주변 포함: 정답이 장소 조회 결과를 쓰는 인자마다. 사용자가 적은 scope literal은 args 비교로 충분하다.
    provenance, vicinity_ok = True, True
    for key, value in final["args"].items():
        if key not in vicinity or not isinstance(value, str):
            continue
        sources = produced.get(value)
        if not sources:
            provenance = False
            continue
        if not any(bool(args.get("include_vicinity")) == vicinity[key]
                                       for args in sources):
            vicinity_ok = False
    checks["scope_from_lookup"] = provenance
    checks["vicinity_ok"] = vicinity_ok
    checks["answer_value_ok"] = _answer_has_value(observed.get("final_answer"), final.get("result"))
    ok = all(checks[key] for key in ("single_analysis_call", "tool_ok", "args_ok", "scope_from_lookup",
                                     "vicinity_ok", "answer_value_ok"))
    return ("match" if ok else "answered_mismatch"), checks


def run_cost(row):
    """모델 호출·재질의·지연. 기록에 없는 값은 None."""
    calls = row.get("llm_calls") or []
    trace = row.get("planner_trace") or {}
    # 재질의 종류별 시도·성공(pipeline 기록). 성공은 "재질의 응답이 받아들여졌다"이지 의미가 맞았다는 뜻이 아니다.
    repairs = trace.get("repairs") or {}
    tokens = [c.get("eval_count") for c in calls if c.get("eval_count") is not None]
    return {
        "plan_calls": sum(1 for c in calls if c["kind"] == "plan"),
        "repair_calls": sum(1 for c in calls if c["kind"] == "repair"),
        "failed_calls": sum(1 for c in calls if c.get("failed")),
        "repairs": sum(v.get("attempted") or 0 for v in repairs.values()),
        "repair_kinds": sorted(kind for kind, v in repairs.items() if v.get("attempted")),
        "repair_failed": sum((v.get("attempted") or 0) - (v.get("succeeded") or 0)
                             for v in repairs.values()),
        "llm_ms": round(sum(c.get("duration_ms") or 0 for c in calls)),
        "total_ms": (trace.get("durations") or {}).get("total_ms"),
        "thinking_chars": sum(c.get("thinking_chars") or 0 for c in calls),
        "eval_tokens": sum(tokens) if tokens else None,
        "truncated": sum(1 for c in calls if c.get("done_reason") == "length"),
    }


#: 채점 범주 → 보고용 결과 분류. 모든 범주가 정확히 하나로 간다(합계가 분모와 같다).
RESULT_CLASSES = ("정상 답변", "오답", "정당한 거부", "부당한 거부", "실행 실패", "미실행")
_CLASS_OF = {
    "match": "정상 답변",
    "answered_mismatch": "오답",                 # 답했지만 Tool·인자·답변 값이 정답과 다름
    "answered_instead_of_refusal": "오답",       # 답하지 말아야 할 문항에 답함
    "expected_refusal": "정당한 거부",            # 기대한 결과 종류로 멈춤
    "refused_unsupported": "부당한 거부",         # 답해야 할 문항을 지원 안 함으로 멈춤
    "refused_clarification": "부당한 거부",       # 답해야 할 문항을 확인 요청으로 멈춤
    "wrong_refusal_kind": "부당한 거부",          # 멈춰야 할 문항이지만 다른 종류로 멈춤
    "wrong_refusal_reason": "부당한 거부",        # 기대한 종류로 멈췄지만 이유(expected_error)가 다름
    "failed": "실행 실패",                        # 오류로 끝남(계획·합성·조회 실패 등)
    "no_gold_grounding": "미실행",                # 정답 grounding 층에서 표현할 수 없어 실행하지 않음
}


def result_class(row):
    """행 하나의 보고용 결과 분류. 기대가 거부인 문항이 실행 실패로 끝나면 실행 실패로 센다."""
    if row["category"] == "wrong_refusal_kind" and row.get("outcome") not in (
            "unsupported", "needs_clarification"):
        return "실행 실패"
    return _CLASS_OF[row["category"]]


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
                              "failed": sum(1 for c in calls for x in c if x.get("failed")),
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
        payload = json.loads(json.dumps(item["gold_grounding"], ensure_ascii=False))
        return _current_contract(payload)
    if item["gold"]:
        return derive_grounding(item["gold"])
    return None


def _current_contract(payload):
    """정답 라벨의 구간 선택(집계 IR select)을 현재 flat 계약의 표기로 적는다. 뜻은 바꾸지 않는다.

    grounding_v4 라벨은 select=max|min으로 적었다. 현재 flat 계약은 같은 뜻을 answer=bucket + rollup=max|min으로 적는다.
    """
    from geoflow.factors import FACTOR_SPECS

    factors = payload.get("factors") or {}
    if "select" in factors and "select" not in FACTOR_SPECS and "answer" in FACTOR_SPECS:
        factors = dict(factors)
        factors["rollup"] = factors.pop("select")
        factors["answer"] = "bucket"
        payload = {**payload, "factors": factors}
    return payload


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
    raw_factors = payload.get("factors") or {}
    factors = {key: value for key, value in raw_factors.items()
               if value is not None and defaults.get(key, object()) != value
               and key not in _AGGREGATION_KEYS}
    spec = _aggregation_view(payload)
    if spec is not None:
        factors["aggregation_spec"] = spec
    return {"measure": measure, "places": sorted(places, key=str), "scopes": sorted(scopes, key=str),
            "factors": factors}


#: 집계를 적는 자리. grounding 비교에서는 표현 방식과 무관한 집계 IR 하나로 바꿔 비교한다.
_AGGREGATION_KEYS = ("aggregation", "bucket", "rollup", "select", "answer", "aggregation_plan")


def _aggregation_view(payload):
    """집계 IR(bucket, inner, outer, select). 없으면 None. 해석할 수 없는 표기는 그대로 표시한다.

    flat factor, 구조화 aggregation_plan, Grounding.to_dict()의 "aggregation"을 같은 형태로 만든다.
    구간이 없는 한 단계 avg는 Tool 기본값과 같다(호출 채점과 같은 규칙). 구간 안 집계가 없으면 unspecified.
    """
    from geoflow import aggregation as A
    from geoflow.errors import PlannerError

    factors = payload.get("factors") or {}
    try:
        if isinstance(payload.get("aggregation"), dict) and payload["aggregation"].get("source"):
            spec = payload["aggregation"]
            spec = (spec.get("bucket"), spec.get("inner"), spec.get("outer"), spec.get("select"))
        elif factors.get(A.PLAN_KEY) is not None:
            plan = A.parse_plan(factors[A.PLAN_KEY])
            spec = (plan.bucket, plan.inner, plan.outer, plan.select)
        else:
            flat = A.from_flat({key: factors.get(key) for key in A.FLAT_KEYS if factors.get(key)})
            spec = (flat.bucket, flat.inner, flat.outer, flat.select)
            if factors.get("select") and flat.bucket:
                # 정답 라벨의 flat select(구간 선택)는 계약 표기와 무관하게 같은 IR로 읽는다.
                spec = (flat.bucket, flat.inner, None, factors["select"])
    except PlannerError:
        return ["invalid", str(factors.get(A.PLAN_KEY))[:60]]
    bucket, inner, outer, select = spec
    if bucket is None and inner == "avg":
        inner = None
    if bucket is not None and inner is None:
        inner = A.UNSPECIFIED
    if (bucket, inner, outer, select) == (None, None, None, None):
        return None
    return [bucket, inner, outer, select]


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
    # think는 지정한 경우에만 payload에 들어간다(auto = 넣지 않음, 이전 기록과 같은 요청).
    sampling = sampling_settings(args)
    client = OllamaClient(args.host, args.model, {"temperature": 0},
                          chat_timeout=args.chat_timeout, think=resolve_think(getattr(args, "model_think", "auto")))
    environment = environment_record(args.host) if getattr(args, "record_env", False) else None
    version, digest, details = A._server_details(args.host, args.model)
    document = load_gold(GOLD_PATH)
    global REFERENCE_DATE
    REFERENCE_DATE = args.reference_date
    settings = run_settings(args)
    items = order_items([item for item in document["items"]
                         if not args.only or item["id"] in args.only.split(",")], args.order)
    out = Path(args.out)
    partial = out.with_suffix(".jsonl")
    from geoflow.planner import GeoFlowPlanner
    prompt_sha = hashlib.sha256(GeoFlowPlanner(client=None).system_prompt().encode(
        "utf-8")).hexdigest()
    spec = run_spec(args, digest=digest, version=version, prompt_sha=prompt_sha, items=items)
    spec_sha = _execution_spec_module().spec_sha256(spec)
    done, session = load_partial_rows(partial, spec, spec_sha, model_state=args.model_state,
                                      new_session=args.resume_new_session)
    partial.with_suffix(".spec.json").write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")
    cache = load_replay_cache(args.replay_from) if args.replay_from else None
    if cache is None:
        A.unload_all_models(args.host)
    reset = A.OllamaStateReset(args.host, args.model)
    with partial.open("a", encoding="utf-8") as handle:
        for item in items:
            if item["id"] in done:
                continue
            item_started = datetime.now(ZoneInfo("Asia/Seoul"))
            replayed = cache is not None and (prompt_sha, item["question"]) in cache
            keep = args.model_state == "keep_loaded"
            if not replayed:
                state = type("Kept", (), {"succeeded": None})() if keep else reset.reset()
                replay = _ReplayClient(client, cache) if cache is not None else None
            else:
                # 첫 계획은 기록을 돌려준다. 재질의 같은 실제 호출이 생기면 그 직전에 모델을 내린다.
                state = type("Deferred", (), {"succeeded": True})()

                def _reset_before_live(state=state):
                    if not keep:
                        state.succeeded = reset.reset().succeeded
                replay = _ReplayClient(client, cache, before_live=_reset_before_live)
            seeded = _SeededClient(client, sampling, item["id"]) if sampling is not None else None
            recorder = _RecordingClient(replay or seeded or client)
            # 기준 코드(--code-root)에는 없는 인자다. 기본값이 아닐 때만 넘긴다.
            options = {}
            if args.condition_notes:
                options["condition_notes"] = True
            elif args.condition_check:
                options["condition_notes"] = False   # production CLI 기본(감사 문구 없음)
            if args.no_normalize:
                options["normalize_grounding"] = False
            if args.no_semantic:
                options["semantic_reinterpretation"] = False
            pipeline = GeoFlowPipeline.create(
                client=recorder, tool_executor=_executor(),
                aggregation_grounding=args.aggregation_grounding,
                clock=lambda: REFERENCE_DATE, condition_check=args.condition_check,
                execution_profile=providers.profile_for(providers.MOCK, providers.LEGACY),
                **options)
            try:
                observed = run_item(pipeline, item["question"])
            except Exception as error:  # noqa: BLE001 - 평가 대상 코드의 미처리 예외도 문항 결과로 남긴다
                # 이전에는 run 전체가 멈췄다. 모델 응답(llm_calls)과 예외를 남기고 실패(답 없음)로 센다.
                observed = _crashed(error)
            category, checks = score(item, observed)
            grounding_ok, grounding_diffs = grounding_check(item, observed["grounding"])
            row = {"id": item["id"], "question": item["question"],
                   "vendor_verdict": item["vendor_verdict"], "category": category,
                   "checks": checks, "reset_ok": state.succeeded,
                   "run_settings": settings, "sequence_index": len(done) + 1,
                   "run_spec_sha256": spec_sha, "session": session,
                   "measurement": _measurement(recorder.calls),
                   "grounding_ok": grounding_ok, "grounding_diffs": grounding_diffs,
                   "llm_calls": recorder.calls,
                   # 모델 unload(격리)와 실행을 포함한 문항 경과 시간. 전체 경과 시간은 첫 started_at부터
                   # 마지막 finished_at까지다(이어 실행하면 사이의 빈 시간이 포함되므로 따로 적는다).
                   "started_at": item_started.isoformat(),
                   "finished_at": datetime.now(ZoneInfo("Asia/Seoul")).isoformat(),
                   **observed}
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
            handle.flush()
            done[item["id"]] = row
            print(f"{item['id']} {category} {observed['outcome']} {observed['error_code'] or ''}",
                  flush=True)
    rows = [done[item["id"]] for item in items if item["id"] in done]
    import httpx
    # 결과에 영향을 주는 모델 쪽 설정: Modelfile 기본 파라미터(penalty 등), 적재된 context 길이와 VRAM.
    try:
        shown = httpx.post(f"{args.host}/api/show", json={"model": args.model}, timeout=30).json()
        loaded = [m for m in httpx.get(f"{args.host}/api/ps", timeout=5).json().get("models", [])
                  if m.get("name") == args.model]
        runtime = {"modelfile_parameters": shown.get("parameters"),
                   "capabilities": shown.get("capabilities"),
                   "context_length": loaded[0].get("context_length") if loaded else None,
                   "size_vram": loaded[0].get("size_vram") if loaded else None}
    except Exception as error:  # noqa: BLE001 - 기록 실패가 결과 저장을 막지 않게
        runtime = {"error": f"{type(error).__name__}: {error}"}
    result = {"meta": _meta("llm", {"model": args.model, "model_digest": digest,
                                    "ollama_version": version, "model_details": details,
                                    "model_runtime": runtime,
                                    "planner_prompt_sha256": prompt_sha,
                                    "replay_from": args.replay_from,
                                    "pipeline": {"aggregation_grounding": args.aggregation_grounding,
                                                 "condition_check": args.condition_check,
                                                 "condition_notes": args.condition_notes,
                                                 "normalize_grounding": not args.no_normalize,
                                                 "semantic_reinterpretation": not args.no_semantic,
                                                 "provider": "mock", "tims_execution": "legacy",
                                                 "temperature": 0, "think": getattr(args, "model_think", "auto"),
                                                 "isolation": args.model_state,
                                                 **({"temperature": sampling["temperature"], "sampling": sampling}
                                                    if sampling is not None else {})},
                                    **({"environment": environment} if environment is not None else {}),
                                    "run_settings": settings,
                                    "item_order": [item["id"] for item in items],
                                    "run_spec": spec, "run_spec_sha256": spec_sha,
                                    **_continuity(rows, args.model_state),
                                    "chat_timeout_s": args.chat_timeout,
                                    "finished_at": datetime.now(ZoneInfo("Asia/Seoul")).isoformat(),
                                    "scorer_version": SCORER_VERSION}),
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


def _request_sha(messages):
    return hashlib.sha256(json.dumps(messages, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


class _SequenceClient:
    """기록된 모델 응답(계획·재질의)을 순서대로 돌려준다. 모델을 부르지 않는다.

    코드만 바꾼 후보(판정·수정 범위 guard)를 같은 모델 출력으로 다시 적용해 보려는 것이다. 기록보다 많은 호출이
    필요해지면(코드가 새 재질의를 요구) ``needs_live``로 표시하고 실패로 둔다. 기록에서 실패한 호출은 같은 오류로
    다시 실패시킨다.
    """

    def __init__(self, calls, model):
        self.calls = list(calls)
        self.model = model
        self.needs_live = False
        #: 호출마다 요청이 기록과 같은지: "same" / "changed" / "unknown"(기록에 hash 없음).
        self.request_match = []

    def chat(self, messages, tools=None, **kwargs):
        if not self.calls:
            self.needs_live = True
            raise RuntimeError("기록에 없는 모델 호출")
        call = self.calls.pop(0)
        recorded = call.get("request_sha256")
        self.request_match.append(
            "unknown" if recorded is None else "same" if recorded == _request_sha(messages) else "changed")
        if call.get("failed"):
            raise RuntimeError(call.get("error") or "기록된 호출 실패")
        return {"message": {"content": call["content"]}, "done_reason": "stop", "replayed": True}


def cmd_rerun(args):
    """기록된 모델 응답을 순서대로 넣어 이 코드로 다시 실행한다(모델 호출 없음, 격리 불필요)."""
    source = json.loads(Path(args.source).read_text(encoding="utf-8"))
    gold = {item["id"]: item for item in load_gold(GOLD_PATH)["items"]}
    from geoflow import providers
    from geoflow.pipeline import GeoFlowPipeline

    rows = []
    for row in source["rows"]:
        client = _SequenceClient(row.get("llm_calls") or [], source["meta"].get("model"))
        recorder = _RecordingClient(client)
        pipeline = GeoFlowPipeline.create(
            client=recorder, tool_executor=_executor(), clock=lambda: REFERENCE_DATE,
            condition_check=source["meta"].get("pipeline", {}).get("condition_check", True),
            condition_notes=False,
            execution_profile=providers.profile_for(providers.MOCK, providers.LEGACY))
        observed = run_item(pipeline, row["question"])
        category, checks = score(gold[row["id"]], observed)
        grounding_ok, grounding_diffs = grounding_check(gold[row["id"]], observed["grounding"])
        # 지연은 원 기록의 모델 호출 시간을 쓴다(다시 부르지 않았으므로). 쓰지 않은 기록 호출은 뺀다.
        used = recorder.calls
        for index, call in enumerate(used):
            if index < len(row.get("llm_calls") or []):
                call["duration_ms"] = row["llm_calls"][index].get("duration_ms", 0.0)
        rows.append({"id": row["id"], "question": row["question"],
                     "vendor_verdict": row.get("vendor_verdict", "-"), "category": category,
                     "checks": checks, "reset_ok": row.get("reset_ok"),
                     "grounding_ok": grounding_ok, "grounding_diffs": grounding_diffs,
                     "llm_calls": used, "needs_live": client.needs_live,
                     # 요청이 기록과 다르면(재질의 문구·경로 변경) 이 행은 모델 성능이 아니라 기록 응답의 코드 처리다.
                     "request_match": client.request_match, **observed})
    meta = dict(source["meta"])
    meta.update(_meta("llm", {}))
    meta.update({key: source["meta"].get(key) for key in (
        "model", "model_digest", "ollama_version", "planner_prompt_sha256", "pipeline", "chat_timeout_s")})
    meta["rerun_from"] = args.source
    result = {"meta": meta, "summary": _summary(rows), "rows": rows}
    _write(args.out, result)
    _print_summary(result)
    print("needs_live", sum(row["needs_live"] for row in rows))
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


def _rescored(path):
    """저장된 결과를 현재(최종) 채점기로 메모리에서 다시 채점한다. 파일은 바꾸지 않는다."""
    result = json.loads(Path(path).read_text(encoding="utf-8"))
    gold = {item["id"]: item for item in load_gold(
        HERE / result["meta"]["gold_file"] if result["meta"].get("gold_file") else None)["items"]}
    for row in result["rows"]:
        item = gold[row["id"]]
        row["expected_outcome"] = item.get("expected_outcome", "answered")
        if row["category"] != "no_gold_grounding":
            row["category"], row["checks"] = score(item, row)
        if result["meta"].get("kind") in ("llm", "llm_replay"):
            row["grounding_ok"], row["grounding_diffs"] = grounding_check(item, row.get("grounding"))
        row["result_class"] = result_class(row)
    return result


def _percentile(values, fraction):
    """최근접 순위 백분위수(보간 없음). 값이 없으면 None."""
    if not values:
        return None
    ordered = sorted(values)
    import math
    return ordered[max(0, math.ceil(fraction * len(ordered)) - 1)]


def run_statistics(result):
    """호출·지연·timeout·재시도. 긴 지연을 빼지 않는다. 기록이 없는 항목은 None."""
    rows = result["rows"]
    timeout_ms = float(result["meta"].get("chat_timeout_s") or 300.0) * 1000
    totals = [(row.get("planner_trace") or {}).get("durations", {}).get("total_ms")
              for row in rows]
    totals = [value for value in totals if value is not None]
    calls = [call for row in rows for call in row.get("llm_calls") or []]
    hidden = []
    for row in rows:
        total = (row.get("planner_trace") or {}).get("durations", {}).get("total_ms") or 0
        recorded = sum(call["duration_ms"] for call in row.get("llm_calls") or [])
        if not any(call.get("failed") for call in row.get("llm_calls") or []) \
                and total - recorded >= 0.9 * timeout_ms:
            # 실패한 호출을 기록하지 않던 평가기(v1)의 run. 기록된 호출 시간과 전체 시간의 차이가
            # timeout에 가까우면 timeout 뒤 재시도가 있었다고 본다(추정, 개수 = 차이 / timeout).
            hidden.append({"id": row["id"], "gap_s": round((total - recorded) / 1000, 1),
                           "estimated_timeouts": int((total - recorded) // (0.9 * timeout_ms))})
    started = [row["started_at"] for row in rows if row.get("started_at")]
    finished = [row["finished_at"] for row in rows if row.get("finished_at")]
    wall = None
    if started and finished and len(started) == len(rows):
        wall = round((datetime.fromisoformat(max(finished))
                      - datetime.fromisoformat(min(started))).total_seconds(), 1)
    return {
        "items": len(rows),
        "plan_calls": sum(1 for call in calls if call["kind"] == "plan" and not call.get("failed")),
        "repair_calls": sum(1 for call in calls
                            if call["kind"] == "repair" and not call.get("failed")),
        "failed_calls_recorded": sum(1 for call in calls if call.get("failed")),
        "timeouts_inferred": sum(item["estimated_timeouts"] for item in hidden),
        "timeout_rows_inferred": hidden,
        "rows_with_repair": sum(1 for row in rows if any(
            call["kind"] == "repair" for call in row.get("llm_calls") or [])),
        "latency_s": {
            "median": round(_percentile(totals, 0.5) / 1000, 1) if totals else None,
            "p90": round(_percentile(totals, 0.9) / 1000, 1) if totals else None,
            "max": round(max(totals) / 1000, 1) if totals else None,
            "sum": round(sum(totals) / 1000, 1) if totals else None,
        },
        "wall_clock_s": wall,
    }


def cmd_report(args):
    """변경 전후 결과를 같은 최종 채점기로 다시 채점해 분모·합계가 맞는 보고서를 쓴다."""
    lines = [f"# 결과 보고 (채점기 {SCORER_VERSION}, `evaluate_vendor100.py report`)", ""]
    correct = {"정상 답변", "정당한 거부"}
    for name, before_path, after_path in args.pair:
        before, after = _rescored(before_path), _rescored(after_path)
        old = {row["id"]: row for row in before["rows"]}
        new = {row["id"]: row for row in after["rows"]}
        if set(old) != set(new):
            raise SystemExit(f"{name}: 두 결과의 문항 id가 다릅니다")
        lines += [f"## {name}", "",
                  f"- 전: `{before_path}` (코드 `{before['meta'].get('code_commit', '')[:10]}`)",
                  f"- 후: `{after_path}` (코드 `{after['meta'].get('code_commit', '')[:10]}`)", "",
                  "| 결과 분류 | 전 | 후 |", "|---|---|---|"]
        for label in RESULT_CLASSES:
            lines.append(f"| {label} | {sum(1 for r in old.values() if r['result_class'] == label)}"
                         f" | {sum(1 for r in new.values() if r['result_class'] == label)} |")
        for rows in (old, new):
            assert sum(1 for r in rows.values() if r["result_class"] in RESULT_CLASSES) == len(rows)
        lines.append(f"| **합계(분모)** | {len(old)} | {len(new)} |")
        lines.append("")
        for label, result in (("전", before), ("후", after)):
            judged = [r for r in result["rows"] if r.get("grounding_ok") is not None]
            excluded = [r["id"] for r in result["rows"] if r.get("grounding_ok") is None]
            if result["meta"].get("kind") in ("llm", "llm_replay"):
                lines.append(f"- 최종 grounding 정확({label}, 조건 계층·정규화·재질의 뒤): "
                             f"{sum(1 for r in judged if r['grounding_ok'])}"
                             f"/{len(judged)}" + (f" — 제외 {', '.join(excluded)}(정답 grounding 없음)"
                                                  if excluded else ""))
        lines.append("")
        for label, result in (("전", before), ("후", after)):
            if result["meta"].get("kind") != "llm":
                continue
            stats = run_statistics(result)
            latency = stats["latency_s"]
            lines.append(
                f"- 호출·지연({label}): 계획 {stats['plan_calls']}, 재질의 {stats['repair_calls']}"
                f"(재질의한 문항 {stats['rows_with_repair']}), 실패 호출 기록 {stats['failed_calls_recorded']}, "
                f"timeout 추정 {stats['timeouts_inferred']}"
                + (f"({', '.join(i['id'] for i in stats['timeout_rows_inferred'])})"
                   if stats["timeout_rows_inferred"] else "")
                + f"; 문항 지연 중앙값 {latency['median']}초, p90 {latency['p90']}초, 최대 {latency['max']}초, "
                f"합계 {latency['sum']}초; 전체 경과 "
                + (f"{stats['wall_clock_s']}초" if stats["wall_clock_s"] is not None
                   else "기록 없음(평가기 v1)"))
        lines += ["", "| 전→후 | 문항 |", "|---|---|"]
        moves = {}
        for key in old:
            moves.setdefault((old[key]["result_class"], new[key]["result_class"]), []).append(key)
        fixed = sorted(k for k in old if old[k]["result_class"] not in correct
                       and new[k]["result_class"] in correct)
        regressed = sorted(k for k in old if old[k]["result_class"] in correct
                           and new[k]["result_class"] not in correct)
        for (a, b), keys in sorted(moves.items()):
            if a != b:
                lines.append(f"| {a} → {b} | {', '.join(sorted(keys))} |")
        lines += ["", f"- 새로 맞음 {len(fixed)}: {', '.join(fixed) or '-'}",
                  f"- 회귀(맞던 문항이 틀림) {len(regressed)}: {', '.join(regressed) or '-'}", ""]
        if args.items:
            lines += ["| 문항 | 기대 | 전 | 후 | 후 오류 코드 / 인자 차이 | grounding 전→후 |",
                      "|---|---|---|---|---|---|"]
            for key in old:
                a, b = old[key], new[key]
                detail = b.get("error_code") or ""
                if (b.get("checks") or {}).get("arg_mismatches"):
                    detail += " " + json.dumps(b["checks"]["arg_mismatches"], ensure_ascii=False)
                if (b.get("checks") or {}).get("place_lookup_count_ok") is False:
                    detail += " 장소 조회 횟수 불일치"
                lines.append(f"| {key} | {b['expected_outcome']} | {a['result_class']} | "
                             f"{b['result_class']} | {detail.strip()} | "
                             f"{a.get('grounding_ok')}→{b.get('grounding_ok')} |")
            lines.append("")
    text = "\n".join(lines) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    print(text)
    return 0


#: grounding 층. 모델 원출력에서 최종 grounding까지 한 층씩 더한다(재질의 전).
LAYERS = ("raw", "normalized", "preserved", "reinterpreted")
LAYER_LABELS = {
    "raw": "모델 원출력",
    "normalized": "형식 정규화 뒤(의미 불변)",
    "preserved": "조건 보존 뒤(날짜·유형·상태, 장소 근거)",
    "reinterpreted": "의미 재해석 뒤(측정값·관계·집계 다시 읽기)",
}


def _first_plan(row):
    return next((call.get("content") for call in row.get("llm_calls") or []
                 if call["kind"] == "plan" and not call.get("failed")), None)


def grounding_layers(item, row):
    """행 하나의 층별 (형식 유효, 의미 정확, 멈춘 코드). 기록된 원출력을 현재 코드로 다시 통과시킨다.

    각 층은 앞 층에 한 단계만 더한다. 재질의는 하지 않는다(재질의는 최종 grounding에만 반영된다).
    - raw: 원출력 payload 그대로. 형식 유효 = grounding 계약(parse, 정규화 끔)을 통과.
    - normalized: 의미를 바꾸지 않는 자리 바로잡기(parse 정규화).
    - preserved: + 조건 계층의 날짜·택시 유형·운행 상태 보존과 장소 근거 확인(의미 재해석 끔).
    - reinterpreted: + 측정값·사건·관계·집계 다시 읽기(grounding_v2 전체 경로).
    """
    from geoflow import conditions
    from geoflow.errors import PlannerError
    from geoflow.grounding import parse_grounding
    from geoflow.planner import parse_planner_json

    out = {}
    text = _first_plan(row)
    try:
        payload = parse_planner_json(text) if text else None
    except PlannerError as error:
        payload = None
        out["parse_error"] = error.code
    if not isinstance(payload, dict) or "concepts" not in payload:
        return {layer: {"valid": False, "ok": None if gold_grounding(item) is None else False,
                        "code": out.get("parse_error", "NO_PAYLOAD")} for layer in LAYERS}
    import inspect
    has_semantic = "semantic_reinterpretation" in inspect.signature(
        conditions.reconcile_payload).parameters
    for layer in LAYERS:
        if layer == "reinterpreted" and not has_semantic:
            # 이 코드에는 의미 재해석이 없다(grounding_v3). 조건 보존 층과 같다.
            out[layer] = dict(out["preserved"], absent_in_code=True)
            continue
        try:
            current = payload
            if layer in ("preserved", "reinterpreted"):
                options = ({"semantic_reinterpretation": layer == "reinterpreted"}
                           if has_semantic else {})
                current, _ = conditions.reconcile_payload(
                    payload, item["question"], reference_date=REFERENCE_DATE, raw_text=text,
                    **options)
            grounding = parse_grounding(current, item["question"], raw_text=text,
                                        normalize=layer != "raw")
            view_source = current if layer == "raw" else grounding.to_dict()
            ok, diffs = grounding_check(item, view_source)
            out[layer] = {"valid": True, "ok": ok, "code": None, "diffs": diffs}
        except PlannerError as error:
            # 형식 무효라도 의미 정확도는 원출력 payload로 따로 본다(raw만).
            ok = grounding_check(item, current if layer == "raw" else None)[0] \
                if layer == "raw" else (None if gold_grounding(item) is None else False)
            out[layer] = {"valid": False, "ok": ok, "code": error.code}
        except AssertionError as error:
            out[layer] = {"valid": False, "ok": False, "code": f"ASSERTION: {error}"}
    return out


def cmd_layers(args):
    """층별 grounding 성능과 보정의 이득·훼손. LLM을 부르지 않는다(기록된 원출력 재통과)."""
    lines = ["# grounding 층별 성능 (`evaluate_vendor100.py layers`)", "",
             "원출력(`llm_calls`의 첫 계획 응답)을 현재 코드의 각 층에 다시 통과시킨다. 재질의는 하지 않는다.",
             "의미 정확 = 정답 grounding과 같은 측정값·장소(이름·지역·역할)·scope·factor(기본값 정규화).", ""]
    for name, path in args.run:
        result = _rescored(path)
        gold = {item["id"]: item for item in load_gold(
            HERE / result["meta"]["gold_file"] if result["meta"].get("gold_file") else None)["items"]}
        rows = result["rows"]
        layers = {row["id"]: grounding_layers(gold[row["id"]], row) for row in rows}
        judged = [row["id"] for row in rows if gold_grounding(gold[row["id"]]) is not None]
        lines += [f"## {name}", "", f"`{path}` · 의미 정확 분모 {len(judged)}"
                  f"(정답 grounding 없는 {len(rows) - len(judged)}문항 제외)", "",
                  "| 층 | 형식 유효 | 의미 정확 | 앞 층 대비 고침 | 앞 층 대비 훼손 |", "|---|---|---|---|---|"]
        previous = None
        for layer in LAYERS:
            valid = sum(1 for key in layers if layers[key][layer]["valid"])
            ok = sum(1 for key in judged if layers[key][layer]["ok"])
            fixed = damaged = "-"
            if previous:
                fixed = sorted(k for k in judged if layers[k][layer]["ok"] and not layers[k][previous]["ok"])
                damaged = sorted(k for k in judged if not layers[k][layer]["ok"] and layers[k][previous]["ok"])
                fixed = f"{len(fixed)} {', '.join(fixed)}".strip()
                damaged = f"{len(damaged)} {', '.join(damaged)}".strip()
            lines.append(f"| {LAYER_LABELS[layer]} | {valid}/{len(rows)} | {ok}/{len(judged)} | "
                         f"{fixed} | {damaged} |")
            previous = layer
        final_ok = sum(1 for row in rows if row.get("grounding_ok"))
        correct = sum(1 for row in rows if row["result_class"] in ("정상 답변", "정당한 거부"))
        # 재질의의 고침·훼손: 마지막 보정 층(재질의 전)과 최종 grounding(재질의 후)을 비교한다.
        by_id = {row["id"]: row for row in rows}
        last = "preserved"
        gained = sorted(k for k in judged if by_id[k].get("grounding_ok") and not layers[k][last]["ok"])
        lost = sorted(k for k in judged if not by_id[k].get("grounding_ok") and layers[k][last]["ok"])
        lines += ["", f"- 재질의 전({LAYER_LABELS[last]}) → 최종 grounding: 고침 {len(gained)} {', '.join(gained)} / "
                  f"훼손 {len(lost)} {', '.join(lost)}"]
        lines += [f"- 이 run의 최종 grounding(그 run의 경로 + 재질의) 정확: {final_ok}/{len(judged)}",
                  f"- 이 run의 최종 호출·답변 맞음(정상 답변 + 정당한 거부): {correct}/{len(rows)}", ""]
        if args.json:
            Path(args.json).parent.mkdir(parents=True, exist_ok=True)
            with open(args.json, "a", encoding="utf-8") as handle:
                handle.write(json.dumps({"name": name, "path": path, "layers": layers},
                                        ensure_ascii=False, default=str) + "\n")
    text = "\n".join(lines) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    print(text)
    return 0


def _resolve_place(name, region):
    """장소 이름을 실행기(mock 제공자)로 푼 scope. 풀리지 않으면 이름 그대로. grounding 층 비교용."""
    executor = _gold_scopes.executor = getattr(_gold_scopes, "executor", None) or _executor()
    result = executor.execute("get_place_scope", {"name": name, **({"region": region} if region else {})})
    return result if isinstance(result, str) else f"name:{name}|{region or ''}"


def _od_view(payload, trip=True):
    """(장소 끝 집합, 묶는 끝). 장소 끝 = {(장소 scope, pickup|dropoff)}; od_role both는 두 끝으로 편다.

    묶는 끝은 dimension이 있을 때만 본다. 생략은 schema 기본값 both다(실행 계약과 같다).
    """
    if not payload or not isinstance(payload, dict) or "concepts" not in payload:
        return None
    ends = set()
    for concept in payload.get("concepts") or []:
        if concept.get("concept") != "LOCATION" or concept.get("role") == "MEASURE":
            continue
        role = (concept.get("attributes") or {}).get("od_role") or concept.get("od_role")
        value = concept.get("value")
        if concept.get("subtype") == "place" and isinstance(value, dict):
            where = _resolve_place(value.get("name"), value.get("region"))
        else:
            where = str(value)
        for end in ({"pickup", "dropoff"} if role == "both" else {role or "-"}):
            ends.add((where, end))
    factors = payload.get("factors") or {}
    target = (factors.get("dimension_target") or "both") if factors.get("dimension") else None
    return frozenset(ends), target


def _od_call_view(call):
    args = call.get("args") or {}
    ends = {(args[key], end) for key, end in (("scope_pickup", "pickup"), ("scope_dropoff", "dropoff"))
            if key in args}
    target = (args.get("dimension_target") or "both") if args.get("dimension") else None
    return frozenset(ends), target


OD_LAYERS = ("raw", "normalized", "preserved", "repaired", "final_call")


def od_layers(item, row):
    """trip 건수 문항의 층별 (장소 끝 맞음, 묶는 끝 맞음, 둘 다). trip 건수 문항이 아니면 None.

    - raw/normalized/preserved: 첫 계획 원출력을 현재 코드의 각 층에 다시 통과(``grounding_layers``와 같은 층).
    - repaired: 이 run의 최종 grounding(재질의 반영).
    - final_call: 실행된 get_trip_count 인자(장소는 scope 값).
    """
    from geoflow import conditions
    from geoflow.errors import PlannerError
    from geoflow.grounding import parse_grounding
    from geoflow.planner import parse_planner_json

    gold_calls = item.get("gold") or []
    if not any(call["tool"] == "get_trip_count" for call in gold_calls) or \
            item.get("expected_outcome", "answered") != "answered":
        return None
    want = _od_view(gold_grounding(item))
    out = {}

    def judge(view):
        if view is None:
            return {"ends": False, "target": False, "both": False}
        ends_ok, target_ok = view[0] == want[0], view[1] == want[1]
        return {"ends": ends_ok, "target": target_ok, "both": ends_ok and target_ok}

    text = _first_plan(row)
    try:
        payload = parse_planner_json(text) if text else None
    except PlannerError:
        payload = None
    for layer in ("raw", "normalized", "preserved"):
        view = None
        if isinstance(payload, dict) and "concepts" in payload:
            try:
                current = payload
                if layer == "preserved":
                    current, _ = conditions.reconcile_payload(
                        payload, item["question"], reference_date=REFERENCE_DATE, raw_text=text)
                view = _od_view(current if layer == "raw" else parse_grounding(
                    current, item["question"], raw_text=text).to_dict())
            except PlannerError:
                view = _od_view(payload) if layer == "raw" else None
        out[layer] = judge(view)
    out["repaired"] = judge(_od_view(row.get("grounding")))
    trip = [call for call in row.get("calls") or [] if call["tool"] == "get_trip_count"]
    # 최종 호출은 scope 값으로 비교한다. 정답 쪽도 정답 조회를 실행기에 넣은 scope로 바꾼다.
    gold_places = [call for call in gold_calls if call["tool"] == "get_place_scope"]
    gold_scope = _gold_scopes(gold_places)
    gold_final = [call for call in gold_calls if call["tool"] == "get_trip_count"][-1]
    gold_args = {}
    for key, value in gold_final["args"].items():
        match = _BINDING.match(str(value))
        gold_args[key] = gold_scope[gold_places.index(_binding_place(match.group(1), gold_places))] \
            if match else value
    want_call = _od_call_view({"args": gold_args})
    if trip and row.get("outcome") == "answered":
        got = _od_call_view(trip[-1])
        out["final_call"] = {"ends": got[0] == want_call[0], "target": got[1] == want_call[1],
                             "both": got == want_call}
    else:
        out["final_call"] = {"ends": False, "target": False, "both": False}
    return out


def axes_rows(path):
    """저장된 run 하나를 v3 범주와 축별 채점으로 다시 본다. 파일은 바꾸지 않는다."""
    result = _rescored(path)
    gold = {item["id"]: item for item in load_gold(
        HERE / result["meta"]["gold_file"] if result["meta"].get("gold_file") else None)["items"]}
    rows = []
    for row in result["rows"]:
        item = gold[row["id"]]
        category, checks = (score_semantic(item, row) if row["category"] != "no_gold_grounding"
                            else (row["category"], {}))
        v4 = dict(row, category=category)
        rows.append({"id": row["id"], "v3": row["result_class"], "v4": result_class(v4),
                     "v4_checks": checks, "v3_checks": row.get("checks"),
                     "path": execution_path(item, row) if row.get("outcome") == "answered" else None,
                     "cost": run_cost(row), "od": od_layers(item, row),
                     "outcome": row.get("outcome"), "error_code": row.get("error_code"),
                     "grounding_ok": row.get("grounding_ok")})
    return result["meta"], rows


def _axes_summary(rows):
    from collections import Counter
    v3, v4 = Counter(r["v3"] for r in rows), Counter(r["v4"] for r in rows)
    answered = [r for r in rows if r["v4"] == "정상 답변"]
    costs = [r["cost"] for r in rows]
    totals = sorted(c["total_ms"] or 0 for c in costs)
    od = [r["od"] for r in rows if r["od"]]
    summary = {
        "items": len(rows), "v3": dict(v3), "v4": dict(v4),
        "v4_normal_clean_path": sum(1 for r in answered if r["path"] and r["path"]["clean"]),
        "v4_normal_failed_lookup": sum(1 for r in answered if r["path"] and r["path"]["failed_lookups"]),
        "v4_normal_discarded_or_dup": sum(1 for r in answered if r["path"] and (
            r["path"]["discarded_lookups"] or r["path"]["duplicate_lookups"])),
        "plan_calls": sum(c["plan_calls"] for c in costs),
        "repair_calls": sum(c["repair_calls"] for c in costs),
        "failed_calls": sum(c["failed_calls"] for c in costs),
        "repairs": sum(c["repairs"] for c in costs),
        "repair_failed": sum(c["repair_failed"] for c in costs),
        "items_with_repair": sum(1 for c in costs if c["repairs"]),
        "normal_with_repair": sum(1 for r in answered if r["cost"]["repairs"]),
        "total_s": round(sum(totals) / 1000), "median_s": round(totals[len(totals) // 2] / 1000, 1)
        if totals else None,
        "p90_s": round(totals[min(len(totals) - 1, int(0.9 * len(totals)))] / 1000, 1) if totals else None,
        "max_s": round(totals[-1] / 1000, 1) if totals else None,
        "truncated": sum(c["truncated"] for c in costs),
        "eval_tokens": sum(c["eval_tokens"] or 0 for c in costs) if any(
            c["eval_tokens"] is not None for c in costs) else None,
        "od_items": len(od),
        "od": {layer: {key: sum(1 for o in od if o[layer][key]) for key in ("ends", "target", "both")}
               for layer in OD_LAYERS} if od else {},
    }
    return summary


def cmd_axes(args):
    """여러 run을 같은 축별 채점으로 비교한다(모델 호출 없음). 원 결과 파일은 바꾸지 않는다."""
    report = {"scorer": {"v3": SCORER_VERSION, "axes": SEMANTIC_SCORER_VERSION}, "runs": {}}
    lines = [f"# 축별 채점 (`evaluate_vendor100.py axes`, v3 + {SEMANTIC_SCORER_VERSION})", ""]
    for name, *paths in args.run:
        rows, metas = [], []
        for path in paths:
            meta, part = axes_rows(path)
            for row in part:
                row["set"] = Path(path).stem
            rows += part
            metas.append({key: meta.get(key) for key in ("code_commit", "model", "model_digest",
                                                          "planner_prompt_sha256", "ollama_version",
                                                          "gold_file", "options")})
        summary = _axes_summary(rows)
        report["runs"][name] = {"paths": paths, "meta": metas, "summary": summary, "rows": rows}
        changed = [r for r in rows if r["v3"] != r["v4"]]
        lines += [f"## {name}", "", f"- 문항 {summary['items']}; v3 {summary['v3']}",
                  f"- 축별 {summary['v4']}",
                  f"- v3 → 축별 바뀐 문항 {len(changed)}: " + ", ".join(
                      f"{r['set']}/{r['id']}({r['v3']}→{r['v4']}; 경로 {r['path'] and r['path']['lookup_kinds']})"
                      for r in changed), ""]
    text = "\n".join(lines) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    if args.json:
        Path(args.json).write_text(json.dumps(report, ensure_ascii=False, indent=1, default=list),
                                   encoding="utf-8")
    print(text)
    return 0


def cmd_gold_audit(args):
    """정답 grounding을 조건 계층에 통과시켜 훼손 여부를 본다(실행기 평가와 별개). LLM 없음."""
    from geoflow import conditions
    from geoflow.errors import PlannerError

    lines = ["# 정답 grounding의 보정 계층 통과 (`evaluate_vendor100.py gold-audit`)", "",
             "정답 grounding은 이미 맞다. 여기서 바뀌거나 멈춘 것은 모두 보정의 훼손이다. 정답 grounding을 실행기에",
             "넣는 평가(`gold`)와 다르다. 한쪽으로 다른 쪽의 정확성을 주장하지 않는다.", "",
             "| 셋 | 정답 grounding | 조건 보존만: 바뀜 / 멈춤 | 의미 재해석까지: 바뀜 / 멈춤 |",
             "|---|---|---|---|"]
    for path in args.gold_files:
        items = [item for item in load_gold(path)["items"] if gold_grounding(item) is not None]
        cells = []
        import inspect
        has_semantic = "semantic_reinterpretation" in inspect.signature(
            conditions.reconcile_payload).parameters
        for semantic in (False, True):
            if semantic and not has_semantic:
                cells.append("(이 코드에 없음)")
                continue
            changed, stopped = [], []
            for item in items:
                try:
                    _, audit = conditions.reconcile_payload(
                        gold_grounding(item), item["question"], reference_date=REFERENCE_DATE,
                        **({"semantic_reinterpretation": semantic} if has_semantic else {}))
                except PlannerError as error:
                    if item.get("expected_outcome", "answered") == "answered":
                        stopped.append(f"{item['id']}({error.code})")
                    continue
                if audit["corrections"]:
                    changed.append(item["id"] + "(" + ",".join(
                        f"{c['condition']}:{c['from']}→{c['to']}" for c in audit["corrections"]) + ")")
            cells.append(f"{len(changed)} {' '.join(changed)} / {len(stopped)} {' '.join(stopped)}")
        lines.append(f"| `{path}` | {len(items)} | {cells[0]} | {cells[1]} |")
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


def build_parser():
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
    llm.add_argument("--condition-check", action="store_true",
                     help="질문 원문으로 날짜·택시 유형·운행 상태를 다시 정한다(geoflow/conditions.py)")
    llm.add_argument("--condition-notes", action="store_true",
                     help="조건 계층의 감사 문구를 답변에 덧붙인다(CLI --condition-check와 같음)")
    llm.add_argument("--no-normalize", action="store_true",
                     help="장소 값 자리 바로잡기를 끈다(이전 동작)")
    llm.add_argument("--aggregation-grounding", default="flat", choices=("flat", "structured"),
                     help="집계를 적는 grounding 계약(flat factor 또는 구조화 aggregation_plan)")
    llm.add_argument("--no-semantic", action="store_true",
                     help="조건 계층의 의미 재해석(측정값·관계·집계 다시 읽기)을 끈다. 날짜·유형·상태 보존과 "
                          "장소 근거 확인은 그대로다")
    llm.add_argument("--model-think", choices=("auto", "on", "off"), default="auto",
                     help="Ollama /api/chat의 think. auto(기본)는 payload에 넣지 않는다(이전 평가와 같은 요청). "
                          "on/off는 think=true/false를 넣는다")
    llm.add_argument("--reference-date", type=date.fromisoformat, default=REFERENCE_DATE,
                     help="상대 날짜를 풀 기준일(조건 계층·컴파일·채점에 같이 쓴다). 기본 2026-09-25(정답 셋의 기준일)")
    llm.add_argument("--model-state", choices=MODEL_STATES, default=MODEL_STATES[0],
                     help="unload_per_question: 문항마다 모델을 내리고 실행(기존 평가 조건). "
                          "keep_loaded: 시작할 때만 내리고 모델을 올린 채 연속 실행(CLI 연속 사용과 같은 서버 조건)")
    llm.add_argument("--resume-new-session", action="store_true",
                     help="keep_loaded run을 중단 뒤 이어 실행할 때 나머지를 별도 세션으로 기록한다(순수 연속 아님으로 표시)")
    llm.add_argument("--order", default="file",
                     help="문항 순서: file(기본), reverse, shuffle:SEED")
    llm.add_argument("--replay-from", default=None,
                     help="이전 llm 결과의 계획 응답을 prompt hash가 같을 때 재생(나머지는 실제 호출)")
    llm.add_argument("--temperature", type=float, default=None,
                     help="sampling(path_repeat_001). 지정하지 않으면 기존 temperature 0 요청. --top-p·--top-k·--seed와 함께 쓴다")
    llm.add_argument("--top-p", type=float, default=None)
    llm.add_argument("--top-k", type=int, default=None)
    llm.add_argument("--seed", type=int, default=None,
                     help="회차 seed. 호출 seed는 call_seed(회차 seed, 문항 id, 호출 순번)")
    llm.add_argument("--record-env", action="store_true",
                     help="meta에 host GPU 이름·UUID·드라이버와 Ollama 컨테이너 GPU를 남긴다(생성에는 영향 없음)")
    rerun = sub.add_parser("rerun")
    rerun.add_argument("source")
    rerun.add_argument("--out", required=True)
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
    layers = sub.add_parser("layers")
    layers.add_argument("--run", nargs=2, action="append", required=True, metavar=("NAME", "RUN"))
    layers.add_argument("--out", default="")
    layers.add_argument("--json", default="")
    axes = sub.add_parser("axes")
    axes.add_argument("--run", nargs="+", action="append", required=True, metavar="NAME RUN",
                      help="이름 다음에 결과 파일 여러 개(셋마다 하나)")
    axes.add_argument("--out", default="")
    axes.add_argument("--json", default="")
    gold_audit = sub.add_parser("gold-audit")
    gold_audit.add_argument("gold_files", nargs="+")
    gold_audit.add_argument("--out", default="")
    report = sub.add_parser("report")
    report.add_argument("--pair", nargs=3, action="append", required=True,
                        metavar=("NAME", "BEFORE", "AFTER"))
    report.add_argument("--items", action="store_true", help="문항별 표를 덧붙인다")
    report.add_argument("--out", default="")
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    global GOLD_PATH
    GOLD_PATH = Path(args.gold).resolve() if args.gold else None
    return {"extract": cmd_extract, "gold": cmd_gold, "llm": cmd_llm, "replay": cmd_replay,
            "rerun": cmd_rerun,
            "rescore": cmd_rescore, "compare": cmd_compare,
            "report": cmd_report, "layers": cmd_layers,
            "gold-audit": cmd_gold_audit, "axes": cmd_axes}[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
