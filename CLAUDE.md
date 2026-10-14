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
5. Do not make other model calls (e.g. live repair calls from replay experiments) while a measurement is running.
   Since decision 79 (2026-10-12) Ollama measurements run continuously with the model kept loaded, so any other call
   changes the server state the cell is measured under.

## SFT/DPO work branch rules (geoflow/sft-dpo-t2pc)

These rules apply to all SFT/DPO work on this branch, in this and later sessions.

1. The work branch is `geoflow/sft-dpo-t2pc`. Do not commit or push to `geoflow/dev-v2` or
   `geoflow/sft-dpo-thor`. Read thor only through `git show` or a temporary worktree.
2. After each work unit, in this order: verify → review the diff and the staged diff → make a logical
   commit → `git push origin geoflow/sft-dpo-t2pc` → report the SHA.
   - The first push sets upstream with `-u`.
   - No force push, merge/rebase or history rewrite, except the rebase that rule 14 allows for a rejected push.
   - If a push fails, follow rule 14. Otherwise report the cause; do not work around it.
3. Commit all data (decision 33, 2026-10-07): generated training/evaluation data and raw outputs (corpora, thinking
   and teacher traces, evaluation raw outputs under `training/generated/`, summaries). Never commit model/adapter
   weights, checkpoints, merged models, GGUF files, caches or temporary files. Never use `git add -f`; if data is
   ignored, change `.gitignore` instead.
4. Ollama: use the existing Docker server (`localhost:11434`) as is. Since decision 69 (2026-10-12) the default GPU for
   Ollama measurements is host GPU 3 (UUID `GPU-48f798cc-9437-50ac-d604-448bbad7b311`). The container's `device_ids`
   decide which GPU Ollama actually uses (2026-10-12: "3"; earlier records under decisions 32 and 38 ran on GPU 2;
   record in `sft_dpo_inventory/pilot_001/ollama/container/`).
   - Do not move, restart or reconfigure the container or change its GPU assignment. A person does that.
   - Do not start another Ollama server and do not pull models. If something is needed, stop and report.
   - Ollama calls are allowed (decision 19, 2026-10-06). Rule 7 (measurement method, HF and Ollama measurements in
     sequence) still applies.
5. Default GPU (decision 69, 2026-10-12; replaces the GPU split of decision 38): Ollama measurements and HF work
   (training, HF inference) both use host GPU 3 (UUID `GPU-48f798cc-9437-50ac-d604-448bbad7b311`) by default.
   - GPU 2 (UUID `GPU-a644de12-2a2c-ca3d-4822-b80f704b0b21`) is a spare, used only when GPU 3 cannot be used (for
     example, another user's process is on it). Never use GPU 0 or GPU 1.
   - Exception (decision 83, 2026-10-13): in work under decision Y (pilot_003), GPU 0–3 may be used. Since decision 84 (2026-10-13)
     GPU `a644de12…` is gone and the remaining three are indices 0–2; GPU `48f798cc…` (the Ollama GPU) is now index 2, so map by UUID. Training still uses one
     GPU. Before each use check UUID, state, memory in use and other users' processes, and skip a GPU that has another
     process. Do not run HF on GPU 3 while an Ollama measurement (E reference cell, teacher collection) runs. Before splitting
     work across GPUs, compare HF sampling of 5 items with the same seed on each GPU against GPU 3 byte for byte; if any GPU
     differs, measure all samples of a cell on one GPU and both cells of a paired comparison on the same GPU. Record the
     device of every sample.
     Decision 89 (2026-10-14) allows the same GPUs and checks for the vLLM serving check (`serving_vllm`).
   - HF runs with `CUDA_VISIBLE_DEVICES=3` (or `=2` for the spare); inside the process it appears as `cuda:0`. Do not
     change `CUDA_DEVICE_ORDER`.
   - Never unload Ollama models yourself and never touch the container to free a GPU. If an Ollama measurement is
     scheduled, finish or stop HF work on the Ollama GPU before it starts.
   - Before using any GPU, check host `nvidia-smi` (not the Ollama API): the UUID, state, memory already in use, and
     processes of other users. If another user's process is on that GPU (GPU 3 is shared with another user at
     times), do not use it; switch to the spare or stop and report.
6. Before GPU work, confirm by UUID which physical GPU each job uses.
   - Compare host `nvidia-smi -L`, the Ollama container's GPU (`nvidia-smi -L` inside it; if that fails with the
     NVML error, its `docker inspect` DeviceRequests and `/dev/nvidia*` node), and the torch device UUID under the
     `CUDA_VISIBLE_DEVICES` value in use.
   - HF and Ollama may share one GPU only in sequence (rule 7), never at the same time. If the GPU in use cannot be
     confirmed, stop and report.
7. Ollama measurement method (decision 79, 2026-10-12; replaces the per-question and per-sample model unload).
   - Measure continuously: do not unload the model per question or between samples, and do not wait for keep_alive
     to expire. `evaluate_vendor100.py llm` defaults to `--model-state keep_loaded` with no unload at start;
     `calibration_001/run_cal.sh` defaults to `ISOLATION=continuous`.
   - The old isolated method stays available only to reproduce earlier records (`--model-state unload_per_question`,
     `ISOLATION=per_question`). `evaluate_v2.py` and `evaluate_prompt_ab.py` are older harnesses that still unload
     per observation; do not use them for new cells.
   - All cells in one comparison use the same method. Do not compare a continuous cell directly with a record measured
     with unloading (everything up to calibration_001 and quant_recipe); if the comparison is needed, measure the
     reference cell again continuously.
   - Record the method in the result metadata (`pipeline.isolation`, `pipeline.start_unload`, `run_settings.model_state`).
   - Measure one cell at a time, and make no other model calls during a measurement (rule 5 at the top).
   - The decision 55 checks (rule 13) stay as they are.
   - Do not run HF and Ollama measurements at the same time; run them in sequence.
8. Keep the existing data policies: protected dev/validation/diagnostic data never becomes training input,
   and annotation recommendations or validator PASS are not human approval. Vendor 100 results are
   evaluation-only (never used for training, checkpoint selection or annotation candidates).
9. Thinking condition (decided 2026-10-06): the training target is qwen3:8b + T2PC code and prompt 87048d0c with
   thinking ON, for both training and evaluation.
   - Comparison baselines: Ollama path = cell E (think unspecified, which Ollama 0.34.4 renders as thinking on;
     grounding_ok 79). HF path = HF-E (base Qwen3-8B@b968826d, `enable_thinking=True`).
   - Operating path (decision 76, 2026-10-12): HF transformers BF16, base Qwen3-8B@b968826d plus the adapter. The main
     comparison is HF-base vs the HF trained model on that path. Ollama E is a reference cell only (reported, never
     judged), and the Ollama quantized paths (Q4, Q8) are no longer operating targets.
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
13. Ollama GPU check (decision 55, 2026-10-08). When the container loses its GPU, Ollama silently runs on the CPU. This
    rule protects the execution condition only; it does not change any judgment rule.
    - Before starting an Ollama cell (evaluation, render check, collection): `docker exec ollama nvidia-smi -L` must list
      the Ollama GPU of rule 5 (default GPU 3, UUID `GPU-48f798cc…`; the guard's `--gpu-uuid` names the spare GPU 2
      when it is used). After (or during) the first item, `ollama ps` must show PROCESSOR 100% GPU
      (`/api/ps` `size_vram == size`).
    - During the cell, check the recorded generation rate of every item (eval_count / eval_duration; evaluation records
      without eval_duration use eval_count / (duration_ms − load_duration_ms)). If it falls far below the same model's
      GPU records (threshold fixed beforehand from existing records and written in the run's plan-deviation record;
      pilot_002: 30 tok/s, `sft_dpo_inventory/pilot_002/PLAN_DEVIATIONS.md`), stop the cell at once.
      `sft_dpo_inventory/pilot_002/ollama_gpu_guard.py` does both checks.
    - Keep a stopped cell's output as `ABORTED_*`; never use it for baselines or judgments. Do not touch the container;
      report. Once the cause is fixed, the cell may be measured again from the start; this replaces an invalid
      measurement and is not a rerun. Record that and why.
14. Several sessions on one branch (decision 57, 2026-10-09). This rule takes precedence over the "no merge/rebase" part of rule 2.
    - If a push is rejected, `git fetch` and compare the files changed by the remote-only commits with the files changed by the
      local-only commits (`git diff --name-only <merge-base> origin/<branch>` vs `... HEAD`).
    - If no file is in both lists, rebase the local commits onto the remote branch, then push. Never force push.
    - If any file is in both lists, or the rebase hits a conflict, stop (abort the rebase) and report.
    - Before adding a decision, fetch the remote and use the next free number in `sft_dpo_inventory/DECISIONS.md`.
    - Never edit commits or files that another session pushed.
15. Running scripts (decision 88, 2026-10-14). Never edit a script file while a process is executing it: bash reads scripts
    incrementally, so an edit can make the running shell execute different or partial lines. If a change is needed, write a new
    file and use it from the next run.
