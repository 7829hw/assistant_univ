# -*- coding: utf-8 -*-
"""세션 3 실행 준비(결정 154·157): 학습 config 넷과 scheduler6e 작업 표를 RC 데이터에서 만든다. 모델 호출 없음. PLAN 고정 전에 커밋한다.

    hfvenv/bin/python sft_dpo_inventory/pilot_006/run3/make_jobs.py --rc RC3   # -> run3/configs/*.yaml, run3/jobs.json

- config: ``training/configs/qwen3_8b_t2pc_thinking_pilot005_v1_sft.yaml``(pilot_005 V1)에서 데이터(RC의 arm 디렉터리), ``grounding_target``, seed(43, 20261016),
  ``max_seq_length`` 12,288(결정 125), 출력 위치만 바꾼다. 2 epoch, save_steps 0.5(epoch 1·2 저장) 그대로. epoch 1 checkpoint = ``checkpoint-<N>``(N = 그 arm 레코드 수,
  batch 1·accum 1), epoch 2 = ``checkpoint-<2N>``.
- 작업(PLAN.md 3·5절): 학습 넷(F-s43, P-s43, F-s1016 먼저, P-s1016은 처음 비는 GPU), base 셋째 selection_v2 k=4(결정 134), epoch 1 셀(주 셋 151 = selection_v2 + holdout
  네 모델 k=4, valid98·aux k=4·업체 100 k=8은 s43 두 모델만), epoch 2 selection_v2 k=4(보고만, 네 모델), 지연 창(s43 F·P, 고정 30문항, 다른 GPU 비움, 결정 113·154).
"""
import argparse
import json
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BASE_CFG = ROOT / "training/configs/qwen3_8b_t2pc_thinking_pilot005_v1_sft.yaml"
OUT_ROOT = "/home/hwkim/sftdpo_work/pilot_006/train"
MODELS = [("F43", "full", 43), ("P43", "partial", 43), ("F1016", "full", 20261016), ("P1016", "partial", 20261016)]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--rc", required=True)
    a = p.parse_args()
    rc = f"sft_dpo_inventory/pilot_006/build/{a.rc}"
    (HERE / "configs").mkdir(exist_ok=True)
    jobs, ck = [], {}
    for name, arm, seed in MODELS:
        man = json.loads((ROOT / rc / arm / "manifest.json").read_text(encoding="utf-8"))["sft"]
        n = man["train_count"]
        cfg = yaml.safe_load(BASE_CFG.read_text(encoding="utf-8"))
        cfg["data"] = {"train": f"{rc}/{arm}/sft_train.jsonl", "valid": f"{rc}/{arm}/sft_valid.jsonl", "manifest": f"{rc}/{arm}/manifest.json",
                       "grounding_target": arm}
        out = f"{OUT_ROOT}/{name}"
        cfg["training"].update(output_dir=out, max_seq_length=12288, seed=seed)
        cfg["training"].pop("eval_steps", None)
        cfg["training"]["eval_strategy"] = "no"
        cfg.setdefault("profiling", {})["output"] = f"{out}_profile.json"
        path = HERE / f"configs/pilot006_{name}.yaml"
        path.write_text(f"# pilot_006 {name}(결정 154): pilot_005 V1 config에서 데이터({a.rc}/{arm}), grounding_target, seed {seed}, max_seq_length 12288, 출력 위치만 바꿈."
                        " 평가 셋이 없으므로 eval_strategy no.\n" + yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")
        ck[name] = {"e1": f"{out}/checkpoint-{n}", "e2": f"{out}/checkpoint-{2 * n}", "records": n, "arm": arm}
        jobs.append({"id": f"TR_{name}", "type": "train", "kind": f"train_{name}", "server": "train", "est": round(2 * n * (8.3 if arm == "partial" else 7.5) / 60),
                     "prio": {"F43": 1, "P43": 1, "F1016": 2, "P1016": 3}[name], "config": str(path.relative_to(ROOT)), "deps": []})
    jobs.append({"id": "BASE3", "type": "cell", "kind": "cell_base_selection_v2_k4_third", "server": "b17408", "est": 25, "prio": 4,
                 "label": "b5_sel_base_s3", "model": "base", "target": "full", "gold": "sel", "deps": []})
    for name, arm, seed in MODELS:
        c = ck[name]
        srv = f"lora:{name}={c['e1']}"
        dep = [f"file:{c['e1']}/adapter_model.safetensors|TR_{name}"]
        sets = [("sel", 4, 25), ("holdout", 4, 12)] + ([("valid98", 4, 25), ("aux", 4, 15), ("vendor100", 8, 50)] if seed == 43 else [])
        for gold, k, est in sets:
            jobs.append({"id": f"E1_{name}_{gold}", "type": "cell", "kind": f"cell_{name}_e1_{gold}_k{k}", "server": srv, "est": est, "prio": 5 if seed == 43 else 6,
                         "label": f"{name.lower()}_e1_{gold}", "model": name, "target": arm, "gold": gold, "k": k, "deps": dep})
        jobs.append({"id": f"E2_{name}_sel", "type": "cell", "kind": f"cell_{name}_e2_sel_k4", "server": f"lora:{name}e2={c['e2']}", "est": 25, "prio": 8,
                     "label": f"{name.lower()}_e2_sel", "model": f"{name}e2", "target": arm, "gold": "sel", "k": 4,
                     "deps": [f"file:{c['e2']}/adapter_model.safetensors|TR_{name}"]})
    others = [j["id"] for j in jobs]
    jobs.append({"id": "LAT", "type": "latency", "kind": "latency_base_F43_P43", "server": f"lora:F={ck['F43']['e1']} P={ck['P43']['e1']}", "est": 40, "prio": 9,
                 "f_model": "F", "p_model": "P", "label": "lat6", "deps": ["notrain", "done:" + ",".join(others)]})
    (HERE / "jobs.json").write_text(json.dumps({"rc": a.rc, "checkpoints": ck, "jobs": jobs}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(len(jobs), {k: v["records"] for k, v in ck.items()})


if __name__ == "__main__":
    main()
