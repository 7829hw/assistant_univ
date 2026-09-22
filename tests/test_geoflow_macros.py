# -*- coding: utf-8 -*-
"""Macro 정의 로딩과 IO port 호환성 테스트.

여기서 검증하는 것은 "질문을 어떤 유형으로 분류했는가"가 아니라 "조각이
서로 연결 가능한가"다.
"""

import sys
import unittest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from geoflow.errors import MacroError  # noqa: E402
from geoflow.macros import (  # noqa: E402
    DEFAULT_MACRO_DIR,
    MacroLibrary,
    PortSpec,
    load_macro,
)
from geoflow.types import (  # noqa: E402
    CoreConcept,
    FunctionalRole,
    NodeSource,
    Subtype,
)

EXPECTED_MACROS = (
    "EVENT_TO_MEASURE",
    "OD_EVENT_TO_MEASURE",
    "PLACE_TO_SCOPE",
    "SCOPE_TO_PLACE",
)


def write_macro(directory, name, body):
    path = Path(directory) / f"{name}.yaml"
    path.write_text(body, encoding="utf-8")
    return path


MINIMAL_MACRO = """
name: MINIMAL
description: 테스트용 조각.
inputs:
  place:
    concept: LOCATION
    subtypes: [place]
outputs:
  scope:
    concept: LOCATION
    subtypes: [scope]
concepts:
  - key: scope
    role: COND
    source: tool
    subtype: scope
transformations:
  - id: resolve
    inputs: [place]
    output: scope
"""


class MacroLoadingTest(unittest.TestCase):
    """A. macro loading."""

    @classmethod
    def setUpClass(cls):
        cls.library = MacroLibrary.from_directory()

    def test_library_loads_every_macro(self):
        self.assertEqual(sorted(self.library.names), sorted(EXPECTED_MACROS))

    def test_input_and_output_ports_are_parsed(self):
        macro = self.library.require("PLACE_TO_SCOPE")
        self.assertEqual(sorted(macro.input_ports), ["place"])
        self.assertEqual(sorted(macro.output_ports), ["scope"])
        self.assertEqual(
            macro.input_ports["place"].types,
            frozenset({(CoreConcept.LOCATION, Subtype.PLACE)}),
        )
        self.assertEqual(
            macro.output_ports["scope"].types,
            frozenset({
                (CoreConcept.LOCATION, Subtype.SCOPE),
                (CoreConcept.LOCATION, Subtype.VICINITY_SCOPE),
            }),
        )

    def test_optional_port_is_marked(self):
        macro = self.library.require("EVENT_TO_MEASURE")
        self.assertTrue(macro.input_ports["event"].required)
        self.assertFalse(macro.input_ports["area"].required)
        self.assertEqual(macro.required_input_ports, ("event",))

    def test_multi_concept_output_port_is_parsed(self):
        macro = self.library.require("EVENT_TO_MEASURE")
        types = macro.output_ports["measure"].types
        self.assertIn((CoreConcept.AMOUNT, Subtype.FARE), types)
        self.assertIn((CoreConcept.PROPORTION, Subtype.VACANT_RATIO), types)
        # AMOUNT/vacant_ratio 같은 실재하지 않는 조합은 계약에 없다.
        self.assertNotIn((CoreConcept.AMOUNT, Subtype.VACANT_RATIO), types)

    def test_no_macro_declares_a_final_node(self):
        """macro는 완성된 workflow가 아니므로 최종 node를 갖지 않는다."""
        for path in sorted(DEFAULT_MACRO_DIR.glob("*.yaml")):
            self.assertNotIn(
                "final_node", path.read_text(encoding="utf-8"), path.name,
            )

    def test_no_macro_names_a_semantic_operator(self):
        """operator 선택은 macro가 아니라 operator mapping이 한다."""
        for path in sorted(DEFAULT_MACRO_DIR.glob("*.yaml")):
            body = path.read_text(encoding="utf-8")
            self.assertNotIn("operator:", body, path.name)

    def test_unknown_concept_is_rejected(self):
        with self.assertRaises(MacroError) as caught:
            self._load_modified("concept: LOCATION", "concept: TAXI")
        self.assertIn("허용되지 않은 값", caught.exception.detail)

    def test_unknown_subtype_is_rejected(self):
        with self.assertRaises(MacroError) as caught:
            self._load_modified("subtypes: [place]", "subtypes: [부동산]")
        self.assertIn("없는 subtype", caught.exception.detail)

    def test_subtype_from_another_concept_is_rejected(self):
        """이름은 있으나 그 concept에 속하지 않는 조합도 막는다."""
        with self.assertRaises(MacroError) as caught:
            self._load_modified("subtypes: [place]", "subtypes: [speed]")
        self.assertIn("LOCATION에 없는 subtype", caught.exception.detail)

    def test_unknown_role_is_rejected(self):
        with self.assertRaises(MacroError) as caught:
            self._load_modified("role: COND", "role: FILTER")
        self.assertIn("허용되지 않은 값", caught.exception.detail)

    def test_user_source_is_rejected_for_produced_node(self):
        """macro가 만든 node를 사용자 입력이라고 선언할 수 없다."""
        with self.assertRaises(MacroError) as caught:
            self._load_modified("source: tool", "source: user")
        self.assertIn("source", caught.exception.detail)

    def test_final_node_key_is_rejected(self):
        with self.assertRaises(MacroError) as caught:
            self._load_modified(
                "transformations:", "final_node: scope\ntransformations:",
            )
        self.assertIn("final_node", caught.exception.detail)

    def test_operator_key_is_rejected(self):
        with self.assertRaises(MacroError) as caught:
            self._load_modified(
                "transformations:", "operator: PASSAGE_METRIC\ntransformations:",
            )
        self.assertIn("operator", caught.exception.detail)

    def test_unproducible_output_type_is_rejected(self):
        """어떤 operator도 만들 수 없는 출력은 정의 단계에서 막는다."""
        with self.assertRaises(MacroError) as caught:
            self._load_modified(
                "outputs:\n  scope:\n    concept: LOCATION\n    subtypes: [scope]",
                "outputs:\n  scope:\n    concept: NETWORK\n    subtypes: [road_edge]",
            )
        self.assertIn("만들 수 없는", caught.exception.detail)

    def test_transformation_referencing_unknown_input_is_rejected(self):
        with self.assertRaises(MacroError) as caught:
            self._load_modified("inputs: [place]", "inputs: [지역]")
        self.assertIn("정의되지 않은 입력", caught.exception.detail)

    def test_output_port_without_producer_is_rejected(self):
        with self.assertRaises(MacroError) as caught:
            self._load_modified("output: scope", "output: other")
        self.assertIn("concepts 정의가 없", caught.exception.detail)

    def test_duplicate_macro_name_is_rejected(self):
        macro = load_macro(self._write(MINIMAL_MACRO))
        with self.assertRaises(MacroError) as caught:
            MacroLibrary([macro, macro])
        self.assertIn("중복", caught.exception.detail)

    def test_empty_directory_is_rejected(self):
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(MacroError):
                MacroLibrary.from_directory(directory)

    # -- helper -----------------------------------------------------------

    def _write(self, body):
        import tempfile

        directory = tempfile.mkdtemp()
        self.addCleanup(
            lambda: __import__("shutil").rmtree(directory, ignore_errors=True),
        )
        return write_macro(directory, "minimal", body)

    def _load_modified(self, old, new):
        body = MINIMAL_MACRO.replace(old, new)
        self.assertNotEqual(body, MINIMAL_MACRO, "치환 대상이 없습니다.")
        return load_macro(self._write(body))


class PortCompatibilityTest(unittest.TestCase):
    """B. port compatibility."""

    @classmethod
    def setUpClass(cls):
        cls.library = MacroLibrary.from_directory()

    def test_place_connects_to_place_to_scope_input(self):
        port = self.library.require("PLACE_TO_SCOPE").input_ports["place"]
        self.assertTrue(port.accepts(
            CoreConcept.LOCATION, Subtype.PLACE, role=FunctionalRole.SUBCOND,
        ))

    def test_scope_is_rejected_by_place_input(self):
        port = self.library.require("PLACE_TO_SCOPE").input_ports["place"]
        self.assertFalse(port.accepts(CoreConcept.LOCATION, Subtype.SCOPE))

    def test_role_outside_allowed_set_is_rejected(self):
        port = self.library.require("PLACE_TO_SCOPE").input_ports["place"]
        self.assertFalse(port.accepts(
            CoreConcept.LOCATION, Subtype.PLACE, role=FunctionalRole.MEASURE,
        ))

    def test_place_to_scope_output_feeds_event_to_measure_area(self):
        produced = self.library.require("PLACE_TO_SCOPE").output_ports["scope"]
        area = self.library.require("EVENT_TO_MEASURE").input_ports["area"]
        for concept, subtype in produced.types:
            self.assertTrue(
                area.accepts(concept, subtype, role=FunctionalRole.COND),
                f"{concept.value}/{subtype}",
            )

    def test_event_port_rejects_other_concepts(self):
        port = self.library.require("EVENT_TO_MEASURE").input_ports["event"]
        self.assertFalse(port.accepts(CoreConcept.AMOUNT, Subtype.SPEED))
        self.assertTrue(port.accepts(
            CoreConcept.EVENT, Subtype.PASSAGE, role=FunctionalRole.SUPPORT,
        ))

    def test_od_ports_are_distinguished_by_attribute(self):
        macro = self.library.require("OD_EVENT_TO_MEASURE")
        pickup = macro.input_ports["pickup"]
        dropoff = macro.input_ports["dropoff"]
        self.assertTrue(pickup.accepts(
            CoreConcept.LOCATION, Subtype.SCOPE,
            role=FunctionalRole.COND, attributes={"od_role": "pickup"},
        ))
        self.assertFalse(pickup.accepts(
            CoreConcept.LOCATION, Subtype.SCOPE,
            role=FunctionalRole.COND, attributes={"od_role": "dropoff"},
        ))
        self.assertTrue(dropoff.accepts(
            CoreConcept.LOCATION, Subtype.SCOPE,
            role=FunctionalRole.COND, attributes={"od_role": "dropoff"},
        ))

    def test_plain_area_port_rejects_od_scope(self):
        """승하차 구분이 붙은 범위는 포함 조건으로 쓰이지 않는다."""
        area = self.library.require("EVENT_TO_MEASURE").input_ports["area"]
        self.assertTrue(area.accepts(CoreConcept.LOCATION, Subtype.SCOPE))
        self.assertFalse(area.accepts(
            CoreConcept.LOCATION, Subtype.SCOPE,
            attributes={"od_role": "pickup"},
        ))

    def test_output_subtype_follows_vicinity_factor(self):
        node = self.library.require("PLACE_TO_SCOPE").concepts["scope"]
        self.assertEqual(node.resolve_subtype({}), Subtype.SCOPE)
        self.assertEqual(node.resolve_subtype({"vicinity": False}), Subtype.SCOPE)
        self.assertEqual(
            node.resolve_subtype({"vicinity": True}), Subtype.VICINITY_SCOPE,
        )

    def test_produced_node_source_is_always_tool(self):
        for macro in self.library.all():
            for spec in macro.concepts.values():
                self.assertIn(
                    spec.source, (NodeSource.TOOL, NodeSource.DERIVED),
                    f"{macro.name}.{spec.key}",
                )

    def test_producing_lookup_is_deterministic(self):
        first = self.library.producing(CoreConcept.AMOUNT, Subtype.TRIP_COUNT)
        second = self.library.producing(CoreConcept.AMOUNT, Subtype.TRIP_COUNT)
        self.assertEqual(
            [item.name for item in first], [item.name for item in second],
        )
        self.assertEqual(
            sorted(item.name for item in first),
            ["EVENT_TO_MEASURE", "OD_EVENT_TO_MEASURE"],
        )

    def test_unrelated_type_has_no_producer(self):
        self.assertEqual(
            self.library.producing(CoreConcept.NETWORK, Subtype.ROAD_EDGE), (),
        )

    def test_port_describe_is_readable(self):
        spec = PortSpec(
            name="area",
            types=frozenset({(CoreConcept.LOCATION, Subtype.SCOPE)}),
            required=False,
        )
        self.assertEqual(spec.describe(), "area: LOCATION/scope (optional)")


if __name__ == "__main__":
    unittest.main()
