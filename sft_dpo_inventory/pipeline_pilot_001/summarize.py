# -*- coding: utf-8 -*-
"""pipeline_pilot_001 결과 요약(보고서용). GPU를 쓰지 않는다.

    python sft_dpo_inventory/pipeline_pilot_001/summarize.py

- valid 결과(``valid/*.json``): 셀별 grounding_ok·first_raw_ok·결과 종류·재질의·생성 길이, base / 고른 SFT / 고른 DPO의
  문항 단위 전이 표.
- 학습 기록: checkpoint의 ``trainer_state.json`` log_history(loss, learning rate, DPO reward), profile(step 시간, 메모리),
  nvidia-smi 표본의 peak.
- checkpoint·adapter: 경로와 adapter 파일 sha256(파일은 저장소 밖에 있고 커밋하지 않는다).
결과는 ``summary.json``에 쓴다.
"""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORK = Path("/home/hwkim/sftdpo_work/pipeline_pilot_001")


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def adapter_files(directory):
    out = {}
    for path in sorted(Path(directory).rglob("adapter_model.safetensors")):
        out[str(path)] = file_sha(path)
    return out


def nvidia_peak(path):
    values = []
    if Path(path).exists():
        for line in Path(path).read_text().splitlines():
            try:
                values.append(int(line.strip()))
            except ValueError:
                pass
    return {"samples": len(values), "peak_mib": max(values) if values else None}


def training(stage):
    out = {"checkpoints": {}}
    root = WORK / "checkpoints" / stage
    states = sorted(root.glob("checkpoint-*"), key=lambda p: int(p.name.split("-")[1]))
    if states:
        state = load(states[-1] / "trainer_state.json")
        out["log_history"] = state["log_history"]
    for ck in states:
        out["checkpoints"][ck.name] = adapter_files(ck)
    final = root / "adapter_model.safetensors"
    out["final_output"] = {str(final): file_sha(final)} if final.exists() else {}
    profile = WORK / "metrics" / f"{stage}_profile.json"
    if profile.exists():
        out["profile"] = load(profile)
    out["nvidia_smi"] = nvidia_peak(HERE / "train_logs" / f"{stage}_nvidia_smi.txt")
    return out


def main():
    cells = {}
    for path in sorted((HERE / "valid").glob("*.json")):
        result = load(path)
        cells[result["meta"]["label"]] = result
    summary = {"cells": {label: {**r["summary"], "adapter": r["meta"]["adapter"],
                                 "adapter_sha256": r["meta"]["adapter_sha256"],
                                 "device_uuid": r["meta"]["device_uuid"],
                                 "code_fingerprint": r["meta"]["code_fingerprint"][:8],
                                 "planner_prompt_sha256": r["meta"]["planner_prompt_sha256"][:8],
                                 "peak_allocated_gib": round(r["meta"]["peak_allocated_bytes"] / 2**30, 2)}
                         for label, r in cells.items()}}
    selected = {}
    for stage in ("sft", "dpo"):
        path = HERE / f"selection_{stage}.json"
        if path.exists():
            selected[stage] = load(path)["selected"]["label"]
    summary["selected"] = selected
    chain = ["base"] + [selected[s] for s in ("sft", "dpo") if s in selected]
    items = {}
    for label in chain:
        for row in cells[label]["rows"]:
            entry = items.setdefault(row["id"], {})
            entry[label] = {"ok": row["grounding_ok"], "first_raw_ok": row["first_raw_ok"],
                            "outcome": f"{row['outcome']}:{row['error_code']}",
                            "place_repair_calls": row["place_repair_calls"],
                            "diff_keys": [d[0] if isinstance(d, list) else d for d in row["grounding_diffs"]]}
    summary["chain"] = chain
    summary["items"] = items
    transitions = {}
    for left, right in zip(chain, chain[1:]):
        counts = {}
        for entry in items.values():
            key = ("O" if entry[left]["ok"] else "X") + "→" + ("O" if entry[right]["ok"] else "X")
            counts[key] = counts.get(key, 0) + 1
        transitions[f"{left}→{right}"] = counts
    summary["transitions"] = transitions
    summary["all_checkpoints_by_item"] = {
        row_id: {label: next(r["grounding_ok"] for r in cells[label]["rows"] if r["id"] == row_id)
                 for label in cells} for row_id in items}
    summary["training"] = {stage: training(stage) for stage in ("sft", "dpo")}
    (HERE / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"cells": {k: v["grounding_ok"] for k, v in summary["cells"].items()},
                      "selected": selected, "transitions": transitions}, ensure_ascii=False))


if __name__ == "__main__":
    main()
