#!/usr/bin/env python3
"""Apply documented disposition reviews to an immutable physical scan.

This reads only generated inventory metadata, never the original data. Existing
source sizes, hashes, timestamps and physical destinations stay unchanged.
"""
from collections import Counter
import csv
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import argparse
import subprocess

import build_migration_inventory as inventory

POLICY_FIELDS = {"category", "classification_basis", "runtime_requirement", "git_archive_path",
                 "classification_before_document_review", "git_index_identical_paths", "git_coverage", "git_disposition",
                 "git_archive_destination_status", "git_archive_path_ignored"}


def physical_evidence(row):
    return json.dumps({k: v for k, v in row.items() if k not in POLICY_FIELDS}, sort_keys=True)


def read_rows(path):
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        return [json.loads(line) for line in stream]


def refine(rows, rules):
    changes = []
    for row in rows:
        if row["type"] != "file" or row["hash_status"] == "protected_metadata_only":
            continue
        for rule in rules:
            rel = row["relative_path"]
            if row["source_root"] != rule["root"] or not (rel == rule["prefix"] or rel.startswith(rule["prefix"] + "/")):
                continue
            if row["category"] == rule["category"] and row["classification_basis"] == rule["basis"]:
                break
            changes.append({"source": row["source_path"], "old_category": row["category"], "new_category": rule["category"], "basis": rule["basis"]})
            row.setdefault("classification_before_document_review", row["category"])
            row.update(category=rule["category"], classification_basis=rule["basis"], runtime_requirement=rule["runtime"],
                       git_archive_path=inventory.git_archive_path(row["source_root"], rel, rule["category"]))
            if row["git_archive_path"]:
                same_path = row["source_root"] == "repo" and rel in row.get("git_index_identical_paths", [])
                verified = row["hash_status"] == "verified_at_scan"
                row["git_coverage"] = ("unverified_source_hash" if not verified else "index_same_path_and_bytes" if same_path
                                       else "index_identical_elsewhere" if row.get("git_index_identical_paths") else "no_identical_index_blob")
                row["git_disposition"] = "preserve_training_or_run_record" if verified else "unverified_do_not_import"
            else:
                for key in ("git_coverage", "git_disposition", "git_archive_path_ignored", "git_archive_destination_status"):
                    row.pop(key, None)
            break
    return changes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--review-revision", type=int, default=1)
    args = parser.parse_args()
    d = args.directory
    summary = json.loads((d / "summary.json").read_text())
    previous_review = summary.get("classification_review")
    previous_revision = previous_review.get("revision", 1) if previous_review else 0
    if args.review_revision <= previous_revision:
        raise RuntimeError("review revision must increase; previous evidence and classification history are preserved")
    if subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=args.repo).decode().strip() != summary["repo_head"]:
        raise RuntimeError("HEAD changed since the physical scan; review coverage before refinement")
    external = read_rows(d / "external_entries.jsonl.gz")
    repository = read_rows(d / "repository_entries.jsonl.gz")
    rules = json.loads((d / "classification_review.json").read_text())["rules"]
    all_rows = external + repository
    current_index = inventory.load_index(args.repo)
    for row in all_rows:
        if row["type"] == "file":
            row["git_index_identical_paths"] = current_index.get(row.get("git_blob_sha1"), []) if row["hash_status"] == "verified_at_scan" else []
    before = {r["source_path"]: physical_evidence(r) for r in all_rows}
    changes = refine(all_rows, rules)
    candidates = [r for r in all_rows if r.get("git_archive_path") and r["type"] == "file"]
    # Proposed archives do not exist for new external records. Repository sources
    # are already their own archive paths, so no source or protected data is read.
    for row in candidates:
        if row["source_root"] == "repo":
            row["git_archive_destination_status"] = "existing_source_in_working_tree"
        verified = row["hash_status"] == "verified_at_scan"
        same_path = row["source_root"] == "repo" and row["relative_path"] in row.get("git_index_identical_paths", [])
        row["git_coverage"] = ("unverified_source_hash" if not verified else "index_same_path_and_bytes" if same_path
                               else "index_identical_elsewhere" if row.get("git_index_identical_paths") else "no_identical_index_blob")
    paths = [r["git_archive_path"] for r in candidates]
    ignored = subprocess.run(["git", "check-ignore", "--no-index", "-z", "--stdin"], cwd=args.repo,
                             input=("\0".join(paths) + "\0").encode(), capture_output=True)
    if ignored.returncode not in (0, 1):
        raise RuntimeError(ignored.stderr.decode())
    ignored_paths = {p.decode() for p in ignored.stdout.split(b"\0") if p}
    for row in candidates:
        row["git_archive_path_ignored"] = row["git_archive_path"] in ignored_paths
    assert before == {r["source_path"]: physical_evidence(r) for r in all_rows}
    if dict(current_index) != dict(inventory.load_index(args.repo)):
        raise RuntimeError("Git index changed during classification refinement")
    inventory.write_jsonl_gz(d / "external_entries.jsonl.gz", external)
    inventory.write_jsonl_gz(d / "repository_entries.jsonl.gz", repository)
    inventory.write_jsonl_gz(d / "git_candidates.jsonl.gz", candidates)
    if previous_review:
        (d / f"classification_changes_r{previous_revision}.json").write_bytes((d / "classification_changes.json").read_bytes())
        summary.setdefault("classification_review_history", []).append(previous_review)
    inventory.write_json(d / "classification_changes.json", changes)
    summary["external_categories"] = dict(Counter(r["category"] for r in external))
    summary["repo_generated_categories"] = dict(Counter(r["category"] for r in repository if r["type"] == "file"))
    summary["git_candidates"] = {"files": len(candidates), "logical_bytes": sum(r["size_bytes"] for r in candidates),
                                 "no_identical_index_blob": sum(r.get("git_coverage") == "no_identical_index_blob" for r in candidates),
                                 "ignored_proposed_archive_paths": sum(r["git_archive_path_ignored"] for r in candidates),
                                 "at_least_100_mib": sum(r["size_bytes"] >= 100 * 1024**2 for r in candidates)}
    summary["classification_review"] = {"updated_utc": datetime.now(timezone.utc).isoformat(), "revision": args.review_revision,
                                        "files_refined": sum("classification_before_document_review" in r for r in all_rows),
                                        "files_refined_this_revision": len(changes),
                                        "rules": "classification_review.json", "physical_metadata_and_hashes_unchanged": True,
                                        "git_index_coverage_recomputed": True,
                                        "generator_sha256": hashlib.sha256(Path(inventory.__file__).read_bytes()).hexdigest(),
                                        "refinement_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    inventory.write_json(d / "summary.json", summary)
    groups = {}
    for row in external:
        key = (row["source_root"], row["relative_path"].split("/")[0] or ".")
        g = groups.setdefault(key, {"entries": 0, "files": 0, "logical_bytes": 0, "allocated_bytes": 0})
        g["entries"] += 1
        if row["type"] == "file":
            g["files"] += 1
            g["logical_bytes"] += row["size_bytes"]
            g["allocated_bytes"] += row["allocated_bytes"]
    with (d / "groups.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["source_root", "group", "entries", "files", "logical_bytes", "allocated_bytes"])
        for (root, group), counts in sorted(groups.items()):
            writer.writerow([root, group, *counts.values()])
    with (d / "actions.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["source", "external_destination", "category", "git_archive_path", "git_coverage", "ignored", "runtime_requirement", "basis"])
        for r in all_rows:
            if r["type"] == "file" and (r.get("git_archive_path") or r["category"] == "pending_classification"):
                writer.writerow([r["source_path"], r["destination_path"], r["category"], r.get("git_archive_path"),
                                 r.get("git_coverage"), r.get("git_archive_path_ignored"), r["runtime_requirement"], r["classification_basis"]])
    artifacts = {p.name: {"bytes": p.stat().st_size, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
                 for p in sorted(d.iterdir()) if p.is_file() and p.name not in {"artifacts.json", "README.md", "REVIEW.md"}}
    inventory.write_json(d / "artifacts.json", artifacts)
    print(json.dumps({"files_refined": len(changes), "git_candidates": summary["git_candidates"]}))


if __name__ == "__main__":
    main()
