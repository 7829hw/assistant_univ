# -*- coding: utf-8 -*-
"""A2 보고 보조(C4, 진단). 판정·해석 규칙은 ``select_a2.py``(고정)만 한다. 모델 호출 없음. 없는 셀은 건너뛴다.

    hfvenv/bin/python sft_dpo_inventory/pilot_007/analysis/a2_report.py   # -> analysis/a2_report.json

- 표 1: (a) C-s<seed> 대 pilot_006 F 같은 seed(F-s43 e1, F-s1016 e1, D-F7 100%) — 주 셋·valid98·aux·개발 셋 평균·주 셋 구조 오류율·U.
  pilot_006 값은 세션 3·4 표본(``pilot_006/post/samples_s3·s4.jsonl``), F-s1016 개발 셋은 이 세션 기준 셀(``ref_f1016_e1_*``).
- 표 2: (b) R1p-o<seed> — 같은 항목, recipe 요약(주 셋 sd·개발 셋 평균), A단계 R1·R2 요약(``a_report.json``)과 나란히.
- 학습: lr 합(dry-run 계획 ``train/configs_a2/lr_check.json``), 시간·마지막 100 step loss(로그), (b) 궤적(25·50·75% greedy, 있으면).
"""
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
P6POST = ROOT / "sft_dpo_inventory/pilot_006/post"
P7 = ROOT / "sft_dpo_inventory/pilot_007"
sys.path.insert(0, str(P6POST))
CELLS = "sft_dpo_inventory/pilot_007/cells/"


def exists(label, k):
    return all((ROOT / f"{CELLS}{label}_s{j}.json").exists() for j in range(1, k + 1))


def metrics(rows):
    g = defaultdict(list)
    for r in rows:
        g[(r["set"], r["id"])].append(r)

    def acc(sets, f):
        v = [np.mean([x[f] for x in xs]) for (s, _), xs in g.items() if s in sets]
        return round(100 * float(np.mean(v)), 2) if v else None
    return {"main": acc(("sel", "holdout"), "ok"), "valid98": acc(("valid98",), "ok"), "aux": acc(("aux",), "ok"), "dev_mean": acc(("valid98", "aux"), "ok"),
            "main_struct": acc(("sel", "holdout"), "struct"), "main_U": acc(("sel", "holdout"), "U")}


def cell_rows(name, label, sets, k=4):
    import itemdata as I
    out = []
    for st in sets:
        if exists(f"{label}_{st}", k):
            out += I.cell_rows(f"{CELLS}{label}_{st}", st, name, k, with_tokens=False)
    return out


def train_info(jid):
    log = P7 / f"gpu/{jid}.log"
    if not log.exists():
        return None
    loss, lrs = [], []
    for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
        i = line.find("{'loss'")
        if i >= 0:
            d = eval(line[i:line.index("}", i) + 1], {"__builtins__": {}}, {"nan": float("nan")})  # noqa: S307
            loss.append(d["loss"])
            lrs.append(d["learning_rate"])
    tl = [json.loads(l) for l in (P7 / "gpu/timeline.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    t = next((x for x in tl if x["job_id"] == jid), None)
    return {"steps_logged": len(loss), "lr_sum_logged": round(sum(lrs), 5), "loss_last100_mean": round(float(np.mean(loss[-100:])), 4) if loss else None,
            "hours": round((datetime.fromisoformat(t["end"]) - datetime.fromisoformat(t["start"])).total_seconds() / 3600, 2) if t else None,
            "status": t["status"] if t else None}


def main():
    p6 = defaultdict(list)
    for f in ("samples_s3.jsonl", "samples_s4.jsonl"):
        for l in (P6POST / f).read_text(encoding="utf-8").splitlines():
            r = json.loads(l)
            p6[r["model"]].append(r)
    out = {"table1_a_vs_pilot006F": {}, "table2_b": {}, "training": {}, "trajectory_b": {}}
    for seed, cname, ref in (("s43", "C_s43", "F43e1"), ("s1016", "C_s1016", "F1016e1"), ("s7", "C_s7", "D_F7q100")):
        a = cell_rows(cname, cname.lower(), ("sel", "holdout", "valid98", "aux"))
        rr = list(p6[ref]) + (cell_rows("F1016e1", "ref_f1016_e1", ("valid98", "aux")) if seed == "s1016" else [])
        ma, mr = (metrics(a) if a else None), metrics(rr)
        out["table1_a_vs_pilot006F"][seed] = {"a": ma, "pilot006_F": mr,
                                               "diff": {k: round(ma[k] - mr[k], 2) for k in ma if ma and ma[k] is not None and mr.get(k) is not None} if ma else None}
    ms = []
    for o in ("o43", "o1016", "o7"):
        nm = f"R1p_{o}"
        rows = cell_rows(nm, nm.lower(), ("sel", "holdout", "valid98", "aux"))
        if rows:
            out["table2_b"][nm] = metrics(rows)
            ms.append(out["table2_b"][nm])
    if len(ms) == 3:
        out["table2_b"]["summary_R1p"] = {k: {"mean": round(float(np.mean([m[k] for m in ms])), 2), "sd": round(float(np.std([m[k] for m in ms], ddof=1)), 2)}
                                          for k in ("main", "dev_mean", "main_struct", "main_U")}
    ar = P7 / "analysis/a_report.json"
    if ar.exists():
        d = json.loads(ar.read_text(encoding="utf-8"))
        out["table2_b"]["A_stage"] = {r: d.get(f"summary_{r}") for r in ("R1", "R2")}
        out["table2_b"]["A_stage_struct"] = {m: v["main_struct"] for m, v in d["models"].items()}
    plan = json.loads((P7 / "train/configs_a2/lr_check.json").read_text(encoding="utf-8"))
    for jid in ("C-s43", "C-s1016", "C-s7", "R1p-o43", "R1p-o1016", "R1p-o7"):
        out["training"][jid] = {"lr_sum_planned": plan[jid]["lr_sum_to_stop"], **(train_info(jid) or {})}
    out["training"]["reference"] = {"pilot006_F43_epoch1_lr_sum": plan["pilot006_F43(reference)"]["lr_sum_to_stop"], "A_R1_lr_sum": 0.0339, "A_R2_lr_sum": 0.0085}
    for o in ("o43", "o1016", "o7"):
        nm = f"R1p_{o}"
        tr = {}
        for q in ("25", "50", "75"):
            lab = f"{nm.lower()}_q{q}_greedy"
            if exists(f"{lab}_sel", 1) and exists(f"{lab}_holdout", 1):
                rows = cell_rows(nm, lab, ("sel", "holdout"), 1)
                tr[f"q{q}_greedy_main"] = metrics(rows)["main"]
        if nm in out["table2_b"]:
            tr["q100_k4_main"] = out["table2_b"][nm]["main"]
        out["trajectory_b"][nm] = tr
    (HERE / "a2_report.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
