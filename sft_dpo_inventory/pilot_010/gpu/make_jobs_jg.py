# -*- coding: utf-8 -*-
"""pilot_010 JG(결정 270, PLAN_JG) 작업 표. 평가만(학습 없음). **판정 뒤 추가(사후), PF2·H-final 세 번째 사용.**

    python3 sft_dpo_inventory/pilot_010/gpu/make_jobs_jg.py --phase smoke --commit <고정 커밋 40자리>            # -> gpu/JG/jobs_jg_smoke.json
    python3 sft_dpo_inventory/pilot_010/gpu/make_jobs_jg.py --phase main --cond g0|g1 --commit <고정 커밋 40자리>  # -> gpu/JG/jobs_jg_main.json

- 어댑터 22개(SFT 5·RR 5·RR+NM4 5·RR+NM8 7)의 ``adapter_model.safetensors`` sha256을 기록과 대조한다(``gpu/JG/adapters_check_<phase>.json``).
  다르거나 없으면 그 seed의 작업을 만들지 않고 기록에 적는다(PLAN_JG 2절).
- 실행기·인자는 J·JP·JQ 셀과 같다(동시 PF2 8·H-final/H-dev 32, ``--grounding-target full``, 17,408 서버, ``--seed-base 20261100``). 바뀐 것은 decoding뿐:
  G0 = 기존 실행기 ``--greedy``(sampling 인자·seed 없이 → client가 temperature 0 요청, k=1),
  G1 = ``*_g1.py`` 사본(temperature 0.2·top-p 0.95·top-k 20, PF2 k=4 회차 20261101–04, H-final k=1 회차 20261101).
- smoke(PLAN_JG 1절): H-dev(``ablation_012/e2/h_dev.yaml``) 앞 300문항, G0, base·SFT ``o43``·RR+NM4 ``o101``. 셀 ``cells/JG/smoke``, 다시 돌리기 없음.
- main 우선순위(PLAN_JG 2절): RR+NM4·SFT·base PF2(10–20) → 같은 arm H-final(30–40) → RR+NM8 PF2(50–56)·H-final(60–66) → RR PF2(70–74)·H-final(80–84).
  PF2는 ``no_rerun``(J와 같음), H-final은 scheduler20 기본 다시 돌리기 검사(잘림 > 1%, 같은 조건 한 번).
"""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
P10 = HERE.parent
INV = P10.parent
PY = "/data/hwkim/sftdpo_work/runtime/envs/hf/bin/python"
PFD = "/data/hwkim/sftdpo_work/protected_final_v2"
HF_GOLD = "sft_dpo_inventory/ablation_012/e2/h_final.yaml"
HDEV_GOLD = "sft_dpo_inventory/ablation_012/e2/h_dev.yaml"
W = "/data/hwkim/sftdpo_work"
SEEDS = {"V4": ("o101", "o523", "o2029", "o31", "o20271027"), "B2F": ("o43", "o1016", "o7", "o11", "o2027"),
         "V8": ("o43", "o1016", "o7") + tuple(f"o{s}" for s in json.loads((P10 / "build/seeds_jq.json").read_text(encoding="utf-8"))["order_seeds"]),
         "P9": ("o43", "o1016", "o7", "o11", "o2027")}


def ckpt(arm, s):
    if arm == "B2F":
        return f"{W}/pilot_007/train_b2/B2-F-{s}/checkpoint-1811"
    if arm == "P9":
        return f"{W}/pilot_009/train_p9/P9-F-{s}/checkpoint-1993"
    if arm == "V4":
        return f"{W}/pilot_010/train_j/J-V4-{s}/checkpoint-1984"
    if s in ("o43", "o1016", "o7"):
        return f"{W}/pilot_010/train_s10/S-V8-{s}/checkpoint-2071"
    return f"{W}/pilot_010/train_jq/JQ-V8-{s}/checkpoint-2071"


def recorded(arm, s):
    """기록된 sha256: SFT = pilot_007/adapters_B2.json, RR·RR+NM4·RR+NM8 기존 = FREEZE_JP.json, RR+NM8 새 = train/logs_jq/adapters_jq.json."""
    if arm == "B2F":
        return json.loads((INV / "pilot_007/adapters_B2.json").read_text(encoding="utf-8"))["adapters"][f"B2-F-{s}"]["checkpoint-1811"]["adapter_sha256"], "pilot_007/adapters_B2.json"
    if arm == "V8" and s not in ("o43", "o1016", "o7"):
        return (json.loads((P10 / "train/logs_jq/adapters_jq.json").read_text(encoding="utf-8"))[f"JQ-V8-{s}"]["sha256"]["adapter_model.safetensors"],
                "pilot_010/train/logs_jq/adapters_jq.json")
    return json.loads((P10 / "FREEZE_JP.json").read_text(encoding="utf-8"))["adapters_sha256_checked"][arm][s], "pilot_010/FREEZE_JP.json"


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def check(arms):
    out = {}
    for arm in arms:
        for s in SEEDS[arm]:
            p = Path(ckpt(arm, s)) / "adapter_model.safetensors"
            want, src = recorded(arm, s)
            got = sha(p) if p.exists() else None
            out[f"{arm}:{s}"] = {"path": str(p), "recorded": want, "recorded_in": src, "observed": got, "ok": got == want}
    return out


def hf_cmd(cond, model, label, k, gold, out_dir, raw_dir, only=None, sealed=True):
    runner = "run_cell6x.py" if cond == "g0" else "run_cell6x_g1.py"
    sel = f"--only {only}" if only else "--all-items"
    return {"name": f"{label}_s{k}", "label": label, "k": k,
            "cmd": (f"{PY} {{WT}}/sft_dpo_inventory/pilot_006_prep/gpu_data/{runner} --port {{PORT}} --model {model} --label {label} --k {k} "
                    f"--concurrency 32 --grounding-target full --out-dir {out_dir} --raw-dir {raw_dir} --seed-base 20261100 --gold {gold} {sel}"
                    f"{' --sealed' if sealed else ''}{' --greedy' if cond == 'g0' else ''}")}


def pf_cmd(cond, model, label, k):
    runner = "run_cell_pf2.py" if cond == "g0" else "run_cell_pf2_g1.py"
    return {"name": f"{label}_s{k}", "label": label, "k": k,
            "cmd": (f"umask 077 && {PY} {{WT}}/sft_dpo_inventory/pilot_010/protected_final_v2/{runner} --port {{PORT}} --model {model} --label {label} --k {k} "
                    f"--concurrency 8 --grounding-target full --out-dir {PFD}/cells --raw-dir {PFD}/raw --seed-base 20261100 --gold {PFD}/pf2_gold.yaml "
                    f"--all-items --sealed --reference-date 2026-10-26{' --greedy' if cond == 'g0' else ''}")}


def server(arm, s):
    return "base" if arm == "base" else f"lora:{arm}_{s}={ckpt(arm, s)}"


def model(arm, s):
    return "base" if arm == "base" else f"{arm}_{s}"


def tag(arm, s):
    return "base" if arm == "base" else f"{arm.lower()}_{s}"


def smoke_jobs(commit, chk):
    import yaml
    ids = [i["id"] for i in yaml.safe_load((INV.parent / HDEV_GOLD).read_text(encoding="utf-8"))["items"][:300]]
    out_dir, raw_dir = "{MAIN}/sft_dpo_inventory/pilot_010/cells/JG/smoke", "{MAIN}/training/generated/pilot_010/cells_raw_JG/smoke"
    jobs = []
    for i, (arm, s) in enumerate((("base", "base"), ("B2F", "o43"), ("V4", "o101"))):
        if arm != "base" and not chk[f"{arm}:{s}"]["ok"]:
            continue
        c = hf_cmd("g0", model(arm, s), f"hdev300g0_{tag(arm, s)}", 1, HDEV_GOLD, out_dir, raw_dir, only=",".join(ids), sealed=False)
        outs = [f"/home/hwkim/assistant_univ/sft_dpo_inventory/pilot_010/cells/JG/smoke/{c['name']}.{x}" for x in ("json", "log")] + \
               [f"/home/hwkim/assistant_univ/training/generated/pilot_010/cells_raw_JG/smoke/{c['name']}_raw.jsonl"]
        deps = [] if arm == "base" else [f"file:{ckpt(arm, s)}/adapter_model.safetensors|"]
        jobs.append({"id": f"SM-{arm}-{s}" if arm != "base" else "SM-base", "type": "raw", "kind": f"smoke_jg_hdev300_g0_{arm}", "server": server(arm, s), "est": 12,
                     "prio": 1 + i, "commit": commit, "deps": deps, "cells": [c], "no_rerun": True, "outputs": outs})
    return jobs, ids


def main_jobs(commit, cond, chk):
    k_pf = 1 if cond == "g0" else 4
    out = []
    order = [("pf", ("V4", "B2F", "base"), 10), ("hf", ("V4", "B2F", "base"), 30), ("pf", ("V8",), 50), ("hf", ("V8",), 60), ("pf", ("P9",), 70), ("hf", ("P9",), 80)]
    for kind, arms, p0 in order:
        n = 0
        for arm in arms:
            for s in (("base",) if arm == "base" else SEEDS[arm]):
                if arm != "base" and not chk[f"{arm}:{s}"]["ok"]:
                    continue
                deps = [] if arm == "base" else [f"file:{ckpt(arm, s)}/adapter_model.safetensors|"]
                if kind == "pf":
                    cells = [pf_cmd(cond, model(arm, s), f"pf2{cond}_{tag(arm, s)}", k) for k in range(1, k_pf + 1)]
                    outs = [p for c in cells for p in (f"{PFD}/cells/{c['name']}.json", f"{PFD}/cells/{c['name']}.log", f"{PFD}/raw/{c['name']}_raw.jsonl")]
                    out.append({"id": f"PF-{arm}-{s}" if arm != "base" else "PF-base", "type": "raw", "kind": f"pf2_jg_{cond}_{arm}-{s}_k{k_pf}", "server": server(arm, s),
                                "est": 10 * k_pf, "prio": p0 + n, "commit": commit, "deps": deps, "cells": cells, "no_rerun": True, "outputs": outs})
                else:
                    cells = [hf_cmd(cond, model(arm, s), f"hfinal{cond}_{tag(arm, s)}", 1, HF_GOLD, "{MAIN}/sft_dpo_inventory/pilot_010/cells/JG",
                                    "{MAIN}/training/generated/pilot_010/cells_raw_JG")]
                    out.append({"id": f"HF-{arm}-{s}" if arm != "base" else "HF-base", "type": "raw", "kind": f"hfinal_jg_{cond}_{arm}-{s}_k1", "server": server(arm, s),
                                "est": 45, "prio": p0 + n, "commit": commit, "deps": deps, "cells": cells})
                n += 1
    return sorted(out, key=lambda j: (j["prio"], j["id"]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", choices=("smoke", "main"), required=True)
    ap.add_argument("--cond", choices=("g0", "g1"))
    ap.add_argument("--commit", required=True)
    a = ap.parse_args()
    if len(a.commit) != 40:
        raise SystemExit("--commit must be a full 40-hex commit")
    if a.phase == "main" and not a.cond:
        raise SystemExit("--cond required for main")
    G = HERE / "JG"
    G.mkdir(parents=True, exist_ok=True)
    chk = check(("B2F", "V4") if a.phase == "smoke" else ("V4", "B2F", "V8", "P9"))
    (G / f"adapters_check_{a.phase}.json").write_text(json.dumps({"phase": a.phase, "adapters": chk, "all_ok": all(v["ok"] for v in chk.values())},
                                                                  ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    if a.phase == "smoke":
        jobs, ids = smoke_jobs(a.commit, chk)
        note = {"items": "h_dev.yaml 앞 300문항", "first_id": ids[0], "last_id": ids[-1], "ids_sha256": hashlib.sha256(",".join(ids).encode()).hexdigest()}
    else:
        jobs, note = main_jobs(a.commit, a.cond, chk), {"cond": a.cond}
    body = {"note": f"pilot_010 JG(결정 270, PLAN_JG) {a.phase}, 고정 커밋 {a.commit[:8]}. 판정 뒤 추가(사후), PF2·H-final 세 번째 사용.", **note, "jobs": jobs}
    p = G / f"jobs_jg_{a.phase}.json"
    p.write_text(json.dumps(body, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    bad = [k for k, v in chk.items() if not v["ok"]]
    print(json.dumps({"jobs": [(j["prio"], j["id"]) for j in jobs], "adapter_mismatch": bad}, ensure_ascii=False))


if __name__ == "__main__":
    main()
