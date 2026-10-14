# -*- coding: utf-8 -*-
"""결정 88(AC) 유형별 상한 도구. 데이터의 유형 칸(``type_target.profile``의 cell: 집계·dimension·dimension_target 유무) 분포를
개발 셋 분포에 맞춰, 개발 셋 대비 TV가 목표(기본 0.09) 이하가 되는 칸별 상한을 정한다. 최종 데이터는 만들지 않는다(수치만).

    python sft_dpo_inventory/pilot_004_prep/type_caps.py [--tau 0.09]

- 상한 계산(``caps_for``): 칸별 가용 수 a_c, 개발 분포 d_c, 목표 τ. 총수 M에서 TV의 최솟값은 Σ_c max(0, d_c − a_c/M)이다
  (모자란 칸의 부족분만큼 다른 칸이 넘쳐야 하므로). 이 값이 τ 이하이고 Σ a_c ≥ M인 가장 큰 M을 찾고,
  칸별 상한 = min(a_c, floor(d_c·M)) + 남는 몫(부족분 합까지)을 여유 있는 칸에 개발 분포 비율로 나눈다.
- 고르기(``apply_caps``): 칸 안에서 질문을 돌아가며(round-robin) 한 레코드씩 고른다. 질문 순서는 seed로 섞는다(기본 20261014).
  질문 수를 되도록 지키고, 한 질문의 레코드가 몰려 남지 않게 한다.
- 시나리오(pilot_003 데이터 ``thinking_pilot003_t2pc``에 적용):
  - A. 레코드 상한만: SFT 레코드와 DPO 쌍에 각각 상한. 질문 TV는 남은 질문으로 다시 잰다.
  - B. 질문 상한 → 레코드 상한: 먼저 SFT 질문 분포에 상한을 둬 질문을 고르고(칸 안에서 seed 순서), 남은 질문의 레코드에 다시 상한.
    DPO는 남은 SFT 질문에 속한 쌍만 두고 상한.
- 결과: ``type_caps.json``(칸별 수, 상한, 남는 레코드·질문 수, TV, 실차 대조 변형별 남는 수).
"""
import argparse
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_prep_004/type_target"))
from type_target import profile, tv  # noqa: E402

DATA = ROOT / "training/generated/thinking_pilot003_t2pc"
GOLD = ROOT / "training/generated/reviewed_gold_v006_t2pc/sft_train.jsonl"
DEV = ROOT / "sft_dpo_inventory/pilot_prep_004/type_target/type_target.json"
B6_CHECKED = ROOT / "sft_dpo_inventory/batch006/candidates_checked.json"
SEED = 20261014


def read(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def min_tv(available, dev, m):
    return sum(max(0.0, dev.get(c, 0) - available.get(c, 0) / m) for c in set(dev) | set(available))


def caps_for(available, dev, tau):
    """칸별 가용 수 → (총수 M, 칸별 상한). 개발 분포에 없는 칸은 TV에 그대로 더해지므로 상한 0에서 시작해 여유로만 채운다."""
    total = sum(available.values())
    best = 0
    for m in range(total, 0, -1):
        if min_tv(available, dev, m) <= tau + 1e-12:
            best = m
            break
    if best == 0:
        return 0, {c: 0 for c in available}
    base = {c: min(available.get(c, 0), int(dev.get(c, 0) * best)) for c in available}
    rest = best - sum(base.values())
    room = {c: available[c] - base[c] for c in available if available[c] > base[c]}
    while rest > 0 and room:
        # 개발 분포 대비 가장 덜 찬 칸부터 하나씩(동률은 칸 이름 순)
        c = min(room, key=lambda k: ((base[k] + 1) / best - dev.get(k, 0), k))
        base[c] += 1
        rest -= 1
        room[c] -= 1
        if room[c] == 0:
            del room[c]
    return best, base


def apply_caps(items, cell_of, group_of, caps, seed=SEED):
    """items: 순서 있는 목록. 칸마다 질문을 섞은 순서로 돌아가며 하나씩 골라 상한까지 둔다."""
    by_cell = defaultdict(lambda: defaultdict(list))
    for it in items:
        by_cell[cell_of(it)][group_of(it)].append(it)
    kept = []
    for cell, groups in sorted(by_cell.items()):
        order = sorted(groups)
        random.Random(f"{seed}:{cell}").shuffle(order)
        queues = [list(groups[g]) for g in order]
        cap, taken = caps.get(cell, 0), 0
        while taken < cap and any(queues):
            for q in queues:
                if q and taken < cap:
                    kept.append(q.pop(0))
                    taken += 1
    keep_ids = {id(x) for x in kept}
    return [it for it in items if id(it) in keep_ids]


def share(counter):
    n = sum(counter.values())
    return {k: round(v / n, 4) for k, v in sorted(counter.items())} if n else {}


def describe(sft, dpo, cell, variant):
    q = Counter(cell[s] for s in {r["sid"] for r in sft})
    rc = Counter(cell[r["sid"]] for r in sft)
    dc = Counter(cell[r["sid"]] for r in dpo)
    return {"sft_records": len(sft), "sft_questions": len({r["sid"] for r in sft}),
            "dpo_pairs": len(dpo), "dpo_questions": len({r["sid"] for r in dpo}),
            "sft_record_by_source": dict(Counter(r["source"] for r in sft)),
            "cells": {"sft_question": dict(sorted(q.items())), "sft_record": dict(sorted(rc.items())), "dpo_pair": dict(sorted(dc.items()))},
            "tv_vs_dev": {"sft_question": tv(share(q), DEVD), "sft_record": tv(share(rc), DEVD), "dpo_pair": tv(share(dc), DEVD)},
            "passage_status_contrast": {"sft_records": dict(sorted(Counter(variant[r["sid"]] for r in sft if r["sid"] in variant).items())),
                                        "dpo_pairs": dict(sorted(Counter(variant[r["sid"]] for r in dpo if r["sid"] in variant).items()))}}


DEVD = json.loads(DEV.read_text(encoding="utf-8"))["dev_distribution"]["share"]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--tau", type=float, default=0.09)
    args = p.parse_args()
    gold = {r["metadata"]["source_record_id"]: r for r in read(GOLD)}
    stop = {s for s, r in gold.items() if r["metadata"].get("target_kind") == "t2pc_stop_grounding"}
    cell = {s: profile(json.loads(r["messages"][-1]["content"]), s not in stop)["cell"] for s, r in gold.items()}
    sft = [{"sid": r["metadata"]["source_record_id"], "trace": r["metadata"]["trace_id"],
            "source": "teacher" if r["metadata"].get("source") == "teacher" else "hf"} for r in read(DATA / "sft_train.jsonl")]
    dpo = [{"sid": r["metadata"]["source_record_id"], "pair": i} for i, r in enumerate(read(DATA / "dpo_train.jsonl"))]
    # 실차 대조 변형(결정 66): pilot_003 builder와 같은 batch006 후보 기록
    variant = {c["id"]: c["variant"] for c in json.loads(B6_CHECKED.read_text(encoding="utf-8"))["candidates"] if c.get("variant")}
    out = {"tau": args.tau, "seed": SEED, "dev_share": DEVD, "data": str(DATA.relative_to(ROOT)),
           "before": describe(sft, dpo, cell, variant), "scenarios": {}}

    # A. 레코드 상한만
    m_s, caps_s = caps_for(Counter(cell[r["sid"]] for r in sft), DEVD, args.tau)
    m_d, caps_d = caps_for(Counter(cell[r["sid"]] for r in dpo), DEVD, args.tau)
    sft_a = apply_caps(sft, lambda r: cell[r["sid"]], lambda r: r["sid"], caps_s)
    dpo_a = apply_caps(dpo, lambda r: cell[r["sid"]], lambda r: r["sid"], caps_d)
    out["scenarios"]["A_record_caps"] = {"caps": {"sft_record": caps_s, "dpo_pair": caps_d}, "max_total": {"sft": m_s, "dpo": m_d},
                                         **describe(sft_a, dpo_a, cell, variant)}

    # B. 질문 상한 → 레코드 상한
    questions = sorted({r["sid"] for r in sft})
    m_q, caps_q = caps_for(Counter(cell[s] for s in questions), DEVD, args.tau)
    keep_q = {r["sid"] for r in apply_caps([{"sid": q} for q in questions], lambda r: cell[r["sid"]], lambda r: r["sid"], caps_q)}
    sft_q = [r for r in sft if r["sid"] in keep_q]
    dpo_q = [r for r in dpo if r["sid"] in keep_q]
    m_s2, caps_s2 = caps_for(Counter(cell[r["sid"]] for r in sft_q), DEVD, args.tau)
    m_d2, caps_d2 = caps_for(Counter(cell[r["sid"]] for r in dpo_q), DEVD, args.tau)
    sft_b = apply_caps(sft_q, lambda r: cell[r["sid"]], lambda r: r["sid"], caps_s2)
    dpo_b = apply_caps(dpo_q, lambda r: cell[r["sid"]], lambda r: r["sid"], caps_d2)
    out["scenarios"]["B_question_then_record_caps"] = {
        "caps": {"sft_question": caps_q, "sft_record": caps_s2, "dpo_pair": caps_d2},
        "max_total": {"sft_question": m_q, "sft": m_s2, "dpo": m_d2},
        "dropped_questions": sorted(set(questions) - keep_q), **describe(sft_b, dpo_b, cell, variant)}
    (HERE / "type_caps.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for name, s in [("before", out["before"])] + list(out["scenarios"].items()):
        print(name, {k: s[k] for k in ("sft_records", "sft_questions", "dpo_pairs", "dpo_questions", "tv_vs_dev", "sft_record_by_source")},
              s["passage_status_contrast"])


if __name__ == "__main__":
    main()
