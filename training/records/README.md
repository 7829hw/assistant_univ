# Committed training evidence

This directory contains deliberate, small text snapshots from ignored local artifacts. The original `training/experiments/`, `training/annotations/generated/`, datasets, model caches and checkpoints remain ignored and unchanged. `snapshot_manifest.json` maps each selected source file to its committed copy, byte count and SHA256. No ignored path was force-added.

Local `.gitattributes` preserves snapshot bytes on checkout. The historical learning-curve CSV retains its original CRLF row endings.

- `pilots/`: bounded Thor pilot 001/002 reports, selected configurations, generation records, preference/profiling results and provenance. Pilot 001 narrative is [PILOT_REPORT.md](../PILOT_REPORT.md); pilot 002 narrative is [REPORT.md](pilots/thor_pilot_002/REPORT.md). Dev/validation/diagnostic predictions remain protected evidence; they are not training pairs.
- `corpora/`: v001/v002 approval audits, compact reviewed annotations, coverage, policies and dataset/config hashes. Generated chat training JSONL and weights are deliberately absent. The annotations alone are not a ready-to-train export; approved pairs, existing split assignments and protection checks must also be preserved.
- `reviews/`: finalized batch 001/002 evidence and pending batch 003 text views. Batch 003 has **zero approvals** and no `decisions.jsonl`; recommendations do not change status. Local XLSX views are omitted because they are ignored binary review artifacts.

These copies are **read-only historical evidence**, not a second operational corpus or an `import-reviewed` queue. Inner manifests retain their original paths/hashes (including references to omitted local files). A fresh clone does not contain those local inputs or adapters and cannot rerun the exact pilots from reports alone. Do not reinterpret an unavailable source as an approval, unsupported label, or export permission.

The batch 003 planned family splits/dependencies must be explicitly applied when assembling a future reviewed v003; the generic standalone importer does not carry v002 forward or honor that sidecar automatically. Current pilot token limits do not fit seven pending candidates; the proposed larger token limits need a future memory smoke check after human review.

`COMMIT_VALIDATION.md` records the tests and artifact/hash checks performed before this work was committed. Existing smoke/pilot measurements are historical; no new GPU training was run during branch creation or commit preparation.
