# -*- coding: utf-8 -*-
"""path_repeat_001(결정 56) harness 옵션: sampling과 호출 seed 규칙, 기본 동작 불변."""
import hashlib
import json
import sys
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory" / "thinking_prep_001"))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory" / "path_repeat_001"))

import cell_guard  # noqa: E402
import evaluate_vendor100 as E  # noqa: E402
import hf_eval_thinking  # noqa: E402
import hf_thinking  # noqa: E402
from tests.test_operational_controls import FIXED, GOLD_FIXTURE, QuestionClient  # noqa: E402

HERE = Path(__file__).resolve().parent
E_RECORD = ROOT / "sft_dpo_inventory" / "pilot_prep_003" / "ollama" / "E.json"


class CallSeedTest(unittest.TestCase):
    def test_rule_matches_the_plan(self):
        expected = int.from_bytes(hashlib.sha256(b"20261010:008:0").digest()[:4], "big") & 0x7FFFFFFF
        self.assertEqual(E.call_seed(20261010, "008", 0), expected)

    def test_seed_depends_on_round_item_and_call(self):
        seeds = {E.call_seed(r, i, c) for r in (20261010, 20261011) for i in ("001", "002") for c in (0, 1)}
        self.assertEqual(len(seeds), 8)
        self.assertTrue(all(0 <= s < 2 ** 31 for s in seeds))


class OptionRecordingClient(QuestionClient):
    """첫 호출은 JSON이 아닌 답을 내 재질의를 부르고, 호출 때의 options를 남긴다."""

    def __init__(self, *, broken_first=False):
        super().__init__()
        self.seen = []
        self.broken_first = broken_first

    def chat(self, messages, tools=None, **kwargs):
        self.seen.append((messages[-1]["content"][:20], dict(self.options)))
        if self.broken_first and len(self.seen) == 1:
            return {"message": {"content": "not json"}}
        return super().chat(messages, tools=tools, **kwargs)


class LlmSamplingTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=HERE)
        self.dir = Path(self.tmp.name)
        self.gold = self.dir / "gold.yaml"
        self.gold.write_text("items:\n" + GOLD_FIXTURE, encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def args(self, name="run", **extra):
        return Namespace(host="http://x", model="m", chat_timeout=1.0, out=str(self.dir / f"{name}.json"), only="",
                         condition_check=True, condition_notes=False, no_normalize=False,
                         aggregation_grounding="flat", no_semantic=False, replay_from=None, reference_date=FIXED,
                         model_state="unload_per_question", order="file", resume_new_session=False, **extra)

    def run_llm(self, args, client):
        class Reset:
            def __init__(self, *a, **k):
                pass

            def reset(self):
                return Namespace(succeeded=True)

        with mock.patch.object(E, "GOLD_PATH", self.gold), \
                mock.patch("ollama_client.OllamaClient", return_value=client), \
                mock.patch("evaluate_prompt_ab.OllamaStateReset", Reset), \
                mock.patch("evaluate_prompt_ab.unload_all_models", return_value=[]), \
                mock.patch("evaluate_prompt_ab._server_details", return_value=("0.40.1", "d1", {})), \
                mock.patch("builtins.print"):
            E.cmd_llm(args)
        return json.loads(Path(args.out).read_text(encoding="utf-8"))

    def test_default_requests_spec_and_records_are_unchanged(self):
        old_style = self.run_llm(self.args(), OptionRecordingClient())
        client = OptionRecordingClient()
        new_style = self.run_llm(self.args("new", temperature=None, top_p=None, top_k=None, seed=None,
                                           record_env=False),
                                 client)
        self.assertEqual({tuple(sorted(o.items())) for _, o in client.seen}, {(("temperature", 0),)})
        self.assertEqual(old_style["meta"]["run_spec"], new_style["meta"]["run_spec"])
        self.assertEqual(old_style["meta"]["run_spec_sha256"], new_style["meta"]["run_spec_sha256"])
        self.assertEqual(old_style["meta"]["pipeline"], new_style["meta"]["pipeline"])
        self.assertNotIn("environment", new_style["meta"])
        self.assertEqual(new_style["meta"]["pipeline"]["temperature"], 0)
        for row in new_style["rows"]:
            for call in row["llm_calls"]:
                self.assertNotIn("sampling_seed", call)

    def test_seeded_client_numbers_every_call_of_an_item(self):
        client = OptionRecordingClient(broken_first=True)
        sampling = E.sampling_settings(Namespace(temperature=0.6, top_p=0.95, top_k=20, seed=20261010,
                                                 replay_from=None))
        seeded = E._SeededClient(client, sampling, "a")
        message = [{"role": "user", "content": "2026년 9월 1일 택시 수입은?"}]
        seeded.chat(message)                    # 첫 plan(깨진 응답)
        seeded.chat(message + message)          # 같은 문항의 재질의
        with mock.patch.object(QuestionClient, "chat", side_effect=TimeoutError("t")), \
                self.assertRaises(TimeoutError):
            seeded.chat(message)                # 실패한 호출도 순번을 쓴다
        self.assertEqual([o["seed"] for _, o in client.seen[:2]],
                         [E.call_seed(20261010, "a", 0), E.call_seed(20261010, "a", 1)])
        self.assertEqual(client.options["seed"], E.call_seed(20261010, "a", 2))
        self.assertEqual(seeded.calls, 3)

    def test_sampling_sets_values_and_a_seed_per_call(self):
        client = OptionRecordingClient()
        result = self.run_llm(self.args(temperature=0.6, top_p=0.95, top_k=20, seed=20261010, record_env=False),
                              client)
        rows = {row["id"]: row for row in result["rows"]}
        expected = []
        for item_id in ("a", "b", "c"):
            for index, call in enumerate(rows[item_id]["llm_calls"]):
                self.assertEqual(call["sampling_seed"], E.call_seed(20261010, item_id, index))
                expected.append({"temperature": 0.6, "top_p": 0.95, "top_k": 20,
                                 "seed": E.call_seed(20261010, item_id, index)})
        self.assertEqual([o for _, o in client.seen], expected)
        spec = result["meta"]["run_spec"]
        self.assertEqual(spec["options"]["temperature"], 0.6)
        self.assertEqual(spec["options"]["sampling"]["round_seed"], 20261010)
        self.assertEqual(spec["options"]["sampling"]["seed_rule"], E.SEED_RULE)
        self.assertEqual(result["meta"]["pipeline"]["sampling"]["top_k"], 20)

    def test_partial_sampling_options_are_refused(self):
        with self.assertRaises(SystemExit):
            E.sampling_settings(Namespace(temperature=0.6, top_p=None, top_k=20, seed=1, replay_from=None))
        with self.assertRaises(SystemExit):
            E.sampling_settings(Namespace(temperature=0.6, top_p=0.9, top_k=20, seed=1, replay_from="x.json"))

    def test_record_env_adds_only_meta(self):
        client = OptionRecordingClient()
        with mock.patch.object(E, "environment_record", return_value={"host_gpus": [{"uuid": "GPU-x"}]}):
            result = self.run_llm(self.args(temperature=None, top_p=None, top_k=None, seed=None, record_env=True),
                                  client)
        self.assertEqual(result["meta"]["environment"], {"host_gpus": [{"uuid": "GPU-x"}]})
        self.assertEqual({tuple(sorted(o.items())) for _, o in client.seen}, {(("temperature", 0),)})


class RecordedSpecTest(unittest.TestCase):
    """옵션 없는 명세가 기존 E 기록(지문 791c4a68)의 명세와 같은 hash를 낸다."""

    def test_e_record_spec_is_reproduced(self):
        record = json.loads(E_RECORD.read_text(encoding="utf-8"))["meta"]
        spec = record["run_spec"]
        args = Namespace(model="qwen3:8b", replay_from=None, condition_check=True, condition_notes=False,
                         no_normalize=False, no_semantic=False, aggregation_grounding="flat", chat_timeout=300.0,
                         model_think="auto", reference_date=FIXED, model_state="unload_per_question", order="file",
                         temperature=None, top_p=None, top_k=None, seed=None)
        items = [{"id": item_id} for item_id in spec["items"]]
        with mock.patch.object(E, "GOLD_PATH", None):
            rebuilt = E.run_spec(args, digest=spec["model_digest"], version=spec["ollama_version"],
                                 prompt_sha=spec["planner_prompt_sha256"], items=items)
        self.assertEqual(rebuilt, spec)
        self.assertEqual(E._execution_spec_module().spec_sha256(rebuilt), record["run_spec_sha256"])


class FakeHF:
    def __init__(self):
        self.kwargs = []
        self.log = []

    def generate(self, messages, **kwargs):
        self.kwargs.append(kwargs)
        return [{"raw_text": "<think>t</think>{}", "raw_sha256": "s", "thinking": "t", "content": "{}",
                 "think_closed": True, "prompt_tokens": 3, "generated_tokens": 2, "done_reason": "stop"}]


class HFSamplingTest(unittest.TestCase):
    def test_default_chat_is_greedy_as_before(self):
        client = FakeHF()
        response = hf_thinking.chat_response(client, [{"role": "user", "content": "q"}])
        self.assertEqual(client.kwargs, [{}])
        self.assertEqual(response, {"message": {"content": "{}", "thinking": "t"}, "prompt_eval_count": 3,
                                    "eval_count": 2, "done_reason": "stop"})
        self.assertEqual(client.log, [{"raw_sha256": "s", "generated_tokens": 2, "done_reason": "stop",
                                       "think_closed": True}])

    def test_sampling_call_passes_seed_and_params(self):
        client = FakeHF()
        params = {"temperature": 0.6, "top_p": 0.95, "top_k": 20}
        client.sampling_call = {"seed": 123, "params": params}
        response = hf_thinking.chat_response(client, [{"role": "user", "content": "q"}])
        self.assertEqual(client.kwargs, [{"sample": True, "seed": 123, "sampling": params}])
        self.assertEqual(response["sampling_seed"], 123)
        self.assertEqual(client.log[0]["sampling_seed"], 123)

    def test_sampling_settings_validation(self):
        base = dict(temperature=None, top_p=None, top_k=None, seed=None)
        self.assertIsNone(hf_eval_thinking.sampling_settings(Namespace(do_sample=False, **base)))
        with self.assertRaises(SystemExit):
            hf_eval_thinking.sampling_settings(Namespace(do_sample=False, **{**base, "seed": 1}))
        with self.assertRaises(SystemExit):
            hf_eval_thinking.sampling_settings(Namespace(do_sample=True, **{**base, "seed": 1}))
        self.assertEqual(hf_eval_thinking.sampling_settings(Namespace(do_sample=True, temperature=0.6, top_p=0.95,
                                                                      top_k=20, seed=7)),
                         {"params": {"temperature": 0.6, "top_p": 0.95, "top_k": 20}, "round_seed": 7})


class GuardRateTest(unittest.TestCase):
    def test_item_rate_uses_successful_calls_without_load_time(self):
        record = {"llm_calls": [{"duration_ms": 3000, "load_duration_ms": 1000, "eval_count": 200},
                                {"duration_ms": 1000, "load_duration_ms": 0, "eval_count": 100},
                                {"failed": True, "duration_ms": 50000}]}
        self.assertAlmostEqual(cell_guard.item_rate(record), 100.0)
        self.assertIsNone(cell_guard.item_rate({"llm_calls": [{"failed": True}]}))


if __name__ == "__main__":
    unittest.main()
