# -*- coding: utf-8 -*-
"""taxi_type cohort만 paired로 잰다. 제품 코드는 건드리지 않는다.

D0 = 현재 production prompt
T  = production + taxi_type이 개념이 아니라 조건이라는 구분
T2 = T + subtype이 없는 core concept은 쓰지 않는다는 한 줄
"""
import dataclasses, hashlib, json, sys, time
sys.path.insert(0, "/home/hwkim/assistant_univ")

import evaluate_planner as E
from geoflow import factors as F
from geoflow.composer import MacroComposer
from geoflow.macros import MacroLibrary
from geoflow.planner import GeoFlowPlanner
from geoflow.types import CONCEPT_SUBTYPES
from ollama_client import OllamaClient
from query_loader import load_queries


class _Stub:
    model = "probe"


# --- 세 prompt를 문자열로 먼저 확정한다 ------------------------------------
TAXI_MEANING = (
    '택시 영업 유형을 제한하는 조건이며 개념이 아니다. "개인택시", "법인택시"는\n'
    "    별도 개념 node로 만들지 않고 이 조건으로만 적는다.\n"
    '    예: "법인택시의 평균 운행시간" → EVENT/operation + AMOUNT/hours +\n'
    "    taxi_type=corporate (OBJECT/corporate, OBJECT/taxi_type으로 적지 않는다)"
)

D0 = GeoFlowPlanner(client=_Stub()).system_prompt()

_original = F.FACTOR_SPECS["taxi_type"]
F.FACTOR_SPECS["taxi_type"] = dataclasses.replace(_original, meaning=TAXI_MEANING)
T = GeoFlowPlanner(client=_Stub()).system_prompt()
F.FACTOR_SPECS["taxi_type"] = _original

# subtype이 비어 있는 core concept은 어휘 정의에서 읽는다.
_empty = sorted(c.value for c, subs in CONCEPT_SUBTYPES.items() if not subs)
_NOTE = ("\n" + "와 ".join(_empty)
         + "는 TIMS에서 쓸 수 있는 subtype이 없으므로 개념으로 적지 않습니다.")
_ANCHOR = "\n\nTIMS 고유 개념은 새 core concept가 아니라 subtype으로 표현합니다."
assert _ANCHOR in T, "core concept 절 anchor를 찾지 못했다"
T2 = T.replace(_ANCHOR, _NOTE + _ANCHOR, 1)

PROMPTS = {"D0": D0, "T": T, "T2": T2}
for name, text in PROMPTS.items():
    print(f"[prompt] {name:<3} sha256={hashlib.sha256(text.encode()).hexdigest()[:16]} "
          f"chars={len(text)}", flush=True)
assert hashlib.sha256(D0.encode()).hexdigest().startswith("64bbceb4e171085f"), \
    "D0가 production prompt와 다르다"


class FixedPromptPlanner(GeoFlowPlanner):
    """미리 확정한 prompt 문자열만 돌려준다."""

    fixed_prompt = ""

    def system_prompt(self):
        return self.fixed_prompt


# --- 대상 -------------------------------------------------------------------
COHORT = ("b05", "b10", "b14", "b24")          # taxi_type이 나오는 전부
CONTROL = ("b11", "b20", "b21")                # 관계 재질의 / 거부 안전성 / factor 경로
queries = [q for q in load_queries("stub_query_boundary.yaml")
           if q["id"][:3] in COHORT + CONTROL]
queries.sort(key=lambda q: q["id"])
RUNS = 10
OUT = "/tmp/claude-1005/-home-hwkim-assistant-univ/e8c0baf4-9410-41f3-a18c-521c3cf55e4e/scratchpad/taxi_probe.jsonl"

client = OllamaClient("http://localhost:11434", "qwen3:8b", {"temperature": 0},
                      chat_timeout=300)
planners = {}
for name, text in PROMPTS.items():
    planner = FixedPromptPlanner(client=client)
    planner.fixed_prompt = text
    planners[name] = planner
composer = MacroComposer(MacroLibrary.from_directory())
order_base = list(PROMPTS)
print(f"[setup] {len(queries)} queries x {RUNS} runs x {len(PROMPTS)} variants "
      f"= {len(queries)*RUNS*len(PROMPTS)} calls", flush=True)

fh = open(OUT, "w", encoding="utf-8")
t0 = time.perf_counter()
for run in range(1, RUNS + 1):
    for index, item in enumerate(queries):
        # 질문·반복마다 변형 순서를 돌려 순서 효과를 줄인다.
        shift = (run + index) % len(order_base)
        for variant in order_base[shift:] + order_base[:shift]:
            record = E.evaluate_once(
                planners[variant], composer, item,
                attempt=run, variant=variant,
                system_prompt_chars=len(PROMPTS[variant]),
            )
            fh.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
            fh.flush()
        print(f"[run {run}] {item['id']:<40} {time.perf_counter()-t0:6.0f}s", flush=True)
fh.close()
print("TAXI PROBE DONE", flush=True)
