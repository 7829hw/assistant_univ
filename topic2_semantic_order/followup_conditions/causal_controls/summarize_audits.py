"""Produce a compact, reproducible summary of exposure contrasts."""
from schedules import HERE, ORDER_SEEDS
from common import load
from taxonomy import write_csv


def main():
    factorial, spacing, placebo = [], [], []
    for seed in ORDER_SEEDS:
        audit = load(HERE/f"audits/o{seed}.json")
        for name, edge in audit["factorial"].items():
            factorial.append(dict(order_seed=seed,contrast=name,eligible=edge["eligible"],
                failed_gates="|".join(k for k,v in edge["gates"].items() if not v),
                **{f"{k}_improvement":edge["improvement"].get(k) for k in edge["residuals"]},
                **{f"{k}_{stat}_tv":v[i] for k,v in edge["residuals"].items()
                   for i,stat in enumerate(("mean","max"))}))
        pair=audit["spacing"]
        spacing.append(dict(order_seed=seed,eligible=pair["eligible"],
            failed_gates="|".join(k for k,v in pair["checks"].items() if not v),
            low_mean_max_gap=pair["low"]["mean_max_gap_steps"],high_mean_max_gap=pair["high"]["mean_max_gap_steps"],
            gap_delta=pair["gap_delta"],low_switch=pair["low"]["switch_fraction"],
            high_switch=pair["high"]["switch_fraction"],switch_drop=pair["switch_drop"],**pair["lr_residuals"]))
        p=audit["placebo"]
        row=dict(order_seed=seed,eligible=p["eligible"],reassigned_fine_fraction=p["fine_reassigned_fraction"],
                 true_vs_placebo_scope_match=p["true_vs_placebo_scope_match"],
                 placebo_coarse_improvement=p["placebo_improvement"]["coarse"],
                 placebo_fine_improvement=p["placebo_improvement"]["fine"])
        placebo.append(dict(**row,**{f"true_{k}_mean_tv":value[0] for k,value in audit["balance"]["placebo"].items()}))
    for name,rows in (("factorial_matching",factorial),("spacing_matching",spacing),("placebo_matching",placebo)):
        write_csv(HERE/"tables"/f"{name}.csv",rows)


if __name__=="__main__":
    main()
