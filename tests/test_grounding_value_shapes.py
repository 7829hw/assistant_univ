# -*- coding: utf-8 -*-
"""모델 출력의 값 형식이 틀려도 grounding 입구가 처리되지 않은 예외로 끝나지 않는다.

grounding 입구(``parse_grounding``와 planner의 ``_validate_payload``, 조건 계층 켬·끔)는 성공하거나 grounding 계약
오류(``PlannerError``)만 낸다. 정리 단계(장소 이름 정리, 조건 개념 옮기기, factor 정리, 조건 계층)는 형식이 틀린 값을
"정리 규칙에 해당하지 않음"으로 보고 그대로 넘기고, 형식 검증이 계약 오류로 거부한다.

재현: think를 끈 qwen3:8b가 업체 100 057에서 subtype 없는 OBJECT에 dict 값을 적었고,
``hoist_condition_concepts``가 ``TypeError: unhashable type: 'dict'``로 끝났다
(geoflow/sft-dpo-t2pc sft_dpo_inventory/baseline_conditions_001). 아래 테스트는 그 최소 형태만 쓴다.
"""
import copy
import json
import unittest
from datetime import date

from geoflow.errors import PlannerError
from geoflow.factors import FACTOR_SPECS
from geoflow.grounding import parse_grounding
from geoflow.planner import GeoFlowPlanner

QUESTION = "지난달 동대구역에서 승차한 개인택시 실차 건수를 읍면동별로 많은 순으로 3곳 알려줘"
REFERENCE = date(2026, 9, 25)


def _support(subtype="operation"):
    return {"id": "e", "concept": "EVENT", "subtype": subtype, "role": "SUPPORT", "source": "implicit"}


def _measure(subtype="revenue"):
    return {"id": "m", "concept": "AMOUNT", "subtype": subtype, "role": "MEASURE", "source": "implicit"}


def _place(**extra):
    return {"id": "p", "text": "동대구역", "concept": "LOCATION", "subtype": "place", "role": "SUBCOND",
            "source": "user", "value": {"name": "동대구역", "region": ""}, **extra}


#: 정리 규칙마다 그 규칙에 들어가는 올바른 형식의 출발점.
BASES = {
    "revenue_place": {"concepts": [_place(), _support(), _measure()],
                      "factors": {"date": "last_month", "taxi_type": "private", "aggregation": "avg"}},
    "od_trip": {"concepts": [_place(attributes={"od_role": "pickup"}), _support("trip"), _measure("trip_count")],
                "factors": {"date": "last_month", "dimension": "emd", "dimension_target": "dropoff",
                            "order": "top", "limit": 3}},
    "condition_name": {"concepts": [{"id": "t", "text": "개인택시", "concept": "OBJECT", "subtype": "taxi_type",
                                     "role": "COND", "source": "user", "value": "private"},
                                    _support(), _measure()],
                       "factors": {"date": "last_month"}},
    "condition_value": {"concepts": [{"id": "t", "text": "개인택시", "concept": "OBJECT", "subtype": "",
                                      "role": "COND", "source": "user", "value": "private"},
                                     _support(), _measure()],
                        "factors": {"date": "last_month", "taxi_type": "private"}},
    "unit_word_place": {"concepts": [{"id": "p", "text": "도착 읍면동", "concept": "LOCATION", "subtype": "place",
                                      "role": "SUBCOND", "source": "user", "value": None},
                                     _support("trip"), _measure("trip_count")],
                        "factors": {"date": "last_month", "dimension": "emd"}},
}
SHAPES = {"dict": {"a": 1}, "list": ["x"], "int": 3, "float": 1.5, "bool": True, "null": None,
          "str": "private"}
CONCEPT_FIELDS = ("concept", "subtype", "role", "source", "value", "text", "attributes", "od_role",
                  "attributes.od_role", "value.name", "value.region", "id")


def _entries():
    yield "parse_grounding", lambda payload: parse_grounding(payload, QUESTION)
    yield "parse_grounding(normalize=False)", lambda payload: parse_grounding(payload, QUESTION, normalize=False)
    for condition_check in (False, True):
        planner = GeoFlowPlanner(client=None, condition_check=condition_check, clock=lambda: REFERENCE)
        yield (f"planner(condition_check={condition_check})",
               lambda payload, planner=planner: planner._validate_payload(
                   payload, json.dumps(payload, ensure_ascii=False), QUESTION))


def _mutations():
    for base_name, base in BASES.items():
        for index in range(len(base["concepts"])):
            for field in CONCEPT_FIELDS:
                for shape, value in SHAPES.items():
                    payload = copy.deepcopy(base)
                    concept = payload["concepts"][index]
                    if field.startswith("value."):
                        if not isinstance(concept.get("value"), dict):
                            continue
                        concept["value"][field.split(".", 1)[1]] = copy.deepcopy(value)
                    elif field == "attributes.od_role":
                        concept["attributes"] = {**(concept.get("attributes") or {}), "od_role": copy.deepcopy(value)}
                    else:
                        concept[field] = copy.deepcopy(value)
                    yield f"{base_name}.concepts[{index}].{field}={shape}", payload
        for key in sorted(FACTOR_SPECS) + ["holiday", "aggregation_plan", "unknown_factor"]:
            for shape, value in SHAPES.items():
                payload = copy.deepcopy(base)
                payload["factors"][key] = copy.deepcopy(value)
                yield f"{base_name}.factors.{key}={shape}", payload
        for shape, value in SHAPES.items():
            for container in ("factors", "concepts"):
                payload = copy.deepcopy(base)
                payload[container] = copy.deepcopy(value)
                yield f"{base_name}.{container}={shape}", payload
            payload = copy.deepcopy(base)
            payload["concepts"].append(copy.deepcopy(value))
            yield f"{base_name}.concepts+={shape}", payload


class ReproductionTest(unittest.TestCase):
    """버그 보고의 최소 형태. 고치기 전에는 TypeError로 끝났다."""

    def assert_contract_error(self, payload):
        for name, entry in _entries():
            with self.subTest(entry=name):
                with self.assertRaises(PlannerError):
                    entry(copy.deepcopy(payload))

    def test_object_without_subtype_with_dict_value(self):
        # 057의 형태: subtype이 빈 OBJECT 개념에 dict 값.
        self.assert_contract_error({
            "concepts": [{"id": "taxi", "text": "부산 소속 택시", "concept": "OBJECT", "subtype": "",
                          "role": "COND", "source": "user", "value": {"region": "부산"}},
                         _support(), _measure()],
            "factors": {"date": "20260401-20260430", "aggregation": "avg"}})

    def test_condition_name_subtype_with_dict_or_list_value(self):
        for value in ({"name": "private"}, ["private"]):
            with self.subTest(value=value):
                self.assert_contract_error({
                    "concepts": [{"id": "t", "text": "개인택시", "concept": "OBJECT", "subtype": "taxi_type",
                                  "role": "COND", "source": "user", "value": value},
                                 _support(), _measure()],
                    "factors": {"date": "last_month"}})

    def test_condition_subtype_itself_dict_or_list(self):
        for subtype in ({"taxi_type": "private"}, ["taxi_type"]):
            with self.subTest(subtype=subtype):
                self.assert_contract_error({
                    "concepts": [{"id": "t", "concept": "OBJECT", "subtype": subtype, "role": "COND",
                                  "source": "user", "value": "private"}, _support(), _measure()],
                    "factors": {"date": "last_month"}})


class ValueShapeMutationTest(unittest.TestCase):
    """각 개념 필드·factor에 dict, list, 정수, 실수, bool, null, 문자열을 넣는다. 입구는 성공하거나 PlannerError만 낸다."""

    def test_entry_raises_only_contract_errors(self):
        failures = []
        checked = 0
        for name, payload in _mutations():
            for entry_name, entry in _entries():
                checked += 1
                try:
                    entry(copy.deepcopy(payload))
                except PlannerError:
                    pass
                except Exception as error:  # noqa: BLE001 - 계약 오류가 아닌 예외를 모은다
                    failures.append(f"{entry_name} {name}: {type(error).__name__}: {error}")
        self.assertGreater(checked, 5000)
        self.assertEqual(failures, [], f"{len(failures)}건. 처음 10건:\n" + "\n".join(failures[:10]))


class ValidShapesUnchangedTest(unittest.TestCase):
    """올바른 형식의 입력은 정리 규칙이 그대로 적용된다."""

    def test_condition_concepts_still_move_to_factors(self):
        grounding = parse_grounding(copy.deepcopy(BASES["condition_name"]), QUESTION)
        self.assertEqual(grounding.factors.get("taxi_type"), "private")
        grounding = parse_grounding(copy.deepcopy(BASES["condition_value"]), QUESTION)
        self.assertEqual(grounding.factors.get("taxi_type"), "private")
        self.assertNotIn("t", [concept.id for concept in grounding.concepts])

    def test_unit_word_place_still_dropped_with_dimension(self):
        grounding = parse_grounding(copy.deepcopy(BASES["unit_word_place"]), QUESTION)
        self.assertNotIn("p", [concept.id for concept in grounding.concepts])


if __name__ == "__main__":
    unittest.main()
