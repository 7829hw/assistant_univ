#!/usr/bin/env python3
"""List tracked-file path references without exporting their text contents."""
from pathlib import Path
import argparse
import gzip
import json
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    needles = {"home": b"/home/hwkim/sftdpo_work", "data": b"/data/hwkim/sftdpo_work"}
    text_suffixes = {".py", ".sh", ".yaml", ".yml", ".md", ".json", ".jsonl", ".txt", ".log", ".csv", ".toml", ".ini"}
    records, skipped = [], []
    for raw in subprocess.check_output(["git", "ls-files", "-z"], cwd=args.repo).split(b"\0"):
        if not raw:
            continue
        rel = raw.decode("utf-8", "surrogateescape")
        p = args.repo / rel
        if p.suffix not in text_suffixes or not p.is_file() or p.is_symlink():
            continue
        if any(x.startswith("protected_final") for x in Path(rel).parts):
            skipped.append({"path": rel, "reason": "protected-name scope; no content read"})
            continue
        lines = {key: [] for key in needles}
        counts = {key: 0 for key in needles}
        with p.open("rb") as f:
            for n, line in enumerate(f, 1):
                for key, needle in needles.items():
                    count = line.count(needle)
                    if count:
                        counts[key] += count
                        lines[key].append(n)
        if not any(counts.values()):
            continue
        kind = "executable_review" if p.suffix in {".py", ".sh"} else "config_review" if p.suffix in {".yaml", ".yml"} else "historical_or_data_reference"
        records.append({"path": rel, "reference_counts": counts, "line_numbers": lines,
                        "review_class": kind, "action": "review_active_vs_frozen; never bulk-replace historical bytes"})
    output = {"head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=args.repo).decode().strip(),
              "files_with_references": len(records), "records": records, "protected_paths_not_read": skipped,
              "scope": "tracked regular text files at capture time; excluded types and protected-name paths are not content-scanned"}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(args.output, "wt", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=True, sort_keys=True)
        f.write("\n")
    print(json.dumps({"files_with_references": len(records), "protected_paths_not_read": len(skipped),
                      "home_reference_files": sum(bool(r["reference_counts"]["home"]) for r in records)}))


if __name__ == "__main__":
    main()
