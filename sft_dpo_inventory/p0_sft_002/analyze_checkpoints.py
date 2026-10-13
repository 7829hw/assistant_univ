# -*- coding: utf-8 -*-
"""checkpoint 진단 분석(CHECKPOINT_DIAGNOSTIC_PLAN.md 4절, 결과 전에 고정). 모델 호출 없음.

    python sft_dpo_inventory/p0_sft_002/analyze_checkpoints.py   # -> checkpoint_diagnostic.json

- 입력:
  - checkpoint_diag/{arm}_ckpt{77,154,231,308}.json, 원문 training/generated/p0_sft_002/checkpoint_diag_raw/
  - Base: p0_sft_001 base 결과의 panel 문항(같은 평가 조건, 다시 재지 않음)
- 문항 지표: p0_sft_001과 같은 함수(`P.item_view`, `V98.extra_view`), panel gold로 채점.
- thinking 지표: 문항의 첫 호출(call 0) 원문 기준.
  - think_emission = 원문에 `<think>`가 있음
  - first_token = 원문 앞 공백을 뗀 첫 꼴: `<think>` → think, `{` → json, 그 밖 → other
  - thinking_chars = `</think>` 앞 길이(없으면 0, `<think>`만 있고 잘리면 전체 길이)
- stratum별 정답 수, 학습 loss(그 checkpoint 직전 77 step 평균, trainer_state).
- 재현 확인: checkpoint-308 결과의 문항별 category가 p0_sft_001 최종 평가(같은 adapter)와 같은가.
"""
import collections
import importlib.util
import json
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
P1 = ROOT / "sft_dpo_inventory/p0_sft_001"
RAW = ROOT / "training/generated/p0_sft_002/checkpoint_diag_raw"
ARMS = ("gold_only", "clean_hybrid")
STEPS = (77, 154, 231, 308)


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


A = _load("ab_p0_3_analyze", ROOT / "evaluation/partial_grounding/ab_p0_3/analyze.py")
P, V98 = A.P, A.V98


def first_calls(raw_path, key_of=lambda r: r["id"]):
    out = {}
    for line in Path(raw_path).read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        if r["call"] == 0:
            out[key_of(r)] = r
    return out


def think_view(raw):
    text = raw["raw_text"]
    head = text.lstrip()
    first = "think" if head.startswith("<think>") else "json" if head.startswith("{") else "other"
    if "</think>" in text:
        chars = len(text.split("</think>", 1)[0].split("<think>", 1)[-1].strip())
    elif "<think>" in text:
        chars = len(text)
    else:
        chars = 0
    return {"think": "<think>" in text, "first": first, "thinking_chars": chars, "tokens": raw["generated_tokens"],
            "truncated": raw["done_reason"] == "length"}


def summarize(views, thinks, strata):
    n = len(views)
    m = V98.cell_metrics(list(views.values()))
    tv = list(thinks.values())
    return {"n": n, "correct": sum(v["correct"] for v in views.values()),
            "semantic_correctness": round(m["semantic_correctness"], 3),
            "grounding_failure": m["grounding_failure"], "structural_first_response": m["structural_first_response"],
            "malformed_first": m["malformed_first"],
            "think_emission_rate": round(sum(t["think"] for t in tv) / n, 3),
            "first_token": dict(collections.Counter(t["first"] for t in tv)),
            "thinking_chars_median": statistics.median(t["thinking_chars"] for t in tv),
            "generated_tokens_median": statistics.median(t["tokens"] for t in tv),
            "truncated": sum(t["truncated"] for t in tv),
            "by_stratum": {s: [sum(views[k]["correct"] for k in ks), len(ks)] for s, ks in strata.items()}}


def main():
    panel = json.loads((HERE / "diagnostic_panel.json").read_text(encoding="utf-8"))
    P.V.GOLD_PATH = HERE / "diagnostic_panel_gold.yaml"
    gold = {i["id"]: i for i in P.V.load_gold(P.V.GOLD_PATH)["items"]}
    strata = collections.defaultdict(list)
    for p in panel["items"]:
        strata[p["stratum"]].append(p["key"])
    result = {"panel_size": len(gold), "runs": {}}
    # Base(p0_sft_001 결과 재사용)
    views, thinks = {}, {}
    for key, item in gold.items():
        s, i = key.split(":", 1)
        rows = {r["id"]: r for r in json.loads((P1 / f"evaluation/base/{s}.json").read_text(encoding="utf-8"))["rows"]}
        v = P.item_view(item, rows[i])
        v.update(V98.extra_view(item, rows[i]))
        v["malformed_first"] = v["first_error"] in V98.MALFORMED
        views[key] = v
        thinks[key] = think_view(first_calls(ROOT / f"training/generated/p0_sft_001/eval_raw/base_{s}.jsonl")[i])
    result["runs"]["base"] = summarize(views, thinks, strata)
    reproduce = {}
    for arm in ARMS:
        state = json.loads((P1 / f"training/{arm}/trainer_state.json").read_text(encoding="utf-8"))
        losses = {x["step"]: x["loss"] for x in state["log_history"] if "loss" in x}
        for step in STEPS:
            name = f"{arm}_ckpt{step}"
            f = HERE / "checkpoint_diag" / f"{name}.json"
            if not f.is_file():
                continue
            rows = {r["id"]: r for r in json.loads(f.read_text(encoding="utf-8"))["rows"]}
            raws = first_calls(RAW / f"{name}.jsonl")
            views = {}
            for key, item in gold.items():
                v = P.item_view(item, rows[key])
                v.update(V98.extra_view(item, rows[key]))
                v["malformed_first"] = v["first_error"] in V98.MALFORMED
                views[key] = v
            summary = summarize(views, {k: think_view(raws[k]) for k in gold}, strata)
            window = [losses[s] for s in range(step - 76, step + 1) if s in losses]
            summary["train_loss_window_mean"] = round(sum(window) / len(window), 4)
            summary["epoch"] = round(step / 154, 2)
            result["runs"][name] = summary
            if step == 308:
                same = 0
                for key in gold:
                    s, i = key.split(":", 1)
                    old = {r["id"]: r for r in json.loads((P1 / f"evaluation/{arm}/{s}.json").read_text(encoding="utf-8"))["rows"]}
                    same += old[i]["category"] == rows[key]["category"]
                reproduce[arm] = {"same_category": same, "of": len(gold)}
    result["reproduce_ckpt308_vs_p0_sft_001"] = reproduce
    (HERE / "checkpoint_diagnostic.json").write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for k, v in result["runs"].items():
        print(k, {x: v[x] for x in ("correct", "think_emission_rate", "first_token", "thinking_chars_median",
                                     "structural_first_response", "by_stratum")})
    print("reproduce", reproduce)


if __name__ == "__main__":
    main()
