# -*- coding: utf-8 -*-
"""pilot_006 승인 corpus(R0, ``pilot_006_prep/approved``) 읽기와 id 대응. 모델 호출 없음.

- corpus id: trunk ``t2pc:<sid>``, pg ``pg:<sid>``(pg batch006은 ``pg:pg-b006-NN``), aug300 ``aug300-NNN``, batch007 ``b007:b007-NN``, batch008 ``b008:b008-NN``, batch009 ``b009:b009-NN``.
- 표본 원문 id(수집 입력의 id): J1·J6 = ``aug300-NNN``, ``b007-NN``, ``pg-rr-<sid>``; 세션 2b 새 입력은 corpus id를 그대로 쓴다.
- gold: 승인 semantics를 ``render_full``로 바꾼 Full payload(``grounding_check``의 gold_grounding).
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PREP = HERE.parent
APPROVED = PREP / "approved"
#: 기본 판(세션 2c P1부터 v2: v1 + aug300 6 + batch009 51). RC1과 세션 2b 판정은 v1로 만들었다(각 출력에 manifest sha256 기록).
VERSION = "v2"
MANIFEST = {"v1": "manifest.json", "v2": "manifest_v2.json"}


def read_jsonl(p):
    return [json.loads(l) for l in Path(p).read_text(encoding="utf-8").splitlines() if l.strip()]


def load(include_holdout=False, version=None):
    rows = read_jsonl(APPROVED / f"approved_train_{version or VERSION}.jsonl")
    for r in rows:
        r["split"] = "train"
    if include_holdout:
        for r in read_jsonl(APPROVED / "approved_holdout_v1.jsonl"):
            r["split"] = "holdout"
            rows.append(r)
    return {r["id"]: r for r in rows}


def corpus_id(raw_id):
    if raw_id.startswith("pg-rr-"):
        sid = raw_id[len("pg-rr-"):]
        return f"pg:pg-{sid}" if sid.startswith("b006-") else f"pg:{sid}"
    if raw_id.startswith("b007-"):
        return f"b007:{raw_id}"
    if raw_id.startswith("b008-"):
        return f"b008:{raw_id}"
    if raw_id.startswith("b009-"):
        return f"b009:{raw_id}"
    return raw_id


def gold_payload(rec):
    from grounding.full_renderer import render_full
    return render_full(rec["semantics"])


def invalidated():
    """질문 문구가 바뀐 문항의 이전 문구 출력 trace id 집합(R0)."""
    d = json.loads((APPROVED / "invalidated_outputs.json").read_text(encoding="utf-8"))
    return set(d["questions"]), {t for per in d["outputs"].values() for ts in per.values() for t in ts}
