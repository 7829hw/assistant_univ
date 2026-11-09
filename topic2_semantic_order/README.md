# GeoFlow Topic 2: semantic-balanced training-order experiment

This package implements a **new training data order**, not a trained model. It runs offline and does not use evaluation examples to determine schedule labels. Files are designed to be copied under `topic2_semantic_order/` in the root of `7829hw/assistant_univ`, branch `geoflow/sft-dpo-t2pc`.

## Current status

The real A/B experiment (decision 264) has been run on GPU and evaluated. **Result: H1 (semantic-balanced order reduces group collapse) is not supported** — all pre-registered criteria S1–S4 failed (see `RESULTS.md`, `STATISTICAL_ANALYSIS.md`, `PAPER_FINDINGS.md`). Scheduling-fairness metrics (`orders/offline_validation_summary.json`, fig4) are mechanical and are NOT accuracy results. C/D coverage arms were not run (blocked, `DATA_AUDIT.md`). H-final was never opened.

## Offline: generate B schedules on the actual V4 data

```bash
# From original GitHub repository ROOT, with this package unpacked as topic2_semantic_order/
python topic2_semantic_order/semantic_schedule.py \
  --train sft_dpo_inventory/pilot_010/build/V4/full/sft_train.jsonl \
  --approved sft_dpo_inventory/pilot_006_prep/approved/approved_train_v6.jsonl \
  --output-dir topic2_semantic_order/orders \
  --seeds 1102 211102 2026113 2026117 2026131 \
  --reference-order-dir sft_dpo_inventory/ablation_011/build/orders \
  --reference-order-dir sft_dpo_inventory/ablation_013/build/orders

python topic2_semantic_order/make_training_configs.py \
  --repo-root . --schedule-dir topic2_semantic_order/orders \
  --config-dir topic2_semantic_order/configs \
  --seeds 1102 211102 2026113 2026117 2026131 \
  --repeats 1

python -m unittest -v topic2_semantic_order.test_semantic_schedule
```

Outputs: frozen semantic-order JSON files, a summary of **actual** original O4′ vs balanced exposure metrics, a config for both A and B for every order seed. `reference_is_true_o4prime` must be `true` for all five seed reports. Existing V4 train/approved data are NEVER modified.

## GPU: dry-run before actual training

```bash
runtime/envs/hf/bin/python sft_dpo_inventory/ablation_011/train/train_a11.py \
  --config topic2_semantic_order/configs/baseline_o1102_r1.yaml --dry-run

runtime/envs/hf/bin/python topic2_semantic_order/train_semantic.py \
  --config topic2_semantic_order/configs/semantic_o1102_r1.yaml --dry-run

# Then perform --tokenizer-check for both paths.
# Only AFTER logs and paths are verified, remove --dry-run for a genuine training run.
```

**Do not run training before confirming the original GPU usage rules in `CLAUDE.md`.** The experiment does not deploy jobs or manage Ollama/GPU containers. Both original and semantic runs should use the same frozen base model revision and evaluator. The wrapper prints schedule SHA-256, exact identity checks, and installed SequentialSampler.

## Optional C/D coverage arms

`audit_coverage_arm.py` verifies an *externally approved* coverage replacement dataset with equal record count, tokenizer-derived loss-token budget within ±1%, and authoritative protected-ID and protected-family exclusion lists. If new rows are introduced and the lists are missing or empty, it fails closed. `coverage_o4prime.py` recreates the reference NumPy O4′ ordering only after a successful audit.

Neither script constructs extra teacher traces, overrides decision 120/C-1, reads H-final, or silently selects approved examples. The user's original `ablation_013/QUESTIONS.md` records human decisions that must be resolved before the C/D experiment.

## Included files

- `semantic_schedule.py`: train-only semantic signatures, hierarchical deficit scheduler, SHA/unique/max-run checks, fair-exposure metrics, fail-closed coverage validator.
- `train_semantic.py`: same `train_b7b`/`train_a11` SFT training path and losses, but using a frozen semantic order.
- `make_training_configs.py`: paired A/B configs for five order seeds and optional repeats.
- `audit_coverage_arm.py`, `coverage_o4prime.py`: policy-respecting preparation for the coverage-factor arms.
- `test_semantic_schedule.py`: unit tests with synthetic 1,984-record fixtures.
- `offline_smoke.py` and `offline_smoke_results.json`: labeled artificial-fixture structural validation.
- `PLAN.md`: experimental controls, metrics, criteria and uncertainty.

Do not describe a prospective hypothesis or schedule-fairness metric as a demonstrated reduction in model errors. Validation requires new checkpoint training and frozen evaluation.
