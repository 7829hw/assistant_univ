# -*- coding: utf-8 -*-
"""protected_final_v2 고정 전 검사(pilot_010 판정 단계, 결정 267 §3). ``validate_pf2b.validate``(그대로 둠)를 겹침 대상을 넓혀 부른다.
질문·정답 내용은 출력하지 않는다(수치·행 번호·코드만). 모델 호출 없음.

    runtime/envs/hf/bin/python check_pf2_j.py --xlsx /data/hwkim/sftdpo_work/protected_final_v2/protected_final_v2.xlsx \
        --report /data/hwkim/sftdpo_work/protected_final_v2/check_pf2_j_YYYYMMDD.json

- 겹침 대상 = ``precheck_pf2_10.targets()``(validate_pf2 대상: refusal_dev v1·v2, valid98·aux, selection_v2, batch011·012, 승인 corpus v4·v5, RC5–7 등 + batch013 초안)
  + ``train_rc:V4/full``(V4 학습 레코드 1,984의 질문 494, ``validate_v2.train_targets``·corpus v6) + ``approved_v6``(승인 corpus v6 전체)
  + ``main_holdout53``(주 셋 151의 holdout 53, ``pilot_006_prep/aug300/augmentation_holdout_v1_gold.yaml``) + ``batch014``(``batch014/candidates_draft.yaml`` 전부).
  주 셋 151의 나머지 98은 ``selection_v2``(기존 대상)다.
- report는 저장소 밖 700 디렉터리에 600 권한(커밋하지 않음). stdout에는 ok·rows·문제 코드·분포·대상 크기만.
"""
import argparse
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
for p in (ROOT, ROOT / "sft_dpo_inventory/pilot_009/protected_final_v2", ROOT / "sft_dpo_inventory/pilot_006/protected_final", HERE):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

V4 = "sft_dpo_inventory/pilot_010/build/V4/full/sft_train.jsonl"
V6 = "sft_dpo_inventory/pilot_006_prep/approved/approved_train_v6.jsonl"
HOLDOUT = ROOT / "sft_dpo_inventory/pilot_006_prep/aug300/augmentation_holdout_v1_gold.yaml"
B014 = ROOT / "sft_dpo_inventory/batch014/candidates_draft.yaml"


def targets():
    import yaml
    import evaluate_vendor100 as EV
    import precheck_pf2_10
    import validate_v2
    from grounding.full_renderer import render_full
    from training.data.common import read_jsonl
    tg = precheck_pf2_10.targets()
    tt, missing = validate_v2.train_targets([V4], V6)
    if missing:
        raise SystemExit(f"V4 ids missing in corpus v6: {len(missing)}")
    tg.update(tt)
    tg["approved_v6"] = [(r["id"], r["question"], render_full(r["semantics"]) if not (r["semantics"] or {}).get("unsupported") else None) for r in read_jsonl(ROOT / V6)]
    der = lambda c: EV.derive_grounding(EV.parse_calls(c["gold_text"])) if c.get("gold_text") else None  # noqa: E731
    tg["main_holdout53"] = [(c["id"], c["question"], der(c)) for c in yaml.safe_load(HOLDOUT.read_text(encoding="utf-8"))["items"]]
    tg["batch014"] = [(c["id"], c["question"], der(c)) for c in yaml.safe_load(B014.read_text(encoding="utf-8"))["candidates"]]
    return tg


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--xlsx", required=True)
    p.add_argument("--report", required=True)
    a = p.parse_args()
    out = Path(a.report)
    if str(out.resolve()).startswith(str(ROOT)) or oct(out.parent.stat().st_mode)[-3:] != "700":
        raise SystemExit("report must be in a 700 directory outside the repository")
    import validate_pf2b
    tg = targets()
    report = validate_pf2b.validate(a.xlsx, False, tg)
    report["check"] = {"pin_check": True, "tool": "check_pf2_j (validate_pf2b + V4·corpus v6·holdout53·batch014)",
                       "extra_overlap_targets": {"train_rc:V4/full": V4, "approved_v6": V6, "main_holdout53": str(HOLDOUT.relative_to(ROOT)),
                                                 "batch014": str(B014.relative_to(ROOT)), "batch013": "sft_dpo_inventory/batch013/candidates_draft.yaml"},
                       "target_sizes": {k: len(v) for k, v in tg.items()}}
    fd = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(json.dumps(report, ensure_ascii=False, indent=1) + "\n")
    os.chmod(out, 0o600)
    print(json.dumps({k: report.get(k) for k in ("ok", "rows", "file_problems", "row_problems", "row_problem_counts", "distribution_problems",
                                                 "distribution", "jaccard_max_any_target", "overlap_target_sizes")}, ensure_ascii=False, indent=1))
    print(json.dumps({"target_sizes": report["check"]["target_sizes"]}, ensure_ascii=False))
    raise SystemExit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()
