"""대상 문항 목록(gold로 정함)을 만든다. CPU 전용, 모델 출력은 읽지 않는다.

정의는 fare_dissociation_check.py 26–45행을 그대로 옮긴 것이다(파일을 import하면 분석 전체가 돌기 때문에 복사).
    python make_targets.py REPO OUT.json
출력: H-dev 요금 문항(171)과 그중 장소 조회가 필요한 문항(147)의 id, 장소 이름, 목록 sha256.
목록 sha256 = sha256(json.dumps(sorted_ids).encode()) (json 기본 설정).
"""
import hashlib
import json
import re
import sys

import yaml


def parse_gold(text):
    calls = []
    for line in (text or "").split("\n"):
        m = re.match(r"\s*(\w+)\((.*)\)\s*$", line)
        if m:
            args = dict(kv.split("=", 1) for kv in m.group(2).split(", ") if "=" in kv)
            calls.append((m.group(1), {k.strip(): v.strip() for k, v in args.items()}))
    return calls


def targets(repo):
    path = f"{repo}/sft_dpo_inventory/ablation_012/e2/h_dev.yaml"
    raw = open(path, "rb").read()
    gold = yaml.safe_load(raw.decode("utf-8"))
    t1 = {}
    for it in gold["items"]:
        calls = parse_gold(it["gold_text"])
        analysis = [c for c in calls if c[0] != "get_place_scope"]
        place = [c for c in calls if c[0] == "get_place_scope"]
        if analysis and analysis[0][0] == "get_trip_metrics":
            t1[it["id"]] = place[0][1].get("name") if place else None
    ids = sorted(t1)
    need = [i for i in ids if t1[i]]
    return {
        "gold": "sft_dpo_inventory/ablation_012/e2/h_dev.yaml",
        "gold_sha256": hashlib.sha256(raw).hexdigest(),
        "definition": "fare_dissociation_check.py 26-45행: 첫 분석 호출이 get_trip_metrics인 문항 = 요금 문항, 그중 gold에 get_place_scope가 있는 문항 = 대상",
        "fare_ids": ids,
        "fare_ids_sha256": hashlib.sha256(json.dumps(ids).encode()).hexdigest(),
        "target_ids": need,
        "target_ids_sha256": hashlib.sha256(json.dumps(need).encode()).hexdigest(),
        "target_place": {i: t1[i] for i in need},
    }


if __name__ == "__main__":
    out = targets(sys.argv[1])
    with open(sys.argv[2], "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(len(out["fare_ids"]), len(out["target_ids"]), out["target_ids_sha256"])
