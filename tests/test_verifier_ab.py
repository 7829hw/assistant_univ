# -*- coding: utf-8 -*-
"""사전 등록한 H0 vs V0 판정 규칙과 관측 주석을 못박는다."""

import json
import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("ASSISTANT_TOOL_PROVIDER", "mock")

import evaluate_prompt_ab as A
import paraphrase_corpus as P
import verifier_ab as VA
from geoflow.composer import MacroComposer
from geoflow.macros import MacroLibrary
from tests.test_prompt_ab_harness import FakeLLM, FakeServer, make_reset

OP = {"id": "op", "concept": "EVENT", "subtype": "operation", "role": "SUPPORT",
      "source": "implicit"}


def summary(**overrides):
    base = {"v0_only_silent": [], "invariant_violations": [], "fp_intents": [],
            "tp_intents": ["v05", "v09"], "tp_families": ["B_taxi_type", "C_date_time"],
            "precision": 1.0, "fallback_rate": 0.02}
    return {**base, **overrides}


class DecisionTest(unittest.TestCase):
    def test_clear_detector(self):
        self.assertEqual(VA.decide(summary())["case"], "A")

    def test_one_false_rejection_intent_needs_review(self):
        self.assertEqual(VA.decide(summary(fp_intents=["v08"], precision=0.95))["case"],
                         "A_REVIEW")

    def test_false_rejections_discard(self):
        self.assertEqual(VA.decide(summary(fp_intents=["v04", "v08"]))["case"], "C")
        self.assertEqual(VA.decide(summary(precision=0.8))["case"], "C")

    def test_low_recall(self):
        self.assertEqual(VA.decide(summary(tp_intents=["v05"]))["case"], "D")
        self.assertEqual(VA.decide(summary(tp_intents=[], tp_families=[],
                                           precision=None))["case"], "D")

    def test_single_family(self):
        self.assertEqual(VA.decide(summary(tp_families=["A_aggregation"]))["case"], "B")

    def test_unreliable_verifier(self):
        self.assertEqual(VA.decide(summary(fallback_rate=0.2))["case"], "UNRELIABLE")

    def test_a_new_plan_is_an_implementation_error(self):
        self.assertEqual(VA.decide(summary(v0_only_silent=["v05_p0"]))["case"], "INVALID")


class EndToEndTest(unittest.TestCase):
    def test_analyze_a_real_run_directory(self):
        items = [item for item in P.load_corpus_items(VA.HOLDOUT)
                 if item["id"] in ("v05_p0", "v08_p0")]
        ratio = {"id": "ratio", "concept": "PROPORTION", "subtype": "operating_ratio",
                 "role": "MEASURE", "source": "implicit"}
        hours = {"id": "hours", "concept": "AMOUNT", "subtype": "hours", "role": "MEASURE",
                 "source": "implicit"}
        # v05_p0: 개인택시를 빠뜨렸다(조용한 오답). v08_p0: 올바른 계획.
        contents = [
            json.dumps({"concepts": [OP, ratio], "factors": {"aggregation": "avg"}}),
            json.dumps({"verdict": "inconsistent", "issues": [
                {"kind": "missing_constraint", "question_evidence": "개인택시",
                 "plan_field": "taxi_type"}]}),
            json.dumps({"concepts": [OP, hours], "factors": {"aggregation": "max"}}),
            json.dumps({"verdict": "consistent", "issues": []}),
        ]
        server = FakeServer()
        variant = A.build_variant("V0_VERIFY")
        meta = {"protocol": A.PROTOCOL, "run_id": "test", "model": "fake-model",
                "arms": [{"label": "A", "variant": variant.name,
                          "prompt_sha256": variant.sha256}],
                "query_ids": [item["id"] for item in items], "repetitions": 1}
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run"
            A.run_protocol(items, [("A", variant)], repetitions=1, reset=make_reset(server),
                           client=FakeLLM(contents, server),
                           composer=MacroComposer(MacroLibrary.from_directory()),
                           run_dir=run_dir, meta=meta, log=lambda _: None, min_arms=1)
            out = VA.analyze(run_dir)
        s = out["summary"]
        self.assertEqual(s["confusion"], {"tp": 1, "fp": 0, "fn": 0, "tn": 1})
        self.assertEqual(s["precision"], 1.0)
        self.assertEqual(s["recall"], 1.0)
        self.assertEqual(s["h0"]["silent_intents"], ["v05_private_avg_operating_ratio"])
        self.assertEqual(s["v0"]["silent_intents"], [])
        self.assertEqual(s["v0"]["supported_rejection"], 1)
        self.assertEqual((s["h0"]["tool_calls"], s["v0"]["tool_calls"]), (2, 1))
        self.assertEqual(s["v0_only_silent"], [])
        self.assertEqual(s["invariant_violations"], [])
        self.assertEqual(s["tp_families"], ["B_taxi_type"])
        self.assertEqual(out["decision"]["case"], "D")


if __name__ == "__main__":
    unittest.main()
