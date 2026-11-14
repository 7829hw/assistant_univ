"""CPU checks for frozen schedules, factorial gates, and training-unit inference."""
from collections import Counter
import unittest

from schedules import (HERE, ORDER_SEEDS, TRAIN_SEEDS, blind_order, experiment,
                       placebo_labels, spacing_audit)
from common import load, np
from execution import CHECKPOINT_STEPS, evaluate_checkpoints, execute_train, plan_locked, validate_job
from analyze_controls import holm, paired_contrasts, sign_flip_p
from taxonomy import classify
from uncertainty import secondary_intervals, transition_summary
from attribution import attribution_flags


class ControlsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records,cls.blocks,cls.labels,_ = experiment()
        cls.manifest=load(HERE/"orders/manifest.json")

    def test_frozen_orders_and_checkpoints(self):
        plan=plan_locked()
        self.assertEqual(len(plan["jobs"]),112)
        for job in plan["jobs"]:
            validate_job(job,self.records,self.blocks)
            self.assertEqual(tuple(c["step"] for c in job["checkpoints"]),CHECKPOINT_STEPS)

    def test_blind_is_reproducible_and_matches_committed_order(self):
        for seed in ORDER_SEEDS:
            a=blind_order(self.blocks,np.random.default_rng(seed))
            self.assertEqual(a,load(HERE/"orders/S0T0"/f"o{seed}.json")["block_order"])

    def test_placebo_preserves_record_level_label_scope_joint_counts(self):
        def distribution(labels):
            return Counter((labels[b.question],scope) for b in self.blocks for scope in b.scopes)
        assigned=placebo_labels(self.blocks,self.labels,np.random.default_rng(303))
        self.assertEqual(distribution(assigned),distribution(self.labels))
        self.assertNotEqual(assigned,self.labels)

    def test_spacing_match_with_real_token_ledger(self):
        for seed in ORDER_SEEDS:
            order=lambda arm:load(HERE/"orders"/arm/f"o{seed}.json")["block_order"]
            pair=spacing_audit(order("low_gap"),order("high_gap"),self.blocks,self.labels)
            self.assertTrue(pair["eligible"])
            self.assertFalse(spacing_audit(order("low_gap"),order("low_gap"),self.blocks,self.labels)["eligible"])

    def test_holm_and_complete_training_blocks(self):
        audits={s:load(HERE/f"audits/o{s}.json") for s in ORDER_SEEDS}
        runs={(arm,o,t):dict(collapse20=3 if arm=="high_gap" else 1,comparison_signature="same")
              for arm in ("low_gap","high_gap") for o in ORDER_SEEDS for t in TRAIN_SEEDS}
        res=paired_contrasts(runs,audits)
        self.assertEqual(res["high_vs_low_gap"]["estimate"],2)
        self.assertEqual(sign_flip_p([2]*8),2/256)
        self.assertEqual(res["high_vs_low_gap"]["holm_adjusted_p"],12/256)
        self.assertFalse(res["interaction"]["eligible"])
        runs.pop(("high_gap",ORDER_SEEDS[0],TRAIN_SEEDS[0]))
        self.assertFalse(paired_contrasts(runs,audits)["high_vs_low_gap"]["eligible"])
        self.assertEqual(holm({"a":.01,"b":.02,"c":1}),{"a":.03,"b":.04,"c":1})

    def test_gpu_modes_require_new_authorization(self):
        with self.assertRaisesRegex(ValueError,"New task-specific GPU authorization"):
            execute_train(None,None,None)
        with self.assertRaisesRegex(ValueError,"New task-specific GPU authorization"):
            evaluate_checkpoints(None,None)

    def test_transition_rates_use_separate_base_denominators(self):
        summary = transition_summary(np.array([False, True, True]), np.array([1., .5, 0.]))
        self.assertEqual(summary["base_correct_to_wrong"], 1.)
        self.assertEqual(summary["base_wrong_to_correct"], 1.5)
        self.assertAlmostEqual(summary["base_correct_to_wrong_rate"], 2/3)
        self.assertEqual(summary["base_wrong_to_correct_rate"], 1.)
        self.assertIsNone(transition_summary(np.array([True]), np.array([0.]))["base_correct_to_wrong_rate"])

    def test_bootstrap_pairs_arms_and_resamples_whole_templates(self):
        class TwoTemplates:
            K = 2
            N = np.ones((2,1))
            @staticmethod
            def sums(vector):
                return np.asarray(vector).reshape(2,1),

        orders, training = (1,2), (11,12)
        vectors = {(a,o,t):[1, 0] if a=="ours" else [1, 1]
                   for a in ("ours","reference") for o in orders for t in training}
        intervals = secondary_intervals(TwoTemplates(), vectors, [1,1], orders, training,
                                        {"difference":{"ours":1,"reference":-1}}, reps=512)
        self.assertEqual(intervals["difference"]["run_only_ci95"], [1.,1.])
        self.assertEqual(intervals["difference"]["run_plus_template_ci95"], [0.,1.])
        self.assertEqual(intervals["difference"]["within_order_sample_sd"], [0.,0.])

    def test_place_omission_attributes_only_parseable_single_plan(self):
        gold = {"gold":[{"tool":"get_place_scope","args":{"name":"p"}}]}
        row = {"outcome":"answered","llm_calls":[{"kind":"plan","content":'{"concepts": []}'}]}
        self.assertIn("model_plan_location_omission", attribution_flags(row,gold))
        row["llm_calls"].append({"kind":"repair","content":"{}"})
        flags = attribution_flags(row,gold)
        self.assertIn("place_origin_ambiguous",flags)
        self.assertNotIn("model_plan_location_omission",flags)

    def test_overlapping_errors(self):
        r={"category":"answered_mismatch","grounding_ok":False,
           "checks":{"tool_ok":False,"arg_mismatches":[["aggregation","sum","avg"]]},
           "hf_calls":[{"finish_reason":"length"}]}
        self.assertEqual(classify(r),{"tool_selection","grounding","argument","aggregation","silent_wrong","truncation"})
        self.assertEqual(classify({"category":"expected_refusal"}),set())
        self.assertEqual(classify({"category":"refused_clarification"}),{"refusal"})


if __name__=="__main__":
    unittest.main()
