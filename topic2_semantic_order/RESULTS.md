# RESULTS — topic2_semantic_order (decision 264)

Run window: 2026-11-08 17:47 → 2026-11-09 18:47 (+09:00). Base Qwen3-8B@b968826d, V4 `sft_train.jsonl` (1,984 records / 494 questions), LoRA SFT, thinking ON, seed 43.

## Verdict (pre-registered S1–S4, CT10K, semantic_fine groups ≥ 30 items, 5 order seeds)

**H1 ("Semantic-balanced order reduces Semantic Group Collapse") is NOT supported.** All four criteria failed; the evidence points the other way, mostly through the fare (T1) groups. This is reported as a failed hypothesis; criteria were not changed after seeing results.

| criterion | result | pass |
|---|---|---|
| S1 worst-group B−A > 0, CI lower bound > 0 | −7.09 pp [−29.05, +9.17] | FAIL |
| S2 fewer 20 pp-collapse groups, CI upper bound < 0 | +8.2 groups [0.0, +12.8] (A 10.4 → B 18.6) | FAIL |
| S3 smaller seed SD of overall acc **and** smaller mean across-seed group variance (point estimates) | SD 4.67 → 5.70 pp; group var 0.0160 → 0.0172 | FAIL |
| S4 overall B−A CI lower bound > −2 pp | −5.93 pp [−13.58, +0.57] | FAIL |

Most CIs include 0 (5 seeds, few clusters): the data do **not** show B is significantly worse on every metric; they show no improvement, point estimates all worse, and collapse count worse at the CI boundary (S2 lower bound 0.0; template_group collapse20 +6.8 [0.8, 8.2]).

## Stage status (what was actually done)

| stage | status |
|---|---|
| GPU training (real) | **done**: 5 B models (fresh from base) + 2 repeat-pair models (A0-o2026131-r2, B-o2026131-r2); 7 trainings, 0 failures, 0 retries |
| Evaluation (real, vLLM LoRA) | **done**: B × 5 seeds on H-dev, E1, CT10K; A0-o2026117/o2026131 CT10K newly measured; repeat-pair H-dev |
| Improvement | **not confirmed** (failed) |
| C/D coverage arms | **not run — blocked** (DATA_AUDIT.md: unapproved batch014, 44 fare questions undecided, protected families, no teacher/Ollama, no loss-token-budget match) |
| Optional ablations (coarse-only / coarse+fine) | **not run** — A/B is negative and each costs ~3.3 h/GPU; not started |
| H-final | **never opened, run, analysed or used** |
| Bit-exact A0 reproducibility | **not achievable**: same-config same-order retrain gives a different adapter and different accuracy (below) |

## Per-arm / per-seed status and CT10K metrics (overall % | worst-group | collapse20 groups)

| order seed | A (existing A0, reused) | B (new) | B adapter sha256 (prefix) |
|---|---|---|---|
| 1102 | 92.81 \| 48.0 \| 6 | 76.47 \| 0.0 \| 23 | 63c8b14f5c337d4f |
| 211102 | 89.80 \| 3.9 \| 9 | 76.68 \| 0.0 \| 24 | 4e345dbffe317378 |
| 2026113 | 90.58 \| 23.5 \| 7 | 86.55 \| 32.0 \| 15 | 4631a1787993581a |
| 2026117 | 86.68 \| 27.4 \| 12 | 89.11 \| 31.4 \| 14 | 02c4087e9eb702ee |
| 2026131 | 80.75 \| 0.0 \| 18 | 82.14 \| 4.0 \| 17 | 827ea1e3023b384e |

B is better than A for 2 of 5 seeds on overall (2026117, 2026131) and on worst-group (2026113, 2026117, 2026131 vs A) but much worse for seeds 1102 and 211102. Checkpoints (external, never committed): `/data/hwkim/sftdpo_work/topic2_semantic_order/train/B-o<seed>/checkpoint-1984`; A0: `/data/hwkim/sftdpo_work/{ablation_011,ablation_012,ablation_013}/train/A0-*/checkpoint-1984`. Full sha256: `tables/adapters_sha256.txt`.

## Evaluation conditions
Same for A and B: vLLM LoRA serving via `run_cell6x.py`, bf16, thinking ON, grounding-target full; CT10K k=1 cells c1–c5 (10,000 items), H-dev 2,000 items k=1, E1 4 repeats per set; seed-base 20261100/20261101. Truncation reruns by the pre-registered rule (15 rerun jobs, 65 cells; originals in `cells/replaced/`; `RERUNS_T2.json`). A cells reused from ablation_012/013 (verified identical config: gates G1–G10, `CONFIG_AUDIT.md`). Evaluation groups come from gold calls of evaluation items; the scheduler order never used CT10K/H-dev errors.

## Secondary metrics (mean over 5 seeds)

| metric | CT10K A | CT10K B | H-dev A | H-dev B |
|---|---|---|---|---|
| overall acc % | 88.12 | 82.19 | 86.79 | 82.02 |
| silent wrong (answered_mismatch) % | 3.66 | 6.68 | 3.89 | 6.13 |
| tool failure % | 6.10 | 6.88 | 7.46 | 7.98 |
| refused_unsupported % | 2.10 | 4.19 | 1.85 | 3.70 |
| truncation rate | 0.6% | 1.1% | 0.4% | 1.3% |
| latency p50 / p95 s | 20.5 / 31.0 | 19.7 / 32.7 | 20.6 / 31.5 | 20.1 / 34.8 |

B answers wrongly-but-silently and refuses unsupported more often, and truncates ~2–3× more. E1 (B−A, 5 seeds, hierarchical CI): dev accuracy −4.90 pp [−9.93, −0.17]; correct refusal +7.94 [0.06, 15.89]; over-refusal +4.29 [1.33, 7.31]; U-rate +1.07 [−0.91, 3.29]. I.e. B refuses more, in both the right and the wrong cases.

## T1 (fare) vs T5 (OD top-N), mean over seeds (CT10K)
T1: A 77.4 → B 47.3 (A SD 19.1, B SD 30.7 pp; B-o1102 18.3, B-o211102 9.7). T5: A 78.6 → B 75.2 (SD 10.8 → 6.0). H-dev T1: 76.8 → 46.1; T5: 77.3 → 74.3. Worst B−A CT10K groups are `get_trip_metrics|fare|…|reg=province` (−27 to −41 pp). Per-seed: `tables/*_T1_T5.csv`.

## Repeat pair (order effect vs retraining/GPU nondeterminism), H-dev, seed o2026131 only
Same config, same order, retrained (adapters differ: A0 `06f824f3…` vs r2 `f38ea145…`; B `827ea1e3…` vs r2 `0a054bf5…`):

| comparison | acc x | acc y | diff (y−x) | discordant items |
|---|---|---|---|---|
| A vs A-r2 | 78.60 | 76.80 | −1.80 | 9.1% |
| B vs B-r2 | 82.70 | 78.45 | −4.25 | 16.7% |
| A vs B | 78.60 | 82.70 | +4.10 | 16.0% |
| A-r2 vs B-r2 | 76.80 | 78.45 | +1.65 | 19.4% |

Retraining noise alone (1.8–4.3 pp overall on one seed) is the same size as the A/B difference of that seed (+4.1 / +1.65), and the B−A gap on this seed shrinks from +4.10 (original pair) to +1.65 (repeat pair), i.e. the same intervention gives a 2.5× different estimate. One seed, one repeat: descriptive, no inference. It shows that single-training comparisons are noise-limited, which supports the hierarchical-over-seeds design but also means per-seed B−A numbers above are not individually reliable.

## Experiments not run
C/D coverage arms (blocked); coarse-only and coarse+fine ablations; further order seeds; repeat pairs on seeds other than 2026131; H-final (sealed).

## Hashes and failures
V4 sha256 `3575c7f0…` (G1). Frozen B orders and their SHA-256: `orders/`. Adapter sha256: `tables/adapters_sha256.txt`. Failures: none (no failed job, no retry). Deviation: 22 h no-new-job deadline waived by user for `RT2-15` (GPU_EXECUTION_LOG.md). Scheduler log copies: `tables/runs.log.copy`, `tables/timeline.jsonl.copy`.
