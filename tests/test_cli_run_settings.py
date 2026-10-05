# -*- coding: utf-8 -*-
"""CLI의 모델·chat timeout 결정: CLI 인자 > 환경변수 > 실행 모드 기본값. GeoFlow 기본값은 평가 조합과 같다."""

import hashlib
import sys
import unittest
import unittest.mock
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import assistant_cli as cli  # noqa: E402


def args(mode, model=None, timeout=None):
    return SimpleNamespace(agent_mode=mode, model=model, chat_timeout=timeout)


class RunSettingsTest(unittest.TestCase):
    def test_geoflow_default_is_the_evaluated_combination(self):
        result = cli.resolve_run_settings(args(cli.AGENT_MODE_GEOFLOW), environ={})
        self.assertEqual((result.model, result.model_source), (cli.GEOFLOW_DEFAULT_MODEL_NAME, "default"))
        self.assertEqual(result.chat_timeout, cli.GEOFLOW_DEFAULT_CHAT_TIMEOUT)

    def test_react_default_is_unchanged(self):
        result = cli.resolve_run_settings(args(cli.AGENT_MODE_REACT), environ={})
        self.assertEqual(result.model, cli.DEFAULT_MODEL_NAME)
        self.assertEqual(result.chat_timeout, 120.0)

    def test_user_settings_win(self):
        env = {"OLLAMA_MODEL": "env-model", "OLLAMA_CHAT_TIMEOUT": "45"}
        result = cli.resolve_run_settings(args(cli.AGENT_MODE_GEOFLOW), environ=env)
        self.assertEqual((result.model, result.model_source, result.chat_timeout), ("env-model", "OLLAMA_MODEL", 45.0))
        result = cli.resolve_run_settings(args(cli.AGENT_MODE_GEOFLOW, "cli-model", 30.0), environ=env)
        self.assertEqual((result.model, result.model_source, result.chat_timeout), ("cli-model", "--model", 30.0))

    def test_default_model_is_a_verified_combination(self):
        self.assertIn(cli.GEOFLOW_DEFAULT_MODEL_NAME, cli.GEOFLOW_VERIFIED_MODELS)

    def test_verified_combination_matches_current_prompt(self):
        from geoflow.planner import GeoFlowPlanner
        digest = hashlib.sha256(GeoFlowPlanner(client=None).system_prompt().encode("utf-8")).hexdigest()
        self.assertTrue(digest.startswith(cli.GEOFLOW_VERIFIED_PROMPT_SHA256_PREFIX),
                        "prompt가 바뀌었다. 검증 조합(GEOFLOW_VERIFIED_MODELS)을 다시 검증하고 hash를 갱신한다.")

    def test_unverified_model_is_marked_not_blocked(self):
        previous = cli.AGENT_MODE
        try:
            cli.AGENT_MODE = cli.AGENT_MODE_GEOFLOW
            self.assertEqual(cli.geoflow_combination_note(cli.GEOFLOW_DEFAULT_MODEL_NAME), "")
            self.assertIn("검증하지 않은", cli.geoflow_combination_note("qwen3:8b"))
            cli.AGENT_MODE = cli.AGENT_MODE_REACT
            self.assertEqual(cli.geoflow_combination_note("qwen3:8b"), "")
        finally:
            cli.AGENT_MODE = previous

    def verified_settings(self, **changes):
        settings = dict(cli.GEOFLOW_VERIFIED_SPEC["settings"], model=cli.GEOFLOW_VERIFIED_SPEC["model"])
        settings.update(changes)
        return settings

    def verified_facts(self, **changes):
        facts = {"model_digest": cli.GEOFLOW_VERIFIED_SPEC["model_digest"],
                 "ollama_version": cli.GEOFLOW_VERIFIED_SPEC["ollama_version"]}
        facts.update(changes)
        return facts

    def test_verified_spec_matches_only_the_whole_execution_spec(self):
        self.assertEqual(cli.verification_differences(self.verified_settings(), self.verified_facts()), [])
        self.assertEqual(cli.verification_differences(self.verified_settings(model="qwen3:8b"), self.verified_facts()),
                         ["model"])
        self.assertEqual(cli.verification_differences(self.verified_settings(), self.verified_facts(model_digest="x")),
                         ["model_digest"])
        self.assertEqual(cli.verification_differences(self.verified_settings(think=False, provider="reference"),
                                                      self.verified_facts()), ["think", "provider"])
        self.assertEqual(cli.verification_differences(self.verified_settings(), self.verified_facts(ollama_version=None)),
                         ["ollama_version(확인 불가)"])

    def test_default_settings_are_the_verified_settings(self):
        """CLI 기본값(geoflow 모드)이 검증한 실행 설정과 같다. 기본값을 바꾸면 재검증이 필요하다."""
        args = cli.parse_args(["--agent-mode", "geoflow", "--query", "q"])
        previous = (cli.AGENT_MODE, cli.CONDITION_CHECK, cli.CONDITION_NOTES, cli.TIMS_EXECUTION,
                    cli.EXAMPLE_RETRIEVAL, cli.AGGREGATION_GROUNDING, cli.OLLAMA_CLIENT)
        try:
            cli.AGENT_MODE = cli.AGENT_MODE_GEOFLOW
            cli.CONDITION_CHECK = not args.no_condition_check
            cli.TIMS_EXECUTION = args.tims_execution
            cli.EXAMPLE_RETRIEVAL = args.example_retrieval
            cli.AGGREGATION_GROUNDING = args.aggregation_grounding
            cli.configure_ollama_client(args.ollama_host, cli.GEOFLOW_VERIFIED_SPEC["model"], 300.0,
                                        think=cli.resolve_think(args.model_think), num_predict=args.num_predict)
            with unittest.mock.patch.dict("os.environ", {"ASSISTANT_TOOL_PROVIDER": "mock"}):
                settings = cli.geoflow_run_settings()
            self.assertEqual(cli.verification_differences(settings, self.verified_facts()), [])
        finally:
            (cli.AGENT_MODE, cli.CONDITION_CHECK, cli.CONDITION_NOTES, cli.TIMS_EXECUTION,
             cli.EXAMPLE_RETRIEVAL, cli.AGGREGATION_GROUNDING, cli.OLLAMA_CLIENT) = previous

    def test_parse_args_applies_the_resolution(self):
        parsed = cli.parse_args(["--agent-mode", "geoflow", "--query", "q"])
        self.assertIn(parsed.model_source, ("default", "OLLAMA_MODEL"))


if __name__ == "__main__":
    unittest.main()
