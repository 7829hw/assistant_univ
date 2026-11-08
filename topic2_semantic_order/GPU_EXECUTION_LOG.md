# GPU_EXECUTION_LOG (decision 264) — updated as the run proceeds

| Item | Value |
|---|---|
| Scheduler | `gpu/scheduler16.py` (copy of scheduler15), pinned worktree `/data/hwkim/sftdpo_work/worktrees/wt_5d31bba_sched16`, commit `5d31bbab` |
| Start | 2026-11-08 17:47:36 +09:00, deadline 2026-11-09 17:47:25 (no new job after) |
| GPUs (by UUID) | idx0 `GPU-2445b100…`, idx1 `GPU-a5ce83d0…`, idx2 `GPU-48f798cc…`; all three idle before start (15 MiB, no foreign process, no Ollama container) |
| Rule | one job = one GPU, never two jobs on one GPU, next ready job starts within seconds; per-job timeline `gpu/timeline.jsonl`, scheduler log `gpu/runs.log` |
| First wave | T-B-o1102 -> GPU0, T-B-o211102 -> GPU1, T-B-o2026113 -> GPU2 (17:47–17:48). At the first optimizer step: ~36–37 GiB reserved per GPU (of 48 GiB), 100% utilisation. |
| Queue after | T-B-o2026117, T-B-o2026131, then H-dev (10-14), E1 (20-24), CT10K (30-34) of B, CT10K of A0-o2026117/o2026131 (40-41), repeat pair trainings (50-51) and H-dev (60-61). Eval jobs are held until `gpu/ready/T2_TOOLS.json`. |

The final per-job table (start/end, GPU, status, peak memory, retries) is written into this file after `gpu/DONE` appears.
