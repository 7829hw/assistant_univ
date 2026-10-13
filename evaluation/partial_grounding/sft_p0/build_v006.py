"""reviewed_gold_v006_p0 빌더(검토 결정 뒤에만 실행, 결정 66·67). 모델 호출 없음.

    python evaluation/partial_grounding/sft_p0/build_v006.py --approvals sft_dpo_inventory/batch006/review_decisions.json

- 입력: v005 P0 target 111건(`targets_v005_sft_p0.jsonl`), 검토 결정(`review_decisions.json`, final = approve |
  approve_after_recheck | reject), 승인·수정 문장의 재검사 결과(`approved_checks.jsonl`, apply_review.py →
  check_candidates.py --source approved.jsonl).
- 승인된 후보만 넣는다. 재검사에서 겹침(excluded_overlap)이 나온 후보는 승인되어 있어도 빼고 manifest에 남긴다.
  계약 실패(contract_fail)가 있으면 멈춘다.
- 출력: `training/generated/reviewed_gold_v006_p0/sft_train.jsonl`(system = P0 결합 prompt, user = 질문, assistant = P0 target JSON)
  과 manifest. 레코드 metadata에 provenance(source = v005 | augment_dt_event | augment_od_vs_dt | augment_scope_reverse),
  Full target, 승인자를 남긴다. v005는 덮어쓰지 않는다.
- 승인 파일이 없으면 아무것도 만들지 않는다.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "training/generated/reviewed_gold_v006_p0"
SOURCE = {"A": "augment_dt_event", "B": "augment_od_vs_dt", "C": "augment_scope_reverse"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--approvals", required=True)
    a = ap.parse_args()
    path = Path(a.approvals)
    if not path.exists():
        raise SystemExit(f"승인 파일이 없다: {path}. 사람 승인 전에는 v006을 만들지 않는다(결정 45·66).")
    approvals = json.loads(path.read_text(encoding="utf-8"))
    from geoflow.planner import GeoFlowPlanner, load_planner_prompt
    planner = GeoFlowPlanner(client=None, prompt=load_planner_prompt(ROOT / "evaluation/partial_grounding/prompts/partial_p0.yaml"))
    system = planner.system_prompt()
    sha = hashlib.sha256(system.encode("utf-8")).hexdigest()
    if not sha.startswith("d7f4c12a"):
        raise SystemExit(f"P0 prompt hash {sha[:8]}")
    records = []
    for line in (HERE / "targets_v005_sft_p0.jsonl").read_text(encoding="utf-8").splitlines():
        t = json.loads(line)
        records.append({"id": t["id"], "question": t["question"], "target_p0": t["target_p0"],
                        "target_full": t["target_full"], "source": "v005", "approved_by": "v005 승인(결정 13·47)"})
    cands = {c["id"]: c for c in (json.loads(x) for x in (HERE / "approved_checks.jsonl").read_text(
        encoding="utf-8").splitlines() if x.strip())}
    excluded = {}
    for d in approvals["items"]:
        if d["final"] not in ("approve", "approve_after_recheck"):
            continue
        cid = d["id"]
        c = cands[cid]
        if c["status"] == "contract_fail":
            raise SystemExit(f"{cid}: 계약 실패 {c['contract_fail']}")
        if c["status"] != "auto_ok":
            excluded[cid] = c["excluded_reasons"]
            continue
        records.append({"id": cid, "question": c["question"], "target_p0": c["p0_target"], "target_full": c["full_target"],
                        "source": SOURCE[c["gap"]], "approved_by": approvals["reviewer"],
                        "batch": "b006", "review_decision": d["decision"], "edited": d["edited"],
                        "pair": c["pair"], "mock_available": c["mock_note"] is None})
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "sft_train.jsonl", "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps({"messages": [{"role": "system", "content": system}, {"role": "user", "content": r["question"]},
                                             {"role": "assistant", "content": json.dumps(r["target_p0"], ensure_ascii=False)}],
                                "metadata": {"source_record_id": r["id"], "source": r["source"], "approved_by": r["approved_by"],
                                             **{k: r[k] for k in ("batch", "review_decision", "edited", "pair",
                                                                  "mock_available") if k in r},
                                             "contract": "P0", "prompt_sha256": sha, "target_full": r["target_full"],
                                             "dataset_version": "reviewed_gold_v006_p0"}}, ensure_ascii=False) + "\n")
    manifest = {"version": "reviewed_gold_v006_p0", "prompt_sha256": sha, "records": len(records),
                "by_source": {s: sum(r["source"] == s for r in records) for s in {r["source"] for r in records}},
                "approvals": str(path), "approvals_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "excluded_after_recheck": excluded,
                "base": "training/generated/reviewed_gold_v005_t2pc/sft_train.jsonl(덮어쓰지 않음)",
                "canonical": "Full gold(metadata.target_full) → build_targets.convert → P0 target"}
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False))


if __name__ == "__main__":
    main()
