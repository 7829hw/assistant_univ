# -*- coding: utf-8 -*-
"""A2("결론" 문장): 학습 모델 출력의 유형 비율, RC3 학습 데이터의 유형별 레코드 수·loss token 비중, (ii) 유무와 정답률(전체·문항 안). 모델 호출 없음.

    hfvenv/bin/python a2_concl.py   # -> a2_concl.json

- 유형 판정은 ``itemdata.concl_types``(출력·학습 데이터 같은 규칙).
- loss token 비중: teacher 레코드(loss_scope full_response)는 thinking+JSON 전체가 loss라 "결론"이 든 문장(줄 단위)의 token / 그 arm의 전체 loss token.
  8b 레코드는 JSON만 loss(thinking 없음 또는 prompt 쪽)라 0으로 센다.
- 문항 안 비교: 같은 (모델, 문항)에서 (ii)가 있는 표본과 없는 표본이 둘 다 있을 때 정답률 차(문항 평균), 문항 bootstrap 10,000.
"""
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
from itemdata import concl_types, tok  # noqa: E402

RC3 = ROOT / "sft_dpo_inventory/pilot_006/build/RC3"
MODELS = ("F43e1", "P43e1", "F1016e1", "P1016e1", "F43e2", "P43e2", "F1016e2", "P1016e2", "base", "R2")


def training_data():
    t = tok()
    out = {}
    for arm in ("full", "partial"):
        recs = [json.loads(l) for l in (RC3 / arm / "sft_train.jsonl").read_text(encoding="utf-8").splitlines()]
        by = defaultdict(Counter)
        loss_all = loss_concl = 0
        type_tokens = Counter()
        for r in recs:
            scope = r["metadata"]["loss_scope"]
            c = r["messages"][-1]["content"]
            th = c.split("</think>")[0] if "<think>" in c else ""
            ty = concl_types(th)
            by[scope]["records"] += 1
            by[scope]["any"] += bool(ty)
            for x in ty:
                by[scope][x] += 1
            if scope == "full_response":
                n = len(t(c, add_special_tokens=False)["input_ids"])
                loss_all += n
                for line in th.splitlines():
                    if re.search(r"결론|conclusion", line, re.I):
                        k = len(t(line, add_special_tokens=False)["input_ids"])
                        loss_concl += k
                        for x in concl_types(line) or {"iv"}:
                            type_tokens[x] += k
            else:
                ans = c.split("</think>")[-1]
                loss_all += len(t(ans, add_special_tokens=False)["input_ids"])
        out[arm] = {"by_scope": {k: dict(v) for k, v in by.items()}, "loss_tokens_total": loss_all, "loss_tokens_in_결론_lines": loss_concl,
                    "share_pct": round(100 * loss_concl / loss_all, 2), "type_tokens(line-level)": dict(type_tokens)}
    return out


def outputs():
    rows = [json.loads(l) for l in (HERE / "samples_s3.jsonl").read_text(encoding="utf-8").splitlines()]
    rows = [r for r in rows if r["set"] in ("sel", "holdout")]
    rng = np.random.default_rng(20261109)
    res = {}
    for m in MODELS:
        v = [r for r in rows if r["model"] == m]
        if not v:
            continue
        n = len(v)
        c = Counter(x for r in v for x in r["concl"])
        has = [r["ok"] for r in v if "ii" in r["concl"]]
        no = [r["ok"] for r in v if "ii" not in r["concl"]]
        items = defaultdict(lambda: ([], []))
        for r in v:
            items[(r["set"], r["id"])][0 if "ii" in r["concl"] else 1].append(r["ok"])
        mixed = [(np.mean(a), np.mean(b)) for a, b in items.values() if a and b]
        within = None
        if len(mixed) >= 5:
            d = np.array([a - b for a, b in mixed])
            boots = [d[rng.integers(0, len(d), len(d))].mean() for _ in range(10000)]
            within = {"items": len(d), "ii_minus_no_ii_pp": round(100 * d.mean(), 2),
                      "ci95": [round(100 * float(np.percentile(boots, 2.5)), 2), round(100 * float(np.percentile(boots, 97.5)), 2)]}
        res[m] = {"samples": n, "any_pct": round(100 * sum(bool(r["concl"]) for r in v) / n, 1),
                  "types_pct": {x: round(100 * c[x] / n, 1) for x in ("i", "ii", "iii", "iv")},
                  "ok_with_ii": round(100 * np.mean(has), 2) if has else None, "ok_without_ii": round(100 * np.mean(no), 2) if no else None,
                  "within_item": within}
    return res


def main():
    out = {"rule": "itemdata.concl_types (i 다섯 줄 형식, ii 숨은 결론 암시, iii 영어, iv 기타)", "outputs_main_set": outputs(), "training_data_rc3": training_data()}
    (HERE / "a2_concl.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(out["training_data_rc3"], ensure_ascii=False))
    for m, v in out["outputs_main_set"].items():
        print(m, v["types_pct"], v["ok_with_ii"], v["ok_without_ii"], v["within_item"])


if __name__ == "__main__":
    main()
