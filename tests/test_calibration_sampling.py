# -*- coding: utf-8 -*-
"""calibration_001: 명시적 sampling 값(min_p·penalty)과 --raw-out. 주지 않으면 이전과 같다."""
import json
import sys
import unittest
from argparse import Namespace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "sft_dpo_inventory" / "thinking_prep_001"))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory" / "path_repeat_001"))

import evaluate_vendor100 as E  # noqa: E402
import hf_eval_thinking  # noqa: E402
from tests.test_path_repeat_sampling import LlmSamplingTest, OptionRecordingClient  # noqa: E402

SAMPLING = dict(temperature=0.6, top_p=0.95, top_k=20, seed=20261101)
EXTRA = dict(min_p=0.0, repeat_penalty=1.0, presence_penalty=0.0, frequency_penalty=0.0)


class ExtraOptionsTest(LlmSamplingTest):
    def test_extra_values_go_into_every_request_and_the_spec(self):
        client = OptionRecordingClient()
        raw = ROOT / "training/generated/calibration_001/raw/_test_raw.jsonl"
        raw.unlink(missing_ok=True)
        try:
            result = self.run_llm(self.args(record_env=False, raw_out=str(raw), **SAMPLING, **EXTRA), client)
            for _, options in client.seen:
                self.assertEqual({k: options[k] for k in EXTRA}, EXTRA)
                self.assertEqual(options["temperature"], 0.6)
            self.assertEqual(result["meta"]["run_spec"]["options"]["sampling"]["extra_options"], EXTRA)
            lines = [json.loads(line) for line in raw.read_text(encoding="utf-8").splitlines()]
            calls = sum(len(row["llm_calls"]) for row in result["rows"])
            self.assertEqual(len(lines), calls)
            self.assertTrue(all({"id", "call", "thinking", "content", "sampling_seed"} <= set(line) for line in lines))
        finally:
            raw.unlink(missing_ok=True)

    def test_extra_without_sampling_is_refused(self):
        with self.assertRaises(SystemExit):
            E.sampling_settings(Namespace(temperature=None, top_p=None, top_k=None, seed=None, replay_from=None,
                                          min_p=0.0))

    def test_without_extra_the_spec_is_unchanged(self):
        plain = E.sampling_settings(Namespace(replay_from=None, **SAMPLING))
        same = E.sampling_settings(Namespace(replay_from=None, min_p=None, repeat_penalty=None,
                                             presence_penalty=None, frequency_penalty=None, **SAMPLING))
        self.assertEqual(plain, same)
        self.assertNotIn("extra_options", plain)

    def test_raw_out_must_be_ignored_inside_the_repository(self):
        with self.assertRaises(SystemExit):
            E.open_raw_out(str(ROOT / "sft_dpo_inventory/calibration_001/raw.jsonl"))


class HfExtraTest(unittest.TestCase):
    def test_hf_params_include_explicit_values(self):
        args = Namespace(do_sample=True, min_p=0.0, repetition_penalty=1.0, **SAMPLING)
        self.assertEqual(hf_eval_thinking.sampling_settings(args)["params"],
                         {"temperature": 0.6, "top_p": 0.95, "top_k": 20, "min_p": 0.0, "repetition_penalty": 1.0})

    def test_hf_extra_without_sampling_is_refused(self):
        args = Namespace(do_sample=False, temperature=None, top_p=None, top_k=None, seed=None, min_p=0.0,
                         repetition_penalty=None)
        with self.assertRaises(SystemExit):
            hf_eval_thinking.sampling_settings(args)


if __name__ == "__main__":
    unittest.main()
