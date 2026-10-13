"""P0 SFT 데이터 분포(v005 기준, batch006 보강 후보, 승인 시 예상 v006). 모델 호출 없음.

    python evaluation/partial_grounding/sft_p0/dataset_stats.py   # -> dataset_stats.json

od_role ≠ dimension_target: dimension_target이 있고 장소 od_role이 하나 이상이며, dimension_target 값이 장소 od_role 값 집합에
없는 문항(양 끝 제한 both와 grouping pickup/dropoff도 다름으로 센다).
scope 역조회: 사용자 scope concept와 값 없는 답 장소 concept가 함께 있는 문항.
"""
import collections
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def stats(payloads):
    c = collections.defaultdict(collections.Counter)
    for p in payloads:
        f = p.get("factors") or {}
        concepts = p.get("concepts") or []
        roles = {(x.get("attributes") or {}).get("od_role") for x in concepts if x.get("subtype") in ("place", "scope")} - {None}
        dt = f.get("dimension_target")
        c["items"]["total"] += 1
        c["dimension_target"][dt or "-"] += 1
        c["dimension"][f.get("dimension", "-")] += 1
        c["bucket"][f.get("bucket", "-")] += 1
        for x in concepts:
            if x.get("subtype") in ("place", "scope"):
                c["od_role"][(x.get("attributes") or {}).get("od_role", "-")] += 1
        if dt and roles:
            c["od_role_and_dimension_target"]["both_present"] += 1
            if dt not in roles:
                c["od_role_and_dimension_target"]["different"] += 1
        has_scope = any(x.get("subtype") == "scope" and x.get("value") for x in concepts)
        has_answer_place = any(x.get("subtype") == "place" and not x.get("value") for x in concepts)
        if has_scope and has_answer_place:
            c["scope_reverse"]["items"] += 1
    return {k: dict(v.most_common()) for k, v in c.items()}


def main():
    v005 = [json.loads(line)["target_p0"] for line in (HERE / "targets_v005_sft_p0.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()]
    cands = [json.loads(line) for line in (HERE / "augmentation_candidates.jsonl").read_text(encoding="utf-8").splitlines()
             if line.strip()]
    ok = [c for c in cands if c["status"] == "auto_ok"]
    out = {
        "note": "batch006 후보는 승인 전이다(결정 45). '예상 v006'은 자동 검사를 통과한 후보가 모두 승인된다고 가정한 값이다.",
        "v005": stats(v005),
        "batch006_drafted": {"count": len(cands), "by_gap": dict(collections.Counter(c["gap"] for c in cands)),
                             "status": dict(collections.Counter(c["status"] for c in cands))},
        "batch006_auto_ok": {"by_gap": dict(collections.Counter(c["gap"] for c in ok)), **stats([c["p0_target"] for c in ok])},
        "batch006_all_drafted": stats([c["p0_target"] for c in cands]),
        "projected_v006_if_all_auto_ok_approved": stats(v005 + [c["p0_target"] for c in ok]),
    }
    (HERE / "dataset_stats.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for k in ("v005", "batch006_auto_ok", "projected_v006_if_all_auto_ok_approved"):
        v = out[k]
        print(k, json.dumps({kk: v.get(kk) for kk in ("items", "dimension_target", "dimension", "od_role",
                                                         "od_role_and_dimension_target", "bucket", "scope_reverse", "by_gap")},
                            ensure_ascii=False))


if __name__ == "__main__":
    main()
