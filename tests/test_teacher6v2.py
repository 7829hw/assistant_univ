import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_006/teacher"))
import teacher6v2 as T  # noqa: E402

TRIP_DT = {"nodes": [{"subtype": "place", "text": "부산", "value": {"name": "부산", "region": ""}, "attributes": {"od_role": "pickup"}},
                     {"subtype": "trip_count", "text": "건수"}], "event": "trip",
           "factors": {"dimension": "emd", "dimension_target": "dropoff", "order": "top", "limit": 3}, "unsupported": None}
PASS_OCC = {"nodes": [{"subtype": "place", "text": "광안리", "value": {"name": "광안리"}}, {"subtype": "passage_count", "text": "통행량"}],
            "event": "passage", "factors": {"taxi_status": "occupied", "vicinity": True}, "unsupported": None}
BUCKET = {"nodes": [{"subtype": "operating_days", "text": "운행 일수"}], "event": "operation",
          "factors": {"aggregation": "avg", "bucket": "month", "rollup": "max"}, "unsupported": None}


class ParseTest(unittest.TestCase):
    def test_trip_dt(self):
        c = "측정: 실차 운행 건수\n끝: 승차\n묶음: 읍면동별, 하차 쪽\n집계: 없음, 순위 상위 3\n주변: 아니오"
        r = T.check_conclusion(c, TRIP_DT)
        self.assertTrue(r["pass"], r)

    def test_wrong_side_fails(self):
        c = "측정: 실차 운행 건수\n끝: 승차\n묶음: 읍면동별, 승차 쪽\n집계: 없음, 순위 상위 3\n주변: 아니오"
        r = T.check_conclusion(c, TRIP_DT)
        self.assertFalse(r["pass"])
        self.assertFalse(r["items"]["묶음"])

    def test_status_and_vicinity(self):
        ok = "측정: 통행량, 상태 실차\n끝: 없음\n묶음: 없음\n집계: 없음\n주변: 예"
        self.assertTrue(T.check_conclusion(ok, PASS_OCC)["pass"])
        no_status = "측정: 통행량\n끝: 없음\n묶음: 없음\n집계: 없음\n주변: 예"
        self.assertFalse(T.check_conclusion(no_status, PASS_OCC)["items"]["측정"])
        trip = "측정: 실차 운행 건수\n끝: 없음\n묶음: 없음\n집계: 없음\n주변: 예"
        self.assertFalse(T.check_conclusion(trip, PASS_OCC)["pass"])

    def test_bucket_rollup(self):
        c = "**측정**: 운행 일수\n끝: 없음\n묶음: 월 단위로 먼저 집계\n집계: 평균, 다시 최대\n주변: 아니오"
        self.assertTrue(T.check_conclusion(c, BUCKET)["pass"])
        c2 = "측정: 운행 일수\n끝: 없음\n묶음: 월 단위로 먼저 집계\n집계: 최대, 다시 평균\n주변: 아니오"
        self.assertFalse(T.check_conclusion(c2, BUCKET)["pass"])

    def test_missing_line(self):
        r = T.check_conclusion("측정: 통행량\n끝: 없음", PASS_OCC)
        self.assertFalse(r["parsed_all_lines"])
        self.assertFalse(r["pass"])

    def test_field_names(self):
        self.assertFalse(T.check_field_names("dimension_target은 pickup", "")["pass"])
        self.assertTrue(T.check_field_names("승차한 곳으로 나눈다", "측정: 통행량")["pass"])

    def test_prompt_has_no_field_words(self):
        self.assertTrue(T.check_field_names(T.instruction_text(), "")["pass"])


if __name__ == "__main__":
    unittest.main()
