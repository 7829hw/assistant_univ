# -*- coding: utf-8 -*-
"""ablation_011 A0-soup(결정 261, PLAN_A11 4절). 학습 없음. 기존 V4 adapter S-V4-o43·o1016·o7 checkpoint-1984의 **정확한** 평균 adapter를 CPU에서 만든다.

    runtime/envs/hf/bin/python sft_dpo_inventory/ablation_011/soup/soup11.py   # -> /data/hwkim/sftdpo_work/ablation_011/soup/V4-soup3/, soup/soup_check.json

- 모듈마다 A' = concat(A1, A2, A3)(행, rank 48), B' = concat(B1, B2, B3)/3(열). r = 48, lora_alpha = 96(alpha/r = 2 = 원래 32/16) →
  B'A'·2 = (1/3) Σ B_i A_i · 2 = 세 delta의 평균. 저장 dtype은 원래와 같은 float32. 그 밖의 adapter_config 값은 o43과 같다.
- 검사: ``numpy.random.default_rng(261)``로 고른 모듈 12개(≥ 5)에서 B'A'·scale과 세 delta 평균의 최대 절대 차를 세 delta 평균의 최대 절대값으로 나눈 값이
  float64 계산과 저장 dtype(float32) 계산 모두 1e-5 미만인지. 실패하면 adapter를 쓰지 않고 멈춘다(soup만 뺌).
- 입력 adapter sha256이 pilot_010 기록(``adapters_s10_sha256.txt``)과 같은지 확인한다. 토크나이저 파일은 o43 checkpoint에서 복사(세 seed에서 같은지 확인).
"""
import hashlib
import json
import shutil
import sys
from pathlib import Path

import numpy as np
import torch
from safetensors import safe_open
from safetensors.torch import save_file

HERE = Path(__file__).resolve().parent
SRC = Path("/data/hwkim/sftdpo_work/pilot_010/train_s10")
SEEDS = ("o43", "o1016", "o7")
WANT = {"o43": "a3a1222f2900b40e30be095eb57f7f71665a9fb1b55b9b4c86370f272971ed72", "o1016": "1a25e09649959bd9d52a9e42703400e989ca208b3d195ba76e51b2b63f990e93",
        "o7": "e715e0558efb463ec58a437e59fed92f7b1b50cbc3d8555434e2f8c1506996d4"}
OUT = Path("/data/hwkim/sftdpo_work/ablation_011/soup/V4-soup3")
COPY = ("added_tokens.json", "chat_template.jinja", "merges.txt", "special_tokens_map.json", "tokenizer_config.json", "tokenizer.json", "vocab.json")
TOL = 1e-5


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    ck = {s: SRC / f"S-V4-{s}/checkpoint-1984" for s in SEEDS}
    in_sha = {s: sha(ck[s] / "adapter_model.safetensors") for s in SEEDS}
    if in_sha != WANT:
        raise SystemExit(f"input adapter sha256 mismatch: {in_sha}")
    cfgs = {s: json.loads((ck[s] / "adapter_config.json").read_text(encoding="utf-8")) for s in SEEDS}
    for s in SEEDS:
        c = cfgs[s]
        if (c["r"], c["lora_alpha"], c.get("use_rslora"), c.get("use_dora"), sorted(c["target_modules"])) != (16, 32, False, False, sorted(cfgs["o43"]["target_modules"])):
            raise SystemExit(f"unexpected adapter config {s}")
    tok_same = {f: len({sha(ck[s] / f) for s in SEEDS}) == 1 for f in COPY}
    if not all(tok_same.values()):
        raise SystemExit(f"tokenizer files differ: {tok_same}")
    T = {s: {} for s in SEEDS}
    for s in SEEDS:
        with safe_open(str(ck[s] / "adapter_model.safetensors"), "pt") as f:
            for k in f.keys():
                T[s][k] = f.get_tensor(k)
    keys = sorted(T["o43"])
    if any(sorted(T[s]) != keys for s in SEEDS):
        raise SystemExit("adapter keys differ")
    mods = sorted({k.rsplit(".lora_", 1)[0] for k in keys})
    if any(set(k for k in keys if k.startswith(m + ".lora_")) != {f"{m}.lora_A.weight", f"{m}.lora_B.weight"} for m in mods):
        raise SystemExit("unexpected key layout")
    dtype = T["o43"][keys[0]].dtype
    new = {}
    for m in mods:
        new[f"{m}.lora_A.weight"] = torch.cat([T[s][f"{m}.lora_A.weight"] for s in SEEDS], dim=0).contiguous()
        new[f"{m}.lora_B.weight"] = (torch.cat([T[s][f"{m}.lora_B.weight"] for s in SEEDS], dim=1) / 3).to(dtype).contiguous()
    scale_old = cfgs["o43"]["lora_alpha"] / cfgs["o43"]["r"]
    r_new, alpha_new = 16 * len(SEEDS), cfgs["o43"]["lora_alpha"] * len(SEEDS)
    scale_new = alpha_new / r_new
    pick = sorted(np.random.default_rng(261).choice(len(mods), size=12, replace=False).tolist())
    checks = []
    for i in pick:
        m = mods[i]
        row = {"module": m}
        for name, dt in (("float64", torch.float64), ("stored_" + str(dtype).replace("torch.", ""), dtype)):
            mean = sum(T[s][f"{m}.lora_B.weight"].to(dt) @ T[s][f"{m}.lora_A.weight"].to(dt) * scale_old for s in SEEDS) / len(SEEDS)
            soup = new[f"{m}.lora_B.weight"].to(dt) @ new[f"{m}.lora_A.weight"].to(dt) * scale_new
            diff = (soup - mean).abs().max().item()
            ref = mean.abs().max().item()
            row[name] = {"max_abs_diff": diff, "max_abs_mean_delta": ref, "relative": diff / ref}
        row["shape_A"], row["shape_B"] = list(new[f"{m}.lora_A.weight"].shape), list(new[f"{m}.lora_B.weight"].shape)
        checks.append(row)
    ok = len(checks) >= 5 and all(v["relative"] < TOL for r in checks for k, v in r.items() if isinstance(v, dict))
    report = {"inputs": {s: {"path": str(ck[s]), "adapter_sha256": in_sha[s]} for s in SEEDS}, "rule": "A' = concat(A_i) rows, B' = concat(B_i)/3 cols, r 48, lora_alpha 96",
              "scale_old": scale_old, "scale_new": scale_new, "modules": len(mods), "checked_modules": len(checks), "rng": "numpy default_rng(261) choice 12",
              "tolerance_relative": TOL, "checks": checks, "ok": ok, "tokenizer_files_same": tok_same}
    if ok:
        OUT.mkdir(parents=True, exist_ok=True)
        save_file(new, str(OUT / "adapter_model.safetensors"), metadata={"format": "pt"})
        cfg = dict(cfgs["o43"], r=r_new, lora_alpha=alpha_new)
        (OUT / "adapter_config.json").write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
        for f in COPY:
            shutil.copy2(ck["o43"] / f, OUT / f)
        # 저장한 파일을 다시 읽어 같은지
        with safe_open(str(OUT / "adapter_model.safetensors"), "pt") as f:
            report["reload_equal"] = all(torch.equal(f.get_tensor(k), new[k]) for k in new)
        report["output"] = {"path": str(OUT), "adapter_sha256": sha(OUT / "adapter_model.safetensors"), "adapter_config_sha256": sha(OUT / "adapter_config.json"),
                            "r": r_new, "lora_alpha": alpha_new}
    (HERE / "soup_check.json").write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("ok", "modules", "checked_modules", "scale_old", "scale_new")}, ensure_ascii=False),
          max(v["relative"] for r in checks for v in r.values() if isinstance(v, dict)), report.get("output"))
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
