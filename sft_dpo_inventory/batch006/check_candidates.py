# -*- coding: utf-8 -*-
"""batch006(P0 SFT 보강) 후보 자동 검사(모델 호출 없음). 승인하지 않는다(결정 45).

    /data/hwkim/path_repeat_001/venv/py/bin/python sft_dpo_inventory/batch006/check_candidates.py
    /data/hwkim/path_repeat_001/venv/py/bin/python sft_dpo_inventory/batch006/check_candidates.py --source approved.jsonl

`--source approved.jsonl`(검토 뒤, apply_review.py 출력)이면 같은 검사를 승인·수정 문장에 다시 돌려
approved_checks.jsonl, overlap_report_approved.json으로 쓴다(초안 결과 파일은 그대로 둔다).

입력: candidates_draft.yaml(이 디렉터리). 출력(evaluation/partial_grounding/sft_p0/): augmentation_candidates.jsonl(후보마다 결과·상태), overlap_report.json.

검사(batch005 `build_candidates.py`와 같은 것 + P0):
1. 형식: thor `check_shape`, `serialize_planner_target`(학습 직렬화).
2. Full 계약: thor `assess`(normalize False/True), `assess_t2pc`(조건 계층·compose·validate·compile, 기준일 2026-09-25).
3. mock 운영 경로 실행(재질의 없이): outcome, Tool 호출. mock 데이터가 없는 조합은 실패가 아니라 표시(mock_note)로 남긴다.
4. P0 변환 불변식(`../build_targets.convert`): 실행 결과·operator·의미 서명(EVENT 제외)·평가 비교 정규형이 Full과 같음.
5. 겹침(겹치면 뺀다):
   - thor `Protection.current(reviewed_gold_v005_t2pc)`(보호 원본 전체): 정규화 질문, id, semantic template, semantic family.
   - 확장 겹침(batch004 `extended_fingerprints`): vendor 형식 보호 셋 정답의 template·family.
   - 평가 셋 명시 대조(vendor100, valid98, sel154, aux_test_v1): pilot_002 검사기 키(질문·id·template·family).
   - 보수 규칙(이번에 추가): 한 장소 od_role=both는 평가 gold의 "같은 장소 pickup·dropoff 두 개"와 뜻이 같으므로(결정 47)
     두 장소로 펼친 payload의 template·family도 같은 보호 집합에 대조한다.
   - 후보끼리 질문 중복.
6. 학습(v005)과의 겹침은 정보로만 남긴다.
"""
import argparse
import copy
import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
#: 초안(yaml)은 evaluation/** 밖에 둔다. evaluation/**/*.yaml은 보호 원본이라 초안이 자기 자신과 겹친 것으로 잡힌다.
SFT = ROOT / "evaluation/partial_grounding/sft_p0"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory"))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/batch004"))
sys.path.insert(0, str(SFT))
sys.path.insert(0, str(ROOT / "evaluation/partial_grounding/resident_isolation"))

from build_candidates import extended_fingerprints  # noqa: E402  (batch004)
from training.annotations.inventory import Protection, as_record, family_key  # noqa: E402
from training.data.canonicalize import check_shape, serialize_planner_target  # noqa: E402
from training.data.common import read_jsonl  # noqa: E402
from training.data.split import question_key, template_key  # noqa: E402
from training.data.validation import assess, assess_t2pc, chosen_ok, t2pc_chosen_ok  # noqa: E402

import build_targets as BT  # noqa: E402
import build_items as BI  # noqa: E402  (mock 운영 경로 실행)
import evaluate_vendor100 as EV  # noqa: E402

spec = importlib.util.spec_from_file_location("check_overlap", ROOT / "sft_dpo_inventory/pilot_002/data/check_overlap.py")
CO = importlib.util.module_from_spec(spec)
spec.loader.exec_module(CO)

GOLD_DIR = ROOT / "training/generated/reviewed_gold_v005_t2pc"
EVAL_FILES = {
    "vendor100": ROOT / "evaluation/vendor100/gold.yaml",
    "valid98": ROOT / "sft_dpo_inventory/pilot_001_analysis/decision43/valid98_gold.yaml",
    "sel154": ROOT / "evaluation/partial_grounding/ab_p0_3/sel154_gold.yaml",
}
AUX = ROOT / "sft_dpo_inventory/pilot_prep_005/sets/aux_test_items.json"


def expand_both(payload):
    """한 장소 od_role=both를 같은 장소 pickup·dropoff 두 개로 펼친다(보수적 겹침 대조용). 없으면 None."""
    out, changed = copy.deepcopy(payload), False
    concepts = []
    for c in out["concepts"]:
        if (c.get("attributes") or {}).get("od_role") == "both":
            changed = True
            for role in ("pickup", "dropoff"):
                d = copy.deepcopy(c)
                d["id"] = f"{c['id']}_{role}"
                d["attributes"] = {**c["attributes"], "od_role": role}
                concepts.append(d)
        else:
            concepts.append(c)
    out["concepts"] = concepts
    return out if changed else None


def eval_index():
    index = {}
    for name, path in EVAL_FILES.items():
        index[name] = [(i["id"], i) for i in EV.load_gold(path)["items"]]
    spec_items = json.loads(AUX.read_text(encoding="utf-8"))["items"]
    docs, items = {}, []
    for ref in spec_items:
        if ref["path"] not in docs:
            docs[ref["path"]] = {str(i["id"]): i for i in EV.load_gold(ROOT / ref["path"])["items"]}
        items.append((f"{ref['set']}/{ref['id']}", docs[ref["path"]][str(ref["id"])]))
    index["aux_test_v1"] = items
    keys = {}
    for name, items in index.items():
        k = {"question": set(), "id": set(), "template": set(), "family": set()}
        for eid, item in items:
            payload = EV.gold_grounding(item)
            kk = CO.keys(str(eid).split("/")[-1], item["question"], payload) if payload is not None else \
                {"question": CO.question_key(item["question"]), "id": str(eid).split("/")[-1]}
            for kind in k:
                if kind in kk:
                    k[kind].add(kk[kind])
        keys[name] = k
    return keys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default="candidates_draft.yaml")
    a = ap.parse_args()
    if a.source.endswith(".jsonl"):
        document = {"candidates": read_jsonl(HERE / a.source)}
        out_rows, out_report = "approved_checks.jsonl", "overlap_report_approved.json"
    else:
        document = yaml.safe_load((HERE / a.source).read_text(encoding="utf-8"))
        out_rows, out_report = "augmentation_candidates.jsonl", "overlap_report.json"
    guard = Protection.current(GOLD_DIR)
    ext_templates, ext_families = extended_fingerprints()
    evk = eval_index()
    train = read_jsonl(GOLD_DIR / "sft_train.jsonl")
    train_q = {question_key(r["messages"][1]["content"]) for r in train}
    train_f = {family_key(json.loads(r["messages"][-1]["content"])) for r in train}
    rows, seen_q = [], {}
    for item in document["candidates"]:
        gold = item["gold"]
        check_shape(gold)
        target = serialize_planner_target(gold)
        payload = json.loads(target)
        q = item["question"]
        raw = assess(payload, q, normalize=False)
        normalized = assess(payload, q, normalize=True)
        t2pc = assess_t2pc(payload, q)
        t2pc.pop("signature", None)
        observed = BI.observe(q, payload)
        mock = ({"outcome": observed["outcome"], "error_code": observed.get("error_code"),
                 "calls": [{"tool": c["tool"], "args": c["args"]} for c in observed["calls"]]}
                if observed else {"outcome": "repair_requested"})
        p0, conv = BT.convert(q, payload)
        reasons = list(guard.reasons(q, payload, [item["id"], item.get("pair") or item["id"]]))
        tk, fk = template_key(as_record(payload)), family_key(payload)
        extended = {"template": sorted(ext_templates.get(tk, ())), "family": sorted(ext_families.get(fk, ()))}
        expanded = expand_both(payload)
        alt = None
        if expanded is not None:
            atk, afk = template_key(as_record(expanded)), family_key(expanded)
            alt = {"template": atk, "family": afk}
            if atk in guard.templates or atk in ext_templates:
                reasons.append("both_expanded_template")
            if afk in guard.families or afk in ext_families:
                reasons.append("both_expanded_family")
        qk = question_key(q)
        eval_hits = {}
        for name, k in evk.items():
            hit = [kind for kind, value in (("question", qk), ("id", item["id"]), ("template", tk), ("family", fk))
                   if value in k[kind]]
            if alt:
                hit += [f"both_expanded_{kind}" for kind in ("template", "family") if alt[kind] in k[kind]]
            if hit:
                eval_hits[name] = hit
        duplicate = seen_q.get(qk)
        seen_q.setdefault(qk, item["id"])
        contract = {"thor_normalize_false": chosen_ok(raw), "thor_normalize_true": chosen_ok(normalized),
                    "t2pc": t2pc_chosen_ok(t2pc), "compile": t2pc.get("compile_ok") is True,
                    "p0_invariants": conv["auto_pass"]}
        # mock 실행기에 그 조합의 응답 데이터가 없는 것(UNSUPPORTED_COMBINATION 등)은 계약 실패가 아니다(결정 7과 같은 취지).
        # 계약(T2PC·compile)을 통과하면 표시만 하고 사람 검토에서 본다.
        mock_note = None if mock["outcome"] == "answered" else f"mock:{mock.get('outcome')}:{mock.get('error_code')}"
        why_excluded = (reasons + [f"extended_{k}" for k, v in extended.items() if v]
                        + [f"eval:{n}:{','.join(h)}" for n, h in eval_hits.items()]
                        + ([f"duplicate_of:{duplicate}"] if duplicate else []))
        contract_fail = [k for k, v in contract.items() if not v]
        status = ("excluded_overlap" if why_excluded else "contract_fail" if contract_fail else "auto_ok")
        rows.append({
            "id": item["id"], "gap": item["gap"], "pair": item["pair"], "question": q, "rationale": item["rationale"],
            "status": status, "excluded_reasons": why_excluded, "contract_fail": contract_fail,
            "full_target": payload, "p0_target": p0, "contract": contract, "compile_ok": t2pc.get("compile_ok"),
            "t2pc": {k: t2pc.get(k) for k in ("outcome", "error_code", "validation_codes", "operators", "compile_ok",
                                               "compile_error_code", "condition_changed_meaning")},
            "mock": mock, "mock_note": mock_note, "p0_problems": conv["problems"],
            "keys": {"template": tk, "family": fk, "both_expanded": alt},
            "overlap_training_info": {"question": qk in train_q, "family": fk in train_f},
            "review": ({"status": "pending", "reviewer": None} if "review_decision" not in item else
                       {"status": item["review_decision"], "edited": item["edited"], "original": item["original"]}),
            **({"provenance": item["provenance"], "pair_draft": item["pair_draft"]} if "provenance" in item else {}),
        })
    with open(SFT / out_rows, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    report = {
        "protection_sources": len(guard.paths), "drafted": len(rows),
        "status": dict(Counter(r["status"] for r in rows)),
        "source": a.source,
        "by_gap": {g: dict(Counter(r["status"] for r in rows if r["gap"] == g)) for g in ("A", "B", "C")},
        "excluded_by_reason": dict(Counter(x.split(":")[0] if x.startswith(("eval", "duplicate")) else x
                                           for r in rows for x in r["excluded_reasons"])),
        "eval_overlap_by_set": dict(Counter(x.split(":")[1] for r in rows for x in r["excluded_reasons"]
                                            if x.startswith("eval:"))),
        "excluded_items": {r["id"]: r["excluded_reasons"] for r in rows if r["excluded_reasons"]},
        "contract_fail_items": {r["id"]: r["contract_fail"] for r in rows if r["contract_fail"]},
        "mock_notes": {r["id"]: r["mock_note"] for r in rows if r["mock_note"]},
        "training_overlap_info": {"question": sum(r["overlap_training_info"]["question"] for r in rows),
                                  "family": sum(r["overlap_training_info"]["family"] for r in rows)},
    }
    (SFT / out_report).write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("drafted", "status", "by_gap", "excluded_by_reason", "eval_overlap_by_set",
                                             "contract_fail_items", "mock_notes")}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
