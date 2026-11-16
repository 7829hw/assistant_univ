"""x12_score.string_logprob·prep_writers.cut_point 단위 테스트(CPU, 모델 없음).

가짜 어휘와 이력에 따라 정해지는 가짜 분포로, 문자열 접두 확률을 모든 token 열을 펼친 전수 계산과 비교한다.
    python -m unittest test_x12 -v   (이 디렉터리에서)
"""
import contextlib
import hashlib
import itertools
import math
import unittest

import prep_writers as PW
import x12_score as X

VOCAB = [b'"', b'"}', b'"},', b'"},{"', b'}', b']', b'],"', b']}', b',', b',{"', b'{"', b'concept', b'":"', b'LOC', b'ATION',
         b'LOCATION', b'a', b'"c']


def dist(history):
    """이력(token id 튜플) → 로그 확률 벡터(결정적)."""
    w = [int(hashlib.sha256(repr((history, i)).encode()).hexdigest()[:6], 16) / 2 ** 24 + 0.05 for i in range(len(VOCAB))]
    z = sum(w)
    return [math.log(x / z) for x in w]


class Fake:
    def __init__(self):
        self.hist = ()

    def branch(self, i):
        outer = self

        @contextlib.contextmanager
        def cm():
            saved = outer.hist
            outer.hist = saved + (i,)
            try:
                yield dist(outer.hist)
            finally:
                outer.hist = saved
        return cm()


def brute(s, max_len=8):
    """모든 token 열을 펼쳐, 처음으로 길이 ≥ len(s)가 되는 시점에 s로 시작하면 그 열의 확률을 더한다."""
    total = 0.0

    def rec(hist, text, lp):
        nonlocal total
        logp = dist(hist)
        for i, b in enumerate(VOCAB):
            t = text + b
            if len(t) >= len(s):
                if t.startswith(s):
                    total += math.exp(lp + logp[i])
            elif s.startswith(t) and len(hist) < max_len:
                rec(hist + (i,), t, lp + logp[i])
    rec((), b"", 0.0)
    return math.log(total) if total > 0 else -math.inf


class T(unittest.TestCase):
    def setUp(self):
        self.cands = X.Candidates(VOCAB)

    def check(self, s):
        f = Fake()
        got = X.string_logprob(s, dist(()), f.branch, self.cands)
        self.assertAlmostEqual(got, brute(s), places=9)

    def test_close(self):
        self.check(b'"}]')

    def test_cont(self):
        self.check(b'"},')

    def test_loc(self):
        self.check(b'"},{"concept":"LOCATION"')

    def test_partition(self):
        # tail 뒤 한 글자의 확률 합은 tail의 확률을 넘지 않는다
        f = Fake()
        tail = X.string_logprob(b'"}', dist(()), f.branch, self.cands)
        parts = [X.string_logprob(b'"}' + bytes([c]), dist(()), f.branch, self.cands) for c in range(256)]
        self.assertLessEqual(sum(math.exp(p) for p in parts if p > -math.inf), math.exp(tail) + 1e-12)
        self.assertAlmostEqual(sum(math.exp(p) for p in parts if p > -math.inf), math.exp(tail), places=9)

    def test_cut(self):
        plan = ('{"concepts":[{"concept":"AMOUNT","id":"c1","text":"요금"},{"concept":"EVENT","id":"c2","subtype":"operation"}'
                ',{"concept":"LOCATION","id":"c3","value":{"name":"대구","region":""}}],"factors":{}}')
        c, end = PW.cut_point(plan)
        self.assertEqual(plan[c:end + 1], '"}')
        self.assertEqual(plan[end + 1], ",")
        plan2 = '{"concepts":[{"concept":"AMOUNT","value":{"a":"}"}},{"concept":"EVENT","value":{"x":"y"}}],"factors":{}}'
        c, end = PW.cut_point(plan2)
        self.assertEqual(plan2[c:end + 1], '"}}')
        self.assertEqual(plan2[end + 1], "]")


if __name__ == "__main__":
    unittest.main()
