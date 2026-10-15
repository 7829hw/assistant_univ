# -*- coding: utf-8 -*-
"""300문항 v2의 현재 코드 결과(W6 2)와 저장소 겹침 재검사(W6 3). 모델 호출 없음, 승인 아님, 상태를 바꾸지 않는다.

    hfvenv/bin/python sft_dpo_inventory/pilot_006_prep/aug300/check_aug300.py [--pg-dir DIR]

1. 현재 코드(W6 2): 300문항 모두 정답 호출의 schema 검사(``build()`` tool schema, ``evaluate_vendor100 extract``와 같은 검사), 정답 호출 역산 grounding
   → ``_GoldPlanner`` pipeline(compose → validate → compile → mock execute) → 업체 100 채점(``score``)으로 정답 호출과 같은 실행인지 본다.
   ``cmd_gold``와 같은 경로다. 수정 4가지(130·305·306 질문·정답, SCOPE_NAME 난이도 30건)는 따로 표시한다.
2. 겹침 재검사(W6 3, batch007 ``build_candidates.py``와 같은 도구):
   - thor leakage: ``Protection.current(reviewed_gold_v006_t2pc)``의 정규화 질문, id, semantic template, semantic family.
   - 확장 겹침: vendor 형식 보호 셋(업체 100 포함)의 정답 역산 template·family(``batch004/build_candidates.extended_fingerprints``).
   - 셋별: selection_v1, selection_v2, valid98, aux_test_v1, 업체 100, batch007(초안 27), 학습 데이터(``reviewed_gold_v006_t2pc``,
     ``thinking_pilot004_t2pc``), pg 데이터(partial-grounding ``ab9d215``의 ``batch006/approved.jsonl``, ``reviewed_reasoning_v001``,
     ``reviewed_gold_v006_p0``; ``--pg-dir``에 ``git show``로 꺼낸 파일). 셋마다 정규화 질문, 문자 3-gram Jaccard, 같은 정답 grounding
     (``_grounding_view`` 일치), template, family.
3. 판정 기준(결과를 보기 전에 정함):
   - **강한 겹침**: 정규화 질문 일치, thor ``protected_question``·``protected_parent_or_family``, 문자 3-gram Jaccard ≥ 0.5,
     같은 정답 grounding. xlsx 기준(업체 100 동일 정답 또는 Jaccard ≥ 0.5 → 보류, 다른 보호 셋 Jaccard ≥ 0.5 → 제외)을 모든 대상 셋으로 넓힌 것이다.
   - **약한 겹침**: template·family. 같은 tool 공간에서 피할 수 없으므로 기록만 한다(계획서 v2 6.2절, 결정 54).
   - xlsx 상태가 이미 설명하는 겹침(보류_vendor100의 업체 100 겹침, 제외의 보호 셋 Jaccard ≥ 0.5, 축소)은 "알려진 겹침"이다.
     그 밖의 강한 겹침은 "새 겹침"이고 ``status_proposals.json``에 제안으로만 남긴다(상태는 바꾸지 않는다).
   - **holdout 고정(W6 5)은 holdout 문항에 새 강한 겹침이 0일 때만** 한다. holdout의 약한 겹침은 수만 보고한다.
출력: ``check_results.json``(문항별), ``status_proposals.json``(새 겹침 제안), 표준 출력에 요약.
"""
import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/batch004"))

from build_candidates import extended_fingerprints  # noqa: E402
from training.annotations.inventory import Protection, as_record, family_key  # noqa: E402
from training.data.common import read_jsonl  # noqa: E402
from training.data.split import question_key, template_key  # noqa: E402

GOLD_DIR = ROOT / "training/generated/reviewed_gold_v006_t2pc"
P004_DIR = ROOT / "training/generated/thinking_pilot004_t2pc"
SETS = {
    "selection_v1": ROOT / "sft_dpo_inventory/pilot_prep_005/sets/selection_items.json",
    "selection_v2": ROOT / "sft_dpo_inventory/calibration_001/selection_v2_items.json",
    "aux_test_v1": ROOT / "sft_dpo_inventory/pilot_prep_005/sets/aux_test_items.json",
    "valid98": ROOT / "sft_dpo_inventory/pilot_001/valid98/valid98_items.json",
}
PROTECTED = ("selection_v1", "selection_v2", "aux_test_v1", "valid98", "vendor100")
VENDOR = ROOT / "evaluation/vendor100/gold.yaml"
BATCH007 = ROOT / "sft_dpo_inventory/batch007/candidates_checked.json"
PG_FILES = {
    "pg_batch006": "sft_dpo_inventory_batch006_approved.jsonl",
    "pg_reviewed_reasoning_v001": "sft_dpo_inventory_reviewed_reasoning_v001_dataset.jsonl",
    "pg_reviewed_gold_v006_p0": "training_generated_reviewed_gold_v006_p0_sft_train.jsonl",
}
NGRAM, STRONG_AT = 3, 0.5
EDITED_GOLD = {"aug300-130", "aug300-305", "aug300-306"}


def grams(text):
    return {text[i:i + NGRAM] for i in range(max(len(text) - NGRAM + 1, 1))}


def _payload_from_target(content):
    text = content.split("</think>")[-1].strip()
    match = re.search(r"\{.*\}", text, re.S)
    return json.loads(match.group(0)) if match else None


def load_targets(pg_dir):
    """{set: [(id, question, payload or None)]}"""
    import evaluate_vendor100 as EV
    cache, out = {}, defaultdict(list)

    def items_of(path):
        if path not in cache:
            cache[path] = {i["id"]: i for i in EV.load_gold(ROOT / path)["items"]}
        return cache[path]

    def payload_of(item):
        try:
            return EV.gold_grounding(item)
        except Exception:  # noqa: BLE001 - 정답 호출이 없는 문항
            return None

    for name, listing in SETS.items():
        for entry in json.loads(listing.read_text(encoding="utf-8"))["items"]:
            item = items_of(entry["path"])[entry["id"]]
            out[name].append((f"{entry.get('set', '')}/{item['id']}".lstrip("/"), item["question"], payload_of(item)))
    for item in EV.load_gold(VENDOR)["items"]:
        out["vendor100"].append((item["id"], item["question"], payload_of(item)))
    for row in json.loads(BATCH007.read_text(encoding="utf-8"))["candidates"]:
        out["batch007"].append((row["id"], row["question"], row["draft_grounding"]))
    for name, directory in (("train_v006_t2pc", GOLD_DIR), ("train_thinking_pilot004_t2pc", P004_DIR)):
        for path in sorted(directory.glob("sft_*.jsonl")):
            for i, row in enumerate(read_jsonl(path)):
                question = next(m["content"] for m in row["messages"] if m["role"] == "user")
                rid = (row.get("metadata") or {}).get("source_record_id") or f"{path.stem}#{i}"
                out[name].append((rid, question, _payload_from_target(row["messages"][-1]["content"])))
    if pg_dir:
        for name, fname in PG_FILES.items():
            for i, row in enumerate(read_jsonl(Path(pg_dir) / fname)):
                if "messages" in row:
                    question = next(m["content"] for m in row["messages"] if m["role"] == "user")
                    meta = row.get("metadata") or {}
                    rid, payload = meta.get("source_record_id") or f"#{i}", meta.get("target_full")
                else:
                    question, rid = row["question"], row["id"]
                    gold = row["gold"]
                    payload = gold if isinstance(gold, dict) else None
                out[name].append((rid, question, payload))
    return out


def main():
    import evaluate_vendor100 as EV
    from jsonschema import Draft202012Validator

    from build import build

    parser = argparse.ArgumentParser()
    parser.add_argument("--pg-dir", default=None, help="partial-grounding ab9d215에서 git show로 꺼낸 파일 위치")
    args = parser.parse_args()
    items = read_jsonl(HERE / "augmentation_300.jsonl")
    tools, _ = build()
    schemas = {t["function"]["name"]: t["function"]["parameters"] for t in tools}

    # 1. 현재 코드
    code = {}
    for item in items:
        schema_errors = []
        for index, call in enumerate(item["gold"]):
            schema = schemas.get(call["tool"])
            if schema is None:
                schema_errors.append(f"unknown_tool {call['tool']}")
                continue
            concrete = {k: ("scope:district:0000000000" if isinstance(v, str) and EV._BINDING.match(v) else v)
                        for k, v in call["args"].items()}
            schema_errors += [f"{call['tool']}[{index}]: {e.message}" for e in Draft202012Validator(schema).iter_errors(concrete)]
        try:
            payload = EV.derive_grounding(item["gold"])
            observed = EV.run_item(EV._pipeline(EV._GoldPlanner(payload)), item["question"])
        except Exception as error:  # noqa: BLE001 - 기록하고 계속
            payload, observed = None, EV._crashed(error)
        gold_item = {"id": item["id"], "question": item["question"], "gold": item["gold"], "expected_outcome": "answered",
                     "vendor_verdict": "-"}
        category, checks = EV.score(gold_item, observed)
        code[item["id"]] = {"schema_errors": schema_errors, "derived_grounding": payload, "outcome": observed["outcome"],
                            "error_code": observed["error_code"], "category": category,
                            "compile_ok": observed["outcome"] == "answered" and bool(observed["calls"]),
                            "calls": [{"tool": c["tool"], "args": c["args"]} for c in observed["calls"]],
                            "mock_result_present": all(c.get("result") is not None for c in observed["calls"])}

    # 2. 겹침
    guard = Protection.current(GOLD_DIR)
    ext_templates, ext_families = extended_fingerprints()
    targets = load_targets(args.pg_dir)
    index = {}
    for name, rows in targets.items():
        idx = {"q": defaultdict(list), "g": [], "view": defaultdict(list), "t": defaultdict(list), "f": defaultdict(list)}
        for rid, question, payload in rows:
            qk = question_key(question)
            idx["q"][qk].append(rid)
            idx["g"].append((rid, grams(qk)))
            if payload:
                try:
                    view = json.dumps(EV._grounding_view(payload), ensure_ascii=False, sort_keys=True, default=str)
                    idx["view"][view].append(rid)
                    idx["t"][template_key(as_record(payload))].append(rid)
                    idx["f"][family_key(payload)].append(rid)
                except Exception:  # noqa: BLE001 - 해석할 수 없는 payload는 질문 키만 쓴다
                    pass
        index[name] = idx
    results, proposals = [], []
    for item in items:
        payload = code[item["id"]]["derived_grounding"]
        qk = question_key(item["question"])
        g = grams(qk)
        tk = template_key(as_record(payload)) if payload else None
        fk = family_key(payload) if payload else None
        view = json.dumps(EV._grounding_view(payload), ensure_ascii=False, sort_keys=True, default=str) if payload else None
        thor = guard.reasons(item["question"], payload, [item["id"]])
        per_set = {}
        for name, idx in index.items():
            best = max(((len(g & vg) / len(g | vg), rid) for rid, vg in idx["g"]), default=(0.0, None))
            entry = {"question": idx["q"].get(qk, []), "jaccard_max": round(best[0], 3), "jaccard_nearest": best[1],
                     "same_grounding": idx["view"].get(view, []) if view else [],
                     "template": len(idx["t"].get(tk, [])) if tk else 0, "family": len(idx["f"].get(fk, [])) if fk else 0}
            per_set[name] = entry
        strong = []
        for name, e in per_set.items():
            if e["question"]:
                strong.append(f"{name}:question")
            if e["jaccard_max"] >= STRONG_AT:
                strong.append(f"{name}:jaccard>={STRONG_AT}({e['jaccard_nearest']},{e['jaccard_max']})")
            if e["same_grounding"]:
                strong.append(f"{name}:same_grounding({','.join(map(str, e['same_grounding'][:3]))})")
        strong += [f"thor:{r}" for r in thor if r in ("protected_question", "protected_parent_or_family")]
        weak = [f"thor:{r}" for r in thor if r not in ("protected_question", "protected_parent_or_family")]
        weak += [f"extended_{k}" for k, v in (("template", ext_templates.get(tk)), ("family", ext_families.get(fk))) if v]
        weak += [f"{n}:{k}" for n, e in per_set.items() for k in ("template", "family") if e[k]]
        status = item["status_v2"]

        def known(hit):
            if status == "보류_vendor100" and hit.startswith("vendor100:"):
                return True
            if status == "제외" and hit.split(":")[0] in PROTECTED and "jaccard" in hit:
                return True
            if status == "축소":
                return True
            # 보호 원본(Protection)은 evaluation/**/*.yaml을 포함하므로 업체 100 문항과의 질문 일치도 thor로 잡힌다.
            if status == "보류_vendor100" and hit.startswith("thor:") and per_set["vendor100"]["question"]:
                return True
            return False

        new_strong = [h for h in strong if not known(h)]
        results.append({"id": item["id"], "status_v2": status, "status": item["status"], "family_id": item["family_id"],
                        "code": {k: v for k, v in code[item["id"]].items() if k != "derived_grounding"},
                        "strong_overlap": strong, "new_strong_overlap": new_strong, "weak_overlap": weak,
                        "per_set": per_set, "template_key": tk, "family_key": fk})
        code_fail = code[item["id"]]["category"] != "match" or bool(code[item["id"]]["schema_errors"])
        if new_strong or code_fail:
            proposals.append({"id": item["id"], "status_v2": status, "status_d1": item["status"], "new_strong_overlap": new_strong,
                              "current_code": None if not code_fail else [code[item["id"]]["category"], code[item["id"]]["error_code"],
                                                                         code[item["id"]]["schema_errors"]],
                              "proposal": "사람 검토: 제외 또는 보류 여부(상태는 바꾸지 않았다)" if new_strong else
                                          "사람 검토: 현재 코드에서 정답 호출이 실행되지 않음. 학습에서 뺄지, 정답을 고칠지(상태는 바꾸지 않았다)"})
    by_status = defaultdict(Counter)
    for r in results:
        by_status[r["status"]]["items"] += 1
        by_status[r["status"]]["new_strong"] += bool(r["new_strong_overlap"])
        by_status[r["status"]]["weak_any"] += bool(r["weak_overlap"])
        for h in r["weak_overlap"]:
            by_status[r["status"]][f"weak:{h}"] += 1
    holdout_weak_train = Counter()
    for r in results:
        if r["status"] == "holdout":
            for name in ("train_v006_t2pc", "train_thinking_pilot004_t2pc", *PG_FILES):
                if name in r["per_set"] and r["per_set"][name]["family"]:
                    holdout_weak_train[name] += 1
    summary = {
        "items": len(results), "pg_dir_used": bool(args.pg_dir),
        "target_sets": {n: len(rows) for n, rows in targets.items()},
        "protection_sources": len(guard.paths),
        "code": {"schema_error_items": [r["id"] for r in results if r["code"]["schema_errors"]],
                 "category": dict(Counter(r["code"]["category"] for r in results)),
                 "outcome": dict(Counter(f"{r['code']['outcome']}:{r['code']['error_code']}" for r in results)),
                 "not_match": {r["id"]: [r["code"]["category"], r["code"]["error_code"]] for r in results
                               if r["code"]["category"] != "match"},
                 "edited_gold(130,305,306)": {i: code[i]["category"] for i in sorted(EDITED_GOLD)},
                 "scope_name_difficulty_edited": dict(Counter(code[it["id"]]["category"] for it in items
                                                              if "난이도" in it["v2_cell_comments"]))},
        "proposals": len(proposals), "overlap": {"new_strong_items": sum(bool(p["new_strong_overlap"]) for p in proposals),
                    "new_strong_by_status": {s: c["new_strong"] for s, c in by_status.items()},
                    "holdout_new_strong": [p["id"] for p in proposals if p["status_d1"] == "holdout" and p["new_strong_overlap"]],
                    "weak_by_status": {s: {k: v for k, v in c.items() if k.startswith("weak")} for s, c in by_status.items()},
                    "holdout_family_overlap_with_training(info)": dict(holdout_weak_train)},
    }
    (HERE / "check_results.json").write_text(json.dumps({"summary": summary, "items": results}, ensure_ascii=False, indent=1) + "\n",
                                             encoding="utf-8")
    (HERE / "status_proposals.json").write_text(json.dumps({"criteria": "check_aug300.py docstring 3", "pg_dir_used": bool(args.pg_dir),
                                                            "proposals": proposals}, ensure_ascii=False, indent=1) + "\n",
                                                encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
