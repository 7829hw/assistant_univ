# -*- coding: utf-8 -*-
"""시간 표현 cohort를 paired로 잰다. 변형은 인자로 고른다.

    python time_probe.py <출력파일> <변형이름>...
변형은 PROMPT_BUILDERS에 정의된 것만 쓴다.
"""
import dataclasses, hashlib, json, sys, time
sys.path.insert(0, "/home/hwkim/assistant_univ")

import evaluate_planner as E
from geoflow import factors as F
from geoflow.composer import MacroComposer
from geoflow.macros import MacroLibrary
from geoflow.planner import GeoFlowPlanner
from ollama_client import OllamaClient
from query_loader import load_queries


class _Stub:
    model = "probe"


def _with(name, **changes):
    """factor 정의 하나만 바꿔 prompt를 만든다. 제품 상태는 되돌린다."""
    original = F.FACTOR_SPECS[name]
    F.FACTOR_SPECS[name] = dataclasses.replace(original, **changes)
    try:
        return GeoFlowPlanner(client=_Stub()).system_prompt()
    finally:
        F.FACTOR_SPECS[name] = original


#: taxi_type 개선 이전 상태. 회귀가 실제로 생긴 것인지 확인하는 대조군이다.
D_PRE = _with("taxi_type", meaning="택시 유형 조건.")
T0 = GeoFlowPlanner(client=_Stub()).system_prompt()

#: 후보 W. dimension이 필터가 아니라 그룹 기준이라는 것만 덧붙인다.
W_DIMENSION = (
    "결과를 어떤 범주별로 나눠 돌려줄지 정하는 그룹 기준이며 기간을 고르는\n"
    "    조건이 아니다. 질문이 결과를 나눠 보여 달라고 할 때만 넣는다.\n"
    "    특정 기간만 보려는 표현은 date 조건으로 적는다.\n"
    "    지정하면 단일 값이 아니라 그룹별 분포를 얻는다. bucket과 함께 쓸 수 없다."
)
W = _with("dimension", meaning=W_DIMENSION)

PROMPT_BUILDERS = {"D_PRE": D_PRE, "T0": T0, "W": W}

OUT = sys.argv[1]
NAMES = sys.argv[2:] or ["D_PRE", "T0"]
PROMPTS = {n: PROMPT_BUILDERS[n] for n in NAMES}
for n, t in PROMPTS.items():
    print(f"[prompt] {n:<6} sha256={hashlib.sha256(t.encode()).hexdigest()[:16]} "
          f"chars={len(t)}", flush=True)


class FixedPromptPlanner(GeoFlowPlanner):
    fixed_prompt = ""

    def system_prompt(self):
        return self.fixed_prompt


#: 주말 / 요일별 / 지난달 / 주 단위 / 월 단위 / 특정 날짜 + taxi_type 대조
WANT = ("b16", "b04", "b08", "b21", "b24", "b10")
queries = [q for q in load_queries("stub_query_boundary.yaml") if q["id"][:3] in WANT]
for item in load_queries("stub_query.yaml"):
    if item["id"].startswith(("q01", "q18")):
        queries.append(item)
queries.sort(key=lambda q: q["id"])
RUNS = 10

client = OllamaClient("http://localhost:11434", "qwen3:8b", {"temperature": 0},
                      chat_timeout=300)
planners = {}
for n, t in PROMPTS.items():
    pl = FixedPromptPlanner(client=client)
    pl.fixed_prompt = t
    planners[n] = pl
composer = MacroComposer(MacroLibrary.from_directory())
order = list(PROMPTS)
print(f"[setup] {len(queries)} x {RUNS} x {len(order)} = "
      f"{len(queries)*RUNS*len(order)} calls", flush=True)
for q in queries:
    print(f"   - {q['id']}: {q['question']}", flush=True)

fh = open(OUT, "w", encoding="utf-8")
t0 = time.perf_counter()
for run in range(1, RUNS + 1):
    for index, item in enumerate(queries):
        shift = (run + index) % len(order)
        for variant in order[shift:] + order[:shift]:
            rec = E.evaluate_once(planners[variant], composer, item,
                                  attempt=run, variant=variant,
                                  system_prompt_chars=len(PROMPTS[variant]))
            fh.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
            fh.flush()
        print(f"[run {run}] {item['id']:<40} {time.perf_counter()-t0:6.0f}s", flush=True)
fh.close()
print("TIME PROBE DONE", flush=True)
