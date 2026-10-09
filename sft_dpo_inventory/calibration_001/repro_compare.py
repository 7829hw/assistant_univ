# -*- coding: utf-8 -*-
"""재현성 확인(PLAN.md 5절): 같은 seed로 두 번 생성한 원문을 호출별로 바이트 비교한다. 모델 호출 없음.

    python sft_dpo_inventory/calibration_001/repro_compare.py

- HF: ``raw_text``. Ollama: thinking과 content. 원문은 ignore 경로(``training/generated/calibration_001/raw``)에서 읽고,
  결과(``repro/repro_compare.json``)에는 일치 여부·sha256·처음 갈라진 위치만 남긴다.
"""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAW = HERE.parents[1] / "training/generated/calibration_001/raw"
PAIRS = {"HF-base": ("hf_base_a", "hf_base_b"), "Ollama E": ("ollama_E_a", "ollama_E_b")}


def text(r):
    return r["raw_text"] if "raw_text" in r else (r.get("thinking") or "") + "\n</think>\n" + (r.get("content") or "")


def load(name):
    path = RAW / f"{name}_raw.jsonl"
    if not path.exists():
        return None
    return {(r["id"], r["call"]): r for r in map(json.loads, path.read_text(encoding="utf-8").splitlines())}


def first_diff(a, b):
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            return i
    return min(len(a), len(b)) if len(a) != len(b) else None


def main():
    out = {}
    for label, (x, y) in PAIRS.items():
        a, b = load(x), load(y)
        if a is None or b is None:
            out[label] = {"missing": [n for n, d in ((x, a), (y, b)) if d is None]}
            continue
        calls = []
        for key in sorted(set(a) | set(b)):
            ta, tb = (text(a[key]) if key in a else None), (text(b[key]) if key in b else None)
            same = ta is not None and ta == tb
            calls.append({"id": key[0], "call": key[1], "same": same,
                          "seed": [(a.get(key) or {}).get("sampling_seed"), (b.get(key) or {}).get("sampling_seed")],
                          "sha256": [ta and hashlib.sha256(ta.encode()).hexdigest()[:16], tb and hashlib.sha256(tb.encode()).hexdigest()[:16]],
                          "chars": [ta and len(ta), tb and len(tb)],
                          "first_diff_char": None if same or ta is None or tb is None else first_diff(ta, tb)})
        first = [c for c in calls if c["call"] == 0]
        out[label] = {"calls": len(calls), "same_calls": sum(c["same"] for c in calls),
                      "first_calls": len(first), "same_first_calls": sum(c["same"] for c in first), "detail": calls}
        print(label, out[label]["same_calls"], "/", out[label]["calls"], "first", out[label]["same_first_calls"], "/", len(first))
    (HERE / "repro" / "repro_compare.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
