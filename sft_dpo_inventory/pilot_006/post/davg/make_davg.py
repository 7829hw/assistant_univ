# -*- coding: utf-8 -*-
"""D-avg(세션 4 우선 10, 선택): F-s43·F-s1016 e1 LoRA의 ΔW = (α/r)·B·A를 평균한 모델. 가중치는 커밋하지 않는다(규칙 3).

    hfvenv/bin/python make_davg.py   # -> /home/hwkim/sftdpo_work/pilot_006/davg/F_avg_e1/ + post/davg/davg_manifest.json

- 평균을 rank 32 LoRA 하나로 정확히 나타낸다: A' = [A₁; A₂](2r × d_in), B' = [B₁, B₂] / 2(d_out × 2r), α' = 2α →
  (α'/2r)·B'A' = (α/r)·(B₁A₁ + B₂A₂)/2. base BF16에 더해 합친 모델과 같은 ΔW이고(합칠 때의 BF16 반올림만 없음),
  비교 대상(F-s43·F-s1016 e1)과 같은 vLLM LoRA 경로로 서빙한다(같은 backend·sampler). 지시의 "base BF16에 더함"과 다른 점은 이 표현뿐이다.
- 검사: 무작위 모듈 몇 개에서 ΔW' 와 두 ΔW 평균의 최대 절대 차(float32).
"""
import hashlib
import json
import shutil
from pathlib import Path

import torch
from safetensors.torch import load_file, save_file

TRAIN = Path("/home/hwkim/sftdpo_work/pilot_006/train")
SRC = {"F43": TRAIN / "F43/checkpoint-1861", "F1016": TRAIN / "F1016/checkpoint-1861"}
OUT = Path("/home/hwkim/sftdpo_work/pilot_006/davg/F_avg_e1")
HERE = Path(__file__).resolve().parent


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    cfgs = {k: json.loads((v / "adapter_config.json").read_text()) for k, v in SRC.items()}
    c1, c2 = cfgs["F43"], cfgs["F1016"]
    assert c1["r"] == c2["r"] and c1["lora_alpha"] == c2["lora_alpha"] and not c1.get("use_rslora") and not c1.get("use_dora")
    assert sorted(c1["target_modules"]) == sorted(c2["target_modules"])
    r, alpha = c1["r"], c1["lora_alpha"]
    w1, w2 = load_file(str(SRC["F43"] / "adapter_model.safetensors")), load_file(str(SRC["F1016"] / "adapter_model.safetensors"))
    assert set(w1) == set(w2)
    out, checks = {}, []
    for key in sorted(w1):
        if ".lora_A." in key:
            out[key] = torch.cat([w1[key], w2[key]], dim=0).contiguous()
        elif ".lora_B." in key:
            out[key] = (torch.cat([w1[key], w2[key]], dim=1) / 2).contiguous()
        else:
            raise SystemExit(f"unexpected tensor {key}")
    for key in [k for k in sorted(w1) if ".lora_A." in k][::50][:6]:
        kb = key.replace(".lora_A.", ".lora_B.")
        d_avg = ((alpha / r) * (w1[kb].float() @ w1[key].float()) + (alpha / r) * (w2[kb].float() @ w2[key].float())) / 2
        d_new = (2 * alpha / (2 * r)) * (out[kb].float() @ out[key].float())
        checks.append({"module": key.replace(".lora_A.weight", ""), "max_abs_diff": float((d_avg - d_new).abs().max()), "max_abs_delta": float(d_avg.abs().max())})
    if OUT.exists():
        raise SystemExit(f"{OUT} exists")
    OUT.mkdir(parents=True)
    save_file(out, str(OUT / "adapter_model.safetensors"), metadata={"format": "pt"})
    cfg = dict(c1, r=2 * r, lora_alpha=2 * alpha)
    (OUT / "adapter_config.json").write_text(json.dumps(cfg, indent=2) + "\n")
    for f in SRC["F43"].iterdir():
        if f.name in ("tokenizer.json", "tokenizer_config.json", "special_tokens_map.json", "added_tokens.json", "vocab.json", "merges.txt", "chat_template.jinja"):
            shutil.copy(f, OUT / f.name)
    man = {"output": str(OUT), "rank": 2 * r, "lora_alpha": 2 * alpha, "sources": {k: {"path": str(v), "adapter_sha256": sha(v / "adapter_model.safetensors")} for k, v in SRC.items()},
           "adapter_sha256": sha(OUT / "adapter_model.safetensors"), "tensors": len(out), "equivalence_checks": checks,
           "note": "ΔW' = (ΔW_F43 + ΔW_F1016)/2 정확히(rank 32 concat). 서빙은 serve6c.sh(--max-lora-rank 32, 나머지 serve6b와 같음)."}
    (HERE / "davg_manifest.json").write_text(json.dumps(man, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(man, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
