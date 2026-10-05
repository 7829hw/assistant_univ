# Bounded Thor pilot

This is an observation experiment on 12 SFT training questions and 82 DPO
pairs, not production model validation. The LLM still produces grounding only;
production prompt, contract, composer, validator and execution remain frozen.
No bitsandbytes, QLoRA, flash-attn, FP8/FP4 or system configuration changes.

## Reproduction

Use the environment and immutable container image described in THOR.md. Inside
the container the training Python is `/workspace/training/runs/thor-env/bin/python`.
The following commands assume repository root and that Python environment:

```bash
python -m training.pilot freeze --directory training/experiments/thor_pilot_002
python -m training.pilot configs --stage sft --directory training/experiments/thor_pilot_002
python -m training.pilot evaluate --label base --directory training/experiments/thor_pilot_002
python -m training.pilot_run --directory training/experiments/thor_pilot_002
```

`freeze` needs Git (run this step on the host's data-only Python if the container
has no Git). Relative dataset paths are portable between host and `/workspace`.
The experiment directory includes git diff/status, tracked **and untracked**
source snapshots, dataset copies/hashes, prompt/definition hashes, model and
tokenizer revision, decoding, leakage checks, configs, command logs, adapter
checkpoints, trainer state, memory profiles and actual JSON predictions.

Base must complete before the sequential runner accepts training. Each process
exits before the next GPU job starts. A failure stops the runner; inspect its
numbered log before continuing individual commands. Never rerun `freeze` over
an existing experiment. Generated artifacts are ignored by Git.

## Fixed experiment

- Existing Qwen3-8B revision, BF16 LoRA rank 16 / alpha 32 / dropout 0.05,
  all 252 verified projection modules, checkpointing, SDPA, AdamW.
- SFT 6912, DPO prompt 6784 / completion 256 / total 6912; no truncation.
- Seed 42; greedy generation, nonthinking chat template, max_new_tokens 1024,
  cache on for inference only. Tokenizer/model generation defaults are from the
  same pinned revision. No decoding optimization per model.
- Batch 1, accumulation **1** in this bounded pilot to make each optimizer step
  observable cheaply. Generic Thor configs keep accumulation 8. This pilot is
  not a test of effective batch 8.
- SFT LR: 5e-5, 1e-4, 2e-4. All share a 12-step linear scheduler horizon and
  one warmup step. Initially stop each at 6, observe actual validation generation
  at 2/4/6, then resume one selected experiment at checkpoint-6 to step 12.
  Observe resumed steps 8/12. Total SFT optimizer steps: 24.
- DPO: (5e-6, beta .1), (5e-6, beta .05), (1e-5, beta .1), six steps each,
  observations 2/4/6, frozen selected SFT reference on the shared base.
  Existing exact FP32 adapter reload and reference hash checks are retained.
- Evaluation/save every 2 steps, logging every step, adapter checkpoints only.
  Selection uses actual three-question validation grounding exact first, factor
  exact, role/concept, downstream validation, JSON. SFT loss breaks remaining
  ties; DPO uses six-pair observation preference accuracy before the earlier
  step tie-break. Do not compare reward margins across beta as equivalent scales.

The fixed three-question generation validation set selects checkpoints. The
20-question external development subset is evaluated only for Base and selected
models, and never selects a model. It has no exact question or conservative
semantic-template overlap with SFT training. Two unsupported diagnostics share
the deliberately broad unsupported training family and are reported separately.
The corpus is already development and is not human reviewed. "Unseen" here
means excluded from training, not a fresh final benchmark or pretraining audit.
One external example (`w22_p0`) intentionally has `expected_outcome:
needs_clarification`: its unspecified inner aggregation should fail composition.
The comparison retains this fixed example and reports that expected failure
separately; a structurally executable graph is not the correct outcome for it.

DPO training sees at most six of the 82 pairs in each run. Frequent teacher-forced
observations use a fixed balanced six-pair subset (one semantic and one
constraint pair per validation parent) after full dataset validation. Final preference statistics use
all 24 validation and all 82 training pairs, retaining category/type counts.
This experiment cannot establish full-epoch DPO memorization onset.

## Individual commands and resume

```bash
python -m training.pilot train --stage sft \
  --config training/experiments/thor_pilot_001/configs/sft_1.yaml --stop-step 6
python -m training.pilot train --stage sft \
  --config training/experiments/thor_pilot_001/configs/sft_1_resume.yaml \
  --resume-from-checkpoint training/experiments/thor_pilot_001/checkpoints/sft_1/checkpoint-6
python -m training.pilot evaluate --label candidate --splits valid \
  --adapter training/experiments/thor_pilot_001/checkpoints/sft_1/checkpoint-6
python -m training.pilot preferences --label dpo_candidate --splits valid train \
  --config training/experiments/thor_pilot_001/configs/dpo_1.yaml \
  --adapter training/experiments/thor_pilot_001/checkpoints/dpo_1/checkpoint-6/policy
```

The actual selected run number and adapter paths are in `best_sft.json` and
`best_dpo.json`; a `sft_1_resume.yaml` exists only when that run was extended.
Resume keeps the original total scheduler horizon (12), loads optimizer,
scheduler, RNG and dataloader progress, and really runs subsequent steps in a
new process. Changing max_steps from 6 to 12 is not the same schedule.

## Interpretation

Always report count/total. Three validation questions cannot establish statistical
improvement. Train exact match versus validation and external exact match is
distinct from teacher-forced loss and DPO preference accuracy. At initial SFT
policy = reference, DPO rewards/margins are zero and strict preference accuracy
has ties, not evidence of zero semantic ability.

Execution uses the fixed synthetic reference provider and date from the existing
evaluator, including the production `profile_for('reference')` compiler contract.
That provider has limited location/tool/metric support; compilation may also
reject unverified aggregation contracts. Report these separately from incorrect
grounding, and never relax the validator/compiler to improve the score.

JSON parse is the production tolerant extractor rate. Strict formatting errors
(fences/trailing prose) are also saved in error categories. Parser failures count
toward gold concept/macro/operator denominators. The pilot discovered and fixed
an evaluator observation bug; preserve pre-fix Base metrics separately and use
corrected Base for all comparisons. The observer restores the original chat
method, preserving client identity and existing A/B repair-phase instrumentation.
The thin evaluation wrapper also formerly compiled reference-handler plans with
the default TIMS contract. The pilot passes the existing provider profile through
the evaluator without changing compiler rules. Saved live generations are replayed
with that same profile for all final models; pre-correction reports are preserved,
and semantic/composition/validation scores are asserted identical. Only plans
which reached compilation are replayed, requiring one actual response and no
repair calls. Pre-compilation failures retain their live records, including failed
repairs. A validated repaired plan would require its full response trace; the
correction refuses to approximate that case.

Read-only tegrastats and nvidia-smi logs supplement per-stage CUDA/system memory
profiles. No power modes or clock settings are changed. Token throughput includes
prompt tokens, not just completion; DPO counts policy chosen+rejected tokens but
not reference work. A lower final loss is never sufficient for checkpoint choice.
Prompt compression is a separate future experiment: prompt token fraction is
not a measured FLOP fraction, and completion-only loss still processes the prompt.

See PILOT_REPORT.md for actual results and remaining annotation priorities.
