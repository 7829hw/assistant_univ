# -*- coding: utf-8 -*-
"""P0.3 판정용 셋 sel154(결정 61)을 ``evaluate_vendor100.py --gold``가 읽는 한 파일로 모은다. 모델을 부르지 않는다.

    python evaluation/partial_grounding/ab_p0_3/build_holdout.py

- 문항: 결정 46의 선택용 후보 154 = selection_v1(100, ``selection_items.json`` 순서) + 후보 중 뽑히지 않은 54(``survey_sets.json``의
  ``selection_pool_rest.ids`` 순서). 문항 내용·라벨은 원본 YAML 그대로이고 id만 ``set/id``로 바꾼다.
- 확인(질문 문장은 출력하지 않는다):
  1. selection_items.json sha256이 PROTOCOL_v2 7절 값과 같고, 원본 YAML sha256이 목록과 같다.
  2. 154문항 id 중복 없음, selection_v1과 나머지 54의 교집합 없음.
  3. 정답 grounding을 Full 그대로와 Partial(to_partial)로 같은 pipeline에 넣으면 154문항 모두 같은 결과이고 정답 범주다.
- 결과: ``sel154_gold.yaml``, ``sel154_check.json``(수와 범주만).
"""
import collections
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "evaluation" / "partial_grounding"))
import evaluate_vendor100 as EV  # noqa: E402
from replay_partial import to_partial  # noqa: E402

spec = importlib.util.spec_from_file_location("cc98", ROOT / "evaluation/partial_grounding/ab_valid98/contract_check.py")
CC = importlib.util.module_from_spec(spec)
spec.loader.exec_module(CC)

SEL = ROOT / "sft_dpo_inventory/pilot_prep_005/sets/selection_items.json"
SEL_SHA256 = "405af9c879ff2989374f6285195467793ee38a4b61fe867919e6eae8893cad25"  # PROTOCOL_v2 7절
SURVEY = HERE / "survey_sets.json"
SURVEY_SETS = ROOT / "sft_dpo_inventory/pilot_prep_004/sets/survey.json"
OUT = HERE / "sel154_gold.yaml"


def main():
    assert hashlib.sha256(SEL.read_bytes()).hexdigest() == SEL_SHA256
    sel = json.loads(SEL.read_text(encoding="utf-8"))
    for path, digest in sel["sources_sha256"].items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest, path
    paths = {name: s["path"] for name, s in json.loads(SURVEY_SETS.read_text(encoding="utf-8"))["sets"].items()}
    refs = [(r["set"], r["path"], str(r["id"])) for r in sel["items"]]
    rest = json.loads(SURVEY.read_text(encoding="utf-8"))["selection_pool_rest"]["ids"]
    refs += [(key.split("/", 1)[0], paths[key.split("/", 1)[0]], key.split("/", 1)[1]) for key in rest]
    keys = [f"{s}/{i}" for s, _, i in refs]
    assert len(keys) == 154 and len(set(keys)) == 154
    assert not {f"{r['set']}/{r['id']}" for r in sel["items"]} & set(rest)
    docs, items = {}, []
    for set_name, path, item_id in refs:
        if path not in docs:
            docs[path] = {str(i["id"]): i for i in yaml.safe_load((ROOT / path).read_text(encoding="utf-8"))["items"]}
        item = dict(docs[path][item_id])
        item["id"] = f"{set_name}/{item_id}"
        items.append(item)
    sources = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in sorted({p for _, p, _ in refs})}
    document = {"note": "sel154(결정 61) P0.3 prompt contract 판정 전용. selection_v1(결정 46) 100 + 같은 후보 pool의 나머지 54. "
                        "원본: " + ", ".join(sources) + ". 학습·annotation·데이터 설계에 쓰지 않음.", "items": items}
    OUT.write_text(yaml.safe_dump(document, allow_unicode=True, sort_keys=False, width=1000), encoding="utf-8")
    loaded = EV.load_gold(OUT)["items"]
    assert [i["id"] for i in loaded] == keys
    for (set_name, path, item_id), item in zip(refs, loaded):
        orig = {str(i["id"]): i for i in EV.load_gold(ROOT / path)["items"]}[item_id]
        assert {k: v for k, v in item.items() if k != "id"} == {k: v for k, v in orig.items() if k != "id"}, item["id"]
    EV.GOLD_PATH = OUT
    check = collections.Counter()
    bad = []
    for item in loaded:
        payload = EV.gold_grounding(item)
        partial, _ = to_partial(json.loads(json.dumps(payload)))
        full_view, partial_view = CC.run(item["question"], payload, item), CC.run(item["question"], partial, item)
        check[(full_view["category"], partial_view["category"], full_view == partial_view)] += 1
        if full_view != partial_view or full_view["category"] not in ("match", "expected_refusal"):
            bad.append(item["id"])
    result = {"gold_sha256": hashlib.sha256(OUT.read_bytes()).hexdigest(), "items": len(loaded),
              "by_set": dict(collections.Counter(k.split("/")[0] for k in keys)),
              "expected": dict(collections.Counter(i.get("expected_outcome", "answered") for i in loaded)),
              "sources_sha256": sources,
              "gold_pipeline_check": {f"full={a} partial={b} same={c}": n for (a, b, c), n in check.items()},
              "not_passing": bad}
    (HERE / "sel154_check.json").write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
