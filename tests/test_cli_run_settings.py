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

    def default_spec(self):
        return cli.GEOFLOW_VERIFIED_SPECS[cli.GEOFLOW_DEFAULT_SPEC_NAME]

    def test_default_model_is_the_default_spec_model(self):
        self.assertEqual(cli.GEOFLOW_DEFAULT_MODEL_NAME, self.default_spec()["model"])

    def test_current_code_and_prompt_are_the_default_spec(self):
        """현재 checkout의 실행 의미 코드·prompt가 기본 조합의 검증 명세와 같다. 다르면 재검증하거나(새 명세),
        되돌리기 중이면 GEOFLOW_DEFAULT_SPEC_NAME을 복원한 코드의 조합으로 바꾼다."""
        local = cli.local_code_facts()
        spec = self.default_spec()
        self.assertEqual(local["prompt_sha256"], spec["prompt_sha256"], "prompt가 기본 조합의 검증 명세와 다르다")
        self.assertEqual(local["code_fingerprint"], spec["code_fingerprint"],
                         "실행 의미 코드(execution_spec.SEMANTIC_CODE)가 기본 조합의 검증 명세와 다르다")
        self.assertEqual(cli.select_verified_spec(local), cli.GEOFLOW_DEFAULT_SPEC_NAME)

    def settings(self, **changes):
        spec = self.default_spec()
        settings = dict(spec["settings"], model=spec["model"])
        settings.update(changes)
        return settings

    def server(self, **changes):
        spec = self.default_spec()
        facts = {"model_digest": spec["model_digest"], "ollama_version": spec["ollama_version"]}
        facts.update(changes)
        return facts

    def local(self, **changes):
        spec = self.default_spec()
        facts = {"prompt_sha256": spec["prompt_sha256"], "code_fingerprint": spec["code_fingerprint"]}
        facts.update(changes)
        return facts

    def compare(self, settings=None, server=None, local=None):
        return cli.compare_with_spec(settings or self.settings(), server or self.server(), local or self.local(),
                                     self.default_spec())

    def test_comparison_separates_matched_different_and_unchecked(self):
        result = self.compare()
        self.assertEqual((result["different"], result["unchecked"]), ([], {}))
        self.assertIn("code", result["matched"])
        self.assertIn("prompt", result["matched"])
        result = self.compare(settings=self.settings(model="not-the-spec-model", think=False, provider="reference"))
        self.assertEqual(result["different"], ["model", "think", "provider"])
        result = self.compare(server=self.server(model_digest="x"), local=self.local(code_fingerprint="other"))
        self.assertEqual(result["different"], ["model_digest", "code"])
        result = self.compare(server=self.server(ollama_version=None, model_digest=None))
        self.assertEqual(set(result["unchecked"]), {"model_digest", "ollama_version"})
        self.assertEqual(result["different"], [])

    def test_line_does_not_claim_a_match_when_something_is_unchecked(self):
        result = dict(self.compare(server=self.server(ollama_version=None)), compared_to=cli.GEOFLOW_DEFAULT_SPEC_NAME)
        line = cli.verification_line(result)
        self.assertIn("확인되지 않음", line)
        self.assertIn("확인 안 함: ollama_version", line)
        result = dict(self.compare(), compared_to=cli.GEOFLOW_DEFAULT_SPEC_NAME)
        self.assertIn("검증한 실행 명세와 같음", cli.verification_line(result))
        self.assertIn("명세 밖", cli.verification_line(result))

    def test_spec_selection_follows_the_code(self):
        b = cli.GEOFLOW_VERIFIED_SPECS["B"]
        self.assertEqual(cli.select_verified_spec({"prompt_sha256": b["prompt_sha256"],
                                                   "code_fingerprint": b["code_fingerprint"]}), "B")
        self.assertEqual(cli.select_verified_spec({"prompt_sha256": "x", "code_fingerprint": "y"}),
                         cli.GEOFLOW_DEFAULT_SPEC_NAME)

    def test_default_settings_are_the_verified_settings(self):
        """CLI 기본값(geoflow 모드)이 검증한 실행 설정과 같다. 기본값을 바꾸면 재검증이 필요하다."""
        parsed = cli.parse_args(["--agent-mode", "geoflow", "--query", "q"])
        previous = (cli.AGENT_MODE, cli.CONDITION_CHECK, cli.CONDITION_NOTES, cli.TIMS_EXECUTION,
                    cli.EXAMPLE_RETRIEVAL, cli.AGGREGATION_GROUNDING, cli.OLLAMA_CLIENT)
        try:
            cli.AGENT_MODE = cli.AGENT_MODE_GEOFLOW
            cli.CONDITION_CHECK = not parsed.no_condition_check
            cli.TIMS_EXECUTION = parsed.tims_execution
            cli.EXAMPLE_RETRIEVAL = parsed.example_retrieval
            cli.AGGREGATION_GROUNDING = parsed.aggregation_grounding
            cli.configure_ollama_client(parsed.ollama_host, parsed.model, parsed.chat_timeout,
                                        think=cli.resolve_think(parsed.model_think), num_predict=parsed.num_predict)
            with unittest.mock.patch.dict("os.environ", {"ASSISTANT_TOOL_PROVIDER": "mock"}):
                settings = cli.geoflow_run_settings()
            result = cli.compare_with_spec(settings, self.server(), cli.local_code_facts(), self.default_spec())
            if parsed.model_source == "default":
                self.assertEqual(result["different"], [])
            else:   # OLLAMA_MODEL이 설정된 환경: 모델 외에는 같아야 한다
                self.assertEqual([d for d in result["different"] if d != "model"], [])
        finally:
            (cli.AGENT_MODE, cli.CONDITION_CHECK, cli.CONDITION_NOTES, cli.TIMS_EXECUTION,
             cli.EXAMPLE_RETRIEVAL, cli.AGGREGATION_GROUNDING, cli.OLLAMA_CLIENT) = previous

    def test_parse_args_applies_the_resolution(self):
        parsed = cli.parse_args(["--agent-mode", "geoflow", "--query", "q"])
        self.assertIn(parsed.model_source, ("default", "OLLAMA_MODEL"))


if __name__ == "__main__":
    unittest.main()
