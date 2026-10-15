# -*- coding: utf-8 -*-
"""canonical 계층(W5): semantics ↔ Full·Partial 렌더링과 검증 사슬. LLM을 부르지 않는다."""
import copy
import unittest

from grounding.canonical import semantic_key, semantics_from_full, view
from grounding.full_renderer import render_full
from grounding.partial_renderer import render_partial
from grounding.validation import validate_semantics

QUESTION = "지난달 동성로에서 평균 속도를 알려줘."
FULL = {"concepts": [{"id": "place_1", "text": "동성로", "concept": "LOCATION", "subtype": "place", "role": "SUBCOND", "source": "user",
                      "value": {"name": "동성로", "region": ""}},
                     {"id": "passage", "concept": "EVENT", "subtype": "passage", "role": "SUPPORT", "source": "implicit"},
                     {"id": "speed", "text": "평균 속도", "concept": "AMOUNT", "subtype": "speed", "role": "MEASURE", "source": "implicit"}],
        "factors": {"date": "last_month", "aggregation": "avg"}}


class CanonicalTest(unittest.TestCase):
    def test_partial_render_drops_structure_and_event(self):
        partial = render_partial(semantics_from_full(FULL))
        self.assertEqual(partial, {"concepts": [{"text": "동성로", "subtype": "place", "value": {"name": "동성로", "region": ""}},
                                                {"text": "평균 속도", "subtype": "speed"}],
                                   "factors": {"date": "last_month", "aggregation": "avg"}})

    def test_full_render_round_trips_semantics(self):
        sem = semantics_from_full(FULL)
        self.assertEqual(semantics_from_full(render_full(sem)), sem)
        self.assertEqual(semantic_key(semantics_from_full(render_full(sem))), semantic_key(sem))
        self.assertEqual(sem["event"], "passage")

    def test_non_inferable_role_is_kept(self):
        payload = copy.deepcopy(FULL)
        payload["concepts"][0]["role"] = "EXTENT"
        sem = semantics_from_full(payload)
        self.assertEqual(sem["nodes"][0]["role_override"], "EXTENT")
        self.assertEqual(render_partial(sem)["concepts"][0]["role"], "EXTENT")
        self.assertEqual(render_full(sem)["concepts"][0]["role"], "EXTENT")

    def test_view_lists_measure_and_conditions(self):
        out = view(semantics_from_full(FULL))
        self.assertEqual(out["measure"], {"subtype": "speed", "text": "평균 속도"})
        self.assertIn({"subtype": "date", "span": None, "value": "last_month", "od_role": None}, out["conditions"])
        self.assertEqual(out["aggregation"], "avg")

    def test_validation_chain_full_and_partial_agree(self):
        result = validate_semantics(semantics_from_full(FULL), QUESTION)
        self.assertTrue(result["ok"])
        self.assertTrue(result["mock_same"])
        self.assertEqual([tool for tool, _ in result["mock_full"]["calls"]], ["get_place_scope", "get_passage_metrics"])


if __name__ == "__main__":
    unittest.main()
