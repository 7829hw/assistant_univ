# -*- coding: utf-8 -*-
"""A단계 보고 보조(C1, 판정 아님). 선택은 ``select_a.py``(고정)만 한다. 모델 호출 없음. 없는 셀은 건너뛴다.

    hfvenv/bin/python sft_dpo_inventory/pilot_007/analysis/a_report.py   # -> analysis/a_report.json

- recipe × 순서 seed 표(주 셋·valid98·aux·개발 셋 평균·U·silent·구조), pilot_006 F와 비교(seed 셋 75.99 ± 5.74, 개발 셋 기준값 66.19).
- epoch 1 안 궤적: 25·50·75% greedy k=1(E-Aq, 있으면) + 100% k=4.
- 학습: 시간(timeline), 마지막 100 step loss 평균, 로그의 lr 끝값.
주 셋 값은 seed sd의 근거로만 쓴다(선택 기준 아님, 결정 167).
"""
import json
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_006/post"))
P7 = ROOT / "sft_dpo_inventory/pilot_007"
CELLS = "sft_dpo_inventory/pilot_007/cells/"


def exists(label, k):
    return all((ROOT / f"{CELLS}{label}_s{j}.json").exists() for j in range(1, k + 1))


def metrics(rows):
    g = defaultdict(list)
    for r in rows:
        g[(r["set"], r["id"])].append(r)
    acc = lambda sets, f: round(100 * float(np.mean([np.mean([x[f] for x in v]) for (s, _), v in g.items() if s in sets])), 2)  # noqa: E731
    return {"main": acc(("sel", "holdout"), "ok"), "valid98": acc(("valid98",), "ok"), "aux": acc(("aux",), "ok"),
            "dev_mean": acc(("valid98", "aux"), "ok"), "main_U": acc(("sel", "holdout"), "U"), "main_silent": acc(("sel", "holdout"), "silent"),
            "main_struct": acc(("sel", "holdout"), "struct")}


def train_info(jid):
    log = P7 / f"gpu/{jid}.log"
    if not log.exists():
        return None
    steps = []
    for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
        i = line.find("{'loss'")
        if i >= 0:
            steps.append(eval(line[i:line.index("}", i) + 1], {"__builtins__": {}}, {"nan": float("nan")}))  # noqa: S307
    tl = [json.loads(l) for l in (P7 / "gpu/timeline.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()] if (P7 / "gpu/timeline.jsonl").exists() else []
    t = next((x for x in tl if x["job_id"] == jid), None)
    hours = round((datetime.fromisoformat(t["end"]) - datetime.fromisoformat(t["start"])).total_seconds() / 3600, 2) if t else None
    loss = [s["loss"] for s in steps]
    return {"steps_logged": len(steps), "hours": hours, "status": t["status"] if t else None, "loss_last100_mean": round(float(np.mean(loss[-100:])), 4) if loss else None,
            "lr_last": steps[-1]["learning_rate"] if steps else None}


def main():
    import itemdata as I
    out = {"models": {}, "trajectory": {}, "training": {}, "pilot006_F": {"main_seed_set": "75.99 ± 5.74 (82.62, 72.68, 72.68)", "dev_reference": 66.19}}
    for r in ("R1", "R2"):
        for o in ("o43", "o1016", "o7"):
            jid, nm = f"A-{r}-{o}", f"A_{r}_{o}"
            out["training"][jid] = train_info(jid)
            low = nm.lower()
            if all(exists(f"{low}_{st}", 4) for st in ("sel", "holdout", "valid98", "aux")):
                rows = []
                for st in ("sel", "holdout", "valid98", "aux"):
                    rows += I.cell_rows(f"{CELLS}{low}_{st}", st, nm, 4, with_tokens=False)
                out["models"][nm] = metrics(rows)
            tr = {}
            for q in ("25", "50", "75"):
                lab = f"{low}_q{q}_greedy"
                if exists(f"{lab}_sel", 1) and exists(f"{lab}_holdout", 1):
                    rows = I.cell_rows(f"{CELLS}{lab}_sel", "sel", nm, 1, with_tokens=False) + I.cell_rows(f"{CELLS}{lab}_holdout", "holdout", nm, 1, with_tokens=False)
                    tr[f"q{q}_greedy_main"] = metrics(rows)["main"]
            if nm in out["models"]:
                tr["q100_k4_main"] = out["models"][nm]["main"]
            out["trajectory"][nm] = tr
    for r in ("R1", "R2"):
        ms = [out["models"].get(f"A_{r}_{o}") for o in ("o43", "o1016", "o7")]
        if all(ms):
            out[f"summary_{r}"] = {k: {"mean": round(float(np.mean([m[k] for m in ms])), 2), "sd": round(float(np.std([m[k] for m in ms], ddof=1)), 2)}
                                   for k in ("main", "valid98", "aux", "dev_mean", "main_U")}
    (HERE / "a_report.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
