# -*- coding: utf-8 -*-
"""``pilot_006_prep/self_samples/judge6.py``를 승인 corpus v5로 돌리는 wrapper(결정 233: batch012 승인분 포함). judge6·approved6·judge8은 고치지 않는다.

    hfvenv/bin/python sft_dpo_inventory/pilot_009/build/judge9.py --arm full --raw RAW.jsonl --out OUT.json [--questions INPUT.jsonl]

- ``approved6.VERSION = "v5"``, ``MANIFEST["v5"] = "manifest_v5.json"``, ``corpus_id``에 batch010·batch011·batch012(``b012-NNN`` → ``b012:b012-NNN``)를 더한다.
  판정 규칙은 judge6 그대로(r2 근접 대조 표본 판정에 쓴다; r1 거부 표본은 RC7 빌드에서 모델 거부 출력으로 따로 고른다).
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_006_prep/self_samples"))
import approved6 as AP  # noqa: E402

AP.VERSION = "v5"
AP.MANIFEST["v5"] = "manifest_v5.json"
_orig = AP.corpus_id


def corpus_id(raw_id):
    for p in ("b010-", "b011-", "b012-"):
        if raw_id.startswith(p):
            return f"{p[:-1]}:{raw_id}"
    return _orig(raw_id)


AP.corpus_id = corpus_id
import judge6  # noqa: E402

if __name__ == "__main__":
    judge6.main()
