# -*- coding: utf-8 -*-
"""B2 C1: B단계 F 하락 진단(판정 아님). 같은 순서 seed끼리 A3 F(무작위 순서), B F(O4 질문 단위 순서), B2 F(O4', 있으면)를 비교한다. P도 같이 본다. 모델 호출 없음.

    hfvenv/bin/python sft_dpo_inventory/pilot_007/analysis/diag_b_fdrop.py   # -> analysis/diag_b_fdrop.json

1. loss 곡선: 학습 로그의 step loss를 10구간 평균(``gpu/<작업>.log``).
2. epoch 끝 구간: 학습 순서의 마지막 10% 레코드(F 181, P 178)에 든 질문 수·출처(corpus_group)·loss_scope(teacher full_response / 8b json_only)와 전체 비율.
   A3는 accelerate 순서 재현(``make_order7b.a3_random``), B는 ``order7.order_records``, B2는 ``order7b``.
3. 질문당 레코드 수: arm 간 차이(F 1,811 대 P 1,775)가 어느 질문·출처·loss_scope에서 나는지.
4. 잃은 문항(같은 seed A3 F → B F, 주 셋): 문항 정답률(k=4 평균)이 0.5 이상 떨어진 문항 수, 그 문항의 B F 표본 오류 코드·분류(cls)·U 표시(u_flags), 문항 유형(gold 마지막 tool).
   U 증가 원인: 주 셋 U 표본의 u_flags 빈도를 A3 F·B F·B P에서 비교.
5. 가설(문장, 가설임을 밝힘)은 B2_RESULTS에 적는다.
"""
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
P7 = HERE.parent
ROOT = P7.parents[1]
sys.path.insert(0, str(P7 / "train"))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_006/post"))
SEEDS = {"o43": 43, "o1016": 20261016, "o7": 7, "o11": 11, "o2027": 2027}
C7 = "sft_dpo_inventory/pilot_007/cells/"


def losses(job):
    f = P7 / f"gpu/{job}.log"
    if not f.exists():
        return None
    out = []
    for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
        i = line.find("{'loss'")
        if i >= 0:
            m = re.search(r"'loss': ([0-9.e-]+|nan)", line[i:])
            out.append(float(m.group(1)))
    return out or None


def deciles(x):
    a = np.array(x)
    return [round(float(c.mean()), 4) for c in np.array_split(a, 10)]


def tail_profile(records):
    n = len(records)
    tail = records[n - round(n * 0.1):]
    return {"tail_records": len(tail), "tail_questions": len({r["metadata"]["source_record_id"] for r in tail}),
            "tail_corpus_group": dict(Counter(r["metadata"].get("corpus_group") for r in tail).most_common()),
            "tail_loss_scope": dict(Counter(r["metadata"]["loss_scope"] for r in tail)),
            "all_loss_scope_share": {k: round(v / n, 4) for k, v in Counter(r["metadata"]["loss_scope"] for r in records).items()},
            "tail_loss_scope_share": {k: round(v / len(tail), 4) for k, v in Counter(r["metadata"]["loss_scope"] for r in tail).items()}}


def main():
    import order7
    import order7b
    from make_order7b import a3_random
    import itemdata as I
    rc = P7 / "build/RC5"
    recs = {arm: order7.load_jsonl(rc / arm / "sft_train.jsonl") for arm in ("full", "partial")}
    out = {"loss_deciles": {}, "epoch_tail": {}, "records_per_question": {}, "lost_items": {}, "u_flags": {}}
    # 1
    for o in SEEDS:
        for job in ([f"A3-R1pp-{o}"] if o in ("o43", "o1016", "o7") else []) + [f"B-F-{o}", f"B-P-{o}", f"B2-F-{o}", f"B2-P-{o}"]:
            x = losses(job)
            if x and len(x) >= 1700:
                out["loss_deciles"][job] = deciles(x)
    # 2
    for o, s in SEEDS.items():
        d = {}
        if o in ("o43", "o1016", "o7"):
            d["A3_F(random)"] = tail_profile(a3_random(recs["full"], s))
        for arm, tag in (("full", "F"), ("partial", "P")):
            d[f"B_{tag}(O4)"] = tail_profile(order7.order_records(recs[arm], s))
            of = json.loads((rc / f"order_b2_o{s}.json").read_text(encoding="utf-8"))
            d[f"B2_{tag}(O4')"] = tail_profile(order7b.order_records(recs[arm], of["order"]))
        out["epoch_tail"][o] = d
    # 3
    cnt = {arm: Counter(r["metadata"]["source_record_id"] for r in recs[arm]) for arm in recs}
    grp = {r["metadata"]["source_record_id"]: r["metadata"].get("corpus_group") for r in recs["full"] + recs["partial"]}
    scope_cnt = {arm: Counter((r["metadata"]["source_record_id"], r["metadata"]["loss_scope"]) for r in recs[arm]) for arm in recs}
    diff_q = {q: cnt["full"][q] - cnt["partial"][q] for q in cnt["full"] if cnt["full"][q] != cnt["partial"][q]}
    out["records_per_question"] = {
        "F_records": len(recs["full"]), "P_records": len(recs["partial"]), "questions_with_diff": len(diff_q),
        "F_more": sum(v > 0 for v in diff_q.values()), "P_more": sum(v < 0 for v in diff_q.values()), "net_diff": sum(diff_q.values()),
        "diff_by_corpus_group": dict(Counter({g: 0 for g in []}) + Counter({grp[q]: v for q, v in diff_q.items()})) if diff_q else {},
        "diff_by_loss_scope": {sc: sum(scope_cnt["full"][(q, sc)] - scope_cnt["partial"][(q, sc)] for q in cnt["full"]) for sc in ("full_response", "json_only")},
        "mean_records_per_question": {arm: round(len(recs[arm]) / len(cnt[arm]), 3) for arm in recs}}
    gq = defaultdict(int)
    for q, v in diff_q.items():
        gq[grp[q]] += v
    out["records_per_question"]["diff_by_corpus_group"] = dict(gq)
    # 4
    def item_means(prefix, model):
        rows = I.cell_rows(prefix + "_sel", "sel", model, 4, with_tokens=False) + I.cell_rows(prefix + "_holdout", "holdout", model, 4, with_tokens=False)
        g = defaultdict(list)
        for r in rows:
            g[(r["set"], r["id"])].append(r)
        return g
    cat = {}  # 문항 유형 = gold 마지막 tool(정답 호출 없으면 expected_outcome)
    for st in ("sel", "holdout"):
        for i, it in I.gold(st).items():
            cat[(st, i)] = it["gold"][-1]["tool"] if it.get("gold") else it.get("expected_outcome")
    uf = {}
    for o in ("o43", "o1016", "o7"):
        a3 = item_means(f"{C7}a3_r1pp_{o}", "A3")
        bf = item_means(f"{C7}b_f_{o}", "BF")
        bp = item_means(f"{C7}b_p_{o}", "BP")
        lost = [k for k in a3 if np.mean([r["ok"] for r in a3[k]]) - np.mean([r["ok"] for r in bf[k]]) >= 0.5]
        gained = [k for k in a3 if np.mean([r["ok"] for r in bf[k]]) - np.mean([r["ok"] for r in a3[k]]) >= 0.5]
        bad = [r for k in lost for r in bf[k] if not r["ok"]]
        out["lost_items"][o] = {"lost_ge_0.5": len(lost), "gained_ge_0.5": len(gained), "lost_by_set": dict(Counter(k[0] for k in lost)),
                                "lost_by_category": dict(Counter(cat.get(k) for k in lost).most_common()),
                                "lost_BF_failed_samples": len(bad), "lost_BF_cls": dict(Counter(r["cls"] for r in bad).most_common()),
                                "lost_BF_code": dict(Counter(r["code"] for r in bad).most_common(8)),
                                "lost_BF_flags": {f: sum(bool(r[f]) for r in bad) for f in ("U", "silent", "struct", "gfail", "repair", "mm_nm", "dt_missing")},
                                "lost_items_P_same_seed_ok_mean": round(float(np.mean([np.mean([r["ok"] for r in bp[k]]) for k in lost])), 3) if lost else None}
        for name, g in (("A3_F", a3), ("B_F", bf), ("B_P", bp)):
            us = [r for rs in g.values() for r in rs if r["U"]]
            c = uf.setdefault(name, {"U_samples": 0, "flags": Counter()})
            c["U_samples"] += len(us)
            for r in us:
                c["flags"].update(r["u_flags"] if isinstance(r["u_flags"], (list, tuple)) else [str(r["u_flags"])])
    out["u_flags"] = {k: {"U_samples(3 seeds)": v["U_samples"], "flags": dict(v["flags"].most_common(10))} for k, v in uf.items()}
    (HERE / "diag_b_fdrop.json").write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1, default=str)[:6000])


if __name__ == "__main__":
    main()
