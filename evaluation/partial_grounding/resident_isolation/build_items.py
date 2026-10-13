"""격리 확인 실험(AUDIT.md 4절)의 10문항과 채점용 gold 파일을 만든다(모델 호출 없음).

- 후보: reviewed_gold_v005_t2pc SFT 111건(판정에 쓰지 않는 학습 gold. 평가셋 아님).
- 실행 전 자격 조건(결과를 보기 전에 정함, RUN_PLAN.md 2절): 승인 Full gold를 같은 운영 경로(mock 실행기, 조건 계층, 기준일
  2026-09-25)에 넣었을 때 재질의 없이 answered이고 Tool 호출이 있으며 장소 조회가 2개 이하인 문항. harness 채점(score)에
  gold_text가 필요하기 때문이다.
- 고르기: 자격 문항 id를 정렬한 뒤 random.Random(20261013).sample(…, 10). 파일 순서는 고른 순서 그대로 둔다.
- gold_text: 그 실행의 호출에서 장소 조회 결과 scope를 `$pickup.scope`·`$dropoff.scope`(장소 2개) 또는 `$area.scope`(1개)로 바꾼다.
  만든 gold로 같은 실행을 채점해 match인지 확인한다.

    /data/hwkim/path_repeat_001/venv/py/bin/python evaluation/partial_grounding/resident_isolation/build_items.py
"""
import json
import random
import sys
from datetime import date
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))

import evaluate_vendor100 as EV  # noqa: E402
from geoflow import providers  # noqa: E402
from geoflow.pipeline import GeoFlowPipeline  # noqa: E402
from tests.test_geoflow import ScriptedClient, planner_response  # noqa: E402

SOURCE = ROOT / "training/generated/reviewed_gold_v005_t2pc/sft_train.jsonl"
SEED = 20261013
N = 10


def observe(question, payload):
    pipeline = GeoFlowPipeline.create(
        client=ScriptedClient([planner_response(payload)]), tool_executor=EV._executor(),
        aggregation_grounding="flat", clock=lambda: date(2026, 9, 25), condition_check=True,
        execution_profile=providers.profile_for(providers.MOCK, providers.LEGACY), condition_notes=False)
    try:
        return EV.run_item(pipeline, question)
    except AssertionError:          # 재질의가 일어났다
        return None


def fmt(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def gold_text(calls):
    places = [c for c in calls if c["tool"] == "get_place_scope"]
    final = [c for c in calls if c["tool"] != "get_place_scope"][-1]
    by_scope = {c["result"]: c for c in places if isinstance(c.get("result"), str)}
    refs = {}
    if len(places) == 1:
        refs[places[0]["result"]] = "area"
    elif len(places) == 2:
        pick = final["args"].get("scope_pickup")
        drop = final["args"].get("scope_dropoff")
        if pick in by_scope and drop in by_scope and pick != drop:
            places = [by_scope[pick], by_scope[drop]]
            refs = {pick: "pickup", drop: "dropoff"}
        else:
            return None
    lines = []
    for c in places:
        args = {k: v for k, v in c["args"].items() if not (k == "include_vicinity" and v is False)}
        lines.append(f"get_place_scope({', '.join(f'{k}={fmt(v)}' for k, v in args.items())})")
    args = {k: (f"${refs[v]}.scope" if isinstance(v, str) and v in refs else v) for k, v in final["args"].items()}
    if any("," in fmt(v) for v in args.values()):
        return None
    lines.append(f"{final['tool']}({', '.join(f'{k}={fmt(v)}' for k, v in args.items())})")
    return "\n".join(lines)


def main():
    records = [json.loads(line) for line in SOURCE.read_text(encoding="utf-8").splitlines() if line.strip()]
    eligible = {}
    for r in records:
        sid = r["metadata"]["source_record_id"]
        q = r["messages"][1]["content"]
        observed = observe(q, json.loads(r["messages"][-1]["content"]))
        if not observed or observed["outcome"] != "answered" or not observed["calls"]:
            continue
        if sum(c["tool"] == "get_place_scope" for c in observed["calls"]) > 2:
            continue
        text = gold_text(observed["calls"])
        if text is None:
            continue
        item = {"id": sid, "question": q, "gold_text": text}
        loaded = dict(item, gold=EV.parse_calls(text), expected_outcome="answered")
        if EV.score(loaded, observed)[0] != "match":
            continue
        eligible[sid] = item
    chosen = random.Random(SEED).sample(sorted(eligible), N)
    doc = {"note": "격리 확인 실험용(AUDIT.md 4절, RUN_PLAN.md). 판정에 쓰지 않는 v005 학습 gold에서 고정 seed로 골랐다. "
                   "gold_text는 승인 Full gold를 mock 운영 경로에 넣은 호출에서 만들었다.",
           "source": str(SOURCE.relative_to(ROOT)), "seed": SEED, "eligible": len(eligible),
           "items": [eligible[sid] for sid in chosen]}
    # evaluation/**/*.yaml은 학습 데이터 보호 원본이므로 JSON으로 둔다(RESULT.md 6절).
    (HERE / "items_gold.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"eligible": len(eligible), "chosen": chosen}, ensure_ascii=False))


if __name__ == "__main__":
    main()
