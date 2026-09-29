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
