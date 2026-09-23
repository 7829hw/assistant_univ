# -*- coding: utf-8 -*-
"""모델 상태를 비우는 prompt A/B harness가 측정 사고를 막는지 확인한다.

실제 Ollama에 의존하지 않는다. reset 서버와 LLM을 가짜로 두고 harness의
기록·판정 규칙만 본다. 여기 적힌 사고는 모두 실제 측정에서 한 번씩 일어났다.

- 같은 질문을 두 변형으로 인접 호출해 뒤 호출이 오염됐다.
- harness가 production과 다른 prompt를 "D"라고 불렀다.
- 거부된 grounding의 원문이 남지 않았다.
- expected NONE인 질의를 뒤집어 채점했다.
- 기록 하나가 중복되고 마지막 줄이 잘렸다.
"""

import hashlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("ASSISTANT_TOOL_PROVIDER", "mock")

import evaluate_prompt_ab as A
from geoflow.composer import MacroComposer
from geoflow.macros import MacroLibrary
from geoflow.planner import GeoFlowPlanner

COLD_NS = 3_000_000_000
WARM_NS = 1_000_000

REVENUE_ITEM = {
    "id": "t01_revenue", "question": "개인택시의 평균 수입은?",
    "expected_concepts": ["EVENT/operation:SUPPORT", "AMOUNT/revenue:MEASURE"],
    "expected_macros": ["EVENT_TO_MEASURE"],
    "expected_operators": ["OPERATION_METRIC"],
}
MONTH_ITEM = {
    "id": "t02_month", "question": "월 단위로 집계한 수입의 최대값은?",
    "expected_concepts": ["EVENT/operation:SUPPORT", "AMOUNT/revenue:MEASURE"],
    "expected_macros": ["EVENT_TO_MEASURE"],
    "expected_operators": ["OPERATION_METRIC"],
}
NONE_ITEM = {
    "id": "t03_none", "question": "대구와 부산 중 어디가 더 빠른가요?",
    "expected_concepts": [], "expected_macros": ["NONE"], "expected_operators": [],
}

CONCEPTS = [
    {"id": "op", "concept": "EVENT", "subtype": "operation", "role": "SUPPORT",
     "source": "implicit"},
    {"id": "r", "concept": "AMOUNT", "subtype": "revenue", "role": "MEASURE",
     "source": "implicit"},
]


def grounding(factors, concepts=CONCEPTS):
    return json.dumps({"concepts": concepts, "factors": factors}, ensure_ascii=False)


GOOD = grounding({"taxi_type": "private", "aggregation": "avg"})
UNSUPPORTED = json.dumps({"unsupported": True})


class _Response:
    def __init__(self, status_code=200, body=None):
        self.status_code = status_code
        self._body = body

    def json(self):
        if isinstance(self._body, Exception):
            raise self._body
        return self._body


class FakeServer:
    """unload와 /api/ps를 흉내 낸다."""

    def __init__(self, *, unload_reason="unload", stays_loaded=False,
                 unload_status=200, raise_on_unload=False):
        self.loaded = True
        self.unload_reason = unload_reason
        self.stays_loaded = stays_loaded
        self.unload_status = unload_status
        self.raise_on_unload = raise_on_unload
        self.unloads = 0

    def post(self, url, json=None, timeout=None):
        assert url.endswith("/api/generate") and json["keep_alive"] == 0
        self.unloads += 1
        if self.raise_on_unload:
            raise ConnectionError("down")
        if not self.stays_loaded:
            self.loaded = False
        return _Response(self.unload_status, {"done_reason": self.unload_reason})

    def get(self, url, timeout=None):
        assert url.endswith("/api/ps")
        models = [{"name": "fake-model"}] if self.loaded else []
        return _Response(200, {"models": models})


class FakeLLM:
    """응답을 차례로 돌려준다. unload 뒤 첫 호출만 cold load를 보고한다."""

    model = "fake-model"

    def __init__(self, contents, server=None, *, always_warm=False):
        self.contents = list(contents)
        self.server = server
        self.always_warm = always_warm
        self.calls = 0

    def chat(self, messages, tools=None):
        self.calls += 1
        cold = False
        if self.server is not None and not self.server.loaded:
            self.server.loaded = True
            cold = not self.always_warm
        content = self.contents.pop(0)
        if isinstance(content, Exception):
            raise content
        return {"message": {"content": content}, "done_reason": "stop",
                "load_duration": COLD_NS if cold else WARM_NS,
                "prompt_eval_count": 100, "eval_count": 10,
                "total_duration": 4_000_000_000}


def make_reset(server):
    clock = iter(range(0, 10_000)).__next__
    return A.OllamaStateReset("http://fake", "fake-model", http=server,
                              timeout=5, sleep=lambda _: None,
                              clock=lambda: float(clock()))


def run(tmp, items, llm_contents, *, arms=("T0", "T0"), repetitions=1,
        server=None, max_invalid=0, always_warm=False):
    server = server or FakeServer()
    llm = FakeLLM(llm_contents, server, always_warm=always_warm)
    variants = [A.build_variant(name) for name in arms]
    meta = {
        "protocol": A.PROTOCOL, "run_id": "test", "model": "fake-model",
        "arms": [{"label": label, "variant": v.name, "prompt_sha256": v.sha256}
                 for label, v in zip("AB", variants)],
        "query_ids": [item["id"] for item in items],
        "repetitions": repetitions,
    }
    run_dir = Path(tmp) / "run"
    A.run_protocol(items, list(zip("AB", variants)), repetitions=repetitions,
                   reset=make_reset(server), client=llm,
                   composer=MacroComposer(MacroLibrary.from_directory()),
                   run_dir=run_dir, meta=meta, max_invalid=max_invalid,
                   log=lambda _: None)
    return run_dir, llm, server


def rows_of(run_dir):
    return [json.loads(line) for line in
            (run_dir / "observations.jsonl").read_text(encoding="utf-8").splitlines()]


class ResetTest(unittest.TestCase):
    def test_successful_reset_is_verified_by_ps(self):
        result = make_reset(FakeServer()).reset()
        self.assertTrue(result.succeeded)
        self.assertEqual(result.loaded_after, ())

    def test_model_that_stays_loaded_is_a_failed_reset(self):
        result = make_reset(FakeServer(stays_loaded=True)).reset()
        self.assertFalse(result.succeeded)
        self.assertIn("fake-model", result.loaded_after)

    def test_wrong_done_reason_is_a_failed_reset(self):
        result = make_reset(FakeServer(unload_reason="stop")).reset()
        self.assertFalse(result.succeeded)

    def test_http_error_and_connection_error_are_failed_resets(self):
        self.assertFalse(make_reset(FakeServer(unload_status=500)).reset().succeeded)
        self.assertFalse(make_reset(FakeServer(raise_on_unload=True)).reset().succeeded)


class ObservationValidityTest(unittest.TestCase):
    def test_every_valid_observation_carries_a_successful_reset(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir, _, server = run(tmp, [REVENUE_ITEM], [GOOD, GOOD])
            rows = rows_of(run_dir)
        self.assertEqual(server.unloads, 2)
        for row in rows:
            self.assertEqual(row["measurement"], A.VALID)
            self.assertTrue(row["reset_attempted"])
            self.assertTrue(row["reset_succeeded"])
            self.assertTrue(row["cold_load_verified"])

    def test_reset_failure_aborts_without_calling_the_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            server = FakeServer(stays_loaded=True)
            with self.assertRaises(A.BenchmarkAborted):
                run(tmp, [REVENUE_ITEM], [GOOD, GOOD], server=server)
            rows = rows_of(Path(tmp) / "run")
            status = json.loads((Path(tmp) / "run" / "run_status.json").read_text())
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["measurement"], A.INVALID)
        self.assertEqual(rows[0]["invalid_reason"], "reset_failed")
        self.assertEqual(rows[0]["llm_calls"], [])
        self.assertFalse(status["completed"])
        self.assertIn("무효", status["aborted_reason"])

    def test_warm_first_call_means_the_reset_did_not_take_effect(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir, _, _ = run(tmp, [REVENUE_ITEM], [GOOD, GOOD],
                                always_warm=True, max_invalid=5)
            rows = rows_of(run_dir)
        for row in rows:
            self.assertEqual(row["measurement"], A.INVALID)
            self.assertEqual(row["invalid_reason"], "reset_not_effective")

    def test_invalid_observations_are_excluded_from_pairs_and_denominator(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir, _, _ = run(tmp, [REVENUE_ITEM], [GOOD, GOOD],
                                always_warm=True, max_invalid=5)
            meta, rows, report = A.load_run(run_dir)
        summary = A.summarize(meta, rows, report)
        self.assertEqual(summary["valid_observations"], 0)
        self.assertEqual(summary["pairs"], 0)
        self.assertEqual(report.invalid_observations, 2)


class PromptIdentityTest(unittest.TestCase):
    def _digest(self, text):
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def test_pinned_variants_match_their_recorded_hashes(self):
        for name, expected in A.PINNED_SHA256.items():
            with self.subTest(variant=name):
                self.assertEqual(A.build_variant(name).sha256, expected)

    def test_t0_is_byte_identical_to_production(self):
        production = GeoFlowPlanner(client=A._StubClient()).system_prompt()
        self.assertEqual(A.build_variant("T0").prompt, production)

    def test_d_pre_differs_only_in_the_taxi_type_meaning(self):
        d_pre = A.build_variant("D_PRE").prompt
        t0 = A.build_variant("T0").prompt
        self.assertIn("    택시 유형 조건.", d_pre)
        self.assertNotIn("개념이 아니다", d_pre)
        self.assertEqual(len(t0) - len(d_pre), 199)

    def test_hash_mismatch_refuses_to_run(self):
        with self.assertRaises(A.BenchmarkAborted):
            A.build_variant("T0", pinned={"T0": "0" * 64})

    def test_building_variants_leaves_production_untouched(self):
        before = self._digest(GeoFlowPlanner(client=A._StubClient()).system_prompt())
        A.build_variant("D_PRE")
        after = self._digest(GeoFlowPlanner(client=A._StubClient()).system_prompt())
        self.assertEqual(before, after)

    def test_each_observation_records_the_prompt_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir, _, _ = run(tmp, [REVENUE_ITEM], [GOOD, GOOD],
                                arms=("D_PRE", "T0"))
            rows = rows_of(run_dir)
        hashes = {row["variant"]: row["prompt_sha256"] for row in rows}
        self.assertEqual(hashes, {"D_PRE": A.PINNED_SHA256["D_PRE"],
                                  "T0": A.PINNED_SHA256["T0"]})


class ProtocolTest(unittest.TestCase):
    def test_order_alternates_deterministically(self):
        orders = [A.arm_order(index, rep, ["A", "B"])
                  for rep in (1, 2) for index in range(3)]
        self.assertEqual(orders, [["B", "A"], ["A", "B"], ["B", "A"],
                                  ["A", "B"], ["B", "A"], ["A", "B"]])

    def test_records_follow_the_order_and_reset_before_every_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir, _, server = run(tmp, [REVENUE_ITEM, REVENUE_ITEM | {"id": "t01b"}],
                                     [GOOD] * 8, repetitions=2)
            rows = rows_of(run_dir)
        self.assertEqual(server.unloads, len(rows))
        sequence = [(row["id"], row["repeat_index"], row["arm"]) for row in rows]
        self.assertEqual(sequence, [
            ("t01_revenue", 1, "B"), ("t01_revenue", 1, "A"),
            ("t01b", 1, "A"), ("t01b", 1, "B"),
            ("t01_revenue", 2, "A"), ("t01_revenue", 2, "B"),
            ("t01b", 2, "B"), ("t01b", 2, "A"),
        ])
        self.assertEqual({row["execution_order"] for row in rows}, {1, 2})

    def test_self_comparison_is_supported(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir, _, _ = run(tmp, [REVENUE_ITEM], [GOOD, GOOD], arms=("T0", "T0"))
            meta, rows, report = A.load_run(run_dir)
        summary = A.summarize(meta, rows, report)
        self.assertEqual(summary["pairs"], 1)
        self.assertEqual(summary["agreement"]["raw_equal"]["rate"], 1.0)
        self.assertEqual(summary["paired"]["discordant"], 0)

    def test_existing_run_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            run(tmp, [REVENUE_ITEM], [GOOD, GOOD])
            with self.assertRaises(FileExistsError):
                run(tmp, [REVENUE_ITEM], [GOOD, GOOD])


class RawResponseTest(unittest.TestCase):
    def test_raw_response_is_kept_on_every_rejection_path(self):
        """INVALID_FACTOR는 오류 context에 원문을 싣지 않는다. client에서 받는다."""
        cases = {
            "INVALID_FACTOR": grounding({"dimension": "week"}),
            "INVALID_SUBTYPE": grounding({}, [{"id": "t", "concept": "OBJECT",
                                               "subtype": "taxi_type", "role": "COND",
                                               "source": "user", "value": "x"}] + CONCEPTS),
            "JSON_NOT_FOUND": "죄송합니다",
            "UNSUPPORTED_QUESTION": UNSUPPORTED,
        }
        for status, content in cases.items():
            with self.subTest(status=status), tempfile.TemporaryDirectory() as tmp:
                run_dir, _, _ = run(tmp, [REVENUE_ITEM], [content, content])
                row = rows_of(run_dir)[0]
                self.assertEqual(row["status"], status)
                self.assertEqual(row["raw_text"], content.strip())
                self.assertEqual(row["llm_calls"][0]["content"], content)

    def test_repair_response_is_recorded_separately(self):
        month = grounding({"bucket": "month", "aggregation": "max"})
        patch = json.dumps({"kind": "factor_completion", "factors": {"rollup": "max"}})
        with tempfile.TemporaryDirectory() as tmp:
            run_dir, _, _ = run(tmp, [MONTH_ITEM], [month, patch, month, patch])
            row = rows_of(run_dir)[0]
        self.assertTrue(row["repair_attempted"])
        self.assertTrue(row["repair_succeeded"])
        self.assertEqual([call["phase"] for call in row["llm_calls"]],
                         ["initial", "repair"])
        self.assertEqual(row["raw_text"], month)
        self.assertEqual(row["repair_raw_texts"], [patch])
        self.assertEqual(row["planner_calls"], 2)

    def test_record_fields_exist_even_when_the_model_call_fails(self):
        """초기화 누락으로 KeyError가 났던 자리다."""
        with tempfile.TemporaryDirectory() as tmp:
            run_dir, _, _ = run(tmp, [REVENUE_ITEM],
                                [ConnectionError("x")] * 3 + [GOOD], max_invalid=5)
            row = rows_of(run_dir)[0]
        for key in ("raw_text", "initial_error", "repair_attempted", "factors"):
            self.assertIn(key, row)
        self.assertEqual(row["status"], "PLANNER_CALL_FAILED")


class NoLeakTest(unittest.TestCase):
    def test_previous_observation_does_not_leak_into_the_next(self):
        month = grounding({"bucket": "month", "aggregation": "max"})
        patch = json.dumps({"kind": "factor_completion", "factors": {"rollup": "max"}})
        with tempfile.TemporaryDirectory() as tmp:
            run_dir, _, _ = run(tmp, [MONTH_ITEM], [month, patch, UNSUPPORTED])
            first, second = rows_of(run_dir)
        self.assertTrue(first["repair_attempted"])
        self.assertFalse(second["repair_attempted"])
        self.assertEqual(second["factors"], {})
        self.assertEqual(second["repair_raw_texts"], [])
        self.assertEqual(len(second["llm_calls"]), 1)
        self.assertEqual(second["raw_text"], UNSUPPORTED)


class ScoringTest(unittest.TestCase):
    def _one(self, item, content):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir, _, _ = run(tmp, [item], [content, content])
            return rows_of(run_dir)[0]

    def test_expected_none_refusal_is_a_correct_rejection(self):
        row = self._one(NONE_ITEM, UNSUPPORTED)
        self.assertTrue(row["correct"])
        self.assertEqual(row["category"], "correct")

    def test_expected_none_with_a_valid_plan_is_wrong(self):
        self.assertFalse(self._one(NONE_ITEM, GOOD)["correct"])

    def test_refusing_an_answerable_question_is_wrong(self):
        row = self._one(REVENUE_ITEM, UNSUPPORTED)
        self.assertFalse(row["correct"])
        self.assertEqual(row["category"], "unsupported")

    def test_taxi_type_as_concept_is_its_own_category(self):
        bad = grounding({}, [{"id": "t", "concept": "OBJECT", "subtype": "corporate",
                              "role": "COND", "source": "user", "value": "x"}] + CONCEPTS)
        self.assertEqual(self._one(REVENUE_ITEM, bad)["category"], "taxi_type_as_concept")


class IntegrityTest(unittest.TestCase):
    def _run_and_edit(self, tmp, edit):
        run_dir, _, _ = run(tmp, [REVENUE_ITEM], [GOOD, GOOD])
        path = run_dir / "observations.jsonl"
        path.write_text(edit(path.read_text(encoding="utf-8")), encoding="utf-8")
        return A.load_run(run_dir)

    def test_duplicate_record_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, _, report = self._run_and_edit(
                tmp, lambda text: text + text.splitlines()[0] + "\n")
        self.assertTrue(report.duplicate_keys)
        self.assertFalse(report.clean)

    def test_truncated_line_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, _, report = self._run_and_edit(
                tmp, lambda text: text + text.splitlines()[0][:50] + "\n")
        self.assertTrue(report.truncated_lines)
        self.assertFalse(report.clean)

    def test_missing_observation_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, _, report = self._run_and_edit(
                tmp, lambda text: text.splitlines()[0] + "\n")
        self.assertEqual(len(report.missing_keys), 1)
        self.assertFalse(report.clean)

    def test_unfinished_run_is_not_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir, _, _ = run(tmp, [REVENUE_ITEM], [GOOD, GOOD])
            status = run_dir / "run_status.json"
            status.write_text(json.dumps({"completed": False}), encoding="utf-8")
            _, _, report = A.load_run(run_dir)
        self.assertFalse(report.clean)

    def test_analysis_refuses_dirty_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir, _, _ = run(tmp, [REVENUE_ITEM], [GOOD, GOOD])
            path = run_dir / "observations.jsonl"
            path.write_text(path.read_text(encoding="utf-8").splitlines()[0] + "\n",
                            encoding="utf-8")
            with self.assertRaises(SystemExit):
                A.cmd_analyze(type("Args", (), {"run_dir": run_dir,
                                                "allow_incomplete": False})())


class ComparisonTest(unittest.TestCase):
    def test_canonical_form_ignores_notation_only(self):
        reordered = json.dumps({"factors": {"aggregation": "avg", "taxi_type": "private"},
                                "concepts": [dict(reversed(list(c.items())))
                                             for c in reversed(CONCEPTS)]})
        renamed = grounding({"taxi_type": "private", "aggregation": "avg"},
                            [dict(c, id=c["id"] + "_x", text="표현") for c in CONCEPTS])
        base = A.canonical_grounding(GOOD)
        self.assertEqual(A.canonical_grounding(reordered), base)
        self.assertEqual(A.canonical_grounding(renamed), base)

    def test_canonical_form_keeps_meaning_differences(self):
        other = grounding({"taxi_type": "corporate", "aggregation": "avg"})
        subtype = grounding({"taxi_type": "private", "aggregation": "avg"},
                            [CONCEPTS[0], dict(CONCEPTS[1], subtype="hours")])
        duplicate = grounding({}, [CONCEPTS[0], dict(CONCEPTS[1], id="op")])
        distinct = grounding({}, CONCEPTS)
        base = A.canonical_grounding(GOOD)
        self.assertNotEqual(A.canonical_grounding(other), base)
        self.assertNotEqual(A.canonical_grounding(subtype), base)
        # id는 이름일 뿐이지만 중복 여부는 결과를 바꾼다.
        self.assertNotEqual(A.canonical_grounding(duplicate),
                            A.canonical_grounding(distinct))

    def test_unreadable_response_has_no_canonical_form(self):
        self.assertIsNone(A.canonical_grounding("죄송합니다"))
        self.assertIsNone(A.canonical_grounding(""))

    def test_exact_mcnemar(self):
        self.assertEqual(A.mcnemar_exact(0, 0), 1.0)
        self.assertAlmostEqual(A.mcnemar_exact(0, 5), 0.0625)
        self.assertAlmostEqual(A.mcnemar_exact(3, 11), 0.0574, places=4)
        self.assertEqual(A.mcnemar_exact(4, 4), 1.0)

    def test_summary_separates_agreement_levels(self):
        """원문은 달라도 의미가 같을 수 있고, 의미가 달라도 결과는 같을 수 있다."""
        reordered = json.dumps({"factors": {"aggregation": "avg", "taxi_type": "private"},
                                "concepts": CONCEPTS})
        with tempfile.TemporaryDirectory() as tmp:
            run_dir, _, _ = run(tmp, [REVENUE_ITEM], [GOOD, reordered])
            meta, rows, report = A.load_run(run_dir)
        agreement = A.summarize(meta, rows, report)["agreement"]
        self.assertEqual(agreement["raw_equal"]["count"], 0)
        self.assertEqual(agreement["semantic_equal"]["count"], 1)
        self.assertEqual(agreement["behavior_equal"]["count"], 1)

    def test_printers_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir, _, _ = run(tmp, [REVENUE_ITEM], [GOOD, GOOD], arms=("D_PRE", "T0"))
            meta, rows, report = A.load_run(run_dir)
        summary = A.summarize(meta, rows, report)
        A.print_summary(summary, out=io.StringIO())
        A.print_floor([summary], out=io.StringIO())


if __name__ == "__main__":
    unittest.main()
