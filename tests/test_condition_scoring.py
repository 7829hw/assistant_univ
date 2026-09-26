# -*- coding: utf-8 -*-
"""조건 채점기 v2와 평가 기록 보호. 관측 기록은 손으로 만든다(제품 코드를 쓰지 않는다)."""

import json
import tempfile
import unittest
from pathlib import Path

import condition_scoring as cs
from evaluation_records import verify_inputs, write_analysis, write_new

GOLD_YAML = """
questions:
  - {id: q1, question: "지난달 서구 개인택시 평균 수입은?",
     expected: {outcome: answered, plan: {final: avg},
                conditions: {date: {accept: [last_month, 20260801-20260831], request: last_month},
                             taxi_type: private, place: 서구}}}
  - {id: q2, question: "지난달 서구 전체 택시 평균 수입은?",
     expected: {outcome: answered, plan: {final: avg},
                conditions: {date: {accept: [last_month, 20260801-20260831], request: last_month},
                             taxi_stated: explicit_all, place: 서구}}}
  - {id: q3, question: "2026년 9월 24일 서구 택시 수입 합계는?",
     expected: {outcome: answered, contract_executable: true, plan: {final: sum},
                conditions: {date: {accept: ["20260924"]}, taxi_stated: not_stated, place: 서구}}}
"""


def gold(tmp):
    path = Path(tmp) / "gold.yaml"
    path.write_text(GOLD_YAML, encoding="utf-8")
    return cs.load_gold(path)[1]


def grounding(date=None, taxi=None, places=("서구",), final="avg"):
    factors = {}
    if date is not None:
        factors["date"] = date
    if taxi is not None:
        factors["taxi_type"] = taxi
    return {"factors": factors, "aggregation": {"inner": final},
            "concepts": [{"concept": "LOCATION", "role": "SUBCOND", "value": {"name": p}}
                         for p in places]}


def record(qid, g, *, outcome="answered", dates=None, taxis=(), places=("서구",),
           audit=None, code=None):
    row = {"id": qid, "arm": "flat", "outcome": outcome, "grounding": g,
           "error": {"code": code} if code else None, "condition_audit": audit}
    if dates is not None:
        row["executed"] = {"measure_calls": max(1, len(dates)), "dates": list(dates),
                           "taxi_types": list(taxis), "place_lookups": list(places)}
    return row


class InterpretationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.gold = gold(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_equivalent_expressions_score_the_same(self):
        token = cs.judge(record("q1", grounding("last_month", "private"),
                                dates=["last_month"], taxis=["private"]), self.gold["q1"])
        absolute = cs.judge(record("q1", grounding("20260801-20260831", "private"),
                                   dates=["20260801-20260831"], taxis=["private"]),
                            self.gold["q1"])
        self.assertTrue(token["interpretation"]["ok"])
        self.assertTrue(absolute["interpretation"]["ok"])
        self.assertEqual(token["correct_answer"], absolute["correct_answer"])
        # 전체 택시: all을 적든 생략하든 같은 실행 의미다. 명시했다는 사실은 따로 남는다.
        with_all = cs.judge(record("q2", grounding("last_month", "all"),
                                   dates=["last_month"], taxis=["all"]), self.gold["q2"])
        omitted = cs.judge(record("q2", grounding("last_month"), dates=["last_month"]),
                           self.gold["q2"])
        self.assertEqual(with_all["interpretation"]["status"]["taxi_type"], "ok")
        self.assertEqual(omitted["interpretation"]["status"]["taxi_type"], "ok")
        self.assertEqual(with_all["taxi_stated"], "explicit_all")

    def test_private_or_corporate_is_not_merged_with_all(self):
        wrong = cs.judge(record("q2", grounding("last_month", "private"),
                                dates=["last_month"], taxis=["private"]), self.gold["q2"])
        self.assertEqual(wrong["interpretation"]["status"]["taxi_type"], "added")
        self.assertTrue(wrong["silent_semantic_error"])
        missing = cs.judge(record("q1", grounding("last_month", "all")), self.gold["q1"])
        self.assertEqual(missing["interpretation"]["status"]["taxi_type"], "missing")

    def test_rejected_grounding_is_not_counted_as_missing_conditions(self):
        row = cs.judge(record("q1", None, outcome="failed", code="INVALID_FACTOR"),
                       self.gold["q1"])
        self.assertFalse(row["interpretation"]["judgeable"])
        self.assertNotIn("missing", row["interpretation"]["status"].values())
        summary, _ = cs.score_records(
            [record("q1", None, outcome="failed", code="INVALID_FACTOR")], self.gold, ["flat"])
        arm = summary["arms"]["flat"]
        self.assertEqual((arm["not_judgeable"], arm["interpretation_judgeable"]), (1, 0))
        self.assertEqual(arm["interpretation_status"]["taxi_type"], {})

    def test_unverifiable_status_is_not_counted_as_verified(self):
        audit = {"date": {"status": "interpreted"}, "taxi_type": {"status": "unverifiable"}}
        row = cs.judge(record("q1", grounding("last_month", "private"), dates=["last_month"],
                              taxis=["private"], audit=audit), self.gold["q1"])
        self.assertTrue(row["verified_claims"]["date"]["verified_ok"])
        self.assertFalse(row["verified_claims"]["taxi_type"]["verified_ok"])
        self.assertTrue(row["verified_claims"]["taxi_type"]["unverified"])

    def test_request_match_and_provider_semantics_are_separate(self):
        row = cs.judge(record("q1", grounding("last_month", "private"), dates=["last_month"],
                              taxis=["private"]), self.gold["q1"])
        self.assertTrue(row["request"]["ok"])
        self.assertFalse(row["provider"]["date_confirmed"])
        self.assertTrue(row["answered_provider_unverified"])
        self.assertIs(row["mock_correct"], True)
        single = cs.judge(record("q3", grounding("20260924", final="sum"), dates=["20260924"]),
                          self.gold["q3"])
        self.assertTrue(single["provider"]["date_confirmed"])
        self.assertFalse(single["answered_provider_unverified"])
        self.assertEqual(single["real_data_correct"], "not_measured")

    def test_daily_composition_is_not_mock_comparable(self):
        days = [f"202608{d:02d}" for d in range(1, 32)]
        row = cs.judge(record("q1", grounding("last_month", "private"), dates=days,
                              taxis=["private"]), self.gold["q1"])
        self.assertTrue(row["request"]["ok"])
        # 날짜 하나하나는 단일 날짜지만, 합성에 필요한 기록 계약이 TIMS에 없다.
        self.assertFalse(row["provider"]["date_confirmed"])
        self.assertTrue(row["provider"]["composition_unverified"])
        self.assertEqual(row["mock_correct"], "mock_not_comparable")
        short = cs.judge(record("q1", grounding("last_month", "private"), dates=days[:-1],
                                taxis=["private"]), self.gold["q1"])
        self.assertFalse(short["request"]["date_ok"])

    def test_good_bad_and_unnecessary_corrections(self):
        audit = {"corrections": [
            {"condition": "date", "from": "20260501-20260531", "to": "last_month"},  # good
            {"condition": "taxi_type", "from": "private", "to": None},                # bad
        ]}
        row = cs.judge(record("q1", grounding("last_month"), audit=audit), self.gold["q1"])
        self.assertEqual(row["corrections"], {"good": 1, "bad": 1})
        audit = {"corrections": [
            {"condition": "taxi_type", "from": None, "to": "all"},                     # 같은 의미
            {"condition": "date", "from": "20260801-20260831", "to": "last_month"},   # 같은 의미
        ]}
        row = cs.judge(record("q2", grounding("last_month", "all"), audit=audit),
                       self.gold["q2"])
        self.assertEqual(row["corrections"], {"unnecessary": 2})

    def test_contract_refusal_is_separated_from_unjust_refusal(self):
        contract = cs.judge(record("q1", grounding("last_month", "private"),
                                   outcome="unsupported", code="DATE_EXECUTION_UNVERIFIED"),
                            self.gold["q1"])
        self.assertTrue(contract["contract_refusal"])
        self.assertFalse(contract["unjust_refusal"])
        self.assertEqual(contract["block_cause"], "contract")
        # 계약상 실행할 수 있는 질문(단일 날짜)을 멈추면 부당한 거부다.
        unjust = cs.judge(record("q3", grounding("20260924", final="sum"),
                                 outcome="unsupported", code="DATE_EXECUTION_UNVERIFIED"),
                          self.gold["q3"])
        self.assertTrue(unjust["unjust_refusal"])
        aggregation = cs.judge(record("q1", grounding("last_month", "private"),
                                      outcome="needs_clarification",
                                      code="AMBIGUOUS_INNER_AGGREGATION"), self.gold["q1"])
        self.assertEqual(aggregation["block_cause"], "aggregation")
        # 계약 코드여도 집계 계획이 틀렸다면(지어낸 bucket) 집계 원인이다.
        invented = dict(grounding("last_month", "private"),
                        aggregation={"bucket": "month", "inner": "avg", "outer": "avg"})
        wrong_plan = cs.judge(record("q1", invented, outcome="unsupported",
                                     code="UNVERIFIED_TIMS_CONTRACT"), self.gold["q1"])
        self.assertEqual(wrong_plan["block_cause"], "aggregation")
        self.assertFalse(wrong_plan["contract_refusal"])


class StructureTest(unittest.TestCase):
    """v2.4: dimension·order·limit과 값/구간 반환을 판정한다."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.gold = gold(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_list_query_is_not_a_correct_scalar_answer(self):
        g = grounding("20260924", final="sum")
        g["factors"].update(dimension="emd", order="bottom")
        row = cs.judge(record("q3", g, dates=["20260924"]), self.gold["q3"])
        self.assertEqual(row["structure"]["wrong"], ["dimension", "order"])
        self.assertFalse(row["plan_ok"])
        self.assertTrue(row["silent_semantic_error"])
        plain = cs.judge(record("q3", grounding("20260924", final="sum"), dates=["20260924"]),
                         self.gold["q3"])
        self.assertTrue(plain["structure"]["ok"])
        self.assertTrue(plain["correct_answer"])

    def test_declared_structure_and_group_selection(self):
        gold = dict(self.gold["q3"], structure={"dimension": "emd", "order": "top", "limit": 3})
        g = grounding("20260924", final="sum")
        g["factors"].update(dimension="emd", order="top", limit=3)
        self.assertTrue(cs.judge(record("q3", g), gold)["structure"]["ok"])
        g["factors"]["limit"] = 5
        self.assertEqual(cs.judge(record("q3", g), gold)["structure"]["wrong"], ["limit"])
        select_gold = dict(self.gold["q3"], plan={"bucket": "week", "inner": "sum",
                                                   "select": "max"})
        value_answer = dict(grounding("20260924"), aggregation={
            "bucket": "week", "inner": "sum", "outer": "max"})
        row = cs.judge(record("q3", value_answer), select_gold)
        self.assertEqual((row["returns"], row["returns_ok"], row["plan_ok"]),
                         ("value", False, False))


class SlotTest(unittest.TestCase):
    """v2.7: 집계 의미를 칸별로 센다. 이전 판정(plan_ok)은 그대로다."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.gold = gold(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_value_versus_group_differs_only_in_outer_and_result_kind(self):
        want = dict(self.gold["q3"], plan={"bucket": "week", "inner": "avg", "final": "max"})
        chose_group = dict(grounding("20260924"), aggregation={
            "bucket": "week", "inner": "avg", "select": "max"})
        row = cs.judge(record("q3", chose_group, dates=["20260924"]), want)
        slots = row["slots"]
        self.assertEqual({key: slots[key] for key in ("bucket", "inner", "outer", "result_kind")},
                         {"bucket": True, "inner": True, "outer": False, "result_kind": False})
        self.assertFalse(row["plan_ok"])

    def test_rejected_grounding_and_unsupported_gold_are_not_slot_judged(self):
        row = cs.judge(record("q3", None, outcome="failed"), self.gold["q3"])
        self.assertIsNone(row["slots"])
        unsupported = dict(self.gold["q3"], outcome="unsupported", plan=None)
        row = cs.judge(record("q3", grounding("20260924", final="sum")), unsupported)
        self.assertIsNone(row["slots"])
        self.assertTrue(row["silent_semantic_error"])

    def test_retrieval_coverage_uses_store_tags(self):
        want = dict(self.gold["q3"], retrieval_tags=["value_not_group"])
        rec = record("q3", grounding("20260924", final="sum"), dates=["20260924"])
        self.assertIsNone(cs.judge(rec, want)["retrieval_covered"])
        rec["retrieval"] = {"included": ["ex06", "ex07"]}
        self.assertFalse(cs.judge(rec, want)["retrieval_covered"])
        rec["retrieval"] = {"included": ["ex06", "ex09"]}
        self.assertTrue(cs.judge(rec, want)["retrieval_covered"])


class ReferenceAnswerTest(unittest.TestCase):
    """v2.5: reference 관측은 계산 값과 reference 계약으로 판정한다."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = gold(self.tmp.name)["q1"]
        self.value_gold = dict(base, answer={"value": 103333.33333333333})
        self.group_gold = dict(base, plan={"bucket": "week", "inner": "sum", "select": "max"},
                               answer={"value": 300000,
                                       "groups": ["20260803-20260809", "20260810-20260816"]})

    def tearDown(self):
        self.tmp.cleanup()

    def reference_record(self, g, final_value, dates=("20260801-20260831",)):
        row = record("q1", g, dates=list(dates), taxis=["private"])
        row.update(final_value=final_value, execution_profile={"provider": "reference"})
        return row

    def test_value_and_reference_contract(self):
        row = cs.judge(self.reference_record(grounding("last_month", "private"), 1240000 / 12),
                       self.value_gold)
        self.assertTrue(row["answer_correct"])
        self.assertTrue(row["provider"]["date_confirmed"])  # reference 계약: 범위 확인
        self.assertEqual(row["mock_correct"], "not_applicable")
        wrong = cs.judge(self.reference_record(grounding("last_month", "private"), 680000 / 6),
                         self.value_gold)
        self.assertFalse(wrong["answer_correct"])

    def test_weekly_range_calls_that_tile_the_period_preserve_the_date(self):
        weeks = ["20260801-20260802", "20260803-20260809", "20260810-20260816",
                 "20260817-20260823", "20260824-20260830", "20260831-20260831"]
        row = cs.judge(self.reference_record(grounding("last_month", "private"), 1, weeks),
                       self.value_gold)
        self.assertTrue(row["request"]["date_ok"])
        gap = cs.judge(self.reference_record(grounding("last_month", "private"), 1,
                                             weeks[:2] + weeks[3:]), self.value_gold)
        self.assertFalse(gap["request"]["date_ok"])

    def test_selected_groups_must_match_including_ties(self):
        g = dict(grounding("last_month", "private"),
                 aggregation={"bucket": "week", "inner": "sum", "select": "max"})
        both = {"select": "max", "value": 300000, "groups": [
            {"label": "20260803-20260809"}, {"label": "20260810-20260816"}]}
        self.assertTrue(cs.judge(self.reference_record(g, both), self.group_gold)["answer_correct"])
        one = dict(both, groups=both["groups"][:1])
        self.assertFalse(cs.judge(self.reference_record(g, one), self.group_gold)["answer_correct"])


class RecordProtectionTest(unittest.TestCase):
    def test_existing_results_are_never_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp)
            observations = run / "observations.jsonl"
            observations.write_text('{"id": "q1"}\n', encoding="utf-8")
            first = write_new(run / "summary.json", {"n": 1})
            with self.assertRaises(FileExistsError):
                write_new(first, {"n": 2})
            scorer = {"name": "t", "version": "1", "source": __file__}
            a = write_analysis(run, analysis_id="v2", outputs={"summary.json": {"n": 2}},
                               scorer=scorer, config={}, inputs=[observations])
            b = write_analysis(run, analysis_id="v2", outputs={"summary.json": {"n": 3}},
                               scorer=scorer, config={}, inputs=[observations],
                               corrects={"previous": [str(a)], "reason": "테스트"})
            self.assertEqual((a.name, b.name), ("v2", "v2-2"))
            self.assertEqual(json.loads(first.read_text())["n"], 1)
            self.assertEqual(json.loads((a / "summary.json").read_text())["n"], 2)
            manifest = json.loads((b / "manifest.json").read_text())
            self.assertEqual(manifest["corrects"]["reason"], "테스트")
            self.assertIn(str(observations), manifest["inputs"])
            self.assertEqual(verify_inputs(b), [])
            observations.write_text('{"id": "q2"}\n', encoding="utf-8")
            self.assertEqual(verify_inputs(b), [str(observations)])


if __name__ == "__main__":
    unittest.main()
