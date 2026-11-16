"""X4 학습 설정 18개(PREREGISTRATION 6.2). CPU 전용.

기존 A0 설정(ablation_011 A0-o1102·o211102, ablation_013 A0-o2026131)을 읽어 바꾸는 것: data(대조 V4 / 처치 V4S), training.seed·data_seed(학습 seed),
output_dir, profiling.output. 순서 seed·O4' 순서 파일·레코드 순서 파일·나머지 설정은 그 A0 설정 그대로.
쌍 번호 = (순서 seed, 학습 seed) 행 우선 1–9. 홀수 쌍은 대조 먼저, 짝수 쌍은 처치 먼저. 쌍 k는 GPU 레인 (k−1) % 3.
    python make_x4_configs.py MAIN_REPO
"""
import copy
import json
import sys
from pathlib import Path

import yaml

main = Path(sys.argv[1]).resolve()
X4 = main / "topic2_semantic_order/dissociation/x4"
OUT = "/data/hwkim/sftdpo_work/topic2_dissociation/train"
A0 = {"1102": "sft_dpo_inventory/ablation_011/train/configs/A0-o1102.yaml",
      "211102": "sft_dpo_inventory/ablation_011/train/configs/A0-o211102.yaml",
      "2026131": "sft_dpo_inventory/ablation_013/train/configs/A0-o2026131.yaml"}
DATA = {"C": "sft_dpo_inventory/pilot_010/build/V4/full", "T": "topic2_semantic_order/dissociation/x4/V4S/full"}
SEEDS = [43, 2026116, 2026119]
(X4 / "train/configs").mkdir(parents=True, exist_ok=True)
pairs = []
k = 0
for o in ("1102", "211102", "2026131"):
    base = yaml.safe_load((main / A0[o]).read_text(encoding="utf-8"))
    for s in SEEDS:
        k += 1
        ids = []
        for arm in ("C", "T"):
            cid = f"X4{arm}-o{o}-s{s}"
            c = copy.deepcopy(base)
            c["data"].update(train=f"{DATA[arm]}/sft_train.jsonl", valid=f"{DATA[arm]}/sft_valid.jsonl", manifest=f"{DATA[arm]}/manifest.json")
            c["training"].update(seed=s, data_seed=s, output_dir=f"{OUT}/{cid}")
            c["profiling"]["output"] = f"{OUT}/{cid}_profile.json"
            head = (f"# X4 {'대조(V4 원본)' if arm == 'C' else '처치(V4S 범위 칸)'} 순서 seed {o}, 학습 seed {s}, 쌍 {k}. "
                    f"{A0[o]}에서 data·seed·data_seed·출력만 바꿈. wrapper ablation_011/train/train_a11.py.\n")
            (X4 / f"train/configs/{cid}.yaml").write_text(head + yaml.safe_dump(c, allow_unicode=True, sort_keys=False), encoding="utf-8")
            ids.append(cid)
        order = ids if k % 2 == 1 else ids[::-1]
        pairs.append({"pair": k, "order_seed": int(o), "train_seed": s, "lane": f"g{(k - 1) % 3}", "run_order": order})
(X4 / "train/pairs.json").write_text(json.dumps(pairs, indent=1) + "\n", encoding="utf-8")
print(json.dumps(pairs))
