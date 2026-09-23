# -*- coding: utf-8 -*-
"""block 설계로 D_PRE vs T0를 다시 잰다.

번갈아 실행하면 앞선 요청의 서버 상태가 뒤 요청을 망친다는 것이 확인됐으므로,
한 변형을 통째로 돌린 뒤 다른 변형을 돌린다. 시간 변동은 두 방향(A블록 먼저,
B블록 먼저)으로 반복해 상쇄한다.
"""
import dataclasses, json, sys, time
sys.path.insert(0, "/home/hwkim/assistant_univ")
import evaluate_planner as E
from geoflow import factors as F
from geoflow.composer import MacroComposer
from geoflow.macros import MacroLibrary
from geoflow.planner import GeoFlowPlanner
from ollama_client import OllamaClient
from query_loader import load_queries

class _Stub: model = "x"
_orig = F.FACTOR_SPECS["taxi_type"]
F.FACTOR_SPECS["taxi_type"] = dataclasses.replace(_orig, meaning="택시 유형 조건.")
D_PRE = GeoFlowPlanner(client=_Stub()).system_prompt()
F.FACTOR_SPECS["taxi_type"] = _orig
T0 = GeoFlowPlanner(client=_Stub()).system_prompt()
P = {"D_PRE": D_PRE, "T0": T0}

class Fixed(GeoFlowPlanner):
    fixed_prompt = ""
    def system_prompt(self): return self.fixed_prompt

WANT = ("b05", "b10", "b14", "b16", "b21", "b24")
items = [q for q in load_queries("stub_query_boundary.yaml") if q["id"][:3] in WANT]
items.sort(key=lambda q: q["id"])
c = OllamaClient("http://localhost:11434", "qwen3:8b", {"temperature": 0}, chat_timeout=300)
comp = MacroComposer(MacroLibrary.from_directory())
planners = {}
for n, t in P.items():
    pl = Fixed(client=c); pl.fixed_prompt = t; planners[n] = pl

OUT = "/tmp/claude-1005/-home-hwkim-assistant-univ/e8c0baf4-9410-41f3-a18c-521c3cf55e4e/scratchpad/block_cohort.jsonl"
fh = open(OUT, "w", encoding="utf-8")
ROUNDS = 3          # 블록 순서를 번갈아 3회
PER = 2             # 블록 안에서 질의당 반복
t0 = time.perf_counter()
for rnd in range(1, ROUNDS + 1):
    order = ("D_PRE", "T0") if rnd % 2 else ("T0", "D_PRE")
    for variant in order:
        for item in items:
            for k in range(PER):
                rec = E.evaluate_once(planners[variant], comp, item,
                                      attempt=(rnd - 1) * PER + k + 1,
                                      variant=variant,
                                      system_prompt_chars=len(P[variant]))
                rec["block_round"] = rnd
                rec["block_order"] = "/".join(order)
                fh.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
                fh.flush()
        print(f"[round {rnd}] {variant} 블록 완료 {time.perf_counter()-t0:6.0f}s", flush=True)
fh.close()
print("BLOCK COHORT DONE", flush=True)
