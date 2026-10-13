"""Partial P0 SFT용 학습·평가 데이터 inventory와 겹침 검사(모델 호출 없음).

- 학습 후보: reviewed_gold_v005_t2pc(SFT·DPO), thinking_pilot002_t2pc(SFT·DPO), 이전 판 v003·v004(참고).
- 평가·보호 셋: vendor100, valid98, sel154(selection_v1 100 + pool 나머지 54), aux_test_v1.
- 겹침 키는 pilot_002 검사기와 같다(`sft_dpo_inventory/pilot_002/data/check_overlap.py`의 keys: 정규화 질문, id, thor template,
  thor family). sel154는 이번에 처음 대조한다. 나머지 셋은 기존 overlap.json(pilot_002)을 인용한다.
- 변환 결과는 build_targets.py의 conversion_report.json을 읽는다.

    /data/hwkim/path_repeat_001/venv/py/bin/python evaluation/partial_grounding/sft_p0/inventory.py
"""
import importlib.util
import json
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory"))

import evaluate_vendor100 as EV  # noqa: E402

spec = importlib.util.spec_from_file_location("check_overlap", ROOT / "sft_dpo_inventory/pilot_002/data/check_overlap.py")
CO = importlib.util.module_from_spec(spec)
spec.loader.exec_module(CO)

GEN = ROOT / "training/generated"
SEL154 = ROOT / "evaluation/partial_grounding/ab_p0_3/sel154_gold.yaml"


def count(path):
    return sum(1 for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()) if Path(path).exists() else 0


def main():
    v005 = CO.read(GEN / "reviewed_gold_v005_t2pc/sft_train.jsonl")
    train = {r["metadata"]["source_record_id"]: CO.keys(r["metadata"]["source_record_id"], r["messages"][1]["content"],
                                                         json.loads(r["messages"][-1]["content"])) for r in v005}
    index = defaultdict(lambda: defaultdict(set))
    for sid, k in train.items():
        for name, value in k.items():
            index[name][value].add(sid)
    sel = EV.load_gold(SEL154)["items"]
    hits = defaultdict(list)
    for item in sel:
        payload = EV.gold_grounding(item)
        k = CO.keys(item["id"].split("/")[-1], item["question"], payload) if payload is not None else \
            {"question": CO.question_key(item["question"]), "id": item["id"].split("/")[-1]}
        for kind, value in k.items():
            for sid in sorted(index[kind].get(value, ())):
                hits[kind].append({"eval_id": item["id"], "train_id": sid})
    overlap_prev = json.loads((ROOT / "sft_dpo_inventory/pilot_002/data/overlap.json").read_text(encoding="utf-8"))
    conv = json.loads((HERE / "conversion_report.json").read_text(encoding="utf-8"))
    datasets = [
        {"name": "reviewed_gold_v005_t2pc/sft_train", "path": "training/generated/reviewed_gold_v005_t2pc/sft_train.jsonl",
         "items": count(GEN / "reviewed_gold_v005_t2pc/sft_train.jsonl"), "split": "train(승인 gold, 결정 13·47)",
         "full_target": "있음(assistant = Full planner JSON, thinking 없음)",
         "p0_convertible": f"{conv['v005_sft']['auto_pass']}/{conv['v005_sft']['records']} 자동 통과",
         "use_for_p0_sft": "주 입력"},
        {"name": "reviewed_gold_v005_t2pc/dpo_train", "path": "training/generated/reviewed_gold_v005_t2pc/dpo_train.jsonl",
         "items": count(GEN / "reviewed_gold_v005_t2pc/dpo_train.jsonl"), "split": "train(DPO 쌍)",
         "full_target": "chosen·rejected Full JSON", "p0_convertible": conv["v005_dpo"]["conversion"],
         "use_for_p0_sft": "SFT에는 쓰지 않음(DPO 단계 후보)"},
        {"name": "thinking_pilot002_t2pc/sft_train", "path": "training/generated/thinking_pilot002_t2pc/sft_train.jsonl",
         "items": count(GEN / "thinking_pilot002_t2pc/sft_train.jsonl"), "split": "train(pilot_002, 107질문)",
         "full_target": "thinking + Full JSON(HF·teacher trace)",
         "p0_convertible": {"json_part": conv["thinking_pilot002_sft"]["json_conversion"],
                            "thinking_mentions_full_fields": conv["thinking_pilot002_sft"]["thinking_full_field_mentions"]},
         "use_for_p0_sft": "JSON만 바꾸면 thinking이 Full 구조(role 등)를 계획한 채 남는다. P0 prompt로 trace를 다시 모으는 것을 권장"},
        {"name": "thinking_pilot002_t2pc/dpo_train", "path": "training/generated/thinking_pilot002_t2pc/dpo_train.jsonl",
         "items": count(GEN / "thinking_pilot002_t2pc/dpo_train.jsonl"), "split": "train(DPO full_response)",
         "full_target": "thinking + Full JSON", "p0_convertible": "검사 안 함", "use_for_p0_sft": "아니오"},
        {"name": "reviewed_gold_v003_t2pc / v004_t2pc", "path": "training/generated/reviewed_gold_v00{3,4}_t2pc",
         "items": {"v003_sft": count(GEN / "reviewed_gold_v003_t2pc/sft_train.jsonl") + count(GEN / "reviewed_gold_v003_t2pc/sft_valid.jsonl"),
                   "v004_sft": count(GEN / "reviewed_gold_v004_t2pc/sft_train.jsonl")},
         "split": "이전 판(v005에 포함)", "full_target": "Full JSON", "p0_convertible": "v005로 대체", "use_for_p0_sft": "아니오(중복)"},
    ]
    eval_sets = [
        {"name": "vendor100", "items": 100, "use": "평가 전용(CLAUDE.md 8, 결정 36)", "full_target": "gold_text(역산 가능)",
         "train_overlap": {k: len(v) for k, v in overlap_prev["sets"]["vendor100"].items() if isinstance(v, list)}},
        {"name": "valid98", "items": 98, "use": "보조 기록(결정 41·60), P0.x 설계에 씀", "full_target": "gold_text",
         "train_overlap": {k: len(v) for k, v in overlap_prev["sets"]["valid98"].items() if isinstance(v, list)}},
        {"name": "selection_v1", "items": 100, "use": "checkpoint 선택(결정 46·53)", "full_target": "gold_text",
         "train_overlap": {k: len(v) for k, v in overlap_prev["sets"]["selection_v1"].items() if isinstance(v, list)}},
        {"name": "aux_test_v1", "items": 51, "use": "판정에 쓰지 않는 보조 시험(결정 42)", "full_target": "gold_text",
         "train_overlap": {k: len(v) for k, v in overlap_prev["sets"]["aux_test_v1"].items() if isinstance(v, list)}},
        {"name": "sel154", "items": len(sel), "use": "P0.3 판정(결정 61, 1회 판정)", "full_target": "gold_text",
         "train_overlap_v005": {kind: len(hits.get(kind, [])) for kind in ("question", "id", "template", "family")},
         "train_overlap_v005_hits": dict(hits)},
    ]
    out = {"note": "모델 호출 없음. 평가 셋은 학습 target 생성에서 뺀다(결정 36·41·42·46·61, CLAUDE.md 8).",
           "datasets": datasets, "eval_sets": eval_sets,
           "pilot002_overlap_source": "sft_dpo_inventory/pilot_002/data/overlap.json (thinking_pilot002_t2pc 질문 기준, 결정 54)"}
    (HERE / "inventory.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"sel154_vs_v005": eval_sets[-1]["train_overlap_v005"], "hits": dict(hits)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
