# -*- coding: utf-8 -*-
"""B2단계 순서 파일(결정 206 O4')과 연속 길이 표. 모델 호출 없음.

    hfvenv/bin/python sft_dpo_inventory/pilot_007/train_data/make_order7b.py --rc sft_dpo_inventory/pilot_007/build/RC5 --seeds 43 20261016 7 11 2027
    # -> <rc>/order_b2_o<seed>.json, <rc>/run_length_B2.json

연속 길이 표(같은 질문이 연달아 나오는 run):
- A3(무작위 순서, Full만): accelerate ``SeedableRandomSampler`` 규칙 재현 = 파일 순서 레코드에 ``torch.randperm(n, generator=torch.Generator().manual_seed(data_seed + epoch 0))``
  (A3 config data_seed 43·20261016·7). 로그와 대조하지 않은 재현이다.
- B(O4, ``order7.order_records``): arm·seed마다.
- B2(O4', ``order7b``): arm·seed마다. 최대 run > 4면 그 seed는 학습하지 않는다(``max_run_ok``).
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import order7  # noqa: E402
import order7b  # noqa: E402


def a3_random(records, data_seed):
    import torch
    g = torch.Generator()
    g.manual_seed(int(data_seed))
    return [records[i] for i in torch.randperm(len(records), generator=g).tolist()]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--rc", required=True)
    p.add_argument("--seeds", type=int, nargs="+", required=True)
    a = p.parse_args()
    rc = Path(a.rc)
    recs = {arm: order7.load_jsonl(rc / arm / "sft_train.jsonl") for arm in ("full", "partial")}
    table = {"A3_random(full)": {}, "B_O4": {}, "B2_O4prime": {}}
    for s in a.seeds:
        d = order7b.order_file(recs, s)
        for arm in ("full", "partial"):
            seq = [order7b.qid(r) for r in order7b.order_records(recs[arm], d["order"])]
            assert order7b.run_stats(seq) == d["arms"][arm]["run_stats"]
        (rc / f"order_b2_o{s}.json").write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        table["B2_O4prime"][f"o{s}"] = {arm: d["arms"][arm]["run_stats"] for arm in ("full", "partial")}
        table["B2_O4prime"][f"o{s}"].update(order_sha256=d["order_sha256"], question_list_sha256=d["question_list_sha256"],
                                           common_relative_order_equal=d["common_relative_order_equal"], max_run_ok=d["max_run_ok"])
        table["B_O4"][f"o{s}"] = {arm: order7b.run_stats([order7b.qid(r) for r in order7.order_records(recs[arm], s)]) for arm in ("full", "partial")}
        print(s, d["order_sha256"][:12], d["common_relative_order_equal"], d["max_run_ok"], {k: v["run_stats"]["max_run"] for k, v in d["arms"].items()})
    for s in (43, 20261016, 7):
        table["A3_random(full)"][f"data_seed {s}"] = order7b.run_stats([order7b.qid(r) for r in a3_random(recs["full"], s)])
    (rc / "run_length_B2.json").write_text(json.dumps(table, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(table, ensure_ascii=False)[:3000])


if __name__ == "__main__":
    main()
