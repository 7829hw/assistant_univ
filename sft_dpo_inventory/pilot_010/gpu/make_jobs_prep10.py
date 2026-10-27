# -*- coding: utf-8 -*-
"""pilot_010 준비 GPU 작업 표(결정 242·243, 지시 2절). scheduler12(세 장, Ollama GPU = GPU 2 48f798cc)가 읽는다. 진단 작업은 판정에 쓰지 않는다.
``pilot_009/gpu/make_jobs_prep.py``·``make_jobs_prep2.py``와 같은 방식(그 파일들은 그대로).

    python3 make_jobs_prep10.py   # -> gpu/jobs_prep10.json, gpu/seeds_prep10.json

| 우선 | ID | 작업 | 조건 |
| 1 | T-C | 근접 대조 teacher 지시 확인(20 × 8, Ollama, ``teacher/run_c10.py --job T-C``, warm-up 1회) | P1 커밋(스케줄러 시작 커밋) |
| 2 | TEACH-C | 본 수집(batch011·012 r2 승인분 + batch013 초안 + 승인 corpus 요금 지표 답하는 문항 중 teacher 통과 trace 없는 것, × 8, Ollama) | T-C ok, ``ready/TEACH-C.json``(T-C 통과·batch013 겹침 검사 뒤 만듦) |
| 3 | J-b013 | batch013 초안 base 첫 응답(greedy, ``collect6b --mode first``)과 표본(greedy 1 + 8, ``--mode self``) | ``ready/J-b013.json``(P2 커밋 뒤) |
| 3 | J-p9-b013·J-b2f-b013 | batch013 초안 P9-o43(checkpoint-1993)·B2 F-o11(checkpoint-1811) 첫 응답(greedy, ``collect8 --mode first``) | 같음 |

- Ollama 작업(server "ollama")은 Ollama GPU에서만, 결정 55 guard(``run_c10``). scheduler12는 Ollama 작업이 남아 있으면 그 GPU에 45분 이하 작업만 주고,
  Ollama 작업 뒤 ``/api/ps``가 빌 때까지 다음 작업을 붙이지 않는다. 실행기도 끝난 뒤 ``/api/ps``가 빌 때까지 기다린다(모델을 내리지 않음).
- 입력 파일은 MAIN에서 읽고 sha256을 ``ready/<ID>.json``을 만들 때 적는다(명령 안에서 ``check_ready.sh``로 확인).
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = "/home/hwkim/sftdpo_work/hfvenv/bin/python"
VM = "/data/hwkim/sftdpo_work/pilot_006_prep/vllm"
SELF = "{MAIN}/training/generated/pilot_010/self"
B13 = "sft_dpo_inventory/batch013"
O11 = {"name": "B2_F_o11", "ckpt": "/home/hwkim/sftdpo_work/pilot_007/train_b2/B2-F-o11/checkpoint-1811",
       "sha256": "2d94933b5756c769c1b1068a6003540fd92d64ab7717b1fc4ea6793ef78574f2"}
P9 = json.loads((HERE.parents[1] / "pilot_009/adapters_P9.json").read_text(encoding="utf-8"))
P9O43 = {"name": "P9_F_o43", "ckpt": "/home/hwkim/sftdpo_work/pilot_009/train_p9/P9-F-o43/checkpoint-1993",
         "sha256": P9["adapters"]["P9-F-o43"]["checkpoint-1993"]["adapter_sha256"]}
CHK = "bash {MAIN}/sft_dpo_inventory/pilot_010/gpu/check_ready.sh {ID} && "


def first(model, sha, label, out):
    return (f"mkdir -p {SELF}/raw && {PY} {{WT}}/sft_dpo_inventory/pilot_008/gpu/collect8.py --port {{PORT}} --server-meta {VM} --mode first --model {model} "
            f"--adapter-sha256 {sha} --label {label} --inputs {{MAIN}}/{B13}/inputs_first_response.jsonl --raw-out {SELF}/raw/{label}_raw.jsonl --out {{MAIN}}/{B13}/{out}")


jb013 = (f"mkdir -p {SELF}/raw && {PY} {{WT}}/sft_dpo_inventory/pilot_006_prep/gpu/collect6b.py --port {{PORT}} --server-meta {VM} --mode first --label Jb013_first "
         f"--inputs {{MAIN}}/{B13}/inputs_first_response.jsonl --raw-out {SELF}/raw/Jb013_first_raw.jsonl --out {{MAIN}}/{B13}/base_first_response.jsonl && "
         f"{PY} {{WT}}/sft_dpo_inventory/pilot_006_prep/gpu/collect6b.py --port {{PORT}} --server-meta {VM} --mode self --grounding-target full --label Jb013_full "
         f"--inputs {{MAIN}}/{B13}/inputs_self.jsonl --raw-out {SELF}/raw/Jb013_full_raw.jsonl --out {SELF}/Jb013_full_manifest.json")


def job(id_, kind, server, est, prio, cmd, deps, ready_id=None):
    full = (CHK.replace("{ID}", ready_id) + cmd) if ready_id else cmd
    return {"id": id_, "type": "raw", "kind": kind, "server": server, "est": est, "prio": prio, "deps": deps, "cmd": ["bash", "-c", full], "outputs": []}


jobs = [
    job("T-C", "teacher_contrast_check_TC", "ollama", 20, 1, f"{PY} {{WT}}/sft_dpo_inventory/pilot_010/teacher/run_c10.py --main {{MAIN}} --job T-C", []),
    job("TEACH-C", "teacher_contrast_collect", "ollama", 150, 2, f"{PY} {{WT}}/sft_dpo_inventory/pilot_010/teacher/run_c10.py --main {{MAIN}} --job TEACH-C",
        ["T-C", "ready:TEACH-C"], "TEACH-C"),
    job("J-b013", "first_response_and_self_base_batch013", "b17408", 60, 3, jb013, ["ready:J-b013"], "J-b013"),
    job("J-p9-b013", "first_response_p9o43_batch013", f"lora:{P9O43['name']}={P9O43['ckpt']}", 10, 3,
        first(P9O43["name"], P9O43["sha256"], "Jp9b013_first", "p9_first_response.jsonl"), ["ready:J-b013"], "J-b013"),
    job("J-b2f-b013", "first_response_b2fo11_batch013", f"lora:{O11['name']}={O11['ckpt']}", 10, 3,
        first(O11["name"], O11["sha256"], "Jb2fb013_first", "b2f_first_response.jsonl"), ["ready:J-b013"], "J-b013"),
]
(HERE / "jobs_prep10.json").write_text(json.dumps({"jobs": jobs}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
seeds = {"T-C": {"seed_base": 20271027, "rule": "seed_base + 1000 × 질문 순번 + 표본 번호, temperature 0.6", "warmup_seed": 20271026},
         "TEACH-C": {"seed_base": 20272027, "rule": "같음", "warmup_seed": 20272026},
         "J-b013 self": {"round_seed": 20261015, "rule": "collect6b 기본(J1): greedy 1 + 표본 8, 표본 seed = EV.call_seed(20261015, 문항 id, s)"},
         "J-b013 / J-p9-b013 / J-b2f-b013 first": {"greedy": True}}
(HERE / "seeds_prep10.json").write_text(json.dumps(seeds, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print([(j["prio"], j["id"], j["server"][:24], j["deps"]) for j in jobs])
