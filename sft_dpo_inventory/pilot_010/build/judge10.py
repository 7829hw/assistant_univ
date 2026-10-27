# -*- coding: utf-8 -*-
"""``pilot_006_prep/self_samples/judge6.py``를 승인 corpus v6로 돌리는 wrapper(결정 247: batch013 승인분 포함). ``pilot_009/build/judge9.py``의 사본(judge6·approved6·judge9는 고치지 않음).

    hfvenv/bin/python sft_dpo_inventory/pilot_010/build/judge10.py --arm full --raw RAW.jsonl --out OUT.json [--questions INPUT.jsonl]

- ``approved6.VERSION = "v6"``, ``MANIFEST["v6"] = "manifest_v6.json"``, ``corpus_id``에 batch010–013(``b013-NNN`` → ``b013:b013-NNN``)을 더한다. 판정 규칙은 judge6 그대로.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_006_prep/self_samples"))
import approved6 as AP  # noqa: E402

AP.VERSION = "v6"
AP.MANIFEST["v6"] = "manifest_v6.json"
_orig = AP.corpus_id


def corpus_id(raw_id):
    for p in ("b010-", "b011-", "b012-", "b013-"):
        if raw_id.startswith(p):
            return f"{p[:-1]}:{raw_id}"
    return _orig(raw_id)


AP.corpus_id = corpus_id
import judge6  # noqa: E402

if __name__ == "__main__":
    judge6.main()
