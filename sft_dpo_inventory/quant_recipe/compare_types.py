# -*- coding: utf-8 -*-
"""공식 방식 Q4(결정 75)의 텐서별 타입을 공식 qwen3:8b blob과 비교한다. CPU, 모델 호출 없음.

    /home/hwkim/sftdpo_work/llamacpp_venv/bin/python sft_dpo_inventory/quant_recipe/compare_types.py

- gguf-py(llama.cpp b11434)로 텐서 이름·모양·타입만 읽는다. 결과: ``compare_types.json``.
- 비교 대상: 공식 qwen3:8b(E) blob, 자체 Q4_K_M 두 개(base, pilot_002 최종), 공식 방식 Q4 두 개.
"""
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, "/home/hwkim/sftdpo_work/llama.cpp-b11434/gguf-py")
from gguf import GGUFReader  # noqa: E402

HERE = Path(__file__).resolve().parent
BLOBS = "/data/hwkim/ollama/models/blobs/sha256-"
FILES = {
    "official_qwen3_8b": BLOBS + "a3de86cd1c132c822487ededd47a324c50491393e6565cd14bafa40d0b8e686f",
    "base_self_q4km": "/home/hwkim/sftdpo_work/gguf/qwen3-8b-b968826d-base-Q4_K_M.gguf",
    "final_self_q4km": "/data/hwkim/sftdpo_work/gguf/qwen3-8b-pilot002-final-Q4_K_M.gguf",
    "base_official_q4": "/data/hwkim/sftdpo_work/gguf/quant_recipe/qwen3-8b-b968826d-base-Q4_K_M-official.gguf",
    "final_official_q4": "/data/hwkim/sftdpo_work/gguf/quant_recipe/qwen3-8b-pilot002-final-Q4_K_M-official.gguf",
}


def tensors(path):
    reader = GGUFReader(path)
    return {t.name: {"type": t.tensor_type.name, "shape": [int(x) for x in t.shape]} for t in reader.tensors}


def main():
    data = {k: tensors(v) for k, v in FILES.items()}
    ref = data["official_qwen3_8b"]
    out = {"files": FILES, "tensor_count": {k: len(v) for k, v in data.items()},
           "type_counts": {k: dict(Counter(t["type"] for t in v.values())) for k, v in data.items()}, "vs_official": {}}
    for k, v in data.items():
        if k == "official_qwen3_8b":
            continue
        names = set(ref) | set(v)
        diff = [{"tensor": n, "official": ref.get(n, {}).get("type"), k: v.get(n, {}).get("type")}
                for n in sorted(names) if ref.get(n, {}).get("type") != v.get(n, {}).get("type")]
        shape_diff = [n for n in names if ref.get(n, {}).get("shape") != v.get(n, {}).get("shape")]
        groups = Counter((d["tensor"].split(".")[-2] if d["tensor"].count(".") >= 2 else d["tensor"],
                          d["official"], d[k]) for d in diff)
        out["vs_official"][k] = {"same_type": len(names) - len(diff), "total": len(names), "type_diff": len(diff),
                                 "shape_diff": len(shape_diff),
                                 "diff_groups": [{"tensor": g[0], "official": g[1], "this": g[2], "count": c}
                                                 for g, c in sorted(groups.items())]}
    (HERE / "compare_types.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: {x: v[x] for x in ("same_type", "total", "type_diff", "shape_diff", "diff_groups")}
                      for k, v in out["vs_official"].items()}, ensure_ascii=False, indent=1))
    print(out["type_counts"])


if __name__ == "__main__":
    main()
