# -*- coding: utf-8 -*-
"""C3: J1(Full)과 J6(Partial) 판정 대조. 모델 호출 없음. 판정은 ``judge_self.py``(조건 계층 전, gold 상태별)를 그대로 쓴다.

    python3 compare_arms.py   # -> arm_comparison.json

- 질문별 정답 표본 유무를 두 arm에서 대조: 둘 다 / Full만 / Partial만 / 둘 다 없음(gold 상태별).
- Partial이 Full보다 많이 틀린 차이 종류(표본 단위)와 질문의 risk tag(aug300) 관계: 차이 종류별로 그 차이가 난 표본 비율을 tag별로 비교.
- J5S'에서 실패한 "실차"·dt 문항 패턴(g02·g04·g12 = 승차·하차 끝 묶음 누락 계열)과 같은지: dimension_target 차이가 dt tag 문항에 몰리는지 본다.
"""
import json
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
j1 = {q["id"]: q for q in json.loads((HERE / "j1_judgement.json").read_text(encoding="utf-8"))["per_question"]}
j6 = {q["id"]: q for q in json.loads((HERE / "j6_judgement.json").read_text(encoding="utf-8"))["per_question"]}
items = {json.loads(l)["id"]: json.loads(l) for l in (ROOT / "sft_dpo_inventory/pilot_006_prep/aug300/augmentation_300.jsonl").read_text(encoding="utf-8").splitlines()}


def diffs(raw, judge_arm):
    """표본별 차이 종류(판정기를 다시 돌리지 않고 원문 판정 결과 파일에서): judge_self.py가 per_question에 차이를 남기지 않으므로 다시 계산한다."""
    return None


cross = defaultdict(Counter)
lists = defaultdict(list)
for i in j1:
    a, b = j1[i]["correct"] > 0, j6[i]["correct"] > 0
    k = "both" if a and b else "full_only" if a else "partial_only" if b else "neither"
    cross[j1[i]["gold_status"]][k] += 1
    if k in ("full_only", "partial_only"):
        lists[k].append(i)
# 차이 종류 × risk tag: judge를 다시 돌려 차이를 모은다
import sys
sys.path.insert(0, str(ROOT))
import evaluate_vendor100 as EV  # noqa: E402
from geoflow.planner import parse_planner_json  # noqa: E402
from grounding.completion import complete_grounding_payload  # noqa: E402
from training.data.thinking import split_response  # noqa: E402
golds = {json.loads(l)["id"]: json.loads(l) for l in (ROOT / "sft_dpo_inventory/pilot_006_prep/gpu/inputs/self_questions.jsonl").read_text(encoding="utf-8").splitlines()}
by_tag = {arm: defaultdict(Counter) for arm in ("full", "partial")}
tot_tag = {arm: Counter() for arm in ("full", "partial")}
for arm, path in (("full", "self_full/raw/self_full_raw.jsonl"), ("partial", "self_partial/raw/self_partial_raw.jsonl")):
    for line in (ROOT / "training/generated/pilot_006" / path).read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        if not r["id"].startswith("aug300-"):
            continue
        tags = items[r["id"]]["risk_tags"] or ["(none)"]
        kinds = set()
        try:
            pl = parse_planner_json(split_response(r["raw_text"])[1])
            pl = complete_grounding_payload(pl) if arm == "partial" else pl
            ok, d = EV.grounding_check({"gold_grounding": golds[r["id"]]["gold_grounding"], "gold": None}, pl)
            kinds = {x if isinstance(x, str) else x[0] for x in d}
        except Exception:  # noqa: BLE001
            kinds = {"no_json"}
        for t in tags:
            tot_tag[arm][t] += 1
            for k in kinds:
                by_tag[arm][k][t] += 1
rate = {arm: {k: {t: round(c / tot_tag[arm][t], 3) for t, c in v.items()} for k, v in by_tag[arm].items()} for arm in by_tag}
focus = ("factor:dimension_target", "measure", "places", "factor:aggregation_spec")
dt_tags = ("dt_pickup", "dt_dropoff", "dt_both", "od_both_dt_one")
summary = {k: {"full": {t: rate["full"].get(k, {}).get(t, 0) for t in (*dt_tags, "silcha_trip", "occupied_passage", "group_by", "ranking", "(none)")},
               "partial": {t: rate["partial"].get(k, {}).get(t, 0) for t in (*dt_tags, "silcha_trip", "occupied_passage", "group_by", "ranking", "(none)")}}
           for k in focus}
out = {"cross_by_gold_status": {k: dict(v) for k, v in cross.items()}, "full_only": lists["full_only"], "partial_only": lists["partial_only"],
       "diff_rate_by_risk_tag(aug300 samples, share of samples with that diff)": summary, "samples_per_tag": {a: dict(v) for a, v in tot_tag.items()},
       "note": "draft gold 기준 판정 포함(초안). 조건 계층 전."}
(HERE / "arm_comparison.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print(json.dumps({"cross": out["cross_by_gold_status"], "dt_rate": summary["factor:dimension_target"], "measure_rate": summary["measure"]}, ensure_ascii=False, indent=1))
