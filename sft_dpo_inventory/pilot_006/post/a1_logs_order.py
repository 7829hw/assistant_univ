# -*- coding: utf-8 -*-
"""A1(학습 로그·데이터 순서): pilot_006 학습 넷의 loss 곡선과 epoch별 데이터 순서. 모델 호출 없음.

    hfvenv/bin/python a1_logs_order.py   # -> a1_logs_order.json

- 로그: ``pilot_006_prep/gpu/TR_<모델>.log``의 step별 ``loss``·``grad_norm``·``num_tokens``(누적 학습 token).
- 순서 재구성: accelerate ``SeedableRandomSampler``(data_seed 없음 → ``torch.random.initial_seed()`` = set_seed 값)는 epoch e에서
  ``torch.randperm(n, generator=Generator().manual_seed(seed + e))``. 검증: 재구성한 순서의 레코드 token 수(학습 렌더링 전체 길이, completion mask 전)를
  누적한 값이 로그의 ``num_tokens``와 같은지 본다.
- epoch 1 마지막 25% step에 몰린 레코드: 출처(teacher/8b), 출처 묶음(trunk·pg·aug300·batch007·008·009), 약점 부분집합(coverage_h4.subsets) 비율을 seed별로.
- epoch 2(s43 하락·s1016 상승)도 같은 틀(epoch 2 마지막 25%).
"""
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import torch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_006_prep/analysis"))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/thinking_prep_001"))
LOGS = ROOT / "sft_dpo_inventory/pilot_006_prep/gpu"
RC3 = ROOT / "sft_dpo_inventory/pilot_006/build/RC3"
MODELS = {"F43": ("full", 43), "P43": ("partial", 43), "F1016": ("full", 20261016), "P1016": ("partial", 20261016)}


def parse_log(path):
    steps = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        i = line.find("{'loss'")
        if i >= 0:
            d = eval(line[i:line.index("}", i) + 1], {"__builtins__": {}}, {"nan": float("nan"), "inf": float("inf")})  # noqa: S307 - trainer가 쓴 dict repr
            steps.append(d)
    return steps


def perm(n, seed, epoch):
    g = torch.Generator()
    g.manual_seed(seed + epoch)
    return torch.randperm(n, generator=g).tolist()


def main():
    import coverage_h4 as H4
    from grounding.canonical import semantics_from_full  # noqa: F401
    from training.trainer_common import load_config, load_records, render_records, tokenizer_for
    out = {"models": {}}
    corpus = {json.loads(l)["id"]: json.loads(l) for l in (ROOT / "sft_dpo_inventory/pilot_006_prep/approved/approved_train_v2.jsonl").read_text(encoding="utf-8").splitlines()}
    lens_cache = {}
    for name, (arm, seed) in MODELS.items():
        logs = parse_log(LOGS / f"TR_{name}.log")
        recs = [json.loads(l) for l in (RC3 / arm / "sft_train.jsonl").read_text(encoding="utf-8").splitlines()]
        n = len(recs)
        if arm not in lens_cache:
            cfg = load_config(str(ROOT / f"sft_dpo_inventory/pilot_006/run3/configs/pilot006_{name}.yaml"), "sft")
            tk = tokenizer_for(cfg)
            records, _ = load_records(cfg, "sft")
            rendered = render_records(tk, records["train"], cfg, "sft")
            lens_cache[arm] = [len(tk(r["prompt"] + r["completion"], add_special_tokens=False)["input_ids"]) for r in rendered]
        lens = lens_cache[arm]
        p0 = perm(n, seed, 0)
        nt = [s["num_tokens"] for s in logs]
        verify = None
        if lens and lens[0] is not None and len(nt) >= 50:
            cum = np.cumsum([lens[i] for i in p0 + perm(n, seed, 1)])
            verify = {"steps_compared": 50, "exact_match": int(sum(int(cum[i]) == int(nt[i]) for i in range(50))),
                      "first5_log": nt[:5], "first5_reconstructed": [int(x) for x in cum[:5]]}
        loss = [s["loss"] for s in logs]
        q = n // 4
        res = {"steps_logged": len(logs), "records": n, "seed": seed, "order_verify": verify,
               "loss": {"epoch1_mean": round(float(np.mean(loss[:n])), 4), "epoch1_last25_mean": round(float(np.mean(loss[n - q:n])), 4),
                        "epoch2_mean": round(float(np.mean(loss[n:])), 4) if len(loss) > n else None,
                        "final_100_mean": round(float(np.mean(loss[-100:])), 4)},
               "grad_norm": {"epoch1_mean": round(float(np.mean([s["grad_norm"] for s in logs[:n]])), 4),
                             "epoch1_last25_mean": round(float(np.mean([s["grad_norm"] for s in logs[n - q:n]])), 4)},
               "loss_by_quarter_e1": [round(float(np.mean(loss[i * q:(i + 1) * q])), 4) for i in range(4)]}
        for ep, pp in (("epoch1_last25", p0[n - q:]), ("epoch2_last25", perm(n, seed, 1)[n - q:])):
            sel = [recs[i] for i in pp]
            src = Counter(r["metadata"]["loss_scope"] for r in sel)
            grp = Counter(r["metadata"].get("corpus_group") for r in sel)
            subs = Counter()
            for r in sel:
                c = corpus.get(r["metadata"]["source_record_id"])
                if c:
                    subs.update(H4.subsets(c))
            allsrc = Counter(r["metadata"]["loss_scope"] for r in recs)
            res[ep] = {"teacher_share": round(src["full_response"] / len(sel), 3), "teacher_share_all": round(allsrc["full_response"] / n, 3),
                       "groups": dict(grp), "subsets_share": {k: round(v / len(sel), 3) for k, v in sorted(subs.items())}}
        out["models"][name] = res
    (HERE / "a1_logs_order.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for k, v in out["models"].items():
        print(k, v["order_verify"], v["loss"], v["loss_by_quarter_e1"], v["epoch1_last25"]["teacher_share"], v["epoch2_last25"]["teacher_share"])


if __name__ == "__main__":
    main()
