# STATISTICAL_ANALYSIS — topic2_semantic_order

Tool: `analysis/analyze_t2.py` (frozen in commit `5de4ef68` before any B result existed; only the exposure-figure title in `make_figures.py` was edited after results). Output: `analysis/results_t2.json`, `tables/`. The analysis tool reproduces ablation_012 CT10K statistics for the A arm (smoke).

## Design
- Paired by order seed (A and B share the seed, data, config, training seed). 5 pairs.
- Groups: semantic_fine (tool, metric, aggregation, temporal unit, region type, OD role) from the **gold calls of evaluation items** (never model output); CT10K groups ≥ 30 items (95 groups; 10 small groups / 10 items excluded), H-dev ≥ 20 (31 groups, 58 small excluded, 702 items). Secondary groupings: semantic_coarse (tool, metric; 10 groups) and template_group (95).
- Collapse: group accuracy of a seed < base mean (3 base CT10K runs) − 20 pp (also 30 pp).
- Hierarchical bootstrap, 10,000 replicates, `default_rng(20261108)`: seed pairs resampled, then template_group clusters (178 CT10K, 160 H-dev), the same resample for A and B; items inside a cluster are not treated as independent.
- Pre-registered criteria S1–S4 (PLAN.md, committed before evaluation); non-inferiority margin −2 pp. H-dev and E1 are secondary replication only.

## CT10K semantic_fine, B − A (95% CI)
| metric | A | B | diff | CI |
|---|---|---|---|---|
| worst-group (pp) | 20.57 | 13.47 | −7.09 | [−29.05, 9.17] |
| bottom-10% group mean | 45.16 | 29.57 | −15.60 | [−42.15, 9.09] |
| groups >20 pp below base | 10.4 | 18.6 | +8.2 | [0.0, 12.8] |
| groups >30 pp below base | 8.4 | 13.4 | +5.0 | [−2.2, 11.6] |
| across-seed group variance | 0.0160 | 0.0172 | +0.0012 | [−0.0117, 0.0102] |
| overall (pp) | 88.12 | 82.19 | −5.93 | [−13.58, 0.57] |
| overall SD across seeds (pp) | 4.67 | 5.70 | +1.03 | [−3.47, 5.38] |

Other groupings: template_group collapse20 +6.8 [0.8, 8.2]; semantic_coarse worst −24.45 [−54.28, 3.59].
H-dev semantic_fine: worst −22.78 [−45.17, 4.26]; overall −4.77 [−12.06, 1.57]; collapse20 +2.8 [−0.4, 5.2]; overall SD −0.33 [−4.55, 4.51] (B slightly smaller on H-dev only).
Outcomes: S1 FAIL, S2 FAIL (CI lower bound = 0.0, not < 0), S3 FAIL (CT10K), S4 FAIL; H1 not supported. Per-seed values: `tables/ct10k_semantic_fine_per_seed.csv`.

## Interpretation limits
- Five seeds and 178 clusters give wide CIs; no B−A difference is both large and significant except E1 over-refusal (+4.29 [1.33, 7.31]) and E1 dev accuracy (−4.90 [−9.93, −0.17]). "Not supported" ≠ "proven harmful".
- B−A varies in sign by seed (o2026117/o2026131 B ≥ A on overall; o1102/o211102 far worse). Seeds are the dominant variance source; repeat pair (RESULTS.md) shows retraining noise of 1.8–4.3 pp on one seed.
- Worst-group is sensitive to tiny groups (several groups at 0–4%), so it is a high-variance statistic.
- The B degradation concentrates in T1 fare/province groups. Whether this is a causal effect of ordering (e.g. fare records spread thin) or seed-specific instability was **not tested**; no causal claim.
- Multiple groupings and datasets are reported without multiplicity correction; the pre-registered primary is CT10K semantic_fine.
