# Implementation verification — 2026-10-04

This is the earlier CPU implementation snapshot. Subsequent **actual Jetson AGX Thor
BF16 LoRA SFT/DPO** operation, memory, throughput and reference precision validation
is recorded in [THOR_VALIDATION.md](THOR_VALIDATION.md).

Workspace branch: `geoflow/dev-v2`; initial HEAD: `65e9ea2`.
Tests ran in `/tmp/geoflow-training-venv` with runtime requirements installed.
Only tokenizer dependencies (transformers 4.56.2 and Jinja2) were additionally
installed. No torch, model weights, GPU training or external provider execution
was used. Generated data and run artifacts are ignored by git.

## Results

- Existing suite before changes: 1,058 tests; one existing expected failure and two
  environment errors (missing vendor XLSX, sandbox localhost socket restriction).
- New CPU training tests: **34 passed**. They cover canonical serialization,
  production prompt reuse, supported/unsupported gold, downstream validation,
  mutations (including structurally valid OD swap), group leakage, strict reports,
  source mixing, manifests/checksums, hard-negative mining, configs/dry-run,
  token-boundary guards and the existing evaluator integration.
- Final whole suite: **1,092 tests**; 1,090 passed, one existing expected failure,
  one existing environment error. The error is
  `tests.test_provider_delegation.GoldExtractionTest.test_gold_file_matches_the_vendor_sources`:
  `evaluation/vendor100/질문 결과 및 정답 설명_100문항.xlsx` is not in this workspace.
  Socket tests passed when executed with local sockets allowed. No new regression
  remains. The full suite does not have a green exit because of the missing XLSX.
- SFT strict build: **12 train / 3 validation**, 15 samples, 13 connected intent
  groups. One known clarification example (`ex11`) excluded with a report.
- DPO strict build: **82 train / 24 validation** pairs; **66 semantic / 40 constraint**.
  Changing library/seed/max-negatives changes these distributions.
- Direct inspection of JSONL: assistant outputs are compact JSON only, contain
  concepts/factors or explicit unsupported, and have no graph/runtime metadata.
  All 15 chosen outputs rechecked: 13 parse/compose/G1-G7 successes, two explicit
  refusals (no graph validation claimed for these).
- Both SFT and DPO split checks passed. Rebuilding with seed 42 produced the same
  bytes for all four JSONL files (manifest timestamps intentionally vary).
- SFT and DPO config/dataset/provenance dry-runs passed. Module imports and seven
  CLI `--help` commands passed without the GPU training stack.
- **Actual Qwen3-8B tokenizer** prefix and length checks passed for SFT and DPO.
  SFT maximum prompt: 6,748 tokens; completion including EOS: 138 tokens;
  full sequence maximum: 6,883 tokens. Defaults 8,192 full / 7,168 prompt /
  1,024 completion cover these seed examples. The model was not downloaded.
- Existing evaluator replay on the 15 gold examples produced grounding/factor
  exact match 1.0 and G1-G7 pass rates 1.0 among the 13 checked supported samples.
  This is an integration smoke check, **not measured model performance**.
- Existing evaluator -> compiler -> executor mock smoke passed for a direct scope
  speed question. Report comparison CLI also passed a replay smoke check.
- `compileall`, AST parsing and `git diff --check` passed.

## Files

Modified:

```text
.gitignore                         Ignore datasets/checkpoints/runs
geoflow/aggregation.py             Lossless to_flat serialization helper only
evaluate_planner.py                Missing raw/factor/exact/G-rule metrics only
```

Added:

```text
training/__init__.py
training/ARCHITECTURE.md
training/README.md
training/VALIDATION.md
training/requirements.txt
training/data/__init__.py
training/data/canonicalize.py
training/data/validation.py
training/data/common.py
training/data/split.py
training/data/build_sft.py
training/data/negative_mutations.py
training/data/build_dpo.py
training/configs/qwen_sft.yaml
training/configs/qwen_dpo.yaml
training/trainer_common.py
training/train_sft.py
training/train_dpo.py
training/inference.py
training/predict_groundings.py
training/evaluate_checkpoint.py
training/merge_adapter.py
tests/test_training_data.py
tests/test_training_trainers.py
tests/test_training_evaluation.py
```

## Limits

The seed source contains no OD gold and only a narrow set of measures/aggregation
families. Reviewer provenance includes annotations awaiting human review. New
independent reviewed examples and benchmark families are needed before drawing
fine-tuning conclusions. Existing benchmark files remain reserved from training.

Actual TRL optimizer steps, LoRA/QLoRA GPU initialization, frozen dual-adapter
resume/save, full checkpoint merge, multi-GPU and GGUF/Ollama deployment remain
unexecuted. The pinned Trainer API was checked against the official versioned
TRL documentation/source; GPU behavior still needs hardware verification.
