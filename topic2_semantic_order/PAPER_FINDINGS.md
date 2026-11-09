# PAPER_FINDINGS — topic2_semantic_order

## Validated findings (real GPU training + evaluation, 5 seeds)
1. **A semantic-balanced record order (hierarchical deficit round-robin on tool×metric, then agg/time/region/OD signature, max run 4) did not reduce semantic group collapse** relative to the O4′ random order on CT10K: collapse20 groups 10.4 → 18.6 (+8.2, CI [0.0, 12.8]), worst-group 20.6 → 13.5 pp (−7.1, CI [−29.1, 9.2]), overall 88.12 → 82.19 (−5.93, CI [−13.58, 0.57]). All pre-registered criteria S1–S4 failed. H-dev (secondary) agrees in direction.
2. **Mechanical balance ≠ behavioural balance.** Window exposure imbalance fell from ~9.5% to 1.2% (fig4) while accuracy did not improve: making exposure uniform in order does not by itself protect low-frequency groups under this SFT recipe (1 epoch, batch 1, lr 2e-4 linear decay).
3. **Degradation concentrated in fare (T1)**: 77.4 → 47.3% (CT10K) with seed-dependent severity (B-o1102 18%, B-o211102 10%); OD (T5) roughly unchanged (78.6 → 75.2) with smaller seed SD (10.8 → 6.0 pp).
4. B showed more refusals (E1 over-refusal +4.3 pp [1.3, 7.3]; refused_unsupported 2.1 → 4.2%), more silent wrong answers (3.7 → 6.7%) and ~2× truncation.
5. **Retraining noise is as large as the effect**: identical config and order, retrained, differ by 1.8 pp (A) and 4.25 pp (B) on H-dev with 9–17% discordant items, and the B−A gap on seed o2026131 shrinks from +4.10 to +1.65 between the original and repeat pair. Order-effect studies with single trainings per cell are not interpretable.
6. Identical token budget (16,047,305 policy tokens), same loss level (mean logged loss 0.19) across arms: the difference is not a data/loss-budget artefact.

## Claimable novelty (carefully)
- A reproducible, pre-registered, seed-paired, hierarchical-bootstrap protocol for testing training-order interventions against group collapse, with an eval-gold-derived group definition and H-final sealed.
- A **negative result** for a natural curriculum/balancing fix, plus a quantified noise floor from repeat pairs. Honest framing: "uniform interleaving of semantic groups is not sufficient (and may hurt fare groups)".

## Must not be claimed
- That Semantic-balanced scheduling improves, or reduces collapse in, GeoFlow; that B is significantly worse across the board (most CIs include 0).
- Any causal mechanism for the fare degradation (untested).
- Any C/D (coverage) result — not run; nothing about adding the 44 fare questions.
- Anything about H-final (sealed). Anything from coarse-only/fine-weight ablations (not run; `fine_weight=0.24` was fixed, never tuned).
- Per-seed B−A as reliable effects (noise floor above); the repeat-pair result generalising beyond one seed.

## Next experiments (priority)
1. More repeat pairs / seeds to estimate retraining variance per arm (cheap relative to claims; resolves finding 5) before any further order study.
2. Diagnose B fare failure on seeds 1102/211102 (inspect failure categories, loss on fare tokens, position of fare records in B order) — diagnostic only, never feed CT10K/H-dev errors back into the scheduler.
3. Coarse-only (fine_weight=0) and coverage-neutral variants as ablation; consider oversampling/loss-weighting instead of order, as a **separate** factor.
4. C/D coverage arms after the data-approval blockers are resolved by the user.

## Title / contribution candidates
- "Balancing the Order Is Not Enough: A Negative Result on Semantic-Balanced Training Schedules for Tool-Calling SFT"
- "Does Interleaving Semantic Groups Prevent Group Collapse? A Pre-registered Seed-Paired Study with a Retraining Noise Floor"
- Contributions: (i) negative result with pre-registered criteria, (ii) hierarchical seed→template→item paired bootstrap protocol, (iii) quantified GPU/retraining nondeterminism that dominates small order effects.
