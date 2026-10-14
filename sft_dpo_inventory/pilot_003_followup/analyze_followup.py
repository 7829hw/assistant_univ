# -*- coding: utf-8 -*-
"""pilot_003 후속 2: 기록만 쓰는 원인 분석(결정 85). 모델 호출 없음.

    python sft_dpo_inventory/pilot_003_followup/analyze_followup.py

a. aux_test_v1에서 HF-최종에 새로 U가 생긴 5문항(final_v12/f02, f31, f33, f50, f53)
   - 문항·표본마다 HF-base·HF-최종의 grounding_ok, 보고 분류, U 종류, 결과, 오류 유형, 차이(grounding_diffs).
   - 세 셋(selection_v2, aux_test_v1, 업체 100)에서 U 종류별 표본 수(HF-base → HF-최종). 업체 100 문항은 설명에만 쓴다(결정 36).
   - 학습 데이터(pilot_002·pilot_003)의 관련 형태 레코드 수: vicinity, od_role both, place 없음, dimension_target, taxi_status.
b. 실차 통행량
   - selection_v2 old44/g02·g04·indepv2/n33(HF-base, SFT 920, DPO 174)과 valid98 h30(SFT 920, DPO 174)의 원문(ignore 경로)에서
     첫 계획 호출의 thinking이 "실차 → trip"으로 추론하는지, 출력 measure가 무엇인지 센다. 보고서에는 수와 요지만 쓴다.
   - 학습 데이터에서 taxi_status occupied 레코드의 출처별 수와 DPO 쌍 수.
- 결과: ``analysis.json``(원문 문장 없음).
"""
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_003/vendor100"))
import judge_v3 as J  # noqa: E402  (analyze_cal 함수와 U 키 연결)

A = J.A
P3 = ROOT / "sft_dpo_inventory/pilot_003"
RAW3 = ROOT / "training/generated/pilot_003/raw"
NEW_U = ["final_v12/f02", "final_v12/f31", "final_v12/f33", "final_v12/f50", "final_v12/f53"]
DATA = {"pilot_002": ROOT / "training/generated/thinking_pilot002_t2pc", "pilot_003": ROOT / "training/generated/thinking_pilot003_t2pc"}
REAL_TRIP_SEL = ["old44/g02", "old44/g04", "indepv2/n33"]
# thinking 확인(같은 줄 안): "실차"를 "real trip"으로 옮김 / 실차와 trip_count를 잇는 문장 / occupied(실차 상태) 언급 / passage_count 언급
REAL_TRIP = re.compile(r"real[- ]trips?", re.I)
TRIP_READ = re.compile(r"실차[^\n]{0,160}trip_count|trip_count[^\n]{0,80}실차|실차[^\n]{0,40}refers to trips?", re.I)
OCCUPIED = re.compile(r"occupied", re.I)
PASSAGE_MENTION = re.compile(r"passage_count", re.I)


def answer_json(text):
    tail = text.split("</think>")[-1]
    m = re.search(r"\{.*\}", tail, re.S)
    try:
        return json.loads(m.group(0)) if m else None
    except json.JSONDecodeError:
        return None


def features(payload):
    if not isinstance(payload, dict):
        return set()
    out = set()
    concepts = payload.get("concepts") or []
    factors = payload.get("factors") or {}
    places = [c for c in concepts if c.get("concept") == "LOCATION"]
    if not places:
        out.add("no_place")
    if any((c.get("attributes") or {}).get("od_role") == "both" for c in places):
        out.add("od_role_both")
    if factors.get("vicinity"):
        out.add("vicinity")
    if factors.get("dimension_target"):
        out.add("dimension_target")
    if factors.get("dimension"):
        out.add("dimension")
    status = factors.get("taxi_status")
    if status:
        out.add(f"taxi_status_{status}")
    measure = next((c.get("subtype") for c in concepts if c.get("role") == "MEASURE"), None)
    if status == "occupied" and measure:
        out.add(f"occupied_measure_{measure}")
    return out


def read(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def data_features():
    out = {}
    for name, d in DATA.items():
        sft = Counter()
        by_source = defaultdict(Counter)
        questions = defaultdict(set)
        for r in read(d / "sft_train.jsonl"):
            src = "teacher" if r["metadata"]["source"] == "teacher" else "hf"
            f = features(answer_json(r["messages"][-1]["content"]))
            sft.update(f)
            by_source[src].update(f)
            for x in f:
                questions[x].add(r["metadata"]["source_record_id"])
        dpo = Counter()
        for r in read(d / "dpo_train.jsonl"):
            chosen = r["chosen"] if isinstance(r["chosen"], str) else r["chosen"][-1]["content"]   # 대화 형식 [{"role": "assistant", ...}]
            dpo.update(features(answer_json(chosen)))
        out[name] = {"sft_records": dict(sorted(sft.items())), "sft_records_by_source": {k: dict(sorted(v.items())) for k, v in by_source.items()},
                     "sft_questions": {k: len(v) for k, v in sorted(questions.items())}, "dpo_pairs(chosen)": dict(sorted(dpo.items()))}
    return out


def new_u_items():
    cfg = J.SETS["aux"]
    gold = {i["id"]: i for i in A.EV.load_gold(cfg["gold"])["items"]}
    out = {}
    for cell in ("HF-base", "HF-final"):
        samples, _ = J.load_cell(cfg, cell, gold)
        for k, s in enumerate(samples, 1):
            src = {r["id"]: r for r in json.loads((cfg["runs"] / f"aux_{cell}_s{k}.json").read_text(encoding="utf-8"))["rows"]}
            for i in NEW_U:
                r = s[i]
                out.setdefault(i, {"gold_features": sorted(features(A.EV.gold_grounding(gold[i])))}).setdefault(cell, []).append({
                    "sample": k, "ok": r["ok"], "class": r["class"], "u_flags": r["u_flags"], "outcome": r["outcome"],
                    "errors": [e for e in A.ERRORS if r[e]], "diffs": src[i].get("grounding_diffs"),
                    "output_features": sorted(features(src[i].get("grounding")))})
    for i, v in out.items():
        v["U_samples"] = {c: sum(x["class"] == A.CS.U_CLASS for x in v[c]) for c in ("HF-base", "HF-final")}
        v["ok_samples"] = {c: sum(x["ok"] for x in v[c]) for c in ("HF-base", "HF-final")}
    return out


def u_kinds():
    """세 셋에서 U 종류별 표본 수(HF-base → HF-최종). 종류는 U 플래그의 앞부분(U1:…, U2:vicinity 등)."""
    sets = {"selection_v2": (J.SETS["selftest"], "HF-base", "dpo_step174"),
            "aux_test_v1": (J.SETS["aux"], "HF-base", "HF-final"),
            "vendor100(설명에만)": (J.SETS["vendor100"], "HF-base", "HF-final")}
    out = {}
    for name, (cfg, a, b) in sets.items():
        gold = {i["id"]: i for i in A.EV.load_gold(cfg["gold"])["items"]}
        row = {}
        for label, cell in (("HF-base", a), ("HF-final", b)):
            samples, _ = J.load_cell(cfg, cell, gold)
            c = Counter()
            for s in samples:
                for r in s.values():
                    if r["class"] == A.CS.U_CLASS:
                        c.update(sorted({f.split(",")[0] for f in r["u_flags"]}))
            row[label] = {"U_item_samples": sum(r["class"] == A.CS.U_CLASS for s in samples for r in s.values()),
                          "samples": len(samples), "items": len(samples[0]), "flags": dict(sorted(c.items()))}
        out[name] = row
    return out


def thinking_of(r):
    if r.get("thinking") is not None:
        return r["thinking"]
    return A.CS.split_think(r["raw_text"])[0] or ""


def real_trip():
    cells = {"HF-base": [RAW3 / f"HF-base_s{k}_raw.jsonl" for k in range(1, 5)],
             "SFT_920": [RAW3 / f"sft_step920_s{k}_raw.jsonl" for k in range(1, 5)],
             "DPO_174(final)": [RAW3 / f"dpo_step174_s{k}_raw.jsonl" for k in range(1, 5)]}
    out = {"selection_v2": {}, "valid98_h30": {}}
    for cell, paths in cells.items():
        for i in REAL_TRIP_SEL:
            rec = Counter()
            for p in paths:
                first = None
                for r in read(p):
                    if r["id"] == i and (first is None or r.get("call", 0) < first.get("call", 0)):
                        first = r
                t = thinking_of(first)
                ans = answer_json(first.get("raw_text") or first.get("content") or "")
                measure = next((c.get("subtype") for c in (ans or {}).get("concepts", []) if c.get("role") == "MEASURE"), None)
                rec["samples"] += 1
                rec["thinking_translates_real_trip"] += bool(REAL_TRIP.search(t))
                rec["thinking_links_silcha_to_trip_count"] += bool(TRIP_READ.search(t))
                rec["thinking_mentions_occupied"] += bool(OCCUPIED.search(t))
                rec["thinking_mentions_passage_count"] += bool(PASSAGE_MENTION.search(t))
                rec[f"first_plan_measure:{measure}"] += 1
                rec["first_plan_taxi_status_occupied"] += ((ans or {}).get("factors") or {}).get("taxi_status") == "occupied"
            out["selection_v2"].setdefault(i, {})[cell] = dict(rec)
    for cell, name in (("SFT_920", "valid98_sft"), ("DPO_174(final)", "valid98_final")):
        rows = [r for r in read(RAW3 / f"{name}_raw.jsonl") if r["id"].endswith("h30")]
        first = min(rows, key=lambda r: r.get("call", 0))
        t = thinking_of(first)
        ans = answer_json(first.get("raw_text") or first.get("content") or "")
        out["valid98_h30"][cell] = {"calls": len(rows), "thinking_translates_real_trip": bool(REAL_TRIP.search(t)),
                                    "thinking_links_silcha_to_trip_count": bool(TRIP_READ.search(t)),
                                    "thinking_mentions_occupied": bool(OCCUPIED.search(t)),
                                    "thinking_mentions_passage_count": bool(PASSAGE_MENTION.search(t)),
                                    "first_plan_measure": next((c.get("subtype") for c in (ans or {}).get("concepts", [])
                                                                if c.get("role") == "MEASURE"), None),
                                    "first_plan_taxi_status": ((ans or {}).get("factors") or {}).get("taxi_status")}
    return out


def main():
    out = {"note": "모델 호출 없음. 원문 문장은 넣지 않는다.", "a_new_u_items": new_u_items(), "a_u_kinds_by_set": u_kinds(),
           "training_data_features": data_features(), "b_real_trip": real_trip()}
    (HERE / "analysis.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("a_u_kinds_by_set", "b_real_trip")}, ensure_ascii=False, indent=1))
    for i, v in out["a_new_u_items"].items():
        print(i, v["gold_features"], v["U_samples"], v["ok_samples"])
    for n, d in out["training_data_features"].items():
        print(n, d["sft_records"], d["sft_records_by_source"], d["dpo_pairs(chosen)"])


if __name__ == "__main__":
    main()
