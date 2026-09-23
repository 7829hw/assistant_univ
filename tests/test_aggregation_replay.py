# -*- coding: utf-8 -*-
"""H1 재생 판정과, 그 결론을 만든 census 수치를 못박는다."""

import json
import unittest
from pathlib import Path

import aggregation_replay as R
import failure_census as C

RUN_DIR = Path(__file__).resolve().parent.parent / "evaluation" / "prompt_ab" / \
    "20260924_005520_census_head"


class RuleTest(unittest.TestCase):
    def test_h0_and_h1(self):
        cases = (
            ({"bucket": "month", "aggregation": "sum", "rollup": "avg"}, False, False),
            ({"bucket": "month", "rollup": "avg"}, False, True),
            ({"aggregation": "avg"}, False, False),
            ({"rollup": "avg"}, True, True),
            ({"bucket": "month", "aggregation": "max"}, True, True),
            ({}, False, False),
        )
        for factors, h0, h1 in cases:
            with self.subTest(factors=factors):
                self.assertEqual(R.h0_rejects(factors), h0)
                self.assertEqual(R.h1_rejects(factors), h1)


class CensusReplayTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rows = [json.loads(line) for line in
                (RUN_DIR / "census_rows.jsonl").read_text(encoding="utf-8").splitlines()]
        cls.replayed = {row["id"]: row for row in R.replay(rows, C.goldens())}

    def _ids(self, label):
        return sorted(key for key, row in self.replayed.items() if row["h1"] == label)

    def test_h1_catches_the_omitted_inner_reducer_of_f01(self):
        self.assertEqual(self._ids("silent_wrong_h1_rejects"),
                         ["b24_p5", "f01_p0", "f01_p1", "f01_p2", "f01_p3"])
        # b24_p5의 틀린 인자는 taxi_type이다. aggregation을 채워도 오답으로 남는다.
        self.assertEqual(self.replayed["b24_p5"]["arg_mismatches"],
                         [["taxi_type", "private", None]])

    def test_h1_does_not_address_the_repaired_b24_p3(self):
        """첫 grounding은 H0이 이미 막았다. 틀린 값은 재질의가 채운 rollup이다."""
        row = self.replayed["b24_p3"]
        self.assertEqual(row["h1"], "already_rejected_by_h0")
        self.assertEqual(row["initial_stages"],
                         {"bucket": "month", "aggregation": "max", "rollup": None})
        self.assertEqual(row["arg_mismatches"], [["rollup", "max", "sum"]])

    def test_h1_rejects_groundings_that_are_correct_for_their_question(self):
        """f03·b21_p4의 질문에는 안쪽 집계 표현이 없다. f01과 구조가 같다."""
        self.assertEqual(self._ids("correct_h1_newly_rejects"),
                         ["b21_p4", "f02_p1", "f03_p0", "f03_p1", "f03_p2", "f03_p3"])
        for key in ("f03_p0", "f01_p0"):
            self.assertEqual(self.replayed[key]["initial_stages"]["aggregation"], None)
            self.assertEqual(self.replayed[key]["initial_stages"]["rollup"] is not None, True)

    def test_the_outer_reducer_is_written_as_aggregation(self):
        """H0이 막은 17건은 모두 바깥 집계 값을 aggregation에 적은 경우다."""
        rows = [row for row in self.replayed.values() if row["h1"] == "already_rejected_by_h0"]
        self.assertEqual(len(rows), 17)
        for row in rows:
            with self.subTest(id=row["id"]):
                self.assertIsNone(row["initial_stages"]["rollup"])
                self.assertEqual(row["initial_stages"]["aggregation"],
                                 row["expected_stages"]["rollup"])


if __name__ == "__main__":
    unittest.main()
