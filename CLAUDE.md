# CLAUDE.md

## Waiting for long-running jobs (LLM evaluation runs, etc.)

GPU evaluation runs (`evaluate_vendor100.py llm`, `evaluate_v2.py run`, ...) take tens of minutes to hours.
Choosing the wrong way to wait means waiting long after the job has finished. On 2026-09-29 a wait loop
matched its own command line with `pgrep -f`, never exited, and the GPU sat idle for about two hours.

1. Run the job itself in the background (chain dependent steps with `&&` in that one command) and wait
   for its completion notification. Do not add a separate polling loop.
2. If a separate wait is unavoidable, wait on an unambiguous completion signal the job produces: the final
   summary line in its log (e.g. `grep -q '^{"items"' run.log`), the finished output file, or the PID
   captured at launch (`kill -0 $PID`). Also match a failure marker (`Traceback`) so the loop ends if the
   job dies.
3. Never use `pgrep -f` / `pkill -f` with a pattern that appears in the current shell command. It matches
   itself, so the loop never ends, or the kill takes down its own shell. If a process check is needed, use
   a bracket pattern such as `'[b]0_holdout'` or exclude your own PID.
4. If a wait runs longer than the job's expected duration, check the actual state instead of assuming:
   log modification time, output line count, `curl -s localhost:11434/api/ps`.
5. Do not make other model calls (e.g. live repair calls from replay experiments) while an isolated
   measurement is running. They break the per-observation model unload (`OllamaStateReset`).

## SFT/DPO work branch rules (geoflow/sft-dpo-t2pc)

These rules apply to all SFT/DPO work on this branch, in this and later sessions.

1. The work branch is `geoflow/sft-dpo-t2pc`. Do not commit or push to `geoflow/dev-v2` or
   `geoflow/sft-dpo-thor`. Read thor only through `git show` or a temporary worktree.
2. After each work unit, in this order: verify → review the diff and the staged diff → make a logical
   commit → `git push origin geoflow/sft-dpo-t2pc` → report the SHA.
   - The first push sets upstream with `-u`.
   - No force push, merge/rebase or history rewrite.
   - If a push fails, report the cause; do not work around it.
3. Commit all data (decision 33, 2026-10-07): generated training/evaluation data and raw outputs (corpora, thinking
   and teacher traces, evaluation raw outputs under `training/generated/`, summaries). Never commit model/adapter
   weights, checkpoints, merged models, GGUF files, caches or temporary files. Never use `git add -f`; if data is
   ignored, change `.gitignore` instead.
4. Ollama: use the existing Docker server on GPU 3 (`localhost:11434`) as is.
   - Do not restart or reconfigure the container or change its GPU assignment.
   - Do not start another Ollama server and do not pull models. If something is needed, stop and report.
5. GPU work outside Ollama (training, HF inference) uses CUDA GPU 2 by default (decided 2026-10-06).
   - Run with `CUDA_VISIBLE_DEVICES=2`; inside the process it appears as `cuda:0`.
   - Do not change `CUDA_DEVICE_ORDER`.
   - GPU 3 (the Ollama GPU) may be used only for additional work while Ollama is not in use
     (`CUDA_VISIBLE_DEVICES=3`). Before each use, confirm with host `nvidia-smi` that no Ollama model is loaded
     on GPU 3 (memory in use and processes). If anything is loaded, do not use GPU 3.
   - Never unload Ollama models yourself and never touch the container to free GPU 3.
   - If an Ollama measurement or Ollama use is scheduled, finish or stop GPU 3 work before it starts.
   - The GPU 3 check itself uses host `nvidia-smi`, not the Ollama API.
   - Ollama calls are allowed again (decision 19, 2026-10-06; the earlier ban while the container's NVML failed is
     lifted). Rule 7 (isolated measurements, HF and Ollama measurements in sequence) still applies.
6. Before GPU work, confirm by UUID that the training GPU and the Ollama GPU are different physical GPUs.
   - Compare host `nvidia-smi -L`, the Ollama container's GPU (`nvidia-smi -L` inside it; if that fails with the
     NVML error, its `docker inspect` DeviceRequests and `/dev/nvidia*` node), and the torch device UUID under
     `CUDA_VISIBLE_DEVICES=2`.
   - If they are the same or cannot be confirmed, stop and report. Also check memory already in use on GPU 2.
7. While an isolated Ollama measurement runs, make no other Ollama calls (rule 5 above). Do not run HF and
   Ollama measurements at the same time; run them in sequence.
8. Keep the existing data policies: protected dev/validation/diagnostic data never becomes training input,
   and annotation recommendations or validator PASS are not human approval. Vendor 100 results are
   evaluation-only (never used for training, checkpoint selection or annotation candidates).
9. Thinking condition (decided 2026-10-06): the training target is qwen3:8b + T2PC code and prompt 87048d0c with
   thinking ON, for both training and evaluation.
   - Comparison baselines: Ollama path = cell E (think unspecified, which Ollama 0.34.4 renders as thinking on;
     grounding_ok 79). HF path = HF-E (base Qwen3-8B@b968826d, `enable_thinking=True`).
   - Do not go back to nonthinking settings (`enable_thinking: false`, `--model-think off`) for new training data,
     training configs or evaluation cells. Ask the user first if a task seems to need them.
   - Existing nonthinking records (F, HF-F, the nonthinking `reviewed_gold_v003_t2pc` exports and configs) stay
     as records. Do not delete or rewrite them.
10. Later decisions (data selection, loss scope, rendering, DPO reference, checkpoint selection) are recorded with
    dates in `sft_dpo_inventory/DECISIONS.md`. Read it before SFT/DPO work and follow it.
11. Training runs use `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True` by default (decision 17, 2026-10-06).
    It changes only the CUDA allocator, not data, lengths, precision or LoRA.
12. `ollama create` is approved only for (decision 20, 2026-10-06):
    - the base Qwen3-8B conversion, and
    - the models selected later in the real pilot (SFT and final SFT+DPO).
    Register each under a new name. Never overwrite, re-tag or delete an existing Ollama model. Any other
    registration needs a new user approval.
