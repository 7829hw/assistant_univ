# -*- coding: utf-8 -*-
"""GPU 작업 기록 한 줄을 ``timeline.jsonl``에 더한다(5.2절). 작업이 끝날 때 한 번 부른다.

    python3 timeline.py --file TIMELINE --id J1 --kind self_samples --uuid GPU-... --commit SHA --start ISO --end ISO --status ok --out PATH...
"""
import argparse
import json


def main():
    p = argparse.ArgumentParser()
    for name in ("file", "id", "kind", "uuid", "commit", "start", "end", "status"):
        p.add_argument(f"--{name}", required=True)
    p.add_argument("--out", nargs="*", default=[])
    p.add_argument("--note", default="")
    a = p.parse_args()
    row = {"job_id": a.id, "kind": a.kind, "gpu_uuid": a.uuid, "worktree_commit": a.commit, "start": a.start, "end": a.end,
           "status": a.status, "outputs": a.out, "note": a.note}
    with open(a.file, "a", encoding="utf-8") as stream:
        stream.write(json.dumps(row, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
