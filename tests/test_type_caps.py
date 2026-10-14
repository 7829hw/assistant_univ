"""Decision 88 (AC): type-cell caps that bring the TV against the dev distribution under a target."""
import importlib.util
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("type_caps", ROOT / "sft_dpo_inventory/pilot_004_prep/type_caps.py")
T = importlib.util.module_from_spec(spec)
spec.loader.exec_module(T)


def tv(counts, dev):
    n = sum(counts.values())
    return 0.5 * sum(abs(counts.get(k, 0) / n - dev.get(k, 0)) for k in set(dev) | set(counts))


class CapsTest(unittest.TestCase):
    dev = {"a": 0.5, "b": 0.3, "c": 0.2}

    def test_caps_meet_target_and_are_maximal(self):
        available = {"a": 10, "b": 40, "c": 30}
        m, caps = T.caps_for(available, self.dev, 0.09)
        self.assertEqual(sum(caps.values()), m)
        self.assertTrue(all(caps[c] <= available[c] for c in available))
        self.assertLessEqual(tv(caps, self.dev), 0.09 + 1e-9)
        self.assertGreater(T.min_tv(available, self.dev, m + 1), 0.09)   # one more record breaks the target

    def test_no_cap_needed_when_already_close(self):
        available = {"a": 50, "b": 30, "c": 20}
        m, caps = T.caps_for(available, self.dev, 0.09)
        self.assertEqual(m, 100)
        self.assertEqual(caps, available)

    def test_cell_absent_from_dev_counts_against_target(self):
        available = {"a": 50, "b": 30, "c": 20, "x": 50}
        m, caps = T.caps_for(available, self.dev, 0.09)
        self.assertLessEqual(tv(caps, self.dev), 0.09 + 1e-9)
        self.assertLessEqual(caps["x"] / m, 0.09 + 1e-9)

    def test_apply_caps_round_robins_questions(self):
        items = [{"q": q, "i": i} for q in ("q1", "q2", "q3") for i in range(4)]
        kept = T.apply_caps(items, lambda r: "a", lambda r: r["q"], {"a": 6})
        self.assertEqual(len(kept), 6)
        self.assertEqual(sorted(Counter(r["q"] for r in kept).values()), [2, 2, 2])
        self.assertEqual(kept, [r for r in items if r in kept])   # original order kept

    def test_apply_caps_is_deterministic(self):
        items = [{"q": f"q{k}", "i": i} for k in range(7) for i in range(3)]
        a = T.apply_caps(items, lambda r: "a", lambda r: r["q"], {"a": 5})
        b = T.apply_caps(items, lambda r: "a", lambda r: r["q"], {"a": 5})
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
