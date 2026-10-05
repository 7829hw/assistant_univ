# -*- coding: utf-8 -*-
"""thor reviewed gold v001–v003이 현재(dev-v2, T2PC) 계약에서 유효한지 확인한다. 모델 호출·학습 없음.

    python sft_dpo_inventory/check_reviewed_gold.py

확인하는 경로(모두 현재 저장소의 production 코드를 import해 쓴다. 라벨은 고치지 않는다):
  A. thor ``training.data.validation.assess``와 같은 순서: parse_grounding(normalize=False) → compose → validate.
  B. 같은 경로 normalize=True(+ drop_unsupported_regions). thor가 학습 자료 기록에 쓴 판정 경로다.
  C. T2PC planner 경로: stub client가 학습 target 문자열을 그대로 돌려주게 하고 ``GeoFlowPlanner.plan``
     (condition_check=True, normalize_grounding=True, 기준일 2026-09-25) → compose → validate(mock Tool 목록)
     → compile_plan(mock·legacy 프로필). 학습된 모델이 target을 정확히 출력했을 때 운영 경로가 하는 일이다.
  D. C와 같되 condition_check=False. C와 D의 차이가 조건 계층의 효과다.
thor assess의 ``check_shape``(학습 직렬화 형태 검사)는 thor 전용 모듈이라 여기서 하지 않는다. 재질의(repair)는 하지 않는다.
"""
import copy
import json
from collections import Counter
from datetime import date

from _common import (CORPORA, T2PC_PROMPT_SHA, THOR_PROMPT_SHA, THOR_REF, production_prompt, sha256_bytes,
                     thor_json, thor_yaml, write_output)

from agent_graph import extract_scopes
from geoflow import providers
from geoflow.compiler import compile_plan
from geoflow.composer import MacroComposer
from geoflow.errors import GeoFlowError
from geoflow.grounding import drop_unsupported_regions, parse_grounding
from geoflow.planner import GeoFlowPlanner
from geoflow.validator import validate

#: 평가 harness의 고정 기준일(paraphrase_corpus.EVALUATION_REFERENCE_DATE).
REFERENCE_DATE = date(2026, 9, 25)
#: 측정값 정의가 실차로 고정된 operator의 measure(operator_registry ``inherent_conditions``).
GROUPING_CUES = ("구별", "동별", "시도별", "시군구별", "읍면동별", "요일별", "지역별")


def _executor():
    from build import build
    from tool_executor import ToolExecutor
    from tool_handlers import get_tool_handlers
    tools, _ = build()
    return ToolExecutor(tools=tools, handlers=get_tool_handlers("mock"))


EXECUTOR = _executor()
PROFILE = providers.profile_for()


class StubClient:
    """학습 target 문자열을 그대로 돌려주는 client. 모델을 부르지 않는다."""
    model = "stub-gold"

    def __init__(self, text):
        self.text = text

    def chat(self, messages, **kwargs):
        return {"message": {"content": self.text}, "done_reason": "stop"}


def signature(grounding):
    """의미 비교 키: local id·text·순서를 무시하고 concept/subtype/role/source/value/attributes와 factor를 본다."""
    concepts = sorted(json.dumps({"concept": c.concept.value, "subtype": c.subtype, "role": c.role.value,
                                  "source": c.source.value, "value": c.value, "attributes": c.attributes},
                                 ensure_ascii=False, sort_keys=True) for c in grounding.concepts)
    return {"concepts": concepts, "factors": dict(sorted(grounding.factors.items()))}


def _err(error):
    return {"code": getattr(error, "code", type(error).__name__), "detail": str(error)[:300]}


def assess(payload, question, *, normalize):
    """thor assess와 같은 단계(check_shape 제외)."""
    out = {"stage": None, "parse_ok": False, "compose_ok": None, "validation_ok": None, "validation_codes": [],
           "error_code": None, "outcome": None, "signature": None}
    try:
        if payload.get("unsupported"):
            out.update(parse_ok=True, outcome="unsupported", stage="unsupported")
            return out
        grounding = parse_grounding(copy.deepcopy(payload), question, normalize=normalize)
        if normalize:
            drop_unsupported_regions(grounding)
        out.update(parse_ok=True, compose_ok=False, stage="compose", signature=signature(grounding))
        plan = MacroComposer().compose(grounding)
        out.update(compose_ok=True, validation_ok=False, stage="validate")
        report = validate(plan, user_scopes=set(extract_scopes(question)))
        out.update(validation_ok=report.ok, validation_codes=report.failed_rules(),
                   outcome="answered" if report.ok else "validation_failed", stage="ok" if report.ok else "validate",
                   macros=list(plan.applied_macros), operators=[s.operator for s in plan.transformations])
    except (GeoFlowError, ValueError, TypeError) as error:
        out["error_code"] = getattr(error, "code", "INVALID_TRAINING_STRUCTURE")
        out["error_detail"] = str(error)[:300]
        if out["stage"] is None:
            out["stage"] = "parse"
    return out


def planner_path(text, question, *, condition_check):
    """T2PC 운영 경로(재질의 없음). 첫 실패 단계와 코드, 조건 계층 기록을 돌려준다."""
    out = {"stage": None, "error": None, "signature": None, "condition_actions": {}, "corrections": [],
           "operators": None, "validation_codes": []}
    planner = GeoFlowPlanner(client=StubClient(text), condition_check=condition_check,
                             normalize_grounding=True, clock=lambda: REFERENCE_DATE)
    try:
        output = planner.plan(question)
    except GeoFlowError as error:
        out.update(stage="plan", error=_err(error))
        context = getattr(error, "context", {}) or {}
        for key in ("date", "taxi_type", "taxi_status"):
            if isinstance(context.get(key), dict):
                out["condition_actions"][key] = {k: context[key].get(k) for k in ("action", "basis", "llm_value",
                                                                                   "value")}
        return out
    grounding = output.grounding
    out["signature"] = signature(grounding)
    audit = grounding.condition_audit or {}
    for key in ("date", "taxi_type", "taxi_status"):
        record = audit.get(key) or {}
        if record.get("action") not in (None, "none", "confirmed"):
            out["condition_actions"][key] = {k: record.get(k) for k in ("action", "basis", "llm_value", "value")}
    out["corrections"] = audit.get("corrections") or []
    try:
        plan = MacroComposer().compose(grounding)
    except GeoFlowError as error:
        out.update(stage="compose", error=_err(error))
        return out
    out["operators"] = [s.operator for s in plan.transformations]
    report = validate(plan, available_tools=EXECUTOR.tool_names, user_scopes=set(extract_scopes(question)))
    if not report.ok:
        out.update(stage="validate", validation_codes=report.failed_rules())
        return out
    try:
        compile_plan(plan, reference_date=REFERENCE_DATE, contract=PROFILE.contract,
                     date_policy=PROFILE.date_policy, delegation=PROFILE.delegation)
    except GeoFlowError as error:
        out.update(stage="compile", error=_err(error))
        return out
    out["stage"] = "ok"
    return out


def outcome_label(result):
    if result["stage"] == "ok":
        return "ok"
    code = (result.get("error") or {}).get("code") or ",".join(result.get("validation_codes") or [])
    return f"{result['stage']}:{code}"


def contract_flags(payload, question):
    """현재 prompt(87048d0c) 설명과 어긋날 수 있는 라벨 형태. 판정이 아니라 사람 검토 후보 표시다."""
    flags = []
    factors = payload.get("factors") or {}
    measures = [c.get("subtype") for c in payload.get("concepts") or [] if c.get("role") == "MEASURE"]
    if factors.get("taxi_status") == "occupied" and set(measures) & {"trip_count", "fare"}:
        flags.append("taxi_status_occupied_with_trip_or_fare_measure")
    if factors.get("bucket") and not factors.get("dimension") and any(cue in question for cue in GROUPING_CUES):
        flags.append("bucket_without_dimension_but_grouping_cue")
    if factors.get("dimension") and set(measures) & {"trip_count"} and "dimension_target" not in factors:
        flags.append("trip_dimension_without_dimension_target(=both)")
    return flags


def check_one(text, question):
    payload = json.loads(text)
    a = assess(payload, question, normalize=False)
    b = assess(payload, question, normalize=True)
    c = planner_path(text, question, condition_check=True)
    d = planner_path(text, question, condition_check=False)
    return {
        "A_normalize_false": a, "B_normalize_true": b, "C_t2pc_path": c, "D_no_condition_check": d,
        "normalization_changed_meaning": (a["signature"] is not None and b["signature"] is not None
                                          and a["signature"] != b["signature"]),
        "condition_layer_changed_meaning": (c["signature"] is not None and d["signature"] is not None
                                            and c["signature"] != d["signature"]),
        "condition_layer_changed_outcome": outcome_label(c) != outcome_label(d),
        "contract_flags": contract_flags(payload, question),
    }


def _question(messages):
    return next(m["content"] for m in messages if m["role"] == "user")


def main():
    corpora = {v: thor_yaml(f"{CORPORA}/reviewed_gold_{v}/reviewed_annotations.yaml")["examples"]
               for v in ("v001", "v002", "v003")}
    index = thor_json(f"{CORPORA}/reviewed_gold_v003/dataset_index.json")
    v003 = {e["id"]: e for e in corpora["v003"]}
    # v003이 v001·v002를 그대로 포함하는지(누적 corpus) 확인한다.
    carried = {v: {"total": len(corpora[v]),
                   "same_in_v003": sum(1 for e in corpora[v] if e["id"] in v003
                                       and v003[e["id"]]["grounding"] == e["grounding"]
                                       and v003[e["id"]]["question"] == e["question"])}
               for v in ("v001", "v002")}

    sft_rows = []
    for split in ("sft_train", "sft_valid"):
        for record in index[split]:
            meta = record["metadata"]
            text = record["messages"][-1]["content"]
            question = _question(record["messages"])
            yaml_item = v003.get(meta["source_record_id"])
            sft_rows.append({
                "split": split, "id": meta["source_record_id"], "batch_item_ids": meta.get("batch_item_ids"),
                "corpus_version": meta.get("corpus_version"), "family": meta.get("family"),
                "tags": meta.get("tags"),
                "target_equals_yaml": yaml_item is not None and json.loads(text) == yaml_item["grounding"],
                "recorded_quality": meta.get("chosen_quality"),
                **check_one(text, question),
            })

    dpo_rows = []
    for split in ("dpo_train", "dpo_valid"):
        for record in index[split]:
            meta = record["metadata"]
            question = _question(record["prompt"])
            chosen, rejected = record["chosen"][0]["content"], record["rejected"][0]["content"]
            rc, rr = check_one(chosen, question), check_one(rejected, question)
            c_sig, r_sig = rc["C_t2pc_path"]["signature"], rr["C_t2pc_path"]["signature"]
            dpo_rows.append({
                "split": split, "id": meta.get("source_record_id"), "batch_item_ids": meta.get("batch_item_ids"),
                "negative_type": meta.get("negative_type"), "negative_category": meta.get("negative_category"),
                "mutation_source": meta.get("mutation_source"),
                "recorded_chosen_quality": meta.get("chosen_quality"),
                "recorded_rejected_quality": meta.get("rejected_quality"),
                "chosen": rc, "rejected": rr,
                "t2pc_outcome": {"chosen": outcome_label(rc["C_t2pc_path"]),
                                 "rejected": outcome_label(rr["C_t2pc_path"])},
                "no_condition_outcome": {"chosen": outcome_label(rc["D_no_condition_check"]),
                                         "rejected": outcome_label(rr["D_no_condition_check"])},
                "t2pc_pair_collapsed": c_sig is not None and c_sig == r_sig,
            })

    def recorded_matches(recorded, current):
        if not recorded:
            return None
        keys = ("parse_ok", "compose_ok", "validation_ok", "error_code", "outcome")
        same = all(recorded.get(k) == current.get(k) for k in keys)
        same &= sorted(recorded.get("validation_codes") or []) == sorted(current.get("validation_codes") or [])
        if recorded.get("operators") is not None and current.get("operators") is not None:
            same &= recorded["operators"] == current["operators"]
        return same

    for row in sft_rows:
        row["recorded_quality_reproduced"] = recorded_matches(row["recorded_quality"], row["B_normalize_true"])
    for row in dpo_rows:
        row["recorded_chosen_reproduced"] = recorded_matches(row["recorded_chosen_quality"],
                                                             row["chosen"]["B_normalize_true"])
        row["recorded_rejected_reproduced"] = recorded_matches(row["recorded_rejected_quality"],
                                                               row["rejected"]["B_normalize_true"])

    def ok(result):
        return result["outcome"] in ("answered", "unsupported")

    summary = {
        "thor_ref": THOR_REF,
        "current_prompt_sha256": sha256_bytes(production_prompt().encode("utf-8")),
        "expected_current_prompt_sha256": T2PC_PROMPT_SHA,
        "thor_prompt_sha256": THOR_PROMPT_SHA,
        "reference_date": REFERENCE_DATE.isoformat(),
        "carried_forward_into_v003": carried,
        "sft": {
            "records": len(sft_rows),
            "by_corpus_version": dict(Counter(r["corpus_version"] for r in sft_rows)),
            "target_equals_yaml": sum(r["target_equals_yaml"] for r in sft_rows),
            "A_pass": sum(ok(r["A_normalize_false"]) for r in sft_rows),
            "B_pass": sum(ok(r["B_normalize_true"]) for r in sft_rows),
            "recorded_quality_reproduced": sum(bool(r["recorded_quality_reproduced"]) for r in sft_rows),
            "normalization_changed_meaning": [r["id"] for r in sft_rows if r["normalization_changed_meaning"]],
            "t2pc_outcomes": dict(Counter(outcome_label(r["C_t2pc_path"]) for r in sft_rows)),
            "no_condition_outcomes": dict(Counter(outcome_label(r["D_no_condition_check"]) for r in sft_rows)),
            "condition_layer_changed_meaning": [r["id"] for r in sft_rows if r["condition_layer_changed_meaning"]],
            "condition_layer_changed_outcome": [r["id"] for r in sft_rows if r["condition_layer_changed_outcome"]],
            "condition_actions": dict(Counter(f"{k}:{v['action']}:{v['basis']}" for r in sft_rows
                                              for k, v in r["C_t2pc_path"]["condition_actions"].items())),
            "contract_flags": {r["id"]: r["contract_flags"] for r in sft_rows if r["contract_flags"]},
            "failures": [{"id": r["id"], "batch": r["batch_item_ids"], "split": r["split"],
                          "A": r["A_normalize_false"].get("error_code") or r["A_normalize_false"]["validation_codes"],
                          "B": r["B_normalize_true"].get("error_code") or r["B_normalize_true"]["validation_codes"],
                          "C": outcome_label(r["C_t2pc_path"])}
                         for r in sft_rows if not (ok(r["A_normalize_false"]) and ok(r["B_normalize_true"])
                                                   and r["C_t2pc_path"]["stage"] == "ok")],
        },
        "dpo": {
            "pairs": len(dpo_rows),
            "by_category": dict(Counter(r["negative_category"] for r in dpo_rows)),
            "chosen_A_pass": sum(ok(r["chosen"]["A_normalize_false"]) for r in dpo_rows),
            "chosen_B_pass": sum(ok(r["chosen"]["B_normalize_true"]) for r in dpo_rows),
            "recorded_chosen_reproduced": sum(bool(r["recorded_chosen_reproduced"]) for r in dpo_rows),
            "recorded_rejected_reproduced": sum(bool(r["recorded_rejected_reproduced"]) for r in dpo_rows),
            "recorded_not_reproduced": [{"id": r["id"], "batch": r["batch_item_ids"],
                                         "chosen": r["recorded_chosen_reproduced"],
                                         "rejected": r["recorded_rejected_reproduced"]}
                                        for r in dpo_rows if not (r["recorded_chosen_reproduced"]
                                                                  and r["recorded_rejected_reproduced"])],
            "t2pc_outcome_pairs": dict(Counter(
                f"{r['negative_category']}|chosen={r['t2pc_outcome']['chosen']}|rejected={r['t2pc_outcome']['rejected']}"
                for r in dpo_rows)),
            "condition_layer_changed": [{"id": r["id"], "batch": r["batch_item_ids"], "type": r["negative_type"],
                                         "chosen": [r["no_condition_outcome"]["chosen"], r["t2pc_outcome"]["chosen"]],
                                         "rejected": [r["no_condition_outcome"]["rejected"],
                                                      r["t2pc_outcome"]["rejected"]],
                                         "chosen_meaning": r["chosen"]["condition_layer_changed_meaning"],
                                         "rejected_meaning": r["rejected"]["condition_layer_changed_meaning"]}
                                        for r in dpo_rows
                                        if r["chosen"]["condition_layer_changed_outcome"]
                                        or r["rejected"]["condition_layer_changed_outcome"]
                                        or r["chosen"]["condition_layer_changed_meaning"]
                                        or r["rejected"]["condition_layer_changed_meaning"]],
            "t2pc_pair_collapsed": [r["id"] for r in dpo_rows if r["t2pc_pair_collapsed"]],
            "contract_flags": {f"{r['id']}|{r['negative_type']}": {"chosen": r["chosen"]["contract_flags"],
                                                                   "rejected": r["rejected"]["contract_flags"]}
                               for r in dpo_rows if r["chosen"]["contract_flags"] or r["rejected"]["contract_flags"]},
        },
    }
    path, digest = write_output("reviewed_gold_check.json", {"summary": summary, "sft": sft_rows, "dpo": dpo_rows})
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    print(f"\nwrote {path} sha256={digest}")


if __name__ == "__main__":
    main()
