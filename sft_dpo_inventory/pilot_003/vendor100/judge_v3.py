# -*- coding: utf-8 -*-
"""pilot_003 업체 100 판정과 aux_test_v1 보고(PROTOCOL_v3 5·6절). 모델 호출 없음.

    python sft_dpo_inventory/pilot_003/vendor100/judge_v3.py vendor100   # 업체 100: 판정(HF-base → HF-최종), 참고(E)
    python sft_dpo_inventory/pilot_003/vendor100/judge_v3.py aux         # aux_test_v1: 보고만
    python sft_dpo_inventory/pilot_003/vendor100/judge_v3.py selftest    # 코드 확인: selection_v2 runs(HF-base→dpo_step174)로 같은 계산

- 입력: ``<셋>/runs/<prefix>_<셀>_s<k>.json``. 원문(루프 판정)은 ``training/generated/pilot_003/raw/<같은 이름>_raw.jsonl``(ignore).
- 표본별 채점·분류는 calibration_001 ``analyze_cal.load_sample``(grounding_check, U1–U4, 조용한 오답, 오류 유형, 루프) 그대로다.
- 문항 i의 셀 값은 k표본 평균. 차이의 95% CI는 문항 단위 bootstrap 10,000회(``analyze_cal.boot_ci``).
  비교마다 ``default_rng(20261109)``를 새로 만든다(analyze_selection.py와 같다).
- 판정(6절, 주 비교 HF-base → HF-최종 하나만):
  개선 = grounding_ok CI 하한 > 0, U CI 하한 ≤ 0, 조용한 오답 CI 하한 ≤ 0, 지연 중앙값 비 ≤ 1.5 모두.
  악화 = grounding_ok CI 상한 < 0, U CI 하한 > 0, 조용한 오답 CI 하한 > 0, 지연 중앙값 비 > 1.5 중 하나.
  그 밖은 차이 없음(이 셋·k에서 구분되지 않음).
- 함께 적는 것: 셀별 평균·표본별 값, 안정 정답 문항 수, 새로 생긴·사라진 U·조용한 오답 문항(문항 평균 > 0 기준), 오류 유형 비율,
  greedy 기록(있으면, 기록만), 잡음 폭(같은 셀 두 반쪽 표본 평균 차이의 95% 폭), 표본별 장치, family 분리(결정 15, 판정 없음),
  삼자 비교(E, HF-base, HF-최종; 문항 평균 ≥ 0.5를 O로, 판정 없음).
- family: ``data/overlap.json``의 업체 100 family 겹침 문항(pilot_003 학습 질문의 thor semantic family에 속한 문항).
"""
import json
import sys
from itertools import product
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
P3 = HERE.parent
ROOT = P3.parents[1]
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/calibration_001"))
import analyze_cal as A  # noqa: E402

A.RAW = ROOT / "training/generated/pilot_003/raw"
SEED = 20261109
# U1–U4 판정(grounding_v13 report.unacceptable)은 "셋/id" 키로 원본 gold를 찾는다. 업체 100 문항은 compare_cells.load_cell과 같이 "dev/<id>",
# aux_test_v1의 final_v12 문항은 pilot_002 compare_aux.py와 같은 원본 파일을 쓴다.
A.C.R.C.GOLD_FILES["final_v12"] = "evaluation/grounding_v12/final_questions.yaml"
_unacceptable = A.C.R.unacceptable
A.C.R.unacceptable = lambda key, row, src: _unacceptable(key if "/" in key else f"dev/{key}", row, src)
SETS = {
    "vendor100": {"gold": ROOT / "evaluation/vendor100/gold.yaml", "runs": P3 / "vendor100/runs", "prefix": "v100_", "k": 8,
                  "cells": ["HF-base", "HF-final", "E"], "judged": ("HF-base", "HF-final"),
                  "reference": [("E", "HF-base"), ("E", "HF-final")], "out": HERE / "judgment.json"},
    "aux": {"gold": ROOT / "sft_dpo_inventory/pilot_002/aux_test/aux_test_gold.yaml", "runs": P3 / "aux_test/runs", "prefix": "aux_",
            "k": 4, "cells": ["HF-base", "HF-final", "E"], "judged": None,
            "reference": [("HF-base", "HF-final"), ("E", "HF-base"), ("E", "HF-final")], "out": P3 / "aux_test/comparison.json"},
    "selftest": {"gold": ROOT / "sft_dpo_inventory/conversion_diag/selection_gold.yaml", "runs": P3 / "selection/runs", "prefix": "",
                 "k": 4, "cells": ["HF-base", "dpo_step174"], "judged": ("HF-base", "dpo_step174"), "reference": [],
                 "out": None},
}
GREEDY = {"vendor100": {"HF-base": ROOT / "sft_dpo_inventory/thinking_prep_001/hf_e/HF-E_run1.json"}}


def load_cell(cfg, cell, gold):
    samples, metas = [], []
    for k in range(1, cfg["k"] + 1):
        path = cfg["runs"] / f"{cfg['prefix']}{cell}_s{k}.json"
        if not path.exists():
            return None, None
        meta, rows = A.load_sample(path, gold)
        samples.append(rows)
        metas.append({"sample": k, "source": str(path.relative_to(ROOT)), "device": A.device(meta),
                      "seed": ((meta.get("hf") or {}).get("decoding") or {}).get("round_seed") or (meta.get("pipeline") or {}).get("seed"),
                      "ollama_version": meta.get("ollama_version"), "model_digest": meta.get("model_digest"),
                      "isolation": (meta.get("pipeline") or {}).get("isolation"),
                      "adapter": (meta.get("hf") or {}).get("adapter")})
    return samples, metas


def mats(samples, ids):
    m = {f: np.array([[float(s[i][f] if f != "U" else s[i]["class"] == A.CS.U_CLASS) for s in samples] for i in ids])
         for f in ("ok", "U") + A.ERRORS}
    m["silent"] = np.array([[float(s[i]["class"] == A.CS.SILENT) for s in samples] for i in ids])
    return m


def cell_summary(samples, m, ids, k):
    A.K = k   # unbiased_var·sd 계산의 k
    st = A.cell_stats(m["ok"], m["U"], np.random.default_rng(SEED))
    for drop in ("half_split_diff_pct", "half_split_noise", "single_pairs"):   # 4표본 전용 값은 아래 반쪽 잡음으로 대신
        st.pop(drop, None)
    st["silent_pct"] = round(100 * float(m["silent"].mean()), 2)
    st["per_sample_silent"] = m["silent"].sum(axis=0).astype(int).tolist()
    st["error_rates_pct"] = {e: round(100 * float(m[e].mean()), 2) for e in A.ERRORS}
    st["occupied_misread_item_samples"] = int(m["occupied_misread"].sum())
    st["occupied_misread_items"] = {i: int(v) for i, v in zip(ids, m["occupied_misread"].sum(axis=1)) if v > 0}
    st["latency_median_s"] = round(float(np.median([s[i]["seconds"] for s in samples for i in ids])), 2)
    st["length_capped_calls"] = int(sum(s[i]["truncated"] for s in samples for i in ids))
    loops = [s[i]["loop_calls"] for s in samples for i in ids]
    st["loop_calls"] = None if any(x is None for x in loops) else int(sum(loops))
    # 잡음 폭: 앞 절반 표본과 뒤 절반 표본의 문항 평균 차이(문항 bootstrap 95% 폭)
    h = k // 2
    diff = m["ok"][:, :h].mean(axis=1) - m["ok"][:, h:].mean(axis=1)
    ci = A.boot_ci(diff, np.random.default_rng(SEED))
    st["half_split_noise"] = {"halves": f"s1–s{h} vs s{h + 1}–s{k}", "diff_pct": round(100 * float(diff.mean()), 2),
                              "ci95_pct": [round(100 * x, 2) for x in ci]}
    return st


def item_sets(m, ids, field):
    return {i for i, v in zip(ids, m[field].mean(axis=1)) if v > 0}


def versus(a, b, ma, mb, sa, sb, ids):
    r = A.compare(a, b, ma["ok"], mb["ok"], ma["U"], mb["U"], np.random.default_rng(SEED), sa, sb)
    ds = mb["silent"].mean(axis=1) - ma["silent"].mean(axis=1)
    ci_s = A.boot_ci(ds, np.random.default_rng(SEED))
    out = {k: v for k, v in r.items() if not k.startswith("_") and k not in ("noise95_pct", "U_noise95_pct")}
    k = len(sa["per_sample_grounding_ok"])
    out["noise95_pct(k)"] = round(1.96 * float(np.sqrt(sa["sd_pct"][str(k)] ** 2 + sb["sd_pct"][str(k)] ** 2)), 2)
    out["silent_diff_pct"] = round(100 * float(ds.mean()), 2)
    out["silent_ci95_pct"] = [round(100 * x, 2) for x in ci_s]
    out["latency_ratio"] = round(sb["latency_median_s"] / sa["latency_median_s"], 3)
    for name, field in (("U", "U"), ("silent", "silent")):
        sa_, sb_ = item_sets(ma, ids, field), item_sets(mb, ids, field)
        out[f"{name}_items"] = {"A": len(sa_), "B": len(sb_), "new": sorted(sb_ - sa_), "gone": sorted(sa_ - sb_)}
    d = mb["ok"].mean(axis=1) - ma["ok"].mean(axis=1)
    out["items_B_better"] = sorted(i for i, x in zip(ids, d) if x > 0)
    out["items_A_better"] = sorted(i for i, x in zip(ids, d) if x < 0)
    return out


def verdict(r):
    lo, hi = r["ci95_pct"]
    better = lo > 0 and r["U_ci95_pct"][0] <= 0 and r["silent_ci95_pct"][0] <= 0 and r["latency_ratio"] <= 1.5
    worse = [why for cond, why in ((hi < 0, "grounding_ok CI 상한 < 0"), (r["U_ci95_pct"][0] > 0, "U 비율 CI 하한 > 0"),
                                   (r["silent_ci95_pct"][0] > 0, "조용한 오답 비율 CI 하한 > 0"),
                                   (r["latency_ratio"] > 1.5, f"지연 중앙값 비 {r['latency_ratio']} > 1.5")) if cond]
    if worse:
        return "악화", worse
    if better:
        return "개선", ["grounding_ok CI 하한 > 0, U·조용한 오답 CI 하한 ≤ 0, 지연 비 ≤ 1.5"]
    return "차이 없음", ["개선·악화 조건 모두 아님(이 셋·k에서 구분되지 않음)"]


def diff_ci(ma, mb):
    out = {}
    for key, field in (("diff", "ok"), ("U_diff", "U"), ("silent_diff", "silent")):
        d = mb[field].mean(axis=1) - ma[field].mean(axis=1)
        out[f"{key}_pct"] = round(100 * float(d.mean()), 2)
        out[f"{key}_ci95_pct"] = [round(100 * x, 2) for x in A.boot_ci(d, np.random.default_rng(SEED))]
    return out


def subset(m, idx):
    return {f: v[idx] for f, v in m.items()}


def main():
    name = sys.argv[1]
    cfg = SETS[name]
    gold = {i["id"]: i for i in A.EV.load_gold(cfg["gold"])["items"]}
    data, missing = {}, []
    for cell in cfg["cells"]:
        samples, metas = load_cell(cfg, cell, gold)
        if samples is None:
            missing.append(cell)
            continue
        data[cell] = {"samples": samples, "meta": metas}
    common = set.intersection(*[set(s) for c in data.values() for s in c["samples"]])
    ids = [i for i in gold if i in common]   # gold 순서(analyze_cal·analyze_selection과 같은 bootstrap 순서)
    if any(set(s) != set(ids) for c in data.values() for s in c["samples"]):
        raise SystemExit("표본마다 문항 집합이 다르다")
    for cell, c in data.items():
        c["m"] = mats(c["samples"], ids)
        c["stats"] = cell_summary(c["samples"], c["m"], ids, cfg["k"])
    for cell, path in GREEDY.get(name, {}).items():
        if cell in data and path.exists():
            _, rows = A.load_sample(path, gold)
            data[cell]["stats"]["greedy(record only)"] = {"source": str(path.relative_to(ROOT)),
                                                          "grounding_ok": sum(rows[i]["ok"] for i in ids if i in rows)}
    out = {"set": name, "gold": str(cfg["gold"].relative_to(ROOT)), "items": len(ids), "k": cfg["k"], "missing_cells": missing,
           "cells": {c: {"stats": d["stats"], "samples": d["meta"]} for c, d in data.items()}}
    pairs = ([cfg["judged"]] if cfg["judged"] else []) + cfg["reference"]
    comps = {}
    for a, b in pairs:
        if a in data and b in data:
            comps[f"{a}→{b}"] = versus(a, b, data[a]["m"], data[b]["m"], data[a]["stats"], data[b]["stats"], ids)
    if cfg["judged"] and f"{cfg['judged'][0]}→{cfg['judged'][1]}" in comps:
        r = comps[f"{cfg['judged'][0]}→{cfg['judged'][1]}"]
        r["verdict"], r["verdict_reasons"] = verdict(r)
        out["judgment"] = {"pair": r["pair"], "verdict": r["verdict"], "reasons": r["verdict_reasons"]}
    out["comparisons"] = comps
    if name == "vendor100":
        ov = json.loads((P3 / "data/overlap.json").read_text(encoding="utf-8"))["sets"]["vendor100"]
        in_family = sorted({h["eval_id"] for h in ov["family"]})
        out["family(decision 15, no judgment)"] = {"in_family_items": in_family, "template_overlap_items":
                                                   sorted({h["eval_id"] for h in ov["template"]})}
        a, b = cfg["judged"]
        if a in data and b in data:
            for part, sel in (("in_family", [i in in_family for i in ids]), ("outside", [i not in in_family for i in ids])):
                idx = np.array(sel)
                pids = [i for i, s in zip(ids, sel) if s]
                ma, mb = subset(data[a]["m"], idx), subset(data[b]["m"], idx)
                out["family(decision 15, no judgment)"][part] = {
                    "items": len(pids), "A_mean_pct": round(100 * float(ma["ok"].mean()), 2),
                    "B_mean_pct": round(100 * float(mb["ok"].mean()), 2), **diff_ci(ma, mb)}
        if all(c in data for c in ("E", "HF-base", "HF-final")):
            names = ("E", "HF-base", "HF-final")
            o = {n: {i: v >= 0.5 for i, v in zip(ids, data[n]["m"]["ok"].mean(axis=1))} for n in names}
            combos = {}
            for combo in product("OX", repeat=3):
                sel = [i for i in ids if all(("O" if o[n][i] else "X") == c for n, c in zip(names, combo))]
                combos[" ".join(combo)] = {"n": len(sel), "ids": sel}
            out["three_way(E HF-base HF-final, item mean ≥ 0.5 = O, no judgment)"] = combos
    if cfg["out"]:
        cfg["out"].parent.mkdir(parents=True, exist_ok=True)
        cfg["out"].write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for c, d in data.items():
        s = d["stats"]
        print(f"{c:12s} mean {s['mean_pct']:6.2f} U {s['u_pct']:5.2f} silent {s['silent_pct']:5.2f} stable {s['stable_correct']} "
              f"lat {s['latency_median_s']} cap {s['length_capped_calls']} loop {s['loop_calls']} occ {s['occupied_misread_item_samples']} "
              f"singles {s['per_sample_grounding_ok']}")
    for key, r in comps.items():
        print(f"{key:20s} d {r['diff_pct']} CI {r['ci95_pct']} | U {r['U_diff_pct']} CI {r['U_ci95_pct']} | silent {r['silent_diff_pct']} "
              f"CI {r['silent_ci95_pct']} | lat x{r['latency_ratio']} {r.get('verdict', '')}")
    print("missing", missing)


if __name__ == "__main__":
    main()
