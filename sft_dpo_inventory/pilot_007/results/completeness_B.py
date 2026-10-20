# -*- coding: utf-8 -*-
"""B단계 셀 완료성(C1, 결정 200 R7: 고정 확인 전 허용 범위만). 모델 호출 없음.

    hfvenv/bin/python sft_dpo_inventory/pilot_007/results/completeness_B.py   # -> results/completeness_B.json

셀마다(``gpu/jobs_B.json``의 cells 작업): 셀 파일 존재·sha256, 행 수(= meta.item_order 길이인지), 원문 줄 수·sha256(= meta.hf.raw_out_sha256인지), 원문에 문항이 모두 있는지,
잘림 호출 수(``finish_reason == "length"``), 서버 오류 행 수(``UNHANDLED_EXCEPTION`` 중 연결·HTTP·시간 초과 예외), 1% 넘으면 ``rerun``(지시 정지 규칙).
지연 창: 세 셀 파일 존재·sha256·``latency_summary.json`` 존재만.
**정답률·U·grounding·outcome·gate 값은 읽지도 쓰지도 않는다**(R7).
"""
import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
P7 = HERE.parent
ROOT = P7.parents[1]
CELLS = P7 / "cells"
SERVER_ERR = re.compile(r"^(URLError|HTTPError|ConnectionError|ConnectionResetError|ConnectionRefusedError|RemoteDisconnected|TimeoutError|socket\.timeout|IncompleteRead)\b")


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def cell(label, k):
    f = CELLS / f"{label}_s{k}.json"
    if not f.exists():
        return {"exists": False}
    d = json.loads(f.read_text(encoding="utf-8"))
    rows, meta = d["rows"], d["meta"]
    raw = Path(meta["hf"]["raw_out"])
    rec = {"exists": True, "sha256": sha(f), "rows": len(rows), "rows_equal_item_order": len(rows) == len(meta["item_order"]),
           "model": meta["model"], "code_commit": meta["code_commit"][:7], "fingerprint_ok": meta["code_fingerprint"].startswith("791c4a68"),
           "prompt_sha256": meta["planner_prompt_sha256"][:8], "grounding_target": meta.get("grounding_target", "full"),
           "prompt_ok": meta["planner_prompt_sha256"][:8] == ("8b157c9a" if meta.get("grounding_target") == "partial" else "87048d0c")}
    srv = 0
    for r in rows:
        if r.get("error_code") == "UNHANDLED_EXCEPTION":
            exc = ((r.get("planner_trace") or {}).get("exception") or "")
            srv += bool(SERVER_ERR.match(exc))
    rec["server_error_rows"] = srv
    if raw.exists():
        lines = raw.read_text(encoding="utf-8").splitlines()
        recs = [json.loads(x) for x in lines]
        rec.update(raw_lines=len(lines), raw_sha256_match=sha(raw) == meta["hf"]["raw_out_sha256"],
                   raw_items_cover=set(meta["item_order"]) <= {x["id"] for x in recs},
                   truncated_calls=sum(x.get("finish_reason") == "length" for x in recs))
        rec["truncated_pct"] = round(100 * rec["truncated_calls"] / max(1, len(recs)), 2)
    else:
        rec.update(raw_lines=None, raw_sha256_match=False)
    rec["server_error_pct"] = round(100 * srv / max(1, len(rows)), 2)
    rec["rerun"] = (rec.get("truncated_pct") or 0) > 1.0 or rec["server_error_pct"] > 1.0
    return rec


def main():
    jobs = json.loads((P7 / "gpu/jobs_B.json").read_text(encoding="utf-8"))["jobs"]
    out, missing, rerun = {"cells": {}}, [], []
    for j in jobs:
        for c in j.get("cells", []):
            for k in range(1, c["k"] + 1):
                r = cell(c["label"], k)
                out["cells"][f"{c['label']}_s{k}"] = {"job": j["id"], **r}
                if not r["exists"]:
                    missing.append(f"{c['label']}_s{k}")
                elif r["rerun"] or not (r["rows_equal_item_order"] and r["raw_sha256_match"] and r.get("raw_items_cover")):
                    rerun.append(f"{c['label']}_s{k}")
    lat = P7 / "latency/B"
    out["latency"] = {n: ({"exists": True, "sha256": sha(lat / n)} if (lat / n).exists() else {"exists": False})
                      for n in ("latB-base_s1.json", "latB-F_s1.json", "latB-P_s1.json", "latency_summary.json")}
    out["summary"] = {"cells_expected": len(out["cells"]), "cells_present": len(out["cells"]) - len(missing), "missing": missing, "needs_rerun_or_check": rerun,
                      "truncated_calls_total": sum(v.get("truncated_calls", 0) for v in out["cells"].values()),
                      "server_error_rows_total": sum(v.get("server_error_rows", 0) for v in out["cells"].values()),
                      "latency_files_present": sum(v["exists"] for v in out["latency"].values())}
    (HERE / "completeness_B.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(out["summary"], ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
