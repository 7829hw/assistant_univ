"""x12_tree.tree_logprobs가 x12_score.string_logprob(순차 계산)과 같은 값을 주는지(CPU, 모델 없음, test_x12의 가짜 어휘·분포).
    python -m unittest test_x12_tree -v   (이 디렉터리에서)
"""
import unittest

import x12_score as X
import x12_tree as T
from test_x12 import VOCAB, Fake, dist

TARGETS = [b'"},', b'"}]', b'"},{"concept":"LOCATION"']


class TT(unittest.TestCase):
    def test_same_as_sequential(self):
        cands = X.Candidates(VOCAB)
        got, stats = T.tree_logprobs(dist(()), TARGETS, cands, lambda items: [dist(p + (t,)) for p, t in items])
        for s, g in zip(TARGETS, got):
            f = Fake()
            self.assertAlmostEqual(g, X.string_logprob(s, dist(()), f.branch, cands), places=12)
        self.assertGreater(stats["tree_nodes"], 0)

    def test_prune_same(self):
        cands = X.Candidates(VOCAB)
        old = X.PRUNE
        try:
            X.PRUNE = T.PRUNE = -6.0
            got, _ = T.tree_logprobs(dist(()), TARGETS, cands, lambda items: [dist(p + (t,)) for p, t in items])
            for s, g in zip(TARGETS, got):
                self.assertAlmostEqual(g, X.string_logprob(s, dist(()), Fake().branch, cands), places=12)
        finally:
            X.PRUNE = T.PRUNE = old


if __name__ == "__main__":
    unittest.main()
