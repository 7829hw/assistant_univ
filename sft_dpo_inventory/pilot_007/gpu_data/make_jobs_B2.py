# -*- coding: utf-8 -*-
"""B2단계 작업 표·평가 셀 sampling seed·판정 spec(결정 206–210, 지시 2.2·S2). ``make_jobs_B.py``(B단계 고정본)의 사본: base 셋째 셀 없음(base는 B단계까지의 k=12 재사용, 결정 208),
ID·LoRA 이름·셀 label·학습 wrapper(``train_b7b.py``, configs_b2)·지연 출력만 B2. PLAN_B2 고정 전에 커밋한다. scheduler8(세 장, Ollama GPU = GPU 2)이 읽는다.

    python3 make_jobs_B2.py   # -> gpu/jobs_B2.json, gpu/cell_seeds_B2.json, gates/gate_spec_B2.json

학습(``train_b7b.py``: O4' 순서 파일대로 순차 학습, 25·50·75·100% 저장; raw 작업, server "train" → CUDA_VISIBLE_DEVICES = 그 GPU):
  같은 순서 seed의 F·P를 같은 바퀴에 두려고 바퀴마다 우선을 나눈다 — 1: F-o43·P-o43·F-o1016, 2: P-o1016·F-o7·P-o7, 3: F-o11·P-o11·F-o2027, 4: P-o2027.
평가(우선 5·7·8 = 지시의 2–4, 학습이 모두 먼저; B의 우선 6 base 셋째 셀은 B2에 없음):
  5 E-B2-main_<모델>: 100% checkpoint, 주 셋(selection_v2 + holdout) k=4, sampling seed_base 20261100(학습 모델 셀의 기존 규칙).
  7 E-B2-dev_<모델>: valid98·aux k=4, seed_base 20261100.
  8 L-B2: 지연 창(``pilot_006/latency/latency6.py``: base → F-o43 → P-o43, 한 서버·한 GPU, 동시 1, 고정 30문항) — 다른 작업이 모두 끝난 뒤(``done:`` 전부 + ``notrain``),
    시작 전 다른 두 GPU가 빌 때까지 최대 25분 기다림(쉬는 서버 10분 규칙), latency6가 측정 중 다른 두 GPU가 비었는지 30초마다 확인. ``--gpu-index`` = 서버 포트 − 8620(스케줄러 규칙).
판정 spec: base = B단계와 같은 셀(selection_v2 B1·X2·B-base3 k=12, holdout B2·B-base3 k=8; 결정 208), seed_cells 다섯, latency(o43), 진단 부분집합(결정 140·155,
pilot_006 spec과 같은 목록), 개발 셋.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
P7 = HERE.parent
PY = "/data/hwkim/sftdpo_work/runtime/envs/hf/bin/python"
OUT = "/data/hwkim/sftdpo_work/pilot_007/train_b2"
SEEDS = ["o43", "o1016", "o7", "o11", "o2027"]
FINAL = {"F": 1811, "P": 1775}
ROUNDS = [(1, "F", "o43"), (1, "P", "o43"), (1, "F", "o1016"), (2, "P", "o1016"), (2, "F", "o7"), (2, "P", "o7"),
          (3, "F", "o11"), (3, "P", "o11"), (3, "F", "o2027"), (4, "P", "o2027")]
TARGET = {"F": "full", "P": "partial"}
MODEL_SEED_BASE, BASE3_SEED_BASE = 20261100, 20261300
C7 = "sft_dpo_inventory/pilot_007/cells/"


def jid(a, o):
    return f"B2-{a}-{o}"


def lora(a, o):
    return f"B2_{a}_{o}"


def ck(a, o):
    return f"{OUT}/{jid(a, o)}/checkpoint-{FINAL[a]}"


jobs, seeds_rec = [], {}
for prio, a, o in ROUNDS:
    cfg = f"sft_dpo_inventory/pilot_007/train_data/configs_b2/{jid(a, o)}.yaml"
    jobs.append({"id": jid(a, o), "type": "raw", "kind": f"train_b7b_{jid(a, o)}", "server": "train", "est": 180 if a == "F" else 210, "prio": prio,
                 "cmd": [PY, "{WT}/sft_dpo_inventory/pilot_007/train_data/train_b7b.py", "--config", "{WT}/" + cfg], "outputs": []})
for _, a, o in ROUNDS:
    cells = [{"label": f"{lora(a, o).lower()}_{g}", "model": lora(a, o), "target": TARGET[a], "gold": g, "k": 4, "seed_base": MODEL_SEED_BASE, "greedy": False} for g in ("sel", "holdout")]
    jobs.append({"id": f"E-B2-main_{a}-{o}", "type": "cells", "kind": f"cells_{jid(a, o)}_main_k4", "server": f"lora:{lora(a, o)}={ck(a, o)}", "est": 40, "prio": 5,
                 "deps": [f"file:{ck(a, o)}/adapter_model.safetensors|{jid(a, o)}"], "cells": cells})
    for c in cells:
        seeds_rec[c["label"]] = {"seed_base": MODEL_SEED_BASE, "round_seeds": [MODEL_SEED_BASE + k for k in range(1, 5)], "model": c["model"], "gold": c["gold"]}
for _, a, o in ROUNDS:
    cells = [{"label": f"{lora(a, o).lower()}_{g}", "model": lora(a, o), "target": TARGET[a], "gold": g, "k": 4, "seed_base": MODEL_SEED_BASE, "greedy": False} for g in ("valid98", "aux")]
    jobs.append({"id": f"E-B2-dev_{a}-{o}", "type": "cells", "kind": f"cells_{jid(a, o)}_valid98_aux_k4", "server": f"lora:{lora(a, o)}={ck(a, o)}", "est": 40, "prio": 7,
                 "deps": [f"file:{ck(a, o)}/adapter_model.safetensors|{jid(a, o)}"], "cells": cells})
    for c in cells:
        seeds_rec[c["label"]] = {"seed_base": MODEL_SEED_BASE, "round_seeds": [MODEL_SEED_BASE + k for k in range(1, 5)], "model": c["model"], "gold": c["gold"]}
others = ",".join(j["id"] for j in jobs)
lat_out = "/home/hwkim/assistant_univ/sft_dpo_inventory/pilot_007/latency/B2"
lat_raw = "/home/hwkim/assistant_univ/training/generated/pilot_007/latency_raw"
# 다른 GPU의 쉬는 vLLM 서버는 10분 뒤에야 내려가므로(scheduler8 idle 600 s) 두 GPU가 빌 때까지 최대 25분 기다린 뒤 시작한다(latency6가 시작 전에 다시 확인).
lat_wait = ("IDX=$(( {PORT} - 8620 )); ME=$(nvidia-smi -i $IDX --query-gpu=uuid --format=csv,noheader); "
            "for i in $(seq 1 100); do [ -z \"$(nvidia-smi --query-compute-apps=gpu_uuid --format=csv,noheader | grep -v \"$ME\")\" ] && break; sleep 15; done; ")
lat_cmd = lat_wait + (f"mkdir -p {lat_out} {lat_raw} && {PY} {{WT}}/sft_dpo_inventory/pilot_006/latency/latency6.py --port {{PORT}} --gpu-index $(( {{PORT}} - 8620 )) "
           f"--f-model F --p-model P --out-dir {lat_out} --raw-dir {lat_raw} --label-prefix latB2")
jobs.append({"id": "L-B2", "type": "raw", "kind": "latency_base_F-o43_P-o43", "server": f"lora:F={ck('F', 'o43')} P={ck('P', 'o43')}", "est": 40, "prio": 8,
             "deps": ["notrain", f"done:{others}"], "cmd": ["bash", "-c", lat_cmd], "outputs": [f"{lat_out}/latency_summary.json"]})
seeds_rec["latency(latB2-base/F/P)"] = {"seed_base": 20261100, "round_seeds": [20261101], "note": "latency6.py 고정 규칙(셀과 같은 회차 seed)"}
(HERE / "jobs_B2.json").write_text(json.dumps({"jobs": jobs}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
(HERE / "cell_seeds_B2.json").write_text(json.dumps({"decision": "208 (U4), S2: 실행 전 커밋; base 셀은 새로 재지 않음(B단계 cell_seeds_B.json의 b_base3, pilot_006_prep B1·X2·B2)", "cells": seeds_rec}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
# 판정 spec
P6C, P6P = "sft_dpo_inventory/pilot_006/cells/", "sft_dpo_inventory/pilot_006_prep/cells/"
ks = lambda p, k=4: [f"{p}_s{i}.json" for i in range(1, k + 1)]  # noqa: E731
p6spec = json.loads((P7.parent / "pilot_006/run3/gate_spec_main.json").read_text(encoding="utf-8"))
spec = {"label": "pilot_007 B2단계 주 판정(주 셋 151, O4' 순서 seed 5개 짝, 계층 bootstrap)",
        "sets": {"selection_v2": p6spec["sets"]["selection_v2"], "holdout": p6spec["sets"]["holdout"],
                 "valid98": "sft_dpo_inventory/pilot_004/valid98/valid98_gold.yaml", "aux": "sft_dpo_inventory/pilot_002/aux_test/aux_test_gold.yaml"},
        "base": {"selection_v2": ks(P6P + "b1_sel_base") + ks(P6P + "x2_sel_base_17408") + ks(C7 + "b_base3_sel"),
                 "holdout": ks(P6P + "b2_holdout_base") + ks(C7 + "b_base3_holdout")},
        "seed_cells": {o: {a: {"selection_v2": ks(f"{C7}{lora(a, o).lower()}_sel"), "holdout": ks(f"{C7}{lora(a, o).lower()}_holdout")} for a in ("F", "P")} for o in SEEDS},
        "latency": {"base": "sft_dpo_inventory/pilot_007/latency/B2/latB2-base_s1.json", "F": "sft_dpo_inventory/pilot_007/latency/B2/latB2-F_s1.json",
                    "P": "sft_dpo_inventory/pilot_007/latency/B2/latB2-P_s1.json"},
        "diagnostic_subsets": p6spec["diagnostic_subsets"],
        "dev": {g: {o: {a: ks(f"{C7}{lora(a, o).lower()}_{g}") for a in ("F", "P")} for o in SEEDS} for g in ("valid98", "aux")}}
(P7 / "gates").mkdir(exist_ok=True)
(P7 / "gates/gate_spec_B2.json").write_text(json.dumps(spec, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print(len(jobs), [(j["prio"], j["id"]) for j in jobs])
