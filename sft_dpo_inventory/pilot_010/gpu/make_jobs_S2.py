# -*- coding: utf-8 -*-
"""pilot_010 선택 단계 GPU 작업 표 2부·sampling seed·선택 spec(결정 251·252, 지시 2.2 우선 3·4). 변형 빌드 뒤, PLAN_S 고정 전에 커밋한다.
scheduler12(세 장, Ollama GPU = GPU 2; TEACH-C가 끝나고 ``/api/ps``가 빈 뒤에만 이 표로 새로 시작)가 읽는다. ``pilot_009/gpu/make_jobs_main.py``와 같은 방식(그 파일은 그대로).

    python3 make_jobs_S2.py   # -> gpu/jobs_S2.json, gpu/cell_seeds_S.json, gates/spec_s10.json

| 우선 | 작업 |
| 1–6 | S-V4-o43, S-V8-o43, S-V4-o1016(첫 바퀴) → S-V8-o1016, S-V4-o7, S-V8-o7(둘째 바퀴) 학습(``pilot_007/train/train_b7b.py``, configs_s10). 우선 숫자 = 바퀴 차례 |
| 7 | ES-<V>-<o>: 모델(epoch 끝 checkpoint)마다 refusal_dev v2 k=4 + valid98 k=4 + aux k=4(한 서버에서 차례로), 해당 학습 끝(``file:`` 의존) |

- 셀: ``pilot_006_prep/gpu/run_cell6x.py``(vLLM 0.30.0 BF16, 17,408, 동시 8, PROTOCOL_v4 3절 sampling, 회차 seed S_k = 20261100 + k — base·B2 F·P9 셀과 같음), 출력 ``pilot_010/cells``,
  원문 ``training/generated/pilot_010/cells_raw``(ignore). 주 셋(selection_v2·holdout)은 재지 않는다(결정 252).
- 비교 기준 셀은 이미 있는 것(재측정 없음): base refusal_dev v2 k=12·valid98·aux(``pilot_009/gates/spec_p9.json``의 base), B2 F 다섯 seed valid98·aux(pilot_007 B2)·refusal_dev v2(pilot_009),
  P9 다섯 seed(보조, pilot_009).
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
P10 = HERE.parent
ROOT = P10.parents[1]
PY = "/home/hwkim/sftdpo_work/hfvenv/bin/python"
MAIN = "/home/hwkim/assistant_univ"
SEEDS = {"o43": 43, "o1016": 20261016, "o7": 7}
ROUNDS = ["S-V4-o43", "S-V8-o43", "S-V4-o1016", "S-V8-o1016", "S-V4-o7", "S-V8-o7"]
OUT = "/home/hwkim/sftdpo_work/pilot_010/train_s10"
RDEV = "sft_dpo_inventory/pilot_009/refusal_dev2/approved/rdev_v2_gold.yaml"
GOLD = {"valid98": "sft_dpo_inventory/pilot_004/valid98/valid98_gold.yaml", "aux": "sft_dpo_inventory/pilot_002/aux_test/aux_test_gold.yaml", "rdevv2": RDEV}
SEED_BASE = 20261100
P9SPEC = json.loads((ROOT / "sft_dpo_inventory/pilot_009/gates/spec_p9.json").read_text(encoding="utf-8"))
P9_TRAIN_MIN, P9_RECORDS = 195, 1993


def run(model, label, gold_key, k):
    return (f"{PY} {{WT}}/sft_dpo_inventory/pilot_006_prep/gpu/run_cell6x.py --port {{PORT}} --model {model} --label {label} --k {k} --concurrency 8 "
            f"--grounding-target full --out-dir {MAIN}/sft_dpo_inventory/pilot_010/cells --raw-dir {MAIN}/training/generated/pilot_010/cells_raw --seed-base {SEED_BASE}"
            f" --gold {GOLD[gold_key]} --all-items")


def rounds(k):
    return {"seed_base": SEED_BASE, "round_seeds": [SEED_BASE + i for i in range(1, k + 1)]}


records = {v: json.loads((P10 / f"build/{v}/build_summary.json").read_text(encoding="utf-8"))["records"] for v in ("V4", "V8")}
jobs, seeds, ckpts = [], {}, {}
for prio, jid in enumerate(ROUNDS, start=1):
    v, o = jid.split("-")[1], jid.split("-")[2]
    est = round(P9_TRAIN_MIN * records[v] / P9_RECORDS)
    jobs.append({"id": jid, "type": "raw", "kind": f"train_b7b_{jid}", "server": "train", "est": est, "prio": prio,
                 "cmd": [PY, "{WT}/sft_dpo_inventory/pilot_007/train/train_b7b.py", "--config", f"{{WT}}/sft_dpo_inventory/pilot_010/train/configs_s10/{jid}.yaml"],
                 "outputs": []})
    ckpts[jid] = f"{OUT}/{jid}/checkpoint-{records[v]}"
for jid in ROUNDS:
    v, o = jid.split("-")[1], jid.split("-")[2]
    name, ck = f"S_{v}_{o}", ckpts[jid]
    cmds = [run(name, f"s10_{v.lower()}_{o}_{g}", g, k) for g in ("rdevv2", "valid98", "aux") for k in range(1, 5)]
    jobs.append({"id": f"ES-{v}-{o}", "type": "raw", "kind": f"cells_S_{v}_{o}_rdevv2_valid98_aux_k4", "server": f"lora:{name}={ck}", "est": 45, "prio": 7,
                 "deps": [f"file:{ck}/adapter_model.safetensors|{jid}"], "cmd": ["bash", "-c", " && ".join(cmds)], "outputs": []})
    for g in ("rdevv2", "valid98", "aux"):
        seeds[f"s10_{v.lower()}_{o}_{g}"] = rounds(4)
(HERE / "jobs_S2.json").write_text(json.dumps({"jobs": jobs}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
(HERE / "cell_seeds_S.json").write_text(json.dumps({"decision": "252 (AB6): 실행 전 커밋, PROTOCOL_v4 3절 회차 seed(base·B2 F·P9 셀과 같음)", "cells": seeds,
                                                    "checkpoints": ckpts}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
ks = lambda p, k=4: [f"{p}_s{i}.json" for i in range(1, k + 1)]  # noqa: E731
C10 = "sft_dpo_inventory/pilot_010/cells/"
sel = lambda d: {k: d[k] for k in ("valid98", "aux", "rdev")}  # noqa: E731
spec = {"label": "pilot_010 선택 단계(결정 252)", "sets": {"valid98": GOLD["valid98"], "aux": GOLD["aux"]}, "rdev_gold": RDEV, "rdev_meta": P9SPEC["rdev_meta"],
        "variants": ["V4", "V8"], "seeds": list(SEEDS), "seed_numbers": SEEDS, "excluded_seeds": {},
        "cells": {**{v: {o: {"valid98": ks(f"{C10}s10_{v.lower()}_{o}_valid98"), "aux": ks(f"{C10}s10_{v.lower()}_{o}_aux"), "rdev": ks(f"{C10}s10_{v.lower()}_{o}_rdevv2")}
                         for o in SEEDS} for v in ("V4", "V8")},
                  "B2F": {o: sel(P9SPEC["cells"]["B2F"][o]) for o in P9SPEC["seeds"]}, "P9": {o: sel(P9SPEC["cells"]["P9"][o]) for o in P9SPEC["seeds"]},
                  "base": sel(P9SPEC["cells"]["base"])}}
(P10 / "gates/spec_s10.json").write_text(json.dumps(spec, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print([(j["prio"], j["id"], j["est"]) for j in jobs], records)
