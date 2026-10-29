# Relocated runtime — rebuilt and CPU checked

The copied `hfvenv`, `vllmvenv`, `llamacpp_venv`, `uvtool`, `uv-python`, and
`llama.cpp-b11434` are preserved as historical bytes. Copying them does not
make their interpreters, entry points, absolute links, or build trees movable.

The new environments are under `/data/hwkim/sftdpo_work/runtime/envs/`
as `hf`, `vllm`, `llamacpp`, and `uvtool`. The observed Python versions and
distribution names/versions are in `observed_packages.json`; this records
installed names and versions. The separate wheel provenance records identify
the actual cached and reconstructed wheels used for this offline rebuild. Python 3.12.3 is required for hf, llamacpp and uvtool; vllm requires
3.12.14. Record installation provenance separately without credentials.

`python3 scripts/sftdpo_runtime.py check --lock
sft_dpo_inventory/migration_execution_20261028/runtime/observed_packages.json`
checks interpreter and distribution versions after rebuilding. A successful
check is necessary but not sufficient: inspect console-script shebangs, Python
interpreter targets, native library links and package imports as well. CPU-only
checks do not establish GPU behavior or model equivalence.

The environments were rebuilt offline from the pip HTTP cache. Sixteen HF
CUDA distributions absent from that cache were reconstructed from the copied
environment's RECORD-verified installed files; the reconstructed wheel is not
the original wheel. The `*_wheels.json` records identify cached wheels, source
file hashes and reconstructed wheel hashes. `environment_validation.json`
records version comparison, CPU imports, pip checks, and a file-access trace.
No model, GPU, or full-job execution is covered by those checks. The original
copied environment directories remain preserved separately.

`python3 scripts/sftdpo_runtime.py scan FILE...` identifies old absolute paths
in the explicitly supplied files. It does not discover transitive imports, shell
scripts, dynamically constructed paths or queued JSON commands. For each future
job, audit its entire execution closure, including scheduler, server, client,
configuration and job manifest, before it is eligible to run. Historical files
and logs remain unchanged. The historical scheduler12 and its original helpers
retain their old paths. The new `gpu_data/scheduler12.py` uses the relocated
runtime. A version match alone does not establish a complete execution closure.

`scripts/render_sftdpo_runtime.py` generated sibling execution snapshots and
`render_manifest.json` records both source and generated hashes plus the
replacement rules. The copied job manifests are historical examples, not new
authorization to repeat their jobs. Scheduler12's existing `--dry-run` still
examines GPU and Ollama state and writes a PID, so do not treat it as an
offline or side-effect-free verification. The new server scripts select their
GPU guard from the same pinned worktree. Inputs and record locations remain in
their original repository directories. The sibling snapshots must be included
in a commit before using a worktree pinned to that commit.

The scheduler and server guard scripts load executable helpers from the pinned
worktree; input builders and utilization reports use the original main-checkout
input and timeline directories. `make_jobs_rerun10.py` reads the existing
`gpu/cell_seeds_S.json` for inspection. Its `--apply` option is disabled in the
snapshot to protect both historical files and pinned execution code. Prepare a
new job table separately before committing and pinning a worktree. Job and
config generators write snapshot files: run them before committing and pinning
the worktree, never in an active pinned worktree. `path_validation.json` records
the CPU-only hash, syntax, input, timeline, helper and command checks.

The environments have been built and checked as recorded above. Creating these
snapshots does not authorize rerunning historical jobs or starting a GPU job;
new jobs must be prepared, committed, and pinned before any separately
authorized execution.

The CPU-only native quantizer is
`/data/hwkim/sftdpo_work/runtime/native/llama.cpp-b11434/build/bin/llama-quantize`.
Its source commit, build configuration, binary hash and library resolution are
in `native_build.json`. The executable prints usage with exit 1 for the tested
help/version invocations; model loading and quantization were not tested.
HTTPS support is disabled because OpenSSL development headers were unavailable.

`old_home_absence_validation.json` records successful imports and `pip check`
for all four environments with `/home/hwkim/sftdpo_work` absent, plus an HF
training `--dry-run` using the new V4 config. This command reads the training
records and schedule only; it does not load a model or start GPU training.
