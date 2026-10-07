# -*- coding: utf-8 -*-
"""결정 40-C: batch005(약 60건)의 유형별 후보 수 배분을 정한다. 보호 개발 셋은 집계 통계만 쓴다. 모델을 부르지 않는다.

    python sft_dpo_inventory/pilot_prep_004/type_target/type_target.py

- 유형(질문 하나 = 1): 정답 grounding의 factors로 정한다.
  - 집계: ``bucket``·``aggregation``·``rollup`` 중 하나라도 있으면 "집계 있음"(pilot_001 분석 3c의 ``factor:aggregation_spec``와 같다).
  - ``dimension``: 값이 있으면 그 단위. ``dimension_target``: 값(pickup·dropoff·both)이 있으면 그 값.
  - 칸: (집계 유무) × (dimension 유무) × (dimension_target 유무)의 8칸. 칸 안의 세부(단위, target 값, 장소 od_role, 측정값)는 배분용.
- 개발 셋 분포: ``policy_scale.VENDOR_FORMAT_SETS``에서 업체 100(결정 36)과 사본(cli_check_v14)을 뺀 보호 개발 셋 전체.
  앞 셋과 같은 질문은 한 번만, 정책·모호 라벨과 정답 grounding이 없는 문항은 뺀다. 산출물에는 셋별·전체 건수만 남긴다(문항 id·내용 없음).
- 학습 데이터 분포: pilot_001 SFT(``thinking_v004_t2pc_r1``)의 34질문 + teacher 17질문(결정 40-A) = 51질문의 reviewed gold
  (``reviewed_gold_v004_t2pc``). 레코드 단위(질문별 trace 수 가중) 분포는 D 적용 뒤 trace 수가 정해져야 하므로 참고로 r1만 적는다.
- 배분: 새 질문 n개를 더한 뒤의 칸 분포가 개발 셋 칸 분포에 가까워지게 한다. 기존 학습 질문은 빼지 않으므로 칸마다 부족분
  ``max(0, p_dev × (N+n) − n_train)``에 비례해 n을 나누고(최대 나머지 방식), 칸 안의 세부는 개발 셋의 칸 안 비율로 나눈다.
  차이는 총변동거리(TV = ½Σ|p−q|)와 세 주변 비율(집계 없음, dimension 있음, dimension_target 있음)로 보고한다.
- 레코드 단위(참고): r1 SFT 124 레코드 + teacher 정답 표본 수(``pilot_prep_003/teacher/*/summary.json``의 ``correct_samples_of_8``,
  D·tokenize·계약 필터 전). 새 질문의 레코드 수는 승인 뒤 trace 수집 전에는 알 수 없다.
- 결과: ``type_target.json``.
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory"))

import evaluate_vendor100 as EV  # noqa: E402
from policy_scale import VENDOR_FORMAT_SETS, exclusion_keys, question_key  # noqa: E402

N_NEW = 60
GOLD = ROOT / "training/generated/reviewed_gold_v004_t2pc/sft_train.jsonl"
R1_SFT = ROOT / "training/generated/thinking_v004_t2pc_r1/sft_train.jsonl"
TEACHER = [ROOT / f"sft_dpo_inventory/pilot_prep_003/teacher/targets_{n}.json" for n in ("known7", "batch004", "v003_valid")]
DEV_EXCLUDED = {"vendor100", "cli_check_v14"}
AGG = ("bucket", "aggregation", "rollup")


def profile(payload, answered=True):
    factors = payload.get("factors") or {}
    od = sorted({(c.get("attributes") or {}).get("od_role") or c.get("od_role") or "-"
                 for c in payload.get("concepts") or [] if c.get("concept") == "LOCATION"}) or ["(장소 없음)"]
    measures = sorted(f"{c.get('concept')}/{c.get('subtype')}" for c in payload.get("concepts") or []
                      if c.get("role") == "MEASURE")
    agg = any(k in factors for k in AGG)
    return {"cell": f"{'집계 있음' if agg else '집계 없음'}|dim {'있음' if factors.get('dimension') else '없음'}|"
                    f"dt {'있음' if factors.get('dimension_target') else '없음'}",
            "aggregation": agg, "dimension": factors.get("dimension"), "dimension_target": factors.get("dimension_target"),
            "od_role": "+".join(od), "measure": "+".join(measures) or "-", "answered": answered}


def distribution(profiles):
    n = len(profiles)
    cells = Counter(p["cell"] for p in profiles)
    return {"n": n, "cells": dict(sorted(cells.items())),
            "share": {c: round(v / n, 4) for c, v in sorted(cells.items())},
            "marginals": marginals(profiles)}


def marginals(profiles):
    n = len(profiles)
    return {"집계 없음": round(sum(not p["aggregation"] for p in profiles) / n, 4),
            "dimension 있음": round(sum(bool(p["dimension"]) for p in profiles) / n, 4),
            "dimension_target 있음": round(sum(bool(p["dimension_target"]) for p in profiles) / n, 4),
            "정지 target": round(sum(not p["answered"] for p in profiles) / n, 4)}


def tv(p, q):
    keys = set(p) | set(q)
    return round(0.5 * sum(abs(p.get(k, 0) - q.get(k, 0)) for k in keys), 4)


def largest_remainder(weights, total):
    s = sum(weights.values())
    if s <= 0:
        return {k: 0 for k in weights}
    raw = {k: total * w / s for k, w in weights.items()}
    out = {k: int(v) for k, v in raw.items()}
    for k in sorted(raw, key=lambda k: raw[k] - out[k], reverse=True)[:total - sum(out.values())]:
        out[k] += 1
    return out


def main():
    excluded = exclusion_keys()
    seen = set()
    dev, by_set = [], {}
    for name, path, v13, _ in VENDOR_FORMAT_SETS:
        if name in DEV_EXCLUDED:
            continue
        counts = Counter()
        for item in EV.load_gold(ROOT / path)["items"]:
            key = question_key(item["question"])
            if key in seen:
                counts["duplicate"] += 1
                continue
            seen.add(key)
            if f"{v13 or name}/{item['id']}" in excluded:
                counts["policy_or_ambiguous"] += 1
                continue
            try:
                payload = EV.gold_grounding(item)
            except Exception:  # noqa: BLE001
                payload = None
            if not payload:
                counts["no_gold_grounding"] += 1
                continue
            counts["used"] += 1
            dev.append(profile(payload, item.get("expected_outcome", "answered") == "answered"))
        by_set[name] = dict(counts)
    gold = {json.loads(line)["metadata"]["source_record_id"]: json.loads(line)
            for line in GOLD.read_text(encoding="utf-8").splitlines() if line.strip()}
    r1 = [json.loads(line) for line in R1_SFT.read_text(encoding="utf-8").splitlines() if line.strip()]
    r1_ids = sorted({r["metadata"]["source_record_id"] for r in r1})
    teacher_ids = sorted({t["source_record_id"] for path in TEACHER for t in json.loads(path.read_text(encoding="utf-8"))})
    train_ids = sorted(set(r1_ids) | set(teacher_ids))

    def gold_profile(rid):
        record = gold[rid]
        outcome = (record["metadata"].get("chosen_quality") or {}).get("outcome")
        return profile(json.loads(record["messages"][-1]["content"]), outcome == "answered")
    train = [gold_profile(i) for i in train_ids]
    r1_records = [gold_profile(r["metadata"]["source_record_id"]) for r in r1]
    teacher_correct = {}
    for name in ("known7", "batch004", "v003_valid"):
        summary = json.loads((ROOT / f"sft_dpo_inventory/pilot_prep_003/teacher/{name}/summary.json").read_text(encoding="utf-8"))
        for q in summary["questions"]:
            teacher_correct[q["source_record_id"]] = q["correct_samples_of_8"]
    teacher_records = [gold_profile(i) for i in teacher_ids for _ in range(teacher_correct.get(i, 0))]
    dev_d, train_d = distribution(dev), distribution(train)
    n_train = len(train)
    total = n_train + N_NEW
    deficit = {c: max(0.0, dev_d["share"][c] * total - train_d["cells"].get(c, 0)) for c in dev_d["share"]}
    alloc = largest_remainder(deficit, N_NEW)
    after_cells = Counter(train_d["cells"])
    after_cells.update(alloc)
    after_share = {c: v / total for c, v in after_cells.items()}
    # 칸 안 세부: 개발 셋의 같은 칸 문항의 (dimension, dimension_target, od_role) 조합 비율로 나눈다.
    detail = {}
    for cell, k in alloc.items():
        if not k:
            continue
        sub = Counter(f"dimension={p['dimension'] or '-'}, dimension_target={p['dimension_target'] or '-'}, od_role={p['od_role']}"
                      for p in dev if p["cell"] == cell)
        detail[cell] = {"allocated": k, "dev_within_cell": dict(sub.most_common()),
                        "allocation_within_cell": {s: v for s, v in largest_remainder(dict(sub), k).items() if v}}
    # 주변 비율(배분 뒤): 새 질문은 칸의 성질을 그대로 가진다.
    def m_after(flag):
        base = sum(flag(p) for p in train)
        add = sum(v for c, v in alloc.items() if flag({"aggregation": c.startswith("집계 있음"),
                                                       "dimension": "dim 있음" in c, "dimension_target": "dt 있음" in c,
                                                       "answered": True}))
        return round((base + add) / total, 4)
    after_marginals = {"집계 없음": m_after(lambda p: not p["aggregation"]),
                       "dimension 있음": m_after(lambda p: bool(p["dimension"])),
                       "dimension_target 있음": m_after(lambda p: bool(p["dimension_target"]))}
    # 같은 방식으로 n을 바꿨을 때 TV가 얼마나 줄어드는지(n 선택 근거).
    curve = {}
    for n in (0, 20, 40, 60, 80, 100, 150):
        t = n_train + n
        d = {c: max(0.0, dev_d["share"][c] * t - train_d["cells"].get(c, 0)) for c in dev_d["share"]}
        a = largest_remainder(d, n) if n else {}
        cells = Counter(train_d["cells"])
        cells.update(a)
        curve[n] = tv({c: v / t for c, v in cells.items()}, dev_d["share"])
    out = {
        "n_new": N_NEW,
        "dev_sets(집계만)": {"sets": by_set, "questions": len(dev)},
        "dev_distribution": dev_d,
        "dev_measure_share(참고)": {k: round(v / len(dev), 4) for k, v in Counter(p["measure"] for p in dev).most_common(12)},
        "dev_dimension_values": dict(Counter(p["dimension"] or "-" for p in dev).most_common()),
        "dev_dimension_target_values": dict(Counter(p["dimension_target"] or "-" for p in dev).most_common()),
        "training": {"questions": n_train, "r1_questions": len(r1_ids), "teacher_questions": len(teacher_ids),
                     "teacher_also_in_r1": len(set(teacher_ids) & set(r1_ids)), "distribution": train_d,
                     "dimension_values": dict(Counter(p["dimension"] or "-" for p in train).most_common()),
                     "dimension_target_values": dict(Counter(p["dimension_target"] or "-" for p in train).most_common()),
                     "r1_record_weighted(참고, 124 레코드)": distribution(r1_records),
                     "r1+teacher_record_weighted(참고, teacher는 정답 표본 수 그대로·필터 전)": distribution(r1_records + teacher_records)},
        "tv_before": tv(train_d["share"], dev_d["share"]),
        "allocation_by_cell": {c: v for c, v in alloc.items() if v},
        "allocation_detail": detail,
        "after": {"cells": dict(sorted(after_cells.items())), "share": {c: round(v, 4) for c, v in sorted(after_share.items())},
                  "marginals": after_marginals, "tv_after": tv(after_share, dev_d["share"])},
        "tv_by_n(같은 방식)": curve,
        "note": "기존 학습 질문은 빼지 않는다. 집계 있음 칸은 이미 개발 셋보다 많아 새 질문을 배분하지 않는다. "
                "레코드 단위 비율은 질문별 trace 수(D 적용 뒤)에 따라 달라지므로 pilot_002 데이터 구성 때 다시 센다.",
    }
    (HERE / "type_target.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("tv_before", "allocation_by_cell", "after", "tv_by_n(같은 방식)")}, ensure_ascii=False, indent=1))
    print(json.dumps(dev_d, ensure_ascii=False))
    print(json.dumps(train_d, ensure_ascii=False))


if __name__ == "__main__":
    main()
