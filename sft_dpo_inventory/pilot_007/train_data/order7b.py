# -*- coding: utf-8 -*-
"""두 arm 데이터 순서 공유 — 질문을 섞은 판(결정 206 O4'). ``order7.py``(B단계, 결정 168 O4)는 고치지 않고 질문 안 규칙(``order7.within_key``)만 가져다 쓴다.

- slot: arm마다 한 질문 안 레코드를 ``order7.within_key`` 순으로 놓고 k = 0, 1, 2, …를 붙인다. slot 키 = ``"<질문 id>#<k>"``.
- ``slot_order(slot_keys_by_arm, seed)``: 두 arm slot 키 합집합을 정렬한 뒤 ``numpy.random.default_rng(seed).permutation``으로 한 번 섞은 순서.
- ``order_records(records, slot_order)``: 그 순열에서 그 arm에 있는 slot만 차례로 쓴 레코드 순서(공통 slot은 두 arm에서 같은 상대 순서).
- ``order_file(records_by_arm, seed)``: 두 arm 질문 목록이 같은지 확인하고 순서 파일 내용(slot 순열, arm별 slot 수·순서 sha256, 연속 길이 통계)을 만든다.
- ``run_stats(qids)``: 같은 질문이 연달아 나오는 길이(run) — 최대, 평균, 길이 2 이상인 run의 비율, 길이 2 이상 run에 든 레코드 비율.
- ``common_relative_order_equal(a, b)``: 두 slot 순서를 공통 slot으로 좁혔을 때 같은지.
- 학습에서는 ``order7.install_sequential_sampler()``로 trainer 쪽 섞기를 끈다(``train_b7b.py``).
"""
import hashlib
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import order7  # noqa: E402

MAX_RUN = 4  # 결정 206: 같은 질문 연속 최대 길이가 이보다 크면 그 seed 학습 안 함


def qid(r):
    return r["metadata"]["source_record_id"]


def slots(records):
    """레코드 → [(slot 키, 레코드)] (질문 안 순서 = order7.within_key)."""
    by_q = {}
    for r in records:
        by_q.setdefault(qid(r), []).append(r)
    out = []
    for q in sorted(by_q):
        for k, r in enumerate(sorted(by_q[q], key=order7.within_key)):
            out.append((f"{q}#{k}", r))
    return out


def slot_order(slot_keys_by_arm, seed):
    keys = sorted(set().union(*[set(v) for v in slot_keys_by_arm.values()]))
    perm = np.random.default_rng(int(seed)).permutation(len(keys))
    return [keys[i] for i in perm]


def order_records(records, order):
    s = dict(slots(records))
    out = [s[k] for k in order if k in s]
    assert len(out) == len(records)
    return out


def arm_slot_sequence(records, order):
    s = {k for k, _ in slots(records)}
    return [k for k in order if k in s]


def run_stats(qids):
    runs, cur = [], 1
    for i in range(1, len(qids)):
        if qids[i] == qids[i - 1]:
            cur += 1
        else:
            runs.append(cur)
            cur = 1
    if qids:
        runs.append(cur)
    multi = [r for r in runs if r >= 2]
    return {"records": len(qids), "runs": len(runs), "max_run": max(runs) if runs else 0, "mean_run": round(float(np.mean(runs)), 4) if runs else 0.0,
            "share_runs_ge2": round(len(multi) / len(runs), 4) if runs else 0.0, "share_records_in_runs_ge2": round(sum(multi) / len(qids), 4) if qids else 0.0}


def common_relative_order_equal(a, b):
    common = set(a) & set(b)
    return [k for k in a if k in common] == [k for k in b if k in common]


def sha(lines):
    return hashlib.sha256("\n".join(lines).encode()).hexdigest()


def order_file(records_by_arm, seed):
    qlists = {arm: sorted({qid(r) for r in recs}) for arm, recs in records_by_arm.items()}
    first = next(iter(qlists.values()))
    if any(v != first for v in qlists.values()):
        raise ValueError("arms have different question lists")
    keys = {arm: [k for k, _ in slots(recs)] for arm, recs in records_by_arm.items()}
    order = slot_order(keys, seed)
    arms = {}
    for arm, recs in records_by_arm.items():
        seq = arm_slot_sequence(recs, order)
        arms[arm] = {"slots": len(seq), "slot_sequence_sha256": sha(seq), "run_stats": run_stats([k.rsplit("#", 1)[0] for k in seq])}
    names = list(records_by_arm)
    common_ok = all(common_relative_order_equal(arm_slot_sequence(records_by_arm[a], order), arm_slot_sequence(records_by_arm[b], order))
                    for i, a in enumerate(names) for b in names[i + 1:])
    return {"seed": int(seed), "rule": "O4' (결정 206): slot 키 (질문 id, k) 합집합을 default_rng(seed).permutation으로 한 번 섞음; 질문 안 k 순서 = order7.within_key",
            "questions": len(first), "question_list_sha256": sha(first), "slots_union": len(order), "order_sha256": sha(order),
            "common_slots": len(set.intersection(*[set(v) for v in keys.values()])), "common_relative_order_equal": common_ok,
            "max_run_limit": MAX_RUN, "max_run_ok": all(v["run_stats"]["max_run"] <= MAX_RUN for v in arms.values()), "arms": arms, "order": order}
