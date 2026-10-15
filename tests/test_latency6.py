# -*- coding: utf-8 -*-
"""pilot_006 지연 도구(C8): 서버 로그 prefix cache 적중률 파서(가짜 서버 시험은 latency6.py --test-fake)."""
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "sft_dpo_inventory/pilot_006/latency"))
import latency6 as L  # noqa: E402


class HitRateTest(unittest.TestCase):
    def test_window(self):
        log = ("(APIServer pid=1) INFO 10-15 14:25:09 [loggers.py:315] Engine 000: Avg prompt throughput: 0.0 tokens/s, Prefix cache hit rate: 95.5%\n"
               "(APIServer pid=1) INFO 10-15 14:26:09 [loggers.py:315] Engine 000: Avg prompt throughput: 4.2 tokens/s, Prefix cache hit rate: 96.0%\n")
        with tempfile.NamedTemporaryFile("w", suffix=".log", delete=False) as f:
            f.write(log)
        r = L.hit_rates(f.name, datetime(2026, 10, 15, 14, 25, 0), datetime(2026, 10, 15, 14, 25, 30))
        self.assertEqual(r, {"samples": 1, "last": 95.5, "max": 95.5})


if __name__ == "__main__":
    unittest.main()
