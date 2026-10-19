# -*- coding: utf-8 -*-
"""A3 보고 보조(C1, 진단). 선택은 ``select_a3.py``(고정)만 한다. 모델 호출 없음. 없는 셀은 건너뛴다.

    hfvenv/bin/python sft_dpo_inventory/pilot_007/analysis/a3_report.py   # -> analysis/a3_report.json

- 결과표(모델마다): 주 셋·valid98·aux·개발 셋 평균, 주 셋 구조 오류·U, 출력 지표(주 셋 첫 응답):
  ``"od_role":"none"`` 비율(``od_none.py`` 방법), thinking의 (ii) 문장 비율(``itemdata.concl_types``), 영어 생각 비율(한글 비율 < 0.5, ``teacher_checks7.korean_ratio``).
- 비교 표: pilot_006 F(RC3, lr 합 0.070), A2 (a)(RC3c, 0.051), A2 R1'(RC3c, 0.068), A단계 R1(RC3c, 0.034)·R2(RC3c, 0.0085), A3 R1'(RC5, 0.091)·R1''(RC5, 0.181).
- 학습: lr 합(계획), 마지막 100 step loss, 시간. 궤적(25·50·75% greedy, 있으면).
"""
import glob
import json
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
P6POST = ROOT / "sft_dpo_inventory/pilot_006/post"
P7 = ROOT / "sft_dpo_inventory/pilot_007"
for p in (P6POST, HERE, P7 / "teacher"):
    sys.path.insert(0, str(p))
C6, C7 = "sft_dpo_inventory/pilot_006/cells/", "sft_dpo_inventory/pilot_007/cells/"
OD_NONE = re.compile(r'"od_role"\s*:\s*"none"')

# 모델: (이름, 데이터, lr 합, {셋: (셀 접두, k)})
MODELS = []
for nm, p in (("pilot006_F43", C6 + "f43_e1"), ("pilot006_F1016", C6 + "f1016_e1")):
    MODELS.append((nm, "RC3", 0.0698, {"sel": (p + "_sel", 4), "holdout": (p + "_holdout", 4)}))
MODELS[0][3].update(valid98=(C6 + "f43_e1_valid98", 4), aux=(C6 + "f43_e1_aux", 4))
MODELS[1][3].update(valid98=(C7 + "ref_f1016_e1_valid98", 4), aux=(C7 + "ref_f1016_e1_aux", 4))
MODELS.append(("pilot006_D_F7", "RC3", 0.0698, {g: ("sft_dpo_inventory/pilot_006/post/cells/d_f7_q100_" + g, 4) for g in ("sel", "holdout", "valid98", "aux")}))
for tag, data, lr, pre in (("A_R1", "RC3c", 0.0339, "a_r1"), ("A_R2", "RC3c", 0.0085, "a_r2"), ("A2_C", "RC3c", 0.0508, "c"), ("A2_R1p", "RC3c", 0.0678, "r1p"),
                           ("A3_R1p", "RC5", 0.0906, "a3_r1p"), ("A3_R1pp", "RC5", 0.1811, "a3_r1pp")):
    seeds = ("s43", "s1016", "s7") if tag == "A2_C" else ("o43", "o1016", "o7")
    for s in seeds:
        MODELS.append((f"{tag}_{s}", data, lr, {g: (f"{C7}{pre}_{s}_{g}", 4) for g in ("sel", "holdout", "valid98", "aux")}))


def exists(prefix, k):
    return all((ROOT / f"{prefix}_s{j}.json").exists() for j in range(1, k + 1))


def main():
    import itemdata as I
    from teacher_checks7 import korean_ratio
    out = {"models": {}, "groups": {}, "training": {}, "trajectory": {}}
    for nm, data, lr, sets in MODELS:
        rows, have = [], True
        for st, (pre, k) in sets.items():
            if not exists(pre, k):
                have = have and st not in ("sel", "holdout")
                continue
            rows += I.cell_rows(pre, st, nm, k, with_tokens=False)
        if not rows or not have:
            continue
        g = defaultdict(list)
        for r in rows:
            g[(r["set"], r["id"])].append(r)

        def acc(ss, f):
            v = [np.mean([x[f] for x in xs]) for (s, _), xs in g.items() if s in ss]
            return round(100 * float(np.mean(v)), 2) if v else None
        main_rows = [r for r in rows if r["set"] in ("sel", "holdout")]
        od = []
        for pre, k in (sets["sel"], sets["holdout"]):
            for f in sorted(glob.glob(str(ROOT / f"{pre}_s*.json"))):
                raw = json.loads(Path(f).read_text(encoding="utf-8"))["meta"]["hf"]["raw_out"]
                seen = set()
                for line in Path(raw).read_text(encoding="utf-8").splitlines():
                    x = json.loads(line)
                    if x["id"] not in seen:
                        seen.add(x["id"])
                        od.append(bool(OD_NONE.search((x.get("raw_text") or "").split("</think>")[-1])))
        out["models"][nm] = {"data": data, "lr_sum": lr, "main": acc(("sel", "holdout"), "ok"), "valid98": acc(("valid98",), "ok"), "aux": acc(("aux",), "ok"),
                             "dev_mean": acc(("valid98", "aux"), "ok"), "main_struct": acc(("sel", "holdout"), "struct"), "main_U": acc(("sel", "holdout"), "U"),
                             "od_none_pct": round(100 * float(np.mean(od)), 2) if od else None,
                             "type_ii_pct": round(100 * float(np.mean(["ii" in r["concl"] for r in main_rows])), 1),
                             "english_thinking_pct": round(100 * float(np.mean([korean_ratio(r["thinking"]) < 0.5 for r in main_rows if r["thinking"]])), 1)}
    for grp in ("A_R1", "A_R2", "A2_C", "A2_R1p", "A3_R1p", "A3_R1pp"):
        ms = [v for k, v in out["models"].items() if k.startswith(grp + "_")]
        if len(ms) == 3:
            out["groups"][grp] = {"data": ms[0]["data"], "lr_sum": ms[0]["lr_sum"],
                                  **{k: {"mean": round(float(np.mean([m[k] for m in ms])), 2), "sd": round(float(np.std([m[k] for m in ms], ddof=1)), 2)}
                                     for k in ("main", "dev_mean", "main_struct", "od_none_pct", "type_ii_pct", "english_thinking_pct")}}
    p6 = [out["models"][k] for k in ("pilot006_F43", "pilot006_F1016", "pilot006_D_F7") if k in out["models"]]
    if p6:
        out["groups"]["pilot006_F"] = {"data": "RC3", "lr_sum": 0.0698, **{k: {"mean": round(float(np.mean([m[k] for m in p6 if m[k] is not None])), 2)}
                                                                          for k in ("main", "dev_mean", "main_struct", "od_none_pct", "type_ii_pct", "english_thinking_pct")}}
    plan = json.loads((P7 / "train/configs_a3/lr_check.json").read_text(encoding="utf-8"))
    tl = [json.loads(l) for l in (P7 / "gpu/timeline.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    for cid in ("R1p-o43", "R1p-o1016", "R1p-o7", "R1pp-o43", "R1pp-o1016", "R1pp-o7"):
        jid = f"A3-{cid}"
        log = P7 / f"gpu/{jid}.log"
        loss = []
        if log.exists():
            for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
                i = line.find("{'loss'")
                if i >= 0:
                    loss.append(eval(line[i:line.index("}", i) + 1], {"__builtins__": {}}, {"nan": float("nan")})["loss"])  # noqa: S307
        t = next((x for x in tl if x["job_id"] == jid), None)
        out["training"][jid] = {"lr_sum_planned": plan[cid]["lr_sum"], "steps_logged": len(loss), "loss_last100_mean": round(float(np.mean(loss[-100:])), 4) if loss else None,
                                "hours": round((datetime.fromisoformat(t["end"]) - datetime.fromisoformat(t["start"])).total_seconds() / 3600, 2) if t else None,
                                "status": t["status"] if t else None}
        nm = "A3_" + cid.replace("-", "_")
        tr = {}
        for q in ("q25", "q50", "q75"):
            lab = f"{C7}{nm.lower()}_{q}_greedy"
            if exists(lab + "_sel", 1) and exists(lab + "_holdout", 1):
                rr = I.cell_rows(lab + "_sel", "sel", nm, 1, with_tokens=False) + I.cell_rows(lab + "_holdout", "holdout", nm, 1, with_tokens=False)
                gg = defaultdict(list)
                for r in rr:
                    gg[(r["set"], r["id"])].append(r["ok"])
                tr[f"{q}_greedy_main"] = round(100 * float(np.mean([np.mean(v) for v in gg.values()])), 2)
        if nm in out["models"]:
            tr["q100_k4_main"] = out["models"][nm]["main"]
        out["trajectory"][nm] = tr
    (HERE / "a3_report.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"groups": out["groups"]}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
