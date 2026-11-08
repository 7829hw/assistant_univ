#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GeoFlow semantic-balanced one-epoch scheduler (data order only).

No evaluation examples, predictions, or error rates are read here. Labels derive
solely from the approved TRAIN corpus. This is an experiment implementation,
not evidence of improved model accuracy.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict, deque
import hashlib
import json
import math
from pathlib import Path
import random
from typing import Any, Iterable

MAX_RUN = 4


def canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def sha_lines(lines: Iterable[str]) -> str:
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_jsonl(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def rid(record: dict) -> str:
    m = record["metadata"]
    return f"{m['source_record_id']}|{m['trace_id']}"


def qid(record: dict) -> str:
    return str(record["metadata"]["source_record_id"])


def within_key(record: dict) -> tuple:
    m = record["metadata"]
    if m["loss_scope"] == "full_response":
        return (0, m["trace_id"])
    return (1, m.get("trace_sha256") or m["trace_id"])


def training_record_slots(records: list[dict]) -> dict[str, dict]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        groups[qid(r)].append(r)
    out = {}
    for q in sorted(groups):
        for k, r in enumerate(sorted(groups[q], key=within_key)):
            out[f"{q}#{k}"] = r
    return out


def random_slot_order(records: list[dict], seed: int) -> list[str]:
    """Portable random-slot reference, NOT identical to NumPy O4' RNG."""
    slots = training_record_slots(records)
    keys = sorted(slots)
    random.Random(seed).shuffle(keys)
    return [rid(slots[k]) for k in keys]


def _digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()[:12]


def _value(obj: Any, *names: str) -> str:
    if not isinstance(obj, dict):
        return "unknown"
    for name in names:
        val = obj.get(name)
        if val not in (None, "", [], {}):
            if isinstance(val, (dict, list)):
                return _digest(val)
            return str(val)
    return "unknown"


def _time_type(args: dict) -> str:
    if args.get("bucket"):
        return "bucket:" + str(args["bucket"]) + ("+rollup" if args.get("rollup") else "")
    date = str(args.get("date") or "")
    if not date:
        return "none"
    if date in ("today", "yesterday") or len(date) == 8 and date.isdigit():
        return "day"
    for unit in ("week", "month", "year"):
        if unit in date:
            return unit
    if date in ("weekend", "weekday", "holiday"):
        return "weekday_type"
    return "range" if "-" in date else "other"


SIDO_NAMES = {
    '서울','부산','대구','인천','광주','대전','울산','세종','경기','강원',
    '충북','충남','전북','전남','경북','경남','제주',
    '충청북','충청남','전라북','전라남','경상북','경상남',
}
POI_NAMES = {'광안리','동성로','동대구역','어린이대공원'}


def _region_type(execution: list[dict]) -> str:
    vals = []
    for call in execution:
        if call.get("tool") != "get_place_scope":
            continue
        args = call.get("args") or {}
        n = str(args.get("name") or "")
        if args.get("include_vicinity") or n in POI_NAMES:
            vals.append("poi")
        elif n in SIDO_NAMES or any(n.endswith(suffix) and n[:-len(suffix)] in SIDO_NAMES
                                    for suffix in ('특별자치시','특별자치도','특별시','광역시','도')):
            vals.append('province')
        elif n.endswith(("동", "읍", "면", "가")):
            vals.append("dong")
        elif n.endswith(("구", "군", "시")):
            vals.append("district")
        elif n.endswith(("도", "특별시", "광역시", "특별자치시")):
            vals.append("province")
        else:
            vals.append("poi")
    for v in ("poi", "dong", "district", "province"):
        if v in vals:
            return v
    return "none"


def _date_unit(value: Any) -> str:
    v = str(value or "")
    if not v:
        return "none"
    if v in ("weekend", "weekday", "holiday"):
        return "weekday_type"
    for unit in ("week", "month", "year"):
        if unit in v:
            return unit
    if v in ("today", "yesterday") or (len(v) == 8 and v.isdigit()):
        return "day"
    return "range" if "-" in v else "other"


def _name_region_type(name: str, vicinity: bool) -> str:
    n = str(name or "")
    if vicinity or n in POI_NAMES:
        return "poi"
    if n in SIDO_NAMES or any(n.endswith(x) and n[:-len(x)] in SIDO_NAMES
                              for x in ("특별자치시", "특별자치도", "특별시", "광역시", "도")):
        return "province"
    if n.endswith(("동", "읍", "면", "가")):
        return "dong"
    if n.endswith(("구", "군", "시")):
        return "district"
    return "poi"


def build_tool_map(corpus_rows: Iterable[dict]) -> dict[str, str]:
    """metric -> analysis tool, learned ONLY from approved TRAIN rows that carry gold execution.

    A metric is mapped only if it maps to exactly one tool in that evidence; otherwise it stays 'unknown'
    (no guessing).
    """
    seen: dict[str, set[str]] = defaultdict(set)
    for row in corpus_rows:
        measure = ((row.get("view") or {}).get("measure") or {}).get("subtype")
        call = next((c for c in (row.get("execution") or []) if c.get("tool") != "get_place_scope"), None)
        if measure and call:
            seen[str(measure)].add(str(call["tool"]))
    return {m: next(iter(t)) for m, t in seen.items() if len(t) == 1}


def question_signature(corpus: dict, *, refusal: bool = False, tool_map: dict[str, str] | None = None) -> tuple[str, str]:
    """Two-level, train-only signature derived uniformly from the approved ``view`` (present for every row).

    coarse = (tool, metric); tool comes from approved gold execution when present, otherwise from the
    train-evidence ``tool_map`` (only for metrics whose tool is unique there), otherwise 'unknown'.
    fine   = (coarse, aggregation, temporal_unit, region_type, od_role). Missing fields: aggregation/time/od
    -> 'none' when the approved view states the factor is absent; 'unknown' only when the view itself is missing.
    Never consults evaluation labels or model answers.
    """
    if refusal:
        return ("refusal", "refusal")
    view = corpus.get("view")
    if not isinstance(view, dict):
        return ("unknown|unknown", "unknown")
    measure = str(((view.get("measure") or {}).get("subtype")) or "unknown")
    execution = corpus.get("execution") or []
    call = next((c for c in execution if c.get("tool") != "get_place_scope"), None)
    tool = str(call["tool"]) if call else (tool_map or {}).get(measure, "unknown")
    coarse = f"{tool}|{measure}"
    conds = view.get("conditions") or []
    vicinity = any((c.get("args") or {}).get("include_vicinity") for c in execution if c.get("tool") == "get_place_scope")
    vicinity = vicinity or bool((corpus.get("semantics") or {}).get("factors", {}).get("vicinity"))
    regions = [_name_region_type((c.get("value") or {}).get("name") if isinstance(c.get("value"), dict) else "", vicinity)
               for c in conds if c.get("subtype") == "place"]
    if any(c.get("subtype") == "scope" for c in conds) and not regions:
        regions = ["scope_ref"]
    region = next((r for r in ("poi", "dong", "district", "province", "scope_ref") if r in regions), "none")
    roles = sorted({str(c.get("od_role")) for c in conds if c.get("subtype") in ("place", "scope") and c.get("od_role")})
    od = "+".join(roles) if roles else "none"
    if view.get("dimension_target"):
        od += f">{view['dimension_target']}"
    date = next((c.get("value") for c in conds if c.get("subtype") == "date"), None)
    unit = str(view.get("bucket") or _date_unit(date))
    agg = str(view.get("aggregation") or "none")
    if view.get("rollup"):
        agg += f"/{view['rollup']}"
    fine = f"{coarse}|agg={agg}|t={unit}|reg={region}|od={od}"
    return coarse, fine


def labels_from_approved(records: list[dict], approved: list[dict]) -> dict[str, tuple[str, str]]:
    corpus = {str(x["id"]): x for x in approved}
    by_q: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        by_q[qid(r)].append(r)
    missing = [q for q in by_q if q not in corpus]
    if missing:
        raise ValueError(f"Missing {len(missing)} approved TRAIN ids, e.g. {missing[:3]}")
    tool_map = build_tool_map(corpus[q] for q in by_q)
    labels = {}
    for q, rows in by_q.items():
        refusals = [bool(x["metadata"].get("refusal_source")) for x in rows]
        if len(set(refusals)) != 1:
            raise ValueError("Mixed refusal and answering training records in question " + q)
        labels[q] = question_signature(corpus[q], refusal=refusals[0], tool_map=tool_map)
    return labels


def max_run(values: list[str]) -> int:
    mx = 0
    old = None
    streak = 0
    for x in values:
        streak = streak + 1 if x == old else 1
        mx = max(mx, streak)
        old = x
    return mx


def build_balanced_order(records: list[dict], labels: dict[str, tuple[str, str]], seed: int,
                         max_question_run: int = MAX_RUN,
                         fine_weight: float = 0.24) -> list[str]:
    """Hierarchical deficit round-robin: balanced coarse -> fine -> question.

    Each record occurs exactly once. Question order within a question retains
    the repository's teacher-first / trace-hash rule. Seed changes tie-breaking.
    """
    rng = random.Random(int(seed))
    per_q: dict[str, deque[str]] = {}
    for q in sorted({qid(r) for r in records}):
        rr = sorted((r for r in records if qid(r) == q), key=within_key)
        per_q[q] = deque(rid(x) for x in rr)
    if set(per_q) != set(labels):
        raise ValueError("Question labels do not cover exactly the training question ids")
    if len({rid(r) for r in records}) != len(records):
        raise ValueError("Training record ids are not unique")

    coarse_tot = Counter()
    fine_tot = Counter()
    question_tot = {}
    fine_q: dict[str, list[str]] = defaultdict(list)
    fine_coarse = {}
    for q, queue in per_q.items():
        cg, fg = labels[q]
        n = len(queue)
        coarse_tot[cg] += n
        fine_tot[fg] += n
        question_tot[q] = n
        fine_q[fg].append(q)
        if fg in fine_coarse and fine_coarse[fg] != cg:
            raise ValueError("Fine signature belongs to two coarse groups")
        fine_coarse[fg] = cg
    for qs in fine_q.values():
        rng.shuffle(qs)
    N = len(records)
    coarse_seen = Counter()
    fine_seen = Counter()
    question_seen = Counter()
    all_fine = list(sorted(fine_q))
    out = []
    last_q = None
    run = 0
    for i in range(N):
        tick = i + 1
        # Only groups containing an eligible question may be considered.
        candidates = []
        for f in all_fine:
            if fine_seen[f] >= fine_tot[f]:
                continue
            eligible = [q for q in fine_q[f] if per_q[q] and not (q == last_q and run >= max_question_run)]
            if not eligible:
                continue
            c = fine_coarse[f]
            coarse_lag = tick * coarse_tot[c] / N - coarse_seen[c]
            fine_lag = tick * fine_tot[f] / N - fine_seen[f]
            # Coarse balance first; within one coarse distribute fine labels.
            score = coarse_lag + fine_weight * fine_lag + rng.random() * 0.025
            candidates.append((score, f, eligible))
        if not candidates:
            raise ValueError("No eligible next record; run constraint infeasible")
        _, f, qs = max(candidates, key=lambda x: x[0])
        # Expose each question within a fine group proportionally over the epoch.
        q = max(qs, key=lambda k: (tick * question_tot[k] / N - question_seen[k]) + rng.random() * 0.045)
        out.append(per_q[q].popleft())
        coarse_seen[fine_coarse[f]] += 1
        fine_seen[f] += 1
        question_seen[q] += 1
        run = run + 1 if q == last_q else 1
        last_q = q
    assert len(out) == N and len(set(out)) == N
    assert max_run([k.split("|", 1)[0] for k in out]) <= max_question_run
    return out


def sequence_metrics(seq: list[str], labels: dict[str, tuple[str, str]], window: int = 128) -> dict:
    coarse_of = lambda key: labels[key.split("|", 1)[0]][0]
    fine_of = lambda key: labels[key.split("|", 1)[0]][1]
    N = len(seq)
    frequencies = Counter(map(coarse_of, seq))
    fg = Counter(map(fine_of, seq))
    def metrics_for(getter, totals):
        seen = Counter()
        high = 0.0
        for tick, key in enumerate(seq, 1):
            seen[getter(key)] += 1
            high = max(high, max(abs(seen[g] - tick * count / N)
                                 for g, count in totals.items()))
        windows = []
        for start in range(0, N, window):
            sample = seq[start:start+window]
            actual = Counter(map(getter, sample))
            size = len(sample)
            tv = .5 * sum(abs(actual[k]/size - v/N) for k, v in totals.items())
            windows.append(tv)
        return {"max_observed_label_prefix_discrepancy_records": round(high, 4),
                "mean_window_total_variation": round(sum(windows)/len(windows), 5),
                "max_window_total_variation": round(max(windows), 5)}
    return {"n_records": N,"n_questions": len(set(k.split("|", 1)[0] for k in seq)),
            "n_coarse_groups": len(frequencies),"n_fine_groups": len(fg),
            "max_question_run": max_run([k.split("|", 1)[0] for k in seq]),
            "coarse": metrics_for(coarse_of, frequencies),
            "fine": metrics_for(fine_of, fg)}


def validate_coverage_variant(base: list[dict], candidate: list[dict], approved: list[dict],
                              *, blocked_ids: set[str] | None = None,
                              blocked_families: set[str] | None = None,
                              loss_ledger: dict[str, int] | None = None,
                              token_tolerance: float = 0.01) -> dict:
    """Fail closed on incomplete protection/audit inputs.

    The blocked families must come from the project's authoritative protected
    evaluation overlap rules, not from interpreting test questions here.
    """
    if blocked_ids is None or blocked_families is None or loss_ledger is None:
        raise ValueError("Coverage changes require blocked-id, blocked-family and per-record loss-token ledgers")
    changed = {rid(r) for r in candidate} - {rid(r) for r in base}
    if changed and (not blocked_ids or not blocked_families):
        raise ValueError("Coverage augmentation requires nonempty authoritative protected-id and protected-family blocklists")
    if len(base) != len(candidate):
        raise ValueError("Coverage arm must match baseline record count and SGD steps exactly")
    aid = {str(x["id"]): x for x in approved}
    b_ids = {rid(r) for r in base}
    c_ids = [rid(r) for r in candidate]
    if len(c_ids) != len(set(c_ids)):
        raise ValueError("Duplicate candidate record keys")
    for r in candidate:
        q = qid(r)
        if q not in aid:
            raise ValueError("Unapproved candidate question " + q)
        if q in blocked_ids:
            raise ValueError("Candidate overlaps protected evaluation id " + q)
        fam = str((aid[q].get("metadata") or {}).get("template_group") or aid[q].get("template_group") or "")
        if rid(r) in changed and not fam:
            raise ValueError("New coverage record lacks approved family label; run authoritative overlap auditor")
        if fam and fam in blocked_families:
            raise ValueError("Candidate overlaps protected evaluation family " + fam)
    if any(k not in loss_ledger for k in list(b_ids) + c_ids):
        raise ValueError("Loss token ledger incomplete; calculate with training tokenizer")
    a = sum(loss_ledger[k] for k in b_ids)
    b = sum(loss_ledger[k] for k in c_ids)
    if a <= 0 or abs(a-b)/a > token_tolerance:
        raise ValueError(f"Token budget mismatch: base={a}, candidate={b}, tol={token_tolerance}")
    return {"records": len(base),"questions_base":len({qid(r) for r in base}),
            "questions_candidate":len({qid(r) for r in candidate}),
            "added_record_keys":len(set(c_ids)-b_ids),"removed_record_keys":len(b_ids-set(c_ids)),
            "base_loss_tokens":a,"candidate_loss_tokens":b,
            "loss_token_ratio":b/a,"protected_id_and_family_checks":True}


def build_manifest(train_path: Path, approved_path: Path, output_dir: Path,
                   seeds: list[int], reference_order_dirs: list[Path] | None = None,
                   fine_weight: float = 0.24) -> dict:
    records = read_jsonl(train_path)
    approved = read_jsonl(approved_path)
    labels = labels_from_approved(records, approved)
    record_keys = [rid(x) for x in records]
    if len(record_keys) != len(set(record_keys)):
        raise ValueError("Repeated training record key")
    if not (0.0 <= fine_weight <= 0.5):
        raise ValueError("Fine weight must be in [0.0, 0.5]")
    output_dir.mkdir(parents=True, exist_ok=True)
    baseline_hash = sha_file(train_path)
    gold_hash = sha_file(approved_path)
    approved_by_id = {str(x["id"]):x for x in approved}
    answering = {qid(r) for r in records if not r["metadata"].get("refusal_source")}
    labeled_with_execution = sum(bool(approved_by_id[q].get("execution")) for q in answering)
    label_audit = {"answering_questions":len(answering),
                   "with_approved_execution":labeled_with_execution,
                   "fallback_to_approved_view":len(answering)-labeled_with_execution,
                   "coarse_groups":len({v[0] for v in labels.values()}),
                   "fine_groups":len({v[1] for v in labels.values()})}
    summary = {"label":"semantic_order_offline_only", "training_data":str(train_path),
               "train_sha256":baseline_hash,"approved_sha256":gold_hash,
               "records":len(records),"questions":len(labels),"seeds":{},
               "label_audit":label_audit,
               "fine_weight":fine_weight,"holdout_used_for_order":False}
    for seed in seeds:
        seq = build_balanced_order(records, labels, seed, fine_weight=fine_weight)
        if set(seq) != set(record_keys):
            raise AssertionError("Record set changed")
        baseline = None
        for reference_dir in reference_order_dirs or []:
            p = reference_dir / f"order_b2_o{seed}.json"
            if p.exists():
                order = json.loads(p.read_text(encoding="utf-8"))["order"]
                slots = training_record_slots(records)
                if len(order) != len(slots) or set(order) != set(slots):
                    raise ValueError("Reference O4' order does not cover current train corpus")
                baseline = [rid(slots[k]) for k in order]
                break
        bmetrics = sequence_metrics(baseline or random_slot_order(records, seed), labels)
        metrics = sequence_metrics(seq, labels)
        body = {"arm":"SEMANTIC_ORDER", "seed":seed,
                "rule":"train-only two-level weighted-deficit fair scheduling",
                "fine_weight":fine_weight,
                "training_sha256":baseline_hash,"approved_sha256":gold_hash,
                "record_sequence":seq,"record_sequence_sha256":sha_lines(seq),
                "max_run_limit":MAX_RUN,"max_run_ok":metrics["max_question_run"]<=MAX_RUN,
                "baseline_metrics":bmetrics,"balanced_metrics":metrics,
                "reference_is_true_o4prime":baseline is not None}
        out = output_dir / f"semantic_order_o{seed}.json"
        out.write_text(json.dumps(body,ensure_ascii=False,indent=1)+"\n",encoding="utf-8")
        summary["seeds"][str(seed)]={"file":str(out),"sha256":body["record_sequence_sha256"],
                                    "baseline":bmetrics,"balanced":metrics,
                                    "reference_is_true_o4prime":baseline is not None}
    sp = output_dir / "offline_validation_summary.json"
    sp.write_text(json.dumps(summary,ensure_ascii=False,indent=1)+"\n",encoding="utf-8")
    return summary


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--train",type=Path,required=True)
    ap.add_argument("--approved",type=Path,required=True)
    ap.add_argument("--output-dir",type=Path,required=True)
    ap.add_argument("--seeds",type=int,nargs="+",default=[1102,211102,2026113,2026117,2026131])
    ap.add_argument("--reference-order-dir",type=Path,action="append",default=[])
    ap.add_argument("--fine-weight",type=float,default=0.24)
    args=ap.parse_args(argv)
    report=build_manifest(args.train,args.approved,args.output_dir,args.seeds,args.reference_order_dir,args.fine_weight)
    print(json.dumps({"records":report["records"],"questions":report["questions"],
                      "output_dir":str(args.output_dir),"seeds":list(report["seeds"])}))


if __name__=="__main__":
    main()
