# -*- coding: utf-8 -*-
"""grounding_v12 arm 비교(모델 호출 없음). grounding_v11 report.py의 지표(v4-axes·층별·운행 상태·거부 정확성·조건 계층)에
측정값 오류 유형을 더한다.

    python evaluation/grounding_v12/report.py --scope small|full|heldout [--heldout-file YAML] --arm NAME DIR [...]
        [--extra NAME=SET:PATH] [--base NAME] [--json OUT]

측정값 오류 유형(첫 계획 원출력 MEASURE vs 정답): answer_as_measure(세는 값 대신 LOCATION/place), passage_to_trip,
trip_to_passage, other.
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "grounding_v9"))
sys.path.insert(0, str(HERE.parents[1]))

import importlib.util  # noqa: E402

import compare as C  # noqa: E402
import evaluate_vendor100 as E  # noqa: E402


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# v11 report는 v10 report를 "report"라는 이름으로 불러 쓴다. 먼저 v10을 그 이름으로 올린다.
_load("report", HERE.parent / "grounding_v10" / "report.py")
R11 = _load("report_v11", HERE.parent / "grounding_v11" / "report.py")
from geoflow.planner import parse_planner_json  # noqa: E402

C.SETS = C.SETS + ("measure",)
C.GOLD_FILES["measure"] = "evaluation/grounding_v12/measure_contrast_questions.yaml"
R10 = R11.R10


def _measure(payload):
    for concept in (payload or {}).get("concepts") or []:
        if concept.get("role") == "MEASURE":
            return f"{concept.get('concept')}/{concept.get('subtype')}"
    return None


def measure_errors(rows, raw):
    kinds, items = Counter(), {}
    for key in sorted(rows):
        set_name, item_id = key.split("/", 1)
        item = C._gold(set_name, rows[key])[item_id]
        want = _measure(E.gold_grounding(item))
        if want is None:
            continue
        text = next((c.get("content") for c in raw[key].get("llm_calls") or [] if c["kind"] == "plan" and not c.get("failed")), None)
        try:
            got = _measure(parse_planner_json(text)) if text else None
        except Exception:  # noqa: BLE001
            got = "(parse error)"
        if got == want:
            continue
        if got == "LOCATION/place":
            kind = "answer_as_measure"
        elif (want, got) == ("AMOUNT/passage_count", "AMOUNT/trip_count"):
            kind = "passage_to_trip"
        elif (want, got) == ("AMOUNT/trip_count", "AMOUNT/passage_count"):
            kind = "trip_to_passage"
        else:
            kind = "other"
        kinds[kind] += 1
        items.setdefault(kind, []).append(key)
    return dict(kinds), items


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scope", choices=("small", "full", "heldout"), required=True)
    parser.add_argument("--heldout-file", default="evaluation/grounding_v10/heldout_questions.yaml")
    parser.add_argument("--ids", default="", help="개발 셋 문항 고르기(JSON 파일). 없으면 전체")
    parser.add_argument("--arm", nargs=2, action="append", required=True, metavar=("NAME", "DIR"))
    parser.add_argument("--extra", action="append", default=[])
    parser.add_argument("--base", default=None)
    parser.add_argument("--json", default="")
    args = parser.parse_args()
    C.GOLD_FILES["heldout"] = args.heldout_file
    ids = json.loads(Path(args.ids).read_text()) if args.ids else None
    extras = {}
    for spec in args.extra:
        name, rest = spec.split("=", 1)
        set_name, path = rest.split(":", 1)
        extras.setdefault(name, {})[set_name] = path
    report = {"scope": args.scope, "heldout_file": args.heldout_file, "arms": {}, "diffs": {}}
    arms, raws = {}, {}
    for name, directory in args.arm:
        arms[name], raws[name] = C.load_arm(directory, ids, extras.get(name))
        s = C.summarize(arms[name], raws[name])
        s["status"] = R10.status_metrics(arms[name], raws[name])
        s["by_category"] = R10.by_group(arms[name], "category")
        s["by_group"] = R10.by_group(arms[name], "group")
        s["refusal"], s["refusal_items"] = R11.refusal_accuracy(arms[name], raws[name])
        s["layer"], s["layer_bad"] = R11.layer_effects(arms[name], raws[name])
        s["measure_errors"], s["measure_error_items"] = measure_errors(arms[name], raws[name])
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
                print("     not accurate:", key, r["need"], r["class"], r["code"], "kept", r["kept"], "measure", r["measure_ok"])
        print("  layer", s["layer"], s["layer_bad"])
        print("  measure errors", s["measure_errors"], s["measure_error_items"])
    for name, d in report["diffs"].items():
        print(f"== {name}: common {d['common']} same_first {d['same_first_plan']} changed {d['class_changed']} {d['transitions']}")
        print("   gained", d["gained_normal"]); print("   lost", d["lost_normal"])


if __name__ == "__main__":
    main()
