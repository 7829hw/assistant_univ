# -*- coding: utf-8 -*-
"""모델 상태를 매번 비우고 같은 요청을 반복한다."""
import dataclasses, json, subprocess, sys
sys.path.insert(0, "/home/hwkim/assistant_univ")
from geoflow import factors as F
from geoflow.planner import GeoFlowPlanner
from geoflow.composer import MacroComposer
from geoflow.macros import MacroLibrary
from geoflow.errors import GeoFlowError
from geoflow.repair import decide
from ollama_client import OllamaClient

class _Stub: model = "x"
_orig = F.FACTOR_SPECS["taxi_type"]
F.FACTOR_SPECS["taxi_type"] = dataclasses.replace(_orig, meaning="택시 유형 조건.")
D_PRE = GeoFlowPlanner(client=_Stub()).system_prompt()
F.FACTOR_SPECS["taxi_type"] = _orig
T0 = GeoFlowPlanner(client=_Stub()).system_prompt()

class Fixed(GeoFlowPlanner):
    fixed_prompt = ""
    def system_prompt(self): return self.fixed_prompt

def unload():
    subprocess.run(["curl", "-s", "http://localhost:11434/api/generate",
                    "-d", json.dumps({"model": "qwen3:8b", "keep_alive": 0})],
                   capture_output=True)

c = OllamaClient("http://localhost:11434", "qwen3:8b", {"temperature": 0}, chat_timeout=300)
comp = MacroComposer(MacroLibrary.from_directory())
Q = "월 단위로 집계한 개인택시 수입의 최대값은?"
for name, prompt in (("D_PRE", D_PRE), ("T0", T0)):
    p = Fixed(client=c); p.fixed_prompt = prompt
    results = []
    for i in range(5):
        unload()
        try:
            o = p.plan(Q)
        except GeoFlowError as e:
            results.append(e.code); continue
        try:
            comp.compose(o.grounding); results.append("OK"); continue
        except GeoFlowError as err:
            d = decide(err)
            if not d.repairable:
                results.append(err.code); continue
            try:
                r = p.repair_planning_error(Q, o, error=err, decision=d)
                comp.compose(r.grounding); results.append("OK(재질의)")
            except GeoFlowError as re_:
                results.append(f"{err.code}->{re_.code}")
    ok = sum(1 for x in results if x.startswith("OK"))
    print(f"{name}: {ok}/5  {results}", flush=True)
print("STATE TEST DONE", flush=True)
