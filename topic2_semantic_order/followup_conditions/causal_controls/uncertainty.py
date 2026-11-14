"""Secondary intervals separating training-run and evaluation-item uncertainty."""
import numpy as np

REPLICATES = 10_000
RNG_SEED = 20261115


def transition_summary(correct, base):
    """Expected counts across saved base draws, with conditional rates."""
    lost = float((base * ~correct).sum())
    gained = float(((1 - base) * correct).sum())
    base_correct = float(base.sum())
    base_wrong = len(base) - base_correct
    return dict(base_correct_to_wrong=lost, base_wrong_to_correct=gained,
                base_correct_to_wrong_rate=lost / base_correct if base_correct else None,
                base_wrong_to_correct_rate=gained / base_wrong if base_wrong else None)


def collapse_for_draws(m, base, denominator, draw):
    totals = draw @ denominator
    available = totals > 0
    denominator = np.where(available, totals, 1)
    base_accuracy = (draw @ base) / denominator
    accuracy = np.einsum("bk,skg->bsg", draw, m) / denominator[:, None, :]
    return ((accuracy < (base_accuracy - .20)[:, None, :])
            & available[:, None, :]).sum(axis=-1)


def secondary_intervals(tab, vectors, base, order_seeds, train_seeds, contrasts, reps=REPLICATES):
    """The order block and within-order training-seed pair are the draw units."""
    shape = (len(order_seeds), len(train_seeds))
    pair_keys = [(o, t) for o in order_seeds for t in train_seeds]
    complete = {name: weights for name, weights in contrasts.items()
                if all((arm, o, t) in vectors for arm in weights for o,t in pair_keys)}
    if not complete:
        return {}
    mat = {arm:np.stack([tab.sums(vectors[arm,o,t])[0] for o,t in pair_keys])
           for arm in {a for weights in complete.values() for a in weights}}
    base_m = tab.sums(base)[0]
    full = np.ones((1, tab.K))
    fixed = {arm:collapse_for_draws(m, base_m, tab.N, full).reshape(shape) for arm,m in mat.items()}
    run_rng, item_rng = (np.random.default_rng(s) for s in np.random.SeedSequence(RNG_SEED).spawn(2))
    intervals = {name: ([], []) for name in complete}
    for start in range(0, reps, 128):
        n = min(reps-start,128)
        picked_orders = run_rng.integers(shape[0],size=(n,shape[0],1))
        picked_runs = run_rng.integers(shape[1],size=(n,*shape))
        cluster_draw = item_rng.multinomial(tab.K, np.full(tab.K,1/tab.K),size=n)
        eval_counts = {arm:collapse_for_draws(m,base_m,tab.N,cluster_draw).reshape(n,*shape)
                       for arm,m in mat.items()}
        for name,weights in complete.items():
            x = sum(w*fixed[a] for a,w in weights.items())
            y = sum(w*eval_counts[a] for a,w in weights.items())
            run_only, joint = intervals[name]
            run_only.extend(x[picked_orders,picked_runs].mean(axis=(1,2)))
            joint.extend(y[np.arange(n)[:,None,None],picked_orders,picked_runs].mean(axis=(1,2)))
    result = {}
    for name,weights in complete.items():
        x = sum(w*fixed[a] for a,w in weights.items())
        run_only, joint = intervals[name]
        result[name] = dict(point=float(x.mean()),run_only_ci95=np.percentile(run_only,[2.5,97.5]).tolist(),
                            run_plus_template_ci95=np.percentile(joint,[2.5,97.5]).tolist(),
                            paired_training_seed_deltas=x.tolist(),
                            within_order_sample_sd=x.std(axis=1,ddof=1).tolist(),
                            measurement="descriptive secondary intervals")
    return result
