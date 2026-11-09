"""Repeat-pair analysis (descriptive, written before reading RT2-15 result; H-dev only, seed o2026131).

Separates order effect from retraining/GPU nondeterminism: same config + same order trained twice (A0 original vs r2, B original vs r2),
H-dev, k=1, same eval seed. Reports overall accuracy and item-level discordance. No inference beyond that (one seed, one repeat each).
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
T = ROOT / "topic2_semantic_order/cells"
A13 = ROOT / "sft_dpo_inventory/ablation_013/cells"
paths = {
    "A": A13 / "hdev_a0_o2026131_s1.json",
    "A_r2": T / "hdev_t2_a0_o2026131_r2_s1.json",
    "B": T / "hdev_t2_b_o2026131_s1.json",
    "B_r2": T / "hdev_t2_b_o2026131_r2_s1.json",
}


def load(p):
    d = json.loads(p.read_text(encoding="utf-8"))
    return {r["id"]: r.get("category") == "match" for r in d["rows"]}


def pair(x, y):
    ids = sorted(set(x) & set(y))
    n = len(ids)
    only_x = sum(x[i] and not y[i] for i in ids)
    only_y = sum(y[i] and not x[i] for i in ids)
    return {"n": n, "acc_x": round(100 * sum(x[i] for i in ids) / n, 2), "acc_y": round(100 * sum(y[i] for i in ids) / n, 2),
            "diff_pp": round(100 * (sum(y[i] for i in ids) - sum(x[i] for i in ids)) / n, 2), "x_only_correct": only_x, "y_only_correct": only_y,
            "discordant_pct": round(100 * (only_x + only_y) / n, 2)}


def main():
    miss = [k for k, p in paths.items() if not p.exists()]
    rows = {k: load(p) for k, p in paths.items() if p.exists()}
    out = {"missing": miss, "note": "one seed (o2026131), one repeat per arm; descriptive only"}
    for a, b in (("A", "A_r2"), ("B", "B_r2"), ("A", "B"), ("A_r2", "B_r2")):
        if a in rows and b in rows:
            out[f"{a}_vs_{b}"] = pair(rows[a], rows[b])
    (Path(__file__).parent / "repeat_pair_t2.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
