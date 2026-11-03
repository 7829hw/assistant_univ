# -*- coding: utf-8 -*-
"""ablation_012 작업 표(결정 262) → ``gpu/jobs_a12.json``. scheduler14가 (prio, id) 순으로 고른다(작은 값 먼저).

우선순위(결정 262): (1) A3R 학습 T-*(d1 seed 3개 prio 1–3 → d2 prio 4–6) → (2) 학습이 끝난 모델의 E1 E-*(prio 10–15) → (3) CT10K C-*(prio 20–23) → (4) H-dev H-*(prio 30–).
다시 돌리기 R12-NN은 scheduler14가 prio 0으로 넣는다. 모든 평가 작업은 ``gpu/ready/A12_TOOLS.json``(분석 도구 smoke·고정 커밋 뒤)이 있어야 시작한다.

- E1: refusal_dev v2(거부 90 + 대조 30) → valid98 → aux, k = 1–4(회차 seed 20261100 + k), 동시 8 — ablation_011 E 작업(``make_jobs_a11.py``)과 같은 명령(출력 위치만 ablation_012).
- CT10K: ``client_test_10000/qa_test_10000.yaml``, 묶음 ``client_test_10000/gpu/chunks/c1–c5``, k=1(seed 20261101), 동시 32 — ``run_ct10k.sh``와 같은 client·인자(출력 위치·label만 다름).
- H-dev: ``ablation_012/e2/h_dev.yaml``(2,000) k=1(seed 20261101; base는 k=1·2 = 20261101·02), 동시 32, ``--all-items``.
- 서버: ``lora:<이름=경로>``(rank 16), soup ``lora64:``(rank 64, ablation_011 E-soup과 같음), base ``base``(요청 ``--model base``).
- 학습: ``ablation_011/train/train_a11.py --config ablation_012/train/configs/<id>.yaml``; epoch 끝 checkpoint = checkpoint-<레코드 수>.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = "/data/hwkim/sftdpo_work/runtime/envs/hf/bin/python"
MAIN = "/home/hwkim/assistant_univ"
OUT = f"{MAIN}/sft_dpo_inventory/ablation_012/cells"
RAW = f"{MAIN}/training/generated/ablation_012/cells_raw"
T12 = "/data/hwkim/sftdpo_work/ablation_012/train"
T11 = "/data/hwkim/sftdpo_work/ablation_011/train"
S10 = "/data/hwkim/sftdpo_work/pilot_010/train_s10"
SOUP = "/data/hwkim/sftdpo_work/ablation_011/soup/V4-soup3"
SEEDS = (1102, 211102, 2026113)
STEPS = {"A0": 1984, "A1": 1984, "A2": 1944, "A3": 1522, "A3R-d1": 1520, "A3R-d2": 1525}
E1_SETS = (("rdevv2", "sft_dpo_inventory/pilot_009/refusal_dev2/approved/rdev_v2_gold.yaml"),
           ("valid98", "sft_dpo_inventory/pilot_004/valid98/valid98_gold.yaml"),
           ("aux", "sft_dpo_inventory/pilot_002/aux_test/aux_test_gold.yaml"))
CT = "sft_dpo_inventory/client_test_10000/qa_test_10000.yaml"
CH = "{WT}/sft_dpo_inventory/client_test_10000/gpu/chunks"
HDEV = "sft_dpo_inventory/ablation_012/e2/h_dev.yaml"
SEC_PER_STEP = 5.9
TOOLS = "ready:A12_TOOLS"


def run(model, label, k, conc, gold, extra):
    return (f"{PY} {{WT}}/sft_dpo_inventory/pilot_006_prep/gpu_data/run_cell6x.py --port {{PORT}} --model {model} --label {label} --k {k} "
            f"--concurrency {conc} --grounding-target full --out-dir {OUT} --raw-dir {RAW} --seed-base 20261100 --gold {gold} {extra}").strip()


def e1_cells(model, prefix):
    return [{"name": f"{prefix}_{st}_s{k}", "label": f"{prefix}_{st}", "k": k, "cmd": run(model, f"{prefix}_{st}", k, 8, gold, "--all-items")}
            for st, gold in E1_SETS for k in range(1, 5)]


def ct_cells(model, prefix):
    return [{"name": f"{prefix}_c{c}_s1", "label": f"{prefix}_c{c}", "k": 1, "cmd": run(model, f"{prefix}_c{c}", 1, 32, CT, f'--only "$(cat {CH}/c{c}.txt)"')}
            for c in range(1, 6)]


def hdev_cells(model, prefix, ks=(1,)):
    return [{"name": f"{prefix}_s{k}", "label": prefix, "k": k, "cmd": run(model, prefix, k, 32, HDEV, "--all-items")} for k in ks]


def lora(name, path, rank64=False):
    return f"{'lora64' if rank64 else 'lora'}:{name}={path}"


def main():
    jobs = []
    p = 1
    a3r = []
    for arm in ("A3R-d1", "A3R-d2"):
        for s in SEEDS:
            cid = f"{arm}-o{s}"
            ck = f"{T12}/{cid}/checkpoint-{STEPS[arm]}"
            jobs.append({"id": f"T-{cid}", "type": "raw", "kind": f"train_a12_{cid}", "server": "train", "est": round(STEPS[arm] * SEC_PER_STEP / 60), "prio": p, "deps": [],
                         "cmd": [PY, "{WT}/sft_dpo_inventory/ablation_011/train/train_a11.py", "--config", f"{{WT}}/sft_dpo_inventory/ablation_012/train/configs/{cid}.yaml"]})
            a3r.append((cid, ck, arm.replace("-", "").lower() + f"_o{s}"))
            p += 1
    for i, (cid, ck, tag) in enumerate(a3r):
        name = cid.replace("-", "_")
        jobs.append({"id": f"E-{cid}", "type": "raw", "kind": f"cells_a12_{cid}_rdevv2_valid98_aux_k4", "server": lora(name, ck), "est": 45, "prio": 10 + i,
                     "deps": [f"file:{ck}/adapter_model.safetensors|T-{cid}", TOOLS], "cells": e1_cells(name, f"a12_{tag}")})
    ct = [("A0-o1102", lora("A0_o1102", f"{T11}/A0-o1102/checkpoint-1984")), ("A0-o211102", lora("A0_o211102", f"{T11}/A0-o211102/checkpoint-1984")),
          ("A0-o2026113", lora("A0_o2026113", f"{T11}/A0-o2026113/checkpoint-1984")), ("soup", lora("V4_soup3", SOUP, True))]
    for i, (cid, srv) in enumerate(ct):
        model = srv.split(":", 1)[1].split("=", 1)[0]
        jobs.append({"id": f"C-{cid}", "type": "raw", "kind": f"ct10k_a12_{cid}_k1", "server": srv, "est": 150, "prio": 20 + i, "deps": [TOOLS],
                     "cells": ct_cells(model, f"ct10k_{cid.replace('-', '_').lower()}")})
    # H-dev: A0·A3·A3R 먼저(A3 분리), 다음 soup·V4 기존 seed·base·A1·A2
    hd = []
    for s in SEEDS:
        hd.append((f"A0-o{s}", lora(f"A0_o{s}", f"{T11}/A0-o{s}/checkpoint-1984"), []))
    for s in SEEDS:
        hd.append((f"A3-o{s}", lora(f"A3_o{s}", f"{T11}/A3-o{s}/checkpoint-1522"), []))
    for cid, ck, tag in a3r:
        hd.append((cid, lora(cid.replace("-", "_"), ck), [f"file:{ck}/adapter_model.safetensors|T-{cid}"]))
    hd.append(("soup", lora("V4_soup3", SOUP, True), []))
    for s in ("o43", "o1016", "o7"):
        hd.append((f"V4-{s}", lora(f"V4_{s}", f"{S10}/S-V4-{s}/checkpoint-1984"), []))
    hd.append(("base-k1", "base", []))
    hd.append(("base-k2", "base", []))
    for arm in ("A1", "A2"):
        for s in SEEDS:
            hd.append((f"{arm}-o{s}", lora(f"{arm}_o{s}", f"{T11}/{arm}-o{s}/checkpoint-{STEPS[arm]}"), []))
    for i, (cid, srv, deps) in enumerate(hd):
        if srv == "base":
            model, ks, prefix = "base", (int(cid[-1]),), "hdev_base"
        else:
            model, ks, prefix = srv.split(":", 1)[1].split("=", 1)[0], (1,), f"hdev_{cid.replace('-', '_').lower()}"
        jobs.append({"id": f"H-{cid}", "type": "raw", "kind": f"hdev_a12_{cid}", "server": srv, "est": 35, "prio": 30 + i, "deps": deps + [TOOLS],
                     "cells": hdev_cells(model, prefix, ks)})
    names = [c["name"] for j in jobs for c in j.get("cells", [])]
    assert len(names) == len(set(names)), "duplicate cell names"
    (HERE / "jobs_a12.json").write_text(json.dumps({"label": "ablation_012(결정 262)", "jobs": jobs}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(len(jobs), "jobs;", len(names), "cells;", [(j["id"], j["prio"], j["est"]) for j in jobs])


if __name__ == "__main__":
    main()
