# -*- coding: utf-8 -*-
"""ablation_013 작업 표(결정 263) → ``gpu/jobs_a13.json``. scheduler15가 (prio, id) 순으로 고른다(작은 값 먼저).

우선순위(결정 263 4절): (1) 학습 T-*(A3T seed 3개 prio 1–3 → A0 새 seed 2개 prio 4–5) → (2) 학습이 끝난 모델의 E1 E-*(prio 10–14)·H-dev H-*(prio 20–24)
→ (3) batch014 진단 열 J-b014-*(prio 30–). 다시 돌리기 R13-NN은 scheduler15가 prio 0으로 넣는다.
평가 작업(E·H)은 ``gpu/ready/A13_TOOLS.json``(분석 도구 smoke·고정 커밋 뒤)이 있어야 시작한다. J-b014 작업은 ``gpu/ready/J-b014.json``(batch014 초안 검사·커밋 뒤)이 있어야 시작하고,
명령 첫머리에서 ``check_ready13.sh``로 입력 sha256을 다시 맞춘다.

- 학습: ``ablation_011/train/train_a11.py --config ablation_013/train/configs/<id>.yaml``; epoch 끝 checkpoint = checkpoint-<레코드 수>(A3T 1,786, A0 1,984).
- E1: refusal_dev v2 → valid98 → aux, k = 1–4(회차 seed 20261100 + k), 동시 8 — ablation_012 E 작업(``make_jobs_a12.py``)과 같은 명령(출력 위치만 ablation_013).
- H-dev: ``ablation_012/e2/h_dev.yaml``(2,000) k=1(seed 20261101), 동시 32, ``--all-items`` — ablation_012 H 작업과 같은 명령.
- J-b014-base: base(``base`` 서버), ``collect6b --mode first``(greedy) → ``--mode self``(greedy 1 + 표본 8, round seed 20261015, 표본 seed = EV.call_seed) — pilot_010 J-b013과 같은 명령.
- J-b014-v4-<seed>: V4 o1016·o7·o43(pilot_010 S-V4)과 A0 o1102·o211102·o2026113(ablation_011)의 첫 응답(greedy, ``collect8 --mode first --model <LoRA 이름>``) — pilot_010 J-p9-b013과 같은 명령.
  adapter sha256은 커밋 파일에 쓰지 않는다(결정 255; ``/data/hwkim/sftdpo_work/ablation_013/adapters_sha256.txt``).
- 서버: ``lora:<이름=경로>``(rank 16), base ``base``.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = "/data/hwkim/sftdpo_work/runtime/envs/hf/bin/python"
MAIN = "/home/hwkim/assistant_univ"
OUT = f"{MAIN}/sft_dpo_inventory/ablation_013/cells"
RAW = f"{MAIN}/training/generated/ablation_013/cells_raw"
SELF = "{MAIN}/training/generated/ablation_013/self"
VM = "/data/hwkim/sftdpo_work/pilot_006_prep/vllm"
T13 = "/data/hwkim/sftdpo_work/ablation_013/train"
T11 = "/data/hwkim/sftdpo_work/ablation_011/train"
S10 = "/data/hwkim/sftdpo_work/pilot_010/train_s10"
B14 = "sft_dpo_inventory/batch014"
TRAIN = (("A3T", 1102), ("A3T", 211102), ("A3T", 2026113), ("A0", 2026117), ("A0", 2026131))
STEPS = {"A3T": 1786, "A0": 1984}
E1_SETS = (("rdevv2", "sft_dpo_inventory/pilot_009/refusal_dev2/approved/rdev_v2_gold.yaml"),
           ("valid98", "sft_dpo_inventory/pilot_004/valid98/valid98_gold.yaml"),
           ("aux", "sft_dpo_inventory/pilot_002/aux_test/aux_test_gold.yaml"))
HDEV = "sft_dpo_inventory/ablation_012/e2/h_dev.yaml"
SEC_PER_STEP = 5.9
TOOLS = "ready:A13_TOOLS"
JB = "ready:J-b014"
CHK = "bash {MAIN}/sft_dpo_inventory/ablation_013/gpu/check_ready13.sh J-b014 && "
V4S = (("V4_o1016", f"{S10}/S-V4-o1016/checkpoint-1984"), ("V4_o7", f"{S10}/S-V4-o7/checkpoint-1984"), ("V4_o43", f"{S10}/S-V4-o43/checkpoint-1984"),
       ("A0_o1102", f"{T11}/A0-o1102/checkpoint-1984"), ("A0_o211102", f"{T11}/A0-o211102/checkpoint-1984"), ("A0_o2026113", f"{T11}/A0-o2026113/checkpoint-1984"))


def run(model, label, k, conc, gold, extra):
    return (f"{PY} {{WT}}/sft_dpo_inventory/pilot_006_prep/gpu_data/run_cell6x.py --port {{PORT}} --model {model} --label {label} --k {k} "
            f"--concurrency {conc} --grounding-target full --out-dir {OUT} --raw-dir {RAW} --seed-base 20261100 --gold {gold} {extra}").strip()


def e1_cells(model, prefix):
    return [{"name": f"{prefix}_{st}_s{k}", "label": f"{prefix}_{st}", "k": k, "cmd": run(model, f"{prefix}_{st}", k, 8, gold, "--all-items")}
            for st, gold in E1_SETS for k in range(1, 5)]


def hdev_cells(model, prefix):
    return [{"name": f"{prefix}_s1", "label": prefix, "k": 1, "cmd": run(model, prefix, 1, 32, HDEV, "--all-items")}]


def main():
    jobs = []
    for p, (arm, s) in enumerate(TRAIN, start=1):
        cid = f"{arm}-o{s}"
        jobs.append({"id": f"T-{cid}", "type": "raw", "kind": f"train_a13_{cid}", "server": "train", "est": round(STEPS[arm] * SEC_PER_STEP / 60), "prio": p, "deps": [],
                     "cmd": [PY, "{WT}/sft_dpo_inventory/ablation_011/train/train_a11.py", "--config", f"{{WT}}/sft_dpo_inventory/ablation_013/train/configs/{cid}.yaml"]})
    for i, (arm, s) in enumerate(TRAIN):
        cid = f"{arm}-o{s}"
        ck = f"{T13}/{cid}/checkpoint-{STEPS[arm]}"
        name = cid.replace("-", "_")
        tag = f"{arm.lower()}_o{s}"
        dep = f"file:{ck}/adapter_model.safetensors|T-{cid}"
        jobs.append({"id": f"E-{cid}", "type": "raw", "kind": f"cells_a13_{cid}_rdevv2_valid98_aux_k4", "server": f"lora:{name}={ck}", "est": 45, "prio": 10 + i,
                     "deps": [dep, TOOLS], "cells": e1_cells(name, f"a13_{tag}")})
        jobs.append({"id": f"H-{cid}", "type": "raw", "kind": f"hdev_a13_{cid}", "server": f"lora:{name}={ck}", "est": 35, "prio": 20 + i,
                     "deps": [dep, TOOLS], "cells": hdev_cells(name, f"hdev_{tag}")})
    jb = (f"mkdir -p {SELF}/raw && {PY} {{WT}}/sft_dpo_inventory/pilot_006_prep/gpu_data/collect6b.py --port {{PORT}} --server-meta {VM} --mode first --label Jb014_first "
          f"--inputs {{MAIN}}/{B14}/inputs_first_response.jsonl --raw-out {SELF}/raw/Jb014_first_raw.jsonl --out {{MAIN}}/{B14}/base_first_response.jsonl && "
          f"{PY} {{WT}}/sft_dpo_inventory/pilot_006_prep/gpu_data/collect6b.py --port {{PORT}} --server-meta {VM} --mode self --grounding-target full --label Jb014_full "
          f"--inputs {{MAIN}}/{B14}/inputs_self.jsonl --raw-out {SELF}/raw/Jb014_full_raw.jsonl --out {SELF}/Jb014_full_manifest.json")
    jobs.append({"id": "J-b014-base", "type": "raw", "kind": "first_response_and_self_base_batch014", "server": "base", "est": 60, "prio": 30, "deps": [JB],
                 "cmd": ["bash", "-c", CHK + jb]})
    for i, (name, ck) in enumerate(V4S):
        lab = f"Jv4b014_{name}_first"
        cmd = (f"mkdir -p {SELF}/raw && {PY} {{WT}}/sft_dpo_inventory/pilot_008/gpu/collect8.py --port {{PORT}} --server-meta {VM} --mode first --model {name} "
               f"--label {lab} --inputs {{MAIN}}/{B14}/inputs_first_response.jsonl --raw-out {SELF}/raw/{lab}_raw.jsonl --out {{MAIN}}/{B14}/v4_first_response_{name}.jsonl")
        jobs.append({"id": f"J-b014-v4-{name}", "type": "raw", "kind": f"first_response_{name}_batch014", "server": f"lora:{name}={ck}", "est": 15, "prio": 31 + i,
                     "deps": [JB], "cmd": ["bash", "-c", CHK + cmd]})
    names = [c["name"] for j in jobs for c in j.get("cells", [])]
    assert len(names) == len(set(names)), "duplicate cell names"
    (HERE / "jobs_a13.json").write_text(json.dumps({"label": "ablation_013(결정 263)", "jobs": jobs}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    seeds = {"E1": {"seed_base": 20261100, "rule": "회차 k seed = 20261100 + k (ablation_011·012와 같음)"}, "H-dev": {"seed": 20261101},
             "J-b014-base self": {"round_seed": 20261015, "rule": "collect6b 기본(J-b013과 같음): greedy 1 + 표본 8, 표본 seed = EV.call_seed(20261015, 문항 id, s)"},
             "J-b014-base first / J-b014-v4-*": {"greedy": True}}
    (HERE / "seeds_a13.json").write_text(json.dumps(seeds, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(len(jobs), "jobs;", len(names), "cells;", [(j["id"], j["prio"], j["est"]) for j in jobs])


if __name__ == "__main__":
    main()
