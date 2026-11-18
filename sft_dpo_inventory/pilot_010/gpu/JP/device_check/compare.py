# -*- coding: utf-8 -*-
"""run.sh 결과 비교: 모델(base·V4_o101)마다 기준 GPU와 새 GPU의 호출별 (원문 sha256, 생성 token 수)를 비교 → compare.json."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def calls(p):
    d = json.loads(p.read_text(encoding="utf-8"))
    return {(r["id"], n): (c["raw_sha256"], c["generated_tokens"]) for r in d["rows"] for n, c in enumerate(r.get("hf_calls") or [])}, d["meta"].get("vllm", {}).get("base_url")


out = {"rule": "결정 83: 같은 seed 5문항 출력 바이트 단위 일치", "models": {}}
for m in ("base", "V4_o101"):
    ref, ru = calls(HERE / f"dc_ref_{m}_s1.json")
    new, nu = calls(HERE / f"dc_new_{m}_s1.json")
    diff = sorted(f"{k[0]}#{k[1]}" for k in set(ref) | set(new) if ref.get(k) != new.get(k))
    out["models"][m] = {"ref_calls": len(ref), "new_calls": len(new), "byte_identical": not diff, "different_calls": diff, "ref_url": ru, "new_url": nu}
out["all_identical"] = all(v["byte_identical"] for v in out["models"].values())
(HERE / "compare.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print(json.dumps(out, ensure_ascii=False))
