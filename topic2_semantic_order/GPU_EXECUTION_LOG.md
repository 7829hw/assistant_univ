# GPU_EXECUTION_LOG (decision 264) — updated as the run proceeds

| Item | Value |
|---|---|
| Scheduler | `gpu/scheduler16.py` (copy of scheduler15), pinned worktree `/data/hwkim/sftdpo_work/worktrees/wt_5d31bba_sched16`, commit `5d31bbab` |
| Start | 2026-11-08 17:47:36 +09:00, deadline 2026-11-09 17:47:25 (no new job after) |
| GPUs (by UUID) | idx0 `GPU-2445b100…`, idx1 `GPU-a5ce83d0…`, idx2 `GPU-48f798cc…`; all three idle before start (15 MiB, no foreign process, no Ollama container) |
| Rule | one job = one GPU, never two jobs on one GPU, next ready job starts within seconds; per-job timeline `gpu/timeline.jsonl`, scheduler log `gpu/runs.log` |
| First wave | T-B-o1102 -> GPU0, T-B-o211102 -> GPU1, T-B-o2026113 -> GPU2 (17:47–17:48). At the first optimizer step: ~36–37 GiB reserved per GPU (of 48 GiB), 100% utilisation. |
| Queue after | T-B-o2026117, T-B-o2026131, then H-dev (10-14), E1 (20-24), CT10K (30-34) of B, CT10K of A0-o2026117/o2026131 (40-41), repeat pair trainings (50-51) and H-dev (60-61). Eval jobs are held until `gpu/ready/T2_TOOLS.json`. |



## Final record (2026-11-09 18:47 +09:00)

- First scheduler: 41 jobs, 40 ok, 1 skipped (`RT2-15`, skipped by the 22 h no-new-job deadline at 18:15). No failed job, **no training retry** (OOM/NaN), no kill of any other process.
- **Deadline deviation (user instruction 2026-11-09: "24시간 안에 못 끝내도 계속 해")**: the pre-registered 22 h rule was waived for the one remaining job. `RT2-15` (truncation rerun of `hdev_t2_b_o2026131_r2_s1`, original in `cells/replaced/`) ran on GPU0 as a second `scheduler16.py` invocation with no `--deadline` and jobs file `gpu/jobs_t2_cont.json` (18:16–18:47, ok). First-scheduler DONE kept as `gpu/DONE_first_scheduler.json`. Success criteria and analysis tool were not changed.
- Truncation reruns: 15 rerun jobs (RT2-01…15), 65 cells replaced, rule from PLAN (rdev truncation ≥ 2 or server errors ≥ 2, otherwise > 1 %), originals kept in `cells/replaced/`, rerun regardless of the result. B truncated more often than A (see RESULTS.md), which is why most reruns were B cells.
- Training: one job = one GPU, 3 parallel. Per-training wall time 11,457–11,784 s (3.18–3.27 h), 1,984 optimizer steps, 16,047,305 policy tokens in every run (identical token budget A=B), mean logged loss 0.1885–0.1914. Peak GPU memory was observed only at the first optimizer step (~36–37 GiB reserved of 48 GiB, 100 % utilisation); no continuous peak-memory log was kept, so no peak value is claimed.
- Training and eval jobs ran from commit-pinned worktrees (`5d31bbab`).

### Per-job table (ok jobs, by start time)

| job | GPU | start | end | min | status |
|---|---|---|---|---|---|
| T-B-o1102 | GPU0 (`2445b100…`) | 11-08T17:47 | 11-08T20:59 | 192 | ok |
| T-B-o211102 | GPU1 (`a5ce83d0…`) | 11-08T17:47 | 11-08T21:04 | 197 | ok |
| T-B-o2026113 | GPU2 (`48f798cc…`) | 11-08T17:47 | 11-08T21:05 | 198 | ok |
| T-B-o2026117 | GPU0 (`2445b100…`) | 11-08T20:59 | 11-09T00:11 | 192 | ok |
| T-B-o2026131 | GPU1 (`a5ce83d0…`) | 11-08T21:04 | 11-09T00:20 | 196 | ok |
| H-B-o1102 | GPU2 (`48f798cc…`) | 11-08T21:05 | 11-08T21:39 | 34 | ok |
| RT2-01 | GPU2 (`48f798cc…`) | 11-08T21:39 | 11-08T22:15 | 36 | ok |
| H-B-o211102 | GPU2 (`48f798cc…`) | 11-08T22:15 | 11-08T22:45 | 30 | ok |
| H-B-o2026113 | GPU2 (`48f798cc…`) | 11-08T22:46 | 11-08T23:25 | 39 | ok |
| RT2-02 | GPU2 (`48f798cc…`) | 11-08T23:25 | 11-09T00:01 | 36 | ok |
| E-B-o1102 | GPU2 (`48f798cc…`) | 11-09T00:01 | 11-09T01:17 | 76 | ok |
| H-B-o2026117 | GPU0 (`2445b100…`) | 11-09T00:11 | 11-09T00:47 | 36 | ok |
| H-B-o2026131 | GPU1 (`a5ce83d0…`) | 11-09T00:20 | 11-09T00:53 | 33 | ok |
| RT2-03 | GPU0 (`2445b100…`) | 11-09T00:47 | 11-09T01:24 | 37 | ok |
| RT2-04 | GPU1 (`a5ce83d0…`) | 11-09T00:53 | 11-09T01:29 | 36 | ok |
| RT2-05 | GPU2 (`48f798cc…`) | 11-09T01:17 | 11-09T02:09 | 52 | ok |
| E-B-o211102 | GPU0 (`2445b100…`) | 11-09T01:24 | 11-09T02:40 | 76 | ok |
| E-B-o2026113 | GPU1 (`a5ce83d0…`) | 11-09T01:29 | 11-09T02:43 | 74 | ok |
| E-B-o2026117 | GPU2 (`48f798cc…`) | 11-09T02:09 | 11-09T03:17 | 69 | ok |
| RT2-06 | GPU0 (`2445b100…`) | 11-09T02:41 | 11-09T03:41 | 60 | ok |
| RT2-07 | GPU1 (`a5ce83d0…`) | 11-09T02:43 | 11-09T03:39 | 56 | ok |
| RT2-08 | GPU2 (`48f798cc…`) | 11-09T03:18 | 11-09T04:04 | 46 | ok |
| E-B-o2026131 | GPU1 (`a5ce83d0…`) | 11-09T03:39 | 11-09T05:04 | 84 | ok |
| C-B-o1102 | GPU0 (`2445b100…`) | 11-09T03:41 | 11-09T06:21 | 160 | ok |
| C-B-o211102 | GPU2 (`48f798cc…`) | 11-09T04:04 | 11-09T06:44 | 160 | ok |
| RT2-09 | GPU1 (`a5ce83d0…`) | 11-09T05:04 | 11-09T05:56 | 52 | ok |
| C-B-o2026113 | GPU1 (`a5ce83d0…`) | 11-09T05:56 | 11-09T08:57 | 181 | ok |
| RT2-10 | GPU0 (`2445b100…`) | 11-09T06:21 | 11-09T08:02 | 101 | ok |
| RT2-11 | GPU2 (`48f798cc…`) | 11-09T06:44 | 11-09T07:17 | 32 | ok |
| C-B-o2026117 | GPU2 (`48f798cc…`) | 11-09T07:17 | 11-09T10:11 | 174 | ok |
| C-B-o2026131 | GPU0 (`2445b100…`) | 11-09T08:02 | 11-09T10:53 | 171 | ok |
| RT2-12 | GPU1 (`a5ce83d0…`) | 11-09T08:57 | 11-09T11:53 | 176 | ok |
| RT2-13 | GPU2 (`48f798cc…`) | 11-09T10:11 | 11-09T12:19 | 128 | ok |
| RT2-14 | GPU0 (`2445b100…`) | 11-09T10:53 | 11-09T13:32 | 159 | ok |
| C-A0-o2026117 | GPU1 (`a5ce83d0…`) | 11-09T11:53 | 11-09T14:21 | 148 | ok |
| C-A0-o2026131 | GPU2 (`48f798cc…`) | 11-09T12:19 | 11-09T14:35 | 136 | ok |
| T-A0-o2026131-r2 | GPU0 (`2445b100…`) | 11-09T13:32 | 11-09T16:44 | 192 | ok |
| T-B-o2026131-r2 | GPU1 (`a5ce83d0…`) | 11-09T14:21 | 11-09T17:38 | 197 | ok |
| H-A0-o2026131-r2 | GPU0 (`2445b100…`) | 11-09T16:44 | 11-09T17:14 | 30 | ok |
| H-B-o2026131-r2 | GPU0 (`2445b100…`) | 11-09T17:38 | 11-09T18:15 | 37 | ok |
| RT2-15 | GPU0 (`2445b100…`) | 11-09T18:16 | 11-09T18:47 | 31 | ok |
