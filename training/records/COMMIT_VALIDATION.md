# Branch and commit preparation — 2026-10-05 (Asia/Seoul)

Base: `geoflow/dev-v2` at `65e9ea2ec98f8cec289cbb753ce543dee3efdd92`.
Work branch: `geoflow/sft-dpo-thor`; created at the same HEAD without stash, merge,
rebase, history rewrite, push or deletion of existing artifacts.

Before switching branches, SHA256 was recorded for 1,659 tracked/nonignored files,
and size/mtime for 14,378 local training artifact files. All matched after switching.
The inherited evaluator metrics and aggregation serialization helper are included;
planner prompt/schema, MacroComposer and Validator inference responsibilities are
unchanged. AGENTS.md and training README document the requested follow-up commit policy.

## Verification

- `/tmp/geoflow-training-venv/bin/python -m unittest discover -s tests -q`:
  **1,154 tests, OK (skipped=2, expected failures=1)**, 65.394 seconds with local
  socket access. The first sandboxed run had one localhost HTTPServer permission
  error; the unrestricted rerun passed without code or test changes. An existing
  socket ResourceWarning was emitted but did not fail the test.
- Training modules (data/trainers/evaluation/Thor/pilot/annotations/review_batch):
  **96 tests, OK (skipped=2)**. These are a subset of the full suite.
- Local batch 003 artifact checks: **15 tests, OK**. All 34 candidates remain pending;
  no v003 decisions, corpus import, model inference or GPU training was performed.
- Thor SFT/DPO profile `--dry-run` passed, using the original seed corpus paths:
  SFT12/3, DPO82/24, unchanged production prompt SHA256
  `522aa3b1716248b53a755ee1b236e7aef302c85504e9cfac3825f4d3cc817945`.
  These generic-profile checks do not replace the frozen v002 split of12/5 and16/4.
- Python AST parsing, source/snapshot SHA256 comparisons, credential-pattern and
  file-size/exclusion checks passed. Selected evidence consists of94 files,
  5,722,866 bytes, each byte-identical to its ignored source at capture time.
- Working and staged diff checks are performed before commit. No force-add of
  ignored files is used.

## Intentional exclusions

`training/generated/`, original `training/experiments/`,
`training/annotations/generated/`, `training/checkpoints/`, `training/runs/`,
Python/virtualenv caches, all XLSX views, model/adapter weights, optimizer/scheduler
checkpoints, raw telemetry/logs and temporary files remain outside the commit.
They are retained locally. `training/records/` is a read-only selected text archive,
not a duplicate operational dataset or live review/import directory. Historical
paths/hashes are not rewritten, and missing local models cannot be reconstructed
from these reports alone.
