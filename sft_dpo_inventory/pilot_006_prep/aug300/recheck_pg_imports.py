# -*- coding: utf-8 -*-
"""W6 3 마지막 문단: W3 이식 뒤 ``pg_imports``(저장소 안 이식본)와의 겹침을 다시 본다. 모델 호출 없음.

    hfvenv/bin/python sft_dpo_inventory/pilot_006_prep/aug300/recheck_pg_imports.py

``check_aug300.py``(W3 전에 ``git show``로 꺼낸 같은 파일로 미리 검사)와 같은 기준·같은 계산을 pg_imports 경로로 다시 한다.
holdout 고정에 쓴 ``check_results.json``은 덮어쓰지 않는다. 결과: ``recheck_pg_imports.json``.
holdout에 새 강한 겹침이 나오면 고정한 holdout을 바꾸지 않고 보고한다(지시 W6).
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))
import check_aug300 as W6  # noqa: E402
from training.data.common import read_jsonl, sha256  # noqa: E402

PI = ROOT / "sft_dpo_inventory/pg_imports"
PG = {"pg_batch006": PI / "pg_batch006/approved.jsonl", "pg_reviewed_reasoning_v001": PI / "reviewed_reasoning_v001/dataset.jsonl",
      "pg_reviewed_gold_v006_p0": PI / "reviewed_gold_v006_p0/sft_train.jsonl"}


def main():
    import evaluate_vendor100 as EV
    from training.annotations.inventory import as_record, family_key
    from training.data.split import question_key, template_key
    prior = {r["id"]: r for r in json.loads((HERE / "check_results.json").read_text(encoding="utf-8"))["items"]}
    index = {}
    for name, path in PG.items():
        idx = {"q": {}, "g": [], "view": {}, "t": {}, "f": {}}
        for i, row in enumerate(read_jsonl(path)):
            if "messages" in row:
                q = next(m["content"] for m in row["messages"] if m["role"] == "user")
                payload, rid = (row.get("metadata") or {}).get("target_full"), (row.get("metadata") or {}).get("source_record_id")
            else:
                q, rid, payload = row["question"], row["id"], row["gold"] if isinstance(row["gold"], dict) else None
            qk = question_key(q)
            idx["q"].setdefault(qk, []).append(rid)
            idx["g"].append((rid, W6.grams(qk)))
            if payload:
                idx["view"].setdefault(json.dumps(EV._grounding_view(payload), ensure_ascii=False, sort_keys=True, default=str), []).append(rid)
                idx["t"].setdefault(template_key(as_record(payload)), []).append(rid)
                idx["f"].setdefault(family_key(payload), []).append(rid)
        index[name] = idx
    rows, holdout_new, differs = [], [], []
    for item in read_jsonl(HERE / "augmentation_300.jsonl"):
        payload = EV.derive_grounding(item["gold"])
        qk, g = question_key(item["question"]), W6.grams(question_key(item["question"]))
        vk = json.dumps(EV._grounding_view(payload), ensure_ascii=False, sort_keys=True, default=str)
        tk, fk = template_key(as_record(payload)), family_key(payload)
        per = {}
        for name, idx in index.items():
            best = max(((len(g & vg) / len(g | vg), rid) for rid, vg in idx["g"]), default=(0.0, None))
            per[name] = {"question": idx["q"].get(qk, []), "jaccard_max": round(best[0], 3), "jaccard_nearest": best[1],
                         "same_grounding": idx["view"].get(vk, []), "template": len(idx["t"].get(tk, [])), "family": len(idx["f"].get(fk, []))}
        strong = [f"{n}:{k}" for n, e in per.items() for k in ("question", "same_grounding") if e[k]]
        strong += [f"{n}:jaccard>=0.5" for n, e in per.items() if e["jaccard_max"] >= 0.5]
        before = {n: {k: prior[item["id"]]["per_set"][n][k] for k in ("jaccard_max", "template", "family")}
                  for n in PG if n in prior[item["id"]]["per_set"]}
        now = {n: {k: per[n][k] for k in ("jaccard_max", "template", "family")} for n in PG}
        if before != now:
            differs.append({"id": item["id"], "before(git show)": before, "now(pg_imports)": now})
        if item["status"] == "holdout" and strong:
            holdout_new.append({"id": item["id"], "strong": strong})
        rows.append({"id": item["id"], "status": item["status"], "strong": strong, "per_set": per})
    summary = {"items": len(rows), "pg_imports_sha256": {n: sha256(p) for n, p in PG.items()},
               "strong_overlap_items": sum(bool(r["strong"]) for r in rows), "holdout_new_strong": holdout_new,
               "holdout_family_overlap(info)": {n: sum(1 for r in rows if r["status"] == "holdout" and r["per_set"][n]["family"]) for n in PG},
               "differs_from_precheck": len(differs)}
    (HERE / "recheck_pg_imports.json").write_text(json.dumps({"summary": summary, "differs": differs, "items": rows}, ensure_ascii=False, indent=1) + "\n",
                                                  encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
