# -*- coding: utf-8 -*-
"""pilot_006 teacher 도구(C5): 자동 검사 (a)(b)와 두 arm 레코드 변환. LLM을 부르지 않는다."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_006/teacher"))

import teacher6 as T  # noqa: E402
from grounding.canonical import semantics_from_full  # noqa: E402

FULL = {"concepts": [{"id": "p", "text": "수성구", "concept": "LOCATION", "subtype": "place", "role": "SUBCOND", "source": "user",
                      "value": {"name": "수성구", "region": "대구"}, "attributes": {"od_role": "pickup"}},
                     {"id": "trip", "concept": "EVENT", "subtype": "trip", "role": "SUPPORT", "source": "implicit"},
                     {"id": "m", "concept": "AMOUNT", "subtype": "trip_count", "role": "MEASURE", "source": "implicit"}],
        "factors": {"date": "last_week", "dimension": "emd", "dimension_target": "dropoff"}}
SEM = semantics_from_full(FULL)
GOOD = "수성구에서 손님을 태운 실차 운행을 센다. 결과는 손님을 내려준 곳(하차) 읍면동별로 나눠 보인다. 집계어는 없다. 날짜는 지난주."


class TeacherChecksTest(unittest.TestCase):
    def test_field_names_detected(self):
        self.assertTrue(T.check_field_names(GOOD)["pass"])
        bad = T.check_field_names("The MEASURE is trip_count and od_role is pickup.")
        self.assertFalse(bad["pass"])
        self.assertEqual(bad["found"], ["MEASURE", "od_role", "trip_count"])

    def test_conclusion_matches_and_cues(self):
        ok = T.check_conclusion(GOOD, FULL, SEM)
        self.assertTrue(ok["pass"], ok)
        wrong = dict(FULL, factors={**FULL["factors"], "dimension_target": "pickup"})
        self.assertFalse(T.check_conclusion(GOOD, wrong, SEM)["final_matches_canonical"])
        no_cue = T.check_conclusion("읍면동별로 나눈다.", FULL, SEM)
        self.assertTrue(no_cue["final_matches_canonical"])
        self.assertFalse(no_cue["pass"])

    def test_no_json_fails(self):
        self.assertFalse(T.check_conclusion(GOOD, None, SEM)["pass"])

    def test_arm_records_share_thinking(self):
        recs = T.to_arm_records({"trace_id": "x:teacher6:1", "thinking": GOOD, "model": "qwen3.8:27b"}, SEM, "지난주 대구 수성구에서 태운 손님을 내려준 곳을 읍면동별로", "t2pc:x")
        full, part = recs["full"], recs["partial"]
        self.assertEqual(full["messages"][2]["content"].split("</think>")[0], part["messages"][2]["content"].split("</think>")[0])
        self.assertNotEqual(full["messages"][0]["content"], part["messages"][0]["content"])
        pj = json.loads(part["messages"][2]["content"].split("</think>")[1])
        self.assertTrue(all(set(c) <= {"text", "subtype", "value", "attributes", "concept", "role"} for c in pj["concepts"]))
        self.assertEqual(full["metadata"]["loss_scope"], "full_response")
        self.assertEqual(part["metadata"]["grounding_target"], "partial")


if __name__ == "__main__":
    unittest.main()
