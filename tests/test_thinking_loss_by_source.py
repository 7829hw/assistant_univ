"""Decision 86 (AA): SFT loss scope by record source (teacher: full_response, HF: json_only).

Needs the pinned Qwen3-8B tokenizer offline (HF_HOME with Qwen/Qwen3-8B@b968826d). Skips otherwise.
Loss tokens follow TRL SFTTrainer prompt/completion handling: mask = 0 for tok(prompt), 1 for the rest of tok(prompt + completion).
"""
import unittest

from training.data import thinking
from training.trainer_common import render_prompt, render_records

from tests.test_training_thinking import ANSWER, RESPONSE, TOKENIZER, config, dpo_record, sft_record

INFERENCE = {"chat_template_kwargs": {"enable_thinking": True}}


def teacher_record():
    record = sft_record()
    record["metadata"] = {"format": "thinking", "source": "teacher"}
    return record


def hf_record():
    record = sft_record()
    record["metadata"] = {"format": "thinking", "source": "training/generated/pilot_003/combined_traces.jsonl"}
    return record


def loss_text(row):
    prompt_ids = TOKENIZER(text=row["prompt"])["input_ids"]
    ids = TOKENIZER(text=row["prompt"] + row["completion"])["input_ids"]
    assert ids[:len(prompt_ids)] == prompt_ids
    return TOKENIZER.decode(ids[len(prompt_ids):])


class LossScopeMarkTest(unittest.TestCase):
    def test_assign_marks_by_source(self):
        self.assertEqual(thinking.assign_loss_scope(teacher_record())["metadata"]["loss_scope"], "full_response")
        self.assertEqual(thinking.assign_loss_scope(hf_record())["metadata"]["loss_scope"], "json_only")

    def test_assign_does_not_modify_input(self):
        record = hf_record()
        thinking.assign_loss_scope(record)
        self.assertNotIn("loss_scope", record["metadata"])

    def test_by_source_requires_mark(self):
        with self.assertRaises(ValueError):
            thinking.sft_loss_scope(hf_record(), config("by_source"))

    def test_by_source_refuses_mismatched_mark(self):
        record = teacher_record()
        record["metadata"]["loss_scope"] = "json_only"
        with self.assertRaises(ValueError):
            thinking.sft_loss_scope(record, config("by_source"))

    def test_fixed_scopes_ignore_source(self):
        for scope in ("full_response", "json_only"):
            self.assertEqual(thinking.sft_loss_scope(teacher_record(), config(scope)), scope)
            self.assertEqual(thinking.sft_loss_scope(hf_record(), config(scope)), scope)


@unittest.skipIf(TOKENIZER is None, "pinned Qwen3-8B tokenizer not available offline")
class LossScopeRenderTest(unittest.TestCase):
    def render(self, record):
        return render_records(TOKENIZER, [thinking.assign_loss_scope(record)], config("by_source"), "sft")[0]

    def test_teacher_loss_covers_thinking_and_json(self):
        record = teacher_record()
        row = self.render(record)
        self.assertEqual(row["prompt"], render_prompt(TOKENIZER, record["messages"][:2], INFERENCE))
        text = loss_text(row)
        self.assertEqual(text, RESPONSE + TOKENIZER.eos_token)
        self.assertIn("<think>", text)
        self.assertIn("</think>", text)
        self.assertTrue(text.rstrip().endswith(ANSWER + TOKENIZER.eos_token))

    def test_hf_loss_covers_json_only(self):
        record = hf_record()
        row = self.render(record)
        reasoning, answer = thinking.split_response(RESPONSE)
        self.assertEqual(row["prompt"], render_prompt(TOKENIZER, record["messages"][:2], INFERENCE) + reasoning)
        self.assertTrue(row["prompt"].rstrip().endswith("</think>"))
        text = loss_text(row)
        self.assertEqual(text, answer + TOKENIZER.eos_token)
        self.assertNotIn("<think>", text)
        self.assertNotIn("</think>", text)

    def test_both_scopes_share_the_inference_prefix(self):
        teacher_row = self.render(teacher_record())
        hf_row = self.render(hf_record())
        inference = render_prompt(TOKENIZER, sft_record()["messages"][:2], INFERENCE)
        self.assertTrue(teacher_row["prompt"] == inference and hf_row["prompt"].startswith(inference))
        self.assertTrue(inference.endswith("<|im_start|>assistant\n"))
        # The full sequence is identical for both scopes; only the loss boundary moves.
        self.assertEqual(teacher_row["prompt"] + teacher_row["completion"], hf_row["prompt"] + hf_row["completion"])

    def test_dpo_refuses_by_source(self):
        with self.assertRaises(ValueError):
            render_records(TOKENIZER, [dpo_record()], config("by_source"), "dpo")


if __name__ == "__main__":
    unittest.main()
