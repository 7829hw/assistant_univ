# -*- coding: utf-8 -*-
"""batch012·refusal_dev 확장 후보 검사(pilot_009 준비 P2·P3, 결정 229·230). ``batch011/build_candidates11.py``의 사본: 검사 규칙·결정 120 분류는 그대로, 바꾼 것:
- 대상에 batch011 초안 전체(``batch011``), 승인 corpus v4(``approved_v4``, batch011 승인분 포함), **RC6 실제 학습 레코드**(``validate_v2.train_targets``, RC6 full + corpus v4),
  refusal_dev v1 승인본·초안(``refusal_dev_v1``)을 더함. RC5 학습 레코드(기존 대상)도 그대로 본다.
- ``--set batch012``이면 refusal_dev 확장 초안(``pilot_009/refusal_dev2/candidates_draft.yaml``, 있으면)을, ``--set refusal_dev2``이면 batch012 초안 전체를 대상에 넣는다(둘이 겹치지 않게).
- 거부 문항(``kind: r1_refusal``)은 정규화 질문·문자 3-gram Jaccard ≥ 0.5만, r2는 batch011과 같은 검사(schema, 검증 사슬, Full 경로 답함, 겹침 전부).
모델 호출 없음. 승인하지 않는다.

    hfvenv/bin/python sft_dpo_inventory/batch012/build_candidates12.py [--set batch012|refusal_dev2]

batch011 설명: batch011·refusal_dev 후보 검사(pilot_008 P2·P3, 결정 219). ``batch010/build_candidates10.py``의 사본.

원 설명: batch010 후보 검사(pilot_007 A단계 C3, 결정 169). ``batch009/build_candidates.py``의 사본: 검사 규칙·결정 120 분류는 그대로,
대상에 batch009 후보(검사 통과분)를 더하고 학습 비교 대상을 승인 corpus v2(``approved_train_v2.jsonl``)로 바꿨다. 모델 호출 없음. 승인하지 않는다.

원 설명: batch009 후보의 현재 코드 결과와 겹침 검사. batch008 사본에 결정 120 분류를 바로 적용하고, 대상에 batch008 후보와 pilot_006 승인 corpus(R0)를 더했다.

    hfvenv/bin/python sft_dpo_inventory/batch010/build_candidates10.py

**결정 120 분류(결과 전에 정함)**: 강한 겹침(정규화 질문, Jaccard ≥ 0.5, 같은 정답 grounding, thor 보호 질문·id)·schema·검증 사슬 실패·Full 경로 미응답은 뺀다.
약한 겹침은 selection_v2·augmentation_holdout_v1·valid98·aux_test_v1 중 하나와 family가 같으면 뺀다. 업체 100과만, 또는 template 수준만 겹치면 남긴다(결정 54식 예외로 기록).
그 밖의 family 겹침(selection_v1, thor 보호 family, 확장 family)만 남으면 E5와 같이 "분류 밖"으로 빼 두고 보고한다.

- 현재 코드: 정답 호출 schema 검사, 역산 grounding + 질문 span(``aug300_review/draft_semantics.add_spans``), 검증 사슬
  (``grounding.validation.validate_semantics``: Full·Partial 같은 판정·mock 결과, execution 층과의 일치), T2PC 경로 판정(``assess_t2pc``).
- 겹침 검사: W6(``pilot_006_prep/aug300/check_aug300.py``)과 같은 도구와 대상(보호 셋 5개, batch007, 학습 데이터 v006_t2pc·pilot004,
  pg_imports 세 가지)에 300문항 v2 전체(``aug300``)를 더했다. thor leakage(질문·id·template·family), 확장 template·family도 본다.
- **빼는 기준(batch007과 같음, 결과 전에 정함)**: 정규화 질문 일치, 문자 3-gram Jaccard ≥ 0.5, 같은 정답 grounding(어느 대상이든),
  thor leakage 사유, 확장 template·family, 보호 셋 5개와의 template·family. 학습 데이터·batch007·aug300·pg와의 template·family는 정보로만 남긴다.
  현재 코드에서 검증 사슬이 실패하거나 Full 경로가 mock에서 답하지 못하는 후보도 뺀다.
출력: ``candidates_checked.json``(남은 후보), ``excluded.json``(빠진 이유·분류), ``inputs_first_response.jsonl``(J-b010 첫 응답 입력), ``inputs_self.jsonl``(J-b010 두 arm 표본 입력).
"""
import collections
import json
import sys
from pathlib import Path

import yaml

HERE0 = Path(__file__).resolve().parent
ROOT = HERE0.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/batch004"))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_006_prep/aug300"))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_006_prep/aug300_review"))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_006/protected_final"))
SET = sys.argv[sys.argv.index("--set") + 1] if "--set" in sys.argv else "batch012"
HERE = HERE0 if SET == "batch012" else ROOT / "sft_dpo_inventory/pilot_009/refusal_dev2"
RDEV2 = ROOT / "sft_dpo_inventory/pilot_009/refusal_dev2/candidates_draft.yaml"
RC6 = "sft_dpo_inventory/pilot_008/build/RC6/full/sft_train.jsonl"
V4 = ROOT / "sft_dpo_inventory/pilot_006_prep/approved/approved_train_v4.jsonl"

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


KEEP_OUT = ("selection_v2", "holdout", "valid98", "aux_test_v1")


def targets():
    import evaluate_vendor100 as EV
    out = W6.load_targets(None)
    for row in json.loads((ROOT / "sft_dpo_inventory/batch008/candidates_checked.json").read_text(encoding="utf-8"))["candidates"]:
        out["batch008"].append((row["id"], row["question"], row["draft_grounding"]))
    for row in json.loads((ROOT / "sft_dpo_inventory/batch009/candidates_checked.json").read_text(encoding="utf-8"))["candidates"]:
        out["batch009"].append((row["id"], row["question"], row["draft_grounding"]))
    for row in json.loads((ROOT / "sft_dpo_inventory/batch010/candidates_checked.json").read_text(encoding="utf-8"))["candidates"]:
        out["batch010"].append((row["id"], row["question"], row["draft_grounding"]))
    import validate_v2
    tt, missing = validate_v2.train_targets(validate_v2.DEFAULT_TRAIN, validate_v2.DEFAULT_CORPUS)
    if missing:
        raise SystemExit(f"RC5 ids missing in corpus v3: {len(missing)}")
    out.update(tt)
    tt6, missing6 = validate_v2.train_targets([RC6], str(V4.relative_to(ROOT)))
    if missing6:
        raise SystemExit(f"RC6 ids missing in corpus v4: {len(missing6)}")
    out.update(tt6)
    der = lambda c: EV.derive_grounding(EV.parse_calls(c["gold_text"])) if c.get("gold_text") else None  # noqa: E731
    for c in yaml.safe_load((ROOT / "sft_dpo_inventory/batch011/candidates_draft.yaml").read_text(encoding="utf-8"))["candidates"]:
        out["batch011"].append((c["id"], c["question"], der(c)))
    for c in yaml.safe_load((ROOT / "sft_dpo_inventory/pilot_008/refusal_dev/candidates_draft.yaml").read_text(encoding="utf-8"))["candidates"]:
        out["refusal_dev_v1"].append((f"draft:{c['id']}", c["question"], der(c)))
    for c in yaml.safe_load((ROOT / "sft_dpo_inventory/pilot_008/refusal_dev/approved/rdev_v1_gold.yaml").read_text(encoding="utf-8"))["items"]:
        out["refusal_dev_v1"].append((c["id"], c["question"], der(c)))
    other = RDEV2 if SET == "batch012" else HERE0 / "candidates_draft.yaml"
    if other.exists():
        for c in yaml.safe_load(other.read_text(encoding="utf-8"))["candidates"]:
            out["refusal_dev2_draft" if SET == "batch012" else "batch012_draft"].append((c["id"], c["question"], der(c)))
    from grounding.full_renderer import render_full
    for row in read_jsonl(V4):
        out["approved_v4"].append((row["id"], row["question"], render_full(row["semantics"]) if not (row["semantics"] or {}).get("unsupported") else None))
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
    hold_ids = {i["id"] for i in json.loads((ROOT / "sft_dpo_inventory/pilot_006_prep/aug300/holdout_v1.json").read_text(encoding="utf-8"))["list"]}
    hold_f = {family_key(EV.derive_grounding(i["gold"])) for i in read_jsonl(AUG) if i["id"] in hold_ids}
    hold_t = {template_key(as_record(EV.derive_grounding(i["gold"]))) for i in read_jsonl(AUG) if i["id"] in hold_ids}
    kept, excluded, seen = [], [], {}
    for cand in doc["candidates"]:
        if cand["kind"] == "r1_refusal":
            qk = question_key(cand["question"])
            g = W6.grams(qk)
            t2pc = assess_t2pc({"unsupported": True}, cand["question"])
            t2pc.pop("signature", None)
            thor = guard.reasons(cand["question"], None, [cand["id"]]) if hasattr(guard, "reasons") else []
            per_set = {}
            for name, idx in index.items():
                best = max(((len(g & vg) / len(g | vg), rid) for rid, vg in idx["g"]), default=(0.0, None))
                per_set[name] = {"question": idx["q"].get(qk, []), "jaccard_max": round(best[0], 3), "jaccard_nearest": best[1]}
            why = [f"thor:{r}" for r in thor if r in ("protected_question", "protected_id")]
            for name, e in per_set.items():
                why += [f"{name}:question"] if e["question"] else []
                why += [f"{name}:jaccard>=0.5({e['jaccard_nearest']},{e['jaccard_max']})"] if e["jaccard_max"] >= 0.5 else []
            why += [] if t2pc.get("outcome") == "unsupported" else [f"refusal_target_not_unsupported:{t2pc.get('outcome')}"]
            if qk in seen:
                why.append(f"duplicate_of:{seen[qk]}")
            seen.setdefault(qk, cand["id"])
            row = {**cand, "decision_120": "뺌(강한 겹침·검사 실패)" if why else "남김(거부 문항: 질문·Jaccard만 검사)", "gold": [], "draft_grounding": {"unsupported": True},
                   "t2pc": t2pc, "leakage": {"thor_policy_reasons": thor, "per_set": per_set}}
            (excluded if why else kept).append({**row, "excluded_reasons": why} if why else row)
            continue
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
        strong, weak_keep, weak_out, other = [], [], [], []
        strong += [f"thor:{r}" for r in thor if r in ("protected_question", "protected_id")]
        for name, e in per_set.items():
            strong += [f"{name}:question"] if e["question"] else []
            strong += [f"{name}:jaccard>=0.5({e['jaccard_nearest']},{e['jaccard_max']})"] if e["jaccard_max"] >= 0.5 else []
            strong += [f"{name}:same_grounding"] if e["same_grounding"] and name not in ("approved_v4",) else []
            strong += [f"{name}:same_grounding(training)"] if e["same_grounding"] and name == "approved_v4" else []
        fam_sets = {n for n, e in per_set.items() if e["family"]} | ({"holdout"} if fk in hold_f else set())
        tmpl_sets = {n for n, e in per_set.items() if e["template"]} | ({"holdout"} if tk in hold_t else set())
        weak_out += [f"{n}:family" for n in sorted(fam_sets & set(KEEP_OUT))]
        other += [f"{n}:family" for n in sorted(fam_sets & {"selection_v1"})]
        other += [f"thor:{r}" for r in thor if r == "protected_semantic_family"]
        other += ["extended_family"] if ext_f.get(fk) else []
        weak_keep += [f"{n}:family" for n in sorted(fam_sets & {"vendor100"})]
        weak_keep += [f"{n}:template" for n in sorted(tmpl_sets & (set(KEEP_OUT) | {"selection_v1", "vendor100"}))]
        weak_keep += ["extended_template"] if ext_t.get(tk) else []
        weak_keep += [f"thor:{r}" for r in thor if r == "protected_semantic_template"]
        why = list(strong) + weak_out
        why += [f"schema:{x}" for x in schema_errors]
        why += [] if chain["ok"] else ["validation_chain_failed"]
        why += [] if chain["full_answered"] else [f"full_path_not_answered:{chain['mock_full']['error_code'] or chain['full']['error_code']}"]
        unclassified = not why and bool(other)
        why += [f"분류 밖:{w}" for w in other] if unclassified else []
        if qk in seen:
            why.append(f"duplicate_of:{seen[qk]}")
        seen.setdefault(qk, cand["id"])
        info = {"training_and_other_template_family": {n: {k: per_set[n][k] for k in ("template", "family") if per_set[n][k]}
                                                         for n in per_set if n not in PROTECTED and (per_set[n]["template"] or per_set[n]["family"])}}
        row = {**cand, "decision_120": ("뺌(강한 겹침·검사 실패)" if strong or schema_errors or not chain["ok"] or not chain["full_answered"]
                                         else "뺌(보호 넷 family)" if weak_out else "분류 밖(빼 둔 채 보고)" if unclassified
                                         else "남김(결정 54식 예외: " + ", ".join(weak_keep) + ")" if weak_keep else "남김"),
               "gold": calls, "draft_grounding": payload, "span_flags": span_flags, "semantics": sem, "view": view(sem),
               "validation_chain": {k: chain[k] for k in ("ok", "assess_same", "mock_same", "execution_match", "full_answered")},
               "t2pc": t2pc, "leakage": {"thor_policy_reasons": thor, "per_set": per_set}, "overlap_info": info,
               "template_key": tk, "family_key": fk}
        (excluded if why else kept).append({**row, "excluded_reasons": why} if why else row)
    summary = {"prompt_hash": prompt_hash, "drafted": len(doc["candidates"]), "kept": len(kept), "excluded": len(excluded),
               "kept_by_gap": dict(collections.Counter(r["gap"] for r in kept)), "drafted_by_gap": dict(collections.Counter(c["gap"] for c in doc["candidates"])),
               "excluded_by_class": dict(collections.Counter(f"{r['gap']}|{r['decision_120']}" for r in excluded)),
               "excluded_by_gap": dict(collections.Counter(r["gap"] for r in excluded)),
               "excluded_reasons": dict(collections.Counter(w.split("(")[0] for r in excluded for w in r["excluded_reasons"])),
               "chain_ok_kept(r2)": sum(r["validation_chain"]["ok"] for r in kept if r["kind"] == "r2_contrast"),
               "kept_by_kind": dict(collections.Counter(r["kind"] for r in kept)), "set": SET,
               "t2pc_outcomes_kept": dict(collections.Counter(f"{r['t2pc'].get('outcome')}:{r['t2pc'].get('error_code')}" for r in kept)),
               "jaccard_max_any_target(kept)": max(max(e["jaccard_max"] for e in r["leakage"]["per_set"].values()) for r in kept) if kept else None,
               "target_sets": {n: len(v) for n, v in tg.items()}, "protection_sources": len(guard.paths),
               "inputs": {"candidates_draft.yaml": sha256(HERE / "candidates_draft.yaml"), "aug300": sha256(AUG),
                          "approved_train_v4": sha256(V4), "rc6_full": sha256(ROOT / RC6),
                          "rc5_full": sha256(ROOT / "sft_dpo_inventory/pilot_007/build/RC5/full/sft_train.jsonl"),
                          "batch011_draft": sha256(ROOT / "sft_dpo_inventory/batch011/candidates_draft.yaml"),
                          "refusal_dev_v1_gold": sha256(ROOT / "sft_dpo_inventory/pilot_008/refusal_dev/approved/rdev_v1_gold.yaml"),
                          **({"other_draft": sha256(RDEV2 if SET == "batch012" else HERE0 / "candidates_draft.yaml")}
                             if (RDEV2 if SET == "batch012" else HERE0 / "candidates_draft.yaml").exists() else {}),
                          **{n: sha256(p) for n, p in PG.items()}}}
    (HERE / "candidates_checked.json").write_text(json.dumps({"summary": summary, "candidates": kept}, ensure_ascii=False, indent=1) + "\n",
                                                  encoding="utf-8")
    (HERE / "excluded.json").write_text(json.dumps(excluded, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    with open(HERE / "inputs_first_response.jsonl", "w", encoding="utf-8") as out:
        for r in kept:
            out.write(json.dumps({"id": r["id"], "source": f"{SET}_draft", "question": r["question"], "gold_grounding": r["draft_grounding"],
                                  "gold_kind": f"{SET} 초안(승인 아님)", "kind": r["kind"]}, ensure_ascii=False) + "\n")
    with open(HERE / "inputs_self.jsonl", "w", encoding="utf-8") as out:
        for r in kept:
            out.write(json.dumps({"id": r["id"], "source": f"{SET}_draft", "question": r["question"], "kind": r["kind"]}, ensure_ascii=False) + "\n")
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
