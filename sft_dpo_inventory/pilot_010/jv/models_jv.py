# -*- coding: utf-8 -*-
"""pilot_010 JV(결정 273) 대상 모델 목록(결과와 무관하게 고정, PLAN_JV 1절). 변환·등록·측정·분석이 함께 쓴다.

- 필수 11: base Qwen3-8B@b968826d, SFT(B2F) 5 seed, RR+NM4(V4) 5 seed — 지시의 seed 순서 그대로.
- 선택 7: RR+NM8(V8) 7 seed(JG `adapters_check_main.json`의 순서).
- 줄이는 규칙(smoke 뒤 필수 예상 > 14시간): SFT·RR+NM4를 각 앞 3 seed로(`REDUCED`).
- adapter 경로·sha256 = 학생 BF16 셀이 쓴 것(`pilot_010/gpu/JG/adapters_check_main.json`, 기록값 = 관측값).
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
INV = HERE.parents[1]
JV = Path("/data/hwkim/sftdpo_work/pilot_010_jv")
BASE_SNAPSHOT = Path("/data/hwkim/sftdpo_work/hf-cache/hub/models--Qwen--Qwen3-8B/snapshots/b968826d9c46dd6066d109eabc6255188de91218")
BASE_BF16_GGUF = Path("/data/hwkim/sftdpo_work/gguf/qwen3-8b-b968826d-base-bf16.gguf")       # pilot_prep_001 변환본(읽기만)
BASE_BF16_SHA = "4bed31be"                                                                  # quant_recipe RECIPE.md 2절(앞 8자리)
BASE_OFFICIAL_Q4_SHA = "c55752ae518c9f07e72b03e3ad031e7efb157eab09fea201da91c1f88d681a20"    # 결정 75 base 공식 방식 Q4(재현 대조용)
OFFICIAL_QWEN3_8B_BLOB = "/data/hwkim/ollama/models/blobs/sha256-a3de86cd1c132c822487ededd47a324c50491393e6565cd14bafa40d0b8e686f"  # 읽기만

SFT_SEEDS = ("o43", "o1016", "o7", "o11", "o2027")
V4_SEEDS = ("o101", "o523", "o2029", "o31", "o20271027")
V8_SEEDS = ("o43", "o1016", "o7", "o3110380", "o1821915", "o5415284", "o3616422")
ARM_KEY = {"base": "base", "B2F": "b2f", "V4": "v4", "V8": "v8"}


def _adapters():
    d = json.loads((INV / "pilot_010/gpu/JG/adapters_check_main.json").read_text(encoding="utf-8"))["adapters"]
    return {k: {"path": v["path"], "sha256": v["recorded"]} for k, v in d.items()}


def model(arm, seed):
    """arm ∈ base|B2F|V4|V8 → 이름·adapter·Ollama 이름."""
    if arm == "base":
        name = "jv-qwen3-8b-base"
        return {"arm": "base", "seed": "base", "name": name, "adapter": None, "adapter_sha256": None, "ollama": f"geoflow-{name}:q4km-official-hfthink"}
    a = _adapters()[f"{arm}:{seed}"]
    name = f"jv-{ARM_KEY[arm]}-{seed}"
    return {"arm": arm, "seed": seed, "name": name, "adapter": a["path"], "adapter_sha256": a["sha256"], "ollama": f"geoflow-{name}:q4km-official-hfthink"}


def required(reduced=False):
    n = 3 if reduced else 5
    return [model("base", "base")] + [model("B2F", s) for s in SFT_SEEDS[:n]] + [model("V4", s) for s in V4_SEEDS[:n]]


def optional():
    return [model("V8", s) for s in V8_SEEDS]


def all_models():
    return required() + optional()
