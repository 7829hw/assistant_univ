# -*- coding: utf-8 -*-
"""pilot_008 준비 GPU 작업 표(진단용, 판정에 쓰지 않음; 지시 2절). scheduler10(세 장, Ollama GPU = GPU 2)이 읽는다.

    python3 make_jobs_P8.py   # -> gpu/jobs_P8.json, gpu/seeds_P8.json

| 우선 | ID | 작업 |
| 1 | J-b011 | batch011 초안 100(r1 60·r2 40)에 base(vLLM, Full prompt) 첫 응답(greedy, ``collect6b --mode first``, 채점 ``judge``)과 표본(greedy 1 + 8, ``--mode self``, J1 설정) |
| 2 | J-rdev-base·J-rdev-o11 | refusal_dev 초안 60에 base·F-o11(LoRA ``B2_F_o11``) 각각 k=4(``run_cell6x``, 동시 8, seed_base 20261100) |
| 3 | J-o11-b011 | batch011 초안 100에 F-o11 첫 응답(greedy, ``collect8 --mode first --model B2_F_o11``) |

- 입력 파일 sha256을 명령 안에서 확인한다. 원문은 ``training/generated/pilot_008/{self,cells}_raw``(ignore), manifest·첫 응답 채점·셀 json은 커밋.
"""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
P8 = HERE.parent
MAIN = "/home/hwkim/assistant_univ"
PY = "/home/hwkim/sftdpo_work/hfvenv/bin/python"
B11 = P8.parents[0] / "batch011"
RDEV = P8 / "refusal_dev"
SELF = f"{MAIN}/training/generated/pilot_008/self"
O11 = {"name": "B2_F_o11", "ckpt": "/home/hwkim/sftdpo_work/pilot_007/train_b2/B2-F-o11/checkpoint-1811",
       "sha256": "2d94933b5756c769c1b1068a6003540fd92d64ab7717b1fc4ea6793ef78574f2"}
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()  # noqa: E731
chk = lambda p: f"echo '{sha(p)}  {{MAIN}}/{Path(p).relative_to(MAIN)}' | sha256sum -c - && "  # noqa: E731
F1, FS, G = B11 / "inputs_first_response.jsonl", B11 / "inputs_self.jsonl", RDEV / "rdev_gold.yaml"
jb011 = (chk(F1) + chk(FS) + f"mkdir -p {SELF}/raw && "
         f"{PY} {{WT}}/sft_dpo_inventory/pilot_006_prep/gpu/collect6b.py --port {{PORT}} --server-meta /data/hwkim/sftdpo_work/pilot_006_prep/vllm --mode first --label Jb011_first "
         f"--inputs {{MAIN}}/sft_dpo_inventory/batch011/inputs_first_response.jsonl --raw-out {SELF}/raw/Jb011_first_raw.jsonl --out {{MAIN}}/sft_dpo_inventory/batch011/base_first_response.jsonl && "
         f"{PY} {{WT}}/sft_dpo_inventory/pilot_006_prep/gpu/collect6b.py --port {{PORT}} --server-meta /data/hwkim/sftdpo_work/pilot_006_prep/vllm --mode self --grounding-target full --label Jb011_full "
         f"--inputs {{MAIN}}/sft_dpo_inventory/batch011/inputs_self.jsonl --raw-out {SELF}/raw/Jb011_full_raw.jsonl --out {SELF}/Jb011_full_manifest.json")
jo11 = (chk(F1) + f"mkdir -p {SELF}/raw && "
        f"{PY} {{WT}}/sft_dpo_inventory/pilot_008/gpu/collect8.py --port {{PORT}} --server-meta /data/hwkim/sftdpo_work/pilot_006_prep/vllm --mode first --model {O11['name']} "
        f"--adapter-sha256 {O11['sha256']} --label Jo11b011_first --inputs {{MAIN}}/sft_dpo_inventory/batch011/inputs_first_response.jsonl "
        f"--raw-out {SELF}/raw/Jo11b011_first_raw.jsonl --out {{MAIN}}/sft_dpo_inventory/batch011/o11_first_response.jsonl")


def rdev(model, label):
    runs = " && ".join(f"{PY} {{WT}}/sft_dpo_inventory/pilot_006_prep/gpu/run_cell6x.py --port {{PORT}} --model {model} --label {label} --k {k} --concurrency 8 "
                       f"--grounding-target full --out-dir {{MAIN}}/sft_dpo_inventory/pilot_008/cells --raw-dir {{MAIN}}/training/generated/pilot_008/cells_raw "
                       f"--seed-base 20261100 --gold sft_dpo_inventory/pilot_008/refusal_dev/rdev_gold.yaml --all-items" for k in range(1, 5))
    return chk(G) + runs


jobs = [
    {"id": "J-b011", "type": "raw", "kind": "first_response_and_self_base_batch011", "server": "b17408", "est": 90, "prio": 1, "cmd": ["bash", "-c", jb011], "outputs": []},
    {"id": "J-rdev-base", "type": "raw", "kind": "cells_rdev_base_k4", "server": "b17408", "est": 30, "prio": 2, "cmd": ["bash", "-c", rdev("base", "rdev_base")], "outputs": []},
    {"id": "J-rdev-o11", "type": "raw", "kind": "cells_rdev_o11_k4", "server": f"lora:{O11['name']}={O11['ckpt']}", "est": 30, "prio": 2,
     "cmd": ["bash", "-c", rdev(O11["name"], "rdev_o11")], "outputs": []},
    {"id": "J-o11-b011", "type": "raw", "kind": "first_response_o11_batch011", "server": f"lora:{O11['name']}={O11['ckpt']}", "est": 20, "prio": 3,
     "cmd": ["bash", "-c", jo11], "outputs": []},
]
(HERE / "jobs_P8.json").write_text(json.dumps({"jobs": jobs}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
seeds = {"J-b011 self": {"round_seed": 20261015, "rule": "collect6b 기본(J1): 표본 s의 seed = EV.call_seed(20261015, 문항 id, s), greedy 1 + 표본 8"},
         "J-b011 first / J-o11-b011 first": {"greedy": True},
         "J-rdev cells": {"seed_base": 20261100, "round_seeds": [20261101, 20261102, 20261103, 20261104]}}
(HERE / "seeds_P8.json").write_text(json.dumps(seeds, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print([(j["id"], j["server"][:30]) for j in jobs])
