#!/usr/bin/env python3
"""Inventory a proposed consolidation; never move or edit source files.

All filesystem entries, including nested .git directories and environments, are
listed without following symlinks. Protected final sets are metadata-only.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import sqlite3
import stat
import subprocess
import time
from datetime import datetime, timezone


ENVIRONMENTS = {"hfvenv", "vllmvenv", "llamacpp_venv", "uvtool", "uv-python"}
DEPENDENCIES = {"hf-cache", "llama.cpp-b11434", "cuda_link"}
MODEL_SUPPORT = {"config.json", "adapter_config.json", "tokenizer.json", "tokenizer_config.json",
                 "special_tokens_map.json", "added_tokens.json", "generation_config.json",
                 "model.safetensors.index.json", "chat_template.jinja", "vocab.json", "merges.txt", "README.md"}
CHECKPOINT_STATE = {"optimizer.pt", "scheduler.pt", "rng_state.pth", "training_args.bin"}
FILE_TYPES = ((stat.S_ISREG, "file"), (stat.S_ISDIR, "directory"), (stat.S_ISLNK, "symlink"),
              (stat.S_ISSOCK, "socket"), (stat.S_ISFIFO, "fifo"), (stat.S_ISCHR, "char_device"),
              (stat.S_ISBLK, "block_device"))


def signature(s):
    return (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_mode)


def sealed(parts):
    return any(p.startswith("protected_final") for p in parts)


def classify(relative, kind, repo=False):
    """Return a disposition, explanation, and runtime requirement, not approval."""
    p = Path(relative)
    parts, name = p.parts, p.name
    top = parts[0] if parts else ""
    if sealed(parts):
        return "protected_metadata_only", "existing final-set access restriction; not a privacy classification", "preserve_permissions"
    if top in ENVIRONMENTS:
        return "external_environment", "preserve old environment; create a new environment for execution", "rebuild"
    if top in DEPENDENCIES:
        return "external_dependency", "model cache or third-party build/source, including nested Git metadata", "rebuild" if top == "llama.cpp-b11434" else "check_links"
    if top == "worktrees":
        return "external_worktree", "Git worktree registration depends on the original location", "recreate_worktree"
    if ".git" in parts:
        return "external_git_metadata", "preserve nested repository objects, references and configuration", "check_git_registration"
    if kind == "directory":
        return "directory_metadata", "preserve directory and permission metadata", "none"
    if kind not in {"file", "symlink"}:
        return "runtime_special", "special node needs an explicit recreation decision", "recreate_if_needed"
    if kind == "symlink":
        return "external_link", "link object, not approval to archive its target as data", "check_links"
    if repo and parts[:3] == ("evaluation", "real_data", "records"):
        return "git_real_data", "original real-data records are Git-preserved under decision 256", "none"
    if "__pycache__" in parts or p.suffix in {".pyc", ".pyo", ".pid"} or top == "pids":
        return "external_temporary", "recreatable interpreter/process state", "do_not_reuse_pid"
    if name in CHECKPOINT_STATE or name.startswith("rng_state_"):
        return "external_checkpoint_state", "binary optimizer/scheduler/RNG/training-arguments state", "preserve_bytes"
    if p.suffix in {".safetensors", ".gguf", ".ckpt"}:
        return "external_weights", "model/adapter/merged/quantized weights", "preserve_bytes"
    if name == "trainer_state.json" or name == "training_provenance.json" or name.endswith("_profile.json"):
        return "git_run_record", "training state, resolved provenance, or profile", "none"
    if name in MODEL_SUPPORT and ("merged" in parts or any(x.startswith("checkpoint-") for x in parts)
                                  or any(x.startswith("train") for x in parts) or "davg" in parts):
        return "external_model_support", "tokenizer/model distribution support, not training examples", "preserve_bytes"
    if p.suffix == ".bin" and "scores" in parts:
        return "external_evaluation_artifact", "binary evaluation scores; existing diagnostic storage policy", "preserve_bytes"
    if p.suffix in {".pt", ".pth", ".bin"}:
        return "pending_classification", "binary role needs provenance confirmation", "manual_review"
    if repo:
        if any(x in {"cells_raw", "latency_raw", "post_cells_raw"} for x in parts):
            return "external_evaluation_raw", "explicit evaluation-raw exclusion; no training approval implied", "preserve_bytes"
        if any(x in {"self", "self_full", "self_partial", "self_2b", "self_2c", "self_2d", "thinking_traces"}
               or x.startswith("teacher") for x in parts) or "combined_traces" in name:
            return "git_training_data_candidate", "training trace path; confirm producer; latest user instruction overrides old raw-training exclusion", "producer_review"
        if "realtrip_vllm" in parts:
            return "pending_classification", "collection role must be checked against its producer", "manual_review"
        if "raw" in parts:
            if any(x in {"calibration_001", "quant_recipe", "batch006", "serving_vllm", "serving_vllm_fp8", "pilot_003_followup"}
                   for x in parts):
                return "external_evaluation_raw", "named diagnostic/evaluation raw storage", "preserve_bytes"
            return "pending_classification", "raw alone does not prove training versus evaluation use", "manual_review"
        return "pending_classification", "generated file role requires producer or existing tracking evidence", "manual_review"
    if top == "fix_hoist_rerun":
        return "git_historical_evaluation_candidate", "historical pre-fix evidence; confirm evaluation-raw exception before import", "producer_review"
    if p.suffix in {".jsonl", ".txt"} and top == "logprob_diag":
        return "external_evaluation_artifact", "derived diagnostic token sequences", "preserve_bytes"
    if p.suffix in {".log", ".out", ".txt", ".json", ".yaml", ".yml", ".md", ".py", ".sh", ".csv", ".jsonl"}:
        return "git_run_record_candidate", "possible experiment record; producer and evaluation exclusion review required", "producer_review"
    return "pending_classification", "unrecognized role; retain bytes and review", "manual_review"


def git_archive_path(label, relative, category):
    if not category.startswith("git_"):
        return None
    p = Path(relative)
    if label == "repo":
        return relative
    parts = p.parts
    run = parts[0] if parts and (parts[0].startswith("pilot_") or parts[0] == "pipeline_pilot_001") else "external_misc"
    tail = Path(*parts[1:]) if run != "external_misc" else p
    return str(Path("sft_dpo_inventory") / run / "train_logs" / "migration_20261028" / label / tail)


def enumerate_tree(root, label, destination_root, errors, old_home_root=None):
    old_home_root = old_home_root or (root if label == "home" else Path("/home/hwkim/sftdpo_work"))
    rows, todo = [], [root]
    while todo:
        path = todo.pop()
        try:
            s = path.lstat()
        except OSError as exc:
            errors.append({"phase": "lstat", "path": str(path), "error": str(exc)})
            continue
        relative = str(path.relative_to(root)) if path != root else ""
        kind = next((name for test, name in FILE_TYPES if test(s.st_mode)), "unknown")
        cat, why, runtime = classify(relative, kind)
        row = {"source_root": label, "relative_path": relative, "source_path": str(path), "type": kind,
               "size_bytes": s.st_size, "allocated_bytes": s.st_blocks * 512, "mode": oct(stat.S_IMODE(s.st_mode)),
               "uid": s.st_uid, "gid": s.st_gid, "mtime_ns": s.st_mtime_ns, "ctime_ns": s.st_ctime_ns,
               "device": s.st_dev, "inode": s.st_ino, "nlink": s.st_nlink, "category": cat,
               "rdev": s.st_rdev, "possibly_sparse": kind == "file" and s.st_blocks * 512 < s.st_size,
               "classification_basis": why, "runtime_requirement": runtime,
               "destination_path": str(destination_root / relative),
               "physical_action": "retain_at_destination" if label == "data" else "copy_verify_preserve_source",
               "git_archive_path": git_archive_path(label, relative, cat), "hash_status": "not_applicable",
               "_signature": signature(s)}
        try:
            attrs = os.listxattr(path, follow_symlinks=False)
            row["xattr_sha256"] = {name: hashlib.sha256(os.getxattr(path, name, follow_symlinks=False)).hexdigest()
                                   for name in attrs}
        except OSError as exc:
            row["xattr_error"] = str(exc)
            errors.append({"phase": "xattr", "path": str(path), "error": str(exc)})
        if kind == "symlink":
            try:
                target = os.readlink(path)
                row.update(link_target=target, link_target_absolute=os.path.isabs(target),
                           link_target_exists_before=os.path.exists(path),
                           link_resolved_before=os.path.realpath(path))
                row["link_uses_old_home"] = target == str(old_home_root) or target.startswith(str(old_home_root) + "/")
                row["link_recommended_target"] = target.replace(str(old_home_root), str(destination_root), 1) if row["link_uses_old_home"] else target
                row["link_action"] = "rebuild_environment_link" if runtime == "rebuild" else "rewrite_target_after_archive" if row["link_uses_old_home"] else "preserve_link"
            except OSError as exc:
                errors.append({"phase": "readlink", "path": str(path), "error": str(exc)})
        elif kind == "file":
            row["hash_status"] = "protected_metadata_only" if sealed(Path(relative).parts) else "pending"
        rows.append(row)
        if kind == "directory":
            try:
                fd = open_without_symlinks(path, directory=True)
                try:
                    if signature(os.fstat(fd)) != signature(s):
                        raise OSError("directory changed before enumeration")
                    with os.scandir(fd) as it:
                        children = [path / e.name for e in it]
                finally:
                    os.close(fd)
                todo.extend(sorted(children, reverse=True))
            except OSError as exc:
                errors.append({"phase": "scandir", "path": str(path), "error": str(exc)})
    return rows


def open_without_symlinks(path, directory=False):
    """Resolve each component with dirfd/O_NOFOLLOW, including the parents."""
    path = Path(os.path.abspath(path))
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for i, part in enumerate(path.parts[1:]):
            last = i == len(path.parts) - 2
            flags = os.O_RDONLY | os.O_NOFOLLOW
            if not last or directory:
                flags |= os.O_DIRECTORY
            child = os.open(part, flags, dir_fd=fd)
            os.close(fd)
            fd = child
        return fd
    except BaseException:
        os.close(fd)
        raise


def file_hashes(row, cache, protected_inodes, scan_id="fixture"):
    p = Path(row["source_path"])
    key = (row["device"], row["inode"])
    if sealed(Path(row["relative_path"]).parts) or key in protected_inodes:
        row["hash_status"] = "protected_metadata_only"
        if not sealed(Path(row["relative_path"]).parts):
            row["category"] = "protected_hardlink_alias"
            row["git_archive_path"] = None
        return
    sig = json.dumps([scan_id, row["_signature"]])
    try:
        if signature(p.lstat()) != tuple(row["_signature"]):
            raise RuntimeError("source metadata changed after enumeration")
        fd = open_without_symlinks(p)
        with os.fdopen(fd, "rb") as stream:
            if signature(os.fstat(stream.fileno())) != tuple(row["_signature"]):
                raise RuntimeError("source changed before open")
            old = cache.execute("select sha256, blob_sha1 from hashes where signature=?", (sig,)).fetchone()
            row["hash_read"] = "same_scan_hardlink_cache" if old else "fresh_bytes"
            if old:
                sha256, blob_sha1 = old
            else:
                h, blob = hashlib.sha256(), hashlib.sha1()
                blob.update(b"blob " + str(row["size_bytes"]).encode() + b"\0")
                while chunk := stream.read(8 * 1024 * 1024):
                    h.update(chunk)
                    blob.update(chunk)
                sha256, blob_sha1 = h.hexdigest(), blob.hexdigest()
                cache.execute("insert or replace into hashes values (?, ?, ?)", (sig, sha256, blob_sha1))
            if signature(os.fstat(stream.fileno())) != tuple(row["_signature"]):
                raise RuntimeError("source changed during hashing")
        if signature(p.lstat()) != tuple(row["_signature"]):
            raise RuntimeError("source metadata changed after hashing")
        row.update(sha256=sha256, git_blob_sha1=blob_sha1, hash_status="verified_at_scan")
    except (OSError, RuntimeError) as exc:
        row.update(hash_status="error_or_changed", hash_error=str(exc))


def collision_status(rows):
    if len(rows) == 1:
        return "unique"
    types = {r["type"] for r in rows}
    if len(types) != 1:
        return "type_conflict"
    kind = rows[0]["type"]
    if kind == "directory":
        content = "merge_directories"
    elif kind == "file":
        if any(r.get("hash_status") != "verified_at_scan" for r in rows):
            return "unverified_collision"
        content = "identical_file" if len({(r["size_bytes"], r["sha256"]) for r in rows}) == 1 else "different_file_conflict"
    elif kind == "symlink":
        content = "identical_link" if len({r.get("link_target") for r in rows}) == 1 else "different_link_conflict"
    else:
        return "special_node_conflict"
    if any(r.get("xattr_error") for r in rows):
        return content + "_metadata_unverified"
    metadata = {(r["mode"], r["uid"], r["gid"], r.get("mtime_ns"), json.dumps(r.get("xattr_sha256", {}), sort_keys=True)) for r in rows}
    return content + ("_metadata_diff" if len(metadata) > 1 else "")


def load_index(repo):
    by_blob = defaultdict(list)
    for item in subprocess.check_output(["git", "ls-files", "--stage", "-z"], cwd=repo).split(b"\0"):
        if not item:
            continue
        header, path = item.split(b"\t", 1)
        mode, blob, stage = header.decode().split()
        if stage != "0":
            raise RuntimeError("unmerged Git index")
        by_blob[blob].append(path.decode("utf-8", "surrogateescape"))
    return by_blob


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl_gz(path, rows):
    with path.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as zipped:
            with io.TextIOWrapper(zipped, encoding="utf-8") as out:
                for row in rows:
                    out.write(json.dumps({k: v for k, v in row.items() if not k.startswith("_")}, ensure_ascii=True, sort_keys=True) + "\n")


def compare_enumerations(first, second):
    before, after = ({r["source_path"]: r for r in group} for group in (first, second))
    changes = [{"path": p, "change": "added"} for p in sorted(after.keys() - before.keys())]
    changes += [{"path": p, "change": "removed"} for p in sorted(before.keys() - after.keys())]
    for p in sorted(before.keys() & after.keys()):
        a, b = before[p], after[p]
        if (tuple(a["_signature"]) != tuple(b["_signature"]) or a.get("link_target") != b.get("link_target")
                or a.get("xattr_sha256") != b.get("xattr_sha256") or a.get("xattr_error") != b.get("xattr_error")):
            changes.append({"path": p, "change": "metadata_or_xattr_changed"})
    return changes


def projected_link_target(path, by_destination, destination_root, old_home_root, rewrite=False):
    """Apply each symlink before its subsequent '..', as a filesystem does.

    Outside-root dependencies are followed using metadata only, so an external
    alias back into the old home root cannot be mistaken for independence.
    """
    pending, resolved, seen, chain = str(path).split("/"), [], set(), []
    followed = 0
    while pending:
        part = pending.pop(0)
        if not part or part == ".":
            continue
        if part == "..":
            if resolved:
                resolved.pop()
            continue
        prefix = "/" + "/".join(resolved + [part])
        if prefix == str(old_home_root) or prefix.startswith(str(old_home_root) + "/"):
            return {"status": "uses_old_home", "resolved": prefix, "chain": chain}
        in_union = prefix == str(destination_root) or prefix.startswith(str(destination_root) + "/")
        boundary_parent = str(destination_root).startswith(prefix + "/")
        if in_union:
            group = by_destination.get(prefix)
            if not group:
                return {"status": "missing_in_union", "resolved": prefix, "chain": chain}
            status = collision_status(group)
            if "conflict" in status or "unverified" in status:
                return {"status": "destination_conflict", "resolved": prefix, "chain": chain}
            row = group[0]
            kind = row["type"]
            target = row.get("link_recommended_target") if rewrite else row.get("link_target")
        elif boundary_parent:
            kind, target = "directory", None
        else:
            try:
                s = os.lstat(prefix)
                kind = "symlink" if stat.S_ISLNK(s.st_mode) else "directory" if stat.S_ISDIR(s.st_mode) else "file"
                target = os.readlink(prefix) if kind == "symlink" else None
            except OSError as exc:
                return {"status": "outside_root_missing_or_inaccessible", "resolved": prefix, "chain": chain, "error": str(exc)}
        if kind == "symlink":
            marker = (prefix, tuple(pending))
            if marker in seen or followed >= 80:
                return {"status": "link_loop_or_depth", "resolved": prefix, "chain": chain}
            seen.add(marker)
            followed += 1
            chain.append(prefix)
            if target is None:
                return {"status": "unreadable_link_target", "resolved": prefix, "chain": chain}
            if os.path.isabs(target):
                resolved = []
            pending = target.split("/") + pending
            continue
        if kind != "directory" and any(p for p in pending):
            return {"status": "ancestor_not_directory", "resolved": prefix, "chain": chain}
        resolved.append(part)
    final = "/" + "/".join(resolved)
    status = "exists_in_union" if final == str(destination_root) or final.startswith(str(destination_root) + "/") else "outside_root_existing"
    return {"status": status, "resolved": final, "chain": chain}


def archive_destinations(candidates, repo, protected_inodes=frozenset()):
    groups, issues = defaultdict(list), []
    for row in candidates:
        rel = Path(row["git_archive_path"])
        target = repo / rel
        if rel.is_absolute() or ".." in rel.parts:
            row["git_archive_destination_status"] = "unsafe_relative_path"
            issues.append({"path": str(target), "status": "unsafe_relative_path"})
            continue
        groups[str(target)].append(row)
        parent = target.parent
        while parent != repo.parent:
            if os.path.lexists(parent) and (parent.is_symlink() or not parent.is_dir()):
                row["git_archive_destination_status"] = "ancestor_not_directory_or_link"
                issues.append({"path": str(target), "ancestor": str(parent), "status": "ancestor_not_directory_or_link"})
                break
            if parent == repo:
                break
            parent = parent.parent
        else:
            continue
        if row.get("git_archive_destination_status"):
            continue
        if str(target) == row["source_path"]:
            row["git_archive_destination_status"] = "existing_source_in_working_tree"
        elif not os.path.lexists(target):
            row["git_archive_destination_status"] = "planned_absent"
        elif target.is_symlink() or not target.is_file():
            row["git_archive_destination_status"] = "existing_type_conflict"
            issues.append({"path": str(target), "status": "existing_type_conflict"})
        else:
            s = target.lstat()
            if sealed(target.parts) or (s.st_dev, s.st_ino) in protected_inodes:
                row["git_archive_destination_status"] = "existing_protected_alias_unverified"
                issues.append({"path": str(target), "status": "existing_protected_alias_unverified"})
                continue
            with os.fdopen(open_without_symlinks(target), "rb") as stream:
                if signature(os.fstat(stream.fileno())) != signature(s):
                    raise RuntimeError("Git archive target changed before hashing")
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
                if signature(os.fstat(stream.fileno())) != signature(s):
                    raise RuntimeError("Git archive target changed during hashing")
            status = "existing_identical_bytes" if digest == row.get("sha256") else "existing_different_bytes"
            row["git_archive_destination_status"] = status
            if status == "existing_different_bytes":
                issues.append({"path": str(target), "status": status})
    for target, group in groups.items():
        if len(group) > 1:
            if any(r.get("hash_status") != "verified_at_scan" for r in group):
                status = "multiple_sources_hash_unverified"
            elif len({r.get("sha256") for r in group}) != 1:
                status = "multiple_sources_different_bytes"
            else:
                status = None
            if status:
                issues.append({"path": target, "status": status, "sources": [r["source_path"] for r in group]})
        for parent in Path(target).parents:
            if str(parent) in groups:
                issues.append({"path": target, "ancestor": str(parent), "status": "planned_file_ancestor_conflict"})
                break
    return issues


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home-root", type=Path, default=Path("/home/hwkim/sftdpo_work"))
    parser.add_argument("--data-root", type=Path, default=Path("/data/hwkim/sftdpo_work"))
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cache", type=Path, default=Path("/tmp/sftdpo_migration_20261028_hashes.sqlite"))
    args = parser.parse_args()
    for root in (args.home_root, args.data_root):
        if not root.is_dir() or root.is_symlink():
            raise RuntimeError("source root must be an actual directory: " + str(root))
    args.output.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc).isoformat()
    index = load_index(args.repo)
    initial_head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=args.repo).decode().strip()
    errors = []
    args.repo = args.repo.absolute()
    roots_to_scan = [(args.home_root, "home"), (args.data_root, "data")]
    rows = []
    for root, label in roots_to_scan:
        rows += enumerate_tree(root, label, args.data_root, errors, args.home_root)
    repo_scopes = [Path(p) for p in ("training/generated", "training/annotations/generated", "training/experiments", "evaluation/real_data/records")]
    repo_rows = []
    for rel_scope in repo_scopes:
        root = args.repo / rel_scope
        if not root.exists():
            continue
        group = enumerate_tree(root, "repo", root, errors, args.home_root)
        for row in group:
            row["relative_path"] = str(rel_scope / row["relative_path"])
            cat, why, runtime = classify(row["relative_path"], row["type"], repo=True)
            row.update(category=cat, classification_basis=why, runtime_requirement=runtime,
                       physical_action="retain_in_git_working_tree", destination_path=row["source_path"],
                       git_archive_path=git_archive_path("repo", row["relative_path"], cat))
        repo_rows += group
    all_rows = rows + repo_rows
    print(json.dumps({"phase": "enumerated", "external_entries": len(rows), "repo_entries": len(repo_rows), "errors": len(errors)}), flush=True)
    protected_inodes = {(r["device"], r["inode"]) for r in all_rows if r["type"] == "file" and sealed(Path(r["relative_path"]).parts)}
    cache = sqlite3.connect(args.cache)
    cache.execute("create table if not exists hashes (signature text primary key, sha256 text, blob_sha1 text)")
    last, completed, byte_count = time.monotonic(), 0, 0
    for row in all_rows:
        if row["type"] != "file":
            continue
        file_hashes(row, cache, protected_inodes, started)
        completed += 1
        byte_count += row["size_bytes"]
        row["git_index_identical_paths"] = index.get(row.get("git_blob_sha1"), []) if row.get("git_archive_path") or row["source_root"] == "repo" else []
        same_repo_path = row["source_root"] == "repo" and row["relative_path"] in row["git_index_identical_paths"]
        if same_repo_path and row["category"] == "pending_classification":
            row.update(category="git_existing_generated_record", classification_basis="identical file bytes already tracked in index",
                       runtime_requirement="none", git_archive_path=row["relative_path"])
        if row.get("git_archive_path"):
            row["git_coverage"] = "index_same_path_and_bytes" if same_repo_path else "index_identical_elsewhere" if row["git_index_identical_paths"] else "no_identical_index_blob"
            row["git_disposition"] = "candidate_requires_producer_review" if "candidate" in row["category"] else "preserve_training_or_run_record"
        if time.monotonic() - last > 10:
            cache.commit()
            print(json.dumps({"phase": "hashing", "completed_files": completed, "logical_bytes_seen": byte_count,
                              "current_group": row["relative_path"].split("/")[0]}), flush=True)
            last = time.monotonic()
    cache.commit()
    # A second metadata enumeration detects changes and silent omissions.
    second = []
    for root, label in roots_to_scan:
        second += enumerate_tree(root, label, args.data_root, errors, args.home_root)
    repo_second = []
    for rel_scope in repo_scopes:
        root = args.repo / rel_scope
        if root.exists():
            repo_second += enumerate_tree(root, "repo", root, errors, args.home_root)
    changes = compare_enumerations(rows, second) + compare_enumerations(repo_rows, repo_second)
    by_dest = defaultdict(list)
    for row in rows:
        by_dest[row["destination_path"]].append(row)
    collisions = []
    for dest, group in sorted(by_dest.items()):
        status = collision_status(group)
        for row in group:
            row["destination_collision"] = status
        if len(group) > 1:
            collisions.append({"destination": dest, "status": status,
                               "sources": [r["source_path"] for r in group]})
    ancestor_conflicts = []
    for dest, group in by_dest.items():
        parent = Path(dest).parent
        while parent != args.data_root.parent:
            g = by_dest.get(str(parent), [])
            if g and any(r["type"] != "directory" for r in g):
                ancestor_conflicts.append({"destination": dest, "ancestor": str(parent), "types": sorted({r["type"] for r in g})})
                break
            if parent == args.data_root:
                break
            parent = parent.parent
    cache.close()
    link_analysis = []
    for row in rows:
        if row["type"] == "symlink":
            before_rewrite = projected_link_target(row["destination_path"], by_dest, args.data_root, args.home_root)
            after_rewrite = projected_link_target(row["destination_path"], by_dest, args.data_root, args.home_root, rewrite=True)
            row.update(projected_link_preserved=before_rewrite, projected_link_rewritten=after_rewrite)
            link_analysis.append({"source": row["source_path"], "target": row.get("link_target"),
                                  "runtime_requirement": row["runtime_requirement"], "preserved": before_rewrite, "rewritten": after_rewrite})
    all_candidates = [r for r in all_rows if r.get("git_archive_path") and r["type"] == "file"]
    archive_conflicts = archive_destinations(all_candidates, args.repo, protected_inodes)
    if all_candidates:
        paths = [r["git_archive_path"] for r in all_candidates]
        result = subprocess.run(["git", "check-ignore", "--no-index", "-z", "--stdin"], input=("\0".join(paths) + "\0").encode(),
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=args.repo)
        if result.returncode not in (0, 1):
            raise RuntimeError(result.stderr.decode())
        ignored = {p.decode("utf-8", "surrogateescape") for p in result.stdout.split(b"\0") if p}
        for row in all_candidates:
            row["git_archive_path_ignored"] = row["git_archive_path"] in ignored
    rows.sort(key=lambda r: (r["source_root"], r["relative_path"]))
    repo_rows.sort(key=lambda r: r["relative_path"])
    write_jsonl_gz(args.output / "external_entries.jsonl.gz", rows)
    write_jsonl_gz(args.output / "repository_entries.jsonl.gz", repo_rows)
    write_jsonl_gz(args.output / "git_candidates.jsonl.gz", all_candidates)
    write_json(args.output / "collisions.json", {"overlaps": collisions, "ancestor_conflicts": ancestor_conflicts})
    write_json(args.output / "git_archive_conflicts.json", archive_conflicts)
    write_jsonl_gz(args.output / "link_analysis.jsonl.gz", link_analysis)
    write_json(args.output / "scan_issues.json", {"errors": errors, "source_changes": changes,
                "hash_errors": [{"path": r["source_path"], "error": r.get("hash_error")} for r in rows + repo_rows if r["hash_status"] == "error_or_changed"]})
    roots = {}
    for label in ("home", "data"):
        group = [r for r in rows if r["source_root"] == label]
        roots[label] = {"entries": len(group), "types": dict(Counter(r["type"] for r in group)),
                        "regular_file_logical_bytes": sum(r["size_bytes"] for r in group if r["type"] == "file"),
                        "regular_file_allocated_bytes": sum(r["allocated_bytes"] for r in group if r["type"] == "file")}
    summary = {"schema_version": 1, "scan_started_utc": started, "scan_finished_utc": datetime.now(timezone.utc).isoformat(),
               "repo_head": initial_head,
               "git_index_unchanged_during_scan": dict(index) == dict(load_index(args.repo)),
               "git_head_unchanged_during_scan": initial_head == subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=args.repo).decode().strip(),
               "repository_scope_exists": {str(rel): (args.repo / rel).exists() for rel in repo_scopes},
               "source_roots": {"home": str(args.home_root), "data": str(args.data_root)}, "roots": roots,
               "external_categories": dict(Counter(r["category"] for r in rows)),
               "external_hash_status": dict(Counter(r["hash_status"] for r in rows if r["type"] == "file")),
               "overlap_status": dict(Counter(c["status"] for c in collisions)), "ancestor_conflicts": len(ancestor_conflicts),
               "old_home_absolute_links": sum(bool(r.get("link_uses_old_home")) for r in rows),
               "projected_preserved_link_status": dict(Counter(r["preserved"]["status"] for r in link_analysis)),
               "projected_rewritten_link_status": dict(Counter(r["rewritten"]["status"] for r in link_analysis)),
               "broken_links_before": sum(r["type"] == "symlink" and not r.get("link_target_exists_before", True) for r in rows),
               "scan_errors": len(errors), "source_changes": len(changes),
               "hash_errors": sum(r["hash_status"] == "error_or_changed" for r in rows + repo_rows),
               "hash_reads": dict(Counter(r.get("hash_read", "not_read") for r in all_rows if r["type"] == "file")),
               "hardlink_groups": sum(n > 1 for n in Counter((r["device"], r["inode"]) for r in all_rows if r["type"] == "file").values()),
               "git_archive_conflicts": len(archive_conflicts),
               "git_candidates": {"files": len(all_candidates), "logical_bytes": sum(r["size_bytes"] for r in all_candidates),
                                  "no_identical_index_blob": sum(r.get("git_coverage") == "no_identical_index_blob" for r in all_candidates),
                                  "ignored_proposed_archive_paths": sum(r.get("git_archive_path_ignored", False) for r in all_candidates),
                                  "at_least_100_mib": sum(r["size_bytes"] >= 100 * 1024**2 for r in all_candidates)},
               "repo_generated_categories": dict(Counter(r["category"] for r in repo_rows if r["type"] == "file")),
               "limitations": ["protected final files and any hardlink aliases are metadata-only; hashes deliberately pending",
                               "raw-byte Git SHA1 matching does not apply attributes/line-ending normalization; unmatched is not proof of lost information",
                               "index byte identity anywhere is not intended-path, committed, or remote coverage evidence",
                               "snapshot is an observed scan, not a filesystem snapshot or permission to migrate",
                               "environment/build bytes are inventoried for preservation; runtime relocation requires rebuild",
                               "classification candidates and ambiguous raw/binary files require producer review before import",
                               "this scan uses fresh hashes; only hardlinks with identical metadata within this same scan share hash results"]}
    write_json(args.output / "summary.json", summary)
    artifacts = {}
    for p in sorted(args.output.iterdir()):
        if p.is_file() and p.name not in {"artifacts.json", "README.md", "REVIEW.md"}:
            artifacts[p.name] = {"bytes": p.stat().st_size, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
    write_json(args.output / "artifacts.json", artifacts)
    print(json.dumps({"phase": "finished", "summary": summary}, ensure_ascii=True), flush=True)


if __name__ == "__main__":
    main()
