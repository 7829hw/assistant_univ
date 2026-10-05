"""Reuse production parsers, composition and all G1-G7 checks."""
import copy

from agent_graph import extract_scopes
from geoflow.composer import MacroComposer
from geoflow.errors import GeoFlowError
from geoflow.grounding import drop_unsupported_regions, parse_grounding
from geoflow.validator import validate
from training.data.canonicalize import check_shape


def assess(payload, question, *, normalize=True, composer=None):
    result = dict(parse_ok=False, compose_ok=None, validation_ok=None,
                  validation_codes=[], error_code=None, outcome=None)
    try:
        check_shape(payload)
        if payload.get("unsupported"):
            # Production recognizes refusal before parse_grounding; no graph exists.
            result.update(parse_ok=True, outcome="unsupported")
            return result
        grounding = parse_grounding(copy.deepcopy(payload), question, normalize=normalize)
        if normalize:
            drop_unsupported_regions(grounding)
        result.update(parse_ok=True, compose_ok=False)
        plan = (composer or MacroComposer()).compose(grounding)
        result.update(compose_ok=True, validation_ok=False)
        report = validate(plan, user_scopes=set(extract_scopes(question)))
        result.update(validation_ok=report.ok, validation_codes=report.failed_rules(),
                      outcome="answered" if report.ok else "validation_failed")
        result["macros"] = list(plan.applied_macros)
        result["operators"] = [step.operator for step in plan.transformations]
    except (GeoFlowError, ValueError, TypeError) as error:
        result["error_code"] = getattr(error, "code", "INVALID_TRAINING_STRUCTURE")
        result["error_detail"] = str(error)
    return result


def chosen_ok(result):
    return result["parse_ok"] and (result["outcome"] == "unsupported" or result["validation_ok"] is True)
