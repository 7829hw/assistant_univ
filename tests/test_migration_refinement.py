"""Producer-review overrides preserve the captured physical file evidence."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from refine_migration_inventory import refine


class RefinementTests(unittest.TestCase):
    def row(self, **changes):
        row = {"type": "file", "source_root": "repo", "relative_path": "training/generated/batch006/raw/sample.jsonl",
               "source_path": "/fixture/sample.jsonl", "category": "external_evaluation_raw", "hash_status": "verified_at_scan",
               "sha256": "fixture-hash", "size_bytes": 10, "mtime_ns": 123, "destination_path": "/fixture/sample.jsonl",
               "git_index_identical_paths": []}
        row.update(changes)
        return row

    def rule(self):
        return {"root": "repo", "prefix": "training/generated/batch006/raw", "category": "git_training_review_record",
                "basis": "fixture producer", "runtime": "none"}

    def test_review_changes_only_disposition(self):
        row = self.row()
        original = copy.deepcopy(row)
        result = refine([row], [self.rule()])
        self.assertEqual(len(result), 1)
        self.assertEqual(row["category"], "git_training_review_record")
        for key in ("sha256", "size_bytes", "mtime_ns", "destination_path", "source_path"):
            self.assertEqual(row[key], original[key])

    def test_protected_and_similarly_named_prefixes_are_not_changed(self):
        rows = [self.row(hash_status="protected_metadata_only"),
                self.row(relative_path="training/generated/batch006/raw_other/sample.jsonl")]
        original = copy.deepcopy(rows)
        self.assertEqual(refine(rows, [self.rule()]), [])
        self.assertEqual(rows, original)

    def test_changed_hash_never_becomes_verified_git_coverage(self):
        row = self.row(hash_status="error_or_changed")
        refine([row], [self.rule()])
        self.assertEqual(row["git_coverage"], "unverified_source_hash")
        self.assertEqual(row["git_disposition"], "unverified_do_not_import")


if __name__ == "__main__":
    unittest.main()
