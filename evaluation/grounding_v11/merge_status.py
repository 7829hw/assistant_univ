# -*- coding: utf-8 -*-
"""기준 arm의 운행 상태 대조 결과를 합친다: grounding_v10 기록(s01–s27) + grounding_v11 추가 실행(s28–s33).

    python evaluation/grounding_v11/merge_status.py OLD.json NEW.json OUT.json

같은 모델·prompt·코드·설정에서 문항만 나눠 실행했다(meta에 두 출처를 남긴다). 문항이 겹치면 멈춘다.
"""
import json
import sys
from pathlib import Path

old, new = (json.loads(Path(p).read_text(encoding="utf-8")) for p in sys.argv[1:3])
ids = {r["id"] for r in old["rows"]}
if ids & {r["id"] for r in new["rows"]}:
    raise SystemExit("겹치는 문항이 있습니다")
for key in ("model_digest", "planner_prompt_sha256"):
    if old["meta"].get(key) != new["meta"].get(key):
        raise SystemExit(f"{key}가 다릅니다: {old['meta'].get(key)} / {new['meta'].get(key)}")
merged = {"meta": dict(new["meta"], merged_from=sys.argv[1:3]), "rows": old["rows"] + new["rows"]}
merged["meta"]["gold_file"] = new["meta"]["gold_file"]
Path(sys.argv[3]).parent.mkdir(parents=True, exist_ok=True)
Path(sys.argv[3]).write_text(json.dumps(merged, ensure_ascii=False, indent=1), encoding="utf-8")
print(len(merged["rows"]), sys.argv[3])
