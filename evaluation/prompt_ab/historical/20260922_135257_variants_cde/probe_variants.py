"""Variant C / D / E를 같은 모델로 비교한다. 제품 코드는 바꾸지 않는다."""
import json, sys, time
sys.path.insert(0, "/home/hwkim/assistant_univ")
from geoflow import factors as F
from geoflow.composer import MacroComposer
from geoflow.errors import GeoFlowError, PlannerError
from geoflow.grounding import parse_grounding
from geoflow.planner import (GeoFlowPlanner, describe_factors,
                             describe_vocabulary, parse_planner_json)
from geoflow.repair import decide
from ollama_client import OllamaClient

BASE = ["_VOCABULARY_HEADING", "_FACTOR_HEADING"]

class VariantPlanner(GeoFlowPlanner):
    """system prompt의 factor semantics 절만 바꾼다."""
    variant = "D"
    def system_prompt(self):
        parts = [self.base_prompt,
                 f"[분석 개체와 측정값]\n{describe_vocabulary()}",
                 f"[사용 가능한 factor]\n{describe_factors()}"]
        if self.variant == "D":
            parts.append("[조건이 뜻하는 것]\n"
                         + F.describe_factor_semantics(sorted(F.FACTOR_SPECS))
                         + "\n\n" + F.FACTOR_STAGE_NOTE)
        elif self.variant == "E":
            parts.append("[조건이 뜻하는 것]\n"
                         + F.describe_factor_semantics(compact=True)
                         + "\n\n" + F.FACTOR_STAGE_NOTE)
        parts.append(f"[짝을 이루는 factor]\n{F.describe_constraints()}")
        return "\n\n".join(parts)

QUERIES = [
 ("b21","주 단위로 집계한 택시 수입의 평균은?"),
 ("b24","월 단위로 집계한 개인택시 수입의 최대값은?"),
 ("b05","법인택시의 공차율은?"),
 ("b07","시도별 택시 영업시간은?"),
 ("b18","통행량이 가장 많은 시군구 3곳은?"),
 ("b01","동대구역의 평균 속도는?"),
 ("b06","대구 택시 요금의 최대값은?"),
 ("b11","동성로동에서 출발한 실차 구간 건수는?"),
 ("b19","scope:district:2700000000은 어디인가요?"),
 ("b20","대구와 부산 중 어디가 더 빠른가요?"),
]
RUNS = 5
BAD_ROLLUP = {"week", "month"}
comp = MacroComposer()
client = OllamaClient("http://localhost:11434","qwen3:8b",{"temperature":0},chat_timeout=300)
out = {}
for variant in ("C","D","E"):
    planner = VariantPlanner(client=client)
    planner.variant = variant
    plen = len(planner.system_prompt())
    rows = []
    for tag, q in QUERIES:
        for i in range(RUNS):
            row = {"variant":variant,"id":tag,"run":i+1,"prompt_chars":plen,
                   "initial_ms":0.0,"repair_ms":0.0,"calls":0,"factors":None,
                   "repair":False,"success":False,"error":None,"bad_rollup":False}
            t0=time.perf_counter()
            try:
                o = planner.plan(q)
                row["initial_ms"]=o.duration_ms; row["calls"]=1
                row["factors"]=dict(o.grounding.factors)
                row["bad_rollup"]=row["factors"].get("rollup") in BAD_ROLLUP
            except PlannerError as e:
                row["error"]=e.code; row["initial_ms"]=(time.perf_counter()-t0)*1000
                try:
                    fr=(parse_planner_json((e.context or {}).get("raw_text","")) or {}).get("factors") or {}
                    row["factors"]=fr; row["bad_rollup"]=fr.get("rollup") in BAD_ROLLUP
                except Exception: pass
                rows.append(row); continue
            try:
                comp.compose(o.grounding); row["success"]=True
            except GeoFlowError as e:
                d=decide(e)
                if not d.repairable:
                    row["error"]=e.code; rows.append(row); continue
                row["repair"]=True
                try:
                    rp=planner.repair_planning_error(q,o,error=e,decision=d)
                    row["repair_ms"]=rp.duration_ms; row["calls"]+=1
                    comp.compose(rp.grounding); row["success"]=True
                    row["factors"]=dict(rp.grounding.factors)
                    row["bad_rollup"]=row["bad_rollup"] or row["factors"].get("rollup") in BAD_ROLLUP
                except Exception as ex:
                    row["error"]=getattr(ex,"code",type(ex).__name__)
            rows.append(row)
    out[variant]=rows
    ok=sum(1 for r in rows if r["success"]); bad=sum(1 for r in rows if r["bad_rollup"])
    init=sorted(r["initial_ms"] for r in rows)
    print(f"[{variant}] prompt={plen}자  성공 {ok}/{len(rows)}  bad_rollup {bad}  "
          f"initial 중앙값 {init[len(init)//2]/1000:.1f}s  repair 합계 {sum(r['repair_ms'] for r in rows)/1000:.0f}s", flush=True)
json.dump(out, open("/tmp/claude-1005/-home-hwkim-assistant-univ/e8c0baf4-9410-41f3-a18c-521c3cf55e4e/scratchpad/variants.json","w"), ensure_ascii=False, indent=1)
print("VARIANT PROBE DONE")
