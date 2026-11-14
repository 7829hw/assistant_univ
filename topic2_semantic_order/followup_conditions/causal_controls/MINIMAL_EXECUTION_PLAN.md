# Minimal follow-up execution plan

Status **CPU_VALIDATED / GPU BLOCKED**. E1/E2 and their device-matched A/B evaluation and scheduled analyses keep their current execution paths. The smaller study uses only the eight pre-existing S0T0/S1T0 order pairs and the two registered training seeds. There are 16 matched pairs and exactly 32 unique 1,984-step runs. The two budget options use the same training runs. Pick the option before seeing outcomes. [Prospective amendment](BUDGET_AMENDMENT.md) · [H-dev manifest](budget/option_A.json) · [CT10K manifest](budget/option_B.json)

## GPU and storage budgets

Profiled from the existing E1/E2 execution timeline through 2026-11-15 01:45 KST. The median of nine completed trainings is 3.278 h. The nominal evaluation estimate applies the pooled median completed-attempt duration once per final cell, 0.7094 h for H-dev or 0.7381 h per CT10K chunk. The median of nine server starts is 51 s and is included once per model.

| | A · final H-dev | B · final CT10K |
|---|---:|---:|
| Training runs / final eval cells | 32 / 32 | 32 / 160 |
| Training GPU-hours | 104.9 | 104.9 |
| Evaluation GPU-hours, median-attempt planning estimate | 22.7 | 118.1 |
| Serving startup GPU-hours | 0.5 | 0.5 |
| **Nominal total GPU-hours** | **128.1** | **223.4** |
| Total using first-attempt median only | 128.6 | 211.4 |
| Total under historical retry mix | 145.3 | 319.7 |
| Total if every cell retries once at the observed median durations | 150.0 | 351.8 |
| Ideal three-GPU wall-clock lower bound at nominal cost | 42.7 h | 74.5 h |
| Nominal wall time for the longest assigned lane (12/12/8 runs) | 48.0 h | 83.8 h |
| 32 final checkpoints plus final exports | 21.8 GiB | 21.8 GiB |
| Scored plus raw evaluation data, one retained attempt per cell | 0.6 GiB | 2.9 GiB |

The retry-mix estimate adds the first-attempt median and the second-attempt median weighted by the observed retry fraction. H-dev had 7 second attempts for 9 first attempts and CT10K 27 for 35. These are workload proxies from different order conditions. The H-dev retry-mix estimate falls below the 150 GPU-hour target with about 5 hours of headroom. A hard cap would make completion uncertain. For example, applying the actual mean consumed per first cell including the observed retries and long tail gives roughly 153 GPU-hours for H-dev or 361 for CT10K including training and startup. Wall-time figures exclude queue waits, artifact transfer and preflight gates. Budget disk space separately for cached base weights, temporary shards, audit logs and both attempts where retried. Retaining both evaluation attempts across every cell would take roughly 1.2 or 5.9 GiB at the observed median output sizes. Keep weights outside Git and raw predictions and receipts under the existing retention policy. [Measurements](budget/profile.json)

## Statistical scope and scientific contribution

A gives a paired exploratory estimate on H-dev. B measures the original final CT10K fine-group Collapse20 endpoint across all 10,000 items but estimates only the prospectively defined conditional semantic-versus-random contrast with matched supervision. Both preserve all eight ordering blocks, each crossed with both training seeds. Analyze 16 matched run differences, aggregate to eight order blocks for inference, and report the difference between the two training-seed estimates separately. The primary endpoint's original six contrasts stay registered and are **not tested** by either budget option. With eight order blocks and two fixed training seeds, generalization and separation of training stochasticity from serving variability are limited.

The study estimates the effect of true-semantic scheduling relative to the specified random question-block schedule when supervision exposure is held within tolerance. It leaves the supervision interaction, placebo specificity, spacing, learning dynamics and coverage deferred. Historical base predictions are reused to compute Collapse20. A/B and E1/E2 artifacts support context and runtime profiling; their distinct schedules prevent substituting their adapters or predictions for these 32 runs.

## Evaluator profile and optimization gate

- **Batching and concurrency.** The unchanged runner starts 32 client processes for each H-dev cell or CT10K chunk. Each client handles a fixed item shard serially and vLLM schedules requests continuously. Three sampled ports show median 22–32 active requests and zero queued, 721.6–942.2 generated tokens/s and 15.8–47.2% KV usage in windows with at least eight active requests. GPU snapshots collected separately during the active queue showed high utilization. The logs are consistent with sustained decoding load and with client-side stragglers at the tail. The sampled logs mix datasets and can’t establish the gain from adding requests.
- **Prefix caching.** It is already enabled, along with chunked prefill. Median prefix hit rate was 99.0–99.2% in the same sampled windows. Retain the current cache setting. Deliberate warming or changes to request order can alter batching and must be measured if proposed.
- **Initialization.** Existing code opens one vLLM server per adapter and reuses it for all chunks and retries. The server took 45–52 s to become ready, including 4.3–4.4 s of model weight loading in the three sampled logs. Full cross-adapter server reuse could reclaim at most about 0.45 GPU-hours of measured initialization across 32 runs. It could change batching and adapter behavior. It is lower priority than controlling decode-tail overhead.
- **Duplicate work.** The plan drops intermediate scoring and runs one dataset only. A fully completed cell set with matching receipts and hashes can skip evaluator startup on resume. Keep the existing five pinned CT10K chunks and the original retry gate. The selected dataset’s retry attempts must remain distinguishable in the records.
- **Candidate to benchmark.** Test concurrency 48 against 32 on the same GPU and adapter, separately for the first frozen CT10K chunk and all of H-dev. Keep prompts, item order and IDs, parent and per-call seeds, scorer, kernel, base/adapter hashes and decoding fixed. Include two unchanged 32-concurrency controls in separate fresh serving sessions to estimate run-to-run variation. Use the same registered input manifests and the unchanged scorer. Compare wall time and throughput along with request digests, raw output, tool actions, correctness, failures and truncation. Require at least 10% median speedup across full cells, no increase in failures/truncations over baseline rerun variation, the same input/decoding contract, and scorer/output disagreement no higher than the paired baseline rerun comparison on each input. Treat this as a conservative engineering gate on the measured cells, with no general equivalence claim. Failure keeps the original evaluator. Run any GPU benchmark only under separate explicit authorization.

The CPU replay comparison used an archived same-adapter, same-device H-dev retry at concurrency 32 on exactly 2,000 IDs in the same order. Raw calls differed on 1,661 items, scorer fields on 206, and correctness on 170. Accuracy changed from 88.75% to 88.95%; truncated calls changed from 36 to 23 and measured wall from 2,836.9 to 2,279.3 s. The cell had been retried under the quality gate, so this example measures replay variation conditional on a flagged first attempt. It validates the difference-reporting tool and yields no evidence that an altered evaluator is safe or faster. No alternate evaluator was run or adopted. [Replay report](budget/existing_same_setting_replay.json)

## Reproduction and future authorization

From the repository root:

```bash
export CUDA_VISIBLE_DEVICES="" PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1
p=/data/hwkim/sftdpo_work/runtime/envs/hf/bin/python
f=topic2_semantic_order/followup_conditions
c="$f/causal_controls"
(cd "$c" && sha256sum -c PREREGISTRATION.sha256 && sha256sum -c PREREGISTRATION_AMENDMENT.sha256 && sha256sum -c BUDGET_AMENDMENT.sha256)
"$p" "$c/budget_plan.py"
"$p" "$c/test_budget.py" -v
tmp=$(mktemp -d)
"$p" "$c/profile_budget.py" --out "$tmp/profile.json"
"$p" "$c/compare_eval_replay.py" "$f/cells/replaced/hdev_c_o1102_s1.json" "$f/cells/hdev_c_o1102_s1.json" --out "$tmp/replay.json"
"$p" "$c/analyze_budget.py" A --out-dir "$tmp/option_A"
```

The snapshot of port metrics uses the external serving logs, whose filenames are reused. Running the profiler later may lack those exact serving samples even though the timestamped attempt totals remain reproducible.

After E1/E2 and their registered evaluations and analysis finish, a new approval must bind an option, a full commit and option manifest digest, exact jobs, authorized actions (`train` and/or `evaluate`), the approved workstation4 UUIDs in the manifest lane order, the one GPU UUID for the job's slot, and a timezone-aware start cutoff. Choose a budget and retry allowance before approving. Train and evaluate from a clean detached worktree at the approved commit. For each scheduled job, use `execution.py --budget-option OPTION --train RUN --approval APPROVAL` and the separately scoped `execution.py --budget-option OPTION --evaluate RUN --approval APPROVAL`. The same UUID runs all four jobs for that order seed, with a lock per physical GPU and an exclusion lock against the original queue. Use CUDA index mapped to that UUID and the frozen `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`. Successful training records remain available for a separately authorized evaluation of the other dataset using the same pinned commit and GPU, without repeating training. Neither option manifest authorizes any execution.

## Option B selected

The 2026-11-15 user instruction authorizes the B manifest on the workstation4 three-GPU allocation previously specified for this research. The new queue checks the E1/E2 and A/B completion artifacts and requires the paired final CT10K analysis to have all six arms before it starts. It validates the existing five-item device comparison, rechecks each GPU's current UUID, occupancy and Ollama state, and uses the original evaluator. Option A, all intermediate evaluations and the other interventions are outside this allocation.

From the pinned worktree, `launch_budget_b.py --approval LANE_0 LANE_1 LANE_2` runs 12, 12 and 8 jobs on the fixed GPUs and runs `analyze_budget.py` after all three lanes have finished. Its output is under `causal_controls/budget/results_B/`. The successful final analysis and `execution/done.json` are the completion receipts. The CPU-only `--preview` verifies the lane records without submitting jobs.
