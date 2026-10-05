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

    def test_resume_refuses_legacy_rows_without_spec(self):
        with tempfile.TemporaryDirectory() as tmp:
            partial = Path(tmp) / "run.jsonl"
            partial.write_text(json.dumps({"id": "1", "run_settings": {"model_state": "unload_per_question"}}) + "\n",
                               encoding="utf-8")
            with self.assertRaises(SystemExit):
                E.load_partial_rows(partial, {}, "sha", model_state="unload_per_question")


class QuestionClient:
    """질문의 날짜로 대본 grounding을 고른다(순서와 무관). interrupt_after번째 호출에서 중단을 흉내 낸다."""
    model = "scripted"

    def __init__(self, interrupt_after=None):
        self.calls = 0
        self.interrupt_after = interrupt_after
        self.options = {"temperature": 0}
        self.think = None

    def chat(self, messages, tools=None, **kwargs):
        self.calls += 1
        if self.interrupt_after is not None and self.calls > self.interrupt_after:
            raise KeyboardInterrupt("simulated interruption")
        question = messages[-1]["content"]
        day = "2026090" + question.split("9월 ")[1][0]
        return {"message": {"content": json.dumps(_grounding(day), ensure_ascii=False)}}


GOLD_FIXTURE = "".join(
    f"  - id: {key}\n    question: \"2026년 9월 {n}일 택시 수입은?\"\n"
    f"    gold_text: get_billing_metrics(metric=revenue, date=2026090{n})\n"
    for key, n in (("a", 1), ("b", 2), ("c", 3)))


class ResumePolicyTest(unittest.TestCase):
    """중단 뒤 재개: 문항별 해제 run은 명세가 같으면 새 세션으로 이어 붙이고, keep_loaded run은 거부하거나 별도
    세션으로 기록한다. 실행 명세의 어느 항목이 바뀌어도 기존 기록과 합치지 않는다."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=HERE)
        self.dir = Path(self.tmp.name)
        self.gold = self.dir / "gold.yaml"
        self.gold.write_text("items:\n" + GOLD_FIXTURE, encoding="utf-8")
        self.resets = []

    def tearDown(self):
        self.tmp.cleanup()

    def run_llm(self, model_state, *, interrupt_after=None, digest="d1", resume_new_session=False, only="",
                order="file", replay_from=None, condition_check=True, name="run"):
        resets = self.resets

        class Reset:
            def __init__(self, *a, **k):
                pass

            def reset(self):
                resets.append(1)
                return Namespace(succeeded=True)

        args = Namespace(host="http://x", model="m", chat_timeout=1.0, out=str(self.dir / f"{name}.json"),
                         only=only, condition_check=condition_check, condition_notes=False, no_normalize=False,
                         aggregation_grounding="flat", no_semantic=False, replay_from=replay_from,
                         reference_date=FIXED, model_state=model_state, order=order,
                         resume_new_session=resume_new_session)
        with mock.patch.object(E, "GOLD_PATH", self.gold), \
                mock.patch("ollama_client.OllamaClient", return_value=QuestionClient(interrupt_after)), \
                mock.patch("evaluate_prompt_ab.OllamaStateReset", Reset), \
                mock.patch("evaluate_prompt_ab.unload_all_models", return_value=[]), \
                mock.patch("evaluate_prompt_ab._server_details", return_value=("0.34.4", digest, {})), \
                mock.patch("builtins.print"):
            E.cmd_llm(args)
        return json.loads(Path(args.out).read_text(encoding="utf-8"))

    def interrupted(self, model_state, **kwargs):
        with self.assertRaises(KeyboardInterrupt):
            self.run_llm(model_state, interrupt_after=1, **kwargs)
        rows = (self.dir / "run.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(rows), 1)

    def test_unload_run_resumes_as_a_new_session(self):
        self.interrupted("unload_per_question")
        result = self.run_llm("unload_per_question")
        self.assertEqual([r["session"] for r in result["rows"]], [1, 2, 2])
        self.assertEqual(result["meta"]["sessions"], [{"session": 1, "items": 1}, {"session": 2, "items": 2}])
        self.assertTrue(result["meta"]["pure_live"])
        self.assertFalse(result["meta"]["pure_continuous"])     # 문항별 해제 run은 연속 실행이 아니다

    def test_keep_loaded_run_is_not_resumed_into_the_same_run(self):
        self.interrupted("keep_loaded")
        with self.assertRaises(SystemExit) as raised:
            self.run_llm("keep_loaded")
        self.assertIn("keep_loaded", str(raised.exception))

    def test_keep_loaded_resume_as_separate_session_is_marked_broken(self):
        self.interrupted("keep_loaded")
        result = self.run_llm("keep_loaded", resume_new_session=True)
        self.assertEqual([r["session"] for r in result["rows"]], [1, 2, 2])
        self.assertFalse(result["meta"]["pure_continuous"])

    def test_uninterrupted_keep_loaded_run_is_pure_continuous(self):
        result = self.run_llm("keep_loaded", order="reverse")
        self.assertTrue(result["meta"]["pure_continuous"])
        self.assertEqual(result["meta"]["measurement"], {"live": 3})
        self.assertEqual(self.resets, [])                               # 문항별 해제 없음
        self.assertEqual(result["meta"]["pipeline"]["isolation"], "keep_loaded")
        self.assertEqual(result["meta"]["item_order"], ["c", "b", "a"])
        self.assertEqual(result["meta"]["run_spec"]["items"], ["c", "b", "a"])
        self.assertEqual([r["reset_ok"] for r in result["rows"]], [None] * 3)

    def test_unload_per_question_is_the_default_behaviour(self):
        result = self.run_llm("unload_per_question")
        self.assertEqual(len(self.resets), 3)
        self.assertEqual(result["meta"]["pipeline"]["isolation"], "unload_per_question")
        self.assertEqual(result["meta"]["run_spec"]["model_digest"], "d1")

    def test_any_spec_change_refuses_to_merge(self):
        changes = [{"digest": "d2"}, {"only": "a,b"}, {"order": "reverse"}, {"condition_check": False}]
        for change in changes:
            with self.subTest(change=change):
                for path in self.dir.glob("run.*"):
                    path.unlink()
                self.interrupted("unload_per_question")
                with self.assertRaises(SystemExit) as raised:
                    self.run_llm("unload_per_question", **change)
                self.assertIn("실행 명세", str(raised.exception))

    def test_gold_file_change_refuses_to_merge(self):
        self.interrupted("unload_per_question")
        self.gold.write_text("items:\n" + GOLD_FIXTURE.replace("택시 수입은", "택시 수입은 얼마야"), encoding="utf-8")
        with self.assertRaises(SystemExit) as raised:
            self.run_llm("unload_per_question")
        self.assertIn("gold_sha256", str(raised.exception))

    def test_code_change_refuses_to_merge(self):
        self.interrupted("unload_per_question")
        original = E.run_spec

        def changed(*a, **k):
            spec = original(*a, **k)
            spec["code_fingerprint"] = "other"
            return spec
        with mock.patch.object(E, "run_spec", side_effect=changed):
            with self.assertRaises(SystemExit) as raised:
                self.run_llm("unload_per_question")
        self.assertIn("code_fingerprint", str(raised.exception))

    def test_replayed_rows_are_not_a_pure_live_measurement(self):
        source = self.run_llm("keep_loaded", name="source")
        replay_path = self.dir / "source.json"
        self.assertTrue(source["meta"]["pure_continuous"])
        result = self.run_llm("keep_loaded", replay_from=str(replay_path), name="replayed")
        self.assertEqual({r["measurement"] for r in result["rows"]}, {"replayed"})
        self.assertFalse(result["meta"]["pure_live"])
        self.assertFalse(result["meta"]["pure_continuous"])


if __name__ == "__main__":
    unittest.main()
