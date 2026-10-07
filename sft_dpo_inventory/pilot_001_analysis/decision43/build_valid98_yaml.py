# -*- coding: utf-8 -*-
"""결정 43-2: valid98(``pilot_001/valid98/valid98_items.json``)을 ``evaluate_vendor100.py --gold``가 읽는 한 파일로 모은다.

    python sft_dpo_inventory/pilot_001_analysis/decision43/build_valid98_yaml.py

- 문항 내용·라벨은 원본 YAML 그대로 옮긴다(고치지 않음). id만 HF valid98 기록과 같은 ``set/id``로 바꾼다.
- 원본 sha256을 ``valid98_items.json``과 대조한다. 결과: ``valid98_gold.yaml``(평가 전용, 학습 입력 아님).
"""
import hashlib
import json
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
import evaluate_vendor100 as EV  # noqa: E402

spec_path = ROOT / "sft_dpo_inventory/pilot_001/valid98/valid98_items.json"
spec = json.loads(spec_path.read_text(encoding="utf-8"))
for path, digest in spec["sources_sha256"].items():
    assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest, path
raw = {}
items = []
for ref in spec["items"]:
    if ref["path"] not in raw:
        raw[ref["path"]] = {str(i["id"]): i for i in yaml.safe_load((ROOT / ref["path"]).read_text(encoding="utf-8"))["items"]}
    item = dict(raw[ref["path"]][ref["id"]])
    item["id"] = f"{ref['set']}/{ref['id']}"
    items.append(item)
document = {"note": "valid98(결정 29) 평가 전용 모음. 원본: " + ", ".join(spec["sources_sha256"]) +
            f". 목록 sha256 {hashlib.sha256(spec_path.read_bytes()).hexdigest()}. 학습 입력 아님.", "items": items}
out = HERE / "valid98_gold.yaml"
out.write_text(yaml.safe_dump(document, allow_unicode=True, sort_keys=False, width=1000), encoding="utf-8")
loaded = EV.load_gold(out)["items"]
assert len(loaded) == 98
# 원본 loader로 읽은 것과 같은지(id 제외) 확인한다.
for ref, item in zip(spec["items"], loaded):
    orig = {i["id"]: i for i in EV.load_gold(ROOT / ref["path"])["items"]}[ref["id"]]
    assert {k: v for k, v in item.items() if k != "id"} == {k: v for k, v in orig.items() if k != "id"}, ref
print(out.relative_to(ROOT), len(loaded), hashlib.sha256(out.read_bytes()).hexdigest())
