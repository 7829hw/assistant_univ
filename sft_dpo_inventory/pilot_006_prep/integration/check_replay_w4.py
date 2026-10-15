# -*- coding: utf-8 -*-
"""W4 5·6: partial-grounding replay를 기록된 출력만으로 재현하고, Partial 출력의 실행 서명을 확인한다. 모델 호출 없음.

    hfvenv/bin/python sft_dpo_inventory/pilot_006_prep/integration/check_replay_w4.py

5. 재현: ``pg_tools/replay_partial.py``(이식본: full arm = trunk GeoFlowPlanner, partial arm = PartialPlanner)로 원본과 같은 run 35개
   (``pg_imports/replay/replay_log.txt``의 목록, trunk에 같은 blob)를 다시 돌린다.
   - 정답 = 채점 범주 ``match`` 또는 ``expected_refusal``(원본 README 정정과 같은 정의).
   - 기준(지시 W4 5): Full correct → Partial wrong **0**, Full wrong → Partial correct(회복) **46**.
   - 원본 결과(``pg_imports/replay/replay_result.json``)와 문항 단위로 비교한다: 두 arm의 (범주, outcome, 오류 코드, Tool 호출).
6. 실행 서명(지시 W4 6): replay 대상 문항의 gold마다
   (a) **gold 왕복**: 정답 grounding(``gold_grounding``) → Partial로 줄임(``to_partial``) → PartialPlanner pipeline(completion → compose → validate →
       compile → mock 실행)의 Tool 호출 열이 Full gold를 같은 pipeline(trunk)으로 돌린 Tool 호출 열과 같은가.
   (b) **Partial 정답 출력**: replay partial arm에서 grounding_ok인 문항의 Tool 호출 열이 같은 gold의 Full 실행 호출 열과 같은가.
   불일치는 목록으로 남긴다.
출력: ``replay_w4.json``(문항별, 큰 파일), ``replay_w4_summary.json``.
"""
import collections
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE / "pg_tools"))

import evaluate_vendor100 as V  # noqa: E402
import replay_partial as R  # noqa: E402

PG = ROOT / "sft_dpo_inventory/pg_imports/replay"
CORRECT = {"match", "expected_refusal"}
KEYS = ("category", "outcome", "error_code", "calls")


class _GoldPartialClient:
    """gold payload 하나를 첫 응답으로 돌려주는 client(``_SequenceClient``와 같은 형식)."""


def gold_run(item, payload, target):
    calls = [{"kind": "plan", "content": json.dumps(payload, ensure_ascii=False)}]
    observed, _ = R._run({"question": item["question"]}, calls, {"model": "gold", "pipeline": {"condition_check": True}}, target)
    return observed


def main():
    sources = [line.split()[0] for line in (PG / "replay_log.txt").read_text(encoding="utf-8").splitlines() if line.strip().endswith("}")]
    original = {r["source"]: r for r in json.loads((PG / "replay_result.json").read_text(encoding="utf-8"))}
    results, diffs_vs_original = [], []
    totals = collections.Counter()
    for path in sources:
        result = R.replay(ROOT / path)
        result["source"] = path
        result["summary"] = R.summarize(result)
        results.append(result)
        orig = {row["id"]: row for row in original[path]["rows"]}
        for row in result["rows"]:
            f_ok, p_ok = row["full"]["category"] in CORRECT, row["partial"]["category"] in CORRECT
            totals["items"] += 1
            totals["full_correct_partial_wrong"] += f_ok and not p_ok
            totals["full_wrong_partial_correct"] += (not f_ok) and p_ok
            o = orig.get(row["id"])
            for arm in ("full", "partial"):
                if o is None or {k: row[arm][k] for k in KEYS} != {k: o[arm][k] for k in KEYS}:
                    diffs_vs_original.append({"source": path, "id": row["id"], "arm": arm,
                                              "now": {k: row[arm][k] for k in KEYS[:3]},
                                              "original": {k: o[arm][k] for k in KEYS[:3]} if o else None})
        print(path, json.dumps(result["summary"], ensure_ascii=False), flush=True)
    orig_totals = collections.Counter()
    for res in original.values():
        for row in res["rows"]:
            f_ok, p_ok = row["full"]["category"] in CORRECT, row["partial"]["category"] in CORRECT
            orig_totals["full_correct_partial_wrong"] += f_ok and not p_ok
            orig_totals["full_wrong_partial_correct"] += (not f_ok) and p_ok

    # 6. 실행 서명
    golds = {}
    for path in sources:
        meta = json.loads((ROOT / path).read_text(encoding="utf-8"))["meta"]
        gold_file = meta.get("gold_file")
        for item in V.load_gold(ROOT / gold_file if gold_file else None)["items"]:
            golds[(gold_file, item["id"])] = item
    roundtrip, mismatches_a = {}, []
    for key, item in sorted(golds.items(), key=lambda kv: str(kv[0])):
        payload = V.gold_grounding(item)
        if payload is None:
            continue
        full = gold_run(item, payload, "full")
        partial_payload, _ = R.to_partial(json.loads(json.dumps(payload)))
        partial = gold_run(item, partial_payload, "partial")
        sig = lambda obs: [[c["tool"], c["args"]] for c in obs["calls"]]  # noqa: E731
        same = (full["outcome"], full["error_code"], sig(full)) == (partial["outcome"], partial["error_code"], sig(partial))
        roundtrip[f"{key[0]}:{key[1]}"] = {"full_outcome": full["outcome"], "partial_outcome": partial["outcome"], "same": same,
                                          "full_signature": sig(full)}
        if not same:
            mismatches_a.append({"gold": f"{key[0]}:{key[1]}", "full": [full["outcome"], full["error_code"], sig(full)],
                                 "partial": [partial["outcome"], partial["error_code"], sig(partial)]})
    mismatches_b, checked_b = [], 0
    for res in results:
        meta = json.loads((ROOT / res["source"]).read_text(encoding="utf-8"))["meta"]
        gold_file = meta.get("gold_file")
        for row in res["rows"]:
            if not row["partial"]["grounding_ok"] or not row["converted"]:
                continue
            ref = roundtrip.get(f"{gold_file}:{row['id']}")
            if ref is None:
                continue
            checked_b += 1
            if row["partial"]["calls"] != ref["full_signature"]:
                mismatches_b.append({"source": res["source"], "id": row["id"], "partial_calls": row["partial"]["calls"],
                                     "gold_full_calls": ref["full_signature"]})
    summary = {
        "sources": len(sources), "items": totals["items"],
        "full_correct_partial_wrong": totals["full_correct_partial_wrong"],
        "full_wrong_partial_correct(recovered)": totals["full_wrong_partial_correct"],
        "criterion": {"full_correct_partial_wrong": 0, "recovered": 46},
        "original_recount": dict(orig_totals),
        "pass_5": totals["full_correct_partial_wrong"] == 0 and totals["full_wrong_partial_correct"] == 46,
        "item_level_differences_vs_original": len(diffs_vs_original),
        "item_level_differences_by_arm": dict(collections.Counter(d["arm"] for d in diffs_vs_original)),
        "signature_a_gold_roundtrip": {"golds": len(roundtrip), "same": sum(v["same"] for v in roundtrip.values()),
                                       "mismatches": len(mismatches_a)},
        "signature_b_partial_grounding_ok_outputs": {"checked": checked_b, "mismatches": len(mismatches_b)},
        "pass_6": not mismatches_a and not mismatches_b,
    }
    (HERE / "replay_w4.json").write_text(json.dumps({"summary": summary, "diffs_vs_original": diffs_vs_original,
                                                     "signature_mismatches_a": mismatches_a, "signature_mismatches_b": mismatches_b,
                                                     "runs": results}, ensure_ascii=False) + "\n", encoding="utf-8")
    (HERE / "replay_w4_summary.json").write_text(json.dumps({"summary": summary, "diffs_vs_original": diffs_vs_original[:200],
                                                             "signature_mismatches_a": mismatches_a,
                                                             "signature_mismatches_b": mismatches_b}, ensure_ascii=False, indent=1) + "\n",
                                                 encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
