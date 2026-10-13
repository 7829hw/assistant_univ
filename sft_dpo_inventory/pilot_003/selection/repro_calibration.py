# -*- coding: utf-8 -*-
"""HF-base 재현 확인(PLAN 3절): pilot_003 HF-base(selection_v2, k=4)와 calibration_001 HF-base(selection_v1, 같은 seed)의 같은 98문항 비교.
선택 기준값으로 쓰지 않는다. 모델 호출 없음.

    python sft_dpo_inventory/pilot_003/selection/repro_calibration.py

- 표본 k마다 문항별 원문 sha256(raw_sha256)·grounding_ok가 같은지 센다. 결과는 ``selection/repro_calibration.json``.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
IDS = (HERE / "selection_v2_ids.txt").read_text(encoding="utf-8").strip().split(",")


def rows(path):
    d = json.loads(path.read_text(encoding="utf-8"))
    return d["meta"], {r["id"]: r for r in d["rows"]}


def main():
    out = {"items": len(IDS), "samples": []}
    for k in range(1, 5):
        mc, c = rows(ROOT / f"sft_dpo_inventory/calibration_001/runs/HF-base_s{k}.json")
        mp, p = rows(HERE / f"runs/HF-base_s{k}.json")
        same_raw = sum(1 for i in IDS if [x.get("raw_sha256") for x in c[i].get("hf_calls") or []]
                       == [x.get("raw_sha256") for x in p[i].get("hf_calls") or []])
        ok_c = sum(bool(c[i].get("grounding_ok")) for i in IDS)
        ok_p = sum(bool(p[i].get("grounding_ok")) for i in IDS)
        diff = sorted(i for i in IDS if bool(c[i].get("grounding_ok")) != bool(p[i].get("grounding_ok")))
        dev = lambda m: (m.get("hf") or {}).get("device_uuid")
        out["samples"].append({"sample": k, "same_raw_calls_items": same_raw, "grounding_ok_calibration": ok_c, "grounding_ok_pilot003": ok_p,
                               "grounding_ok_differs": diff, "device_calibration": dev(mc), "device_pilot003": dev(mp)})
    (HERE / "repro_calibration.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
