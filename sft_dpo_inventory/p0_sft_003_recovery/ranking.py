# -*- coding: utf-8 -*-
"""clean-trace ranking(PLAN.md 3절, 결과 전 고정). M2·M3 공통."""
import importlib.util
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("tqa", ROOT / "sft_dpo_inventory/p0_sft_003_prep/trace_quality_analysis.py")
TQA = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(TQA)
WAITHMM = re.compile(r"\b(Wait|Hmm)\b")
TIER_NAME = {1: "CLEAN_DIRECT", 2: "MINOR_SELF_CORRECTION", 3: "SELF_CORRECTED"}


def quality(thinking, target_p0):
    wrong = TQA.wrong_mentions(thinking, target_p0)
    wait_hmm = len(WAITHMM.findall(thinking))
    hedges = len(TQA.HEDGE.findall(thinking))
    tier = 3 if wrong else (1 if wait_hmm <= 2 else 2)
    return {"tier": tier, "tier_name": TIER_NAME[tier], "wrong_mentions": wrong, "wait_hmm": wait_hmm, "hedges": hedges,
            "thinking_chars": len(thinking)}


def rank_key(q, sample_index):
    return (q["tier"], len(q["wrong_mentions"]), q["hedges"], q["thinking_chars"], sample_index)
