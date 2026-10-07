# -*- coding: utf-8 -*-
"""업체 100 정답률 문서(VENDOR100_ACCURACY.md)의 숫자를 결과 파일에서 다시 센다. 모델을 부르지 않는다.

    python sft_dpo_inventory/pilot_001_analysis/accuracy/collect.py

- 채점·분류는 pilot_001 판정과 같은 함수(``baseline_conditions_001/compare_cells.py``: grounding_check 재채점, v4 축,
  grounding_v13 U1–U4, 보고 분류)와 같은 지연 중앙값(judge.py ``median``)을 쓴다.
- 전후 비교(표 3)는 ``pilot_001/vendor100/judgment.json``의 PROTOCOL 판정을 그대로 옮긴다(다시 판정하지 않는다).
- 결과: ``accuracy.json``.
"""
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))


def _module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


C = _module("compare_cells", ROOT / "sft_dpo_inventory/baseline_conditions_001/compare_cells.py")
J = _module("judge", ROOT / "sft_dpo_inventory/pilot_001/vendor100/judge.py")
INV = "sft_dpo_inventory"
CELLS = {
    # 표 1: 파인튜닝 전
    "HF-E": f"{INV}/thinking_prep_001/hf_e/HF-E_run1.json",
    "E": f"{INV}/pilot_prep_003/ollama/E.json",
    "B-conv": f"{INV}/pilot_prep_003/ollama/B-conv.json",
    # 표 2: 파인튜닝 후
    "HF-SFT": f"{INV}/pilot_001/vendor100/HF-sft.json",
    "HF-최종": f"{INV}/pilot_001/vendor100/HF-final.json",
    "Ollama-SFT": f"{INV}/pilot_001/vendor100/Ollama-sft.json",
    "Ollama-최종": f"{INV}/pilot_001/vendor100/Ollama-final.json",
    # 참고
    "운영 기본값 T2PC(qwen3.8:27b)": "evaluation/grounding_v11/runs/full/t2pc/dev.json",
    "HF-E 2회차": f"{INV}/thinking_prep_001/hf_e/HF-E_run2.json",
    "E(Ollama 0.34.4)": f"{INV}/baseline_conditions_001/runs/E.json",
    "F": f"{INV}/baseline_conditions_001/runs/F.json",
    "HF-F 1회차": f"{INV}/pilot_prep_001/hf/HF-F_run1.json",
    "HF-F 2회차": f"{INV}/pilot_prep_001/hf/HF-F_run2.json",
}
U_CLASS, SILENT = J.U_CLASS, J.SILENT


def main():
    empty = HERE / ".empty_arm"
    empty.mkdir(exist_ok=True)
    out = {"cells": {}}
    for name, rel in CELLS.items():
        path = ROOT / rel
        items = C.load_cell(path, empty)
        data = json.loads(path.read_text(encoding="utf-8"))
        meta = data["meta"]
        spec_path = path.with_suffix(".spec.json")
        spec = json.loads(spec_path.read_text(encoding="utf-8")) if spec_path.exists() else {}
        fp = meta.get("code_fingerprint") or spec.get("code_fingerprint")
        fp = fp.get("sha256") if isinstance(fp, dict) else fp
        s = C.summary(items)
        out["cells"][name] = {
            "source": rel, "items": s["items"], "grounding_ok": s["grounding_ok"],
            "grounding_ok_recorded_differs": s["grounding_ok_recorded_differs"],
            "정상": s["v4"].get("정상 답변", 0), "v4": s["v4"], "report_class": s["report_class"],
            "U": sum(i["report_class"] == U_CLASS for i in items.values()),
            "silent": sum(i["report_class"] == SILENT for i in items.values()),
            "latency_median_s": round(J.median([(i["total_ms"] or 0) / 1000 for i in items.values()]), 2),
            "model": meta.get("model"), "model_digest": meta.get("model_digest"),
            "ollama_version": meta.get("ollama_version"), "quantization": (meta.get("model_details") or {}).get("quantization_level"),
            "prompt": (meta.get("planner_prompt_sha256") or "")[:8], "code_fingerprint": fp,
            "code_commit": meta.get("code_commit"), "started_at": meta.get("started_at"),
            "model_think": meta.get("model_think"), "condition_check": meta.get("condition_check"),
            "reference_date": meta.get("reference_date"), "command": meta.get("command"),
            "hf": {k: meta.get(k) for k in ("enable_thinking", "max_new_tokens", "dtype", "attn_implementation") if k in meta},
        }
    empty.rmdir()
    judgment = json.loads((ROOT / f"{INV}/pilot_001/vendor100/judgment.json").read_text(encoding="utf-8"))
    out["protocol"] = {label: {k: v[k] for k in ("pair", "grounding_ok", "b", "c", "mcnemar_p", "U", "U_net", "U_new", "U_gone",
                                                  "silent", "silent_net", "silent_new", "silent_gone", "latency_ratio",
                                                  "verdict", "verdict_reasons")}
                       for label, v in judgment["protocol"].items()}
    out["protocol_source"] = f"{INV}/pilot_001/vendor100/judgment.json"
    (HERE / "accuracy.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for name, c in out["cells"].items():
        print(f"{name:32} g={c['grounding_ok']:3} 정상={c['정상']:3} U={c['U']} S={c['silent']} lat={c['latency_median_s']}"
              f" fp={(c['code_fingerprint'] or '-')[:8]} commit={(c['code_commit'] or '-')[:8]} ov={c['ollama_version']}"
              f" q={c['quantization']} p={c['prompt']} think={c['model_think']} {(c['started_at'] or '')[:10]} diff={c['grounding_ok_recorded_differs']}")


if __name__ == "__main__":
    main()
