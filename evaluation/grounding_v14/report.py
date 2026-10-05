# -*- coding: utf-8 -*-
"""grounding_v14 운영 조건 비교(모델 호출 없음).

    python evaluation/grounding_v14/report.py --run NAME FILE [--run NAME FILE ...] [--pair A B ...] [--json OUT]
    python evaluation/grounding_v14/report.py --retro [--json OUT]     # v13 기록에 확장 지표만 적용(판정 불변)

지표:
- 분류(v4-axes), v13 사전 등록 U(그대로, grounding_v13/report.py), 거부 정확성, 비용(지연·재질의·timeout·모델 적재).
- 확장 요구 보존 점검 R(v14에서 새로 정의, v13 판정에 소급하지 않는다):
  R1 요구 조건을 버리고 답함(U1과 같다).
  R2 표현할 수 없는 요구를 버리고 답함: 기대가 지원 불가(unsupported)인데 답했다. 최종 Tool 인자에 그 요구가 남지 않는
     경우(m40의 시간대별 묶음)도 여기서 잡힌다.
  R3 질문이 정하지 않은 의미를 채워 답함: 기대가 확인 요청(needs_clarification)인데 답했다(c08b·g44의 구간 안 집계).
  R4 질문이 정한 승하차 기준 대신 기본값으로 답함: 답한 호출의 dimension_target이 비어(기본값 both) 있고 정답은
     pickup·dropoff다(f03). U2의 부분집합이다.
  S  멈춘 문항의 해석: 멈춘(답하지 않은) 문항에서 최종 grounding을 정답 grounding과 비교해 측정값이나 date·time·
     taxi_type·taxi_status가 다르면 "해석 오류가 남은 채 멈춤"(v06). 멈춤이 맞았는지와 해석이 맞았는지를 나눠 센다.
- 실행 간 변동(같은 질문, 같은 조합의 두 run): 최초 grounding(첫 계획 응답을 파싱), 최종 grounding, Tool 인자, 최종
  분류가 바뀌었는가. grounding 차이는 개념 text·id만 다른 "문구 차이"와 값이 다른 "의미 차이"로 나눈다.
"""
import argparse
import json
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


R13 = _load("report_v13", HERE.parent / "grounding_v13" / "report.py")
C, E, R11 = R13.C, R13.E, R13.R11
from geoflow.planner import parse_planner_json  # noqa: E402

SET_BY_FILE = {
    "evaluation/grounding_v8/od_contrast_questions.yaml": "od",
    "evaluation/grounding_v10/status_contrast_questions.yaml": "status",
    "evaluation/grounding_v12/measure_contrast_questions.yaml": "measure",
    "evaluation/grounding_v10/heldout_questions.yaml": "heldout",
    "evaluation/grounding_v12/final_questions.yaml": "final",
    "evaluation/vendor100/gold.yaml": "dev",
}
LATENT_FACTORS = ("date", "time", "taxi_type", "taxi_status")
NORMAL, WRONG = "정상 답변", "오답"


def _item(key, row):
    return R13._item(key, row)


def requirement_flags(key, row, source):
    """확장 요구 보존 점검. (플래그 목록, 멈춘 문항의 해석 판정 또는 None)."""
    item = _item(key, row)
    expected = item.get("expected_outcome", "answered")
    answered = source.get("outcome") == "answered"
    flags = []
    u = R13.unacceptable(key, row, source)
    if any(f.startswith("U1") for f in u):
        flags.append("R1")
    need = R11.required_condition(key, item)
    if expected == "unsupported" and answered and not need:
        flags.append("R2")
    if expected == "needs_clarification" and answered:
        flags.append("R3")
    checks = row.get("v4_checks") or {}
    for name, want, got in checks.get("arg_mismatches") or []:
        if name == "dimension_target" and want in ("pickup", "dropoff") and got is None:
            flags.append("R4")
    stop = None
    if not answered:
        gold = E.gold_grounding(item)
        grounding = source.get("grounding")
        if gold and grounding:
            diffs = []
            if _measure(grounding) != _measure(gold):
                diffs.append("measure")
            gf, of = gold.get("factors") or {}, grounding.get("factors") or {}
            for name in LATENT_FACTORS:
                if _norm(name, gf.get(name)) != _norm(name, of.get(name)):
                    diffs.append(name)
            stop = {"latent_errors": diffs}
        else:
            stop = {"latent_errors": None}   # grounding이 없어 판단할 수 없음
    return sorted(set(flags)), stop


def _norm(name, value):
    return None if value in (None, "all") and name in ("taxi_type", "taxi_status") else value


def _measure(grounding):
    for concept in (grounding or {}).get("concepts") or []:
        if concept.get("role") == "MEASURE":
            return concept.get("concept"), concept.get("subtype")
    return None


def first_grounding(source):
    text = C.first_plan(source)
    if not text:
        return None
    try:
        return parse_planner_json(text)
    except Exception:  # noqa: BLE001
        return "(parse error)"


def _strip_text(grounding):
    """개념의 text·id(문구·이름표)를 지운 의미 비교용 사본. id를 가리키는 참조가 없으므로 id는 순서로 대신한다."""
    if not isinstance(grounding, dict):
        return grounding
    concepts = []
    for concept in grounding.get("concepts") or []:
        concepts.append({k: v for k, v in concept.items() if k not in ("text", "id")})
    out = {k: v for k, v in grounding.items() if k != "concepts"}
    out["concepts"] = sorted(concepts, key=lambda c: json.dumps(c, ensure_ascii=False, sort_keys=True))
    return out


def grounding_change(a, b):
    if a == b:
        return "same"
    if _strip_text(a) == _strip_text(b):
        return "wording_only"
    return "semantic"


def calls_of(source):
    return [(c["tool"], c["args"]) for c in source.get("calls") or []]


def summarize(rows, raw, keys, flagged):
    classes = Counter(rows[k]["v4"] for k in keys)
    u_items = {k: R13.unacceptable(k, rows[k], raw[k]) for k in keys}
    u_items = {k: v for k, v in u_items.items() if v}
    r_items, stops = {}, {}
    for k in keys:
        flags, stop = requirement_flags(k, rows[k], raw[k])
        if flags:
            r_items[k] = flags
        if stop is not None:
            stops[k] = stop
    sub_rows = {k: rows[k] for k in keys}
    sub_raw = {k: raw[k] for k in keys}
    refusal, refusal_items = R11.refusal_accuracy(sub_rows, sub_raw)
    totals = sorted((rows[k]["cost"]["total_ms"] or 0) / 1000 for k in keys)
    loads = [sum(c.get("load_duration_ms") or 0 for c in raw[k].get("llm_calls") or []) / 1000 for k in keys]
    n = len(keys)
    latent = {k: s["latent_errors"] for k, s in stops.items() if s["latent_errors"]}
    excl = [k for k in keys if k not in flagged]
    return {
        "items": n,
        "classes": dict(classes),
        "normal_ci": R13.wilson(classes[NORMAL], n),
        "silent_wrong_items": [k for k in keys if rows[k]["v4"] == WRONG],
        "excluding_flagged": {"items": len(excl), "classes": dict(Counter(rows[k]["v4"] for k in excl)),
                              "U": len([k for k in excl if k in u_items]), "R": len([k for k in excl if k in r_items])},
        "U": {"items": len(u_items), "list": u_items},
        "R": {"items": len(r_items), "by_kind": dict(Counter(f for v in r_items.values() for f in v)), "list": r_items},
        "U_or_R_items": len(set(u_items) | set(r_items)),
        "stops": {"items": len(stops), "with_latent_error": latent,
                  "unjudgeable": [k for k, s in stops.items() if s["latent_errors"] is None]},
        "refusal": refusal,
        "refusal_not_accurate": sorted(k for k, r in refusal_items.items() if not r["accurate"]),
        "cost": {"latency_median_s": round(statistics.median(totals), 1) if totals else None,
                 "latency_p90_s": round(totals[int(0.9 * (n - 1))], 1) if totals else None,
                 "model_load_s_total": round(sum(loads), 1),
                 "items_with_model_load": sum(1 for x in loads if x > 1.0),
                 "repair_calls": sum(rows[k]["cost"]["repair_calls"] for k in keys),
                 "failed_llm_calls": sum(rows[k]["cost"]["failed_calls"] for k in keys),
                 "truncated": sum(rows[k]["cost"]["truncated"] for k in keys)},
    }


def variation(rows_a, raw_a, rows_b, raw_b, keys):
    out = {"first_grounding": Counter(), "final_grounding": Counter(), "calls_changed": [], "class_changed": {},
           "first_semantic": [], "final_semantic": []}
    for k in keys:
        fa, fb = first_grounding(raw_a[k]), first_grounding(raw_b[k])
        change = grounding_change(fa, fb)
        out["first_grounding"][change] += 1
        if change == "semantic":
            out["first_semantic"].append(k)
        change = grounding_change(raw_a[k].get("grounding"), raw_b[k].get("grounding"))
        out["final_grounding"][change] += 1
        if change == "semantic":
            out["final_semantic"].append(k)
        if calls_of(raw_a[k]) != calls_of(raw_b[k]):
            out["calls_changed"].append(k)
        if rows_a[k]["v4"] != rows_b[k]["v4"]:
            out["class_changed"][k] = f"{rows_a[k]['v4']}→{rows_b[k]['v4']}"
    out["first_grounding"] = dict(out["first_grounding"])
    out["final_grounding"] = dict(out["final_grounding"])
    out["normal_gained"] = sum(1 for k in keys if rows_b[k]["v4"] == NORMAL != rows_a[k]["v4"])
    out["normal_lost"] = sum(1 for k in keys if rows_a[k]["v4"] == NORMAL != rows_b[k]["v4"])
    out["normal_mcnemar_p"] = R13.mcnemar(out["normal_gained"], out["normal_lost"])
    return out


def load_run(path):
    rows, raw = {}, {}
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    gold_file = data["meta"].get("gold_file", "")
    set_name = SET_BY_FILE.get(gold_file)
    if set_name is None:
        raise SystemExit(f"정답 파일에 맞는 셋 이름이 없다: {gold_file}")
    _, part = E.axes_rows(str(path))
    source = {r["id"]: r for r in data["rows"]}
    for row in part:
        key = f"{set_name}/{row['id']}"
        rows[key], raw[key] = row, source[row["id"]]
    return rows, raw, data["meta"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", nargs=2, action="append", default=[], metavar=("NAME", "FILE"))
    parser.add_argument("--pair", nargs=2, action="append", default=[], metavar=("A", "B"))
    parser.add_argument("--retro", action="store_true")
    parser.add_argument("--json", default="")
    args = parser.parse_args()
    audit = json.loads((HERE.parent / "grounding_v13" / "label_audit.json").read_text(encoding="utf-8"))
    flagged = set(audit["policy_ambiguous"]) | set(audit.get("ambiguous", [])) | set(audit.get("questionable", []))
    loaded = {}
    if args.retro:
        for name in R13.DEV_SOURCES:
            rows, raw = R13.load_sources(R13.DEV_SOURCES[name])
            loaded[f"v13dev_{name}"] = (rows, raw, {})
        for name, d in (("B", "b"), ("T2PC", "t2pc")):
            rows, raw = R13.load_sources([str(ROOT / f"evaluation/grounding_v13/runs/final/{d}")])
            loaded[f"v13final_{name}"] = (rows, raw, {})
    for name, path in args.run:
        loaded[name] = load_run(path)
    report = {"runs": {}, "pairs": {}}
    for name, (rows, raw, meta) in loaded.items():
        keys = sorted(rows)
        s = summarize(rows, raw, keys, flagged)
        s["run_settings"] = meta.get("run_settings")
        s["isolation"] = (meta.get("pipeline") or {}).get("isolation")
        report["runs"][name] = s
    for a, b in args.pair:
        keys = sorted(set(loaded[a][0]) & set(loaded[b][0]))
        report["pairs"][f"{a}|{b}"] = variation(loaded[a][0], loaded[a][1], loaded[b][0], loaded[b][1], keys)
    if args.json:
        Path(args.json).write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    for name, s in report["runs"].items():
        print(f"== {name} ({s['items']}) {s.get('isolation')} {s.get('run_settings')}")
        print(f"   {s['classes']}  U {s['U']['items']}  R {s['R']['items']} {s['R']['by_kind']}  U∪R {s['U_or_R_items']}")
        print(f"   refusal {s['refusal']}  stops {s['stops']['items']} latent {s['stops']['with_latent_error']}")
        print(f"   excl_flagged {s['excluding_flagged']}  cost {s['cost']}")
    for name, d in report["pairs"].items():
        print(f"== {name}: first {d['first_grounding']} final {d['final_grounding']} calls_changed {len(d['calls_changed'])}"
              f" class_changed {len(d['class_changed'])} +{d['normal_gained']} -{d['normal_lost']}")
        print("   ", d["class_changed"])


if __name__ == "__main__":
    main()
