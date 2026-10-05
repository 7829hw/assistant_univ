# -*- coding: utf-8 -*-
"""CLI의 모델·chat timeout 결정: CLI 인자 > 환경변수 > 실행 모드 기본값. GeoFlow 기본값은 평가 조합과 같다."""

import hashlib
import sys
import unittest
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

    def test_parse_args_applies_the_resolution(self):
        parsed = cli.parse_args(["--agent-mode", "geoflow", "--query", "q"])
        self.assertIn(parsed.model_source, ("default", "OLLAMA_MODEL"))


if __name__ == "__main__":
    unittest.main()
