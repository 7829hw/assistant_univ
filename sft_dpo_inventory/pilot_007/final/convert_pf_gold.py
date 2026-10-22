# -*- coding: utf-8 -*-
"""protected_final_v1 xlsx → 평가 gold yaml(결정 215 V5, S1). **질문·정답 호출은 어디에도 출력하지 않는다** — sha256·개수·문항 번호·코드만. 모델 호출 없음.

    hfvenv/bin/python sft_dpo_inventory/pilot_007/final/convert_pf_gold.py --xlsx /home/hwkim/sftdpo_work/protected_final_v1/protected_final_v1.xlsx

- 읽기: ``pilot_006/protected_final/validate.py``의 ``load_rows``(같은 열 규칙).
- 출력(모두 ``/home/hwkim/sftdpo_work/protected_final_v1/``(700) 안 600):
  - ``pf1_gold.yaml``: ``evaluate_vendor100.load_gold`` 형식. 문항 id ``pf1/<번호 3자리>``, ``gold`` = 정답 호출(``EV.parse_calls``),
    거부 문항(거부 문항 = 예)은 ``gold: []``·``expected_outcome: unsupported``(작성 지침: 지원하지 않는 질문), 그 밖 ``answered``.
  - ``pf1_items_meta.json``: 문항 id별 유형(마지막 정답 tool → ``common.TYPE_BY_TOOL``, 거부), hard factor(정답 호출에서 자동 ``validate.factors_of`` + 작성자 표시), 난이도, 거부 여부.
- 확인(validate.py와 같은 방법, 출력은 수치·번호만): 120문항, 번호 중복 없음, 거부 10, 거부 아닌 문항 모두
  ``derive_grounding`` → ``_GoldPlanner`` 파이프라인 mock 실행 → ``EV.score`` = match, 그리고 ``grounding_check(item, 역산 grounding)`` = True.
  하나라도 아니면 exit 1(측정하지 않음).
- 이미 출력 파일이 있으면 덮어쓰지 않는다(``--force`` 없음; 지우고 다시 하려면 사람이 판단).
"""
import argparse
import hashlib
import importlib.util
import json
import os
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PF = ROOT / "sft_dpo_inventory/pilot_006/protected_final"
OUT = Path("/home/hwkim/sftdpo_work/protected_final_v1")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(PF))


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
    from common import MARKS, TYPE_BY_TOOL
    spec = importlib.util.spec_from_file_location("pfv", PF / "validate.py")
    V = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(V)
    if oct(OUT.stat().st_mode & 0o777) != "0o700":
        raise SystemExit("output dir is not 700")
    gold_p, meta_p = OUT / "pf1_gold.yaml", OUT / "pf1_items_meta.json"
    if gold_p.exists() or meta_p.exists():
        raise SystemExit("output exists; not overwriting")
    rows, errs = V.load_rows(Path(a.xlsx))
    if rows is None:
        raise SystemExit(f"load failed: {errs}")
    items, meta, problems = [], {}, {}
    nums = Counter(r["번호"] for r in rows)
    for r in rows:
        n = r["번호"]
        iid = f"pf1/{int(n):03d}"
        refusal = (r["거부 문항"] or "아니오") == "예"
        marks = sorted(x.strip() for x in r["hard factor"].replace("，", ",").split(",") if x.strip() in MARKS)
        if nums[n] > 1:
            problems.setdefault(n, []).append("duplicate_number")
        if refusal:
            items.append({"id": iid, "question": r["질문"], "gold_text": "", "gold": [], "expected_outcome": "unsupported", "vendor_verdict": "-"})
            meta[iid] = {"number": n, "type": "거부", "refusal": True, "difficulty": r["난이도"], "factors": marks}
            continue
        calls = EV.parse_calls(r["정답 호출"])
        payload = EV.derive_grounding(calls)
        auto = sorted(k for k, v in V.factors_of(payload).items() if v)
        item = {"id": iid, "question": r["질문"], "gold_text": r["정답 호출"], "gold": calls, "expected_outcome": "answered", "vendor_verdict": "-"}
        items.append(item)
        meta[iid] = {"number": n, "type": TYPE_BY_TOOL.get(calls[-1]["tool"], "기타"), "refusal": False, "difficulty": r["난이도"], "factors": sorted(set(auto) | set(marks))}
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
    doc = {"note": "protected_final_v1(고정 manifest 2fb30fa, xlsx sha256 " + sha(a.xlsx) + ")에서 convert_pf_gold.py로 변환. 저장소 밖 700 디렉터리 전용.", "items": items}
    write600(gold_p, yaml.safe_dump(doc, allow_unicode=True, sort_keys=False))
    write600(meta_p, json.dumps(meta, ensure_ascii=False, indent=1) + "\n")
    back = EV.load_gold(gold_p)["items"]
    summary = {"xlsx_sha256": sha(a.xlsx), "gold_yaml_sha256": sha(gold_p), "items_meta_sha256": sha(meta_p), "items": len(items), "reload_items": len(back),
               "refusal_items": sum(m["refusal"] for m in meta.values()), "answered_items": sum(not m["refusal"] for m in meta.values()),
               "mock_match_and_grounding_ok": sum(not m["refusal"] and m["number"] not in problems for m in meta.values()),
               "types": dict(Counter(m["type"] for m in meta.values())), "problems": {k: v for k, v in sorted(problems.items(), key=lambda x: int(x[0]))},
               "file_modes": {gold_p.name: oct(gold_p.stat().st_mode & 0o777), meta_p.name: oct(meta_p.stat().st_mode & 0o777)}}
    summary["ok"] = len(items) == 120 and len(back) == 120 and not problems and summary["refusal_items"] == 10
    print(json.dumps(summary, ensure_ascii=False))
    raise SystemExit(0 if summary["ok"] else 1)


if __name__ == "__main__":
    main()
