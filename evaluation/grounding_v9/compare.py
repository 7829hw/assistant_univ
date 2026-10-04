# -*- coding: utf-8 -*-
"""grounding_v9 arm 비교(모델 호출 없음). 저장된 run을 v3와 축별 채점으로 다시 보고 같은 문항 집합에서 비교한다.

    python evaluation/grounding_v9/compare.py --arm NAME DIR [--arm NAME DIR ...] [--ids screen|full] \
        [--base NAME] [--json OUT] [--md OUT]

- DIR 안의 셋 결과(od.json, at.json, ...)를 읽는다. 기록 디렉터리(grounding_v7/runs_final 등)도 된다.
  OD 대조는 `od.json`이 없으면 `--od NAME=PATH`로 따로 준다.
- --ids screen이면 `screen_ids.json`의 개발셋 문항 + OD 대조만 본다.
- 반복 변동: 같은 모델·설명의 두 arm에서 첫 계획 응답 원문이 같은 문항 수와 결과 분류가 바뀐 문항 수.
"""
import argparse
import json
import statistics
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))

import evaluate_vendor100 as E  # noqa: E402

SETS = ("od", "status", "at", "contrast", "dev", "indepv2", "indepv3", "indepv4", "old44", "heldout")
#: grounding_v8이 확인한 qwen3:8b의 OD 혼동 10건(개발셋).
WATCH = ("indepv2/n06", "indepv4/k28", "indepv4/k31", "indepv3/m13", "indepv4/k34", "indepv4/k25",
         "contrast/c04a", "contrast/c04c", "old44/g11", "indepv2/n03")
CLASSES = ("정상 답변", "정당한 거부", "오답", "부당한 거부", "실행 실패")


def load_arm(directory, ids=None, extra=None):
    rows = {}
    raw = {}
    paths = {s: Path(directory) / f"{s}.json" for s in SETS}
    paths.update(extra or {})
    for set_name, path in paths.items():
        if not Path(path).is_file():
            continue
        meta, part = E.axes_rows(str(path))
        source = {r["id"]: r for r in json.loads(Path(path).read_text(encoding="utf-8"))["rows"]}
        for row in part:
            if ids is not None and set_name not in ("od", "status", "heldout") and row["id"] not in ids.get(set_name, ()):
                continue
            key = f"{set_name}/{row['id']}"
            rows[key] = row
            raw[key] = source[row["id"]]
    return rows, raw


def first_plan(raw_row):
    return next((c.get("content") for c in raw_row.get("llm_calls") or []
                 if c["kind"] == "plan" and not c.get("failed")), None)


def summarize(rows, raw):
    keys = sorted(rows)
    trip = [k for k in keys if rows[k]["od"] is not None]
    other = [k for k in keys if rows[k]["od"] is None]
    out = {"items": len(keys)}
    dev = [k for k in keys if not k.startswith(("od/", "heldout/", "status/"))]
    groups = (("all", keys), ("trip", trip), ("other", other), ("dev", dev),
              ("dev_trip", [k for k in dev if k in trip]), ("dev_other", [k for k in dev if k in other]),
              ("od_contrast", [k for k in keys if k.startswith("od/")]))
    for name, subset in groups:
        counter = Counter(rows[k]["v4"] for k in subset)
        out[name] = {c: counter.get(c, 0) for c in CLASSES} | {"n": len(subset)}
    out["v3_all"] = dict(Counter(rows[k]["v3"] for k in keys))
    out["v3_dev"] = dict(Counter(rows[k]["v3"] for k in dev))
    out["watch"] = {k: rows[k]["v4"] for k in WATCH if k in rows}
    od = [rows[k]["od"] for k in trip]
    out["od_layers"] = {layer: {part: sum(1 for o in od if o[layer][part]) for part in ("ends", "target", "both")}
                        for layer in E.OD_LAYERS} if od else {}
    # 최초·재질의 뒤 grounding 의미 정확(정답 grounding 전체와 비교). layers와 같은 정의.
    layer_ok = Counter()
    judged = 0
    for k in keys:
        set_name, item_id = k.split("/", 1)
        item = _gold(set_name, rows[k])[item_id]
        if E.gold_grounding(item) is None:
            continue
        judged += 1
        layers = E.grounding_layers(item, raw[k])
        for layer in ("raw", "normalized", "preserved"):
            layer_ok[layer] += bool(layers[layer]["ok"])
        layer_ok["repaired"] += bool(rows[k]["grounding_ok"])
    out["grounding_ok"] = dict(layer_ok) | {"of": judged}
    costs = [rows[k]["cost"] for k in keys]
    totals = sorted((c["total_ms"] or 0) / 1000 for c in costs)
    normal = [k for k in keys if rows[k]["v4"] == "정상 답변"]
    out["cost"] = {
        "plan_calls": sum(c["plan_calls"] for c in costs), "repair_calls": sum(c["repair_calls"] for c in costs),
        "failed_calls": sum(c["failed_calls"] for c in costs),
        "items_with_failed_call": sum(1 for c in costs if c["failed_calls"]),
        "repairs": sum(c["repairs"] for c in costs), "repair_failed": sum(c["repair_failed"] for c in costs),
        "normal_via_repair": sum(1 for k in normal if rows[k]["cost"]["repairs"]),
        "latency_sum_s": round(sum(totals)), "latency_median_s": round(statistics.median(totals), 1) if totals else None,
        "latency_p90_s": round(totals[min(len(totals) - 1, int(0.9 * len(totals)))], 1) if totals else None,
        "latency_max_s": round(totals[-1], 1) if totals else None,
        "eval_tokens": sum(c["eval_tokens"] or 0 for c in costs),
        "thinking_chars": sum(c["thinking_chars"] for c in costs),
        "truncated": sum(c["truncated"] for c in costs)}
    paths = [rows[k]["path"] for k in normal if rows[k]["path"]]
    out["path"] = {"normal_clean": sum(1 for p in paths if p["clean"]),
                   "normal_failed_lookup": sum(1 for p in paths if p["failed_lookups"]),
                   "normal_discarded_or_dup": sum(1 for p in paths if p["discarded_lookups"] or p["duplicate_lookups"])}
    return out


_GOLD = {}


#: 셋 이름 → 문항 파일. 다른 단계가 held-out 등을 바꿔 쓸 수 있게 모듈 수준에 둔다.
GOLD_FILES = {}


def _gold(set_name, row):
    if set_name not in _GOLD:
        files = {"od": "evaluation/grounding_v8/od_contrast_questions.yaml",
                 "status": "evaluation/grounding_v10/status_contrast_questions.yaml",
                 "at": "evaluation/grounding_v4/answer_target_questions.yaml",
                 "contrast": "evaluation/grounding_v2/contrast_questions.yaml",
                 "dev": "evaluation/vendor100/gold.yaml",
                 "indepv2": "evaluation/grounding_v2/independent_questions.yaml",
                 "indepv3": "evaluation/grounding_v2/independent_v3_questions.yaml",
                 "indepv4": "evaluation/grounding_v3/independent_v4_questions.yaml",
                 "old44": "evaluation/grounding_v1/holdout_questions.yaml",
                 "heldout": "evaluation/grounding_v9/heldout_questions.yaml"}
        files.update(GOLD_FILES)
        _GOLD[set_name] = {i["id"]: i for i in E.load_gold(E.HERE / files[set_name])["items"]}
    return _GOLD[set_name]


def diff(base, other, base_raw, other_raw):
    keys = sorted(set(base) & set(other))
    same_first = sum(1 for k in keys if first_plan(base_raw[k]) == first_plan(other_raw[k]))
    changed = [k for k in keys if base[k]["v4"] != other[k]["v4"]]
    to_normal = [k for k in changed if other[k]["v4"] == "정상 답변"]
    from_normal = [k for k in changed if base[k]["v4"] == "정상 답변"]
    return {"common": len(keys), "same_first_plan": same_first, "class_changed": len(changed),
            "gained_normal": to_normal, "lost_normal": from_normal,
            "transitions": dict(Counter(f"{base[k]['v4']}→{other[k]['v4']}" for k in changed))}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--arm", nargs=2, action="append", required=True, metavar=("NAME", "DIR"))
    parser.add_argument("--od", action="append", default=[], help="NAME=PATH: 그 arm의 OD 대조 결과")
    parser.add_argument("--ids", choices=("screen", "full"), default="full")
    parser.add_argument("--base", default=None)
    parser.add_argument("--json", default="")
    args = parser.parse_args()
    ids = json.loads((HERE / "screen_ids.json").read_text()) if args.ids == "screen" else None
    od_paths = dict(item.split("=", 1) for item in args.od)
    arms, raws, report = {}, {}, {"ids": args.ids, "arms": {}, "diffs": {}}
    for name, directory in args.arm:
        extra = {"od": od_paths[name]} if name in od_paths else None
        arms[name], raws[name] = load_arm(directory, ids, extra)
        report["arms"][name] = summarize(arms[name], raws[name])
    base = args.base or args.arm[0][0]
    for name in arms:
        if name != base:
            report["diffs"][f"{base}→{name}"] = diff(arms[base], arms[name], raws[base], raws[name])
    text = json.dumps(report, ensure_ascii=False, indent=1)
    if args.json:
        Path(args.json).write_text(text, encoding="utf-8")
    for name, summary in report["arms"].items():
        print(f"== {name} ({summary['items']})")
        for g in ("all", "dev", "dev_trip", "dev_other", "od_contrast"):
            print(f"  {g:11s}", summary[g])
        print("  od10 normal", sum(v == "정상 답변" for v in summary["watch"].values()), summary["watch"])
        print("  v3   ", summary["v3_all"])
        print("  grounding_ok", summary["grounding_ok"])
        print("  od", summary["od_layers"])
        print("  cost", summary["cost"]); print("  path", summary["path"])
    for name, d in report["diffs"].items():
        print(f"== {name}: common {d['common']} same_first {d['same_first_plan']} changed {d['class_changed']} "
              f"{d['transitions']}")
        print("   gained", d["gained_normal"]); print("   lost", d["lost_normal"])


if __name__ == "__main__":
    main()
