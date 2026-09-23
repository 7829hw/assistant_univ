# -*- coding: utf-8 -*-
"""Commit C prompt vs Commit D prompt를 paired/interleaved로 비교한다.

같은 질문·같은 반복 안에서 두 변형을 인접하게 실행한다. 변형별로 몰아서
돌리면 모델의 시간 변동과 섞여 구분할 수 없다. 실행 순서도 번갈아 바꿔
"먼저 실행된 쪽"이 유리해지는 효과를 줄인다.
"""
import json, sys, time
sys.path.insert(0, "/home/hwkim/assistant_univ")

import evaluate_planner as E
from geoflow.composer import MacroComposer
from geoflow.macros import MacroLibrary
from ollama_client import OllamaClient
from query_loader import load_queries

HOST = "http://localhost:11434"
MODEL = "qwen3:8b"
TIMEOUT = 300
REPEATS = 5
OUT = "/tmp/claude-1005/-home-hwkim-assistant-univ/e8c0baf4-9410-41f3-a18c-521c3cf55e4e/scratchpad/paired_ab.jsonl"

queries = load_queries("stub_query_boundary.yaml")
# q27은 OD 재질의 경로를 보는 유일한 질의라 stub set에서 함께 가져온다.
for item in load_queries("stub_query.yaml"):
    if item["id"].startswith("q27"):
        queries = list(queries) + [item]
        break

client = OllamaClient(HOST, MODEL, {"temperature": 0}, chat_timeout=TIMEOUT)
planners = {v: E.make_variant_planner(v, client) for v in ("C", "D")}
composer = MacroComposer(MacroLibrary.from_directory())
chars = {v: len(p.system_prompt()) for v, p in planners.items()}
print(f"[setup] {len(queries)} queries x {REPEATS} reps x 2 variants "
      f"= {len(queries)*REPEATS*2} calls; prompt chars {chars}", flush=True)

fh = open(OUT, "w", encoding="utf-8")
t_start = time.perf_counter()
for rep in range(1, REPEATS + 1):
    for index, item in enumerate(queries):
        # 순서 효과를 줄이려고 질문·반복마다 교대한다. 난수를 쓰지 않으므로
        # 재실행해도 같은 순서가 나온다.
        order = ("C", "D") if (rep + index) % 2 == 0 else ("D", "C")
        for variant in order:
            record = E.evaluate_once(
                planners[variant], composer, item,
                attempt=rep, variant=variant,
                system_prompt_chars=chars[variant],
            )
            record["order_position"] = order.index(variant) + 1
            fh.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
            fh.flush()
        print(f"[rep {rep}] {item['id']:<40} order={'/'.join(order)} "
              f"elapsed={time.perf_counter()-t_start:6.0f}s", flush=True)
fh.close()
print("PAIRED AB DONE", flush=True)
