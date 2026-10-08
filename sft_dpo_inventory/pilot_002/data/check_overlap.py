# -*- coding: utf-8 -*-
"""pilot_002 학습 데이터와 평가 셋(selection_v1, aux_test_v1, valid98, 업체 100)의 겹침을 다시 확인한다. 모델을 부르지 않는다.

    python sft_dpo_inventory/pilot_002/data/check_overlap.py

- 학습 쪽: ``thinking_pilot002_t2pc``의 SFT·DPO 레코드가 쓰는 질문(문장과 gold grounding은 ``reviewed_gold_v005_t2pc``).
- 평가 쪽: 각 셋의 원본 YAML 문항(목록 파일 sha256을 PROTOCOL_v2 7절·pilot_001 기록과 대조), gold는 ``evaluate_vendor100.gold_grounding``.
- 키(문항마다): 정규화 질문(``policy_scale.question_key``), id, thor semantic template(``training.data.split.template_key``),
  thor semantic family(``training.annotations.inventory.family_key``). 거친 의미 family(``policy_scale.coarse_family``)는 참고로만 센다.
- 통과 조건: 네 셋 모두 질문·id·template 겹침 0. family 겹침은 selection_v1·aux_test_v1·valid98에서 0.
  업체 100의 family 겹침은 결정 15로 학습에 쓰기로 한 문항(b004-05, 06, 15, 30, 31)만 허용한다.
- 출력: ``overlap.json``(id와 키 종류만, 문장 없음). 실패하면 exit 1.
"""
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory"))

import evaluate_vendor100 as EV  # noqa: E402
from policy_scale import coarse_family, question_key  # noqa: E402
from training.annotations.inventory import as_record, family_key  # noqa: E402
from training.data.split import template_key  # noqa: E402

DATA = ROOT / "training/generated/thinking_pilot002_t2pc"
CORPUS = ROOT / "training/generated/reviewed_gold_v005_t2pc/sft_train.jsonl"
SETS = {
    "selection_v1": ("sft_dpo_inventory/pilot_prep_005/sets/selection_items.json",
                     "405af9c879ff2989374f6285195467793ee38a4b61fe867919e6eae8893cad25"),
    "aux_test_v1": ("sft_dpo_inventory/pilot_prep_005/sets/aux_test_items.json",
                    "692b792fdfd1a95f9bd46c27262ed347d816076d15744070c1ca35ac25779aa0"),
    "valid98": ("sft_dpo_inventory/pilot_001/valid98/valid98_items.json",
                "512be78da0c1d3313a8d655502c7cbf73d44335962898297f76a945ce0080174"),
}
VENDOR100 = ("evaluation/vendor100/gold.yaml", "f99bc5fdef623e973901e5b339ede3c7f4e36cfa133887ea933e9683a7d8b4f0")
DECISION15 = {"b004-05", "b004-06", "b004-15", "b004-30", "b004-31"}


def sha256(path):
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def read(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def keys(item_id, question, payload):
    return {"question": question_key(question), "id": str(item_id), "template": template_key(as_record(payload)),
            "family": family_key(payload), "coarse_family": coarse_family(payload)}


def main():
    used = {r["metadata"]["source_record_id"] for r in read(DATA / "sft_train.jsonl")} | \
           {r["metadata"]["source_record_id"] for r in read(DATA / "dpo_train.jsonl")}
    gold = {r["metadata"]["source_record_id"]: r for r in read(CORPUS)}
    train = {sid: keys(sid, gold[sid]["messages"][1]["content"], json.loads(gold[sid]["messages"][-1]["content"]))
             for sid in sorted(used)}
    index = defaultdict(lambda: defaultdict(set))
    for sid, k in train.items():
        for name, value in k.items():
            index[name][value].add(sid)
    eval_sets = {}
    for name, (path, digest) in SETS.items():
        if sha256(path) != digest:
            raise SystemExit(f"{name} 목록 sha256이 기록과 다르다")
        spec = json.loads((ROOT / path).read_text(encoding="utf-8"))
        docs, items = {}, []
        for ref in spec["items"]:
            if ref["path"] not in docs:
                docs[ref["path"]] = {i["id"]: i for i in EV.load_gold(ROOT / ref["path"])["items"]}
            item = docs[ref["path"]][ref["id"]]
            items.append((f"{ref['set']}/{ref['id']}", item))
        eval_sets[name] = items
    if sha256(VENDOR100[0]) != VENDOR100[1]:
        raise SystemExit("업체 100 gold sha256이 PROTOCOL과 다르다")
    eval_sets["vendor100"] = [(i["id"], i) for i in EV.load_gold(ROOT / VENDOR100[0])["items"]]
    out, failed = {"training_questions": len(train), "data": str(DATA.relative_to(ROOT)), "sets": {}}, []
    for name, items in eval_sets.items():
        hits = defaultdict(list)
        for eid, item in items:
            payload = EV.gold_grounding(item)
            k = keys(eid.split("/")[-1], item["question"], payload) if payload is not None else \
                {"question": question_key(item["question"]), "id": eid.split("/")[-1]}
            for kind, value in k.items():
                for sid in sorted(index[kind].get(value, ())):
                    hits[kind].append({"eval_id": eid, "train_id": sid})
        allowed_family = name == "vendor100"
        family_hits = hits.get("family", [])
        unexpected_family = [h for h in family_hits if not (allowed_family and h["train_id"] in DECISION15)]
        ok = not hits.get("question") and not hits.get("id") and not hits.get("template") and not unexpected_family
        out["sets"][name] = {"items": len(items), "ok": ok,
                             "question": hits.get("question", []), "id": hits.get("id", []),
                             "template": hits.get("template", []), "family": family_hits,
                             "family_allowed_decision15": [h for h in family_hits if h not in unexpected_family],
                             "coarse_family(info)": len({h["eval_id"] for h in hits.get("coarse_family", [])})}
        if not ok:
            failed.append(name)
    out["all_ok"] = not failed
    (HERE / "overlap.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({n: {k: (len(v) if isinstance(v, list) else v) for k, v in s.items()} for n, s in out["sets"].items()},
                     ensure_ascii=False, indent=1))
    print("all_ok", out["all_ok"])
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
