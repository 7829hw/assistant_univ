"""CPU checks for the narrowed execution scope and paired inference."""
from copy import deepcopy
import unittest

from budget_plan import ARMS, DATASETS, ORDER_SEEDS, TRAIN_SEEDS, manifest
from common import ROOT, STEPS, S
from execution import authorized_scope, plan_locked, validate_job
from launch import WORKSTATION_GPUS
from schedules import experiment
from analyze_budget import paired_estimate
from compare_eval_replay import compare


class BudgetTests(unittest.TestCase):
    def test_exact_crossed_scope_and_final_only(self):
        records, blocks, _, _ = experiment()
        original = {j["id"]:j for j in plan_locked()["jobs"]}
        expected = {(a,o,t) for a in ARMS for o in ORDER_SEEDS for t in TRAIN_SEEDS}
        for option, dataset in DATASETS.items():
            plan, _ = manifest(option)
            self.assertEqual(len(plan["jobs"]),32)
            self.assertEqual({(j["arm"],j["order_seed"],j["training_seed"]) for j in plan["jobs"]},expected)
            self.assertEqual([sum(j["gpu_slot"]==lane for j in plan["jobs"]) for lane in range(3)],[12,12,8])
            self.assertEqual(len({(j["order_seed"],j["gpu_slot"]) for j in plan["jobs"]}),8)
            self.assertEqual(plan["optimizer_steps"],STEPS)
            self.assertEqual(plan["intermediate_eval_cells"],0)
            for path,sha in plan["eval_input_sha256"].items():
                self.assertEqual(S.sha_file(ROOT/path),sha)
            for entry in plan["jobs"]:
                checkpoint = entry["checkpoint"]
                self.assertEqual(checkpoint["step"],STEPS)
                self.assertEqual({c["dataset"] for c in checkpoint["cells"]},{dataset})
                self.assertEqual(len(checkpoint["cells"]),1 if option=="A" else 5)
                validate_job(original[entry["job"]],records,blocks)

    def test_authorization_rejects_original_manifest_wrong_lane_and_action(self):
        plan, path = manifest("A")
        example = plan["jobs"][0]
        job = {"id":example["job"]}
        approval = dict(option="A",commit="pinned",manifest_sha256=S.sha_file(path),
                        gpu_uuids=WORKSTATION_GPUS,gpu_uuid=WORKSTATION_GPUS[example["gpu_slot"]],
                        jobs=[job["id"]],actions=["train"])
        self.assertEqual(authorized_scope(job,approval,"pinned","A","train")["dataset"],"H-dev")
        for difference in ({"manifest_sha256":plan["parent_manifest_sha256"]},{"gpu_uuid":WORKSTATION_GPUS[1]},
                           {"actions":["evaluate"]},{"option":"B"},{"jobs":["outside"]}):
            with self.assertRaises(ValueError):
                authorized_scope(job,approval|difference,"pinned","A","train")

    def test_training_seed_differences_and_no_inference_on_missing_pairs(self):
        runs = {(arm,order,t):dict(collapse20=(1+(t==TRAIN_SEEDS[1])) if arm=="S1T0" else 0,
                                   signature="same")
                for arm in ARMS for order in ORDER_SEEDS for t in TRAIN_SEEDS}
        self.assertIsNone(paired_estimate(runs,"A")["sign_flip_p"])
        result = paired_estimate(runs,"B")
        self.assertEqual(result["estimate"],1.5)
        self.assertEqual(result["sign_flip_p"],2/256)
        self.assertEqual(result["training_seed_mean_difference"],1)
        runs[ARMS[0],ORDER_SEEDS[0],TRAIN_SEEDS[0]]["signature"]="different"
        self.assertEqual(paired_estimate(runs,"B")["status"],"INCOMPLETE")

    def test_replay_detects_output_and_metadata_drift(self):
        meta = dict(gold_file="sft_dpo_inventory/ablation_012/e2/h_dev.yaml",gold_sha256="gold",
                    code_fingerprint="code",planner_prompt_sha256="prompt",scorer_version="scorer",
                    item_order=["test"],hf=dict(revision="rev",decoding=dict(round_seed=1,temperature=.6)),
                    vllm=dict(wall_seconds=3,server_meta=dict(gpu_uuid="gpu",adapter_sha256="weights"),
                              concurrency=dict(max_concurrent_requests=32)))
        reference = dict(meta=meta,rows=[dict(id="test",category="match",hf_calls=[dict(raw_sha256="hash")])])
        candidate = deepcopy(reference)
        candidate["rows"][0]["hf_calls"][0]["raw_sha256"]="other"
        self.assertEqual(compare(reference,candidate)["paired_rows_changed"]["raw_calls"],1)
        candidate["meta"]["hf"]["decoding"]["temperature"]=.7
        with self.assertRaisesRegex(ValueError,"sampling"):
            compare(reference,candidate)


if __name__ == "__main__":
    unittest.main()
