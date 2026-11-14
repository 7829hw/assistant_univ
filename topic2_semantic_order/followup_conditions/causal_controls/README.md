# Additional causal controls

The CPU implementation covers 56 schedules, 112 arm × order-seed × training-seed run specifications, and 448 checkpoint specifications. GPU training and checkpoint evaluation require fresh authorization for this study. These files sit alongside the existing A/B and C/D/F0/F48 experiments.

## CPU results

| Exposure comparison | Order seeds passing | Why |
|---|---:|---|
| Semantic balancing with supervision held at the group-blind profile, S0T0 → S1T0 | 8/8 | Mean coarse and fine TV improve by 12.78 and 9.82 percentage points across seeds. Both supervision gates pass. |
| Semantic balancing with supervision balancing on, S0T1 → S1T1 | 0/8 | The supervision profiles differ beyond tolerance. |
| Supervision balancing with semantic balancing off, S0T0 → S0T1 | 0/8 | Coarse and fine matching passes. Mean supervision record and loss-token TV improve by 0.82 and 0.79 percentage points, below the 1.5-point minimum. |
| Supervision balancing with semantic balancing on, S1T0 → S1T1 | 0/8 | Both supervision improvements pass. Fine matching fails for all seeds. |
| Placebo versus group-blind and true semantic versus placebo | 8/8 | The permutation changes the fine label for 86.4–89.4% of records and preserves the joint label/supervision counts. Both placebo manipulation and direct scope matching pass. |
| High versus low gap | 8/8 | The mean coarse-group maximum gap increases by 21.1–46.1 steps and switching drops by 4.0–5.6 percentage points. Decile joint record, input-token and loss-token totals match exactly. Joint decile LR-weighted half-L1 residual is 0.588–0.684% of epoch weighted mass. |

The full factorial and its interaction are exploratory under the fixed construction. The failure indicates that these candidates did not meet the thresholds. Feasibility for other constructions remains open. The spacing intervention changes both maximum gap and switching, so it cannot separate their effects. For the search objective, gap and switching are scaled by 1,984 steps and a threefold switching range respectively, then combined with equal coefficients in opposite directions. The scales are fixed in the generator. Both dimensions must independently clear the protocol gates. The assignment optimizer uses 22,000 same-length swap proposals per arm, with twice the weight on the held factor. The spacing optimizer uses 3,500 same-decile, same-length proposals per arm and caps the sum of accepted LR-weighted movement at 0.35% of epoch mass before the independent pair audit. The bounded searches only use training inputs.

The [matching tables](tables/) and [full audits](audits/) include measured residuals and eligibility per seed. Each order consumes the exact 1,984 records, preserving all 494 questions, both loss scopes and their masked-token totals, and the canonical question trace order. Questions with more than four records are split into fixed chunks, and distinct chunks of one question may not be adjacent. The random-arm permutation is group blind subject to these constraints. Fine and coarse labels in the placebo audit are scheduling assignments separate from the canonical V4 labels.

별도 CPU 감사에서 감독 유형별 record·input·loss·LR-weighted loss 노출을 검증했다. S0T0–S1T0의 decile별 full-response 가중 비중 차이는 seed별 평균 절대값 0.07–0.25%p, 최대 1.26%p였다. S0T1–S1T1의 해당 차이는 2.54–4.38%p, 최대 11.46%p였다. 이 추가 감사는 동결된 eligibility를 바꾸지 않는다. [잔여 차이, decile별 노출 및 연속 구간](tables/integration_temporal/).

## Error analysis and comparability

The first snapshot covers 225,066 scored predictions from 314 complete cells, including 130,760 historical A/B and 94,306 predictions already produced by the running follow-up. It includes overlapping tool selection, grounding, argument, aggregation, refusal and silent-wrong flags, plus truncation, execution failure and unclassified outcomes. Flags use the frozen scorer evidence. Co-occurrence is retained and root causes remain undetermined. The tables are by cohort, arm, order seed, dataset and group. The predictions were reused for CPU scoring only. No output was used to construct an order.

For example, historical CT10K T1 gave overlapping grounding flags on 12.90% (A) and 52.35% (B) and argument flags on 10.27% and 37.53%, respectively, across five historical seeds. The taxonomy retains the underlying frozen scoring category. A grounding flag can occur on a matching answer because the separate grounding assessor measures additional conditions.

Historical and current follow-up evaluation snapshots agree on the observed sets of base revision, scorer fingerprint, decoding, serving versions and GPU identifiers. Code commits differ, and the audit summarizes distributions of recorded settings across cells. The two inspected training profiles agree on the recorded Torch, Transformers, TRL, PEFT, Accelerate and datasets versions. The prior five-item device probe had byte differences between server starts. Historical evidence therefore supplies descriptive context for the new intervention runs.

The expanded snapshot covers 227,164 scores across 316 cells. For historical T1, 481/5,100 A scores and 1,904/5,100 B scores lack a required executed place lookup. A single parseable model plan contained no location concept in 481 A and 1,883 B scores. Twenty-one B scores lack sufficient evidence to localize the omission. The frozen scorer definitions and first snapshot remain available. [Attribution rules](TAXONOMY.md) · [Expanded tables](tables/integration_snapshot/).

## Reproduction

From the repository root with the existing HF environment:

```bash
f=topic2_semantic_order/followup_conditions/causal_controls
p=/data/hwkim/sftdpo_work/runtime/envs/hf/bin/python
export CUDA_VISIBLE_DEVICES="" PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1
export HF_HOME=/data/hwkim/sftdpo_work/hf-cache HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
(cd "$f" && sha256sum -c PREREGISTRATION.sha256 && sha256sum -c PREREGISTRATION_AMENDMENT.sha256)
"$p" "$f/execution.py" --validate
"$p" "$f/test_controls.py" -v
"$p" "$f/execution.py" --dry-run S0T0-o1102-t43
"$p" "$f/execution.py" --tokenizer-check placebo-o211102-t51004
out=$(mktemp -d)
"$p" "$f/audit_temporal.py" --out-dir "$out/temporal"
"$p" "$f/taxonomy.py" --out-dir "$out/taxonomy" --snapshot-from "$f/tables/integration_snapshot/taxonomy_sources_snapshot.csv"
"$p" "$f/analyze_controls.py" --out-dir "$out/new_runs"
"$p" "$f/integration.py" --out-dir "$out/inventory"
```

The snapshot source CSV pins file hashes. Reproducing its current-follow-up rows requires that run's local prediction files. Use `taxonomy.py --historical-only` to analyze only the existing A/B cells. The generated run matrix contains all conditions, including exploratory schedules, and does not authorize them. The current status under `tables/integration_run_status/` reflect the absence of any newly completed causal-control training runs.

After the existing E1/E2 queue, same-GPU A/B reevaluation and final analysis have completed, use a clean detached worktree at the approved commit and provide an authorization record containing that full commit, the run plan SHA-256, the named jobs, one permitted GPU UUID and a timezone-aware start cutoff. Use `execution.py --train RUN --approval PATH` with the frozen HF environment, CUDA index and allocator setting. The checkpoint evaluator `execution.py --evaluate RUN --approval PATH` verifies a completed training receipt and the four external adapter hashes before using the pinned CT10K/H-dev manifests. It reuses the existing evaluation harness and serializes through the existing GPU lock. Final analysis consumes only verified receipts. It reports order-block sign-flip inference with Holm correction and group-level checkpoint trajectories. Secondary intervals distinguish run variation from joint run-and-template variation. Original E1/E2 intermediate adapters are external and inventoried. Supplemental scoring of those checkpoints has its own authorization boundary. [Amendment](PREREGISTRATION_AMENDMENT.md).
