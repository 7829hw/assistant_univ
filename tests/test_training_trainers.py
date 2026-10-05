"""No GPU or transformers required for config/dataset/chat-prefix guards."""
import copy
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import yaml

from training.data.build_sft import build as build_sft
from training.data.build_dpo import build as build_dpo
from training.data.common import ROOT
from training.trainer_common import load_config, load_records, render_records
from training.train_sft import main as sft_main
from training.train_dpo import main as dpo_main
from tests.test_training_data import record


class PrefixTokenizer:
    chat_template = "test generation prefix"
    eos_token = "<end>"

    def apply_chat_template(self, messages, **kwargs):
        # Non-thinking Qwen prefix contains an empty reasoning block already in prompt.
        return "SYS:" + messages[0]["content"] + " USER:" + messages[1]["content"] + " ASSISTANT:<think>\n\n</think>\n\n"

    def __call__(self, text, **kwargs):
        return {"input_ids": list(text.encode("utf-8"))}


class TrainerTest(unittest.TestCase):
    def test_configs_and_reference_defaults(self):
        sft = load_config(ROOT / "training/configs/qwen_sft.yaml", "sft")
        dpo = load_config(ROOT / "training/configs/qwen_dpo.yaml", "dpo")
        self.assertTrue(sft["model"]["load_in_4bit"])
        self.assertEqual(dpo["reference"]["mode"], "initial_policy")
        self.assertEqual(dpo["model"]["initial_mode"], "sft")
        self.assertFalse(sft["chat_template_kwargs"]["enable_thinking"])

    def test_bad_precision_and_reference_config(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.yaml"
            original = load_config(ROOT / "training/configs/qwen_dpo.yaml", "dpo")
            for change in ("precision", "dpo_only_adapter", "no_sft_initialization", "explicit_reference"):
                config = copy.deepcopy(original)
                if change == "precision":
                    config["training"]["fp16"] = True
                elif change == "dpo_only_adapter":
                    config["model"]["initial_mode"] = "dpo_only"
                elif change == "no_sft_initialization":
                    config["model"].pop("adapter_path")
                else:
                    config["reference"]["mode"] = "explicit"
                path.write_text(yaml.safe_dump(config))
                with self.subTest(change=change), self.assertRaises(ValueError):
                    load_config(path, "dpo")

    def test_json_only_completion_and_prefix_in_prompt(self):
        config = load_config(ROOT / "training/configs/qwen_sft.yaml", "sft")
        config["training"]["max_seq_length"] = 100000
        rendered = render_records(PrefixTokenizer(), [record()], config, "sft")[0]
        self.assertIn("<think>", rendered["prompt"])
        self.assertTrue(rendered["completion"].startswith('{"concepts":'))
        self.assertTrue(rendered["completion"].endswith("<end>"))
        self.assertNotIn("<think>", rendered["completion"])
        self.assertEqual(json.loads(rendered["completion"][:-5]), json.loads(record()["messages"][-1]["content"]))

    def test_prompt_and_completion_are_never_silently_truncated(self):
        config = load_config(ROOT / "training/configs/qwen_sft.yaml", "sft")
        config["training"]["max_seq_length"] = 10
        with self.assertRaisesRegex(ValueError, "truncate"):
            render_records(PrefixTokenizer(), [record()], config, "sft")
        tokenizer = PrefixTokenizer()
        original = tokenizer.__class__.__call__
        def boundary_changed(self, text, **kwargs):
            result = original(self, text, **kwargs)
            if '<end>' in text:
                result["input_ids"][0] = -1
            return result
        config["training"]["max_seq_length"] = 100000
        with patch.object(PrefixTokenizer, "__call__", boundary_changed), self.assertRaisesRegex(ValueError, "boundary"):
            render_records(tokenizer, [record()], config, "sft")

    def test_dry_runs_validate_real_data_without_model_imports(self):
        with tempfile.TemporaryDirectory() as directory, redirect_stdout(io.StringIO()):
            output = Path(directory)
            build_sft(ROOT / "geoflow_examples/question_graph_examples.yaml", output, strict=True)
            build_dpo(output, output, strict=True)
            for stage, main in (("sft", sft_main), ("dpo", dpo_main)):
                config = load_config(ROOT / f"training/configs/qwen_{stage}.yaml", stage)
                config["data"] = {"train": str(output / f"{stage}_train.jsonl"),
                                  "valid": str(output / f"{stage}_valid.jsonl"), "manifest": str(output / "manifest.json")}
                path = output / f"{stage}.yaml"
                path.write_text(yaml.safe_dump(config))
                main(["--config", str(path), "--dry-run"])
                with patch("training.trainer_common.production_prompt", return_value="changed prompt"), self.assertRaisesRegex(ValueError, "drift"):
                    load_records(config, stage)


if __name__ == "__main__":
    unittest.main()
