# -*- coding: utf-8 -*-
"""G3 compatibility 10문항(IMPORT_AND_TEACHER_PLAN.md). 정답 여부는 참고로만 기록한다.

    python sft_dpo_inventory/p0_sft_003_teacher27b/compat_check.py   # -> compatibility/raw/calls.jsonl, compatibility/result.json

문항: 결정 31 render check와 같은 선택 규칙(v004 SFT의 v003 train 앞 4, v003 valid 앞 3, batch004 앞 3). prompt만 P0다.
"""
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "evaluation/partial_grounding/sft_p0"))

import ollama_call as O  # noqa: E402


def items():
    from training.data.common import read_jsonl
    valid_ids = {r["metadata"]["source_record_id"] for r in read_jsonl(ROOT / "training/generated/reviewed_gold_v003_t2pc/sft_valid.jsonl")}
    groups = {"v003_train": [], "v003_valid": [], "batch004": []}
    for r in read_jsonl(ROOT / "training/generated/reviewed_gold_v004_t2pc/sft_train.jsonl"):
        sid = r["metadata"]["source_record_id"]
        groups["batch004" if sid.startswith("b004-") else "v003_valid" if sid in valid_ids else "v003_train"].append(r)
    return groups["v003_train"][:4] + groups["v003_valid"][:3] + groups["batch004"][:3]


def main():
    import collect_p0_traces_hf as C
    from geoflow.planner import parse_planner_json
    planner, sha = C.p0_planner()
    out_dir = HERE / "compatibility" / "raw"
    out_dir.mkdir(parents=True, exist_ok=True)
    if (out_dir / "calls.jsonl").exists():
        raise SystemExit("compatibility 원문이 이미 있다")
    rows = []
    with open(out_dir / "calls.jsonl", "w", encoding="utf-8") as f:
        for r in items():
            q = r["messages"][1]["content"]
            res = O.chat(planner.messages(q), {"temperature": 0})
            try:
                parsed = parse_planner_json(res["content"]) if res["content"] else None
            except Exception:  # noqa: BLE001
                parsed = None
            checks = {"http_ok": res["http_status"] == 200 and not res["error"],
                      "thinking_present": bool(res["thinking"].strip()),
                      "content_separated": bool(res["content"].strip()) and "<think>" not in res["content"] and "</think>" not in res["content"],
                      "json_parsed": isinstance(parsed, dict),
                      "done_stop": res["done_reason"] == "stop",
                      "gpu_full": res["guard"]["gpu_full"]}
            row = {"id": r["metadata"]["source_record_id"], "question": q, "prompt_sha256": sha, "model": O.MODEL,
                   "checks": checks, "ok": all(checks.values()), **res,
                   "at": datetime.now(timezone.utc).isoformat()}
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            f.flush()
            rows.append(row)
            print(json.dumps({"id": row["id"], "ok": row["ok"], "checks": checks, "eval": res["eval_count"], "tps": res["tok_per_s"],
                              "done": res["done_reason"], "ctx": res["guard"]["context_length"]}, ensure_ascii=False), flush=True)
    tps = [r["tok_per_s"] for r in rows if r["tok_per_s"]]
    result = {"checked": len(rows), "pass": all(r["ok"] for r in rows), "fail_ids": [r["id"] for r in rows if not r["ok"]],
              "check_counts": {k: sum(r["checks"][k] for r in rows) for k in rows[0]["checks"]},
              "context_length": sorted({r["guard"]["context_length"] for r in rows if r["guard"]["context_length"]}),
              "ps_digest": sorted({r["guard"]["ps_digest"] for r in rows if r["guard"]["ps_digest"]}),
              "done_reasons": sorted({str(r["done_reason"]) for r in rows}),
              "tok_per_s_median": statistics.median(tps) if tps else None,
              "speed_guard_threshold": round(0.5 * statistics.median(tps), 2) if tps else None,
              "load_duration_s_median": statistics.median(r["load_duration"] / 1e9 for r in rows if r["load_duration"]),
              "eval_count_median": statistics.median(r["eval_count"] for r in rows if r["eval_count"]),
              "thinking_chars_median": statistics.median(len(r["thinking"]) for r in rows),
              "message_keys": sorted({k for r in rows for k in r["message_keys"]}),
              "response_keys": sorted({k for r in rows for k in r["response_keys"]})}
    (HERE / "compatibility" / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
