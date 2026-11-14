"""List Git-ready original evaluation records without staging files a worker may write."""
import argparse
import json
from pathlib import Path
import sys

from schedules import HERE
from common import S, local
from integration import json_lines


def completed_cell(followup, cell, scored_sha, replaced=False):
    folder = Path("replaced") if replaced else Path()
    scored = followup/"cells"/folder/f"{cell}.json"
    if S.sha_file(scored) != scored_sha:
        raise ValueError(f"Scored file digest mismatch: {scored}")
    raw = followup/"cells_raw"/folder/f"{cell}_raw.jsonl"
    meta = json.loads(scored.read_bytes())["meta"]["hf"]
    if S.sha_file(raw) != meta["raw_out_sha256"]:
        raise ValueError(f"Raw file digest mismatch: {raw}")
    log = scored.with_suffix(".log")
    if not log.is_file():
        raise ValueError(f"Missing cell log: {log}")
    return (scored, raw, log)


def paths_to_preserve(followup):
    execution = followup/"gpu/execution"
    for folder in (execution, execution/"matched_baselines"):
        for row in json_lines(folder/"eval_provenance.jsonl"):
            yield from completed_cell(followup, row["cell"], row["sha256"])
        for row in json_lines(folder/"reruns.jsonl"):
            yield from completed_cell(followup, row["cell"], row["original_sha256"], replaced=True)
        for event in json_lines(folder/"timeline.jsonl"):
            attempt = event.get("attempt")
            if event["stage"] == "eval":
                yield folder/f"eval_{event['cell']}_a{attempt}.log"
            elif event["stage"] == "train":
                yield folder/f"train_{event['job']}_a{attempt}.log"
                if event["rc"] == 0:
                    yield folder/f"training_{event['job']}.json"
            elif event["stage"] == "job_completed":
                yield folder/f"serve_{event['job']}.log"
                yield folder/f"server_{event['job']}.json"
        for name in ("phase1_assignment.json", "phase2_assignment.json"):
            if (folder/name).is_file():
                yield folder/name
        if (folder/"done.json").is_file():
            yield folder/"done.json"
    for name in ("phase1_done.json", "phase2_done.json"):
        if (execution/name).is_file():
            yield execution/name


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    paths = sorted(set(paths_to_preserve(HERE.parent)))
    missing = [p for p in paths if not p.is_file()]
    if missing:
        raise ValueError(f"Missing completed run artifacts: {missing}")
    for path in paths:
        sys.stdout.buffer.write(local(path).encode("utf-8")+b"\0")


if __name__=="__main__":
    main()
