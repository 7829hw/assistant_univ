# -*- coding: utf-8 -*-
"""pilot_009 준비 GPU 작업 표(결정 228–230, 지시 2절). scheduler11(세 장, Ollama GPU = GPU 2 48f798cc)이 읽는다. 진단 작업은 판정에 쓰지 않는다.

    python3 make_jobs_prep.py   # -> gpu/jobs_prep.json, gpu/seeds_prep.json

| 우선 | ID | 작업 | 조건 |
| 1 | T-R | teacher 거부 지시 확인(20 × 8, Ollama, ``teacher/run_r9.py --job T-R``) | P1 커밋(스케줄러 시작 커밋) |
| 2 | TEACH-R | teacher 본 수집(batch011 r1 60 + batch012 r1 초안 + r2 11, × 8, Ollama) | T-R ok, ``ready/TEACH-R.json``(T-R 통과·batch012 겹침 검사 뒤 만듦) |
| 3 | J-b012 | batch012 초안 base 첫 응답(greedy, ``collect6b --mode first``)과 표본(greedy 1 + 8, ``--mode self``) | ``ready/J-b012.json``(P2 커밋 뒤) |
| 3 | J-o11-b012·J-p8-b012 | batch012 초안 F-o11(B2-F-o11)·P8-o43 첫 응답(greedy, ``collect8 --mode first``) | 같음 |
| 4 | J-rdev2-* | refusal_dev 확장 초안 60에 base·F-o11·P8 다섯 각 k=4(``run_cell6x``, 동시 8, seed_base 20261100, 진단) | ``ready/J-rdev2.json``(P3 커밋 뒤) |

- Ollama 작업(server "ollama")은 Ollama GPU에서만, 결정 55 guard(``run_r9``). scheduler11은 Ollama 작업이 남아 있으면 그 GPU에 45분 이하 작업만 주고,
  Ollama 작업 뒤 ``/api/ps``가 빌 때까지 다음 작업을 붙이지 않는다.
- 입력 파일은 MAIN에서 읽고 sha256을 ``ready/<ID>.json``을 만들 때 적는다(명령 안에서 ``sha256sum -c``로 확인). refusal_dev 확장 gold는 worktree로 복사해 상대 경로로 넘긴다
  (``run_cell6x``가 gold를 저장소 안 상대 경로로 기록하므로).
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = "/home/hwkim/sftdpo_work/hfvenv/bin/python"
VM = "/data/hwkim/sftdpo_work/pilot_006_prep/vllm"
SELF = "{MAIN}/training/generated/pilot_009/self"
B12 = "sft_dpo_inventory/batch012"
RD2 = "sft_dpo_inventory/pilot_009/refusal_dev2/rdev2_gold.yaml"
O11 = {"name": "B2_F_o11", "ckpt": "/home/hwkim/sftdpo_work/pilot_007/train_b2/B2-F-o11/checkpoint-1811",
       "sha256": "2d94933b5756c769c1b1068a6003540fd92d64ab7717b1fc4ea6793ef78574f2"}
P8 = json.loads((HERE.parents[1] / "pilot_008/adapters_P8.json").read_text(encoding="utf-8"))
P8CK = "/home/hwkim/sftdpo_work/pilot_008/train_p8/P8-F-{o}/checkpoint-2005"
SEEDS = ("o43", "o1016", "o7", "o11", "o2027")
CHK = "bash {MAIN}/sft_dpo_inventory/pilot_009/gpu/check_ready.sh {ID} && "


def first(model, sha, label, out):
    return (f"mkdir -p {SELF}/raw && {PY} {{WT}}/sft_dpo_inventory/pilot_008/gpu/collect8.py --port {{PORT}} --server-meta {VM} --mode first --model {model} "
            f"--adapter-sha256 {sha} --label {label} --inputs {{MAIN}}/{B12}/inputs_first_response.jsonl --raw-out {SELF}/raw/{label}_raw.jsonl --out {{MAIN}}/{B12}/{out}")


jb012 = (f"mkdir -p {SELF}/raw && {PY} {{WT}}/sft_dpo_inventory/pilot_006_prep/gpu/collect6b.py --port {{PORT}} --server-meta {VM} --mode first --label Jb012_first "
         f"--inputs {{MAIN}}/{B12}/inputs_first_response.jsonl --raw-out {SELF}/raw/Jb012_first_raw.jsonl --out {{MAIN}}/{B12}/base_first_response.jsonl && "
         f"{PY} {{WT}}/sft_dpo_inventory/pilot_006_prep/gpu/collect6b.py --port {{PORT}} --server-meta {VM} --mode self --grounding-target full --label Jb012_full "
         f"--inputs {{MAIN}}/{B12}/inputs_self.jsonl --raw-out {SELF}/raw/Jb012_full_raw.jsonl --out {SELF}/Jb012_full_manifest.json")


def rdev2(model, label):
    cp = f"mkdir -p {{WT}}/sft_dpo_inventory/pilot_009/refusal_dev2 && cp {{MAIN}}/{RD2} {{WT}}/{RD2} && "
    runs = " && ".join(f"{PY} {{WT}}/sft_dpo_inventory/pilot_006_prep/gpu/run_cell6x.py --port {{PORT}} --model {model} --label {label} --k {k} --concurrency 8 "
                       f"--grounding-target full --out-dir {{MAIN}}/sft_dpo_inventory/pilot_009/cells --raw-dir {{MAIN}}/training/generated/pilot_009/cells_raw "
                       f"--seed-base 20261100 --gold {RD2} --all-items" for k in range(1, 5))
    return cp + runs


def job(id_, kind, server, est, prio, cmd, deps, ready_id=None):
    full = (CHK.replace("{ID}", ready_id) + cmd) if ready_id else cmd
    return {"id": id_, "type": "raw", "kind": kind, "server": server, "est": est, "prio": prio, "deps": deps, "cmd": ["bash", "-c", full], "outputs": []}


jobs = [
    job("T-R", "teacher_refusal_check_TR", "ollama", 35, 1, f"{PY} {{WT}}/sft_dpo_inventory/pilot_009/teacher/run_r9.py --main {{MAIN}} --job T-R", []),
    job("TEACH-R", "teacher_refusal_collect", "ollama", 210, 2, f"{PY} {{WT}}/sft_dpo_inventory/pilot_009/teacher/run_r9.py --main {{MAIN}} --job TEACH-R",
        ["T-R", "ready:TEACH-R"], "TEACH-R"),
    job("J-b012", "first_response_and_self_base_batch012", "b17408", 90, 3, jb012, ["ready:J-b012"], "J-b012"),
    job("J-o11-b012", "first_response_o11_batch012", f"lora:{O11['name']}={O11['ckpt']}", 20, 3,
        first(O11["name"], O11["sha256"], "Jo11b012_first", "o11_first_response.jsonl"), ["ready:J-b012"], "J-b012"),
    job("J-p8-b012", "first_response_p8o43_batch012", f"lora:P8_F_o43={P8CK.format(o='o43')}", 20, 3,
        first("P8_F_o43", P8["adapters"]["P8-F-o43"]["checkpoint-2005"]["adapter_sha256"], "Jp8b012_first", "p8_first_response.jsonl"), ["ready:J-b012"], "J-b012"),
    job("J-rdev2-base", "cells_rdev2_base_k4", "b17408", 25, 4, rdev2("base", "rdev2_base"), ["ready:J-rdev2"], "J-rdev2"),
    job("J-rdev2-o11", "cells_rdev2_o11_k4", f"lora:{O11['name']}={O11['ckpt']}", 20, 4, rdev2(O11["name"], "rdev2_o11"), ["ready:J-rdev2"], "J-rdev2"),
]
for o in SEEDS:
    jobs.append(job(f"J-rdev2-p8-{o}", f"cells_rdev2_P8F_{o}_k4", f"lora:P8_F_{o}={P8CK.format(o=o)}", 20, 4, rdev2(f"P8_F_{o}", f"rdev2_p8_{o}"),
                    ["ready:J-rdev2"], "J-rdev2"))
(HERE / "jobs_prep.json").write_text(json.dumps({"jobs": jobs}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
seeds = {"T-R": {"seed_base": 20261926, "rule": "seed_base + 1000 × 질문 순번 + 표본 번호, temperature 0.6"},
         "TEACH-R": {"seed_base": 20262026, "rule": "같음"},
         "J-b012 self": {"round_seed": 20261015, "rule": "collect6b 기본(J1): greedy 1 + 표본 8, 표본 seed = EV.call_seed(20261015, 문항 id, s)"},
         "J-b012 / J-o11-b012 / J-p8-b012 first": {"greedy": True},
         "J-rdev2 cells": {"seed_base": 20261100, "round_seeds": [20261101, 20261102, 20261103, 20261104]}}
(HERE / "seeds_prep.json").write_text(json.dumps(seeds, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print([(j["prio"], j["id"], j["server"][:24], j["deps"]) for j in jobs])
