# -*- coding: utf-8 -*-
"""protected_final_v2 검사 2판(결정 254 AB8). ``pilot_009/protected_final_v2/validate_pf2.py``(그대로 둠)를 불러 쓰고, **근접 대조 칸의 짧은 이름**만 더 받는다.
질문·정답 내용은 출력하지 않는다(수치·행 번호·코드만). 모델 호출 없음.

    hfvenv/bin/python validate_pf2b.py --xlsx /home/hwkim/sftdpo_work/protected_final_v2/protected_final_v2.xlsx \
        --report /home/hwkim/sftdpo_work/protected_final_v2/precheck_pf2b_10_YYYYMMDD.json

- 근접 대조 칸: 괄호 설명(``(...)``·``（...）``)과 앞뒤 공백을 떼고, 짧은 이름(``SHORT``: 지표·묶음 단위·개별 단위·예측·교통수단·도메인 밖)이나 M 범주 정식 이름이면
  정식 이름으로 바꿔 ``validate_pf2``의 검사에 넘긴다(서식 코드표·설계표가 짧은 이름을 씀). 그 밖의 값은 그대로 넘겨 ``contrast_code``로 잡힌다.
  다른 칸·다른 검사·분포 목표·겹침 규칙은 ``validate_pf2``와 같다.
- 겹침 대상 = ``precheck_pf2_10.targets()``(``validate_pf2.targets()`` + batch013 초안 80). report는 저장소 밖 700 디렉터리에 600 권한(커밋하지 않음).
- 사전 검사다(고정 아님). 고정은 사용자 지시가 있을 때만(결정 254).
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
for p in (ROOT, ROOT / "sft_dpo_inventory/pilot_009/protected_final_v2", HERE):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

#: 짧은 이름 → M 범주 정식 이름(``common_pf2.M_CATEGORIES``).
SHORT = {"지표": "없는 지표", "묶음 단위": "없는 묶음 단위", "개별 단위": "개별 단위", "예측": "예측", "교통수단": "다른 교통수단", "도메인 밖": "도메인 밖"}
_PAREN = re.compile(r"\s*[(（][^()（）]*[)）]\s*")


def normalize_contrast(value):
    """근접 대조 칸 값 → 정식 이름(받을 수 있으면) 또는 원래 값."""
    from common_pf2 import M_CATEGORIES
    v = (value or "").strip()
    core = _PAREN.sub(" ", v).strip()
    core = re.sub(r"\s+", " ", core)
    if core in M_CATEGORIES:
        return core
    return SHORT.get(core, v)


def load_rows_b(path):
    rows, errs = _ORIG_LOAD(path)
    if rows is None:
        return rows, errs
    for r in rows:
        r["근접 대조"] = normalize_contrast(r["근접 대조"])
    return rows, errs


_ORIG_LOAD = None


def validate(path, test=False, tg=None):
    global _ORIG_LOAD
    import validate_pf2
    if _ORIG_LOAD is None:
        _ORIG_LOAD = validate_pf2.load_rows
        validate_pf2.load_rows = load_rows_b
    return validate_pf2.validate(path, test, tg)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--xlsx", required=True)
    p.add_argument("--report", required=True)
    a = p.parse_args()
    out = Path(a.report)
    if str(out.resolve()).startswith(str(ROOT)) or oct(out.parent.stat().st_mode)[-3:] != "700":
        raise SystemExit("report must be in a 700 directory outside the repository")
    import precheck_pf2_10
    report = validate(a.xlsx, False, precheck_pf2_10.targets())
    report["precheck"] = {"pin": False, "tool": "validate_pf2b (근접 대조 짧은 이름 받음)", "extra_overlap_targets": {"batch013": "sft_dpo_inventory/batch013/candidates_draft.yaml"}}
    fd = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(json.dumps(report, ensure_ascii=False, indent=1) + "\n")
    os.chmod(out, 0o600)
    print(json.dumps({k: report.get(k) for k in ("ok", "rows", "file_problems", "row_problems", "row_problem_counts", "distribution_problems",
                                                 "distribution", "jaccard_max_any_target", "overlap_target_sizes")}, ensure_ascii=False, indent=1))
    raise SystemExit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()
