# -*- coding: utf-8 -*-
"""운영 조건 통제(grounding_v14): 기준일 전달, 모델 적재 방식 선택, 실행 조건 기록, 질문 사이 상태 누출."""

import json
import os
import sys
import tempfile
import unittest
from argparse import Namespace
from datetime import date
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import assistant_cli as cli  # noqa: E402
import evaluate_vendor100 as E  # noqa: E402
from build import build  # noqa: E402
from geoflow.pipeline import seoul_today  # noqa: E402

HERE = Path(__file__).resolve().parent
TOOLS, _ = build()
FIXED = date(2026, 9, 25)


def _grounding(day):
    return {"concepts": [
        {"id": "operation", "concept": "EVENT", "subtype": "operation", "role": "SUPPORT", "source": "implicit"},
        {"id": "revenue", "text": "수입", "concept": "AMOUNT", "subtype": "revenue", "role": "MEASURE",
         "source": "implicit"}],
        "factors": {"date": day}}


class RecordingClient:
    """보낸 messages를 모두 기록하고 대본 응답을 돌려준다."""
    model = "scripted"

    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []
        self.options = {"temperature": 0}
        self.think = None

    def chat(self, messages, tools=None, **kwargs):
        self.requests.append([dict(m) for m in messages])
        return {"message": {"content": json.dumps(self.responses.pop(0), ensure_ascii=False)}}


class CliReferenceDateTest(unittest.TestCase):
    def runtime(self, reference):
        with mock.patch.object(cli, "AGENT_MODE", cli.AGENT_MODE_GEOFLOW), \
                mock.patch.object(cli, "REFERENCE_DATE", reference), \
                mock.patch.dict(os.environ, {"ASSISTANT_TOOL_PROVIDER": "mock"}):
            return cli._new_runtime(TOOLS, "system")

    def test_reference_date_reaches_conditions_and_compiler(self):
        geoflow = self.runtime(FIXED).geoflow
        self.assertEqual(geoflow.clock(), FIXED)            # 컴파일(상대 기간을 날짜로)
        self.assertEqual(geoflow.planner.clock(), FIXED)    # 조건 계층

    def test_default_keeps_the_system_date(self):
        geoflow = self.runtime(None).geoflow
        self.assertIs(geoflow.clock, seoul_today)
        self.assertIsNone(geoflow.planner.clock)

    def test_reference_date_is_not_in_the_planner_prompt(self):
        with_date = self.runtime(FIXED).geoflow.planner.system_prompt()
        without = self.runtime(None).geoflow.planner.system_prompt()
        self.assertEqual(with_date, without)

    def test_parse_and_label(self):
        args = cli.parse_args(["--agent-mode", "geoflow", "--query", "q", "--reference-date", "2026-09-25"])
        self.assertEqual(args.reference_date, FIXED)
        with self.assertRaises(SystemExit):
            cli.parse_args(["--agent-mode", "geoflow", "--query", "q", "--reference-date", "9월 25일"])
        with mock.patch.object(cli, "REFERENCE_DATE", FIXED):
            self.assertIn("2026-09-25", cli.reference_date_label())


class CliQuestionIsolationTest(unittest.TestCase):
    """연속 실행에서 각 질문은 새 Runtime으로 처리되고, 이전 질문·grounding·답변이 다음 요청에 들어가지 않는다."""

    def test_consecutive_questions_do_not_share_state(self):
        client = RecordingClient([_grounding("20260901"), _grounding("20260902")])
        queries = [{"id": "a", "question": "2026년 9월 1일 택시 수입은?"},
                   {"id": "b", "question": "2026년 9월 2일 택시 수입은?"}]
        with mock.patch.object(cli, "AGENT_MODE", cli.AGENT_MODE_GEOFLOW), \
                mock.patch.object(cli, "REFERENCE_DATE", FIXED), \
                mock.patch.object(cli, "get_ollama_client", return_value=client), \
                mock.patch.dict(os.environ, {"ASSISTANT_TOOL_PROVIDER": "mock"}), \
                mock.patch("builtins.print"):
            records = cli.run_query_suite(queries, TOOLS, "system", save=False)["records"]
        self.assertEqual(len(client.requests), 2)
        first, second = client.requests
        self.assertEqual([m["role"] for m in first], [m["role"] for m in second])
        self.assertEqual(first[0], second[0])                     # 같은 system prompt
        body_first, body_second = json.dumps(first, ensure_ascii=False), json.dumps(second, ensure_ascii=False)
        self.assertIn("9월 1일", body_first)
        self.assertNotIn("9월 1일", body_second)                  # 이전 질문이 섞이지 않는다
        self.assertNotIn("20260901", body_second)                 # 이전 grounding·답변도 없다
        dates = [r["geoflow"]["grounding"]["factors"]["date"] for r in records]
        self.assertEqual(dates, ["20260901", "20260902"])


class EvaluatorControlsTest(unittest.TestCase):
    def test_order_items(self):
        items = [{"id": str(i)} for i in range(6)]
        self.assertEqual(E.order_items(items, "file"), items)
        self.assertEqual(E.order_items(items, "reverse"), items[::-1])
        a, b = E.order_items(items, "shuffle:7"), E.order_items(items, "shuffle:7")
        self.assertEqual(a, b)
        self.assertEqual(sorted(x["id"] for x in a), [x["id"] for x in items])
        with self.assertRaises(SystemExit):
            E.order_items(items, "random")

    def test_defaults_are_the_existing_evaluation_condition(self):
        args = E.build_parser().parse_args(["llm", "--model", "m", "--out", "x.json"]) \
            if hasattr(E, "build_parser") else None
        if args is None:
            self.skipTest("parser builder not exposed")
        self.assertEqual(E.run_settings(args), {"reference_date": "2026-09-25",
                                                "model_state": "unload_per_question", "order": "file"})

    def test_resume_refuses_rows_from_another_condition(self):
        with tempfile.TemporaryDirectory() as tmp:
            partial = Path(tmp) / "run.jsonl"
            partial.write_text(json.dumps({"id": "1"}) + "\n", encoding="utf-8")   # 예전 기록(조건 없음)
            default = {"reference_date": "2026-09-25", "model_state": "unload_per_question", "order": "file"}
            self.assertIn("1", E.load_partial_rows(partial, default))
            with self.assertRaises(SystemExit):
                E.load_partial_rows(partial, dict(default, model_state="keep_loaded"))

    def run_llm(self, model_state, tmp):
        gold = Path(tmp) / "gold.yaml"
        gold.write_text(
            "items:\n"
            "  - id: a\n    question: \"2026년 9월 1일 택시 수입은?\"\n"
            "    gold_text: get_billing_metrics(metric=revenue, date=20260901)\n"
            "  - id: b\n    question: \"2026년 9월 2일 택시 수입은?\"\n"
            "    gold_text: get_billing_metrics(metric=revenue, date=20260902)\n", encoding="utf-8")
        client = RecordingClient([_grounding("20260901"), _grounding("20260902")])
        resets = []

        class Reset:
            def __init__(self, *a, **k):
                pass

            def reset(self):
                resets.append(1)
                return Namespace(succeeded=True)

        args = Namespace(host="http://x", model="m", chat_timeout=1.0, out=str(Path(tmp) / f"{model_state}.json"),
                         only="", condition_check=True, condition_notes=False, no_normalize=False,
                         aggregation_grounding="flat", no_semantic=False, replay_from=None,
                         reference_date=FIXED, model_state=model_state, order="reverse")
        with mock.patch.object(E, "GOLD_PATH", gold), \
                mock.patch("ollama_client.OllamaClient", return_value=client), \
                mock.patch("evaluate_prompt_ab.OllamaStateReset", Reset), \
                mock.patch("evaluate_prompt_ab.unload_all_models", return_value=[]), \
                mock.patch("evaluate_prompt_ab._server_details", return_value=("0", "d", {})), \
                mock.patch("builtins.print"):
            E.cmd_llm(args)
        return json.loads(Path(args.out).read_text(encoding="utf-8")), resets

    def test_keep_loaded_skips_per_question_unload_and_is_recorded(self):
        with tempfile.TemporaryDirectory(dir=HERE) as tmp:
            result, resets = self.run_llm("keep_loaded", tmp)
            self.assertEqual(resets, [])
            meta = result["meta"]
            self.assertEqual(meta["pipeline"]["isolation"], "keep_loaded")
            self.assertEqual(meta["run_settings"], {"reference_date": "2026-09-25", "model_state": "keep_loaded",
                                                    "order": "reverse"})
            self.assertEqual(meta["item_order"], ["b", "a"])
            self.assertEqual([r["run_settings"]["model_state"] for r in result["rows"]], ["keep_loaded"] * 2)
            self.assertEqual([r["reset_ok"] for r in result["rows"]], [None, None])

    def test_unload_per_question_is_the_default_behaviour(self):
        with tempfile.TemporaryDirectory(dir=HERE) as tmp:
            result, resets = self.run_llm("unload_per_question", tmp)
            self.assertEqual(len(resets), 2)
            self.assertEqual(result["meta"]["pipeline"]["isolation"], "unload_per_question")


if __name__ == "__main__":
    unittest.main()
