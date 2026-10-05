"""Group connected intent/template/contrast families before deterministic splitting."""
import hashlib
import json
import random
import unicodedata

from training.data.canonicalize import canonical_json


def question_key(question):
    return "".join(ch for ch in unicodedata.normalize("NFKC", question)
                   if not ch.isspace() and not unicodedata.category(ch).startswith("P")).casefold()


def template_key(record):
    payload = json.loads(record["messages"][-1]["content"])
    if payload.get("unsupported"):
        # Conservative: all unsupported examples are one family without a reviewed taxonomy.
        return "unsupported"
    concepts = sorted((c.get("concept"), c.get("subtype"), c.get("role"),
                       (c.get("attributes") or {}).get("od_role", "")) for c in payload["concepts"])
    factors = {k: v if k in {"aggregation", "rollup", "bucket", "answer", "dimension", "dimension_target", "order"}
               else "<condition>" for k, v in payload["factors"].items()}
    return hashlib.sha256(canonical_json([concepts_to_lists(concepts), factors]).encode()).hexdigest()


def concepts_to_lists(concepts):
    return [list(c) for c in concepts]


def assign_groups(records):
    parent = list(range(len(records)))
    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    tokens = {}
    ids = {r["metadata"]["source_record_id"]: i for i, r in enumerate(records)}
    for i, record in enumerate(records):
        meta = record["metadata"]
        keys = ["template:" + template_key(record)]
        for field in ("parent_intent", "family"):
            if meta.get(field):
                keys.append(field + ":" + meta[field])
        for tag in meta.get("tags", []):
            if tag.startswith("contrast_pair:") and tag.split(":", 1)[1] in ids:
                parent[root(i)] = root(ids[tag.split(":", 1)[1]])
        for key in keys:
            if key in tokens:
                parent[root(i)] = root(tokens[key])
            tokens[key] = i
    components = {}
    for i, record in enumerate(records):
        components.setdefault(root(i), []).append(record)
    for members in components.values():
        names = sorted(r["metadata"]["source_record_id"] for r in members)
        group = "intent-" + hashlib.sha256(canonical_json(names).encode()).hexdigest()[:16]
        for record in members:
            record["metadata"]["parent_intent"] = group
    return records


def split_records(records, *, seed=42, valid_fraction=0.2):
    if not 0 < valid_fraction < 1:
        raise ValueError("valid_fraction must be between 0 and 1")
    assign_groups(records)
    groups = sorted({r["metadata"]["parent_intent"] for r in records})
    random.Random(seed).shuffle(groups)
    count = max(1, min(len(groups) - 1, round(len(groups) * valid_fraction))) if len(groups) > 1 else 0
    valid_groups = set(groups[:count])
    train, valid = [], []
    for record in records:
        destination = valid if record["metadata"]["parent_intent"] in valid_groups else train
        destination.append(record)
    check_split(train, valid)
    return train, valid


def check_split(train, valid):
    if {r["metadata"]["parent_intent"] for r in train} & {r["metadata"]["parent_intent"] for r in valid}:
        raise ValueError("Parent intent leakage between train/validation")
    def question(record):
        return question_key((record.get("messages") or record["prompt"])[1]["content"])
    if {question(r) for r in train} & {question(r) for r in valid}:
        raise ValueError("Train/validation duplicate question")
