# -*- coding: utf-8 -*-
"""Query YAML의 id는 원문 문자열 그대로여야 한다(YAML 1.1 8진수 해석 금지)."""

import tempfile
import unittest
from pathlib import Path

from query_loader import load_queries, select_queries

BASE_DIR = Path(__file__).resolve().parent.parent


class QueryIdTest(unittest.TestCase):
    def test_vendor_ids_keep_their_leading_zeros(self):
        queries = load_queries(BASE_DIR / "assistant_univ_questions_100_v3.yaml")
        self.assertEqual([q["id"] for q in queries], [f"{n:03d}" for n in range(1, 101)])
        self.assertEqual(queries[9]["question"], "전국 택시의 평균 요금은?")
        self.assertEqual([q["id"] for q in select_queries(queries, ["010"])], ["010"])

    def test_octal_looking_and_plain_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "q.yaml"
            path.write_text("- id: 010\n  question: a\n- id: 008\n  question: b\n"
                            "- id: 7\n  question: c\n- id: q01\n  question: d\n",
                            encoding="utf-8")
            self.assertEqual([q["id"] for q in load_queries(path)], ["010", "008", "7", "q01"])
            self.assertEqual(load_queries(path)[0]["eval_id"], "010")


if __name__ == "__main__":
    unittest.main()
