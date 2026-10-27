# -*- coding: utf-8 -*-
"""T-C 판정 합치기(결정 242, ``pilot_009/teacher/finalize_tr9.py`` 사본): ``tc_analysis.json``의 1부(통과 ≥ 144/160)와 사람이 읽은 ``tc_read_result.json``(10개, 끌어냄/되풀이)의 2부(되풀이 ≤ 3).

    python3 finalize_tc10.py   # -> tc_verdict.json(passed: true면 TEACH-C 시작 가능)
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
rule = json.loads((HERE / "tc_rule.json").read_text(encoding="utf-8"))
an = json.loads((HERE / "tc_analysis.json").read_text(encoding="utf-8"))
rd = json.loads((HERE / "tc_read_result.json").read_text(encoding="utf-8"))
sample = json.loads((HERE / "tc_read_sample.json").read_text(encoding="utf-8"))
assert [j["trace_id"] for j in rd["judgments"]] == [t["trace_id"] for t in sample["traces"]], "읽기 결과가 표본과 다름"
assert all(j["verdict"] in ("끌어냄", "되풀이") for j in rd["judgments"])
repeat = sum(j["verdict"] == "되풀이" for j in rd["judgments"])
p1 = an["pass"] >= rule["pass_rule"]["trace_pass_min"]
p2 = len(rd["judgments"]) == rule["pass_rule"]["read"]["n"] and repeat <= rule["pass_rule"]["read"]["max_repeat"]
v = {"decision": "242 (AA2) T-C", "trace_pass": an["pass"], "of": an["traces"], "part1_ok": p1, "read_n": len(rd["judgments"]), "repeat": repeat,
     "part2_ok": p2, "passed": p1 and p2, "rule": rule["pass_rule"]}
(HERE / "tc_verdict.json").write_text(json.dumps(v, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print(json.dumps(v, ensure_ascii=False))
