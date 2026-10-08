# -*- coding: utf-8 -*-
"""pilot_002 checkpoint별 기록(PLAN 4절)을 한 표로 모은다. 모델을 부르지 않는다. 업체 100은 쓰지 않는다.

    python sft_dpo_inventory/pilot_002/selection/summarize.py

checkpoint마다:
- 학습(``train_logs/{stage}_log_history.json``, ``{stage}_profile.json``, ``{stage}_nvidia_smi.txt``):
  - loss: 그 step의 기록값과 직전 checkpoint 뒤부터 그 step까지의 평균.
  - step당 시간: 같은 구간의 평균(profile ``step_seconds``, 평가·저장 제외).
  - peak 메모리: nvidia-smi는 0.5초 간격 기록을 누적 step 시간에 맞춰 그 step까지의 최대(근사, 모델 적재 시간만큼 앞당겨짐).
    torch는 profile에 단계 전체 최대만 있어 단계 값으로 적는다.
- selection_v1(``runs/sel_{stage}_step{N}.json``): grounding_ok, 결과 분류(outcome:error_code), 업체식 분류, 첫 응답 일치,
  지연(문항 초 중앙·합계), 생성 상한 호출 수, 루프 판정 수(결정 40-D ``is_loop``를 모든 호출의 thinking에 적용, 원문은
  ``training/generated/pilot_002/sel_*_raw.jsonl``), 평가 GPU UUID.
결과: ``SUMMARY.json``, ``SUMMARY.md``.
"""
import json
import statistics
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
P2 = HERE.parent
ROOT = P2.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_001_analysis"))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_prep_004/loop_filter"))

from apply_filter import is_loop, loop_metrics, split_think  # noqa: E402

RAW = ROOT / "training/generated/pilot_002"
BASE = ROOT / "sft_dpo_inventory/pilot_prep_005/sets/runs/selection_base.json"


def read(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def loops(raw_path):
    hits = []
    for r in read(raw_path):
        m = loop_metrics(split_think(r["raw_text"])[0])
        reasons = (is_loop(m) if m else ["empty_thinking"]) or []
        if reasons:
            hits.append({"id": r["id"], "call": r["call"], "reasons": reasons, "done_reason": r["done_reason"]})
    return hits


def eval_summary(path):
    res = json.loads(Path(path).read_text(encoding="utf-8"))
    rows, s = res["rows"], res["summary"]
    raw = Path(res["meta"]["raw_out"])
    loop_hits = loops(raw) if raw.exists() else None
    return {"result": str(Path(path).relative_to(ROOT)), "grounding_ok": s["grounding_ok"], "items": s["items"],
            "first_raw_ok": s["first_raw_ok"], "outcomes": s["outcomes"],
            "vendor_style": dict(Counter(r["vendor_style_category"] for r in rows)),
            "seconds_median": statistics.median(r["seconds"] for r in rows), "seconds_total": s["seconds"],
            "model_calls": s["model_calls"], "truncated_calls": s["truncated_calls"],
            "loop_calls": len(loop_hits) if loop_hits is not None else None,
            "loop_items": len({h["id"] for h in loop_hits}) if loop_hits is not None else None,
            "loop_hits": loop_hits, "device_uuid": res["meta"].get("device_uuid"),
            "adapter": res["meta"].get("adapter"), "adapter_sha256": res["meta"].get("adapter_sha256"),
            "raw_out_sha256": res["meta"].get("raw_out_sha256")}


def stage_summary(stage):
    logs = P2 / "train_logs"
    profile = json.loads((logs / f"{stage}_profile.json").read_text(encoding="utf-8"))
    history = [h for h in json.loads((logs / f"{stage}_log_history.json").read_text(encoding="utf-8")) if "loss" in h]
    smi = [int(x) for x in (logs / f"{stage}_nvidia_smi.txt").read_text().split() if x.isdigit()]
    step_seconds = profile["step_seconds"]
    cum = [sum(step_seconds[:i + 1]) for i in range(len(step_seconds))]
    load = profile.get("model_load_seconds") or 0
    peak_torch = max((e.get("cuda") or {}).get("max_memory_allocated", 0) for e in profile["events"])
    peak_reserved = max((e.get("cuda") or {}).get("max_memory_reserved", 0) for e in profile["events"])
    runs = sorted((HERE / "runs").glob(f"sel_{stage}_step*.json"), key=lambda p: int(p.stem.split("step")[1]))
    out, prev = [], 0
    for run in runs:
        step = int(run.stem.split("step")[1])
        window = [h for h in history if prev < h["step"] <= step]
        at = next((h for h in history if h["step"] == step), None)
        upto = int((cum[step - 1] + load) / 0.5) if step - 1 < len(cum) else len(smi)
        row = {"step": step, "loss_at_step": at and at["loss"],
               "loss_mean_window": round(statistics.mean(h["loss"] for h in window), 5) if window else None,
               "seconds_per_step_window": round(statistics.mean(step_seconds[prev:step]), 2),
               "nvidia_smi_peak_mib_upto": max(smi[:max(upto, 1)]) if smi else None}
        if stage == "dpo" and window:
            row["reward_accuracy_mean_window"] = round(statistics.mean(h.get("rewards/accuracies", 0) for h in window), 3)
            row["reward_margin_mean_window"] = round(statistics.mean(h.get("rewards/margins", 0) for h in window), 3)
        row.update(eval_summary(run))
        out.append(row)
        prev = step
    return {"stage": stage, "optimizer_steps": profile["optimizer_steps"], "total_seconds": round(profile["total_seconds"]),
            "seconds_per_step": round(profile["seconds_per_step"], 2),
            "torch_max_allocated_gib": round(peak_torch / 2**30, 1), "torch_max_reserved_gib": round(peak_reserved / 2**30, 1),
            "nvidia_smi_peak_mib": max(smi) if smi else None,
            "gpu": (P2 / "train_logs" / f"{stage}_gpu.txt").read_text().strip(), "checkpoints": out}


def main():
    stages = {}
    for stage in ("sft", "dpo"):
        if (P2 / "train_logs" / f"{stage}_profile.json").exists():
            stages[stage] = stage_summary(stage)
    base = eval_summary(BASE)
    out = {"base_hf_e": base, "stages": stages}
    for name in ("selection_sft.json", "selection_dpo.json"):
        if (P2 / name).exists():
            out[name.removesuffix(".json")] = json.loads((P2 / name).read_text(encoding="utf-8"))["selected"]
    (HERE / "SUMMARY.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    lines = ["# pilot_002 checkpoint 기록(selection_v1)", "",
             "`summarize.py`가 만든다. 선택 규칙: selection_v1 grounding_ok 최고, 동점이면 이른 step(PLAN 3절).", "",
             f"base HF-E: grounding_ok {base['grounding_ok']}/100, 생성 상한 {base['truncated_calls']}, "
             f"루프 호출 {base['loop_calls']}, 문항 초 중앙 {base['seconds_median']}(`{base['result']}`).", ""]
    for stage, s in stages.items():
        sel = out.get(f"selection_{stage}", {})
        lines += [f"## {stage.upper()}", "",
                  f"- {s['optimizer_steps']} step, {s['total_seconds']}초, step당 {s['seconds_per_step']}초, GPU `{s['gpu']}`.",
                  f"- 메모리: torch max allocated {s['torch_max_allocated_gib']} GiB / reserved {s['torch_max_reserved_gib']} GiB"
                  f"(단계 전체), nvidia-smi peak {s['nvidia_smi_peak_mib']} MiB.",
                  f"- 선택: step {sel.get('step')}(grounding_ok {sel.get('grounding_ok')}).", "",
                  "| step | loss(그 step / 구간 평균) | step당 초 | nvidia-smi peak MiB(그 step까지) | grounding_ok | 첫 응답 일치 "
                  "| 정상 종료 answered | 생성 상한 호출 | 루프 호출(문항) | 문항 초 중앙 | 평가 GPU |",
                  "|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|"]
        for c in s["checkpoints"]:
            answered = sum(v for k, v in c["outcomes"].items() if k.startswith("answered:"))
            lines.append(f"| {c['step']} | {c['loss_at_step']} / {c['loss_mean_window']} | {c['seconds_per_step_window']} "
                         f"| {c['nvidia_smi_peak_mib_upto']} | **{c['grounding_ok']}** | {c['first_raw_ok']} | {answered} "
                         f"| {c['truncated_calls']} | {c['loop_calls']}({c['loop_items']}) | {c['seconds_median']} "
                         f"| `{(c['device_uuid'] or '')[:12]}…` |")
        lines += ["", "결과 분류(outcome:error_code):", ""]
        for c in s["checkpoints"]:
            lines.append(f"- step {c['step']}: " + ", ".join(f"{k} {v}" for k, v in sorted(c["outcomes"].items(),
                                                                                         key=lambda kv: -kv[1])))
        if stage == "dpo":
            lines += ["", "DPO 구간 평균: " + "; ".join(
                f"step {c['step']} reward acc {c.get('reward_accuracy_mean_window')} margin {c.get('reward_margin_mean_window')}"
                for c in s["checkpoints"])]
        lines.append("")
    (HERE / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
