# -*- coding: utf-8 -*-
"""run2.sh 비교: 모델마다 ref 대 new(장치 비교)와 ref 대 ref2(같은 GPU 대조)의 호출별 (원문 sha256, 생성 token 수) → compare2.json."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def calls(tag, m):
    d = json.loads((HERE / f"dc_{tag}_{m}_s1.json").read_text(encoding="utf-8"))
    return {(r["id"], n): (c["raw_sha256"], c["generated_tokens"]) for r in d["rows"] for n, c in enumerate(r.get("hf_calls") or [])}


def cmp(a, b):
    diff = sorted(f"{k[0]}#{k[1]}" for k in set(a) | set(b) if a.get(k) != b.get(k))
    return {"calls": [len(a), len(b)], "byte_identical": not diff, "different_calls": diff}


out = {"rule": "결정 83: 같은 seed 5문항 출력 바이트 단위 일치(동시 1, 셀 차례로)", "models": {}}
for m in ("base", "V4_o101"):
    ref = calls("ref", m)
    out["models"][m] = {"ref_vs_new": cmp(ref, calls("new", m)), "ref_vs_ref2_same_gpu": cmp(ref, calls("ref2", m))}
out["new_gpu_identical"] = all(v["ref_vs_new"]["byte_identical"] for v in out["models"].values())
out["same_gpu_identical"] = all(v["ref_vs_ref2_same_gpu"]["byte_identical"] for v in out["models"].values())
(HERE / "compare2.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print(json.dumps(out, ensure_ascii=False))
