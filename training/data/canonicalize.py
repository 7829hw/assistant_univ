"""Explicit planner contract serialization, separate from runtime to_dict()."""
import copy
import json

from geoflow import aggregation
from training.data.aggregation_flat import to_flat
from geoflow.grounding import Grounding

SCHEMA_VERSION = "geoflow-planner-flat-training-v1"
CONCEPT_KEYS = {"id", "text", "concept", "subtype", "role", "source", "value", "attributes", "od_role"}


def canonical_json(value):
    # Reject dates, sets, NaN and non-JSON objects rather than stringify them.
    def check(item):
        if isinstance(item, dict):
            if any(not isinstance(key, str) for key in item):
                raise ValueError("JSON object keys must be strings")
            for child in item.values():
                check(child)
        elif isinstance(item, list):
            for child in item:
                check(child)
        elif item is not None and not isinstance(item, (str, int, float, bool)):
            raise ValueError(f"Non-JSON value: {type(item).__name__}")
    check(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def check_shape(payload, *, structured=False):
    canonical_json(payload)
    if not isinstance(payload, dict):
        raise ValueError("Planner output must be an object")
    if "unsupported" in payload:
        if payload != {"unsupported": True} or payload["unsupported"] is not True:
            raise ValueError("Unsupported target must be exactly {unsupported: true}")
        return
    if set(payload) != {"concepts", "factors"}:
        raise ValueError("Planner target requires only concepts and factors")
    if not isinstance(payload["concepts"], list) or not isinstance(payload["factors"], dict):
        raise ValueError("concepts must be a list; factors must be an object")
    for concept in payload["concepts"]:
        if not isinstance(concept, dict) or set(concept) - CONCEPT_KEYS:
            raise ValueError("Invalid concept shape or internal concept fields")
        if not isinstance(concept.get("id"), str) or not concept["id"].strip():
            raise ValueError("Concept id must be a nonempty string")
    if "aggregation_plan" in payload or "aggregation_plan" in payload["factors"] and not structured:
        raise ValueError("Structured aggregation is forbidden in the flat training corpus")
    if structured and "aggregation_plan" in payload["factors"]:
        if set(payload["factors"]) & set(aggregation.FLAT_KEYS):
            raise ValueError("Mixed flat/structured annotation")


def planner_payload(grounding):
    if not isinstance(grounding, Grounding):
        return copy.deepcopy(grounding)
    if grounding.aggregation_plan is not None:
        raise ValueError("Convert structured source explicitly before serialization")
    concepts = []
    for item in grounding.concepts:
        raw = {"id": item.id, "concept": item.concept.value, "subtype": item.subtype,
               "role": item.role.value, "source": item.source.value}
        if item.text:
            raw["text"] = item.text
        if item.value is not None:
            raw["value"] = copy.deepcopy(item.value)
        if item.attributes:
            raw["attributes"] = dict(item.attributes)
        concepts.append(raw)
    return {"concepts": concepts, "factors": dict(grounding.factors)}


def serialize_planner_target(grounding):
    """JSON only, stable keys/list order/IDs; never serializes runtime metadata.

    Raw payloads can retain semantic errors for rejected targets; vocabulary and
    downstream checks are intentionally performed separately by validation.py.
    """
    payload = planner_payload(grounding)
    check_shape(payload)
    if payload.get("unsupported"):
        return canonical_json(payload)
    ids = [item["id"] for item in payload["concepts"]]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate concept id")
    concepts = []
    for raw in payload["concepts"]:
        raw = {key: value for key, value in raw.items()
               if not (key in {"text", "attributes"} and not value)
               and not (key == "value" and value is None)}
        raw.setdefault("source", "implicit")
        if "od_role" in raw:
            raw["attributes"] = {**raw.get("attributes", {}), "od_role": raw.pop("od_role")}
        concepts.append(raw)
    concepts.sort(key=lambda c: canonical_json({k: v for k, v in c.items() if k != "id"}))
    for index, concept in enumerate(concepts, 1):
        concept["id"] = f"c{index}"
    return canonical_json({"concepts": concepts, "factors": payload["factors"]})


def semantic_key(payload, *, infer_events=False):
    """Ignore arbitrary IDs and surface text; retain values, roles, source and OD."""
    raw = json.loads(serialize_planner_target(payload))
    if raw.get("unsupported"):
        return canonical_json(raw)
    concepts = [{k: v for k, v in c.items() if k not in {"id", "text"}} for c in raw["concepts"]]
    if infer_events and not any(c.get("concept") == "EVENT" for c in concepts):
        from geoflow.operator_mapping import event_subtype_for
        from geoflow.types import CoreConcept
        measures = [c for c in concepts if c.get("role") == "MEASURE"]
        if len(measures) == 1:
            try:
                event = event_subtype_for(CoreConcept(measures[0]["concept"]), measures[0]["subtype"])
            except ValueError:
                event = None
            if event:
                concepts.append({"concept": "EVENT", "subtype": event, "role": "SUPPORT", "source": "implicit"})
    concepts.sort(key=canonical_json)
    return canonical_json({"concepts": concepts, "factors": raw["factors"]})


def flatten_source(payload):
    """Lossless structured annotation -> production flat contract, with round trip."""
    check_shape(payload, structured=True)
    raw = copy.deepcopy(payload)
    if raw.get("unsupported") or "aggregation_plan" not in raw["factors"]:
        return raw
    rest, spec = aggregation.split_plan(raw["factors"])
    rest.update(to_flat(spec))
    raw["factors"] = rest
    return raw
