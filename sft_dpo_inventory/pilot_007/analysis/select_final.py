# -*- coding: utf-8 -*-
"""최종 판정 후보 고르기(결정 V2). 모델 호출 없음. 측정 전에 실행·커밋한다.

    hfvenv/bin/python sft_dpo_inventory/pilot_007/analysis/select_final.py   # -> analysis/select_final.json

- 대상: B2단계 F 다섯(R1'', O4', 순서 seed 43·1016·7·11·2027), 100% checkpoint(`checkpoint-1811`).
- 기준: 개발 셋 평균 = valid98(98)·aux(51) 문항 정답률(k=4 표본 평균)을 문항 수로 가중한 평균 = 149문항 문항 평균.
  채점은 판정 도구와 같다(``compute_gates.load_arm``: 견고성 패치, grounding_ok). 이미 커밋된 B2 셀(`cells/b2_f_<seed>_{valid98,aux}_s1..4.json`)만 쓴다.
- 같으면 순서 seed 숫자가 작은 쪽. 주 셋·protected_final_v1은 쓰지 않는다.
- 고른 모델의 adapter 경로·sha256(`adapters_B2.json`과 대조)을 함께 적는다.
"""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
P7 = HERE.parent
ROOT = P7.parents[1]
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_006/gates"))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_006/post"))
import robust_scoring  # noqa: E402

robust_scoring.patch()
import compute_gates as CG  # noqa: E402

SEEDS = {"o43": 43, "o1016": 20261016, "o7": 7, "o11": 11, "o2027": 2027}
SETS = {"valid98": "sft_dpo_inventory/pilot_004/valid98/valid98_gold.yaml", "aux": "sft_dpo_inventory/pilot_002/aux_test/aux_test_gold.yaml"}
ADAPTER = "/home/hwkim/sftdpo_work/pilot_007/train_b2/B2-F-{o}/checkpoint-1811"


def main():
    rows = {}
    for o, s in SEEDS.items():
        cells = {st: [f"sft_dpo_inventory/pilot_007/cells/b2_f_{o}_{st}_s{k}.json" for k in range(1, 5)] for st in SETS}
        items, m, per_set = CG.load_arm(cells, SETS, with_tokens=False)
        ok = m["ok"]
        rows[o] = {"order_seed": s, "items": len(items), "dev_mean_pct": round(100 * float(ok.mean()), 4)}
        for st in SETS:
            _, ms, _ = CG.load_arm({st: cells[st]}, SETS, with_tokens=False)
            rows[o][f"{st}_pct"] = round(100 * float(ms["ok"].mean()), 4)
            rows[o][f"{st}_items"] = int(ms["ok"].shape[0])
        rows[o]["check_weighted"] = round((rows[o]["valid98_pct"] * rows[o]["valid98_items"] + rows[o]["aux_pct"] * rows[o]["aux_items"])
                                          / (rows[o]["valid98_items"] + rows[o]["aux_items"]), 4)
    best = sorted(rows, key=lambda o: (-rows[o]["dev_mean_pct"], rows[o]["order_seed"]))[0]
    ad = Path(ADAPTER.format(o=best))
    rec = json.loads((P7 / "adapters_B2.json").read_text(encoding="utf-8"))["adapters"][f"B2-F-{best}"]["checkpoint-1811"]["adapter_sha256"]
    sha = hashlib.sha256((ad / "adapter_model.safetensors").read_bytes()).hexdigest()
    cfg_sha = hashlib.sha256((ad / "adapter_config.json").read_bytes()).hexdigest()
    out = {"rule": "결정 V2: B2 F 다섯 중 valid98·aux 문항 가중 평균(149문항) 최대, 같으면 순서 seed 작은 쪽; 주 셋·protected_final_v1 안 씀",
           "per_seed": rows, "selected": {"model": f"B2-F-{best}", "order_seed": rows[best]["order_seed"], "adapter_dir": str(ad),
                                          "adapter_model_sha256": sha, "adapter_config_sha256": cfg_sha, "matches_adapters_B2_json": sha == rec}}
    (HERE / "select_final.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
