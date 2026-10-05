# -*- coding: utf-8 -*-
"""grounding_v13 7절: 실제 CLI 경로(assistant_cli.py --agent-mode geoflow)의 결과를 같은 조합의 평가 기록과 비교한다(모델 호출 없음).

비교: 계획 grounding(첫 계획을 파싱한 결과), 최종 grounding, 결과 종류(outcome·오류 코드), Tool 호출(이름·인자).
"""
import json
import sys
from pathlib import Path

V = "evaluation/"
RECORDS = {  # 상태 → 셋별 평가 기록
    "adopted_default": {"od": V + "grounding_v11/runs/full/t2pc/od.json", "status": V + "grounding_v11/runs/full/t2pc/status.json",
                        "measure": V + "grounding_v12/runs/measure/t2pc/measure.json"},
    "adopted_model_q8": {s: V + f"grounding_v13/runs/small/q8_t2pc/{s}.json" for s in ("od", "status", "measure")},
    "rollback_default": {"od": V + "grounding_v9/runs/full/q8_cur/od.json",
                         "status": V + "grounding_v11/runs/status_merged/q8_cur/status.json",
                         "measure": V + "grounding_v12/runs/measure/q8_cur/measure.json"},
}


def eval_row(path, item_id):
    rows = {r["id"]: r for r in json.loads(Path(path).read_text(encoding="utf-8"))["rows"]}
    return rows[item_id]


def cli_view(record):
    g = record["geoflow"]
    calls = [(t["tool"], t["arguments"]) for t in (g.get("execution") or {}).get("trace") or [] if t.get("tool")]
    error = g.get("error") or {}
    return {"plan_grounding": (g.get("planner") or {}).get("grounding"), "grounding": g.get("grounding"),
            "outcome": g.get("outcome"), "error_code": error.get("code") if isinstance(error, dict) else None, "calls": calls}


def eval_view(row):
    plan = (row.get("planner_trace") or {}).get("first_grounding") or None
    return {"plan_grounding": plan, "grounding": row.get("grounding"), "outcome": row.get("outcome"),
            "error_code": row.get("error_code"), "calls": [(c["tool"], c["args"]) for c in row.get("calls") or []]}


def main(paths):
    report = {}
    for state, run_dir in paths.items():
        raw = json.loads((Path(run_dir) / "query_raw.json").read_text(encoding="utf-8"))
        out = {"model": raw.get("model"), "items": {}}
        for record in raw["queries"]:
            set_name, item_id = record["id"].split("-", 1)
            cli = cli_view(record)
            ev = eval_view(eval_row(RECORDS[state][set_name], item_id))
            same = {k: cli[k] == ev[k] for k in ("grounding", "outcome", "error_code", "calls")}
            out["items"][record["id"]] = {"same": same, "cli": {k: cli[k] for k in ("outcome", "error_code", "calls")},
                                          "eval": {k: ev[k] for k in ("outcome", "error_code", "calls")}}
        report[state] = out
    return report


if __name__ == "__main__":
    args = dict(a.split("=", 1) for a in sys.argv[1:-1])
    result = main(args)
    Path(sys.argv[-1]).write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    for state, out in result.items():
        print(state, out["model"])
        for key, item in out["items"].items():
            print(" ", key, item["same"], "" if all(item["same"].values()) else (item["cli"], item["eval"]))
