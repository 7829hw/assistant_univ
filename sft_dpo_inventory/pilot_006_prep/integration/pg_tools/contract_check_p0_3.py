# -*- coding: utf-8 -*-
# [pilot_006 준비 W3 이식] 원본: geoflow/partial-grounding 커밋 ab9d215의 evaluation/partial_grounding/ab_p0_3/contract_check.py. 본문은 원본 그대로다(아래 '이식 수정' 줄 제외).
# 원본의 경로 상수(ROOT 등)는 원 위치 기준이라 이 위치에서 바로 돌리려면 경로 인자를 확인한다. 참고값 경로(HF greedy·Ollama, 다른 장비)의 기록용 도구다.
"""P0.3 모델 실행 전 정적·contract 검사(사용자 2026-10-11 지시 5·6절). 모델을 부르지 않는다.

    python evaluation/partial_grounding/ab_p0_3/contract_check.py --out evaluation/partial_grounding/ab_p0_3/contract_check.json

1. 정적 검사: 결합한 system prompt 기준 P0.2 → P0.3 diff(추가·삭제·변경 줄 수), prompt hash, 실행 의미 코드 지문.
2. Frozen pipeline contract 검사(ab_valid98/contract_check.py의 run()과 같은 pipeline):
   A. 사용자가 준 od_role payload.
   B. 기존 gold(valid98, 이미 진단에 쓴 셋)의 dimension_target=pickup / dropoff / both 문항, od_role과 dimension_target이 함께 있는 문항.
   C. 기존 gold의 bucket=week / month 문항.
   B·C는 정답 grounding을 Full 그대로와 Partial(to_partial)로 넣어 채점 범주가 정답인지 본다.
3. P0.3 output_format 예시 1–6(P0.2와 같음)도 다시 넣는다.
"""
import argparse
import difflib
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "evaluation" / "partial_grounding"))

import evaluate_vendor100 as EV  # noqa: E402
import execution_spec  # noqa: E402
from geoflow.planner import GeoFlowPlanner, load_planner_prompt  # noqa: E402
from replay_partial import to_partial  # noqa: E402

spec = importlib.util.spec_from_file_location("cc98", ROOT / "evaluation/partial_grounding/ab_valid98/contract_check.py")
CC = importlib.util.module_from_spec(spec)
spec.loader.exec_module(CC)

PROMPTS = ROOT / "evaluation/partial_grounding/prompts"
GOLD = ROOT / "sft_dpo_inventory/pilot_001_analysis/decision43/valid98_gold.yaml"
PAYLOAD_A = {"concepts": [{"text": "동성로", "subtype": "place", "value": {"name": "동성로", "region": ""},
                           "attributes": {"od_role": "dropoff"}},
                          {"text": "실차 구간 건수", "subtype": "trip_count"}], "factors": {}}
QUESTION_A = "동성로에 도착한 실차 구간 건수는?"


def system_prompt(path):
    return GeoFlowPlanner(client=None, prompt=load_planner_prompt(str(path)) if path else None).system_prompt()


def static():
    p02, p03 = system_prompt(PROMPTS / "partial_p0_2.yaml"), system_prompt(PROMPTS / "partial_p0_3.yaml")
    sm = difflib.SequenceMatcher(a=p02.splitlines(), b=p03.splitlines(), autojunk=False)
    ops = {"insert": 0, "delete": 0, "replace": 0}
    added = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "insert":
            ops["insert"] += j2 - j1
            added.append("\n".join(p03.splitlines()[j1:j2]))
        elif tag == "delete":
            ops["delete"] += i2 - i1
        elif tag == "replace":
            ops["replace"] += max(i2 - i1, j2 - j1)
    return {"prompt_sha256": {name: hashlib.sha256(system_prompt(path).encode("utf-8")).hexdigest()
                              for name, path in (("full", None), ("p0", PROMPTS / "partial_p0.yaml"),
                                                 ("p0_2", PROMPTS / "partial_p0_2.yaml"), ("p0_3", PROMPTS / "partial_p0_3.yaml"))},
            "diff_p0_2_to_p0_3_lines": {"added": ops["insert"], "deleted": ops["delete"], "changed": ops["replace"]},
            "added_block_starts_with_rule_11": len(added) == 1 and added[0].lstrip().startswith("11."),
            "code_fingerprint": execution_spec.code_fingerprint(str(ROOT))["sha256"]}


def gold_cases(items):
    def factors(item):
        return (EV.gold_grounding(item) or {}).get("factors") or {}

    def od(item):
        return any((c.get("attributes") or {}).get("od_role") for c in (EV.gold_grounding(item) or {}).get("concepts") or [])

    picks = {
        "B_dimension_target_pickup": lambda i: factors(i).get("dimension_target") == "pickup",
        "B_dimension_target_dropoff": lambda i: factors(i).get("dimension_target") == "dropoff",
        "B_dimension_target_both": lambda i: factors(i).get("dimension_target") == "both",
        "B_od_role_and_dimension_target": lambda i: od(i) and factors(i).get("dimension_target") in ("pickup", "dropoff"),
        "C_bucket_week": lambda i: factors(i).get("bucket") == "week" and i.get("expected_outcome", "answered") == "answered",
        "C_bucket_month": lambda i: factors(i).get("bucket") == "month" and i.get("expected_outcome", "answered") == "answered",
    }
    return {name: next(i for i in items if pick(i)) for name, pick in picks.items()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    result = {"static": static(), "cases": {}, "examples": []}
    view = CC.run(QUESTION_A, PAYLOAD_A)
    result["cases"]["A_od_role"] = {"source": "사용자 지시 6절 payload", "outcome": view["outcome"], "error_code": view["error_code"],
                                    "calls": view["calls"]}
    EV.GOLD_PATH = GOLD
    for name, item in gold_cases(EV.load_gold(GOLD)["items"]).items():
        payload = EV.gold_grounding(item)
        partial, _ = to_partial(json.loads(json.dumps(payload)))
        full_view, partial_view = CC.run(item["question"], payload, item), CC.run(item["question"], partial, item)
        result["cases"][name] = {"source": f"valid98 {item['id']}", "partial_payload": partial,
                                 "full": {k: full_view[k] for k in ("outcome", "error_code", "category")},
                                 "partial": {k: partial_view[k] for k in ("outcome", "error_code", "category")},
                                 "calls": partial_view["calls"], "same": full_view == partial_view}
    output_format = yaml.safe_load((PROMPTS / "partial_p0_3.yaml").read_text(encoding="utf-8"))["sections"]["output_format"]
    for question, text in re.findall(r"\n질문:\n([^\n]+)\n\n출력:\n(\{.*?\n\})", output_format, re.S):
        v = CC.run(question, json.loads(text))
        result["examples"].append({"question": question, "outcome": v["outcome"], "error_code": v["error_code"]})
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(result["static"], ensure_ascii=False, indent=1))
    for name, c in result["cases"].items():
        print(name, c["source"], {k: c[k] for k in ("full", "partial", "same", "outcome", "error_code") if k in c})
        print("   calls", [(t, dict(a)) for t, a in c["calls"]])
    print("examples", [(e["outcome"], e["error_code"]) for e in result["examples"]])


if __name__ == "__main__":
    main()
