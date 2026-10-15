# -*- coding: utf-8 -*-
"""batch008 후보의 현재 코드 결과와 겹침 검사(모델 호출 없음). 승인하지 않는다.

    hfvenv/bin/python sft_dpo_inventory/batch008/build_candidates.py

- 현재 코드: 정답 호출 schema 검사, 역산 grounding + 질문 span(``aug300_review/draft_semantics.add_spans``), 검증 사슬
  (``grounding.validation.validate_semantics``: Full·Partial 같은 판정·mock 결과, execution 층과의 일치), T2PC 경로 판정(``assess_t2pc``).
- 겹침 검사: W6(``pilot_006_prep/aug300/check_aug300.py``)과 같은 도구와 대상(보호 셋 5개, batch007, 학습 데이터 v006_t2pc·pilot004,
  pg_imports 세 가지)에 300문항 v2 전체(``aug300``)를 더했다. thor leakage(질문·id·template·family), 확장 template·family도 본다.
- **빼는 기준(batch007과 같음, 결과 전에 정함)**: 정규화 질문 일치, 문자 3-gram Jaccard ≥ 0.5, 같은 정답 grounding(어느 대상이든),
  thor leakage 사유, 확장 template·family, 보호 셋 5개와의 template·family. 학습 데이터·batch007·aug300·pg와의 template·family는 정보로만 남긴다.
  현재 코드에서 검증 사슬이 실패하거나 Full 경로가 mock에서 답하지 못하는 후보도 뺀다.
출력: ``candidates_checked.json``(남은 후보), ``excluded.json``, ``inputs_first_response.jsonl``(J7 입력: 남은 후보의 id·질문·역산 grounding).
"""
import collections
import json
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/batch004"))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_006_prep/aug300"))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_006_prep/aug300_review"))

import check_aug300 as W6  # noqa: E402
from build_candidates import extended_fingerprints  # noqa: E402
from draft_semantics import add_spans  # noqa: E402
from grounding.canonical import semantics_from_full, view  # noqa: E402
from grounding.validation import validate_semantics  # noqa: E402
from training.annotations.inventory import Protection, as_record, family_key  # noqa: E402
from training.data.common import check_expected_prompt, read_jsonl, sha256  # noqa: E402
from training.data.split import question_key, template_key  # noqa: E402
from training.data.validation import assess_t2pc  # noqa: E402

PI = ROOT / "sft_dpo_inventory/pg_imports"
PG = {"pg_batch006": PI / "pg_batch006/approved.jsonl", "pg_reviewed_reasoning_v001": PI / "reviewed_reasoning_v001/dataset.jsonl",
      "pg_reviewed_gold_v006_p0": PI / "reviewed_gold_v006_p0/sft_train.jsonl"}
AUG = ROOT / "sft_dpo_inventory/pilot_006_prep/aug300/augmentation_300.jsonl"
PROTECTED = W6.PROTECTED


def targets():
    import evaluate_vendor100 as EV
    out = W6.load_targets(None)
    for name, path in PG.items():
        for i, row in enumerate(read_jsonl(path)):
            if "messages" in row:
                q = next(m["content"] for m in row["messages"] if m["role"] == "user")
                meta = row.get("metadata") or {}
                out[name].append((meta.get("source_record_id") or f"#{i}", q, meta.get("target_full")))
            else:
                out[name].append((row["id"], row["question"], row["gold"] if isinstance(row["gold"], dict) else None))
    for it in read_jsonl(AUG):
        out["aug300"].append((it["id"], it["question"], EV.derive_grounding(it["gold"])))
    return out


def main():
    import evaluate_vendor100 as EV
    from jsonschema import Draft202012Validator

    from build import build
    prompt_hash = check_expected_prompt()
    doc = yaml.safe_load((HERE / "candidates_draft.yaml").read_text(encoding="utf-8"))
    tools, _ = build()
    schemas = {t["function"]["name"]: t["function"]["parameters"] for t in tools}
    guard = Protection.current(ROOT / "training/generated/reviewed_gold_v006_t2pc")
    ext_t, ext_f = extended_fingerprints()
    tg = targets()
    index = {}
    for name, rows in tg.items():
        idx = {"q": collections.defaultdict(list), "g": [], "view": collections.defaultdict(list), "t": collections.defaultdict(list),
               "f": collections.defaultdict(list)}
        for rid, q, payload in rows:
            qk = question_key(q)
            idx["q"][qk].append(rid)
            idx["g"].append((rid, W6.grams(qk)))
            if payload:
                try:
                    idx["view"][json.dumps(EV._grounding_view(payload), ensure_ascii=False, sort_keys=True, default=str)].append(rid)
                    idx["t"][template_key(as_record(payload))].append(rid)
                    idx["f"][family_key(payload)].append(rid)
                except Exception:  # noqa: BLE001
                    pass
        index[name] = idx
    kept, excluded, seen = [], [], {}
    for cand in doc["candidates"]:
        calls = EV.parse_calls(cand["gold_text"])
        schema_errors = []
        for i, call in enumerate(calls):
            concrete = {k: ("scope:district:0000000000" if isinstance(v, str) and EV._BINDING.match(v) else v) for k, v in call["args"].items()}
            schema_errors += [f"{call['tool']}[{i}]: {e.message}" for e in Draft202012Validator(schemas[call["tool"]]).iter_errors(concrete)]
        payload, span_flags = add_spans(EV.derive_grounding(calls), cand["question"])
        sem = semantics_from_full(payload)
        chain = validate_semantics(sem, cand["question"], calls)
        t2pc = assess_t2pc(payload, cand["question"])
        t2pc.pop("signature", None)
        qk = question_key(cand["question"])
        g = W6.grams(qk)
        tk, fk = template_key(as_record(payload)), family_key(payload)
        vk = json.dumps(EV._grounding_view(payload), ensure_ascii=False, sort_keys=True, default=str)
        thor = guard.reasons(cand["question"], payload, [cand["id"]])
        per_set = {}
        for name, idx in index.items():
            best = max(((len(g & vg) / len(g | vg), rid) for rid, vg in idx["g"]), default=(0.0, None))
            per_set[name] = {"question": idx["q"].get(qk, []), "jaccard_max": round(best[0], 3), "jaccard_nearest": best[1],
                             "same_grounding": idx["view"].get(vk, [])[:5], "template": len(idx["t"].get(tk, [])), "family": len(idx["f"].get(fk, []))}
        why = [f"thor:{r}" for r in thor] + [f"extended_{k}" for k, v in (("template", ext_t.get(tk)), ("family", ext_f.get(fk))) if v]
        for name, e in per_set.items():
            why += [f"{name}:question"] if e["question"] else []
            why += [f"{name}:jaccard>=0.5({e['jaccard_nearest']},{e['jaccard_max']})"] if e["jaccard_max"] >= 0.5 else []
            why += [f"{name}:same_grounding"] if e["same_grounding"] else []
            if name in PROTECTED:
                why += [f"{name}:{k}" for k in ("template", "family") if e[k]]
        why += [f"schema:{x}" for x in schema_errors]
        why += [] if chain["ok"] else ["validation_chain_failed"]
        why += [] if chain["full_answered"] else [f"full_path_not_answered:{chain['mock_full']['error_code'] or chain['full']['error_code']}"]
        if qk in seen:
            why.append(f"duplicate_of:{seen[qk]}")
        seen.setdefault(qk, cand["id"])
        info = {"training_and_other_template_family": {n: {k: per_set[n][k] for k in ("template", "family") if per_set[n][k]}
                                                         for n in per_set if n not in PROTECTED and (per_set[n]["template"] or per_set[n]["family"])}}
        row = {**cand, "gold": calls, "draft_grounding": payload, "span_flags": span_flags, "semantics": sem, "view": view(sem),
               "validation_chain": {k: chain[k] for k in ("ok", "assess_same", "mock_same", "execution_match", "full_answered")},
               "t2pc": t2pc, "leakage": {"thor_policy_reasons": thor, "per_set": per_set}, "overlap_info": info,
               "template_key": tk, "family_key": fk}
        (excluded if why else kept).append({**row, "excluded_reasons": why} if why else row)
    summary = {"prompt_hash": prompt_hash, "drafted": len(doc["candidates"]), "kept": len(kept), "excluded": len(excluded),
               "kept_by_gap": dict(collections.Counter(r["gap"] for r in kept)),
               "excluded_by_gap": dict(collections.Counter(r["gap"] for r in excluded)),
               "excluded_reasons": dict(collections.Counter(w.split("(")[0] for r in excluded for w in r["excluded_reasons"])),
               "chain_ok_kept": sum(r["validation_chain"]["ok"] for r in kept),
               "t2pc_outcomes_kept": dict(collections.Counter(f"{r['t2pc'].get('outcome')}:{r['t2pc'].get('error_code')}" for r in kept)),
               "jaccard_max_any_target": max(max(e["jaccard_max"] for e in r["leakage"]["per_set"].values()) for r in kept + excluded),
               "target_sets": {n: len(v) for n, v in tg.items()}, "protection_sources": len(guard.paths),
               "inputs": {"candidates_draft.yaml": sha256(HERE / "candidates_draft.yaml"), "aug300": sha256(AUG),
                          **{n: sha256(p) for n, p in PG.items()}}}
    (HERE / "candidates_checked.json").write_text(json.dumps({"summary": summary, "candidates": kept}, ensure_ascii=False, indent=1) + "\n",
                                                  encoding="utf-8")
    (HERE / "excluded.json").write_text(json.dumps(excluded, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    with open(HERE / "inputs_first_response.jsonl", "w", encoding="utf-8") as out:
        for r in kept:
            out.write(json.dumps({"id": r["id"], "source": "batch008_draft", "question": r["question"], "gold_grounding": r["draft_grounding"],
                                  "gold_kind": "batch008 초안(승인 아님)"}, ensure_ascii=False) + "\n")
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
