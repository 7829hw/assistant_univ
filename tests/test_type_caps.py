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


class ExemptTest(unittest.TestCase):
    """Decision 92 (AG): exempt groups are kept whole; caps apply to the rest only."""

    def setUp(self):
        self.dev = dict(T.DEVD)
        self.cells = sorted(self.dev)

    def items(self):
        # 질문 q0..q9: 앞 셋은 예외 후보, 모두 같은 칸(분포를 크게 벗어나게) + 나머지 칸 고르게
        out = [{"q": f"x{i}", "c": self.cells[0]} for i in range(3) for _ in range(5)]
        out += [{"q": f"q{i}", "c": c} for i, c in enumerate(self.cells) for _ in range(4)]
        return out

    def test_exempt_items_all_kept(self):
        items = self.items()
        exempt = frozenset({"x0", "x1", "x2"})
        kept, caps, m = T.capped(items, lambda r: r["c"], lambda r: r["q"], 0.09, exempt)
        self.assertEqual(sum(r["q"] in exempt for r in kept), 15)
        rest = [r for r in kept if r["q"] not in exempt]
        self.assertEqual(len(rest), m)
        self.assertLessEqual(tv(Counter(r["c"] for r in rest), self.dev), 0.09 + 1e-9)

    def test_no_exempt_matches_plain_caps(self):
        items = self.items()
        kept, caps, m = T.capped(items, lambda r: r["c"], lambda r: r["q"], 0.09)
        m2, caps2 = T.caps_for(Counter(r["c"] for r in items), self.dev, 0.09)
        self.assertEqual((caps, m), (caps2, m2))
        self.assertEqual(len(kept), m2)

    def test_exempt_may_leave_tv_over_target(self):
        items = self.items()
        exempt = frozenset({"x0", "x1", "x2"})
        kept, _, _ = T.capped(items, lambda r: r["c"], lambda r: r["q"], 0.09, exempt)
        # 예외 때문에 전체 TV가 목표를 넘을 수 있고, 도구는 그 값을 줄이려고 예외 항목을 빼지 않는다
        self.assertEqual(sum(r["q"] in exempt for r in kept), 15)
        self.assertGreater(tv(Counter(r["c"] for r in kept), self.dev), 0.0)


if __name__ == "__main__":
    unittest.main()
