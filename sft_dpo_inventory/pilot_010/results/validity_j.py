# -*- coding: utf-8 -*-
"""pilot_010 판정 단계 셀 유효성 검사(PLAN_J 9절). 출력은 셀 이름·개수·해시 접두·코드뿐 — 질문·응답·점수를 출력하지 않는다.

    python sft_dpo_inventory/pilot_010/results/validity_j.py <cell.json> ...
"""
import json
import sys

EXPECT = {"prompt": "87048d0c", "fp": "791c4a68"}


def check(p):
    d = json.load(open(p, encoding="utf-8"))
    m, rows = d["meta"], d["rows"]
    calls = [c for r in rows for c in (r.get("hf_calls") or [])]
    kern = json.dumps(m.get("vllm", {}).get("kernels", ""), ensure_ascii=False)
    out = {"cell": p.rsplit("/", 1)[-1], "rows": len(rows), "items_summary": d["summary"].get("items"),
           "calls": len(calls), "truncated_calls": sum(c.get("finish_reason") == "length" for c in calls),
           "think_unclosed": sum(c.get("think_closed") is False for c in calls),
           "error_rows_server": sum(1 for r in rows if (r.get("error_code") or "").startswith(("server", "http", "timeout"))),
           "prompt_ok": str(m.get("planner_prompt_sha256", "")).startswith(EXPECT["prompt"]),
           "fp_ok": str(m.get("code_fingerprint", "")).startswith(EXPECT["fp"]),
           "ref_date": m.get("reference_date"), "commit": str(m.get("code_commit"))[:8], "dirty": bool(m.get("code_dirty")),
           "gold": str(m.get("gold_sha256"))[:8], "flashinfer": "flashinfer" in kern.lower(), "model": m.get("model"),
           "seeds": sorted({c.get("sampling_seed") for c in calls if c.get("sampling_seed") is not None})[:1],
           "wall_s": m.get("vllm", {}).get("wall_seconds")}
    return out


if __name__ == "__main__":
    for p in sys.argv[1:]:
        print(json.dumps(check(p), ensure_ascii=False))
