# -*- coding: utf-8 -*-
"""ablation_013 사후 진단(**고정 분석 도구 밖**, 결과를 본 뒤 만든 것). 진단, 판정 아님. 모델 호출 없음.
A0 새 seed(o2026117·o2026131)의 H-dev 정답률이 낮게 나와(78.6·86.6), seed 간 차이가 어느 서명·tool에 몰리는지 본다.
H-dev 셀의 행 ``category``(match·failed·answered_mismatch·refused_*)를 PLAN 5.2 서명(``analyze_a13.tsig``)과 정답 tool(``xtab_a12.classify``)로 나눈다.

    runtime/envs/hf/bin/python sft_dpo_inventory/ablation_013/analysis/posthoc_a13.py   # -> analysis/posthoc_a13.json
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import analyze_a13 as A  # noqa: E402
import xtab_a12 as XT  # noqa: E402

ROOT = A.ROOT
C12, C13 = "sft_dpo_inventory/ablation_012/cells", "sft_dpo_inventory/ablation_013/cells"
MODELS = {**{f"A0_{s}": f"{C12}/hdev_a0_{s}_s1.json" for s in A.NEW}, **{f"A0_{s}": f"{C13}/hdev_a0_{s}_s1.json" for s in A.ADD},
          **{f"A3T_{s}": f"{C13}/hdev_a3t_{s}_s1.json" for s in A.NEW}, **{f"V4_{s}": f"{C12}/hdev_v4_{s}_s1.json" for s in A.OLD},
          "base_k1": f"{C12}/hdev_base_s1.json", "base_k2": f"{C12}/hdev_base_s2.json"}


def main():
    import evaluate_vendor100 as EV
    gold = {i["id"]: i for i in EV.load_gold(ROOT / A.HDEV_GOLD)["items"]}
    key = {i: (A.tsig(g.get("gold")), XT.classify(g.get("gold"))[0]) for i, g in gold.items()}
    out = {"note": "사후 진단(고정 도구 밖). 진단, 판정 아님.", "models": {}}
    for n, p in MODELS.items():
        rows = json.loads((ROOT / p).read_text(encoding="utf-8"))["rows"]
        by = defaultdict(Counter)
        for r in rows:
            t, tool = key[r["id"]]
            for k in (f"sig:{t}", f"tool:{tool}", "all"):
                by[k][r.get("category")] += 1
        out["models"][n] = {k: {"items": sum(c.values()), "match_pct": round(100 * c["match"] / sum(c.values()), 1), "categories": dict(c)} for k, c in sorted(by.items())}
    keys = sorted({k for m in out["models"].values() for k in m})
    out["table_match_pct"] = {k: {n: out["models"][n][k]["match_pct"] for n in MODELS if k in out["models"][n]} for k in keys}
    (HERE / "posthoc_a13.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for k, v in out["table_match_pct"].items():
        print(k, v)


if __name__ == "__main__":
    main()
