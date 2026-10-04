# -*- coding: utf-8 -*-
"""grounding_v10 arm 비교(모델 호출 없음). grounding_v9 compare.py의 축별 채점·층별·비용 지표에 운행 상태 지표를 더한다.

    python evaluation/grounding_v10/report.py --scope small|full|heldout --arm NAME DIR [--arm NAME DIR ...] \
        [--extra NAME=SET:PATH ...] [--json OUT]

- small: 운행 상태 대조 + OD 대조 + 원인 확인 개발 문항(cause_ids.json). full: 개발 311 + OD 대조 + 운행 상태 대조.
- 운행 상태 지표
  - status_stops_on_answerable: 답해야 할 문항이 taxi_status 때문에 합성에서 멈춘 수(이번 원인).
  - required: 답하지 말아야 할 문항마다 요구된 조건(정답 grounding의 taxi_status·taxi_type, held-out의 required_condition)이
    최종 grounding에 남았는지, 어떤 이유로 멈췄는지, 조건을 버리고 답했는지(조용한 오답).
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "grounding_v9"))
sys.path.insert(0, str(HERE.parents[1]))

import compare as C  # noqa: E402

C.GOLD_FILES["heldout"] = "evaluation/grounding_v10/heldout_questions.yaml"
#: 개발셋에서 질문이 상태를 요구하지만 측정값이 받지 않는 문항(기대: 지원 불가). 정답 파일에 정답 grounding이 없어 여기 적는다.
DEV_REQUIRED = {"indepv2/n26": {"taxi_status": "vacant"}}


def required_condition(key, item):
    if key in DEV_REQUIRED:
        return DEV_REQUIRED[key]
    if item.get("required_condition"):
        return dict(item["required_condition"])
    factors = (item.get("gold_grounding") or {}).get("factors") or {}
    if item.get("expected_outcome", "answered") != "answered":
        return {k: v for k, v in factors.items() if k in ("taxi_status", "taxi_type")} or None
    return None


def status_metrics(rows, raw):
    stops, required = [], {}
    for key in sorted(rows):
        set_name, item_id = key.split("/", 1)
        item = C._gold(set_name, rows[key])[item_id]
        source = raw[key]
        detail = ((source.get("planner_trace") or {}).get("error_detail") or "")
        status_stop = source.get("error_code") == "UNCONSUMED_CONDITION" and "taxi_status" in detail
        if item.get("expected_outcome", "answered") == "answered" and status_stop:
            stops.append(key)
        need = required_condition(key, item)
        if need:
            factors = (source.get("grounding") or {}).get("factors") or {}
            required[key] = {"need": need, "outcome": source.get("outcome"), "code": source.get("error_code"),
                             "kept_in_grounding": all(factors.get(k) == v for k, v in need.items()),
                             "class": rows[key]["v4"],
                             "dropped_and_answered": source.get("outcome") == "answered"}
    return {"status_stops_on_answerable": stops,
            "required": required,
            "required_summary": {
                "items": len(required),
                "refused_justified": sum(1 for r in required.values() if r["class"] == "정당한 거부"),
                "kept_in_grounding": sum(1 for r in required.values() if r["kept_in_grounding"]),
                "dropped_and_answered": sum(1 for r in required.values() if r["dropped_and_answered"]),
                "codes": dict(Counter(r["code"] for r in required.values()))}}


def by_group(rows, field):
    out = {}
    for key, row in rows.items():
        set_name, item_id = key.split("/", 1)
        item = C._gold(set_name, row)[item_id]
        group = item.get(field)
        if group is None:
            continue
        out.setdefault(f"{set_name}:{group}", Counter())[row["v4"]] += 1
    return {k: dict(v) for k, v in sorted(out.items())}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scope", choices=("small", "full", "heldout"), required=True)
    parser.add_argument("--arm", nargs=2, action="append", required=True, metavar=("NAME", "DIR"))
    parser.add_argument("--extra", action="append", default=[],
                        help="NAME=SET:PATH. 그 arm에 다른 디렉터리의 셋 결과를 더한다(기존 기록 재사용)")
    parser.add_argument("--base", default=None)
    parser.add_argument("--json", default="")
    args = parser.parse_args()
    ids = json.loads((HERE / "cause_ids.json").read_text()) if args.scope == "small" else None
    extras = {}
    for spec in args.extra:
        name, rest = spec.split("=", 1)
        set_name, path = rest.split(":", 1)
        extras.setdefault(name, {})[set_name] = path
    report = {"scope": args.scope, "arms": {}, "diffs": {}}
    arms, raws = {}, {}
    for name, directory in args.arm:
        arms[name], raws[name] = C.load_arm(directory, ids, extras.get(name))
        summary = C.summarize(arms[name], raws[name])
        summary["status"] = status_metrics(arms[name], raws[name])
        summary["by_category"] = by_group(arms[name], "category")
        summary["by_group"] = by_group(arms[name], "group")
        report["arms"][name] = summary
    base = args.base or args.arm[0][0]
    for name in arms:
        if name != base:
            report["diffs"][f"{base}→{name}"] = C.diff(arms[base], arms[name], raws[base], raws[name])
    if args.json:
        Path(args.json).write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    for name, s in report["arms"].items():
        print(f"== {name} ({s['items']})")
        for g in ("all", "dev", "dev_trip", "dev_other", "od_contrast"):
            print(f"  {g:11s}", s[g])
        print("  by_category", s["by_category"])
        print("  by_group", s["by_group"])
        print("  od10 normal", sum(v == "정상 답변" for v in s["watch"].values()))
        print("  grounding_ok", s["grounding_ok"]); print("  od", s["od_layers"])
        print("  cost", s["cost"]); print("  path", s["path"])
        st = s["status"]
        print("  status stops on answerable", len(st["status_stops_on_answerable"]), st["status_stops_on_answerable"])
        print("  required", st["required_summary"])
        for key, r in st["required"].items():
            print("     ", key, r)
    for name, d in report["diffs"].items():
        print(f"== {name}: common {d['common']} same_first {d['same_first_plan']} changed {d['class_changed']} {d['transitions']}")
        print("   gained", d["gained_normal"]); print("   lost", d["lost_normal"])


if __name__ == "__main__":
    main()
