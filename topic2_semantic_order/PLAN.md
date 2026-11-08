# Topic 2 — Semantic-balanced training order: pre-registered plan (decision 264, frozen 2026-11-08 BEFORE any B model was trained or evaluated)

Status: diagnostic experiment, branch `geoflow/sft-dpo-t2pc`. Does not adopt/reject V4, does not touch H-final, does not change any protected-data policy.

## Question and hypotheses (kept separate)
- **H1 order**: same 1,984 V4 records, only the order changes (O4' -> Semantic-balanced) -> fewer collapsed semantic groups, higher worst-group accuracy, smaller seed-to-seed spread, no material loss of overall accuracy. **Tested here (A vs B).**
- **H2 coverage**: adding under-covered, *approved, non-overlapping* types helps those types. **Not tested** (C/D blocked, see DATA_AUDIT.md).
- **H3 interaction**: order effect depends on coverage. **Not tested** (needs C/D).

## Arms (this run)
| Arm | Data | Order | Models |
|---|---|---|---|
| A (reused) | V4 `sft_train.jsonl` sha256 `3575c7f0…ed10e3f`, 1,984 records | original O4' (decision 206) | existing `A0-o{1102,211102,2026113}` (ablation_011), `A0-o{2026117,2026131}` (ablation_013), checkpoint-1984. Verified: same config except order keys/output paths (CONFIG_AUDIT.md). |
| B (new) | identical records | Semantic-balanced (this package) | `B-o{1102,211102,2026113,2026117,2026131}`, trained from the pretrained Qwen3-8B@b968826d, never from an A0 model. |
| repeat pair | same | O4' / balanced, seed 2026131 | `A0-o2026131-r2`, `B-o2026131-r2`: same order and model seed, new run -> GPU run-to-run nondeterminism (H-dev only). |

Order seeds: 1102, 211102, 2026113, 2026117, 2026131. Training seed 43 (model/data seed) for every model.
C/D (coverage) are **not run**; no data was added, removed or replaced.

## Scheduler (semantic_schedule.py) — fixed before training
- Labels use TRAIN data only (`approved_train_v6.jsonl` field `view`, present for all 494 questions; execution only for the tool name). No CT10K/H-dev/H-final item, answer or error rate is read.
- Coarse = (tool, metric). Fine = coarse + (aggregation[/rollup], temporal unit, region type, od role incl. dimension_target). Absent factor = `none`; tool is `unknown` only for a metric with no executed train evidence (vacant_ratio, speed; 57 records).
- Weighted-deficit round robin: score = coarse_lag + 0.24 * fine_lag + seeded tie-noise; question picked proportional to its remaining share. `fine_weight = 0.24` was inherited from the earlier offline draft and **not tuned** on any model output.
- Constraints: each record exactly once; same question never > 4 consecutive records; within-question order = repository `within_key` (teacher/full_response first, then json_only by trace hash); deterministic per seed; order + SHA-256 stored in `orders/`.
- Defect fixed vs the earlier package version: 132 questions without gold execution were put in separate `subtype:*` coarse groups (e.g. `subtype:trip_count` vs `get_trip_count`). Signature is now derived uniformly from `view` (+ train-evidence tool map). Tests still pass (7/7).

## Training controls (identical A vs B)
Qwen3-8B@b968826d9c46dd6066d109eabc6255188de91218, LoRA r16/alpha32/dropout 0.05, 7 modules, lr 2e-4 linear to 0, batch 1 x accum 1, 1 epoch = 1,984 optimizer steps, bf16, max_seq 12,288, thinking ON, loss scope `by_source`, seed 43, SequentialSampler (shuffle off), prompt hash 87048d0c. Only `training.{order keys, output_dir}` and `profiling.output` differ.

## Evaluation (same pipeline/decoding for A and B; nothing re-defined)
- `match` = cell row `category == "match"` (tool/args/answer-value checks as in `run_cell6x.py`), refusal from `C9.sample_values`.
- **CT10K** 10,000 items k=1 (sampling seed 20261101, concurrency 32, 5 chunks) — A: existing for 3 seeds, **new runs for A0-o2026117/o2026131 here**; B: 5 seeds. Development data (used to find the problem), not a final validation set.
- **H-dev** 2,000 items k=1 (seed 20261101) — A existing, B new. **E1** (rdev v2 + valid98 + aux, k=4) — A existing, B new.
- **H-final: never opened, never run.** No H-final signature used in the scheduler.
- Evaluation is run on a different server session than the A runs (vLLM + LoRA, same code commit family); residual session effect is bounded by the repeat pair and reported.

## Groups (fixed now)
1. `template_group` (reproduces earlier analysis): CT10K groups with >= 30 items (95 groups); collapse rule = seed accuracy < base-mean accuracy - 20 pp (base mean = 3 base k-runs, `client_test_10000/results_ct10k_base.json`); also > 30 pp.
2. **Semantic group (primary for worst-group metrics)** from the *gold calls of the evaluation item* (gold_text; gold only describes the question, never model outputs): (tool, metric, aggregation, temporal unit, region type, od role). Minimum group size **30** in CT10K (groups below are pooled into "small", reported separately, excluded from worst/decile/collapse). H-dev: same signature with min size **20**.
3. Coarse semantic (tool, metric) and T1/T5 signatures (`ablation_013/analysis/analyze_a13.py::tsig`) for secondary breakdowns.

## Metrics (fixed now)
Primary: worst-group accuracy; mean accuracy of the lowest 10% of groups; # groups > 20 pp below base; # groups > 30 pp below base; across-seed variance of group accuracy (mean over groups of the across-seed variance).
Secondary: overall accuracy; mean of seed-level SD; Silent Wrong Answer rate (`answered_mismatch`/total answered wrong); tool-execution failure rate (`failed`); over-refusal (E1 169 + H-dev); correct-refusal (E1 rdev 90); T1, T5 accuracy; latency p50/p95; truncation rate.

## Statistics (fixed now)
Paired by order seed (A_s vs B_s). Per seed difference, mean difference, seed SD/range. **Hierarchical bootstrap, 10,000 replicates, `default_rng(20261108)`**: resample seed pairs (5, with replacement) -> within each, resample template_group clusters with replacement (items follow their cluster) -> recompute every metric for A and B on the same resample. Items are never treated as independent training repeats. CI = 2.5/97.5 percentiles. With only 5 seed pairs seed-level intervals are wide; this is stated, not hidden. The cluster-only bootstrap (seeds fixed) is also reported as a diagnostic.

## Success criterion (fixed now; no post-hoc change)
H1 is **supported** only if ALL hold on CT10K, semantic groups, 5 paired seeds:
 S1 worst-group accuracy: B - A mean > 0 and 95% CI lower bound > 0;
 S2 # 20-pp-collapse groups: B mean < A mean and 95% CI upper bound < 0;
 S3 seed spread: SD of overall accuracy across seeds smaller for B, AND mean across-seed group variance smaller for B (point estimates + bootstrap interval reported);
 S4 non-inferiority: overall accuracy B - A has 95% CI lower bound > -2.0 pp.
Otherwise H1 is reported as **not supported**, with whichever criteria failed. H-dev/E1 are replication/secondary and cannot rescue a failed S1-S4. If CT10K A0 cells for o2026117/o2026131 are missing, S1-S4 use the 3 complete seeds and this is declared.

## Order of work / GPU
`gpu/make_jobs_t2.py` -> `gpu/jobs_t2.json`; scheduler16 (copy of scheduler15), one job per GPU (decision 114), three GPUs by UUID (0,1,2), priority: B training -> H-dev -> E1 -> CT10K -> A0 CT10K for 2 seeds -> repeat pair. Evaluation starts only after `gpu/ready/T2_TOOLS.json` (analysis tool committed and smoke-tested on A-only data, before any B result is read). Deadline 24 h after start.

## What this run cannot show
Causal explanation of why a group collapses; coverage or interaction effects; final-set generalization; anything about H-final.
