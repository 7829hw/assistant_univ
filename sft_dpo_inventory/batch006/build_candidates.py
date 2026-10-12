# -*- coding: utf-8 -*-
"""batch006 후보의 현재 코드 결과와 보호 셋 겹침을 계산한다(모델 호출 없음). 승인하지 않는다(결정 66·77).

    python sft_dpo_inventory/batch006/build_candidates.py

batch005(``../batch005/build_candidates.py``)와 같은 방법이다. 다른 점:
- 학습 데이터 기준은 ``reviewed_gold_v005_t2pc``(pilot_002 학습 corpus)다.
- 겹침 검사(겹치면 뺀다):
  1. thor leakage: ``Protection.current(reviewed_gold_v005_t2pc)``(보호 원본 전체: evaluation/**/*.yaml, registry, root 질문·stub,
     이전 판 보호 지문, valid 파일)의 정규화 질문, id, semantic template, semantic family.
  2. 확장 겹침: vendor 형식 보호 셋(업체 100 포함)의 정답 호출 역산 template·family(``batch004/build_candidates.extended_fingerprints``).
  3. 셋별 겹침(명시): selection_v1(100), selection_v2(98), aux_test_v1(51), valid98(98), 업체 100. 각 셋의 문항 목록으로 원본에서
     문항을 읽어 정규화 질문, template, family를 비교한다. 위 1·2가 이미 덮지만 셋 이름별로 따로 남긴다.
  4. 업체 100 문자 n-gram 유사도: 정규화 질문(``question_key``)의 문자 3-gram Jaccard. **0.5 이상이면 뺀다**(이 기준은 결과를 보기 전에
     정했다). 0.35 이상은 정보로 남긴다. 결과에는 업체 문항 id와 값만 적고 문장은 적지 않는다.
- 학습 데이터(v005)와의 겹침은 빼지 않고 정보로 남긴다.
"""
import json
import sys
from collections import Counter
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/batch004"))

from build_candidates import extended_fingerprints  # noqa: E402
from training.annotations.inventory import Protection, as_record, family_key  # noqa: E402
from training.data.canonicalize import check_shape, serialize_planner_target  # noqa: E402
from training.data.common import check_expected_prompt, read_jsonl  # noqa: E402
from training.data.split import question_key, template_key  # noqa: E402
from training.data.validation import assess, assess_t2pc, chosen_ok, t2pc_chosen_ok  # noqa: E402

GOLD_DIR = ROOT / "training/generated/reviewed_gold_v005_t2pc"
SETS = {
    "selection_v1": ROOT / "sft_dpo_inventory/pilot_prep_005/sets/selection_items.json",
    "selection_v2": ROOT / "sft_dpo_inventory/calibration_001/selection_v2_items.json",
    "aux_test_v1": ROOT / "sft_dpo_inventory/pilot_prep_005/sets/aux_test_items.json",
    "valid98": ROOT / "sft_dpo_inventory/pilot_001/valid98/valid98_items.json",
}
VENDOR = ROOT / "evaluation/vendor100/gold.yaml"
NGRAM, EXCLUDE_AT, INFO_AT = 3, 0.5, 0.35


def set_fingerprints():
    import evaluate_vendor100 as EV
    cache, out = {}, {}

    def items_of(path):
        if path not in cache:
            cache[path] = {i["id"]: i for i in EV.load_gold(ROOT / path)["items"]}
        return cache[path]

    def add(name, item):
        fp = out.setdefault(name, {"questions": {}, "templates": {}, "families": {}, "items": 0})
        fp["items"] += 1
        fp["questions"][question_key(item["question"])] = item["id"]
        try:
            payload = EV.gold_grounding(item)
        except Exception:  # noqa: BLE001 - 정답 호출이 없는 문항
            payload = None
        if payload:
            fp["templates"].setdefault(template_key(as_record(payload)), []).append(item["id"])
            fp["families"].setdefault(family_key(payload), []).append(item["id"])

    for name, listing in SETS.items():
        for entry in json.loads(listing.read_text(encoding="utf-8"))["items"]:
            add(name, items_of(entry["path"])[entry["id"]])
    for item in EV.load_gold(VENDOR)["items"]:
        add("vendor100", item)
    vendor_q = {i["id"]: question_key(i["question"]) for i in EV.load_gold(VENDOR)["items"]}
    return out, vendor_q


def grams(text):
    return {text[i:i + NGRAM] for i in range(max(len(text) - NGRAM + 1, 1))}


def main():
    prompt_hash = check_expected_prompt()
    document = yaml.safe_load((HERE / "candidates_draft.yaml").read_text(encoding="utf-8"))
    guard = Protection.current(GOLD_DIR)
    ext_templates, ext_families = extended_fingerprints()
    sets, vendor_q = set_fingerprints()
    vendor_g = {k: grams(v) for k, v in vendor_q.items()}
    train = read_jsonl(GOLD_DIR / "sft_train.jsonl")
    train_q = {question_key(r["messages"][1]["content"]) for r in train}
    train_f = {family_key(json.loads(r["messages"][-1]["content"].split("</think>")[-1])) for r in train}
    train_t = {template_key({"messages": [*r["messages"][:-1], {**r["messages"][-1],
                                                                 "content": r["messages"][-1]["content"].split("</think>")[-1].strip()}]})
               for r in train}
    rows, excluded, ngram_all = [], [], []
    seen_q = {}
    for item in document["candidates"]:
        gold = item["gold"]
        check_shape(gold)
        target = serialize_planner_target(gold)
        payload = json.loads(target)
        raw = assess(payload, item["question"], normalize=False)
        normalized = assess(payload, item["question"], normalize=True)
        t2pc = assess_t2pc(payload, item["question"])
        t2pc.pop("signature", None)
        reasons = guard.reasons(item["question"], payload, [item["id"], item["intent"], item["family"]])
        tk, fk, qk = template_key(as_record(payload)), family_key(payload), question_key(item["question"])
        extended = {"template": sorted(ext_templates.get(tk, ())), "family": sorted(ext_families.get(fk, ()))}
        per_set = {name: {"question": fp["questions"].get(qk), "template": fp["templates"].get(tk, []),
                          "family": fp["families"].get(fk, [])} for name, fp in sets.items()}
        g = grams(qk)
        sims = sorted(((len(g & vg) / len(g | vg), vid) for vid, vg in vendor_g.items()), reverse=True)
        top = [{"vendor_id": vid, "jaccard": round(s, 3)} for s, vid in sims[:3]]
        ngram_all.append({"id": item["id"], "max_jaccard": top[0]["jaccard"], "nearest_vendor_id": top[0]["vendor_id"]})
        duplicate = seen_q.get(qk)
        seen_q.setdefault(qk, item["id"])
        row = {**{k: item[k] for k in ("id", "type", "family", "intent", "variant", "question", "rationale")},
               "draft_grounding": payload, "draft_target": target,
               "results": {"normalize_false": raw, "normalize_true": normalized, "t2pc": t2pc},
               "contract_ok": {"thor_normalize_false": chosen_ok(raw), "thor_normalize_true": chosen_ok(normalized),
                               "t2pc": t2pc_chosen_ok(t2pc)},
               "compile_ok": t2pc.get("compile_ok"),
               "leakage": {"thor_policy_reasons": reasons, "extended_overlap": extended,
                           "per_set": {n: {k: v for k, v in s.items() if v} for n, s in per_set.items()},
                           "vendor100_char3_jaccard_top": top},
               "overlap_training_info": {"question": qk in train_q, "family": fk in train_f, "template": tk in train_t},
               "template_key": tk, "family_key": fk}
        why = list(reasons) + [f"extended_{k}" for k, v in extended.items() if v]
        why += [f"{n}_{k}" for n, s in per_set.items() for k, v in s.items() if v]
        if top[0]["jaccard"] >= EXCLUDE_AT:
            why.append(f"vendor100_char3_jaccard>={EXCLUDE_AT}")
        if duplicate:
            why.append(f"duplicate_of:{duplicate}")
        if why:
            excluded.append({"id": item["id"], "family": item["family"], "variant": item["variant"], "reasons": why,
                             "extended_sources": extended, "vendor100_char3_jaccard_top": top})
        else:
            rows.append(row)
    summary = {
        "prompt_hash": prompt_hash, "reference_date": document["reference_date"], "gold_dir": str(GOLD_DIR.relative_to(ROOT)),
        "protection_sources": len(guard.paths), "drafted": len(document["candidates"]), "kept": len(rows),
        "excluded": len(excluded),
        "kept_by_variant": dict(Counter(r["variant"] for r in rows)),
        "excluded_by_reason": dict(Counter(reason for e in excluded for reason in e["reasons"])),
        "set_items_checked": {n: fp["items"] for n, fp in sets.items()},
        "vendor100_ngram": {"n": NGRAM, "exclude_at": EXCLUDE_AT, "info_at": INFO_AT,
                            "max": max(x["max_jaccard"] for x in ngram_all),
                            "at_or_above_info": [x for x in ngram_all if x["max_jaccard"] >= INFO_AT]},
        "kept_families": len({r["family"] for r in rows}), "kept_semantic_families(family_key)": len({r["family_key"] for r in rows}),
        "contract_failures": [r["id"] for r in rows if not all(r["contract_ok"].values())],
        "t2pc_outcomes": dict(Counter(f"{r['results']['t2pc'].get('outcome')}:{r['results']['t2pc'].get('error_code')}"
                                      for r in rows)),
        "compile_stops": {r["id"]: r["results"]["t2pc"].get("compile_error_code") for r in rows if r["compile_ok"] is False},
        "condition_layer_changed_meaning": [r["id"] for r in rows if r["results"]["t2pc"]["condition_changed_meaning"]],
        "overlap_training_info": {k: sum(r["overlap_training_info"][k] for r in rows) for k in ("question", "family", "template")},
    }
    (HERE / "candidates_checked.json").write_text(json.dumps({"summary": summary, "candidates": rows},
                                                             ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (HERE / "excluded.json").write_text(json.dumps(excluded, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
