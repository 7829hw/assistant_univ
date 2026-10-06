# -*- coding: utf-8 -*-
"""진짜 pilot의 checkpoint 선택용 valid(결정 16: stage_v7 + heldout_v8 + heldout_v9)를 고정하고 v004와 대조한다. 모델을 부르지 않는다.

    python sft_dpo_inventory/pilot_prep_003/valid100/build_valid100.py

- 문항 규칙은 ``pilot_prep_002/valid_proposal/valid_options.json``과 같다.
  - 앞 셋(``policy_scale.VENDOR_FORMAT_SETS`` 순서)과 정규화 질문이 같은 문항은 뺀다(stage_v7 1개).
  - 정답 grounding을 만들 수 없는 문항은 뺀다(heldout_v9 3개).
  - 정책·모호 라벨(``policy_scale.exclusion_keys``)은 뺀다. 이 세 셋은 grounding_v13 감사 대상이 아니라 0개다(감사되지 않았다는 뜻).
- provider는 mock이다(결정 16). 문항마다 장소 provider 분류(``pilot_prep_002/provider``)도 적는다.
- 출력 ``valid100_items.json``에는 셋 이름·경로·id·원본 sha256만 둔다(보호 셋 질문 문장은 넣지 않는다). 평가 스크립트는 원본 YAML에서
  문항을 읽는다. 이 셋은 checkpoint 선택에만 쓰고 학습 입력·annotation 후보로 쓰지 않는다.
- v004 대조: 정규화 질문, 거친 의미 family(thor ``family_key`` 기준, ``policy_scale.coarse_family``), thor ``Protection``이 쓰는
  template·family 지문(``training.annotations.inventory``)이 v004 학습 레코드와 겹치는지 센다.
"""
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory"))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_prep_002/provider"))

import classify_providers as C  # noqa: E402
import evaluate_vendor100 as EV  # noqa: E402
from policy_scale import VENDOR_FORMAT_SETS, coarse_family, exclusion_keys, question_key  # noqa: E402

SETS = ["stage_v7", "heldout_v8", "heldout_v9"]
V004 = ROOT / "training/generated/reviewed_gold_v004_t2pc/sft_train.jsonl"


def earlier_questions(stop_at):
    seen = set()
    for name, path, _, _ in VENDOR_FORMAT_SETS:
        if name == stop_at:
            break
        for item in EV.load_gold(ROOT / path)["items"]:
            seen.add(question_key(item["question"]))
    return seen


def main():
    from training.annotations.inventory import family_key
    from training.data.common import read_jsonl
    from training.data.split import template_key
    from training.data.canonicalize import serialize_planner_target  # noqa: F401
    paths = {name: path for name, path, _, _ in VENDOR_FORMAT_SETS}
    excluded_policy = exclusion_keys()
    seen = earlier_questions(SETS[0])
    items, dropped = [], []
    for name in SETS:
        for item in EV.load_gold(ROOT / paths[name])["items"]:
            key = question_key(item["question"])
            if key in seen:
                dropped.append({"set": name, "id": item["id"], "reason": "duplicate_of_earlier_set"})
                continue
            seen.add(key)
            if f"{name}/{item['id']}" in excluded_policy:
                dropped.append({"set": name, "id": item["id"], "reason": "policy_or_ambiguous"})
                continue
            try:
                gold = EV.gold_grounding(item)
            except Exception:  # noqa: BLE001
                gold = None
            if not gold:
                dropped.append({"set": name, "id": item["id"], "reason": "no_gold_grounding"})
                continue
            cls, _ = C.classify(gold)
            items.append({"set": name, "path": paths[name], "id": item["id"], "provider": "mock",
                          "place_class": cls, "expected_outcome": item.get("expected_outcome", "answered"),
                          "_question": item["question"], "_gold": gold})
    v004 = read_jsonl(V004)
    train_q = {question_key(r["messages"][1]["content"]) for r in v004}
    train_coarse = {coarse_family(json.loads(r["messages"][-1]["content"])) for r in v004}
    train_family = {family_key(json.loads(r["messages"][-1]["content"])) for r in v004}
    train_template = {template_key(r) for r in v004}
    overlap = Counter()
    for it in items:
        record = {"messages": [{"role": "system", "content": ""}, {"role": "user", "content": it["_question"]},
                               {"role": "assistant", "content": json.dumps(it["_gold"], ensure_ascii=False)}],
                  "metadata": {}}
        it["overlap_v004"] = {"question": question_key(it["_question"]) in train_q,
                              "coarse_family": coarse_family(it["_gold"]) in train_coarse,
                              "thor_family_key": family_key(it["_gold"]) in train_family,
                              "thor_template_key": template_key(record) in train_template}
        for k, v in it["overlap_v004"].items():
            overlap[k] += v
    sources = {paths[n]: hashlib.sha256((ROOT / paths[n]).read_bytes()).hexdigest() for n in SETS}
    out = {"decision": "16", "use": "checkpoint selection only; never training input", "provider": "mock",
           "sources_sha256": sources, "counts": {"items": len(items), "by_set": dict(Counter(i["set"] for i in items)),
                                                 "dropped": dict(Counter(d["reason"] for d in dropped)),
                                                 "place_class": dict(Counter(i["place_class"] for i in items)),
                                                 "expected_outcome": dict(Counter(i["expected_outcome"] for i in items))},
           "overlap_with_v004": {"v004_sha256": hashlib.sha256(V004.read_bytes()).hexdigest(), **dict(overlap)},
           "dropped": dropped,
           "items": [{k: v for k, v in i.items() if not k.startswith("_")} for i in items]}
    (HERE / "valid100_items.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("counts", "overlap_with_v004")}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
