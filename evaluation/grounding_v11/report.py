# -*- coding: utf-8 -*-
"""grounding_v11 arm 비교(모델 호출 없음). grounding_v10 report.py의 지표에 거부의 정확성과 조건 계층의 훼손을 더한다.

    python evaluation/grounding_v11/report.py --scope small|full|heldout --arm NAME DIR [...] [--extra NAME=SET:PATH] [--json OUT]

- 정확한 거부(지원 불가 문항): 최종 분류가 정당한 거부이고, 요구된 조건이 최종 grounding에 남았고, 측정값이 정답 grounding과
  같고(정답 grounding이 있을 때), 코드의 멈춤 근거(오류 상세)가 그 조건을 가리킨다. 하나라도 어긋나면 "근거가 틀린 거부"로 센다.
  모델이 스스로 낸 unsupported는 grounding이 없으므로 정확한 거부가 아니다.
- 조건 계층(답해야 할 문항과 지원 불가 문항): 채움·변경이 정답 grounding 값과 다르면 잘못된 추가, 삭제했는데 정답에 값이 있으면
  잘못된 삭제, 측정값 정의로 채우지 않았는데 정답에 값이 있으면 놓친 채움.
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "grounding_v10"))
sys.path.insert(0, str(HERE.parent / "grounding_v9"))
sys.path.insert(0, str(HERE.parents[1]))

import compare as C  # noqa: E402
import report as R10  # noqa: E402
import evaluate_vendor100 as E  # noqa: E402

OWNED = ("taxi_status", "taxi_type")
NEUTRAL = {"taxi_status": (None, "all"), "taxi_type": (None, "all")}


def _measure(grounding):
    for concept in (grounding or {}).get("concepts") or []:
        if concept.get("role") == "MEASURE":
            return concept.get("concept"), concept.get("subtype")
    return None


def refusal_accuracy(rows, raw):
    out = {}
    for key in sorted(rows):
        set_name, item_id = key.split("/", 1)
        item = C._gold(set_name, rows[key])[item_id]
        need = R10.required_condition(key, item)
        if not need:
            continue
        source = raw[key]
        grounding = source.get("grounding") or {}
        factors = grounding.get("factors") or {}
        detail = ((source.get("planner_trace") or {}).get("error_detail") or "") + json.dumps(
            source.get("error_context") or {}, ensure_ascii=False)
        gold = item.get("gold_grounding")
        measure_ok = None if not gold else (_measure(grounding) == _measure(gold))
        kept = all(factors.get(k) == v for k, v in need.items())
        basis = any(k in detail for k in need)
        refused = rows[key]["v4"] == "정당한 거부"
        accurate = refused and kept and basis and measure_ok is not False
        out[key] = {"need": need, "class": rows[key]["v4"], "code": source.get("error_code"), "kept": kept,
                    "measure_ok": measure_ok, "basis_names_condition": basis,
                    "accurate": accurate, "answered": source.get("outcome") == "answered"}
    summary = {"items": len(out), "accurate": sum(r["accurate"] for r in out.values()),
               "refused_but_wrong_basis": sum(1 for r in out.values() if r["class"] == "정당한 거부" and not r["accurate"]),
               "answered_dropping_condition": sum(r["answered"] for r in out.values()),
               "other": sum(1 for r in out.values() if r["class"] != "정당한 거부" and not r["answered"])}
    return summary, out


def layer_effects(rows, raw):
    counts, items = Counter(), []
    for key in sorted(rows):
        set_name, item_id = key.split("/", 1)
        item = C._gold(set_name, rows[key])[item_id]
        gold = E.gold_grounding(item)
        if gold is None:
            continue
        gold_factors = gold.get("factors") or {}
        source = raw[key]
        events = [(c.get("condition"), c.get("action"), c.get("to")) for c in source.get("condition_corrections") or []]
        for name, record in (source.get("condition_actions") or {}).items():
            if record.get("action") == "not_filled":
                events.append((name, "not_filled", None))
        for name, action, value in events:
            if name not in OWNED:
                continue
            want = gold_factors.get(name)
            want_neutral = want in NEUTRAL[name]
            if action in ("filled", "corrected"):
                kind = "correct_fill" if value == want else "wrong_add"
            elif action == "removed_no_evidence":
                kind = "correct_remove" if want_neutral else "wrong_remove"
            elif action == "not_filled":
                kind = "correct_not_filled" if want_neutral else "missed_fill"
            else:
                continue
            counts[kind] += 1
            if kind in ("wrong_add", "wrong_remove", "missed_fill"):
                items.append(f"{key}:{name}:{action}->{value}")
    return dict(counts), items


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scope", choices=("small", "full", "heldout"), required=True)
    parser.add_argument("--arm", nargs=2, action="append", required=True, metavar=("NAME", "DIR"))
    parser.add_argument("--extra", action="append", default=[])
    parser.add_argument("--base", default=None)
    parser.add_argument("--json", default="")
    args = parser.parse_args()
    ids = json.loads((HERE.parent / "grounding_v10" / "cause_ids.json").read_text()) if args.scope == "small" else None
    extras = {}
    for spec in args.extra:
        name, rest = spec.split("=", 1)
        set_name, path = rest.split(":", 1)
        extras.setdefault(name, {})[set_name] = path
    report = {"scope": args.scope, "arms": {}, "diffs": {}}
    arms, raws = {}, {}
    for name, directory in args.arm:
        arms[name], raws[name] = C.load_arm(directory, ids, extras.get(name))
        s = C.summarize(arms[name], raws[name])
        s["status"] = R10.status_metrics(arms[name], raws[name])
        s["by_category"] = R10.by_group(arms[name], "category")
        s["by_group"] = R10.by_group(arms[name], "group")
        s["refusal"], s["refusal_items"] = refusal_accuracy(arms[name], raws[name])
        s["layer"], s["layer_bad"] = layer_effects(arms[name], raws[name])
        report["arms"][name] = s
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
        print("  by_category", s["by_category"]); print("  by_group", s["by_group"])
        print("  od10 normal", sum(v == "정상 답변" for v in s["watch"].values()))
        print("  grounding_ok", s["grounding_ok"]); print("  od", s["od_layers"])
        print("  cost", s["cost"]); print("  path", s["path"])
        print("  status stops on answerable", len(s["status"]["status_stops_on_answerable"]), s["status"]["status_stops_on_answerable"])
        print("  refusal", s["refusal"])
        for key, r in s["refusal_items"].items():
            if not r["accurate"]:
                print("     not accurate:", key, r)
        print("  layer", s["layer"], s["layer_bad"])
    for name, d in report["diffs"].items():
        print(f"== {name}: common {d['common']} same_first {d['same_first_plan']} changed {d['class_changed']} {d['transitions']}")
        print("   gained", d["gained_normal"]); print("   lost", d["lost_normal"])


if __name__ == "__main__":
    main()
