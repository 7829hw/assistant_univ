# -*- coding: utf-8 -*-
"""두 arm 데이터 순서 공유(결정 168 O4). 질문 단위 순열을 seed로 정하고 각 arm 레코드를 그 순서로 놓는다. 공용 학습 코드는 고치지 않는다.

- ``question_order(qids, seed)``: 질문 id를 정렬한 뒤 ``numpy.random.default_rng(seed).permutation``으로 섞은 순서. 두 arm이 같은 질문 목록이면 같은 순서.
- ``within_key(record)``: 한 질문 안 레코드 순서 규칙(두 arm 같은 규칙): teacher(``full_response``) 먼저 ``trace_id`` 순(teacher trace는 두 arm이 같은 id),
  그다음 8b(``json_only``) ``trace_sha256`` 순.
- ``order_records(records, seed)``: 위 두 규칙으로 레코드 목록을 다시 놓는다. 질문 목록 밖 레코드는 없어야 한다.
- ``question_sequence(records)``: 레코드 순서에서 질문이 처음 나오는 순서(검사용).
- ``install_sequential_sampler()``: ``transformers.Trainer._get_train_sampler``를 ``SequentialSampler``로 바꾼다(accelerate는 SequentialSampler를
  그대로 둠 → ``data_seed``와 무관하게 놓인 순서대로 학습). 학습 wrapper(``train_b7.py``)에서 shared_order를 쓸 때만 부른다.
"""
import hashlib
import json

import numpy as np


def question_order(qids, seed):
    q = sorted(set(qids))
    perm = np.random.default_rng(int(seed)).permutation(len(q))
    return [q[i] for i in perm]


def within_key(record):
    m = record["metadata"]
    return (0, m["trace_id"]) if m["loss_scope"] == "full_response" else (1, m.get("trace_sha256") or m["trace_id"])


def order_records(records, seed):
    by_q = {}
    for r in records:
        by_q.setdefault(r["metadata"]["source_record_id"], []).append(r)
    out = []
    for q in question_order(by_q, seed):
        out += sorted(by_q[q], key=within_key)
    assert len(out) == len(records)
    return out


def question_sequence(records):
    seen, seq = set(), []
    for r in records:
        q = r["metadata"]["source_record_id"]
        if q not in seen:
            seen.add(q)
            seq.append(q)
    return seq


def order_file(qids_by_arm, seed):
    """빌드 옵션: 두 arm 질문 목록이 같은지 확인하고 순서 파일 내용을 만든다."""
    lists = {arm: sorted(set(q)) for arm, q in qids_by_arm.items()}
    first = next(iter(lists.values()))
    if any(v != first for v in lists.values()):
        raise ValueError("arms have different question lists")
    order = question_order(first, seed)
    return {"seed": int(seed), "questions": len(order), "question_list_sha256": hashlib.sha256("\n".join(first).encode()).hexdigest(),
            "order_sha256": hashlib.sha256("\n".join(order).encode()).hexdigest(), "order": order,
            "within_question_rule": "teacher(full_response) trace_id 순 → 8b(json_only) trace_sha256 순"}


def install_sequential_sampler():
    import torch
    from transformers import Trainer

    def _seq(self, train_dataset=None):
        ds = train_dataset if train_dataset is not None else self.train_dataset
        return torch.utils.data.SequentialSampler(ds)
    Trainer._get_train_sampler = _seq
    return _seq


def load_jsonl(path):
    return [json.loads(l) for l in open(path, encoding="utf-8").read().splitlines() if l.strip()]
