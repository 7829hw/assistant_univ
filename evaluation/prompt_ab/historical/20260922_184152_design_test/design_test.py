# -*- coding: utf-8 -*-
"""같은 prompt·같은 질문을 block으로 돌릴 때와 번갈아 돌릴 때를 비교한다."""
import dataclasses, sys
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

c = OllamaClient("http://localhost:11434", "qwen3:8b", {"temperature": 0}, chat_timeout=300)
comp = MacroComposer(MacroLibrary.from_directory())
items = {q["id"][:3]: q for q in load_queries("stub_query_boundary.yaml")}
for q in load_queries("stub_query.yaml"):
    items.setdefault(q["id"][:3], q)
planners = {}
for n, t in P.items():
    pl = Fixed(client=c); pl.fixed_prompt = t; planners[n] = pl

N = 6
def run(tag, item, variant):
    r = E.evaluate_once(planners[variant], comp, item, attempt=1, variant=variant)
    return r["correct"], r["status"][:26]

for qid in ("b24", "q18"):
    item = items[qid]
    print(f"\n########## {qid}: {item['question']} ##########", flush=True)
    for variant in ("D_PRE", "T0"):
        res = [run("block", item, variant) for _ in range(N)]
        ok = sum(x[0] for x in res)
        print(f"  [block  ] {variant:<6} {ok}/{N}  {[x[1] for x in res]}", flush=True)
    res = {"D_PRE": [], "T0": []}
    for i in range(N):
        seq = ("D_PRE", "T0") if i % 2 == 0 else ("T0", "D_PRE")
        for v in seq:
            res[v].append(run("inter", item, v))
    for variant in ("D_PRE", "T0"):
        ok = sum(x[0] for x in res[variant])
        print(f"  [번갈아 ] {variant:<6} {ok}/{N}  {[x[1] for x in res[variant]]}", flush=True)
print("\nDESIGN TEST DONE", flush=True)
