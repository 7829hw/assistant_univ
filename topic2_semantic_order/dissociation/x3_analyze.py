"""X3 탐침 분석(PREREGISTRATION 5절). CPU 전용. 지표는 fare_dissociation_check.features()를 고치지 않고 쓴다.

    python x3_analyze.py MAIN_REPO
비교: run마다 탐침 셀 − 원래 기록 셀(같은 어댑터), 대상 147문항. 정확 부호 뒤집기 검정(2^18 전부 열거, 양측).
X3a 지지 = 지표 2 차이 평균 ≥ +10%p 그리고 p < 0.05. X3b 지지 = 지표 1 차이 평균 ≤ −5%p 그리고 p < 0.05. base·arm별 평균은 기술.
출력: dissociation/x3/x3_results.json
"""
import contextlib
import importlib.util
import io
import itertools
import json
import sys
from pathlib import Path

import numpy as np

main = Path(sys.argv[1]).resolve()
D = main / "topic2_semantic_order/dissociation"
spec = importlib.util.spec_from_file_location("fdc", D / "fare_dissociation_check.py")
fdc = importlib.util.module_from_spec(spec)
argv, sys.argv = sys.argv, ["x", str(main)]
with contextlib.redirect_stdout(io.StringIO()):
    spec.loader.exec_module(fdc)
sys.argv = argv
need = fdc.need
assert len(need) == 147
RAW3 = "training/generated/topic2_dissociation/x3_raw"


def metrics(raw):
    missing = [i for i in need if i not in raw]
    if missing:
        raise SystemExit(f"raw에 없는 문항 {len(missing)}")
    F = [fdc.features(raw[i], fdc.T1[i]) for i in need]
    ana = [f for f in F if f["template"] == "analysis"]
    miss = [f for f in ana if not f["location"]]
    return {"n": len(F), "n_analysis": len(ana), "n_refusal": sum(f["template"] == "refusal" for f in F),
            "m1_refusal": float(np.mean([f["template"] == "refusal" for f in F])),
            "m2_location": float(np.mean([f["location"] for f in ana])) if ana else None,
            "m3_taxi_type": float(np.mean([f["taxi_type"] for f in miss])) if miss else None,
            "n_missing": len(miss),
            "location_all_outputs": float(np.mean([f["location"] for f in F])),
            "template_counts": {t: sum(f["template"] == t for f in F) for t in ("analysis", "refusal", "other")},
            "states_region_condition_analysis": float(np.mean([f["states_region_condition"] for f in ana])) if ana else None}


def signflip(d):
    d = np.asarray(d, float)
    obs = abs(d.mean())
    signs = np.array(list(itertools.product((1, -1), repeat=len(d))), dtype=np.int8)
    means = np.abs(signs @ d) / len(d)
    return float(np.mean(means >= obs - 1e-12))


rows = []
for run in fdc.RUNS:
    label = f"{run[0]}-{run[1]}-r{run[2]}"
    tag = label.lower().replace("-", "_")
    orig = metrics(fdc.load_raw(fdc.raw_path(*run)))
    r = {"run": label, "arm": run[0], "orig": orig}
    for p in "ab":
        r[p] = metrics(fdc.load_raw(f"{RAW3}/x3{p}_{tag}_s1_raw.jsonl"))
    rows.append(r)

res = {"targets": len(need), "runs": rows, "tests": {}, "by_arm": {}, "base": []}
for p, key, thr, direction in (("a", "m2_location", 0.10, 1), ("b", "m1_refusal", -0.05, -1)):
    for k in ("m1_refusal", "m2_location", "m3_taxi_type"):
        diffs = [r[p][k] - r["orig"][k] for r in rows if r[p][k] is not None and r["orig"][k] is not None]
        t = {"n_runs": len(diffs), "mean_diff": float(np.mean(diffs)), "sd_diff": float(np.std(diffs, ddof=1)),
             "n_positive": sum(x > 0 for x in diffs), "n_negative": sum(x < 0 for x in diffs)}
        if len(diffs) == 18:
            t["p_signflip_two_sided"] = signflip(diffs)
        res["tests"][f"{p}:{k}"] = t
    prim = res["tests"][f"{p}:{key}"]
    ok = (prim["mean_diff"] >= thr if direction == 1 else prim["mean_diff"] <= thr) and prim.get("p_signflip_two_sided", 1) < 0.05
    res["tests"][f"X3{p}_verdict"] = {"primary": key, "threshold": thr, "supported": bool(ok)}
for arm in "AB":
    sub = [r for r in rows if r["arm"] == arm]
    res["by_arm"][arm] = {c: {k: float(np.mean([r[c][k] for r in sub if r[c][k] is not None]))
                              for k in ("m1_refusal", "m2_location", "m3_taxi_type")} for c in ("orig", "a", "b")}
for s in (1, 2):
    b = {"seed_index": s, "orig": metrics(fdc.load_raw(f"{fdc.G}/ablation_012/cells_raw/hdev_base_s{s}_raw.jsonl"))}
    for p in "ab":
        f = main / f"{RAW3}/x3{p}_base_s{s}_raw.jsonl"
        b[p] = metrics(fdc.load_raw(f"{RAW3}/x3{p}_base_s{s}_raw.jsonl")) if f.exists() else None
    res["base"].append(b)
(D / "x3/x3_results.json").write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

pc = lambda x: "  —  " if x is None else f"{100 * x:5.1f}"
print("run        | 원래 m1  m2    m3   | a: m1  m2    m3   | b: m1  m2    m3")
for r in rows:
    print(f"{r['run']:<11}| " + " | ".join(" ".join(pc(r[c][k]) for k in ("m1_refusal", "m2_location", "m3_taxi_type")) for c in ("orig", "a", "b")))
for b in res["base"]:
    print(f"base s{b['seed_index']}    | " + " | ".join(" ".join(pc(b[c][k]) if b[c] else "  na " for k in ("m1_refusal", "m2_location", "m3_taxi_type")) for c in ("orig", "a", "b")))
print(json.dumps(res["tests"], ensure_ascii=False, indent=1))
print(json.dumps(res["by_arm"], ensure_ascii=False))
for b in res["base"]:
    print("base", b["seed_index"], {c: (b[c]["location_all_outputs"], b[c]["template_counts"]) if b[c] else None for c in ("orig", "a", "b")})
