# -*- coding: utf-8 -*-
"""aux_test_v1(``pilot_prep_005/sets/aux_test_items.json``, 결정 46)을 ``evaluate_vendor100.py --gold``가 읽는 한 파일로 모은다.

    python sft_dpo_inventory/pilot_002/aux_test/build_aux_yaml.py

- ``pilot_001_analysis/decision43/build_valid98_yaml.py``와 같은 방법이다. 문항 내용·라벨은 원본 YAML 그대로 옮긴다(고치지 않음).
  id만 HF 기록(``pilot_prep_005/sets/runs/aux_test_base.json``)과 같은 ``set/id``로 바꾼다.
- 원본 sha256을 목록과 대조하고, 목록 sha256이 PROTOCOL_v2 7절의 값과 같은지 확인한다. 결과: ``aux_test_gold.yaml``(평가 전용).
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

SPEC = ROOT / "sft_dpo_inventory/pilot_prep_005/sets/aux_test_items.json"
SPEC_SHA256 = "692b792fdfd1a95f9bd46c27262ed347d816076d15744070c1ca35ac25779aa0"  # PROTOCOL_v2 7절
assert hashlib.sha256(SPEC.read_bytes()).hexdigest() == SPEC_SHA256
spec = json.loads(SPEC.read_text(encoding="utf-8"))
for path, digest in spec["sources_sha256"].items():
    assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest, path
raw, items = {}, []
for ref in spec["items"]:
    if ref["path"] not in raw:
        raw[ref["path"]] = {str(i["id"]): i for i in yaml.safe_load((ROOT / ref["path"]).read_text(encoding="utf-8"))["items"]}
    item = dict(raw[ref["path"]][ref["id"]])
    item["id"] = f"{ref['set']}/{ref['id']}"
    items.append(item)
document = {"note": "aux_test_v1(결정 42·46) 평가 전용 모음. 원본: " + ", ".join(spec["sources_sha256"]) +
            f". 목록 sha256 {SPEC_SHA256}. 학습·checkpoint 선택·annotation에 쓰지 않음.", "items": items}
out = HERE / "aux_test_gold.yaml"
out.write_text(yaml.safe_dump(document, allow_unicode=True, sort_keys=False, width=1000), encoding="utf-8")
loaded = EV.load_gold(out)["items"]
assert len(loaded) == 51
for ref, item in zip(spec["items"], loaded):
    orig = {i["id"]: i for i in EV.load_gold(ROOT / ref["path"])["items"]}[ref["id"]]
    assert {k: v for k, v in item.items() if k != "id"} == {k: v for k, v in orig.items() if k != "id"}, ref
hf = json.loads((ROOT / "sft_dpo_inventory/pilot_prep_005/sets/runs/aux_test_base.json").read_text(encoding="utf-8"))
assert [r["id"] for r in hf["rows"]] == [i["id"] for i in loaded], "HF 기록과 문항 순서가 다르다"
print(out.relative_to(ROOT), len(loaded), hashlib.sha256(out.read_bytes()).hexdigest())
