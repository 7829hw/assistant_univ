# -*- coding: utf-8 -*-
""""실차 통행량" 오독(결정 63 E-3): 개발 셋(selection_v1, valid98)에서 통행량 + 운행 상태 문항을 찾고, 셀마다 어떻게 읽었는지 센다.

    python sft_dpo_inventory/selection_decline/passage_status.py --out passage_status.json

- 대상 문항: gold grounding의 측정값이 passage_count이고 taxi_status가 있는 문항(실차 occupied, 공차 vacant, 대기영업 stationary).
- 셀마다 문항별로: 측정값(passage_count / trip_count / 기타), taxi_status, 장소 od_role, 결과·코드, grounding_ok.
  - "trip_count로 읽음": 최종 grounding의 측정값이 trip_count.
  - "상태 누락": 측정값은 passage_count인데 taxi_status가 없거나 다름.
- 학습 데이터(``reviewed_gold_v005_t2pc``)에서 같은 유형(passage_count + taxi_status)의 정답 수를 센다.
- 모델 호출 없음. 업체 100 문항은 근거로 쓰지 않는다(결정 36).
"""
import argparse
import json
from collections import Counter
from pathlib import Path

import records as R

V005 = R.ROOT / "training/generated/reviewed_gold_v005_t2pc"


def classify(gold, got, row):
    if got is None:
        return "grounding 없음"
    if got["measure"] == "trip_count":
        return "trip_count로 읽음"
    if got["measure"] != "passage_count":
        return f"다른 측정값({got['measure']})"
    if got["factors"].get("taxi_status") != gold["factors"].get("taxi_status"):
        return f"상태 다름({got['factors'].get('taxi_status')})"
    return "passage_count + 같은 상태"


def training_counts():
    out = {}
    for name in ("sft_train", "dpo_train"):
        c = Counter()
        for line in open(V005 / f"{name}.jsonl", encoding="utf-8"):
            r = json.loads(line)
            msgs = [m for m in r.get("messages") or [] if m["role"] == "assistant"]
            text = msgs[-1]["content"] if msgs else (r["chosen"] if isinstance(r.get("chosen"), str) else r["chosen"][-1]["content"])
            g = json.loads(text.split("</think>")[-1])
            if "concepts" not in g:
                continue
            v = R.view(g)
            question = next((m["content"] for m in r.get("messages") or r.get("prompt") or [] if m["role"] == "user"), "")
            st = v["factors"].get("taxi_status")
            c[f"{v['measure']} + taxi_status {st}"] += 1
            if v["measure"] == "trip_count" and "실차" in question:
                c["trip_count 정답 중 질문에 '실차'"] += 1
            if v["measure"] == "passage_count" and "실차" in question:
                c["passage_count 정답 중 질문에 '실차'"] += 1
            if v["measure"] == "trip_count" and "통행" in question:
                c["trip_count 정답 중 질문에 '통행'"] += 1
        out[name] = {k: v for k, v in sorted(c.items()) if "passage_count" in k or "실차" in k or "통행" in k}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    result = {"items": {}, "cells": {}, "training": training_counts()}
    for set_name in R.GOLD:
        gold = R.gold_items(set_name)
        targets = {}
        for i, item in gold.items():
            v = R.gold_view(item)
            if v and v["measure"] == "passage_count" and v["factors"].get("taxi_status"):
                targets[i] = v
        result["items"][set_name] = {i: {"taxi_status": v["factors"]["taxi_status"], "gold": v} for i, v in targets.items()}
        for (s, cell), (_, kind, desc) in R.CELLS.items():
            if s != set_name:
                continue
            rows = R.load(s, cell, set(targets))
            if rows is None:
                result["cells"][f"{s}:{cell}"] = {"missing": True, "kind": kind, "desc": desc}
                continue
            per = {}
            for i, gv in targets.items():
                row = rows[i]
                got = R.view(row.get("grounding"))
                per[i] = {"class": classify(gv, got, row), "measure": got and got["measure"],
                          "taxi_status": got and got["factors"].get("taxi_status"),
                          "od_roles": got and [p[1] for p in got["places"]],
                          "outcome": row.get("outcome"), "error_code": row.get("error_code"),
                          "grounding_ok": row.get("grounding_ok")}
            occ = [i for i, v in targets.items() if v["factors"]["taxi_status"] == "occupied"]
            result["cells"][f"{s}:{cell}"] = {
                "kind": kind, "desc": desc, "items": per,
                "occupied_items": len(occ),
                "occupied_read_as_trip_count": sum(per[i]["class"] == "trip_count로 읽음" for i in occ),
                "occupied_trip_count_answered": sum(per[i]["class"] == "trip_count로 읽음" and per[i]["outcome"] == "answered" for i in occ),
                "all_status_items": len(per),
                "all_read_as_trip_count": sum(p["class"] == "trip_count로 읽음" for p in per.values()),
                "grounding_ok": sum(bool(p["grounding_ok"]) for p in per.values())}
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for k, v in result["cells"].items():
        if v.get("missing"):
            print(k, "missing")
            continue
        print(k, f"occupied {v['occupied_read_as_trip_count']}/{v['occupied_items']} trip_count "
                 f"(answered {v['occupied_trip_count_answered']}), all {v['all_read_as_trip_count']}/{v['all_status_items']}, ok {v['grounding_ok']}",
              {i: p["class"][:12] + ("" if p["outcome"] == "answered" else "/" + str(p["error_code"])) for i, p in v["items"].items()})
    print(json.dumps(result["training"], ensure_ascii=False))


if __name__ == "__main__":
    main()
