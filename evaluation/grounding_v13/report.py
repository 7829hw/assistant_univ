# -*- coding: utf-8 -*-
"""grounding_v13 고정 후보 비교(모델 호출 없음). 저장 기록과 이번 단계에서 채운 실행을 같은 문항 집합에서 비교한다.

    python evaluation/grounding_v13/report.py --universe dev [--json OUT]
    python evaluation/grounding_v13/report.py --universe final --arm B DIR --arm X DIR [--json OUT]

- 분류는 v4-axes(evaluate_vendor100.score_semantic)를 그대로 쓴다. 정답·채점 코드는 바꾸지 않는다.
- 용납할 수 없는 실패(평균에 묻지 않고 따로 센다):
  U1 요구 조건을 버리고 답함: 지원 불가 문항(required_condition)을 답했거나, 답한 호출에서 정답에 있는
     date·time·taxi_type·taxi_status·dimension이 빠졌다.
  U2 잘못된 scope 사용: 답한 호출의 scope·scope_pickup·scope_dropoff·dimension_target이 정답과 다르거나, scope가 이 run의
     성공한 조회에서 오지 않았거나, 주변 포함 여부가 다르다.
  U3 잘못된 측정 대상 실행: 답한 호출의 Tool이나 metric이 정답과 다르다.
  U4 질문에 없는 조건을 넣거나 조건 값을 바꿔 답함: 답한 호출의 date·time·taxi_type·taxi_status 값이 정답과 다르다(정답은
     없음 포함).
  집계·순위·개수·그룹 단위의 차이는 조용한 오답에는 들어가지만 U에는 넣지 않는다(무엇을 셌는가가 아니라 어떻게 요약했는가).
- 라벨 점검(label_audit.json)에서 "정책 라벨(의미 모호)"로 표시한 문항은 라벨을 바꾸지 않고, 조용한 오답을 그 문항을
  뺀 값으로도 함께 보인다.
"""
import argparse
import json
import math
import random
import statistics
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

import importlib.util  # noqa: E402


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


R12 = _load("report_v12", HERE.parent / "grounding_v12" / "report.py")
C, E, R11, R10 = R12.C, R12.E, R12.R11, R12.R10
C.GOLD_FILES["heldout"] = "evaluation/grounding_v10/heldout_questions.yaml"
C.GOLD_FILES["final"] = "evaluation/grounding_v12/final_questions.yaml"
C.SETS = tuple(C.SETS) + ("final",)

V = "evaluation/"
#: 고정 후보의 개발 기록(428문항 = 개발 311 + OD 대조 16 + 운행 상태 대조 33 + v10 held-out 48 + 측정값 대조 20).
#: 앞의 출처가 같은 문항을 가지면 앞의 것을 쓴다(겹치지 않게 채웠다).
DEV_SOURCES = {
    "B": [V + "grounding_v9/runs/full/q8_cur",
          {"status": V + "grounding_v11/runs/status_merged/q8_cur/status.json",
           "heldout": V + "grounding_v11/runs/heldout/q8_cur/heldout.json",
           "measure": V + "grounding_v12/runs/measure/q8_cur/measure.json"}],
    "T2PC": [V + "grounding_v11/runs/full/t2pc",
             {"heldout": V + "grounding_v11/runs/heldout/t2pc/heldout.json",
              "measure": V + "grounding_v12/runs/measure/t2pc/measure.json"}],
    "T3PC": [V + "grounding_v12/runs/small/t3pc", V + "grounding_v13/runs/fill/t3pc"],
}
POPULATION = ("date", "time", "taxi_type", "taxi_status")
SCOPE_KEYS = ("scope", "scope_pickup", "scope_dropoff", "dimension_target")
NORMAL, WRONG = "정상 답변", "오답"


def load_sources(sources):
    rows, raw = {}, {}
    directory, extras = None, {}
    for source in sources:
        if isinstance(source, dict):
            extras.update(source)
    for source in sources:
        if isinstance(source, dict):
            continue
        part_rows, part_raw = C.load_arm(source, None, extras if directory is None else None)
        directory = directory or source
        for key in part_rows:
            if key not in rows:
                rows[key], raw[key] = part_rows[key], part_raw[key]
    return rows, raw


def _item(key, row):
    set_name, item_id = key.split("/", 1)
    return C._gold(set_name, row)[item_id]


def unacceptable(key, row, source):
    item = _item(key, row)
    need = R11.required_condition(key, item)
    flags = []
    if need and source.get("outcome") == "answered":
        flags.append("U1:" + ",".join(sorted(need)))
    checks = row.get("v4_checks") or {}
    if item.get("expected_outcome", "answered") == "answered" and source.get("outcome") == "answered" and checks:
        if not checks.get("tool_ok", True):
            flags.append("U3:tool")
        for name, want, got in checks.get("arg_mismatches") or []:
            if name in POPULATION + ("dimension",) and want is not None and got is None:
                flags.append(f"U1:{name}")
            elif name in POPULATION:
                flags.append(f"U4:{name}")
            elif name in SCOPE_KEYS:
                flags.append(f"U2:{name}")
            elif name == "metric":
                flags.append("U3:metric")
        if checks.get("scope_from_lookup") is False:
            flags.append("U2:provenance")
        if checks.get("vicinity_ok") is False:
            flags.append("U2:vicinity")
    return sorted(set(flags))


def wilson(k, n, z=1.96):
    if not n:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(c - h, 3), round(c + h, 3)]


def mcnemar(b, c):
    """양측 정확 검정(이항, p=0.5)."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return round(min(1.0, 2 * tail), 4)


def paired_diff_ci(a, b, reps=10000, seed=13):
    """같은 문항 쌍의 정상률 차이(b − a) 부트스트랩 95% 구간."""
    rng = random.Random(seed)
    n = len(a)
    diffs = []
    for _ in range(reps):
        idx = [rng.randrange(n) for _ in range(n)]
        diffs.append(sum(b[i] - a[i] for i in idx) / n)
    diffs.sort()
    return [round(diffs[int(0.025 * reps)], 3), round(diffs[int(0.975 * reps)], 3)]


def summarize(rows, raw, keys, ambiguous):
    classes = Counter(rows[k]["v4"] for k in keys)
    u_items = {k: unacceptable(k, rows[k], raw[k]) for k in keys}
    u_items = {k: v for k, v in u_items.items() if v}
    u_kinds = Counter(flag.split(":")[0] for flags in u_items.values() for flag in set(f.split(":")[0] for f in flags))
    sub_rows = {k: rows[k] for k in keys}
    sub_raw = {k: raw[k] for k in keys}
    refusal, refusal_items = R11.refusal_accuracy(sub_rows, sub_raw)
    layer, layer_bad = R11.layer_effects(sub_rows, sub_raw)
    measure, measure_items = R12.measure_errors(sub_rows, sub_raw)
    totals = sorted((rows[k]["cost"]["total_ms"] or 0) / 1000 for k in keys)
    n = len(keys)
    wrong = [k for k in keys if rows[k]["v4"] == WRONG]
    return {
        "items": n,
        "classes": dict(classes),
        "normal_ci": wilson(classes[NORMAL], n),
        "silent_wrong_ci": wilson(classes[WRONG], n),
        "silent_wrong_items": wrong,
        "silent_wrong_excluding_policy_ambiguous": len([k for k in wrong if k not in ambiguous]),
        "unacceptable": {"items": len(u_items), "by_kind": dict(u_kinds), "list": u_items},
        "refusal": refusal,
        "refusal_not_accurate": {k: r for k, r in refusal_items.items() if not r["accurate"]},
        "layer": layer, "layer_bad": layer_bad,
        "measure_errors": measure, "measure_error_items": measure_items,
        "cost": {"latency_median_s": round(statistics.median(totals), 1) if totals else None,
                 "latency_p90_s": round(totals[int(0.9 * (n - 1))], 1) if totals else None,
                 "repair_calls": sum(rows[k]["cost"]["repair_calls"] for k in keys),
                 "failed_llm_calls": sum(rows[k]["cost"]["failed_calls"] for k in keys)},
        "by_set": {s: dict(Counter(rows[k]["v4"] for k in keys if k.split("/")[0] == s))
                   for s in sorted({k.split("/")[0] for k in keys})},
    }


def paired(base_rows, rows, base_raw, raw, keys):
    trans = Counter()
    moves = {}
    for k in keys:
        a, b = base_rows[k]["v4"], rows[k]["v4"]
        trans[f"{a}→{b}"] += 1
        if a != b:
            moves.setdefault(f"{a}→{b}", []).append(k)
    a = [base_rows[k]["v4"] == NORMAL for k in keys]
    b = [rows[k]["v4"] == NORMAL for k in keys]
    gained = sum(1 for x, y in zip(a, b) if y and not x)
    lost = sum(1 for x, y in zip(a, b) if x and not y)
    wa = [base_rows[k]["v4"] == WRONG for k in keys]
    wb = [rows[k]["v4"] == WRONG for k in keys]
    new_wrong = [k for k, x, y in zip(keys, wa, wb) if y and not x]
    fixed_wrong = [k for k, x, y in zip(keys, wa, wb) if x and not y]
    ua = {k for k in keys if unacceptable(k, base_rows[k], base_raw[k])}
    ub = {k for k in keys if unacceptable(k, rows[k], raw[k])}
    return {
        "common": len(keys),
        "transitions": dict(trans), "moves": moves,
        "normal_gained": gained, "normal_lost": lost, "normal_mcnemar_p": mcnemar(gained, lost),
        "normal_diff_ci": paired_diff_ci(a, b),
        "silent_wrong_new": new_wrong, "silent_wrong_fixed": fixed_wrong,
        "silent_wrong_mcnemar_p": mcnemar(len(new_wrong), len(fixed_wrong)),
        "unacceptable_new": sorted(ub - ua), "unacceptable_fixed": sorted(ua - ub),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--universe", choices=("dev", "final"), required=True)
    parser.add_argument("--arm", nargs=2, action="append", default=[], metavar=("NAME", "DIR"))
    parser.add_argument("--base", default="B")
    parser.add_argument("--json", default="")
    args = parser.parse_args()
    audit = json.loads((HERE / "label_audit.json").read_text(encoding="utf-8"))
    ambiguous = set(audit["policy_ambiguous"]) | set(audit.get("ambiguous", []))
    if args.universe == "dev":
        sources = {name: DEV_SOURCES[name] for name in DEV_SOURCES}
    else:
        sources = {name: [directory] for name, directory in args.arm}
    loaded = {name: load_sources(src) for name, src in sources.items()}
    common = sorted(set.intersection(*[set(r) for r, _ in loaded.values()]))
    report = {"universe": args.universe, "common_items": len(common),
              "items_per_arm": {n: len(r) for n, (r, _) in loaded.items()},
              "policy_ambiguous": sorted(ambiguous), "arms": {}, "paired": {}}
    for name, (rows, raw) in loaded.items():
        report["arms"][name] = summarize(rows, raw, common, ambiguous)
    base_rows, base_raw = loaded[args.base]
    for name, (rows, raw) in loaded.items():
        if name != args.base:
            report["paired"][f"{args.base}→{name}"] = paired(base_rows, rows, base_raw, raw, common)
    names = [n for n in loaded if n != args.base]
    for i, x in enumerate(names):
        for y in names[i + 1:]:
            report["paired"][f"{x}→{y}"] = paired(loaded[x][0], loaded[y][0], loaded[x][1], loaded[y][1], common)
    if args.json:
        Path(args.json).write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print("common", len(common), report["items_per_arm"])
    for name, s in report["arms"].items():
        print(f"== {name}: {s['classes']} normal_ci {s['normal_ci']} sw_ci {s['silent_wrong_ci']}"
              f" sw_excl_policy {s['silent_wrong_excluding_policy_ambiguous']}")
        print("   U", s["unacceptable"]["items"], s["unacceptable"]["by_kind"])
        print("   refusal", s["refusal"], "layer", s["layer"], s["layer_bad"])
        print("   measure", s["measure_errors"], "cost", s["cost"])
    for name, d in report["paired"].items():
        print(f"== {name}: +{d['normal_gained']} -{d['normal_lost']} p={d['normal_mcnemar_p']} diff_ci {d['normal_diff_ci']}"
              f" | sw new {len(d['silent_wrong_new'])} fixed {len(d['silent_wrong_fixed'])} p={d['silent_wrong_mcnemar_p']}"
              f" | U new {d['unacceptable_new']} fixed {len(d['unacceptable_fixed'])}")


if __name__ == "__main__":
    main()
