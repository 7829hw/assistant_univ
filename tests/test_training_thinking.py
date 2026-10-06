"""Thinking-format training records: rendering equals inference rendering, completion equals generated tokens.

Needs the pinned Qwen3-8B tokenizer offline (HF_HOME with Qwen/Qwen3-8B@b968826d). Skips otherwise.
The generated-token check uses collected traces if present (THINKING_TRACES or the default ignored path).
"""
import json
import os
import unittest
from pathlib import Path

from training.data import thinking
from training.data.common import production_prompt
from training.trainer_common import render_prompt, render_records

ROOT = Path(__file__).resolve().parents[1]
REVISION = "b968826d9c46dd6066d109eabc6255188de91218"
TRACES = Path(os.environ.get("THINKING_TRACES", ROOT / "training/generated/thinking_traces/v003_t2pc_train/traces.jsonl"))


def _tokenizer():
    try:
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        from transformers import AutoTokenizer
        return AutoTokenizer.from_pretrained("Qwen/Qwen3-8B", revision=REVISION)
    except Exception:  # noqa: BLE001 - tokenizer가 없는 환경
        return None


TOKENIZER = _tokenizer()
QUESTION = "2026년 9월 1일부터 7일까지 실차 승차가 가장 많은 시군구 세 곳은?"
ANSWER = '{"concepts": [{"id": "trip", "concept": "EVENT", "subtype": "trip", "role": "SUPPORT", "source": "implicit"}, ' \
         '{"id": "count", "concept": "AMOUNT", "subtype": "trip_count", "role": "MEASURE", "source": "implicit"}], ' \
         '"factors": {"date": "20260901-20260907", "dimension": "sigungu", "dimension_target": "pickup", ' \
         '"order": "top", "limit": 3}}'
RESPONSE = "<think>\n승차 끝 기준 묶음이다.\n</think>\n\n" + ANSWER


def config(scope="full_response", thinking_on=True):
    return {"chat_template_kwargs": {"enable_thinking": thinking_on}, "thinking": {"loss_scope": scope},
            "training": {"max_seq_length": 9000, "max_length": 9000, "max_prompt_length": 8000,
                         "max_completion_length": 2000}}


def sft_record(response=RESPONSE):
    return {"messages": [{"role": "system", "content": production_prompt()}, {"role": "user", "content": QUESTION},
                         {"role": "assistant", "content": response}], "metadata": {"format": "thinking"}}


def dpo_record():
    return {"prompt": sft_record()["messages"][:2], "chosen": [{"role": "assistant", "content": RESPONSE}],
            "rejected": [{"role": "assistant", "content": RESPONSE.replace('"pickup"', '"dropoff"')}],
            "metadata": {"format": "thinking"}}


@unittest.skipIf(TOKENIZER is None, "pinned Qwen3-8B tokenizer not available offline")
class ThinkingRenderTest(unittest.TestCase):
    def test_training_prompt_equals_inference_rendering(self):
        record = sft_record()
        row = render_records(TOKENIZER, [record], config(), "sft")[0]
        inference = render_prompt(TOKENIZER, record["messages"][:2], {"chat_template_kwargs": {"enable_thinking": True}})
        direct = TOKENIZER.apply_chat_template(record["messages"][:2], tokenize=False, add_generation_prompt=True,
                                               enable_thinking=True)
        self.assertEqual(row["prompt"], inference)
        self.assertEqual(TOKENIZER(row["prompt"], add_special_tokens=False)["input_ids"],
                         TOKENIZER(direct, add_special_tokens=False)["input_ids"])
        self.assertTrue(row["prompt"].endswith("<|im_start|>assistant\n"))
        self.assertEqual(row["completion"], RESPONSE + TOKENIZER.eos_token)

    def test_json_only_moves_reasoning_into_prompt(self):
        row = render_records(TOKENIZER, [sft_record()], config("json_only"), "sft")[0]
        self.assertTrue(row["prompt"].endswith("</think>\n\n"))
        self.assertEqual(row["completion"], ANSWER + TOKENIZER.eos_token)
        full = render_records(TOKENIZER, [sft_record()], config(), "sft")[0]
        self.assertEqual(row["prompt"] + row["completion"], full["prompt"] + full["completion"])

    def test_dpo_requires_full_response_scope(self):
        row = render_records(TOKENIZER, [dpo_record()], config(), "dpo")[0]
        self.assertEqual(row["chosen"], RESPONSE)
        with self.assertRaisesRegex(ValueError, "full_response"):
            render_records(TOKENIZER, [dpo_record()], config("json_only"), "dpo")

    def test_scope_and_thinking_flag_are_required(self):
        with self.assertRaisesRegex(ValueError, "no default"):
            render_records(TOKENIZER, [sft_record()], {**config(), "thinking": {}}, "sft")
        with self.assertRaisesRegex(ValueError, "enable_thinking"):
            render_records(TOKENIZER, [sft_record()], config(thinking_on=False), "sft")
        with self.assertRaisesRegex(ValueError, "</think>"):
            render_records(TOKENIZER, [sft_record(ANSWER)], config(), "sft")

    @unittest.skipUnless(TRACES.exists(), "collected traces not present")
    def test_completion_tokens_equal_generated_tokens(self):
        checked = 0
        with TRACES.open(encoding="utf-8") as stream:
            for line in stream:
                trace = json.loads(line)
                if trace["done_reason"] != "stop" or not trace["think_closed"]:
                    continue
                ids = trace["generated_ids"]
                self.assertEqual(TOKENIZER(trace["raw_text"] + TOKENIZER.eos_token, add_special_tokens=False)["input_ids"],
                                 ids, trace["trace_id"])
                checked += 1
        self.assertGreater(checked, 0)


class ThinkingSplitTest(unittest.TestCase):
    def test_split_and_answer(self):
        reasoning, answer = thinking.split_response(RESPONSE)
        self.assertEqual(reasoning + answer, RESPONSE)
        self.assertEqual(json.loads(thinking.canonical_answer(RESPONSE)), json.loads(ANSWER))
        with self.assertRaises(ValueError):
            thinking.split_response("<think>\n끝나지 않음")


if __name__ == "__main__":
    unittest.main()
