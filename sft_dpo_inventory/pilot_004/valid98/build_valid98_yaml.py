# -*- coding: utf-8 -*-
"""valid98(결정 29, ``pilot_001/valid98/valid98_items.json``)을 ``evaluate_vendor100``·vLLM 평가가 읽는 한 파일로 모은다(pilot_004 보조 보고).

    python sft_dpo_inventory/pilot_004/valid98/build_valid98_yaml.py

- ``conversion_diag/build_selection_yaml.py``와 같은 방법이다. 문항 내용·라벨은 원본 YAML 그대로(고치지 않음), id만 ``set/id``로 바꾼다.
  원본 sha256을 목록과 대조한다. 결과: ``valid98_gold.yaml``.
- 주의: valid98 원래 측정(``pilot_001/valid98/eval_valid98.py``)은 ``provider_eval.make_pipeline``을 쓴다. 이 파일로 잴 때는 업체 100·selection과 같은
  ``evaluate_vendor100`` pipeline(mock·legacy)이다. 그래서 pilot_003 이전의 valid98 greedy 기록과 직접 비교하지 않는다.
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

SPEC = ROOT / "sft_dpo_inventory/pilot_001/valid98/valid98_items.json"
SPEC_SHA256 = "512be78da0c1d3313a8d655502c7cbf73d44335962898297f76a945ce0080174"
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
document = {"note": "valid98(결정 29) 보조 보고용 모음(pilot_004). 원본: " + ", ".join(spec["sources_sha256"]) +
            f". 목록 sha256 {SPEC_SHA256}. 학습·checkpoint 선택·annotation에 쓰지 않음.", "items": items}
out = HERE / "valid98_gold.yaml"
out.write_text(yaml.safe_dump(document, allow_unicode=True, sort_keys=False, width=1000), encoding="utf-8")
loaded = EV.load_gold(out)["items"]
assert len(loaded) == 98
for ref, item in zip(spec["items"], loaded):
    orig = {i["id"]: i for i in EV.load_gold(ROOT / ref["path"])["items"]}[ref["id"]]
    assert {k: v for k, v in item.items() if k != "id"} == {k: v for k, v in orig.items() if k != "id"}, ref
print(out.relative_to(ROOT), len(loaded), hashlib.sha256(out.read_bytes()).hexdigest(), sorted(spec["sources_sha256"]))
