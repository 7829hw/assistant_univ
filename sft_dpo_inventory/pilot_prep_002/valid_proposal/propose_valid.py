# -*- coding: utf-8 -*-
"""진짜 pilot의 checkpoint 선택용 valid 선택지의 규모·겹침·provider 분류·검정력을 센다. 제안용이며 아무것도 채택하지 않는다.

    python sft_dpo_inventory/pilot_prep_002/valid_proposal/propose_valid.py

- (a) v003_t2pc valid 16문항. (b) batch004 후보 중 일부(아직 승인 전이라 후보 18개 기준). (c) 보호된 개발 셋 중 grounding_v13
  비교에 쓰지 않은 셋(stage_v7, heldout_v8, heldout_v9).
- 산출물에는 보호 셋의 질문 문장을 넣지 않는다(id, 수, 분류만).
- 학습 데이터 = v003_t2pc train 19문항 + batch004 후보 18개(승인 전 상한). 겹침은 두 가지로 센다.
  - 정규화 질문 같음(thor ``question_key``).
  - 거친 의미 family 같음(thor ``family_key``와 같은 기준: 측정값·OD·집계/그룹 factor, ``policy_scale.coarse_family``).
- provider 분류: ``../provider/classify_providers.classify``(gold 장소를 mock·reference로 조회).
- 검정력: 같은 셋에서 checkpoint 두 개를 문항 단위로 비교(McNemar 정확 검정, 양측 0.05). 불일치 문항 수 D에서 유의한
  최소 순차이 |b−c|를 계산하고, D는 pipeline_pilot_001의 같은 학습 안 checkpoint 쌍에서 관측한 불일치 비율로 정한다.
"""
import json
import math
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory"))
sys.path.insert(0, str(HERE.parent / "provider"))

import classify_providers as C  # noqa: E402
import evaluate_vendor100 as EV  # noqa: E402
from policy_scale import coarse_family, exclusion_keys, question_key  # noqa: E402

CORPUS = ROOT / "training/generated/reviewed_gold_v003_t2pc"
BATCH004 = ROOT / "sft_dpo_inventory/batch004/candidates_checked.json"
PILOT_VALID = ROOT / "sft_dpo_inventory/pipeline_pilot_001/valid"
PROTECTED = {"stage_v7": "evaluation/grounding_v7/stage_contrast_questions.yaml",
             "heldout_v8": "evaluation/grounding_v8/heldout_questions.yaml",
             "heldout_v9": "evaluation/grounding_v9/heldout_questions.yaml"}
SECONDS_PER_ITEM = {"user_estimate": 30, "pipeline_pilot_001_observed": None}


def corpus(split):
    for line in (CORPUS / f"sft_{split}.jsonl").read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        yield {"id": r["metadata"]["source_record_id"], "question": r["messages"][1]["content"],
               "grounding": json.loads(r["messages"][2]["content"]), "family": r["metadata"].get("family")}


def batch004():
    for c in json.loads(BATCH004.read_text(encoding="utf-8"))["candidates"]:
        yield {"id": c["id"], "question": c["question"], "grounding": c["draft_grounding"], "family": c["family"],
               "contract_failure": c["id"] in {"b004-34", "b004-35", "b004-40", "b004-41"}}


def describe(items, train_q, train_f):
    classes, overlap_q, overlap_f, no_gold = Counter(), 0, 0, 0
    for item in items:
        g = item["grounding"]
        if not g:
            no_gold += 1
            classes["no_gold_grounding"] += 1
            continue
        classes[C.classify(g)[0]] += 1
        overlap_q += question_key(item["question"]) in train_q
        overlap_f += coarse_family(g) in train_f
    return {"items": len(items), "provider_classes": dict(classes), "no_gold_grounding": no_gold,
            "question_overlap_with_training": overlap_q, "coarse_family_overlap_with_training": overlap_f,
            "families(own grouping)": len({i.get("family") or i["id"] for i in items})}


def min_net_difference(discordant, alpha=0.05):
    """불일치 D개 중 한쪽 b, 다른 쪽 c=D−b. 양측 정확 McNemar p<alpha가 되는 최소 b−c. 없으면 None."""
    for b in range(math.ceil(discordant / 2), discordant + 1):
        tail = sum(math.comb(discordant, k) for k in range(b, discordant + 1)) / 2 ** discordant
        if min(1.0, 2 * tail) < alpha:
            return b - (discordant - b)
    return None


def observed_discordance():
    labels = {"sft": ["sft_step2", "sft_step4", "sft_step6", "sft_step8", "sft_step10", "sft_step12"],
              "dpo": ["dpo_step2", "dpo_step4", "dpo_step6", "dpo_step8"]}
    ok = {}
    seconds = []
    for path in PILOT_VALID.glob("*.json"):
        r = json.loads(path.read_text(encoding="utf-8"))
        if "meta" not in r:
            continue
        ok[r["meta"]["label"]] = {row["id"]: row["grounding_ok"] for row in r["rows"]}
        seconds.append(r["summary"]["seconds"] / r["summary"]["items"])
    pairs = []
    for stage, ls in labels.items():
        for i, a in enumerate(ls):
            for b in ls[i + 1:]:
                pairs.append(sum(ok[a][k] != ok[b][k] for k in ok[a]) / len(ok[a]))
    base_pairs = [sum(ok["base"][k] != ok[l][k] for k in ok["base"]) / len(ok["base"]) for l in ok if l != "base"]
    return {"within_run_pairs": len(pairs), "mean_discordant_rate": round(sum(pairs) / len(pairs), 3),
            "max_discordant_rate": round(max(pairs), 3),
            "base_vs_checkpoint_mean_rate": round(sum(base_pairs) / len(base_pairs), 3),
            "seconds_per_item_observed": round(sum(seconds) / len(seconds), 1)}


def main():
    train = list(corpus("train"))
    b004 = list(batch004())
    train_q = {question_key(i["question"]) for i in train + b004}
    train_f = {coarse_family(i["grounding"]) for i in train + b004}
    excluded = exclusion_keys()
    options = {}
    valid = list(corpus("valid"))
    options["a_v003_t2pc_valid"] = {
        "source": "training/generated/reviewed_gold_v003_t2pc/sft_valid.jsonl (reviewed_gold v001–v003)",
        "human_review": "있음(reviewed corpus: hwkim 최종 확정·import 승인, Codex 재검증)",
        "policy_or_ambiguous_excluded": "해당 감사 없음(grounding_v13 label_audit·dev_report 대상 아님)",
        **describe(valid, {question_key(i["question"]) for i in train + b004},
                   {coarse_family(i["grounding"]) for i in train + b004}),
        "thor_family_overlap_with_train": len({i["family"] for i in valid} & {i["family"] for i in train})}
    b_items = [i for i in b004 if not i["contract_failure"]]
    train_only = train
    options["b_batch004_subset"] = {
        "source": "sft_dpo_inventory/batch004/candidates_checked.json(후보 18개, 사람 검토 전)",
        "human_review": "검토 대기(검토 시트). 승인분만 쓸 수 있다",
        "policy_or_ambiguous_excluded": "검토에서 정해짐(지금 0)",
        "contract_failures_pending_target_decision": 4,
        **describe(b_items, {question_key(i["question"]) for i in train_only},
                   {coarse_family(i["grounding"]) for i in train_only}),
        "families_total(batch004 grouping)": len({i["family"] for i in b004}),
        "note": "family 단위로 나눠야 학습·valid 사이 누수가 없다. valid로 보낸 만큼 학습 후보가 준다."}
    for name, path in PROTECTED.items():
        items = []
        seen = set()
        for item in EV.load_gold(ROOT / path)["items"]:
            key = question_key(item["question"])
            if key in seen:
                continue
            seen.add(key)
            try:
                g = EV.gold_grounding(item)
            except Exception:  # noqa: BLE001
                g = None
            items.append({"id": item["id"], "question": item["question"], "grounding": g,
                          "family": item.get("contrast") or item["id"]})
        policy = sum(1 for i in items if f"{name}/{i['id']}" in excluded)
        options[f"c_{name}"] = {
            "source": path, "human_review": "없음(Claude 작성, 기대 결과를 실행 전에 고정)",
            "policy_or_ambiguous_excluded": f"{policy}(v13 감사 대상이 아니라 감사되지 않았다는 뜻)",
            **describe(items, train_q, train_f),
            "condition": "checkpoint 선택 전용. 학습 입력·annotation 후보로 계속 쓰지 않는다(보호 정책은 학습 입력만 막는다)."}
    obs = observed_discordance()
    sizes = [16, 30, 45, 60, 85, 100, 103]
    power = []
    for n in sizes:
        row = {"n": n}
        for key, rate in (("mean", obs["mean_discordant_rate"]), ("max", obs["max_discordant_rate"])):
            d = max(1, round(rate * n))
            row[f"discordant_{key}"] = d
            row[f"min_net_difference_{key}"] = min_net_difference(d)
        row["minutes_per_checkpoint_30s"] = round(n * 30 / 60, 1)
        row["minutes_per_checkpoint_observed"] = round(n * obs["seconds_per_item_observed"] / 60, 1)
        power.append(row)
    out = {"options": options, "training_reference": {"v003_t2pc_train": len(train), "batch004_candidates": len(b004)},
           "observed_discordance(pipeline_pilot_001)": obs,
           "min_discordant_for_any_significance": next(d for d in range(1, 30) if min_net_difference(d) is not None),
           "power": power}
    (HERE / "valid_options.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
