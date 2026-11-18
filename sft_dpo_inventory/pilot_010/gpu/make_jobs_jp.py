# -*- coding: utf-8 -*-
"""pilot_010 판정 뒤 사후 측정(결정 268, PLAN_J_POSTHOC 3절) 작업 표 ``gpu/JP/jobs_jp.json``. 평가만(학습 작업 없음).

    python3 sft_dpo_inventory/pilot_010/gpu/make_jobs_jp.py --commit <도구 고정 커밋 40자리>

- 셀 명령은 판정 단계 J(``make_jobs_j_eval.py``)·선택 단계 ES(``make_jobs_S2.py``)와 같은 실행기·인자. 바뀐 것은 모델·라벨·출력 위치뿐.
  - PF2: ``protected_final_v2/run_cell_pf2.py``, 동시 8, k=4(회차 20261101–04), ``--sealed``, 기준일 2026-10-26, 셀·원문 700 디렉터리, ``no_rerun``.
  - H-final: ``pilot_006_prep/gpu_data/run_cell6x.py``, 동시 32, k=1(회차 20261101), ``--sealed``, 셀 ``pilot_010/cells/JP``. scheduler18 기본 다시 돌리기 검사.
  - E-A: ``pilot_006_prep/gpu_data/run_cell6x.py``(선택 단계 ``gpu/run_cell6x.py``의 decision 258 실행 사본), 동시 8, refusal_dev v2·valid98·aux 각 k=4, 셀 ``cells/JP``.
    다시 돌리기 검사(PLAN_S 5절: rdev 잘림 ≥ 2·서버 오류 ≥ 2, 그 밖 > 1%).
- 우선순위(결정 268): PF2 P9(10–14) → PF2 V8(20–22) → H-final P9(30–34) → H-final V8(40–42) → E-A V4(50–54).
- 시작 조건: 어댑터 파일 + ``ready:JP_TOOLS``.
"""
import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = "/data/hwkim/sftdpo_work/runtime/envs/hf/bin/python"
PFD = "/data/hwkim/sftdpo_work/protected_final_v2"
HF_GOLD = "sft_dpo_inventory/ablation_012/e2/h_final.yaml"
DEV_GOLD = {"rdevv2": "sft_dpo_inventory/pilot_009/refusal_dev2/approved/rdev_v2_gold.yaml", "valid98": "sft_dpo_inventory/pilot_004/valid98/valid98_gold.yaml",
            "aux": "sft_dpo_inventory/pilot_002/aux_test/aux_test_gold.yaml"}
P9 = {s: f"/data/hwkim/sftdpo_work/pilot_009/train_p9/P9-F-{s}/checkpoint-1993" for s in ("o43", "o1016", "o7", "o11", "o2027")}
V8 = {s: f"/data/hwkim/sftdpo_work/pilot_010/train_s10/S-V8-{s}/checkpoint-2071" for s in ("o43", "o1016", "o7")}
V4 = {s: f"/data/hwkim/sftdpo_work/pilot_010/train_j/J-V4-{s}/checkpoint-1984" for s in ("o101", "o523", "o2029", "o31", "o20271027")}


def pf_cell(model, label, k):
    return {"name": f"{label}_s{k}", "label": label, "k": k,
            "cmd": (f"umask 077 && {PY} {{WT}}/sft_dpo_inventory/pilot_010/protected_final_v2/run_cell_pf2.py --port {{PORT}} --model {model} --label {label} --k {k} "
                    f"--concurrency 8 --grounding-target full --out-dir {PFD}/cells --raw-dir {PFD}/raw --seed-base 20261100 --gold {PFD}/pf2_gold.yaml "
                    f"--all-items --sealed --reference-date 2026-10-26")}


def hf_cell(model, label, k):
    return {"name": f"{label}_s{k}", "label": label, "k": k,
            "cmd": (f"{PY} {{WT}}/sft_dpo_inventory/pilot_006_prep/gpu_data/run_cell6x.py --port {{PORT}} --model {model} --label {label} --k {k} "
                    f"--concurrency 32 --grounding-target full --out-dir {{MAIN}}/sft_dpo_inventory/pilot_010/cells/JP "
                    f"--raw-dir {{MAIN}}/training/generated/pilot_010/cells_raw_JP --seed-base 20261100 --gold {HF_GOLD} --all-items --sealed")}


def dev_cell(model, label, gkey, k):
    return {"name": f"{label}_s{k}", "label": label, "k": k,
            "cmd": (f"{PY} {{WT}}/sft_dpo_inventory/pilot_006_prep/gpu_data/run_cell6x.py --port {{PORT}} --model {model} --label {label} --k {k} "
                    f"--concurrency 8 --grounding-target full --out-dir {{MAIN}}/sft_dpo_inventory/pilot_010/cells/JP "
                    f"--raw-dir {{MAIN}}/training/generated/pilot_010/cells_raw_JP --seed-base 20261100 --gold {DEV_GOLD[gkey]} --all-items")}


def pf_outputs(cells):
    return [p for c in cells for p in (f"{PFD}/cells/{c['name']}.json", f"{PFD}/cells/{c['name']}.log", f"{PFD}/raw/{c['name']}_raw.jsonl")]


def jobs(commit):
    out = []
    arms = [("P9", P9, 10, 30), ("V8", V8, 20, 40)]
    for arm, ad, ppf, phf in arms:
        for i, (s, ck) in enumerate(ad.items()):
            model = f"{arm}_{s}"
            deps = [f"file:{ck}/adapter_model.safetensors|", "ready:JP_TOOLS"]
            cells = [pf_cell(model, f"pf2_{arm.lower()}_{s}", k) for k in range(1, 5)]
            out.append({"id": f"PF-{arm}-{s}", "type": "raw", "kind": f"pf2_jp_{arm}-{s}_k4", "server": f"lora:{model}={ck}", "est": 35, "prio": ppf + i, "commit": commit,
                        "deps": deps, "cells": cells, "no_rerun": True, "outputs": pf_outputs(cells)})
            out.append({"id": f"HF-{arm}-{s}", "type": "raw", "kind": f"hfinal_jp_{arm}-{s}_k1", "server": f"lora:{model}={ck}", "est": 45, "prio": phf + i, "commit": commit,
                        "deps": deps, "cells": [hf_cell(model, f"hfinal_{arm.lower()}_{s}", 1)]})
    for i, (s, ck) in enumerate(V4.items()):
        model = f"V4_{s}"
        cells = [dev_cell(model, f"jp_v4_{s}_{g}", g, k) for g in ("rdevv2", "valid98", "aux") for k in range(1, 5)]
        out.append({"id": f"EA-V4-{s}", "type": "raw", "kind": f"dev_jp_V4-{s}_rdevv2_valid98_aux_k4", "server": f"lora:{model}={ck}", "est": 45, "prio": 50 + i,
                    "commit": commit, "deps": [f"file:{ck}/adapter_model.safetensors|", "ready:JP_TOOLS"], "cells": cells})
    return sorted(out, key=lambda j: (j["prio"], j["id"]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--commit", required=True)
    a = ap.parse_args()
    if len(a.commit) != 40:
        raise SystemExit("--commit must be a full 40-hex commit")
    p = HERE / "JP/jobs_jp.json"
    body = {"note": f"pilot_010 판정 뒤 사후 측정(결정 268, PLAN_J_POSTHOC). 평가만, 도구 커밋 {a.commit[:8]}.", "jobs": jobs(a.commit)}
    p.write_text(json.dumps(body, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps([(j["prio"], j["id"], len(j["cells"])) for j in body["jobs"]], ensure_ascii=False))


if __name__ == "__main__":
    main()
