"""Localize missing place lookups using recorded model and pipeline evidence."""
from collections import Counter
from geoflow.planner import PlannerError, parse_planner_json

POSTPROCESS_STAGES = {"composition", "template", "validation", "compile"}


def place_key(args):
    return args.get("name"), args.get("region") or "", bool(args.get("include_vicinity"))


def model_plan(row):
    calls = [c for c in row.get("llm_calls") or [] if c.get("kind") in ("plan", "repair")]
    trace = row.get("planner_trace") or {}
    if (len(calls) != 1 or calls[0].get("kind") != "plan" or calls[0].get("failed")
        or not isinstance(calls[0].get("content"), str)
        or any(a.get("repair_attempted") for a in trace.get("attempts") or [])
        or any(c.get("finish_reason") == "length" or c.get("done_reason") == "length"
               for c in row.get("hf_calls") or [])):
        return None
    try:
        concepts = parse_planner_json(calls[0]["content"]).get("concepts")
    except PlannerError:
        return None
    if isinstance(concepts, list) and all(isinstance(c, dict) for c in concepts):
        return concepts
    return None


def attribution_flags(row, gold):
    flags = set()
    trace = row.get("planner_trace") or {}
    stage = trace.get("error_stage")
    if row.get("error_code") == "UNHANDLED_EXCEPTION" or trace.get("exception"):
        flags.add("evaluator_or_transport_exception")
    elif stage in POSTPROCESS_STAGES:
        flags.add("deterministic_stage_failure")
    elif stage in ("execution", "answer", "planner"):
        flags.add(f"{stage}_stage_failure")

    required = Counter(place_key(c["args"]) for c in gold.get("gold") or [] if c["tool"] == "get_place_scope")
    calls = row.get("calls") or []
    if (not required or gold.get("expected_outcome", "answered") != "answered"
        or (row.get("outcome") != "answered" and not calls)):
        return flags
    observed = Counter(place_key(c["args"]) for c in calls if c["tool"] == "get_place_scope")
    if not required - observed:
        return flags
    flags.add("missing_get_place_scope")
    if observed:
        return flags | {"wrong_or_partial_place_lookup"}
    flags.add("zero_place_lookups")
    concepts = model_plan(row)
    if concepts is None:
        return flags | {"place_origin_ambiguous"}
    locations = [c for c in concepts if c.get("concept") == "LOCATION"]
    if not locations:
        return flags | {"model_plan_location_omission"}
    emitted = Counter()
    for concept in locations:
        value = concept.get("value")
        if not isinstance(value, dict) or concept.get("subtype") != "place" or not isinstance(value.get("name"), str):
            return flags | {"place_origin_ambiguous"}
        emitted[place_key(value)] += 1
    if emitted != required or any(key[2] for key in required):
        return flags | {"place_origin_ambiguous"}
    place_diff = next((d for d in row.get("grounding_diffs") or [] if len(d) == 3 and d[0] == "places"), None)
    if place_diff and not place_diff[2]:
        return flags | {"place_lost_during_grounding"}
    if row.get("grounding_ok") is True:
        return flags | {"place_plan_present_lookup_missing"}
    return flags | {"place_origin_ambiguous"}
