# -*- coding: utf-8 -*-
"""업체 100 운영 기준선 비교(모델 호출 없음): E(현재 코드) · B-conv · 이전 E · HF-E.

    python sft_dpo_inventory/pilot_prep_003/ollama/compare_baselines.py

- 채점·분류는 ``baseline_conditions_001/compare_cells.py``를 그대로 쓴다(``grounding_check`` 재채점, v4 축, grounding_v13 U1–U4,
  보고 분류, 첫 응답 층별 결과).
- 쌍 비교(PROTOCOL 6절): grounding_ok 전이, b·c, McNemar 정확 검정(양측), U·조용한 오답 순증, 지연 중앙값 비율.
  - 주: E(791c4a68) → B-conv. 둘 다 Q4_K_M이다. 차이는 양자화가 아니라 TEMPLATE·변환 경로(라이브러리 qwen3:8b ↔ 같은 base
    revision에서 llama.cpp b11434로 변환한 GGUF, Ollama가 보고하는 template)의 효과다.
  - 참고: 이전 E(97efa866, Ollama 0.34.4) → E(791c4a68, Ollama 0.35.1), HF-E → B-conv.
- 결정 15의 보조 보고: 업체 100 문항을 v004 학습 데이터의 의미 family(thor ``family_key``)에 속한 문항과 아닌 문항으로 나눈다.
"""
import importlib.util
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("compare_cells", ROOT / "sft_dpo_inventory/baseline_conditions_001/compare_cells.py")
C = importlib.util.module_from_spec(spec)
spec.loader.exec_module(C)

CELLS = {"E_97efa866": ROOT / "sft_dpo_inventory/baseline_conditions_001/runs/E.json",
         "E": HERE / "E.json", "B-conv": HERE / "B-conv.json",
         "HF-E": ROOT / "sft_dpo_inventory/thinking_prep_001/hf_e/HF-E_run1.json"}
PAIRS = [("E", "B-conv", "주: 라이브러리 qwen3:8b ↔ base 변환본(둘 다 Q4_K_M). TEMPLATE·변환 경로 효과"),
         ("E_97efa866", "E", "참고: 코드 97efa866·Ollama 0.34.4 ↔ 코드 791c4a68·Ollama 0.35.1(같은 모델)"),
         ("HF-E", "B-conv", "참고: HF BF16 ↔ Ollama Q4_K_M 변환본(같은 base revision, HF 형식 렌더링)")]
V004 = ROOT / "training/generated/reviewed_gold_v004_t2pc/sft_train.jsonl"


def mcnemar(b, c):
    n = b + c
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, k) for k in range(max(b, c), n + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def median(values):
    values = sorted(values)
    n = len(values)
    return (values[n // 2] if n % 2 else (values[n // 2 - 1] + values[n // 2]) / 2) if n else None


def main():
    import evaluate_vendor100 as EV
    from training.annotations.inventory import family_key
    from training.data.common import read_jsonl
    empty = HERE / ".empty_arm"
    empty.mkdir(exist_ok=True)
    cells = {name: C.load_cell(path, empty) for name, path in CELLS.items()}
    empty.rmdir()
    train_families = {family_key(json.loads(r["messages"][-1]["content"])) for r in read_jsonl(V004)}
    in_family = set()
    for item in EV.load_gold(None)["items"]:
        g = EV.gold_grounding(item)
        if g is not None and family_key(g) in train_families:
            in_family.add(item["id"])
    out = {"cells": {}, "pairs": {}, "family_split(decision 15)": {"v004_train_families": len(train_families),
                                                                   "vendor_items_in_family": sorted(in_family)}}
    for name, items in cells.items():
        meta = json.loads(CELLS[name].read_text(encoding="utf-8"))["meta"]
        s = C.summary(items)
        s["latency_median_s"] = round(median([(i["total_ms"] or 0) / 1000 for i in items.values()]), 1)
        s["silent_wrong(U 아님)"] = sum(i["report_class"] == "조용한 오답(U 아님)" for i in items.values())
        s["U"] = sum(i["report_class"] == "용납할 수 없는 실패" for i in items.values())
        s["family_split"] = {"in_family": {"items": sum(k in in_family for k in items),
                                           "grounding_ok": sum(i["grounding_ok"] for k, i in items.items() if k in in_family)},
                             "outside": {"items": sum(k not in in_family for k in items),
                                         "grounding_ok": sum(i["grounding_ok"] for k, i in items.items()
                                                             if k not in in_family)}}
        s["spec"] = {k: meta.get(k) for k in ("model", "model_digest", "ollama_version", "planner_prompt_sha256",
                                               "code_commit", "reference_date", "started_at")}
        fp = meta.get("code_fingerprint")
        s["spec"]["code_fingerprint"] = fp.get("sha256") if isinstance(fp, dict) else fp
        out["cells"][name] = {"source": str(CELLS[name].relative_to(ROOT)), **s}
    for a, b, label in PAIRS:
        t = C.transition(cells[a], cells[b])
        bb, cc = len(t["grounding_gained"]), len(t["grounding_lost"])
        A, B = out["cells"][a], out["cells"][b]
        t.update(condition=label, b=bb, c=cc, mcnemar_p=round(mcnemar(bb, cc), 4),
                 U_net=B["U"] - A["U"], silent_wrong_net=B["silent_wrong(U 아님)"] - A["silent_wrong(U 아님)"],
                 latency_median_ratio=round(B["latency_median_s"] / A["latency_median_s"], 2),
                 new_U=[k for k in cells[b] if cells[b][k]["report_class"] == "용납할 수 없는 실패"
                        and cells[a][k]["report_class"] != "용납할 수 없는 실패"],
                 new_silent_wrong=[k for k in cells[b] if cells[b][k]["report_class"] == "조용한 오답(U 아님)"
                                   and cells[a][k]["report_class"] != "조용한 오답(U 아님)"],
                 family_split={part: {"b": sum(1 for k in t["grounding_gained"] if (k in in_family) == (part == "in_family")),
                                      "c": sum(1 for k in t["grounding_lost"] if (k in in_family) == (part == "in_family"))}
                               for part in ("in_family", "outside")})
        out["pairs"][f"{a}→{b}"] = t
    (HERE / "comparison.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for name, s in out["cells"].items():
        print(name, s["grounding_ok"], "normal", s["report_class"].get("정상 답변"), "U", s["U"], "silent", s["silent_wrong(U 아님)"],
              "lat", s["latency_median_s"], "fam", s["family_split"], s["spec"]["ollama_version"], s["spec"]["model_digest"] and s["spec"]["model_digest"][:8])
    for k, t in out["pairs"].items():
        print(k, t["grounding_ok_transitions"], "b", t["b"], "c", t["c"], "p", t["mcnemar_p"], "U_net", t["U_net"],
              "silent_net", t["silent_wrong_net"], "lat", t["latency_median_ratio"], t["family_split"])


if __name__ == "__main__":
    main()
