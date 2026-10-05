"""New grounding metrics delegate the pipeline to the existing evaluator."""
import copy
import hashlib
import unittest

from training.thor_evaluate_planner import score_raw_grounding, summarize_grounding_metrics
from training.data.common import production_prompt
from training.evaluate_checkpoint import ReplayClient, evaluate, load_items
from tests.test_training_data import annotation


class EvaluationTest(unittest.TestCase):
    def test_gold_metrics_ignore_id_text_order_but_preserve_values(self):
        import json
        gold = annotation()
        item = {**gold, "golden": gold["grounding"]}
        predicted = copy.deepcopy(gold["grounding"])
        predicted["concepts"].reverse()
        for index, c in enumerate(predicted["concepts"]):
            c["id"], c["text"] = f"another_{index}", "surface text"
        result = score_raw_grounding(json.dumps(predicted), item)
        self.assertTrue(result["json_parse_ok"])
        self.assertTrue(result["planner_contract_ok"])
        self.assertTrue(result["grounding_exact"])
        self.assertTrue(result["factor_exact"])
        predicted["factors"]["aggregation"] = "sum"
        wrong = score_raw_grounding(json.dumps(predicted), item)
        self.assertFalse(wrong["grounding_exact"])
        self.assertEqual(wrong["factor_score"]["matched"], 1)
        self.assertEqual(wrong["factor_score"]["predicted"], 2)

    def test_json_contract_and_unsupported_are_separate_axes(self):
        item = {**annotation(), "golden": annotation()["grounding"]}
        invalid = score_raw_grounding('{"graph":[]}', item)
        self.assertTrue(invalid["json_parse_ok"])
        self.assertFalse(invalid["planner_contract_ok"])
        self.assertFalse(score_raw_grounding("no json", item)["json_parse_ok"])
        refusal = score_raw_grounding('{"unsupported":true}', item)
        self.assertTrue(refusal["planner_contract_ok"])
        self.assertFalse(refusal["grounding_exact"])
        unsupported = score_raw_grounding('{"unsupported":true}', {**item, "golden": {"unsupported": True}})
        metrics = summarize_grounding_metrics([unsupported, refusal])
        self.assertEqual(metrics["unsupported_precision"], 0.5)
        self.assertEqual(metrics["unsupported_recall"], 1)

    def test_labeled_and_unlabeled_metrics(self):
        from geoflow.validator import ALL_RULES
        r = score_raw_grounding('{"unsupported":true}', {"question": "unknown"})
        metrics = summarize_grounding_metrics([r])
        self.assertIsNone(metrics["grounding_exact_match"])
        self.assertIsNone(metrics["factor_exact_match"])
        self.assertIsNone(metrics["g1_g7_pass_rates"][ALL_RULES[0]])

    def test_v2_corpus_gold_and_task_groups_are_available(self):
        items = load_items("evaluation/v2/paraphrases_holdout_v2.yaml")
        self.assertEqual(len(items), 126)
        self.assertTrue(all("golden" in item and "intent_id" in item for item in items))

    def test_replay_existing_evaluator_without_hf_or_gpu(self):
        import json
        from geoflow.composer import MacroComposer
        from geoflow.grounding import parse_grounding
        from training.thor_evaluate_planner import corpus_labels
        raw = annotation()
        macros, operators = corpus_labels(MacroComposer().compose(parse_grounding(raw["grounding"], raw["question"])))
        item = {**raw, "golden": raw["grounding"], "expected_macros": macros, "expected_operators": operators,
                "expected_concepts": [f'{c["concept"]}/{c["subtype"]}:{c["role"]}' for c in raw["grounding"]["concepts"]]}
        client = ReplayClient([{"source_record_id": raw["id"], "question": raw["question"],
                                "raw_text": json.dumps(raw["grounding"]),
                                "prompt_hash": hashlib.sha256(production_prompt().encode()).hexdigest()}])
        report = evaluate(client, [item])
        summary = report["summary"]
        self.assertEqual(summary["grounding_exact_match"], 1)
        self.assertEqual(summary["factor_exact_match"], 1)
        self.assertEqual(summary["concept_accuracy"], 1)
        self.assertEqual(summary["validation_pass_rate"], 1)
        self.assertEqual(summary["composition_success_rate"], 1)
        self.assertEqual(set(summary["g1_g7_pass_rates"].values()), {1})
        self.assertEqual(len(report["by_intent"]), 1)
        self.assertEqual(len(report["by_task_group"]), 1)

    def test_execution_uses_existing_reference_provider_contract(self):
        import json
        from build import build
        from geoflow.examples import load_store
        from geoflow.providers import profile_for
        from tool_executor import ToolExecutor
        from tool_handlers import get_tool_handlers
        from training.pilot import gold_item
        from training.data.build_sft import sft_record

        example = next(e for e in load_store().examples if e.id == 'ex05')
        item = gold_item(sft_record({'id': example.id, 'question': example.question,
                                   'grounding': example.grounding, 'parent_intent': 'weekly_min'},
                                  source='authored', source_representation='structured'), 'valid')
        client = ReplayClient([{'source_record_id': item['id'], 'question': item['question'],
                               'raw_text': json.dumps(item['golden']),
                               'prompt_hash': hashlib.sha256(production_prompt().encode()).hexdigest()}])
        executor = ToolExecutor(tools=build()[0], handlers=get_tool_handlers('reference'),
                                provider='reference')
        record = evaluate(client, [item], execute=True, tool_executor=executor)['records'][0]
        self.assertTrue(record['grounding_exact'])
        self.assertTrue(record['validated'])
        self.assertTrue(record['executed'])
        self.assertEqual(record['execution_profile'], profile_for('reference').to_dict())


if __name__ == "__main__":
    unittest.main()
