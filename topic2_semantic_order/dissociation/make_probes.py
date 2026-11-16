"""X3 탐침 gold 만들기(PREREGISTRATION 5절). CPU 전용.

대상 147문항만 남기고 질문만 바꾼다(나머지 필드는 h_dev.yaml 그대로).
  (a) "(\\S+) 소속 택시" → "\\1에 등록된 택시"  (문항마다 정확히 한 번 해당해야 함)
  (b) "요금" → "수입"(모든 등장, 한 번 이상 해당해야 함)
    python make_probes.py REPO OUT_DIR
"""
import hashlib
import json
import re
import sys
from pathlib import Path

import yaml

repo, out = Path(sys.argv[1]).resolve(), Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
src = repo / "sft_dpo_inventory/ablation_012/e2/h_dev.yaml"
gold = yaml.safe_load(src.read_text(encoding="utf-8"))
targets = json.loads((repo / "topic2_semantic_order/dissociation/targets.json").read_text(encoding="utf-8"))
need = targets["target_ids"]
assert hashlib.sha256(json.dumps(need).encode()).hexdigest() == targets["target_ids_sha256"]
by_id = {str(it["id"]): it for it in gold["items"]}
RULES = {
    "a": (re.compile(r"(\S+) 소속 택시"), r"\1에 등록된 택시", lambda n: n == 1),
    "b": (re.compile(r"요금"), "수입", lambda n: n >= 1),
}
summary = {}
for name, (pat, rep, ok) in RULES.items():
    items, changes = [], []
    for i in need:
        it = dict(by_id[i])
        q2, n = pat.subn(rep, it["question"])
        if not ok(n):
            raise SystemExit(f"탐침 {name}: {i} 치환 {n}회")
        changes.append({"id": i, "before": it["question"], "after": q2})
        it["question"] = q2
        items.append(it)
    doc = {k: v for k, v in gold.items() if k != "items"}
    doc.update({"set": f"dissociation_probe_{name}", "note": "평가 전용 탐침(X3, topic2_semantic_order/dissociation/PREREGISTRATION.md 5절). "
                "h_dev.yaml 대상 147문항의 질문만 바꿈. 채점 결과는 쓰지 않고 지표 1–3만 잰다. 학습·checkpoint 선택·annotation 후보에 쓰지 않는다.",
                "probe_rule": f"{pat.pattern} -> {rep}", "derived_from": {"path": str(src.relative_to(repo)),
                "sha256": hashlib.sha256(src.read_bytes()).hexdigest(), "target_ids_sha256": targets["target_ids_sha256"]},
                "items": items})
    path = out / f"hdev147_probe_{name}.yaml"
    path.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False, width=1000), encoding="utf-8")
    (out / f"hdev147_probe_{name}_changes.json").write_text(json.dumps(changes, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    summary[name] = {"items": len(items), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
print(json.dumps(summary, ensure_ascii=False))
