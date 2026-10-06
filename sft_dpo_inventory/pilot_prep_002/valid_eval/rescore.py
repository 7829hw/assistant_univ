# -*- coding: utf-8 -*-
"""pipeline_pilot_001의 valid 11셀을 결정 11의 provider 선택으로 다시 채점한다. 모델을 부르지 않는다.

    python sft_dpo_inventory/pilot_prep_002/valid_eval/rescore.py

- 입력: ``pipeline_pilot_001/valid/<label>.json``(기존 결과)과 ``training/generated/pipeline_pilot_001/<label>_raw.jsonl``
  (기록된 응답 원문). 둘 다 고치지 않는다. 다시 학습하거나 생성하지 않는다.
- 문항마다 ``provider_eval.provider_for``로 provider를 정하고, 기록된 **첫 응답**을 그 provider의 pipeline에 다시 넣는다.
  pipeline이 두 번째 모델 호출(재질의)을 요청하면 부르지 않고 ``needs_live``로 표시한다.
- 새 점수:
  - provider가 mock인 문항은 기존 경로와 같은 provider·코드이므로 기존 판정을 그대로 쓴다.
    첫 응답만으로 끝났던 문항은 재적용 결과가 기존 판정과 같은지 확인한다(``replay_check``).
  - provider가 reference로 바뀐 문항은 재적용 결과로 판정한다. ``needs_live``이면 판정하지 않고 센다.
- 선택 규칙(``pipeline_pilot_001/PLAN.md``: grounding_ok 최고, 동점이면 이른 step)을 새 점수에 적용해 보고, 이미 고른
  checkpoint와 같은지 적는다. ``needs_live``가 있으면 그 문항을 모두 X로 본 값과 모두 O로 본 값의 두 경우로 적용한다.
  고른 checkpoint는 바꾸지 않는다.
결과는 ``../valid_rescore/``에 쓴다.
"""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/thinking_prep_001"))

import provider_eval as P  # noqa: E402

PILOT = ROOT / "sft_dpo_inventory/pipeline_pilot_001"
RAW = ROOT / "training/generated/pipeline_pilot_001"
OUT = HERE.parent / "valid_rescore"
LABELS = ["base", "sft_step2", "sft_step4", "sft_step6", "sft_step8", "sft_step10", "sft_step12",
          "dpo_step2", "dpo_step4", "dpo_step6", "dpo_step8"]


class NeedsLive(Exception):
    pass


class FirstResponseReplay:
    """기록된 첫 응답만 돌려준다. 두 번째 호출은 새 모델 호출이 필요하다는 뜻이므로 멈춘다."""

    model = "replay-first-response"

    def __init__(self, raw):
        import hf_thinking as H
        thinking, content, closed = H.split_thinking(raw["raw_text"])
        self.response = {"message": {"content": content, "thinking": thinking},
                         "done_reason": raw["done_reason"], "eval_count": raw["generated_tokens"]}
        self.calls, self.requests = 0, []

    def chat(self, messages, tools=None, **kwargs):
        self.calls += 1
        if self.calls > 1:
            self.requests.append((messages[-1].get("content") or "").split("\n", 1)[0])
            raise NeedsLive("second model call requested")
        return self.response


def replay(raw, question, gold, provider):
    import evaluate_vendor100 as EV
    client = FirstResponseReplay(raw)
    try:
        observed = EV.run_item(P.make_pipeline(client, provider), question)
    except Exception as error:  # noqa: BLE001 - evaluate_vendor100 llm과 같은 처리
        observed = EV._crashed(error)
    item = {"gold_grounding": gold, "gold": None}
    ok, diffs = EV.grounding_check(item, observed["grounding"])
    return {"needs_live": client.calls > 1, "second_call_request": client.requests[:1],
            "grounding_ok": bool(ok), "grounding_diffs": json.loads(json.dumps(diffs, ensure_ascii=False)),
            "outcome": observed["outcome"], "error_code": observed["error_code"],
            "tools": [c["tool"] for c in observed["calls"]]}


def select(scores):
    """{label: score} 중 sft·dpo 각각 선택 규칙 적용(동점이면 이른 step)."""
    out = {}
    for stage in ("sft", "dpo"):
        cands = sorted(((int(l.split("step")[1]), l) for l in scores if l.startswith(stage)))
        best = max(scores[l] for _, l in cands)
        out[stage] = {"selected": next(l for _, l in cands if scores[l] == best), "best": best,
                      "tied": [l for _, l in cands if scores[l] == best]}
    return out


def main():
    from training.data.common import read_jsonl
    gold = {r["metadata"]["source_record_id"]: r for r in read_jsonl(ROOT / "training/generated/reviewed_gold_v003_t2pc/sft_valid.jsonl")}
    OUT.mkdir(exist_ok=True)
    cells, replay_checks = {}, []
    for label in LABELS:
        old = json.loads((PILOT / "valid" / f"{label}.json").read_text(encoding="utf-8"))
        raws = {r["id"]: r for r in read_jsonl(RAW / f"{label}_raw.jsonl") if r["call"] == 0}
        rows = []
        for row in old["rows"]:
            raw = raws[row["id"]]
            if raw["raw_sha256"] != row["raw_sha256"][0] or hashlib.sha256(raw["raw_text"].encode()).hexdigest() != raw["raw_sha256"]:
                raise SystemExit(f"raw record mismatch: {label} {row['id']}")
            record = gold[row["id"]]
            question, gold_grounding = record["messages"][1]["content"], json.loads(record["messages"][2]["content"])
            provider, provider_class = P.provider_for(gold_grounding)
            result = replay(raw, question, gold_grounding, provider)
            new = {"id": row["id"], "provider": provider, "provider_class": provider_class,
                   "old_grounding_ok": row["grounding_ok"], "old_outcome": f"{row['outcome']}:{row['error_code']}",
                   "old_model_calls": row["model_calls"], "replay": result}
            if provider == "mock":
                new["new_grounding_ok"] = row["grounding_ok"]
                new["basis"] = "unchanged_path(mock)"
                if row["model_calls"] == 1:
                    same = (result["grounding_ok"] == row["grounding_ok"] and not result["needs_live"]
                            and result["outcome"] == row["outcome"] and result["error_code"] == row["error_code"])
                    new["replay_check"] = same
                    replay_checks.append({"label": label, "id": row["id"], "same": same})
            elif result["needs_live"]:
                new["new_grounding_ok"] = None
                new["basis"] = "needs_live"
            else:
                new["new_grounding_ok"] = result["grounding_ok"]
                new["basis"] = "replayed_first_response(reference)"
            rows.append(new)
        needs_live = [r["id"] for r in rows if r["new_grounding_ok"] is None]
        cells[label] = {
            "old_grounding_ok": old["summary"]["grounding_ok"],
            "new_grounding_ok_known": sum(1 for r in rows if r["new_grounding_ok"]),
            "needs_live": needs_live,
            "new_range": [sum(1 for r in rows if r["new_grounding_ok"]),
                          sum(1 for r in rows if r["new_grounding_ok"] or r["new_grounding_ok"] is None)],
            "changed": [{"id": r["id"], "old": r["old_grounding_ok"], "new": r["new_grounding_ok"],
                         "provider": r["provider"], "new_outcome": f"{r['replay']['outcome']}:{r['replay']['error_code']}",
                         "new_diffs": r["replay"]["grounding_diffs"]}
                        for r in rows if r["new_grounding_ok"] != r["old_grounding_ok"]],
            "rows": rows}
    old_scores = {l: c["old_grounding_ok"] for l, c in cells.items()}
    low = {l: c["new_range"][0] for l, c in cells.items()}
    high = {l: c["new_range"][1] for l, c in cells.items()}
    selection = {"old": select(old_scores), "new_needs_live_as_X": select(low), "new_needs_live_as_O": select(high),
                 "pilot_selected": {"sft": "sft_step4", "dpo": "dpo_step6"}}
    summary = {"rule": "decision 11; first recorded response replayed; no model calls",
               "cells": {l: {k: c[k] for k in ("old_grounding_ok", "new_range", "needs_live", "changed")}
                         for l, c in cells.items()},
               "replay_check": {"checked": len(replay_checks), "same": sum(c["same"] for c in replay_checks),
                                "different": [c for c in replay_checks if not c["same"]]},
               "selection": selection}
    (OUT / "rescore.json").write_text(json.dumps({"summary": summary, "cells": cells}, ensure_ascii=False, indent=1)
                                      + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1)[:6000])


if __name__ == "__main__":
    main()
