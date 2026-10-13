"""reviewed_gold_v006_p0 빌더(사람 승인 뒤에만 실행, 결정 66). 모델 호출 없음.

    python evaluation/partial_grounding/sft_p0/build_v006.py --approvals sft_dpo_inventory/batch006/approvals.json

- 입력: v005 P0 target 111건(`targets_v005_sft_p0.jsonl`), batch006 후보(`augmentation_candidates.jsonl`),
  사람 승인 파일(`{"reviewer": "...", "decisions": {"b006-01": "approve" | "reject", ...}}`).
  수정(문장·gold)은 write_drafts.py를 고치고 check_candidates.py를 다시 돌린 뒤 승인한다.
- 승인된 후보만 넣는다. 자동 검사 상태가 auto_ok가 아닌 후보는 승인되어 있어도 넣지 않고 멈춘다.
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
    cands = {c["id"]: c for c in (json.loads(x) for x in (HERE / "augmentation_candidates.jsonl").read_text(
        encoding="utf-8").splitlines() if x.strip())}
    for cid, decision in sorted(approvals["decisions"].items()):
        if decision != "approve":
            continue
        c = cands[cid]
        if c["status"] != "auto_ok":
            raise SystemExit(f"{cid}: 자동 검사 상태 {c['status']}. 승인되어 있어도 넣지 않는다")
        records.append({"id": cid, "question": c["question"], "target_p0": c["p0_target"], "target_full": c["full_target"],
                        "source": SOURCE[c["gap"]], "approved_by": approvals["reviewer"]})
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "sft_train.jsonl", "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps({"messages": [{"role": "system", "content": system}, {"role": "user", "content": r["question"]},
                                             {"role": "assistant", "content": json.dumps(r["target_p0"], ensure_ascii=False)}],
                                "metadata": {"source_record_id": r["id"], "source": r["source"], "approved_by": r["approved_by"],
                                             "contract": "P0", "prompt_sha256": sha, "target_full": r["target_full"],
                                             "dataset_version": "reviewed_gold_v006_p0"}}, ensure_ascii=False) + "\n")
    manifest = {"version": "reviewed_gold_v006_p0", "prompt_sha256": sha, "records": len(records),
                "by_source": {s: sum(r["source"] == s for r in records) for s in {r["source"] for r in records}},
                "approvals": str(path), "approvals_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False))


if __name__ == "__main__":
    main()
