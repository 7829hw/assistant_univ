import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PF = ROOT / "sft_dpo_inventory/pilot_006/protected_final"
sys.path.insert(0, str(PF))


class ProtectedFinalToolTest(unittest.TestCase):
    """가짜 문항 5개로 validate.py를 돌려 문제 행을 잡고, 출력에 질문·호출 내용이 없는지 본다."""

    def test_validate_fake_items_reports_numbers_only(self):
        import make_fake
        with tempfile.TemporaryDirectory() as d:
            x = Path(d) / "fake.xlsx"
            subprocess.run([sys.executable, str(PF / "make_fake.py"), str(x)], check=True, capture_output=True)
            r = subprocess.run([sys.executable, str(PF / "validate.py"), "--xlsx", str(x), "--test"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 1)
        out = json.loads(r.stdout)
        self.assertIn("unknown_tool", out["row_problems"]["5"])
        self.assertIn("difficulty_code", out["row_problems"]["5"])
        self.assertNotIn("3", out["row_problems"])
        for q in make_fake.QUESTIONS:
            self.assertNotIn(q, r.stdout)
        for frag in ("get_place_scope", "동대구역", "수성구"):
            self.assertNotIn(frag, r.stdout)


if __name__ == "__main__":
    unittest.main()
