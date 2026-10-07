# -*- coding: utf-8 -*-
"""결정 41·42: 새 선택용 셋·보조 시험 셋 후보가 될 보호 개발 셋의 사용 이력과 문항 조건을 센다. 모델을 부르지 않는다.

    python sft_dpo_inventory/pilot_prep_004/sets/survey_sets.py

- 대상: ``policy_scale.VENDOR_FORMAT_SETS``(정답 호출이 있어 정답 grounding을 역산할 수 있는 보호 셋). 사용자가 뺀 업체 100·stage_v7·
  heldout_v8·heldout_v9는 이력만 적는다. 다른 형식의 보호 셋(structured_grounding·reference·retrieval·paraphrase·parents)은 정답
  grounding이 없어(기대 plan·조건만) 조건 3(정답 grounding 통과)을 적용할 수 없으므로 문항 수만 적는다.
- 사용 이력(작업 지시 2의 다섯 가지 + batch004 설계):
  - v13 비교: ``grounding_v13/runs/dev_report.json``(개발 428문항), ``final_report.json``(최종 56문항). 문항 단위 결과
    (조용한 오답·U·측정값 오독 목록)를 보고에 적었는지도 센다.
  - v14 비교: ``grounding_v14/runs/ops``(운영 조건 검증)·``diag``(진단) 기록의 문항.
  - 오류 유형 분석: ``sft_dpo_inventory/generated/error_types_v13_model_name_only.json``(136문항, 문항별 결과).
  - inventory 공백 유형 도출: ``coverage_gap.py``(오류 유형 분석 산출물을 입력으로 씀 → 같은 136문항).
  - batch004 설계: 공백 유형(coverage_gap)을 근거로 했다(``batch004/REPORT.md``) → 같은 136문항이 간접 근거.
  - valid98: ``pilot_001/valid98/valid98_items.json``. pilot_001 분석: valid98과 업체 100(``pilot_001_analysis/analysis.json``).
- 문항 조건(작업 지시 2): 앞 셋과 정규화 질문 중복 없음, 정책·모호 라벨 아님(``policy_scale.exclusion_keys``), 정답 grounding 있음,
  장소가 mock으로 모두 풀림(``classify_providers``: mock·mock_and_reference·no_lookup), 정답 grounding을 현재 pipeline(평가와 같은
  구성: flat, 조건 계층 켬, mock+legacy, 기준일 2026-09-25)에 모델 응답 자리로 그대로 넣었을 때 기대 결과(답이면 v3 ``match``와
  ``grounding_ok``, 정지면 ``expected_refusal``)로 끝남, 학습 데이터(v004 reviewed gold; teacher 17문항은 v004 학습 질문이다)와
  정규화 질문·거친 의미 family·thor family_key·thor template_key가 겹치지 않음.
- 결과: ``survey.json``. 질문 문장은 넣지 않는다(셋·id·수·라벨 값만).
"""
import hashlib
import json
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory"))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_prep_002/provider"))

import classify_providers as CP  # noqa: E402
import evaluate_vendor100 as EV  # noqa: E402
from policy_scale import VENDOR_FORMAT_SETS, Families, coarse_family, exclusion_keys, question_key, stem  # noqa: E402

REFERENCE_DATE = date(2026, 9, 25)
USER_EXCLUDED = {"vendor100", "stage_v7", "heldout_v8", "heldout_v9"}
V004 = ROOT / "training/generated/reviewed_gold_v004_t2pc/sft_train.jsonl"
MOCK_OK = {"mock", "mock_and_reference", "no_lookup"}
OTHER_FORMAT = ["evaluation/structured_grounding/eval_questions_v1.yaml",
                "evaluation/structured_grounding/eval_questions_conditions_v1.yaml",
                "evaluation/structured_grounding/eval_questions_conditions_v2.yaml",
                "evaluation/structured_grounding/dev_questions.yaml",
                "evaluation/reference/reference_questions_v1.yaml", "evaluation/retrieval/retrieval_eval_v1.yaml"]


def _json(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def _ids_in(obj, out):
    """보고서 안의 'set/id' 꼴 문자열(문항 단위로 적힌 결과)을 모은다."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            _ids_in(k, out)
            _ids_in(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _ids_in(v, out)
    elif isinstance(obj, str) and "/" in obj and len(obj) < 40 and " " not in obj:
        out.add(obj)
    return out


def _rows_ids(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = data.get("rows") if isinstance(data, dict) else None
    return {str(r.get("id")) for r in rows or []}


def history():
    v13_name = {name: v13 for name, _, v13, _ in VENDOR_FORMAT_SETS}
    by_v13 = {v: n for n, v in v13_name.items() if v}
    hist = defaultdict(dict)
    dev = _json("evaluation/grounding_v13/runs/dev_report.json")
    final = _json("evaluation/grounding_v13/runs/final_report.json")
    for report, label in ((dev, "v13_dev_comparison(428)"), (final, "v13_final(56)")):
        mentioned = _ids_in(report["arms"], set()) | _ids_in(report.get("paired"), set())
        for arm in report["arms"].values():
            for s, v in (arm.get("by_set") or {}).items():
                name = by_v13.get(s)
                if name:
                    hist[name][label] = {"items": sum(v.values()) if isinstance(v, dict) else None}
        for key in mentioned:
            s = key.split("/")[0]
            if s in by_v13 and label in hist[by_v13[s]]:
                hist[by_v13[s]][label].setdefault("item_level_ids", set()).add(key)
    v14 = defaultdict(set)
    for path in sorted((ROOT / "evaluation/grounding_v14/runs").rglob("*.json")):
        try:
            ids = _rows_ids(path)
        except Exception:  # noqa: BLE001 - rows가 없는 보고 파일
            ids = set()
        if not ids:
            ids = _ids_in(json.loads(path.read_text(encoding="utf-8")), set())
        for key in ids:
            s = key.split("/")[0]
            if s in by_v13:
                v14[by_v13[s]].add(key)
    for name, ids in v14.items():
        hist[name]["v14(ops·diag·check)"] = {"item_level_ids": ids}
    err = _json("sft_dpo_inventory/generated/error_types_v13_model_name_only.json")
    err_ids = set(err["arms"]["q8_T2PC"]["items"])
    for key in err_ids:
        name = by_v13.get(key.split("/")[0])
        for label in ("error_type_analysis(136)", "inventory_gap(coverage_gap, 136)", "batch004_design(간접: 공백 유형)"):
            hist[name].setdefault(label, {"item_level_ids": set()})["item_level_ids"].add(key)
    valid98 = _json("sft_dpo_inventory/pilot_001/valid98/valid98_items.json")
    for ref in valid98["items"]:
        for label in ("valid98", "pilot_001_analysis"):
            hist[ref["set"]].setdefault(label, {"item_level_ids": set()})["item_level_ids"].add(f"{ref['set']}/{ref['id']}")
    hist["vendor100"].setdefault("pilot_001_analysis", {"item_level_ids": set()})["item_level_ids"].add("vendor100/*(100)")
    out = {}
    for name, labels in hist.items():
        out[name] = {label: {"items": v.get("items"), "item_level_ids": len(v.get("item_level_ids") or ()),
                             "item_level_id_list": sorted(v.get("item_level_ids") or ())}
                     for label, v in labels.items()}
    return out, err_ids, by_v13


class _GoldClient:
    """모델 응답 자리에 정답 grounding(JSON)을 그대로 돌려준다. 재질의에도 같은 값을 돌려준다."""

    def __init__(self, payload):
        self.text = json.dumps(payload, ensure_ascii=False)
        self.model = "gold"
        self.calls = 0

    def chat(self, messages, tools=None, **kwargs):
        self.calls += 1
        return {"message": {"role": "assistant", "content": self.text}, "done_reason": "stop"}


def pipeline_check(item, payload):
    sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_prep_002/valid_eval"))
    import provider_eval as P
    client = _GoldClient(payload)
    try:
        observed = EV.run_item(P.make_pipeline(client, "mock"), item["question"])
    except Exception as error:  # noqa: BLE001
        observed = EV._crashed(error)
    category, _ = EV.score(item, observed)
    ok, diffs = EV.grounding_check(item, observed["grounding"])
    expected = item.get("expected_outcome", "answered")
    passed = category == "match" and bool(ok) if expected == "answered" else category == "expected_refusal"
    return {"passed": passed, "category": category, "grounding_ok": bool(ok), "outcome": observed["outcome"],
            "error_code": observed["error_code"], "model_calls": client.calls,
            "grounding_diff_keys": sorted({d if isinstance(d, str) else d[0] for d in diffs or []})}


def main():
    from training.annotations.inventory import as_record, family_key
    from training.data.common import read_jsonl
    from training.data.split import template_key
    EV.REFERENCE_DATE = REFERENCE_DATE
    hist, err_ids, by_v13 = history()
    v004 = read_jsonl(V004)
    train = {"question": {question_key(r["messages"][1]["content"]) for r in v004},
             "coarse_family": {coarse_family(json.loads(r["messages"][-1]["content"])) for r in v004},
             "thor_family_key": {family_key(json.loads(r["messages"][-1]["content"])) for r in v004},
             "thor_template_key": {template_key(r) for r in v004}}
    excluded = exclusion_keys()
    seen = set()
    sets, items_out = {}, []
    for name, path, v13, author in VENDOR_FORMAT_SETS:
        document = EV.load_gold(ROOT / path)
        families = Families()
        counts = Counter()
        for item in document["items"]:
            key = f"{v13 or name}/{item['id']}"
            row = {"set": name, "id": item["id"], "key": key, "expected_outcome": item.get("expected_outcome", "answered")}
            fam = f"{name}:{stem(item['id'])}"
            families.find(fam)
            if item.get("contrast"):
                families.union(fam, f"{name}:contrast:{item['contrast']}")
            row["_fam"] = fam
            qk = question_key(item["question"])
            row["checks"] = checks = {}
            checks["duplicate_of_earlier_set"] = qk in seen
            seen.add(qk)
            checks["policy_or_ambiguous"] = key in excluded
            checks["in_error_type_analysis"] = key in err_ids
            try:
                payload = EV.gold_grounding(item)
            except Exception:  # noqa: BLE001
                payload = None
            checks["gold_grounding"] = bool(payload)
            if payload:
                cls, _ = CP.classify(payload)
                checks["place_class"] = cls
                checks["mock_resolves_all_places"] = cls in MOCK_OK
                checks["pipeline"] = pipeline_check(item, payload)
                checks["overlap_training"] = {
                    "question": qk in train["question"],
                    "coarse_family": coarse_family(payload) in train["coarse_family"],
                    "thor_family_key": family_key(payload) in train["thor_family_key"],
                    "thor_template_key": template_key(as_record(payload)) in train["thor_template_key"]}
                row["coarse_family"] = coarse_family(payload)
                row["thor_family_key"] = family_key(payload)
                row["type"] = type_profile(payload)
            row["eligible_conditions"] = bool(
                not checks["duplicate_of_earlier_set"] and not checks["policy_or_ambiguous"] and checks["gold_grounding"]
                and checks.get("mock_resolves_all_places") and checks["pipeline"]["passed"]
                and not any(checks["overlap_training"].values()))
            counts["items"] += 1
            counts["eligible_conditions"] += row["eligible_conditions"]
            items_out.append(row)
        for row in items_out:
            if row["set"] == name:
                row["family"] = families.find(row.pop("_fam"))
        sets[name] = {"path": path, "sha256": hashlib.sha256((ROOT / path).read_bytes()).hexdigest(), "author": author,
                      "user_excluded": name in USER_EXCLUDED, "history": hist.get(name, {}), **counts}
    other = {}
    import yaml
    for path in OTHER_FORMAT:
        doc = yaml.safe_load((ROOT / path).read_text(encoding="utf-8"))
        other[path] = {"items": len(doc.get("questions") or doc.get("items") or []),
                       "gold_grounding": "없음(기대 plan·조건만) — 조건 3을 적용할 수 없다"}
    out = {"sets": sets, "other_format_sets": other, "items": items_out}
    (HERE / "survey.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for name, s in sets.items():
        print(name, s["items"], "eligible", s["eligible_conditions"], "excluded" if s["user_excluded"] else "",
              {k: v["item_level_ids"] for k, v in s["history"].items()})


def type_profile(payload):
    """유형 분포용 라벨 값(작업 지시 2·3): 집계 유무, dimension, dimension_target, 측정값."""
    factors = payload.get("factors") or {}
    measures = sorted(f"{c.get('concept')}:{c.get('subtype')}" for c in payload.get("concepts") or []
                      if c.get("role") == "MEASURE")
    return {"aggregation": bool(factors.get("aggregation") or factors.get("bucket") or factors.get("rollup")),
            "dimension": factors.get("dimension"), "dimension_target": factors.get("dimension_target"),
            "measure": measures, "unsupported": bool(payload.get("unsupported"))}


if __name__ == "__main__":
    main()
