# -*- coding: utf-8 -*-
"""학습 대상 조합(qwen3:8b + T2PC 코드·prompt)의 실제 오류 유형 분포. 기존 평가 기록만 읽는다(모델 호출 없음).

    python sft_dpo_inventory/error_types.py

- 기록: grounding_v13 ``model_name_only``와 같은 세 arm을 같은 136문항에서 읽는다.
    q8_T2PC = evaluation/grounding_v13/runs/small/q8_t2pc (qwen3:8b + T2PC 코드·prompt 87048d0c, condition_check)
    T2PC, B = grounding_v13 report.py의 DEV_SOURCES(개발 비교와 같은 출처)
- 분류: v4 축(evaluate_vendor100.score_semantic)과 grounding_v13 report.py의 U1–U4 정의를 그대로 쓴다.
    조용한 오답 = v4 "오답", 용납할 수 없는 실패 = U 표시가 하나라도 있는 문항(답한 문항만 해당),
    안전한 실패 = v4 "실행 실패"·"부당한 거부"(답을 내지 않음), 정당한 거부 = v4 "정당한 거부".
- grounding 차이: 기록의 ``grounding_diffs``(최종 grounding = 정규화·조건 계층·재질의 뒤)를 키별로 센다.
  같은 비교를 첫 응답(llm_calls[0], 정규화·조건 계층 전)에도 적용해 단계별로 나눈다.
- 질문 문장은 보호 대상이므로 산출물에 넣지 않는다. 문항 id와 건수만 남긴다.
"""
import importlib.util
import json
import sys
from collections import Counter, defaultdict

from _common import ROOT, write_output

HERE = ROOT / "evaluation" / "grounding_v13"


def _load_report():
    spec = importlib.util.spec_from_file_location("report_v13", HERE / "report.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["report_v13"] = module
    spec.loader.exec_module(module)
    return module


R = _load_report()
import evaluate_vendor100 as EV  # noqa: E402
from geoflow.planner import parse_planner_json  # noqa: E402

ARMS = {
    "q8_T2PC": ["evaluation/grounding_v13/runs/small/q8_t2pc"],
    "T2PC": R.DEV_SOURCES["T2PC"],
    "B": R.DEV_SOURCES["B"],
}
SAFE = ("실행 실패", "부당한 거부")


def diff_keys(diffs):
    return sorted({d if isinstance(d, str) else d[0] for d in diffs or []})


def first_response_diffs(key, row, raw):
    calls = [c for c in raw.get("llm_calls") or [] if c.get("kind") == "plan"]
    if not calls:
        return ["no_call"]
    try:
        payload = parse_planner_json(calls[0].get("content") or "")
    except Exception:  # noqa: BLE001 - 첫 응답이 JSON이 아님
        return ["raw_not_json"]
    if payload.get("unsupported"):
        return ["raw_unsupported"]
    try:
        _, diffs = EV.grounding_check(R._item(key, row), payload)
    except Exception as error:  # noqa: BLE001
        return [f"raw_view_error:{type(error).__name__}"]
    return diff_keys(diffs)


def report_class(row, flags):
    if flags:
        return "용납할 수 없는 실패"
    if row["v4"] == "오답":
        return "조용한 오답"
    if row["v4"] in SAFE:
        return "안전한 실패"
    return row["v4"]


def main():
    audit = json.loads((HERE / "label_audit.json").read_text(encoding="utf-8"))
    ambiguous = set(audit["policy_ambiguous"]) | set(audit.get("ambiguous", []))
    loaded = {name: R.load_sources(sources) for name, sources in ARMS.items()}
    common = sorted(set.intersection(*[set(rows) for rows, _ in loaded.values()]))
    reference = json.loads((HERE / "runs" / "model_name_only_report.json").read_text(encoding="utf-8"))

    out = {"common_items": len(common), "policy_ambiguous_in_common": sorted(ambiguous & set(common)), "arms": {}}
    for name, (rows, raw) in loaded.items():
        summary = R.summarize(rows, raw, common, ambiguous)
        ref = reference["arms"]["B" if name == "B" else name]
        reproduced = (summary["classes"] == ref["classes"]
                      and summary["unacceptable"]["list"] == ref["unacceptable"]["list"]
                      and summary["silent_wrong_items"] == ref["silent_wrong_items"])
        per_item = {}
        final_keys, first_keys = Counter(), Counter()
        keys_by_class = defaultdict(Counter)
        items_by_key = defaultdict(list)
        for key in common:
            row, source = rows[key], raw[key]
            flags = R.unacceptable(key, row, source)
            cls = report_class(row, flags)
            final = diff_keys(source.get("grounding_diffs"))
            first = first_response_diffs(key, row, source)
            per_item[key] = {"v4": row["v4"], "report_class": cls, "u_flags": flags, "outcome": row.get("outcome"),
                             "error_code": row.get("error_code"), "final_grounding_diffs": final,
                             "first_response_diffs": first, "policy_ambiguous": key in ambiguous}
            if row["v4"] != "정상 답변":
                for k in final:
                    final_keys[k] += 1
                    keys_by_class[cls][k] += 1
                    items_by_key[k].append(key)
                for k in first:
                    first_keys[k] += 1
        layer = Counter()
        for key, item in per_item.items():
            first_ok = item["first_response_diffs"] == []
            final_ok = item["final_grounding_diffs"] == []
            layer[f"first={'ok' if first_ok else 'diff'}→final={'ok' if final_ok else 'diff'}"] += 1
        out["arms"][name] = {
            "reproduces_model_name_only_report": reproduced,
            "classes_v4": summary["classes"],
            "report_classes": dict(Counter(i["report_class"] for i in per_item.values())),
            "report_class_items": {c: sorted(k for k, i in per_item.items() if i["report_class"] == c)
                                   for c in ("조용한 오답", "용납할 수 없는 실패", "안전한 실패")},
            "silent_wrong_excluding_policy_ambiguous": summary["silent_wrong_excluding_policy_ambiguous"],
            "unacceptable_by_kind": summary["unacceptable"]["by_kind"],
            "unacceptable_flag_counts": dict(Counter(f for i in per_item.values() for f in i["u_flags"])),
            "measure_errors": summary["measure_errors"], "measure_error_items": summary["measure_error_items"],
            "condition_layer": summary["layer"], "condition_layer_bad": summary["layer_bad"],
            "refusal": summary["refusal"],
            "final_diff_keys_non_normal": dict(final_keys.most_common()),
            "final_diff_keys_by_report_class": {c: dict(v.most_common()) for c, v in keys_by_class.items()},
            "final_diff_key_items": {k: sorted(v) for k, v in items_by_key.items()},
            "first_response_diff_keys_non_normal": dict(first_keys.most_common()),
            "grounding_layer_transitions": dict(layer),
            "error_codes_non_normal": dict(Counter(i["error_code"] for i in per_item.values()
                                                   if i["v4"] != "정상 답변" and i["error_code"])),
            "by_set": summary["by_set"],
            "items": per_item,
        }
    path, digest = write_output("error_types_v13_model_name_only.json", out)
    brief = {name: {k: v for k, v in arm.items() if k not in ("items", "final_diff_key_items")}
             for name, arm in out["arms"].items()}
    print(json.dumps({"common_items": out["common_items"], "arms": brief}, ensure_ascii=False, indent=1))
    print(f"\nwrote {path} sha256={digest}")


if __name__ == "__main__":
    main()
