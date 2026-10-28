"""CPU-only migration inventory checks; fixtures contain no project data."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
import json
import gzip
import subprocess
import sys


SPEC = importlib.util.spec_from_file_location("migration_inventory", Path(__file__).resolve().parents[1] / "scripts/build_migration_inventory.py")
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


class InventoryTests(unittest.TestCase):
    def test_nested_git_empty_directories_and_dangling_links_are_listed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "home"
            (root / ".git").mkdir(parents=True)
            (root / ".git/config").write_text("fixture")
            (root / "empty").mkdir()
            (root / "dangling").symlink_to("absent")
            errors = []
            rows = M.enumerate_tree(root, "home", Path(tmp) / "data", errors)
            self.assertFalse(errors)
            by_path = {r["relative_path"]: r for r in rows}
            self.assertEqual(set(by_path), {"", ".git", ".git/config", "empty", "dangling"})
            self.assertEqual(by_path["dangling"]["type"], "symlink")
            self.assertFalse(by_path["dangling"]["link_target_exists_before"])

    def test_protected_files_and_hardlink_aliases_never_enter_hash_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            import os
            import sqlite3
            root = Path(tmp)
            (root / "protected_final_v2").mkdir()
            secret = root / "protected_final_v2/gold.yaml"
            secret.write_text("fixture only")
            os.link(secret, root / "alias.txt")
            rows = M.enumerate_tree(root, "home", root / "dest", [])
            protected = {(r["device"], r["inode"]) for r in rows if r["relative_path"] == "protected_final_v2/gold.yaml"}
            cache = sqlite3.connect(":memory:")
            # No hashes table: even attempting a lookup would fail this test.
            for r in rows:
                if r["type"] == "file":
                    M.file_hashes(r, cache, protected)
                    self.assertEqual(r["hash_status"], "protected_metadata_only")
                    self.assertNotIn("sha256", r)
            self.assertEqual(next(r for r in rows if r["relative_path"] == "alias.txt")["category"], "protected_hardlink_alias")

    def test_collision_types_content_and_permissions_are_distinguished(self):
        base = {"type": "file", "hash_status": "verified_at_scan", "size_bytes": 1, "sha256": "a", "mode": "0o600", "uid": 1, "gid": 1}
        self.assertEqual(M.collision_status([base, dict(base)]), "identical_file")
        self.assertEqual(M.collision_status([base, dict(base, sha256="b")]), "different_file_conflict")
        self.assertEqual(M.collision_status([base, dict(base, mode="0o644")]), "identical_file_metadata_diff")
        self.assertEqual(M.collision_status([base, dict(base, type="directory")]), "type_conflict")

    def test_training_records_and_checkpoint_state_are_separated(self):
        self.assertEqual(M.classify("pilot_010/train/checkpoint-1/trainer_state.json", "file")[0], "git_run_record")
        self.assertEqual(M.classify("pilot_010/train/checkpoint-1/optimizer.pt", "file")[0], "external_checkpoint_state")
        self.assertEqual(M.classify("training/generated/pilot_006/self_2d/raw/a.jsonl", "file", repo=True)[0], "git_training_data_candidate")
        self.assertEqual(M.classify("training/generated/pilot_006/cells_raw/a.jsonl", "file", repo=True)[0], "external_evaluation_raw")
        self.assertEqual(M.classify("training/generated/pilot_006_prep/raw/a.jsonl", "file", repo=True)[0], "pending_classification")

    def test_protected_path_is_blocked_even_without_inode_registration(self):
        with tempfile.TemporaryDirectory() as tmp:
            import sqlite3
            root = Path(tmp)
            (root / "protected_final_v2").mkdir()
            (root / "protected_final_v2/gold.yaml").write_text("fixture only")
            row = next(r for r in M.enumerate_tree(root, "repo", root, []) if r["type"] == "file")
            M.file_hashes(row, sqlite3.connect(":memory:"), set())
            self.assertEqual(row["hash_status"], "protected_metadata_only")

    def test_nested_git_and_symlink_are_not_git_record_candidates(self):
        self.assertEqual(M.classify("unusual/.git/config.json", "file")[0], "external_git_metadata")
        self.assertEqual(M.classify("some_record.json", "symlink")[0], "external_link")
        self.assertEqual(M.classify("hfvenv", "directory")[2], "rebuild")

    def test_relative_link_chain_detects_old_home_and_rewrite(self):
        def link(path, target, recommended=None):
            return {"type": "symlink", "link_target": target, "link_recommended_target": recommended or target,
                    "mode": "0o777", "uid": 1, "gid": 1}
        tree = {"/data/work": [{"type": "directory"}], "/data/work/first": [link("first", "second")],
                "/data/work/second": [link("second", "/home/work/file", "/data/work/file")],
                "/data/work/file": [{"type": "file"}]}
        before = M.projected_link_target("/data/work/first", tree, Path("/data/work"), Path("/home/work"))
        after = M.projected_link_target("/data/work/first", tree, Path("/data/work"), Path("/home/work"), rewrite=True)
        self.assertEqual(before["status"], "uses_old_home")
        self.assertEqual(after["status"], "exists_in_union")

    def test_symlink_precedes_dotdot_and_external_alias_detects_home(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            outside = root / "outside"
            (outside / "dir").mkdir(parents=True)
            (outside / "weights").write_text("fixture")
            canonical, old = root / "data", root / "home"
            (outside / "alias_home").symlink_to(old)
            def link(target):
                return {"type": "symlink", "link_target": target, "link_recommended_target": target}
            tree = {str(canonical): [{"type": "directory"}],
                    str(canonical / "link"): [link("dir_alias/../weights")],
                    str(canonical / "dir_alias"): [link(str(outside / "dir"))],
                    str(canonical / "weights"): [{"type": "file"}],
                    str(canonical / "home_alias"): [link(str(outside / "alias_home"))]}
            result = M.projected_link_target(str(canonical / "link"), tree, canonical, old)
            self.assertEqual(result["status"], "outside_root_existing")
            self.assertEqual(result["resolved"], str(outside / "weights"))
            self.assertEqual(M.projected_link_target(str(canonical / "home_alias"), tree, canonical, old)["status"], "uses_old_home")

    def test_git_archive_planned_file_ancestor_conflict_and_unverified_hashes(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            rows = [{"git_archive_path": p, "source_path": "/fixture/" + str(i), "hash_status": "pending"}
                    for i, p in enumerate(("new", "new/file.json", "duplicate", "duplicate"))]
            issues = M.archive_destinations(rows, repo)
            self.assertTrue(any(r["status"] == "planned_file_ancestor_conflict" for r in issues))
            self.assertTrue(any(r["status"] == "multiple_sources_hash_unverified" for r in issues))

    def test_git_archive_existing_protected_hardlink_is_not_hashed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "existing.json"
            target.write_text("fixture")
            s = target.stat()
            row = {"git_archive_path": "existing.json", "source_path": "/fixture/source"}
            result = M.archive_destinations([row], root, {(s.st_dev, s.st_ino)})
            self.assertEqual(result[0]["status"], "existing_protected_alias_unverified")

    def test_evaluation_raw_has_priority_over_self_named_children(self):
        self.assertEqual(M.classify("training/generated/pilot_006/cells_raw/self/a.jsonl", "file", repo=True)[0], "external_evaluation_raw")

    def test_archive_uses_repo_argument_and_rejects_symlink_ancestor(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "repo"
            repo.mkdir()
            (repo / "archive").symlink_to(root, target_is_directory=True)
            row = {"git_archive_path": "archive/run.json", "source_path": str(root / "src")}
            issues = M.archive_destinations([row], repo)
            self.assertEqual(issues[0]["status"], "ancestor_not_directory_or_link")

    def test_same_inode_cache_is_not_reused_in_a_different_scan(self):
        with tempfile.TemporaryDirectory() as tmp:
            import sqlite3
            root = Path(tmp)
            (root / "file.txt").write_text("fixture")
            cache = sqlite3.connect(":memory:")
            cache.execute("create table hashes (signature text primary key, sha256 text, blob_sha1 text)")
            row = next(r for r in M.enumerate_tree(root, "home", root, []) if r["type"] == "file")
            for scan in ("scan1", "scan2"):
                M.file_hashes(row, cache, set(), scan)
                self.assertEqual(row["hash_read"], "fresh_bytes")

    def test_full_cli_inventory_includes_repository_protection_and_collisions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home, data, repo, out = [root / p for p in ("home", "data", "repo", "out")]
            for p in (home, data, repo):
                p.mkdir()
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            (repo / "tracked.txt").write_text("fixture")
            subprocess.run(["git", "-C", str(repo), "add", "tracked.txt"], check=True)
            subprocess.run(["git", "-C", str(repo), "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                            "commit", "-qm", "fixture"], check=True)
            (home / "collision.json").write_text("one")
            (data / "collision.json").write_text("two")
            protected = repo / "training/generated/protected_final_v2"
            protected.mkdir(parents=True)
            (protected / "gold.yaml").write_text("fixture only")
            (repo / "training/generated/mystery.bin").write_text("fixture")
            import os
            os.link(protected / "gold.yaml", home / "alias.txt")
            subprocess.run([sys.executable, str(Path(M.__file__)), "--home-root", str(home), "--data-root", str(data),
                            "--repo", str(repo), "--output", str(out), "--cache", str(root / "cache.sqlite")],
                           check=True, capture_output=True, text=True)
            summary = json.loads((out / "summary.json").read_text())
            self.assertEqual(summary["source_changes"], 0)
            self.assertEqual(summary["scan_errors"], 0)
            self.assertEqual(sum(v for k, v in summary["overlap_status"].items() if k.startswith("different_file_conflict")), 1)
            with gzip.open(out / "external_entries.jsonl.gz", "rt") as f:
                alias = next(json.loads(line) for line in f if json.loads(line)["relative_path"] == "alias.txt")
            self.assertEqual(alias["hash_status"], "protected_metadata_only")
            self.assertIsNone(alias["git_archive_path"])
            with gzip.open(out / "repository_entries.jsonl.gz", "rt") as f:
                repository_rows = [json.loads(line) for line in f]
                gold = next(r for r in repository_rows if r["relative_path"].endswith("gold.yaml"))
            self.assertEqual(gold["hash_status"], "protected_metadata_only")
            mystery = next(r for r in repository_rows if r["relative_path"].endswith("mystery.bin"))
            self.assertEqual(mystery["category"], "pending_classification")
            self.assertEqual(mystery["git_index_identical_paths"], ["tracked.txt"])


if __name__ == "__main__":
    unittest.main()
