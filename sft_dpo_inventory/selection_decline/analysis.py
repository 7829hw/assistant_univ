# -*- coding: utf-8 -*-
"""selection_v1 하락 분석(작업 지시 6). 기록만 쓰고 모델 호출은 하지 않는다.

    python sft_dpo_inventory/selection_decline/analysis.py

1. 라벨 표기 가설: gold 중 지금 계약과 다른 표기(같은 장소의 출발·도착을 장소 두 개로 적음 등)를 쓰는 문항과, 호출(컴파일 결과)은 gold와
   같은데 grounding_ok만 X인 문항을 센다. base는 맞고 학습 모델은 틀린 문항에서 이 경우가 얼마나 되는지 본다.
2. base와 SFT·DPO checkpoint의 오류 유형을 원천 셋(old44, contrast, indepv2–4)별로 센다.
3. 학습 데이터(pilot_002 실제 학습 파일 ``thinking_pilot002_t2pc``)의 유형 분포를 selection_v1·valid98 gold 분포와 대조한다.
4. thinking 길이·생성 상한·루프(결정 40-D, HF 원문)를 checkpoint별로 센다.
5. valid98에서 같은 분류를 해서 selection_v1과 비교한다.
- 결과: ``analysis.json``. selection_v1의 gold·셋 구성은 고치지 않는다. 질문 문장은 넣지 않는다.
"""
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

import records as R

sys.path.insert(0, str(R.ROOT / "sft_dpo_inventory/pilot_prep_004/loop_filter"))
from apply_filter import is_loop, loop_metrics, split_think  # noqa: E402

HERE = Path(__file__).resolve().parent
TRAIN = R.ROOT / "training/generated/thinking_pilot002_t2pc"
SEL_CELLS = ["HF-base", "HF-sft190", "HF-sft380", "HF-sft570", "HF-sft758", "HF-dpo72", "HF-dpo144", "HF-dpo216", "HF-dpo288"]
V98_CELLS = ["HF-base", "HF-p001-sft124", "HF-p001-dpo212", "HF-sft380", "HF-dpo144"]
COUNT_MEASURES = {"trip_count", "passage_count", "active_taxi_count", "operating_days"}


def diff_keys(row):
    return [d if isinstance(d, str) else d[0] for d in row.get("grounding_diffs") or []]


def same_place_two(view):
    names = Counter(n for n, _ in view["places"])
    return any(c >= 2 and {r for n2, r in view["places"] if n2 == n} >= {"pickup", "dropoff"} for n, c in names.items())


def classify(row, gview, category):
    """grounding_ok가 X인 문항의 오류 유형(첫 해당 하나)."""
    keys = diff_keys(row)
    mv = R.view(row.get("grounding"))
    if "no_grounding" in keys or mv is None:
        code = row.get("error_code")
        return "출력 없음(생성 상한)" if code == "OUTPUT_TRUNCATED" else f"grounding 없음({code})"
    if category == "match":
        return "호출 같음·grounding만 다름"
    if "places" in keys and gview and same_place_two(gview) and any(r == "both" for _, r in mv["places"]):
        return "장소 표기(옛 표기 ↔ both)"
    if "measure" in keys:
        return "측정값"
    agg = [d for d in row.get("grounding_diffs") or [] if not isinstance(d, str) and d[0] == "factor:aggregation_spec"]
    if agg and agg[0][1] is None:
        return "질문에 없는 집계 추가"
    if "places" in keys:
        return "장소·역할"
    if "factor:taxi_status" in keys:
        return "상태 조건"
    if "factor:dimension_target" in keys:
        return "dimension_target"
    if agg:
        return "집계 다름"
    return "기타(" + ",".join(sorted(set(keys))) + ")"


def raw_stats(set_name, cell):
    path = R.CELLS[(set_name, cell)][0]
    meta = json.loads(path.read_text(encoding="utf-8"))["meta"]
    raw = Path(meta.get("raw_out") or (meta.get("hf") or {}).get("raw_out") or "")
    out = {"loop_calls": None, "loop_items": None}
    if raw.is_file():
        hits = []
        for line in raw.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            m = loop_metrics(split_think(r["raw_text"])[0])
            if is_loop(m) if m else ["empty_thinking"]:
                hits.append(r["id"])
        out = {"loop_calls": len(hits), "loop_items": sorted(set(hits)), "raw": str(raw.relative_to(R.ROOT)) if R.ROOT in raw.parents else str(raw)}
    return out


def cell_block(set_name, cell, gold, base_rows):
    rows = R.load(set_name, cell, set(gold))
    by_set = defaultdict(Counter)
    errors = {}
    for i, r in rows.items():
        src = i.split("/")[0]
        by_set[src]["items"] += 1
        by_set[src]["grounding_ok"] += bool(r["grounding_ok"])
        if not r["grounding_ok"]:
            kind = classify(r, R.gold_view(gold[i]), r.get("vendor_style_category"))
            errors[i] = kind
            by_set[src][kind] += 1
    th = [r.get("thinking_chars_first_plan") for r in rows.values() if r.get("thinking_chars_first_plan") is not None]
    out = {"desc": R.CELLS[(set_name, cell)][2], "grounding_ok": sum(bool(r["grounding_ok"]) for r in rows.values()),
           "items": len(rows), "by_source": {k: dict(v) for k, v in sorted(by_set.items())},
           "error_types": dict(Counter(errors.values())), "errors": errors,
           "compile_match_but_x": sorted(i for i, r in rows.items() if not r["grounding_ok"] and r.get("vendor_style_category") == "match"),
           "truncated_calls": sum(sum(d == "length" for d in r.get("done_reasons") or []) for r in rows.values()),
           "truncated_items": sorted(i for i, r in rows.items() if "length" in (r.get("done_reasons") or [])),
           "first_plan_thinking_chars": {"median": statistics.median(th), "p90": sorted(th)[int(0.9 * (len(th) - 1))], "max": max(th)} if th else None,
           "generated_tokens_median": statistics.median(t for r in rows.values() for t in r.get("generated_tokens") or [0]),
           "model_calls": sum(r.get("model_calls") or 0 for r in rows.values()),
           "seconds_median": round(statistics.median(r["seconds"] for r in rows.values()), 2) if all("seconds" in r for r in rows.values()) else None,
           **raw_stats(set_name, cell)}
    if base_rows is not None and cell != "HF-base":
        lost = sorted(i for i in rows if base_rows[i]["grounding_ok"] and not rows[i]["grounding_ok"])
        gained = sorted(i for i in rows if not base_rows[i]["grounding_ok"] and rows[i]["grounding_ok"])
        out["vs_base"] = {"lost": len(lost), "gained": len(gained),
                          "lost_types": dict(Counter(errors[i] for i in lost)),
                          "lost_items": {i: errors[i] for i in lost},
                          "gained_items_base_type": {i: classify(base_rows[i], R.gold_view(gold[i]), base_rows[i].get("vendor_style_category")) for i in gained},
                          "lost_by_source": dict(Counter(i.split("/")[0] for i in lost)),
                          "gained_by_source": dict(Counter(i.split("/")[0] for i in gained))}
    return out


def features(view, question=None):
    f = view["factors"]
    feats = {"measure:" + str(view["measure"])}
    for k in ("aggregation", "dimension", "dimension_target", "order", "taxi_status", "taxi_type", "bucket", "time", "vicinity"):
        if f.get(k) is not None:
            feats.add(f"{k}")
    if f.get("aggregation"):
        feats.add(f"aggregation={f['aggregation']}")
        if view["measure"] in COUNT_MEASURES:
            feats.add("count measure + aggregation")
    if f.get("taxi_status"):
        feats.add(f"{view['measure']} + taxi_status={f['taxi_status']}")
    roles = [r for _, r in view["places"]]
    if "both" in roles:
        feats.add("od_role both")
    if "pickup" in roles or "dropoff" in roles:
        feats.add("od_role pickup/dropoff")
    if same_place_two(view):
        feats.add("same place pickup+dropoff(옛 표기)")
    if f.get("dimension") and view["measure"] == "trip_count" and not f.get("dimension_target"):
        feats.add("trip_count + dimension, dimension_target 생략")
    return feats


def train_features():
    out = {}
    for name in ("sft_train", "dpo_train"):
        c = Counter()
        n = 0
        questions = set()
        for line in open(TRAIN / f"{name}.jsonl", encoding="utf-8"):
            r = json.loads(line)
            msgs = r.get("messages") or r.get("prompt") or []
            q = next((m["content"] for m in msgs if m["role"] == "user"), None)
            if name == "dpo_train":
                text = r["chosen"] if isinstance(r.get("chosen"), str) else r["chosen"][-1]["content"]
            else:
                text = [m for m in msgs if m["role"] == "assistant"][-1]["content"]
            try:
                g = json.loads(text.split("</think>")[-1])
            except json.JSONDecodeError:
                c["parse_fail"] += 1
                continue
            n += 1
            questions.add(q)
            if "concepts" not in g:
                c["unsupported"] += 1
                continue
            for feat in features(R.view(g)):
                c[feat] += 1
        out[name] = {"records": n, "unique_questions": len(questions), "features": dict(sorted(c.items()))}
    return out


def gold_features(set_name):
    c = Counter()
    for item in R.gold_items(set_name).values():
        v = R.gold_view(item)
        if v is None:
            c["no_gold_grounding"] += 1
            continue
        for feat in features(v):
            c[feat] += 1
    return dict(sorted(c.items()))


def main():
    out = {"note": "기록만 사용, 모델 호출 없음. 판정 규칙 없음.", "selection_v1": {}, "valid98": {}}
    for set_name, cells in (("selection_v1", SEL_CELLS), ("valid98", V98_CELLS)):
        gold = R.gold_items(set_name)
        base = R.load(set_name, "HF-base", set(gold))
        out[set_name]["gold_notation"] = {
            "same_place_pickup_dropoff": sorted(i for i, it in gold.items() if (v := R.gold_view(it)) and same_place_two(v)),
            "vicinity": sorted(i for i, it in gold.items() if (v := R.gold_view(it)) and v["factors"].get("vicinity") is not None)}
        out[set_name]["cells"] = {cell: cell_block(set_name, cell, gold, base) for cell in cells}
        out[set_name]["gold_features"] = gold_features(set_name)
    out["training_features"] = train_features()
    (HERE / "analysis.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for set_name in ("selection_v1", "valid98"):
        print("==", set_name, out[set_name]["gold_notation"])
        for cell, c in out[set_name]["cells"].items():
            vb = c.get("vs_base") or {}
            print(cell, c["grounding_ok"], "lost", vb.get("lost"), "gained", vb.get("gained"), vb.get("lost_types"),
                  "| trunc", c["truncated_calls"], "loops", c["loop_calls"], "think", c["first_plan_thinking_chars"],
                  "| match-but-X", c["compile_match_but_x"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
