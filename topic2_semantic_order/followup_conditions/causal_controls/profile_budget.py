"""Profile timings already logged by E1/E2 without starting any model calls."""
import argparse
from collections import defaultdict
from datetime import datetime
from pathlib import Path
import re
from statistics import median

from schedules import HERE
from common import dump, load
from integration import elapsed, json_lines

CUTOFF = "2026-11-15T01:45:00+09:00"
FIXED_TIME = datetime.fromisoformat(CUTOFF)
START_READY = re.compile(r"vllm serve (start GPU .*?|ready) port (\d+) .* (\S+\+09:00)$")
SERVER_METRICS = re.compile(
    r"Avg prompt throughput: ([\d.]+).*?Avg generation throughput: ([\d.]+).*?"
    r"Running: (\d+) reqs, Waiting: (\d+) reqs, GPU KV cache usage: ([\d.]+)%, Prefix cache hit rate: ([\d.]+)%"
)
LOAD_SECONDS = re.compile(r"Model loading took .*?and ([\d.]+) seconds")
PORTS = (18716, 18724, 18732)


def metrics(start_times):
    # These ports can be reused. Match the initialization time before using
    # the running band's log statistics and discard any unmatched log.
    server_root = Path("/data/hwkim/sftdpo_work/pilot_006_prep/vllm")
    result = {}
    for port in PORTS:
        path = server_root/f"server_{port}_bf16_fi.log"
        if not path.is_file() or port not in start_times:
            continue
        samples, loads, prefix_cache, session = [], [], None, None
        with path.open(encoding="utf-8", errors="replace") as handle:
            for line in handle:
                if "Initializing a V1 LLM engine" in line:
                    session = re.search(r"INFO (\d\d-\d\d \d\d:\d\d:\d\d)", line)
                    prefix_cache = "enable_prefix_caching=True" in line
                if match := LOAD_SECONDS.search(line):
                    loads.append(float(match[1]))
                if match := SERVER_METRICS.search(line):
                    sample_stamp = re.search(r"INFO (\d\d-\d\d \d\d:\d\d:\d\d)", line)
                    if not sample_stamp or sample_stamp[1] > FIXED_TIME.strftime("%m-%d %H:%M:%S"):
                        break
                    a = tuple(map(float, match.groups()))
                    if a[2] >= 8 and a[1] > 0:
                        samples.append(a)
        if not session or not samples:
            continue
        logged = datetime.strptime("2026-"+session[1], "%Y-%m-%d %H:%M:%S").replace(tzinfo=FIXED_TIME.tzinfo)
        age = (logged - start_times[port]).total_seconds()
        if not 0 <= age <= 100:
            continue
        fields = ("prompt_tok_s", "decode_tok_s", "running", "waiting", "kv_pct", "prefix_hit_pct")
        result[str(port)] = dict(init=logged.isoformat(), sample_count=len(samples),
                                 model_load_seconds=loads, prefix_cache_enabled=prefix_cache,
                                 medians={k: median(a) for k, a in zip(fields, zip(*samples), strict=True)})
    return result


def budget(train, windows, ready, checkpoints, cells):
    n = 32
    train_hours = n * median(train)
    between = n * median(ready) / 3600
    first, second = windows[1], windows[2]
    eval_hours = cells * median(first+second)
    sensitivity_hours = cells * (median(first)+(len(second)/len(first))*median(second))
    nominal = train_hours + eval_hours + between
    return dict(runs=n, evaluation_cells=cells, training_gpu_h=train_hours,
                nominal_eval_gpu_h=eval_hours, model_startup_gpu_h=between, nominal_total_gpu_h=nominal,
                first_attempt_only_total_gpu_h=train_hours+cells*median(first)+between,
                historical_retry_mix_total_gpu_h=train_hours+sensitivity_hours+between,
                all_observed_attempt_hours_per_first_cell_total_gpu_h=(
                    train_hours+cells*(sum(first)+sum(second))/len(first)+between),
                one_retry_every_cell_total_gpu_h=train_hours+cells*(median(first)+median(second))+between,
                three_gpu_division_lower_bound_h=nominal/3,
                largest_assigned_lane_central_h=nominal*12/n, checkpoint_and_export_gib=checkpoints)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("Use a fresh profile output")
    followup = HERE.parent
    logdir = followup/"gpu/execution"
    jobs = [j for phase in (1, 2) for j in load(followup/f"gpu/jobs_phase{phase}.json")["jobs"]]
    labels = {f"{c['label']}_s{c['k']}": c["dataset"] for j in jobs for c in j["cells"]}
    events = [r for r in json_lines(logdir/"timeline.jsonl")
              if datetime.fromisoformat(r["time"]) <= FIXED_TIME and r.get("rc") == 0]
    train = [elapsed(r)/3600 for r in events if r["stage"] == "train"]
    times = defaultdict(lambda: defaultdict(list))
    for r in events:
        if r["stage"] == "eval":
            times[labels[r["cell"]]][r["attempt"]].append(elapsed(r)/3600)
    ready, starts = [], {}
    for line in (logdir/"runs.log").read_text().splitlines():
        if not (m := START_READY.search(line)):
            continue
        state, port, date = m.groups()
        port, date = int(port), datetime.fromisoformat(date)
        if date > FIXED_TIME:
            break
        if state == "ready":
            ready.append((date-starts[port]).total_seconds())
        else:
            starts[port] = date
    sizes, footprints = defaultdict(list), defaultdict(list)
    by_job = {j["id"]:j for j in jobs}
    for r in events:
        if r["stage"] != "train":
            continue
        root = Path(by_job[r["job"]]["checkpoint"]).parent
        sizes["checkpoint"].append(sum(p.stat().st_size for p in (root/"checkpoint-1984").iterdir() if p.is_file()))
        sizes["export"].append(sum(p.stat().st_size for p in root.iterdir() if p.is_file()))
    receipts = [r for r in json_lines(logdir/"eval_provenance.jsonl") if datetime.fromisoformat(r["time"]) <= FIXED_TIME]
    for r in receipts:
        cell = r["cell"]
        paths = (followup/"cells"/f"{cell}.json",followup/"cells_raw"/f"{cell}_raw.jsonl")
        footprints[labels[cell]].append(sum(p.stat().st_size for p in paths))
    checkpoint_gib = 32 * sum(median(s) for s in sizes.values())/2**30
    options = {}
    for option, ds, count in (("A", "H-dev", 32), ("B", "CT10K", 160)):
        options[option] = budget(train, times[ds], ready, checkpoint_gib, count)
        options[option]["scored_and_raw_gib_nominal"] = count*median(footprints[ds])/2**30
    dump(args.out, dict(cutoff=CUTOFF, training_hours=train, cell_attempt_hours=times,
                        server_ready_seconds=ready, serving_process_log_samples=metrics(starts),
                        final_checkpoint_and_export_bytes=sizes, options=options))


if __name__ == "__main__":
    main()
