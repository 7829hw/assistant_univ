# -*- coding: utf-8 -*-
"""selection_v1·valid98 기록(HF·Ollama)을 같은 모양으로 읽는다. 모델 호출 없음.

- 셀 목록(``CELLS``)과 gold(``gold_items``), 문항마다 grounding 요약(``view``)을 준다.
- 업체 100과 aux_test_v1 기록은 읽지 않는다(결정 59).
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import evaluate_vendor100 as EV  # noqa: E402

INV = ROOT / "sft_dpo_inventory"
GOLD = {
    "selection_v1": INV / "conversion_diag/selection_gold.yaml",
    "valid98": INV / "pilot_001_analysis/decision43/valid98_gold.yaml",
}
SEL = INV / "pilot_002/selection/runs"
CD = INV / "conversion_diag/selection"
#: (셋, 셀 이름) → (경로, 경로 종류, 설명)
CELLS = {
    ("selection_v1", "HF-base"): (INV / "pilot_prep_005/sets/runs/selection_base.json", "HF", "base Qwen3-8B@b968826d BF16 (HF-E 조건)"),
    **{("selection_v1", f"HF-sft{s}"): (SEL / f"sel_sft_step{s}.json", "HF", f"pilot_002 SFT step {s}") for s in (190, 380, 570, 758)},
    **{("selection_v1", f"HF-dpo{s}"): (SEL / f"sel_dpo_step{s}.json", "HF", f"pilot_002 DPO step {s}") for s in (72, 144, 216, 288)},
    ("selection_v1", "E"): (CD / "E.json", "Ollama", "공식 qwen3:8b Q4_K_M, 공식 TEMPLATE"),
    ("selection_v1", "c"): (CD / "c.json", "Ollama", "공식 qwen3:8b Q4_K_M, HF 형식 TEMPLATE"),
    ("selection_v1", "B-conv"): (CD / "B-conv.json", "Ollama", "직접 변환 base Q4_K_M, HF 형식 TEMPLATE"),
    ("selection_v1", "d"): (CD / "d.json", "Ollama", "직접 변환 base Q8_0, HF 형식 TEMPLATE"),
    ("selection_v1", "Ollama-final"): (CD / "Ollama-final.json", "Ollama", "pilot_002 최종(DPO 144) 병합 Q4_K_M, HF 형식 TEMPLATE"),
    ("selection_v1", "e"): (CD / "e.json", "Ollama", "pilot_002 최종(DPO 144) 병합 Q8_0, HF 형식 TEMPLATE"),
    ("valid98", "HF-base"): (INV / "pilot_prep_003/valid100/runs/base.json", "HF", "base(HF-E 조건, valid100 기록에서 98문항)"),
    ("valid98", "HF-p001-sft124"): (INV / "pilot_001/valid98/runs/sft_step124.json", "HF", "pilot_001 SFT step 124"),
    ("valid98", "HF-p001-dpo212"): (INV / "pilot_001/valid98/runs/dpo_step212.json", "HF", "pilot_001 최종 DPO step 212"),
    ("valid98", "HF-sft380"): (INV / "pilot_002/valid98/valid98_sft.json", "HF", "pilot_002 SFT step 380"),
    ("valid98", "HF-dpo144"): (INV / "pilot_002/valid98/valid98_final.json", "HF", "pilot_002 최종 DPO step 144"),
    ("valid98", "B-conv"): (INV / "pilot_001_analysis/decision43/valid98_B-conv.json", "Ollama", "직접 변환 base Q4_K_M"),
    ("valid98", "Ollama-p001-final"): (INV / "pilot_001_analysis/decision43/valid98_Ollama-final.json", "Ollama", "pilot_001 최종 Q4_K_M"),
}


def gold_items(set_name):
    return {i["id"]: i for i in EV.load_gold(GOLD[set_name])["items"]}


def load(set_name, cell, ids=None):
    path, kind, _ = CELLS[(set_name, cell)]
    if not path.exists():
        return None
    rows = {r["id"]: r for r in json.loads(path.read_text(encoding="utf-8"))["rows"]}
    if ids is not None:
        rows = {k: v for k, v in rows.items() if k in ids}
    return rows


def view(grounding):
    """grounding 요약: measure subtype, 장소별 od_role, factors(dimension_target, taxi_status 등)."""
    if not grounding:
        return None
    concepts = grounding.get("concepts") or []
    measure = [c.get("subtype") for c in concepts if c.get("role") == "MEASURE"]
    places = [((c.get("value") or {}).get("name") if isinstance(c.get("value"), dict) else c.get("value"),
               (c.get("attributes") or {}).get("od_role"))
              for c in concepts if c.get("concept") == "LOCATION" and c.get("role") != "MEASURE"]
    return {"measure": measure[0] if measure else None, "places": places, "factors": dict(grounding.get("factors") or {})}


def gold_view(item):
    return view(EV.gold_grounding(item))
