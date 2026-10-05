# -*- coding: utf-8 -*-
"""정책 대안(개발 셋 일부를 family 단위로 학습에 쓰기)의 규모 계산. 파일을 옮기거나 학습 자료를 만들지 않는다.

    python sft_dpo_inventory/policy_scale.py

셋마다 센다(산출물에 질문 문장은 넣지 않는다):
- 문항 수, 앞 셋과 정규화 질문이 같은 중복 수(thor ``question_key``와 같은 정규화: NFKC, 공백·문장부호 제거, casefold).
- family 수: vendor 형식 셋은 id 줄기(c08a·c08b → c08)와 ``contrast`` 값을 잇는 묶음, paraphrase corpus는 intent.
  참고로 정답 grounding의 거친 의미 family(측정값·OD·집계/그룹 factor; thor ``family_key``와 같은 기준) 수도 센다.
- 학습 target 후보: 정답 grounding(``gold_grounding`` 또는 정답 호출 역산)이 있고, 현재 계약의 parse → compose → validate
  (normalize=False) 결과가 기대 결과와 맞는 문항. 기대가 답이면 통과, 기대가 거부·확인 요청이면 계약 오류로 멈춤(기대 오류 코드가
  있으면 그 코드)이어야 한다. T2PC 계약에서는 멈추는 문항도 grounding이 target이다.
- family 보호 대조: 학습으로 보낼 셋의 target이 평가로 남는 셋(업체 100 포함)과 거친 의미 family가 같은지 센다.
- 정책·모호 라벨 제외: grounding_v13 dev_report.json ``policy_ambiguous``, label_audit.json(policy_ambiguous·ambiguous·
  questionable), evaluation/real_data/decisions.md D1–D4에 예시로 걸린 문항.
registry의 structured_grounding·reference·retrieval·stub_v2 셋은 라벨 형식이 달라 문항·family 수만 센다.
"""
import copy
import json
import re
import unicodedata
from collections import Counter, defaultdict

import yaml

from _common import ROOT, write_output

import evaluate_vendor100 as EV
import paraphrase_corpus as P
from check_reviewed_gold import assess

#: (이름, 파일, grounding_v13 비교 셋 이름 또는 None, 작성 주체)
VENDOR_FORMAT_SETS = [
    ("vendor100", "evaluation/vendor100/gold.yaml", "dev", "업체 작성(보호 대상)"),
    ("old44", "evaluation/grounding_v1/holdout_questions.yaml", "old44", "Claude 작성, 사람 검토 없음"),
    ("contrast", "evaluation/grounding_v2/contrast_questions.yaml", "contrast", "Claude 작성"),
    ("indepv2", "evaluation/grounding_v2/independent_questions.yaml", "indepv2", "Claude 작성"),
    ("indepv3", "evaluation/grounding_v2/independent_v3_questions.yaml", "indepv3", "Claude 작성"),
    ("indepv4", "evaluation/grounding_v3/independent_v4_questions.yaml", "indepv4", "Claude 작성"),
    ("at", "evaluation/grounding_v4/answer_target_questions.yaml", "at", "Claude 작성"),
    ("stage_v7", "evaluation/grounding_v7/stage_contrast_questions.yaml", None, "Claude 작성"),
    ("heldout_v8", "evaluation/grounding_v8/heldout_questions.yaml", None, "Claude 작성"),
    ("od_v8", "evaluation/grounding_v8/od_contrast_questions.yaml", "od", "Claude 작성"),
    ("heldout_v9", "evaluation/grounding_v9/heldout_questions.yaml", None, "Claude 작성"),
    ("heldout_v10", "evaluation/grounding_v10/heldout_questions.yaml", "heldout", "Claude 작성"),
    ("status_v10", "evaluation/grounding_v10/status_contrast_questions.yaml", "status", "Claude 작성"),
    ("measure_v12", "evaluation/grounding_v12/measure_contrast_questions.yaml", "measure", "Claude 작성"),
    ("final_v12", "evaluation/grounding_v12/final_questions.yaml", "final", "Claude 작성, 하위 에이전트 라벨 점검"),
    ("cli_check_v14", "evaluation/grounding_v14/cli_check_gold.yaml", None, "다른 셋 문항의 사본"),
]
DECISIONS_ITEMS = {"D1": ["measure/m05", "measure/m08", "final/f08"], "D2": ["final/f10"],
                   "D3": ["final/f16"], "D4": ["final/f28"]}


def question_key(question):
    return "".join(ch for ch in unicodedata.normalize("NFKC", question)
                   if not ch.isspace() and not unicodedata.category(ch).startswith("P")).casefold()


def coarse_family(payload):
    """thor training.annotations.inventory.family_key와 같은 기준(측정값·OD·집계/그룹 factor)."""
    if payload.get("unsupported"):
        return "unsupported"
    measures = sorted([c.get("concept"), c.get("subtype")] for c in payload.get("concepts") or []
                      if c.get("concept") in {"AMOUNT", "PROPORTION"})
    od = sorted((c.get("attributes") or {}).get("od_role", c.get("od_role", "")) or ""
                for c in payload.get("concepts") or [] if c.get("concept") == "LOCATION")
    factors = {k: v for k, v in (payload.get("factors") or {}).items()
               if k in {"aggregation", "rollup", "bucket", "answer", "dimension", "dimension_target", "order", "vicinity"}}
    if factors.get("answer") == "value":
        factors.pop("answer")
    return json.dumps([measures, [x for x in od if x], factors], ensure_ascii=False, sort_keys=True)


class Families:
    def __init__(self):
        self.parent = {}

    def find(self, x):
        self.parent.setdefault(x, x)
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a, b):
        self.parent[self.find(a)] = self.find(b)


def stem(item_id):
    match = re.fullmatch(r"([A-Za-z_]*\d+)[a-z]?", str(item_id))
    return match.group(1) if match else str(item_id)


def exclusion_keys():
    v13 = ROOT / "evaluation" / "grounding_v13"
    dev = json.loads((v13 / "runs" / "dev_report.json").read_text(encoding="utf-8"))
    audit = json.loads((v13 / "label_audit.json").read_text(encoding="utf-8"))
    reasons = defaultdict(set)
    for key in dev["policy_ambiguous"]:
        reasons[key].add("dev_report.policy_ambiguous")
    for name in ("policy_ambiguous", "ambiguous", "questionable"):
        for key in audit.get(name, []):
            reasons[key].add(f"label_audit.{name}")
    for decision, keys in DECISIONS_ITEMS.items():
        for key in keys:
            reasons[key].add(f"decisions.{decision}")
    return reasons


def main():
    excluded = exclusion_keys()
    seen = {}
    rows = []
    valid_targets = []
    for name, path, v13_name, author in VENDOR_FORMAT_SETS:
        items = EV.load_gold(ROOT / path)["items"]
        families = Families()
        counts = Counter()
        coarse = set()
        trainable_families = set()
        failures = Counter()
        for item in items:
            key = question_key(item["question"])
            if key in seen:
                counts["duplicate_of_earlier_set"] += 1
                continue
            seen[key] = name
            family_id = f"{name}:{stem(item['id'])}"
            families.find(family_id)
            if item.get("contrast"):
                families.union(family_id, f"{name}:contrast:{item['contrast']}")
            set_key = f"{v13_name}/{item['id']}" if v13_name else None
            if set_key in excluded:
                counts["policy_or_ambiguous"] += 1
                continue
            if item.get("expected_outcome", "answered") != "answered":
                counts["expected_not_answered"] += 1
            try:
                payload = EV.gold_grounding(item)
            except Exception:  # noqa: BLE001
                payload = None
            if not payload:
                counts["no_gold_grounding"] += 1
                continue
            result = assess(payload, item["question"], normalize=False)
            passed = result["outcome"] in ("answered", "unsupported")
            code = result.get("error_code") or ",".join(result["validation_codes"])
            expect_answer = item.get("expected_outcome", "answered") == "answered"
            # T2PC 계약: 표현할 수 있는 질문은 grounding을 적고, 실행 가능 여부는 코드가 정한다. 답이 아닌 기대 결과의
            # 문항은 정답 grounding이 계약 오류로 멈추는 것이 맞다(target으로 쓸 수 있음). 기대와 어긋나는 것만 무효로 센다.
            expected_errors = item.get("expected_error") or []
            expected_errors = [expected_errors] if isinstance(expected_errors, str) else list(expected_errors)
            # compile 단계 정지(UNVERIFIED_TIMS_CONTRACT)는 validate 뒤에 일어나므로 여기서는 통과가 기대와 맞다.
            compile_stop = not expect_answer and passed and "UNVERIFIED_TIMS_CONTRACT" in expected_errors
            if compile_stop:
                counts["target_valid_compile_stop"] += 1
            if compile_stop or (passed == expect_answer and (passed or not expected_errors
                                                             or code in expected_errors)):
                counts["target_valid"] += 1
                counts["target_valid_stop" if not passed else "target_valid_answer"] += 1
                coarse.add(coarse_family(payload))
                valid_targets.append((name, coarse_family(payload)))
                trainable_families.add(families.find(family_id))
            else:
                counts["target_invalid"] += 1
                failures[f"expected={item.get('expected_outcome', 'answered')}"
                         f"/{item.get('expected_error') or '-'} got={code or 'ok'}"] += 1
        unique = len(items) - counts["duplicate_of_earlier_set"]
        rows.append({
            "set": name, "path": path, "v13_comparison_set": v13_name, "author": author,
            "items": len(items), "duplicates_of_earlier_set": counts["duplicate_of_earlier_set"],
            "unique_items": unique, "families": len({families.find(x) for x in list(families.parent)
                                                     if ":contrast:" not in x}),
            "policy_or_ambiguous_excluded": counts["policy_or_ambiguous"],
            "after_exclusion": unique - counts["policy_or_ambiguous"],
            "expected_not_answered": counts["expected_not_answered"],
            "no_gold_grounding": counts["no_gold_grounding"],
            "target_valid": counts["target_valid"], "target_valid_answer": counts["target_valid_answer"],
            "target_valid_stop": counts["target_valid_stop"],
            "target_valid_compile_stop(validate 통과, compile에서 정지 기대)": counts["target_valid_compile_stop"],
            "target_invalid": counts["target_invalid"],
            "target_invalid_codes": dict(failures),
            "families_with_valid_target": len(trainable_families),
            "coarse_semantic_families_of_valid_targets": len(coarse),
        })

    registry = yaml.safe_load((ROOT / "evaluation" / "corpus_registry.yaml").read_text(encoding="utf-8"))
    corpora = []
    for entry in registry["corpora"]:
        items = P.load_corpus_items(entry["path"])
        intents = P.load_corpus(entry["path"])
        golden = {i["intent"]: i.get("golden") for i in intents}
        dup = sum(1 for it in items if question_key(it["question"]) in seen)
        for it in items:
            seen.setdefault(question_key(it["question"]), entry["path"])
        unsupported = sum(1 for g in golden.values() if isinstance(g, dict) and g.get("unsupported"))
        valid = invalid = 0
        for intent, g in golden.items():
            if not isinstance(g, dict) or g.get("unsupported"):
                continue
            sample = next(it for it in items if it["intent_id"] == intent)
            document = copy.deepcopy(g)
            if "aggregation_plan" in (document.get("factors") or {}):
                invalid += 1   # structured 표기. flat 변환(thor to_flat)이 필요해 이번에 판정하지 않는다.
                continue
            result = assess(document, sample["question"], normalize=False)
            valid += result["outcome"] == "answered"
            invalid += result["outcome"] != "answered"
        corpora.append({"path": entry["path"], "role": entry["role"], "items": len(items),
                        "duplicates_of_earlier_set": dup, "intents(families)": len(intents),
                        "unsupported_intents": unsupported, "intent_golden_valid_flat": valid,
                        "intent_golden_invalid_or_structured": invalid})
    question_sets = []
    for entry in registry["question_sets"]:
        document = yaml.safe_load((ROOT / entry["path"]).read_text(encoding="utf-8"))
        items = (document.get("questions") or document.get("queries") or document.get("items") or []) \
            if isinstance(document, dict) else document
        question_sets.append({"path": entry["path"], "role": entry.get("role"), "items": len(items),
                              "families": len({i.get("family") or i.get("pair") or i.get("id")
                                               for i in items if isinstance(i, dict)})})

    def total(selected):
        picked = [r for r in rows if r["set"] in selected]
        return {k: sum(r[k] for r in picked) for k in ("unique_items", "families", "after_exclusion",
                                                        "target_valid", "families_with_valid_target")}

    v13_sets = [r["set"] for r in rows if r["v13_comparison_set"]]

    def family_collisions(train_sets):
        """학습으로 보낼 셋의 유효 target 중, 평가로 남는 셋(업체 100 포함)과 거친 의미 family가 같은 문항 수.
        thor Protection은 보호 셋의 semantic family와 같은 학습 후보를 막는다(training.annotations.inventory)."""
        kept = {fam for name, fam in valid_targets if name not in train_sets}
        vendor = {fam for name, fam in valid_targets if name == "vendor100"}
        picked = [fam for name, fam in valid_targets if name in train_sets]
        return {"train_valid_targets": len(picked),
                "collide_with_vendor100_family": sum(f in vendor for f in picked),
                "collide_with_any_kept_eval_family": sum(f in kept for f in picked),
                "free_of_kept_eval_families": sum(f not in kept for f in picked)}
    scenarios = {
        "S0_all_claude_written_vendor_format_sets(vendor100 제외)": total([r["set"] for r in rows if r["set"] != "vendor100"]),
        "S1_sets_outside_v13_comparison(stage_v7, heldout_v8, heldout_v9)": total(["stage_v7", "heldout_v8", "heldout_v9"]),
        "S2_v13_dev_sets_without_vendor100_and_final": total([s for s in v13_sets if s not in ("vendor100", "final_v12")]),
        "v13_dev_universe_428_sets": total([s for s in v13_sets if s != "final_v12"]),
    }
    families_check = {name: family_collisions(sets) for name, sets in {
        "S0": [r["set"] for r in rows if r["set"] != "vendor100"],
        "S1": ["stage_v7", "heldout_v8", "heldout_v9"],
        "S2": [s for s in v13_sets if s not in ("vendor100", "final_v12")]}.items()}
    out = {"family_protection_check": families_check, "exclusions": {k: sorted(v) for k, v in sorted(excluded.items())},
           "vendor_format_sets": rows, "registry_corpora": corpora, "registry_question_sets": question_sets,
           "scenarios": scenarios}
    path, digest = write_output("policy_scale.json", out)
    print(json.dumps(out, ensure_ascii=False, indent=1))
    print(f"\nwrote {path} sha256={digest}")


if __name__ == "__main__":
    main()
