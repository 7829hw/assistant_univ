"""Read-only supplemental audit of the frozen CPU-generated schedules."""
import argparse
from pathlib import Path

import numpy as np

from schedules import FACTORIAL, HERE, ORDER_SEEDS, SCOPES, experiment, exposures
from common import ROOT, S, load
from taxonomy import write_csv

EDGES = (
    ("S0T0", "S1T0"), ("S0T1", "S1T1"), ("S0T0", "S0T1"), ("S1T0", "S1T1"),
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.out_dir.exists():
        parser.error("Use a fresh audit directory")

    _, blocks, labels, _ = experiment()
    registry = load(HERE/"orders/manifest.json")
    profiles, exposures_by_scope, differences, runs = {}, [], [], []
    for entry in registry["runs"]:
        arm, seed = entry["arm"], entry["order_seed"]
        if arm not in (*FACTORIAL, "low_gap", "high_gap"):
            continue
        path = ROOT/entry["path"]
        if S.sha_file(path) != entry["sha256"]:
            raise ValueError(f"Frozen order changed: {path}")
        mass, labels_by_scope, _, coarse, groups = exposures(load(path)["block_order"], blocks, labels)
        if arm in FACTORIAL:
            scope_totals = {
                scope: {name: values[:, [s == scope for _, s in labels_by_scope]].sum(axis=1)
                        for name, values in mass.items()}
                for scope in SCOPES
            }
            weighted = mass["lr_loss"].sum(axis=1)
            with np.errstate(invalid="raise", divide="raise"):
                profiles[seed, arm] = scope_totals["full_response"]["lr_loss"] / weighted
            for scope, totals in scope_totals.items():
                for decile in range(len(weighted)):
                    exposures_by_scope.append(dict(
                        seed=seed, arm=arm, decile=decile+1, scope=scope,
                        records=int(totals["count"][decile]),
                        input_tokens=int(totals["input"][decile]),
                        loss_tokens=int(totals["loss"][decile]),
                        lr_weighted_loss_tokens=float(totals["lr_loss"][decile]),
                        lr_weighted_loss_share=float(totals["lr_loss"][decile]/weighted[decile]),
                    ))
        else:
            bounds = np.r_[0, np.flatnonzero(coarse[1:] != coarse[:-1])+1, len(coarse)]
            lengths = np.diff(bounds)
            run_labels = coarse[bounds[:-1]]
            for code, group in enumerate(groups):
                selected = lengths[run_labels == code]
                runs.append(dict(seed=seed, arm=arm, coarse=group, runs=len(selected),
                                 mean_length=float(selected.mean()), max_length=int(selected.max())))

    for seed in ORDER_SEEDS:
        for left, right in EDGES:
            delta = profiles[seed, right] - profiles[seed, left]
            differences.append(dict(seed=seed, left=left, right=right,
                                    mean_abs_gap=float(np.abs(delta).mean()),
                                    max_abs_gap=float(np.abs(delta).max()),
                                    **{f"d{i}_delta": float(x) for i, x in enumerate(delta, 1)}))
    args.out_dir.mkdir(parents=True)
    write_csv(args.out_dir/"supervision_by_decile.csv", exposures_by_scope)
    write_csv(args.out_dir/"supervision_lr_pair_residuals.csv", differences)
    write_csv(args.out_dir/"spacing_coarse_runs.csv", runs)
    print(len(exposures_by_scope), len(differences), len(runs))


if __name__ == "__main__":
    main()
