# -*- coding: utf-8 -*-
"""D(현행) vs T(taxi_type 구분)를 boundary 전체에서 paired로 잰다."""
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


TAXI_MEANING = (
    '택시 영업 유형을 제한하는 조건이며 개념이 아니다. "개인택시", "법인택시"는\n'
    "    별도 개념 node로 만들지 않고 이 조건으로만 적는다.\n"
    '    예: "법인택시의 평균 운행시간" → EVENT/operation + AMOUNT/hours +\n'
    "    taxi_type=corporate (OBJECT/corporate, OBJECT/taxi_type으로 적지 않는다)"
)
D = GeoFlowPlanner(client=_Stub()).system_prompt()
_orig = F.FACTOR_SPECS["taxi_type"]
F.FACTOR_SPECS["taxi_type"] = dataclasses.replace(_orig, meaning=TAXI_MEANING)
T = GeoFlowPlanner(client=_Stub()).system_prompt()
F.FACTOR_SPECS["taxi_type"] = _orig

PROMPTS = {"D": D, "T": T}
for name, text in PROMPTS.items():
    print(f"[prompt] {name}: sha256={hashlib.sha256(text.encode()).hexdigest()[:16]} "
          f"chars={len(text)}", flush=True)
assert hashlib.sha256(D.encode()).hexdigest().startswith("64bbceb4e171085f")
assert hashlib.sha256(T.encode()).hexdigest().startswith("f268b2b28feb8b29")


class FixedPromptPlanner(GeoFlowPlanner):
    fixed_prompt = ""

    def system_prompt(self):
        return self.fixed_prompt


queries = list(load_queries("stub_query_boundary.yaml"))
for item in load_queries("stub_query.yaml"):
    if item["id"].startswith("q27"):
        queries.append(item)
        break
RUNS = 5
OUT = "/tmp/claude-1005/-home-hwkim-assistant-univ/e8c0baf4-9410-41f3-a18c-521c3cf55e4e/scratchpad/full_taxi_ab.jsonl"

client = OllamaClient("http://localhost:11434", "qwen3:8b", {"temperature": 0},
                      chat_timeout=300)
planners = {}
for name, text in PROMPTS.items():
    planner = FixedPromptPlanner(client=client)
    planner.fixed_prompt = text
    planners[name] = planner
composer = MacroComposer(MacroLibrary.from_directory())
print(f"[setup] {len(queries)} x {RUNS} x 2 = {len(queries)*RUNS*2} calls", flush=True)

fh = open(OUT, "w", encoding="utf-8")
t0 = time.perf_counter()
for rep in range(1, RUNS + 1):
    for index, item in enumerate(queries):
        order = ("D", "T") if (rep + index) % 2 == 0 else ("T", "D")
        for variant in order:
            record = E.evaluate_once(
                planners[variant], composer, item,
                attempt=rep, variant=variant,
                system_prompt_chars=len(PROMPTS[variant]),
            )
            fh.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
            fh.flush()
        print(f"[rep {rep}] {item['id']:<40} {time.perf_counter()-t0:6.0f}s", flush=True)
fh.close()
print("FULL TAXI AB DONE", flush=True)
