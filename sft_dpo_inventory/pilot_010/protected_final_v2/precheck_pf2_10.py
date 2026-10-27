# -*- coding: utf-8 -*-
"""protected_final_v2 사전 검사(pilot_010 준비, 사용자 지시 2026-10-27). **고정(pin)이 아니다.** ``pilot_009/protected_final_v2/validate_pf2.py``(그대로 둠)의
``validate``를 겹침 대상에 batch013 초안을 더해 부른다. 질문·정답 내용은 출력하지 않는다(validate_pf2와 같음: 수치·행 번호·코드만). 모델 호출 없음.

    hfvenv/bin/python precheck_pf2_10.py --xlsx /home/hwkim/sftdpo_work/protected_final_v2/protected_final_v2.xlsx \
        --report /home/hwkim/sftdpo_work/protected_final_v2/precheck_pf2_10_YYYYMMDD.json

- 겹침 대상 = ``validate_pf2.targets()``(RC7 학습 레코드·승인 corpus v4·v5·refusal_dev v1·v2·batch011·batch012 초안·수정 문장, 보호 셋·개발 셋, RC5·RC6, pg, aug300 등)
  + ``batch013``(``batch013/candidates_draft.yaml`` 80건 전부, 정답 호출에서 grounding 역산).
- report는 저장소 밖 700 디렉터리에 600 권한으로 쓴다(커밋하지 않음). stdout에는 ok·rows·문제 코드·분포만.
- 이 검사는 사전 검사다. pilot_010 판정 단계 데이터를 빌드한 뒤 겹침 대상을 바꿔 다시 검사하고, 그때 고정한다(결정 245).
"""
import argparse
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_009/protected_final_v2"))
B013 = ROOT / "sft_dpo_inventory/batch013/candidates_draft.yaml"


def targets():
    import yaml
    import evaluate_vendor100 as EV
    import validate_pf2
    tg = validate_pf2.targets()
    tg["batch013"] = [(c["id"], c["question"], EV.derive_grounding(EV.parse_calls(c["gold_text"])) if c.get("gold_text") else None)
                      for c in yaml.safe_load(B013.read_text(encoding="utf-8"))["candidates"]]
    return tg


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--xlsx", required=True)
    p.add_argument("--report", required=True)
    a = p.parse_args()
    out = Path(a.report)
    if str(out.resolve()).startswith(str(ROOT)) or oct(out.parent.stat().st_mode)[-3:] != "700":
        raise SystemExit("report must be in a 700 directory outside the repository")
    import validate_pf2
    report = validate_pf2.validate(a.xlsx, False, targets())
    report["precheck"] = {"pin": False, "extra_overlap_targets": {"batch013": str(B013.relative_to(ROOT))}}
    fd = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(json.dumps(report, ensure_ascii=False, indent=1) + "\n")
    os.chmod(out, 0o600)
    print(json.dumps({k: report.get(k) for k in ("ok", "rows", "file_problems", "row_problems", "row_problem_counts", "distribution_problems",
                                                 "distribution", "jaccard_max_any_target", "overlap_target_sizes")}, ensure_ascii=False, indent=1))
    raise SystemExit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()
