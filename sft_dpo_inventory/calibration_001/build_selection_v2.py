# -*- coding: utf-8 -*-
"""selection_v2 문항 목록(결정 65): selection_v1(``pilot_prep_005/sets/selection_items.json``)에서 옛 표기 때문에 X가 되는
indepv2/n10, indepv4/k32를 뺀 98문항. selection_v1 파일은 고치지 않는다.

    python sft_dpo_inventory/calibration_001/build_selection_v2.py
"""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
V1 = ROOT / "sft_dpo_inventory/pilot_prep_005/sets/selection_items.json"
REMOVED = {"indepv2/n10": "gold가 옛 표기(같은 장소 pickup·dropoff 두 개)라 지금 계약 표기(both)를 X로 판정",
           "indepv4/k32": "gold가 옛 표기(같은 장소 pickup·dropoff 두 개)라 지금 계약 표기(both)를 X로 판정"}


def main():
    raw = V1.read_bytes()
    v1 = json.loads(raw)
    items = [i for i in v1["items"] if f"{i['set']}/{i['id']}" not in REMOVED]
    assert len(v1["items"]) == 100 and len(items) == 98
    ids = [f"{i['set']}/{i['id']}" for i in items]
    out = {"name": "selection_v2", "decision": "65(결정 G)", "derived_from": str(V1.relative_to(ROOT)),
           "derived_from_sha256": hashlib.sha256(raw).hexdigest(), "removed": REMOVED,
           "kept_as_is": {"indepv3/m12": "장소 이름 오류라 그대로 둔다"},
           "use": "다음 선택 셋. selection_v1(PROTOCOL_v2 고정)은 고치지 않는다. 학습 입력으로 쓰지 않는다",
           "ids_sha256": hashlib.sha256("\n".join(ids).encode("utf-8")).hexdigest(),
           "ids_sha256_rule": "sha256('\\n'.join('set/id' 98개, selection_v1 순서))",
           "counts": {"items": len(items), "by_set": {s: sum(i["set"] == s for i in items) for s in dict.fromkeys(i["set"] for i in items)}},
           "sources_sha256": v1["sources_sha256"], "items": items}
    path = HERE / "selection_v2_items.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(path.name, hashlib.sha256(path.read_bytes()).hexdigest(), "ids", out["ids_sha256"], out["counts"])


if __name__ == "__main__":
    main()
