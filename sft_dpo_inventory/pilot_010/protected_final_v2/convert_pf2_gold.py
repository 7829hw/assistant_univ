# -*- coding: utf-8 -*-
"""protected_final_v2 xlsx → 평가 gold yaml(결정 267, PLAN_J 3절). ``pilot_007/final/convert_pf_gold.py``(protected_final_v1, 그대로 둠)와 같은 방식.
**질문·정답 호출은 어디에도 출력하지 않는다** — sha256·개수·문항 번호·코드만. 모델 호출 없음.

    runtime/envs/hf/bin/python sft_dpo_inventory/pilot_010/protected_final_v2/convert_pf2_gold.py \
        --xlsx /data/hwkim/sftdpo_work/protected_final_v2/protected_final_v2.xlsx

- 읽기: ``validate_pf2b``(근접 대조 짧은 이름 → 정식 이름)와 같은 ``validate_pf2.load_rows``. xlsx sha256이 고정 manifest(``MANIFEST_PF2_J.json``)와 같아야 한다.
- 출력(``/data/hwkim/sftdpo_work/protected_final_v2/``(700) 안 600, 이미 있으면 덮어쓰지 않음):
  - ``pf2_gold.yaml``: ``evaluate_vendor100.load_gold`` 형식. 문항 id ``pf2/<번호 3자리>``. 답하는 문항 ``gold`` = 정답 호출(``EV.parse_calls``)·``expected_outcome: answered``.
    거부 문항 ``gold: []``, ``expected_outcome`` = M·P ``unsupported``, C ``needs_clarification``(채점은 PLAN_J 5절 refused 정의라 이 값을 쓰지 않음).
  - ``pf2_items_meta.json``: 문항 id별 번호·유형(마지막 정답 tool → ``common_pf2.TYPE_BY_TOOL``, 거부는 "거부")·거부 여부·거부 형·거부 범주·근접 대조(범주 또는 "-")·난이도·hard factor.
- 확인(validate_pf2와 같은 방법; 출력은 수치·번호·코드만): 150문항, 번호 중복 없음, 거부 50(M 34·P 10·C 6), 근접 대조 25(답하는 문항만),
  답하는 100문항 모두 ``derive_grounding`` → ``_GoldPlanner`` mock → ``EV.score`` = match 그리고 ``grounding_check`` 참,
  P·C 문항 gold mock 결과 상태 = P ``unsupported``·C ``needs_clarification``. 하나라도 아니면 exit 1(PF2 측정하지 않음).
- 셀·원문·로그 디렉터리 ``cells``·``raw``·``logs``를 700으로 만든다.
"""
import argparse
import hashlib
import json
import os
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
for p in (ROOT, ROOT / "sft_dpo_inventory/pilot_009/protected_final_v2", ROOT / "sft_dpo_inventory/pilot_006/protected_final", HERE):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
OUT = Path("/data/hwkim/sftdpo_work/protected_final_v2")
EXPECT = {"M": "unsupported", "P": "unsupported", "C": "needs_clarification"}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def write600(path, text):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--xlsx", required=True)
    a = p.parse_args()
    import yaml
    import evaluate_vendor100 as EV
    import validate_pf2
    import validate_pf2b
    from common_pf2 import MARKS, NONE, TYPE_BY_TOOL
    from validate_v2 import factors_of
    man = json.loads((HERE / "MANIFEST_PF2_J.json").read_text(encoding="utf-8"))
    if sha(a.xlsx) != man["original"]["sha256"]:
        raise SystemExit("xlsx sha256 differs from MANIFEST_PF2_J.json")
    if oct(OUT.stat().st_mode & 0o777) != "0o700":
        raise SystemExit("output dir is not 700")
    gold_p, meta_p = OUT / "pf2_gold.yaml", OUT / "pf2_items_meta.json"
    if gold_p.exists() or meta_p.exists():
        raise SystemExit("output exists; not overwriting")
    validate_pf2b._ORIG_LOAD = validate_pf2.load_rows
    rows, errs = validate_pf2b.load_rows_b(Path(a.xlsx))
    if rows is None:
        raise SystemExit(f"load failed: {errs}")
    excluded = {int(x) for x in man.get("excluded_rows", [])}
    items, meta, problems = [], {}, {}
    nums = Counter(r["번호"] for r in rows)
    for r in rows:
        n = r["번호"]
        if int(n) in excluded:
            continue
        iid = f"pf2/{int(n):03d}"
        refusal = (r["거부 문항"] or "아니오") == "예"
        marks = sorted(x.strip() for x in r["hard factor"].replace("，", ",").split(",") if x.strip() in MARKS)
        contrast = r["근접 대조"] if r["근접 대조"] and r["근접 대조"] != NONE else NONE
        if nums[n] > 1:
            problems.setdefault(n, []).append("duplicate_number")
        if refusal:
            form = r["거부 형"]
            items.append({"id": iid, "question": r["질문"], "gold_text": "", "gold": [], "expected_outcome": EXPECT.get(form, "unsupported"), "vendor_verdict": "-"})
            meta[iid] = {"number": int(n), "type": "거부", "refusal": True, "form": form, "category": r["거부 범주"] or NONE, "contrast": NONE,
                         "difficulty": r["난이도"], "factors": marks}
            if form in ("P", "C"):
                try:
                    _, obs = validate_pf2.mock_outcome(EV.parse_calls(r["정답 호출"]), r["질문"])
                    if obs.get("outcome") != EXPECT[form]:
                        problems.setdefault(n, []).append(f"pc_outcome:{obs.get('outcome')}")
                except Exception as error:  # noqa: BLE001
                    problems.setdefault(n, []).append(f"pc_mock_failed:{type(error).__name__}")
            elif form != "M":
                problems.setdefault(n, []).append("form_code")
            continue
        calls = EV.parse_calls(r["정답 호출"])
        payload = EV.derive_grounding(calls)
        auto = sorted(k for k, v in factors_of(payload).items() if v)
        item = {"id": iid, "question": r["질문"], "gold_text": r["정답 호출"], "gold": calls, "expected_outcome": "answered", "vendor_verdict": "-"}
        items.append(item)
        meta[iid] = {"number": int(n), "type": TYPE_BY_TOOL.get(calls[-1]["tool"], "기타"), "refusal": False, "form": NONE, "category": NONE, "contrast": contrast,
                     "difficulty": r["난이도"], "factors": sorted(set(auto) | set(marks))}
        try:
            observed = EV.run_item(EV._pipeline(EV._GoldPlanner(payload)), r["질문"])
            category, _ = EV.score(item, observed)
            if category != "match":
                problems.setdefault(n, []).append(f"mock_not_match:{observed.get('error_code') or category}")
            ok, _ = EV.grounding_check(item, payload)
            if ok is not True:
                problems.setdefault(n, []).append("grounding_check_not_true")
        except Exception as error:  # noqa: BLE001
            problems.setdefault(n, []).append(f"compile_failed:{type(error).__name__}")
    doc = {"note": "protected_final_v2(고정 manifest pilot_010/protected_final_v2/MANIFEST_PF2_J.json, xlsx sha256 " + sha(a.xlsx)
                   + ")에서 convert_pf2_gold.py로 변환. 저장소 밖 700 디렉터리 전용. 평가 전용 — 학습·checkpoint 선택·annotation 후보 금지.", "items": items}
    write600(gold_p, yaml.safe_dump(doc, allow_unicode=True, sort_keys=False))
    write600(meta_p, json.dumps(meta, ensure_ascii=False, indent=1) + "\n")
    for d in ("cells", "raw", "logs"):
        (OUT / d).mkdir(mode=0o700, exist_ok=True)
        os.chmod(OUT / d, 0o700)
    back = EV.load_gold(gold_p)["items"]
    ms = list(meta.values())
    summary = {"xlsx_sha256": sha(a.xlsx), "gold_yaml_sha256": sha(gold_p), "items_meta_sha256": sha(meta_p), "items": len(items), "reload_items": len(back),
               "refusal_items": sum(m["refusal"] for m in ms), "answered_items": sum(not m["refusal"] for m in ms),
               "forms": dict(Counter(m["form"] for m in ms if m["refusal"])), "contrast_items": sum(1 for m in ms if m["contrast"] != NONE),
               "mock_match_and_grounding_ok": sum(not m["refusal"] and str(m["number"]) not in problems and m["number"] not in problems for m in ms),
               "types": dict(Counter(m["type"] for m in ms)), "problems": {str(k): v for k, v in sorted(problems.items(), key=lambda x: int(x[0]))},
               "excluded_rows": sorted(excluded), "file_modes": {gold_p.name: oct(gold_p.stat().st_mode & 0o777), meta_p.name: oct(meta_p.stat().st_mode & 0o777)}}
    n_exp = 150 - len(excluded)
    summary["ok"] = (len(items) == n_exp and len(back) == n_exp and not problems and summary["refusal_items"] == 50 and summary["answered_items"] == 100
                     and summary["forms"] == {"M": 34, "P": 10, "C": 6} and summary["contrast_items"] == 25)
    print(json.dumps(summary, ensure_ascii=False))
    raise SystemExit(0 if summary["ok"] else 1)


if __name__ == "__main__":
    main()
