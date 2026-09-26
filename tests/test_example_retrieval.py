# -*- coding: utf-8 -*-
"""질문–graph 예시 저장소, 검색 index, grounding 문맥 연결을 결정적으로 검증한다.

LLM을 부르지 않는다(대본 grounding). reference 예시의 기대값은 이 파일의 독립 SQL로 다시
계산해 대조한다(provider·compiler 코드로 만들지 않는다). 검색은 lexical(임베딩 아님)과
가짜 Ollama 서버로 시험한다.
"""

import copy
import csv
import json
import os
import re
import shutil
import sqlite3
import tempfile
import unittest
from datetime import date
from pathlib import Path

os.environ.setdefault("ASSISTANT_TOOL_PROVIDER", "mock")

import yaml  # noqa: E402

from geoflow import examples as example_store  # noqa: E402
from geoflow.errors import GeoFlowError  # noqa: E402
from geoflow.examples import (  # noqa: E402
    STORE_PATH, load_store, result_kind_of, serialize_graph, verify_example, verify_store,
)
from geoflow.pipeline import GeoFlowPipeline  # noqa: E402
from geoflow.planner import GeoFlowPlanner  # noqa: E402
from geoflow.providers import REFERENCE, profile_for  # noqa: E402
from geoflow.retrieval import (  # noqa: E402
    LEXICAL_INDEX_PATH, SECTION_HEADING, ExampleRetriever, FixedExamples, LexicalEmbedder,
    OllamaEmbedder, RetrievalError, RetrievalSettings, build_index, load_index, normalize,
    render_example, save_index,
)
from tests.test_geoflow_composition import TOOLS  # noqa: E402
from tool_executor import ToolExecutor  # noqa: E402
from tool_handlers import get_tool_handlers  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = ROOT / "reference_data" / "synthetic_operation_days.csv"
REF_DATE = date(2026, 9, 25)
GARAM, NARAE = "scope:ref:district:garam", "scope:ref:district:narae"


def sql_db():
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE ops (service_date, scope, taxi_type, revenue_krw INTEGER)")
    with open(CSV_PATH, encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            db.execute("INSERT INTO ops VALUES (?,?,?,?)", [
                row["service_date"], row["scope"], row["taxi_type"],
                int(row["revenue_krw"]) if row["revenue_krw"] else None])
    return db


# 주: 월요일 시작, 기간 경계에서 자름. 자료 없는 주는 없다(아래 두 조건에서는 매주 기록이 있다).
WEEKLY = """
SELECT min(service_date) AS first, max(service_date) AS last,
       SUM(revenue_krw) AS total, AVG(revenue_krw) AS mean
FROM ops WHERE scope = :scope AND taxi_type = :taxi AND revenue_krw IS NOT NULL
  AND service_date BETWEEN :start AND :end
GROUP BY date(service_date, 'weekday 0', '-6 days') ORDER BY 1
"""


def week_label(first):
    """기록이 있는 첫날이 아니라 기간에서 자른 주 경계를 적는다(월요일 시작)."""
    day = date.fromisoformat(first)
    start = max(date.fromordinal(day.toordinal() - day.weekday()), date(2026, 8, 1))
    end = min(date.fromordinal(start.toordinal() - start.weekday() + 6), date(2026, 8, 31))
    return f"{start:%Y%m%d}-{end:%Y%m%d}"


class _Scripted:
    """대본 grounding을 돌려주고 받은 messages를 남긴다."""

    model = "scripted"

    def __init__(self, *payloads):
        self.payloads = list(payloads)
        self.messages = []

    def chat(self, messages, tools=None, **kwargs):
        self.messages.append(copy.deepcopy(messages))
        return {"message": {"content": json.dumps(self.payloads.pop(0), ensure_ascii=False)}}


def grounding(aggregation, *, where="가람구", period="last_month", taxi="private", **factors):
    concepts = [
        {"id": "place", "concept": "LOCATION", "subtype": "place", "role": "SUBCOND",
         "source": "user", "value": {"name": where}},
        {"id": "operation", "concept": "EVENT", "subtype": "operation", "role": "SUPPORT",
         "source": "implicit"},
        {"id": "revenue", "concept": "AMOUNT", "subtype": "revenue", "role": "MEASURE",
         "source": "implicit"},
    ]
    return {"concepts": concepts, "factors": {"date": period, "taxi_type": taxi,
                                              "aggregation_plan": aggregation, **factors}}


def reference_pipeline(client, selector=None):
    executor = ToolExecutor(tools=TOOLS, handlers=get_tool_handlers(REFERENCE), provider=REFERENCE)
    return GeoFlowPipeline.create(client=client, tool_executor=executor,
                                  aggregation_grounding="structured", clock=lambda: REF_DATE,
                                  execution_profile=profile_for(REFERENCE),
                                  example_selector=selector)


def copy_store(tmp, edit=None):
    """저장소를 임시 경로로 복사한다. edit(document)로 내용을 바꿀 수 있다."""
    target = Path(tmp) / "store.yaml"
    text = STORE_PATH.read_text(encoding="utf-8")
    if edit is not None:
        document = yaml.safe_load(text)
        edit(document)
        text = yaml.safe_dump(document, allow_unicode=True, sort_keys=False)
    target.write_text(text, encoding="utf-8")
    return target


# -- 1. 예시 등록 검증 ---------------------------------------------------------------


class StoreRegistrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store = load_store()

    def test_every_example_passes_registration(self):
        self.assertEqual(verify_store(self.store), {})

    def test_confusable_meanings_are_all_present(self):
        tags = {tag for example in self.store.examples for tag in example.tags}
        for needed in ("overall_average", "avg_of_bucket_sums", "max_of_bucket_avgs",
                       "bucket_select", "grouped_values_list"):
            self.assertIn(needed, tags)
        kinds = {example.result_kind for example in self.store.examples}
        self.assertEqual(kinds, {"scalar", "selected_groups", "grouped_values",
                                 "dimension_groups"})

    def test_graph_serialization_omits_condition_values(self):
        for example in self.store.examples:
            factors = example.grounding.get("factors") or {}
            for key in ("date", "taxi_type"):
                if key in factors:
                    for line in example.graph:
                        self.assertNotIn(f"{key}={factors[key]}", line, example.id)
            for concept in example.grounding.get("concepts") or []:
                name = (concept.get("value") or {}).get("name") if isinstance(
                    concept.get("value"), dict) else None
                if name:
                    self.assertFalse(any(name in line for line in example.graph), example.id)

    def test_reference_examples_match_independent_sql(self):
        db = sql_db()
        want = {}
        (total,), = db.execute("SELECT SUM(revenue_krw) FROM ops WHERE scope=? AND taxi_type=? "
                               "AND service_date BETWEEN '2026-08-01' AND '2026-08-31'",
                               (NARAE, "corporate")).fetchall()
        want["ex02"] = {"value": total}
        weeks = db.execute(WEEKLY, {"scope": NARAE, "taxi": "private", "start": "2026-08-01",
                                    "end": "2026-08-31"}).fetchall()
        self.assertEqual(len(weeks), 6)
        want["ex05"] = {"value": min(total for *_, total, _mean in weeks)}
        lowest = min(mean for *_, mean in weeks)
        want["ex07"] = {"value": lowest, "groups": [week_label(first) for first, _l, _t, mean
                                                    in weeks if mean == lowest]}
        months = db.execute(
            "SELECT strftime('%Y-%m', service_date), SUM(revenue_krw) FROM ops WHERE scope=? "
            "AND taxi_type='private' AND revenue_krw IS NOT NULL AND service_date BETWEEN "
            "'2026-07-01' AND '2026-08-31' GROUP BY 1", (GARAM,)).fetchall()
        self.assertEqual(len(months), 2)
        want["ex14"] = {"value": sum(total for _m, total in months) / 2}
        got = {example.id: {key: example.reference[key] for key in ("value", "groups")
                            if key in example.reference}
               for example in self.store.examples if example.reference}
        self.assertEqual(set(got), set(want))
        for example_id in want:
            self.assertAlmostEqual(got[example_id]["value"], want[example_id]["value"])
            self.assertEqual(got[example_id].get("groups"), want[example_id].get("groups"))

    def _tampered(self, example_id, **changes):
        example = self.store.get(example_id)
        return example.__class__(**{**example.__dict__, **changes})

    def test_registration_rejects_mismatches(self):
        cases = {
            "graph": self._tampered("ex03", graph=self.store.get("ex03").graph[:-1]),
            "macros": self._tampered("ex03", macros=("PLACE_TO_SCOPE", "EVENT_TO_MEASURE")),
            "aggregation": self._tampered("ex03", aggregation={
                "bucket": "week", "inner": "avg", "outer": "avg", "select": None}),
            "result_kind": self._tampered("ex06", result_kind="scalar"),
            "reference": self._tampered("ex07", reference={"value": 30000,
                                                           "groups": ["20260824-20260830"]}),
            "outcome": self._tampered("ex11", expected_outcome="answered", expected_error=None),
        }
        for name, example in cases.items():
            with self.subTest(name):
                self.assertTrue(verify_example(example), name)

    def test_registration_rejects_grounding_that_does_not_parse(self):
        bad = copy.deepcopy(self.store.get("ex03").grounding)
        bad["factors"]["dimension"] = "week"
        example = self._tampered("ex03", grounding=bad)
        problems = verify_example(example)
        self.assertTrue(problems and "INVALID_FACTOR" in problems[0])

    def test_store_rejects_wrong_split_and_duplicates(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = copy_store(tmp, lambda doc: doc["examples"][0].update(split="evaluation"))
            with self.assertRaises(GeoFlowError) as caught:
                load_store(path)
            self.assertEqual(caught.exception.code, "EXAMPLE_SPLIT_INVALID")
            path = copy_store(tmp, lambda doc: doc["examples"].append(doc["examples"][0]))
            with self.assertRaises(GeoFlowError) as caught:
                load_store(path)
            self.assertEqual(caught.exception.code, "EXAMPLE_DUPLICATE_ID")

    def test_result_kind_derivation(self):
        self.assertEqual(result_kind_of({"bucket": "week", "inner": "sum", "select": "max"}),
                         "selected_groups")
        self.assertEqual(result_kind_of({"bucket": "week", "inner": "sum", "outer": None}),
                         "grouped_values")
        self.assertEqual(result_kind_of({"inner": "avg"}, {"dimension": "emd"}),
                         "dimension_groups")


# -- 2. 평가 데이터와 저장소 분리 ------------------------------------------------------


def _questions_in(path):
    found = []

    def walk(node):
        if isinstance(node, dict):
            for key, value in node.items():
                if key in ("question", "text", "paraphrase") and isinstance(value, str):
                    found.append(value)
                else:
                    walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    try:
        walk(yaml.safe_load(path.read_text(encoding="utf-8")))
    except yaml.YAMLError:
        pass
    return found


class StoreIsolationTest(unittest.TestCase):
    def test_no_evaluation_or_development_question_is_in_the_store(self):
        store = {normalize(example.question): example.id for example in load_store().examples}
        files = [path for path in (ROOT / "evaluation").rglob("*.yaml")
                 if "runs" not in path.parts and "vendor_runs" not in path.parts]
        self.assertTrue(files)
        for path in files:
            for question in _questions_in(path):
                self.assertNotIn(normalize(question), store, f"{path}: {question}")

    def test_store_signatures_do_not_repeat_retrieval_evaluation_questions(self):
        """검색 평가 셋과 저장소가 같은 의미 서명(측정값·bucket·inner·outer·select)을 갖지 않는다."""
        path = ROOT / "evaluation" / "retrieval" / "retrieval_eval_v1.yaml"
        if not path.exists():
            self.skipTest("평가 셋이 아직 없다")
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        store = {example.signature: example.id for example in load_store().examples
                 if example.expected_outcome == "answered"}
        for item in document["questions"]:
            signature = item.get("signature")
            if signature is None:
                continue
            self.assertNotIn(tuple(signature), store, item["id"])


# -- 3. index와 검색 ---------------------------------------------------------------


class IndexTest(unittest.TestCase):
    def test_committed_index_matches_store_and_rebuild_is_identical(self):
        store = load_store()
        loaded = load_index(LEXICAL_INDEX_PATH, store)
        self.assertEqual(loaded.data["store"]["sha256"], store.sha256)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "index.json"
            save_index(build_index(store), path)
            self.assertEqual(path.read_text(encoding="utf-8"),
                             LEXICAL_INDEX_PATH.read_text(encoding="utf-8"))

    def test_stale_index_is_rejected(self):
        edits = {
            "question": lambda doc: doc["examples"][0].update(question="바뀐 질문"),
            "version": lambda doc: doc["examples"][0].update(version=2),
            "removed": lambda doc: doc["examples"].pop(),
        }
        for name, edit in edits.items():
            with self.subTest(name), tempfile.TemporaryDirectory() as tmp:
                store = load_store(copy_store(tmp, edit))
                with self.assertRaises(RetrievalError) as caught:
                    load_index(LEXICAL_INDEX_PATH, store)
                self.assertEqual(caught.exception.code, "RETRIEVAL_INDEX_STALE")

    def test_missing_and_malformed_index(self):
        store = load_store()
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(RetrievalError) as caught:
                load_index(Path(tmp) / "none.json", store)
            self.assertEqual(caught.exception.code, "RETRIEVAL_INDEX_MISSING")
            bad = Path(tmp) / "bad.json"
            data = json.loads(LEXICAL_INDEX_PATH.read_text(encoding="utf-8"))
            data["normalization"] = "other"
            bad.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(RetrievalError) as caught:
                load_index(bad, store)
            self.assertEqual(caught.exception.code, "RETRIEVAL_INDEX_INVALID")

    def test_retriever_construction_fails_loudly_on_stale_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = copy_store(tmp, lambda doc: doc["examples"][1].update(question="다른 질문"))
            with self.assertRaises(RetrievalError):
                ExampleRetriever.load(store_path=path)


class RankingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.retriever = ExampleRetriever.load()

    def test_same_input_same_result(self):
        question = "지난달 가람구 개인택시 주별 매출 평균 중 가장 큰 값은?"
        first = self.retriever.select(question).to_dict()
        second = ExampleRetriever.load().select(question).to_dict()
        self.assertEqual(first, second)
        self.assertEqual([c["rank"] for c in first["candidates"]], [1, 2, 3])
        scores = [c["score"] for c in first["candidates"]]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_top_k_and_bounds(self):
        question = "지난달 가람구 개인택시의 매출 합계가 가장 컸던 주는 언제야?"
        full = self.retriever.rank(question)
        self.assertEqual(len(full), len(self.retriever.store.examples))
        for k in (1, 3, 5):
            retriever = ExampleRetriever(self.retriever.store, self.retriever.index,
                                         RetrievalSettings(top_k=k))
            ids = [c["id"] for c in retriever.select(question).candidates]
            self.assertEqual(ids, [example_id for _s, example_id in full[:k]])
        for bad in (0, 6):
            with self.assertRaises(ValueError):
                RetrievalSettings(top_k=bad)

    def test_ties_are_ordered_by_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            def duplicate(doc):
                twin = copy.deepcopy(doc["examples"][0])
                twin["id"] = "aa00"
                doc["examples"].append(twin)
            store = load_store(copy_store(tmp, duplicate))
            retriever = ExampleRetriever(store, load_index(self._index(tmp, store), store),
                                         RetrievalSettings(top_k=5))
            ranked = retriever.rank(store.get("ex01").question)
            self.assertEqual(ranked[0][0], ranked[1][0])
            self.assertEqual([ranked[0][1], ranked[1][1]], ["aa00", "ex01"])

    @staticmethod
    def _index(tmp, store):
        path = Path(tmp) / "index.json"
        save_index(build_index(store), path)
        return path

    def test_min_score_no_match_and_char_budget(self):
        store, index = self.retriever.store, self.retriever.index
        none = ExampleRetriever(store, index, RetrievalSettings(min_score=0.999)).select("무관한 문장")
        self.assertEqual((none.status, none.section, none.included), ("no_match", "", []))
        small = ExampleRetriever(store, index, RetrievalSettings(top_k=3, max_chars=900)).select(
            "지난달 가람구 개인택시의 주별 매출 합계를 평균 내면?")
        self.assertLessEqual(len(small.section), 900)
        self.assertTrue(small.dropped)
        self.assertEqual(len(small.included) + len(small.dropped), 3)

    def test_fixed_examples_ignore_the_question(self):
        fixed = FixedExamples(self.retriever.store, ["ex03", "ex09", "ex10"])
        a, b = fixed.select("질문 하나"), fixed.select("전혀 다른 질문")
        self.assertEqual(a.included, ["ex03", "ex09", "ex10"])
        self.assertEqual(a.section, b.section)

    def test_rendered_examples_show_no_condition_values_outside_the_question(self):
        for example in self.retriever.store.examples:
            body = render_example(example, 1).split("\n", 2)[2]  # 질문 줄 뒤
            factors = example.grounding.get("factors") or {}
            for key in ("date", "taxi_type"):
                if key in factors:
                    self.assertNotIn(str(factors[key]), body, example.id)

    def test_retrieval_input_is_the_question_only(self):
        """검색은 질문 원문만 받는다. gold·기대 macro·result kind를 넘길 자리가 없다."""
        import inspect
        self.assertEqual(list(inspect.signature(ExampleRetriever.select).parameters),
                         ["self", "question"])


class OllamaEmbedderTest(unittest.TestCase):
    """실제 embedding 서버 없이 가짜 HTTP로 인터페이스와 판 확인만 본다."""

    def fake(self, digest="sha256:aaa", error=None):
        def get(url):
            return 200, {"models": [{"name": "embed-model", "digest": digest}]}

        def post(url, payload):
            if error:
                return 500, {"error": error}
            vectors = []
            for text in payload["input"]:
                vectors.append([text.count("주") + 1.0, text.count("평균") + 1.0,
                                text.count("값") + 1.0])
            return 200, {"embeddings": vectors}
        return OllamaEmbedder("embed-model", post=post, get=get)

    def test_embedding_index_round_trip_and_digest_check(self):
        store = load_store()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "index.json"
            save_index(build_index(store, self.fake()), path)
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual((data["embedder"]["kind"], data["embedder"]["version"]),
                             ("embedding", "sha256:aaa"))
            retriever = ExampleRetriever(store, load_index(path, store, self.fake()))
            self.assertEqual(len(retriever.select("주별 평균 중 가장 큰 값").candidates), 3)
            with self.assertRaises(RetrievalError) as caught:
                load_index(path, store, self.fake(digest="sha256:bbb"))
            self.assertEqual(caught.exception.code, "RETRIEVAL_EMBEDDER_MISMATCH")
            with self.assertRaises(RetrievalError) as caught:
                load_index(path, store)
            self.assertEqual(caught.exception.code, "RETRIEVAL_EMBEDDER_MISMATCH")

    def test_server_without_embeddings_is_an_error(self):
        embedder = self.fake(error="This server does not support embeddings.")
        with self.assertRaises(RetrievalError) as caught:
            embedder.embed(["질문"])
        self.assertEqual(caught.exception.code, "RETRIEVAL_EMBEDDER_UNAVAILABLE")

    def test_lexical_is_labelled_as_lexical(self):
        identity = LexicalEmbedder.fit(["가", "나"]).identity()
        self.assertEqual(identity["kind"], "lexical")


# -- 4. grounding 연결 --------------------------------------------------------------


class _Raising:
    mode = "retrieved"

    def select(self, question):
        raise RetrievalError("index 손상", code="RETRIEVAL_INDEX_INVALID")


class GroundingIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.retriever = ExampleRetriever.load()

    def test_retrieval_off_keeps_the_prompt_and_run_record(self):
        client = type("C", (), {"model": "m"})()
        off = GeoFlowPlanner(client=client, aggregation_grounding="structured")
        question = "지난달 가람구 개인택시 주별 매출 평균 중 가장 큰 값은?"
        self.assertEqual(off.messages(question)[0]["content"], off.system_prompt())
        self.assertNotIn(SECTION_HEADING, off.system_prompt())
        on = GeoFlowPlanner(client=client, aggregation_grounding="structured",
                            example_selector=self.retriever)
        self.assertEqual(on.system_prompt(), off.system_prompt())
        with_examples = on.messages(question)[0]["content"]
        self.assertTrue(with_examples.startswith(off.system_prompt() + "\n\n" + SECTION_HEADING))
        flat = GeoFlowPlanner(client=client)
        self.assertNotIn(SECTION_HEADING, flat.messages(question)[0]["content"])
        run = reference_pipeline(_Scripted(grounding({"result": {"reducer": "avg"}}))).run(question)
        self.assertIsNone(run.retrieval)
        self.assertIsNone(run.to_dict()["retrieval"])

    def test_selector_requires_structured_grounding(self):
        with self.assertRaises(ValueError):
            GeoFlowPlanner(client=object(), example_selector=self.retriever)

    def test_examples_do_not_leak_into_execution_arguments(self):
        """검색 예시(나래구·2026년 8월 전체)의 조건이 현재 질문의 실행 인자로 새지 않는다."""
        question = "2026년 8월 1일부터 15일까지 가람구 개인택시 전체 매출 평균은?"
        client = _Scripted(grounding({"result": {"reducer": "avg"}}, period="20260801-20260815"))
        run = reference_pipeline(client, self.retriever).run(question)
        self.assertEqual(run.outcome, "answered", run.runtime_error)
        section = client.messages[0][0]["content"]
        self.assertIn(SECTION_HEADING, section)
        retrieved = [self.retriever.store.get(i) for i in run.retrieval["included"]]
        self.assertTrue(any("나래구" in example.question for example in retrieved))
        calls = [hop for hop in run.hop_log if hop.get("tool") == "get_operation_metrics"]
        self.assertEqual([hop["arguments"] for hop in calls], [{
            "metric": "revenue", "scope": GARAM, "date": "20260801-20260815",
            "taxi_type": "private", "aggregation": "avg"}])
        places = [hop["arguments"]["name"] for hop in run.hop_log
                  if hop.get("tool") == "get_place_scope"]
        self.assertEqual(places, ["가람구"])
        # 값은 reference 데이터 계산이다(r02~r07 6건, 합 700,000). 예시의 기대값과 무관하다.
        (mean,), = sql_db().execute(
            "SELECT AVG(revenue_krw) FROM ops WHERE scope=? AND taxi_type='private' AND "
            "revenue_krw IS NOT NULL AND service_date BETWEEN '2026-08-01' AND '2026-08-15'",
            (GARAM,)).fetchall()
        self.assertAlmostEqual(run.execution["final_value"], mean)
        example_values = {example.reference["value"] for example in self.retriever.store.examples
                          if example.reference}
        self.assertNotIn(run.execution["final_value"], example_values)

    def test_invalid_grounding_is_still_rejected_with_examples(self):
        question = "지난달 가람구 개인택시의 주별 매출 합계를 평균 내면?"
        bad = grounding({"bucket": {"unit": "week", "reducer": "sum"},
                         "result": {"reducer": "avg"}}, dimension="week")
        for selector in (None, self.retriever):
            run = reference_pipeline(_Scripted(bad), selector).run(question)
            self.assertEqual((run.outcome, run.error["code"]), ("failed", "INVALID_FACTOR"))
        # 질문에 없는 scope id를 직접 적으면 scope provenance 검증이 거부한다(예시가 있어도).
        injected = grounding({"result": {"reducer": "avg"}})
        injected["concepts"][0] = {"id": "area", "concept": "LOCATION", "subtype": "scope",
                                   "role": "COND", "source": "user", "value": NARAE}
        for selector in (None, self.retriever):
            run = reference_pipeline(_Scripted(injected), selector).run(question)
            self.assertNotEqual(run.outcome, "answered")
            self.assertFalse([hop for hop in run.hop_log
                              if hop.get("tool") == "get_operation_metrics"])

    def test_run_records_retrieval_and_result_comes_from_reference_data(self):
        question = "지난달 가람구 개인택시의 매출 합계가 가장 컸던 주는 언제야?"
        client = _Scripted(grounding({"bucket": {"unit": "week", "reducer": "sum"},
                                      "result": {"select": "max"}}))
        run = reference_pipeline(client, self.retriever).run(question)
        self.assertEqual(run.outcome, "answered", run.runtime_error)
        record = run.retrieval
        self.assertEqual(record["mode"], "retrieved")
        self.assertEqual(record["status"], "ok")
        self.assertEqual([c["rank"] for c in record["candidates"]], [1, 2, 3])
        self.assertEqual(record["index"]["embedder"]["kind"], "lexical")
        self.assertEqual(record["index"]["store_sha256"], self.retriever.store.sha256)
        self.assertIsNotNone(record["section_sha256"])
        weeks = sql_db().execute(WEEKLY, {"scope": GARAM, "taxi": "private",
                                          "start": "2026-08-01", "end": "2026-08-31"}).fetchall()
        top = max(total for *_, total, _m in weeks)
        want = [week_label(first) for first, _l, total, _m in weeks if total == top]
        value = run.execution["final_value"]
        self.assertEqual(([g["label"] for g in value["groups"]], value["value"]), (want, top))

    def test_selector_failure_is_not_hidden(self):
        run = reference_pipeline(_Scripted(grounding({"result": {"reducer": "avg"}})),
                                 _Raising()).run("질문")
        self.assertEqual((run.outcome, run.error["code"]), ("failed", "RETRIEVAL_FAILED"))

    def test_selection_happens_once_per_question(self):
        calls = []

        class Counting(FixedExamples):
            def select(self, question):
                calls.append(question)
                return super().select(question)

        planner = GeoFlowPlanner(client=object(), aggregation_grounding="structured",
                                 example_selector=Counting(self.retriever.store, ["ex01"]))
        planner.messages("질문")
        planner.messages("질문")
        self.assertEqual(calls, ["질문"])



if __name__ == "__main__":
    unittest.main()
