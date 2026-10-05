"""Reproducible, single semantic edits; no JSON corruption or tool/graph outputs."""
import copy
import random

from training.data.canonicalize import serialize_planner_target


def mutations(payload, *, seed=42):
    candidates = []
    def add(kind, path, value=None, *, remove=False):
        raw = copy.deepcopy(payload)
        node = raw
        for key in path[:-1]:
            node = node[key]
        before = copy.deepcopy(node.get(path[-1])) if isinstance(node, dict) else copy.deepcopy(node[path[-1]])
        if remove:
            del node[path[-1]]
        else:
            node[path[-1]] = value
        if serialize_planner_target(raw) != serialize_planner_target(payload):
            candidates.append({"payload": raw, "negative_type": kind,
                               "negative_details": {"path": list(path), "before": before, "after": value,
                                                    "operation": "remove" if remove else "replace"},
                               "mutation_source": "synthetic"})
    if payload.get("unsupported"):
        # Explicitly documented generic wrong support, never a fabricated graph.
        candidates.append({"payload": {"concepts": [
            {"id": "event", "concept": "EVENT", "subtype": "operation", "role": "SUPPORT", "source": "implicit"},
            {"id": "measure", "concept": "AMOUNT", "subtype": "revenue", "role": "MEASURE", "source": "implicit"}],
            "factors": {"aggregation": "avg"}}, "negative_type": "unsupported_forced_support",
            "negative_details": {"replacement": "generic revenue grounding for unsupported question"},
            "mutation_source": "synthetic"})
    else:
        candidates.append({"payload": {"unsupported": True}, "negative_type": "supported_false_refusal",
                           "negative_details": {"replacement": "unsupported"}, "mutation_source": "synthetic"})
        for i, concept in enumerate(payload["concepts"]):
            base = ("concepts", i)
            if concept["role"] == "MEASURE":
                alternate = {"revenue": "operating_days", "operating_days": "revenue", "fare": "revenue",
                             "speed": "rpm", "rpm": "speed", "trip_count": "passage_count",
                             "passage_count": "trip_count", "active_taxi_ratio": "vacant_ratio",
                             "vacant_ratio": "active_taxi_ratio", "active_taxi_count": "operating_days"}.get(concept["subtype"])
                if alternate:
                    add("measure_confusion", (*base, "subtype"), alternate)
                add("concept_confusion", (*base, "concept"), "PROPORTION" if concept["concept"] == "AMOUNT" else "AMOUNT")
                add("measure_omission", base, remove=True)
                add("role_measure_to_support", (*base, "role"), "SUPPORT")
            if concept["concept"] == "EVENT":
                add("event_subtype_confusion", (*base, "subtype"),
                    "trip" if concept["subtype"] != "trip" else "operation")
                add("role_support_to_measure", (*base, "role"), "MEASURE")
                # EVENT omission is valid when registry infers it; do not label it an error.
            if concept["source"] == "implicit":
                add("source_confusion", (*base, "source"), "user")
            elif concept["source"] == "user":
                add("source_confusion", (*base, "source"), "implicit")
            if concept["role"] == "SUBCOND":
                add("role_subcond_to_cond", (*base, "role"), "COND")
            if concept["concept"] == "LOCATION" and concept["role"] != "MEASURE":
                add("location_omission", base, remove=True)
                if isinstance(concept.get("value"), dict):
                    add("location_confusion", (*base, "value", "name"),
                        "부산" if concept["value"].get("name") != "부산" else "대구")
                    add("region_hallucination", (*base, "value", "region"), "서울")
                od = concept.get("attributes", {}).get("od_role")
                if od:
                    add("od_role_omission", (*base, "attributes", "od_role"), remove=True)
                    add("od_role_confusion", (*base, "attributes", "od_role"),
                        {"pickup": "dropoff", "dropoff": "pickup", "both": "pickup"}[od])
        od_indices = [i for i, c in enumerate(payload["concepts"])
                      if c.get("attributes", {}).get("od_role") in {"pickup", "dropoff"}]
        if {payload["concepts"][i]["attributes"]["od_role"] for i in od_indices} == {"pickup", "dropoff"}:
            swapped = copy.deepcopy(payload)
            for i in od_indices:
                current = swapped["concepts"][i]["attributes"]["od_role"]
                swapped["concepts"][i]["attributes"]["od_role"] = "dropoff" if current == "pickup" else "pickup"
            candidates.append({"payload": swapped, "negative_type": "od_pickup_dropoff_swap",
                               "negative_details": {"paths": [f"concepts.{i}.attributes.od_role" for i in od_indices]},
                               "mutation_source": "synthetic"})
        factors = payload["factors"]
        for name in sorted(factors):
            kind = {"bucket": "bucket_omission", "rollup": "rollup_omission",
                    "vicinity": "vicinity_omission"}.get(name, "factor_omission")
            add(kind, ("factors", name), remove=True)
        for name, value in {"date": "20260101", "taxi_type": "private", "aggregation": "sum",
                            "vicinity": True}.items():
            if name not in factors:
                add("factor_hallucination", ("factors", name), value)
        if "date" in factors:
            add("temporal_scope_confusion", ("factors", "date"),
                "last_year" if factors["date"] != "last_year" else "last_month")
        for name in ("aggregation", "rollup"):
            if name in factors:
                add("aggregation_confusion", ("factors", name),
                    {"avg": "sum", "sum": "avg", "min": "max", "max": "min", "med": "avg"}[factors[name]])
        if factors.get("bucket"):
            add("bucket_confusion", ("factors", "bucket"), "month" if factors["bucket"] == "week" else "week")
        if factors.get("aggregation") and factors.get("rollup") and factors["aggregation"] != factors["rollup"]:
            raw = copy.deepcopy(payload)
            raw["factors"]["aggregation"], raw["factors"]["rollup"] = factors["rollup"], factors["aggregation"]
            candidates.append({"payload": raw, "negative_type": "aggregation_stage_swap",
                               "negative_details": {"paths": ["factors.aggregation", "factors.rollup"]},
                               "mutation_source": "synthetic"})
    unique = {}
    for candidate in candidates:
        key = serialize_planner_target(candidate["payload"])
        unique.setdefault(key, candidate)
    result = list(unique.values())
    random.Random(seed).shuffle(result)
    return result
