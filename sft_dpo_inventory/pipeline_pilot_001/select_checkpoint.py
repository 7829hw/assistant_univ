# -*- coding: utf-8 -*-
"""PLAN.md의 선택 규칙으로 checkpoint 하나를 고른다: valid grounding_ok가 가장 높은 것, 동점이면 더 이른 step.

    python sft_dpo_inventory/pipeline_pilot_001/select_checkpoint.py --stage sft --out selection_sft.json \
        RESULT_step2.json RESULT_step4.json ...

결과 파일의 ``meta.adapter``에서 ``checkpoint-N``의 N을 step으로 읽는다. 다른 지표로 동점을 풀지 않는다.
"""
import argparse
import json
import re
from pathlib import Path


def step_of(adapter):
    match = re.search(r"checkpoint-(\d+)", adapter or "")
    if not match:
        raise SystemExit(f"checkpoint step을 읽을 수 없다: {adapter}")
    return int(match.group(1))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", required=True, choices=["sft", "dpo"])
    parser.add_argument("--out", required=True)
    parser.add_argument("results", nargs="+")
    args = parser.parse_args()
    candidates = []
    for path in args.results:
        result = json.loads(Path(path).read_text(encoding="utf-8"))
        candidates.append({"step": step_of(result["meta"]["adapter"]), "label": result["meta"]["label"],
                           "adapter": result["meta"]["adapter"], "adapter_sha256": result["meta"]["adapter_sha256"],
                           "grounding_ok": result["summary"]["grounding_ok"], "items": result["summary"]["items"],
                           "result": str(path)})
    candidates.sort(key=lambda c: c["step"])
    best = max(c["grounding_ok"] for c in candidates)
    chosen = next(c for c in candidates if c["grounding_ok"] == best)
    selection = {"stage": args.stage, "rule": "max valid grounding_ok; tie -> earliest step", "candidates": candidates,
                 "tied_at_best": [c["step"] for c in candidates if c["grounding_ok"] == best], "selected": chosen}
    Path(args.out).write_text(json.dumps(selection, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"stage": args.stage, "selected_step": chosen["step"], "grounding_ok": best,
                      "tied_at_best": selection["tied_at_best"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
