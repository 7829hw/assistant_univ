# -*- coding: utf-8 -*-
"""``pilot_006_prep/self_samples/judge6.py``를 승인 corpus v3로 돌리는 wrapper(결정 175: batch010 승인분 포함). judge6·approved6 파일은 고치지 않는다.

    hfvenv/bin/python sft_dpo_inventory/pilot_007/build/judge7.py --arm full|partial --raw RAW.jsonl --out OUT.json [--questions INPUT.jsonl]

- ``approved6.VERSION = "v3"``, ``MANIFEST["v3"] = "manifest_v3.json"``, ``corpus_id``에 batch010(``b010-NN`` → ``b010:b010-NN``)을 더한다. 판정 규칙은 judge6 그대로.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_006_prep/self_samples"))
import approved6 as AP  # noqa: E402

AP.VERSION = "v3"
AP.MANIFEST["v3"] = "manifest_v3.json"
_orig = AP.corpus_id


def corpus_id(raw_id):
    return f"b010:{raw_id}" if raw_id.startswith("b010-") else _orig(raw_id)


AP.corpus_id = corpus_id
import judge6  # noqa: E402

if __name__ == "__main__":
    judge6.main()
