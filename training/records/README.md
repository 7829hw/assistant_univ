# Committed training evidence

This directory contains deliberate, small text snapshots from ignored local artifacts. The original `training/experiments/`, `training/annotations/generated/`, datasets, model caches and checkpoints remain ignored and unchanged. `snapshot_manifest.json` maps each selected source file to its committed copy, byte count and SHA256. No ignored path was force-added.

Local `.gitattributes` preserves snapshot bytes on checkout. The historical learning-curve CSV retains its original CRLF row endings.

- `pilots/`: bounded Thor pilot 001/002 reports, selected configurations, generation records, preference/profiling results and provenance. Pilot 001 narrative is [PILOT_REPORT.md](../PILOT_REPORT.md); pilot 002 narrative is [REPORT.md](pilots/thor_pilot_002/REPORT.md). Dev/validation/diagnostic predictions remain protected evidence; they are not training pairs.
- `corpora/`: v001/v002 historical approval audits and the [reviewed v003 extension](corpora/reviewed_gold_v003/README.md), coverage, policies and dataset/config hashes. Generated chat training JSONL and weights are deliberately absent. V003 includes a compact dataset index for exact CPU-only export reconstruction without creating approvals.
- `reviews/`: finalized batch 001/002 evidence and batch 003 text views, preserved semantic draft and final `decisions_003.jsonl`. Explicit user policy accepted 30 records; 2 stay hold and 2 diagnostic-only. The original queue remains pending and recommendations alone do not change status. Local XLSX views are omitted because they are ignored binary review artifacts.
- `validation/`: [v003 token/memory gate](../THOR_V003_TOKEN_VALIDATION.md), disposable LR0 Thor SFT/DPO proofs, unchanged-policy/reference hashes and new pilot003 profile hashes. These probes are memory tests; pilot003 quality training has not started.

These copies are **read-only evidence**, not a second operational review queue. Inner manifests retain their original paths/hashes (including references to omitted local files). A fresh clone does not contain prior local pilot inputs or adapters and cannot rerun the exact pilots from reports alone. V003 dataset exports can be reconstructed from its compact index under the same prompt hash; this does not imply a trained adapter or a runnable GPU environment. Do not reinterpret an unavailable source as an approval, unsupported label, or export permission.

V003 preserves v002 assignments and applies batch 003's pre-review family splits/dependencies explicitly; the generic standalone importer does not carry v002 forward or honor that sidecar automatically. Older 6912 pilot limits do not fit seven approved records. New pilot003 profiles passed the subsequent Thor memory gate at total7040/prompt6816/completion256; frozen v003 corpus evidence remains unchanged. All seven records remain in the reviewed corpus.

`COMMIT_VALIDATION.md` records the tests and artifact/hash checks performed before this work was committed. Existing smoke/pilot measurements are historical; no new GPU training was run during branch creation or commit preparation.
