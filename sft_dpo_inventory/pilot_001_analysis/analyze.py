# -*- coding: utf-8 -*-
"""pilot_001 원인 분석(작업 3의 a–e). 기록된 출력만 읽고 모델을 부르지 않는다.

    python sft_dpo_inventory/pilot_001_analysis/analyze.py

결과는 ``analysis.json``이고, 요약을 표준 출력에 찍는다.

- a. 악화 사유 문항: 업체 100의 기준·학습 셀별 grounding 차이, 보고 분류, U 종류, 멈춘 단계. 설명용(결정 36).
- b. thinking 길이: HF·Ollama·valid98 셀별 첫 계획 호출의 thinking 길이 분포, 생성 상한 도달, 반복 루프 지표.
- c. 학습 쪽 진단: valid98의 base·고른 SFT·최종 오류 유형, 학습 데이터 유형별 규모, 결정 23 습관.
- d. 경로 차이: 같은 가중치의 HF와 Ollama가 문항 단위로 얼마나 다른지, 학습 전후.
- e. 장치: valid98 checkpoint 평가의 장치와 생성 상한 도달.
"""
import importlib.util
import json
import statistics
import sys
import zlib
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

import evaluate_vendor100 as EV  # noqa: E402
from geoflow.planner import parse_planner_json  # noqa: E402


def _module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


C = _module("compare_cells", ROOT / "sft_dpo_inventory/baseline_conditions_001/compare_cells.py")
J = _module("judge", ROOT / "sft_dpo_inventory/pilot_001/vendor100/judge.py")
INV = ROOT / "sft_dpo_inventory"
GEN = ROOT / "training/generated"
VENDOR = {
    "HF-E": (INV / "thinking_prep_001/hf_e/HF-E_run1.json", GEN / "thinking_prep_001/HF-E_run1_raw.jsonl"),
    "HF-SFT": (INV / "pilot_001/vendor100/HF-sft.json", GEN / "pilot_001/HF-sft_raw.jsonl"),
    "HF-최종": (INV / "pilot_001/vendor100/HF-final.json", GEN / "pilot_001/HF-final_raw.jsonl"),
    "E": (INV / "pilot_prep_003/ollama/E.json", None),
    "B-conv": (INV / "pilot_prep_003/ollama/B-conv.json", None),
    "Ollama-SFT": (INV / "pilot_001/vendor100/Ollama-sft.json", None),
    "Ollama-최종": (INV / "pilot_001/vendor100/Ollama-final.json", None),
}
VALID = {"base": (INV / "pilot_prep_003/valid100/runs/base.json", GEN / "pilot_prep_003/valid100_base_raw.jsonl")}
for _label in ("sft_step62", "sft_step124", "sft_step186", "sft_step248",
               "dpo_step53", "dpo_step106", "dpo_step159", "dpo_step212"):
    VALID[_label] = (INV / f"pilot_001/valid98/runs/{_label}.json", GEN / f"pilot_001/{_label}_raw.jsonl")
SELECTED = {"base": "base", "SFT": "sft_step124", "최종": "dpo_step212"}
# 판정 결과(judgment.json)의 악화 사유 문항과 새로 생긴 U·조용한 오답
WORSE = {
    "HF-최종": {"base": "HF-E", "U_new": ["016", "030", "044", "054"], "silent_new": []},
    "HF-SFT": {"base": "HF-E", "U_new": ["037"], "silent_new": ["077"]},
    "Ollama-최종": {"base": "E", "U_new": ["040"], "silent_new": ["077", "100"]},
    "Ollama-SFT": {"base": "E", "U_new": ["026", "044", "059", "093"], "silent_new": ["077", "100"]},
}
SFT_DATA = GEN / "thinking_v004_t2pc_r1/sft_train.jsonl"
DPO_DATA = GEN / "thinking_v004_t2pc_r1/dpo_train.jsonl"
GOLD_SFT = GEN / "reviewed_gold_v004_t2pc/sft_train.jsonl"
GPU = {"GPU-a644de12": "GPU 2", "GPU-48f798cc": "GPU 3"}


def read_jsonl(path):
    with open(path, encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def dist(values):
    values = sorted(v for v in values if v is not None)
    if not values:
        return None
    n = len(values)
    return {"n": n, "median": statistics.median(values), "p90": values[min(n - 1, int(0.9 * n))], "max": values[-1],
            "over_20k": sum(v > 20000 for v in values), "over_50k": sum(v > 50000 for v in values)}


def split_think(text):
    """(thinking, 본문, 닫힘 여부)."""
    text = text or ""
    if "</think>" in text:
        head, body = text.split("</think>", 1)
        return head.replace("<think>", "", 1).strip(), body.strip(), True
    return text.replace("<think>", "", 1).strip(), "", False


def loop_metrics(text):
    """반복 루프 지표. 압축률(낮을수록 반복), 가장 많이 반복된 줄과 횟수, 끝부분의 같은 덩어리 연속 반복 수."""
    if not text:
        return None
    raw = text.encode("utf-8")
    lines = [line.strip() for line in text.splitlines() if len(line.strip()) >= 20]
    common = Counter(lines).most_common(1)
    tail_period, tail_repeats = None, 1
    for period in range(20, min(4000, len(text) // 3)):
        unit = text[-period:]
        k = 1
        while len(text) >= (k + 1) * period and text[-(k + 1) * period:-k * period] == unit:
            k += 1
        if k >= 3:
            tail_period, tail_repeats = period, k
            break
    return {"chars": len(text), "zlib_ratio": round(len(zlib.compress(raw, 9)) / len(raw), 3),
            "top_line_repeats": common[0][1] if common else 0,
            "top_line": (common[0][0][:120] if common else None),
            "tail_period": tail_period, "tail_repeats": tail_repeats}


def first_json(text_body):
    try:
        return parse_planner_json(text_body)
    except Exception:  # noqa: BLE001 - JSON이 아닌 본문
        return None


def habits(payload, gold):
    """결정 23 습관: 장소 role COND(정답 SUBCOND), factors.answer=value(정답에 없음)."""
    if not isinstance(payload, dict):
        return None
    places = [c for c in payload.get("concepts") or [] if isinstance(c, dict)
              and c.get("concept") == "LOCATION" and c.get("subtype") == "place"]
    factors = payload.get("factors") if isinstance(payload.get("factors"), dict) else {}
    gold_factors = (gold or {}).get("factors") or {}
    return {"places": len(places), "place_cond": sum(c.get("role") == "COND" for c in places),
            "place_subcond": sum(c.get("role") == "SUBCOND" for c in places),
            "answer_value": factors.get("answer") == "value",
            "answer_value_not_in_gold": factors.get("answer") == "value" and gold_factors.get("answer") != "value"}


def habit_summary(rows):
    rows = [r for r in rows if r is not None]
    places = sum(r["places"] for r in rows)
    return {"first_json_parsed": len(rows), "place_concepts": places,
            "place_role_COND": sum(r["place_cond"] for r in rows), "place_role_SUBCOND": sum(r["place_subcond"] for r in rows),
            "answer_value": sum(r["answer_value"] for r in rows),
            "answer_value_not_in_gold": sum(r["answer_value_not_in_gold"] for r in rows)}


def diff_type(diff):
    """grounding_check 차이 하나 → 오류 유형 이름. 차이 형식은 [키, 정답 값, 모델 값]."""
    if isinstance(diff, str):
        return diff
    key, gold, got = diff[0], diff[1], diff[2] if len(diff) > 2 else None
    if gold in (None, [], {}) and got not in (None, [], {}):
        return f"{key} 추가"
    if got in (None, [], {}) and gold not in (None, [], {}):
        return f"{key} 누락"
    return f"{key} 다름"


def stop_stage(source):
    trace = source.get("planner_trace") or {}
    attempts = trace.get("attempts") or []
    stages = [a.get("stage") or a.get("status") for a in attempts]
    return {"outcome": source.get("outcome"), "error_code": source.get("error_code"),
            "error_stage": trace.get("error_stage"), "attempt_stages": stages,
            "repairs": sorted(k for k, v in (trace.get("repairs") or {}).items() if (v or {}).get("attempted"))}


# ---------------------------------------------------------------- 업체 100
def vendor_cells():
    empty = HERE / ".empty_arm"
    empty.mkdir(exist_ok=True)
    cells = {}
    for name, (path, _raw) in VENDOR.items():
        cells[name] = {"scored": C.load_cell(path, empty),
                       "rows": {r["id"]: r for r in json.loads(path.read_text(encoding="utf-8"))["rows"]}}
    empty.rmdir()
    return cells


def vendor_first(name, raw_path, rows):
    """문항 id → 첫 계획 호출(thinking 길이, 본문 JSON, 생성 상한 도달, thinking 원문 여부)."""
    out = {}
    if raw_path is not None:
        for r in read_jsonl(raw_path):
            if r["call"] != 0:
                continue
            think, body, closed = split_think(r["raw_text"])
            out[r["id"]] = {"thinking_chars": len(think), "thinking": think, "json": first_json(body),
                            "truncated": r.get("done_reason") == "length", "think_closed": closed,
                            "tokens": r.get("generated_tokens")}
        for item_id, row in rows.items():
            out.setdefault(item_id, {})["calls_truncated"] = sum(
                1 for c in row.get("llm_calls") or [] if c.get("done_reason") == "length")
        return out
    for item_id, row in rows.items():
        calls = row.get("llm_calls") or []
        plans = [c for c in calls if c.get("kind") == "plan"]
        first = plans[0] if plans else {}
        out[item_id] = {"thinking_chars": first.get("thinking_chars"), "thinking": None,
                        "json": first_json(first.get("content") or ""),
                        "truncated": first.get("done_reason") == "length", "tokens": first.get("eval_count"),
                        "calls_truncated": sum(1 for c in calls if c.get("done_reason") == "length"),
                        "content_sha": first.get("content")}
    return out


def part_a(cells, gold):
    detail = {}
    names = list(VENDOR)
    for cell, spec in WORSE.items():
        for item_id in spec["U_new"] + spec["silent_new"]:
            entry = detail.setdefault(item_id, {"reason_in": [], "cells": {}})
            entry["reason_in"].append(f"{cell}: {'새 U' if item_id in spec['U_new'] else '새 조용한 오답'}")
            for name in names:
                if name in entry["cells"]:
                    continue
                scored = cells[name]["scored"][item_id]
                source = cells[name]["rows"][item_id]
                _ok, diffs = EV.grounding_check(gold[item_id], source.get("grounding"))
                entry["cells"][name] = {"grounding_ok": scored["grounding_ok"], "report_class": scored["report_class"],
                                        "u_flags": scored["u_flags"], "v4": scored["v4"],
                                        "diffs": diffs, "diff_types": sorted({diff_type(d) for d in diffs}),
                                        **stop_stage(source)}
    return detail


# ---------------------------------------------------------------- valid98
def valid_gold():
    spec = json.loads((INV / "pilot_001/valid98/valid98_items.json").read_text(encoding="utf-8"))
    documents, gold = {}, {}
    for ref in spec["items"]:
        if ref["path"] not in documents:
            documents[ref["path"]] = {i["id"]: i for i in EV.load_gold(ROOT / ref["path"])["items"]}
        gold[f"{ref['set']}/{ref['id']}"] = documents[ref["path"]][ref["id"]]
    return gold


def valid_cells(gold):
    cells = {}
    for label, (path, raw_path) in VALID.items():
        data = json.loads(path.read_text(encoding="utf-8"))
        rows = {r["id"]: r for r in data["rows"] if r["id"] in gold}
        first = {}
        for r in read_jsonl(raw_path):
            if r["call"] != 0 or r["id"] not in gold:
                continue
            think, body, closed = split_think(r.get("raw_text"))
            first[r["id"]] = {"thinking_chars": len(think), "thinking": think, "json": first_json(body),
                              "truncated": r.get("done_reason") == "length", "think_closed": closed}
        truncated_calls = sum(sum(1 for d in r.get("done_reasons") or [] if d == "length") for r in rows.values())
        cells[label] = {"rows": rows, "first": first, "device": GPU.get(data["meta"]["device_uuid"][:12]),
                        "grounding_ok": sum(r["grounding_ok"] for r in rows.values()), "truncated_calls": truncated_calls}
    return cells


def error_types(rows):
    counter, per_item = Counter(), {}
    for item_id, row in rows.items():
        if row["grounding_ok"]:
            continue
        if row["grounding_diffs"] == ["no_grounding"]:
            types = [f"멈춤: {row['outcome']}:{row['error_code']}"]
        else:
            types = sorted({diff_type(d) for d in row["grounding_diffs"]})
        per_item[item_id] = types
        counter.update(types)
    return counter, per_item


def training_profile():
    """학습 데이터 유형별 규모. SFT target JSON과 DPO chosen·rejected의 factor·장소 특징을 센다."""
    def features(payload):
        if not isinstance(payload, dict):
            return set()
        factors = payload.get("factors") if isinstance(payload.get("factors"), dict) else {}
        feats = {f"factor:{k}" for k in factors}
        if any(k in factors for k in ("bucket", "aggregation", "rollup")):
            feats.add("factor:aggregation_spec")
        places = [c for c in payload.get("concepts") or [] if isinstance(c, dict) and c.get("concept") == "LOCATION"]
        feats.add(f"places={len(places)}")
        measures = [c for c in payload.get("concepts") or [] if isinstance(c, dict) and c.get("role") == "MEASURE"]
        feats.update(f"measure:{c.get('concept')}/{c.get('subtype')}" for c in measures)
        return feats

    sft = read_jsonl(SFT_DATA)
    sft_feats, sft_stop, sft_habits = Counter(), 0, []
    questions = set()
    for r in sft:
        questions.add(r["metadata"].get("source_record_id"))
        _think, body, _closed = split_think(r["messages"][-1]["content"])
        payload = first_json(body)
        sft_feats.update(features(payload))
        if (r["metadata"].get("chosen_quality") or {}).get("outcome") != "answered":
            sft_stop += 1
        sft_habits.append(habits(payload, None))
    dpo = read_jsonl(DPO_DATA)
    dpo_diff = Counter()
    dpo_chosen_habits, dpo_rejected_habits = [], []
    for r in dpo:
        def body_of(x):
            if isinstance(x, list):
                x = x[-1]["content"]
            return split_think(x)[1]
        chosen, rejected = first_json(body_of(r["chosen"])), first_json(body_of(r["rejected"]))
        dpo_chosen_habits.append(habits(chosen, None))
        dpo_rejected_habits.append(habits(rejected, None))
        fc, fr = features(chosen), features(rejected)
        dpo_diff.update(fc ^ fr)
        if isinstance(chosen, dict) and isinstance(rejected, dict):
            cf, rf = chosen.get("factors") or {}, rejected.get("factors") or {}
            for k in set(cf) | set(rf):
                if cf.get(k) != rf.get(k):
                    dpo_diff[f"value_differs:factor:{k}"] += 1
        if rejected is None:
            dpo_diff["rejected_not_json"] += 1
    think_len = {"sft_target": dist([len(split_think(r["messages"][-1]["content"])[0]) for r in sft])}
    def think_of(x):
        if isinstance(x, list):
            x = x[-1]["content"]
        return len(split_think(x)[0])
    think_len["dpo_chosen"] = dist([think_of(r["chosen"]) for r in dpo])
    think_len["dpo_rejected"] = dist([think_of(r["rejected"]) for r in dpo])
    think_len["dpo_rejected_longer_than_chosen"] = sum(think_of(r["rejected"]) > think_of(r["chosen"]) for r in dpo)
    gold_habits = []
    for r in read_jsonl(GOLD_SFT):
        gold_habits.append(habits(first_json(r["messages"][-1]["content"]), None))
    return {"sft_records": len(sft), "sft_questions": len(questions), "sft_stop_targets": sft_stop,
            "sft_features": dict(sft_feats.most_common()), "dpo_pairs": len(dpo),
            "dpo_feature_differs": dict(dpo_diff.most_common()), "thinking_chars": think_len,
            "habits": {"sft_target": habit_summary(sft_habits), "dpo_chosen": habit_summary(dpo_chosen_habits),
                       "dpo_rejected": habit_summary(dpo_rejected_habits),
                       "reviewed_gold_v004_sft(참고)": habit_summary(gold_habits)}}


# ---------------------------------------------------------------- main
def main():
    out = {}
    vgold = {it["id"]: it for it in EV.load_gold(None)["items"]}
    cells = vendor_cells()
    vg = valid_gold()
    firsts = {name: vendor_first(name, VENDOR[name][1], cells[name]["rows"]) for name in VENDOR}

    # a
    out["a_worse_items"] = part_a(cells, vgold)
    vendor_types = {}
    for name in VENDOR:
        counter = Counter()
        for item_id, row in cells[name]["rows"].items():
            ok, diffs = EV.grounding_check(vgold[item_id], row.get("grounding"))
            if not ok:
                counter.update({diff_type(d) for d in diffs})
        vendor_types[name] = dict(sorted(counter.items()))
    out["a_vendor_error_types(설명용, 결정 36)"] = vendor_types

    # b: thinking 길이(업체 100)
    thinking = {}
    loops = {}
    for name, first in firsts.items():
        values = [f.get("thinking_chars") for f in first.values()]
        thinking[f"업체100 {name}"] = {**(dist(values) or {}),
                                     "first_call_truncated": sum(bool(f.get("truncated")) for f in first.values()),
                                     "all_calls_truncated": sum(f.get("calls_truncated") or 0 for f in first.values())}
        for item_id, f in first.items():
            if f.get("thinking") is not None and (f.get("truncated") or (f.get("thinking_chars") or 0) > 20000):
                loops[f"업체100 {name}/{item_id}"] = {**loop_metrics(f["thinking"]), "truncated": f.get("truncated")}
    top = max(firsts["Ollama-SFT"].items(), key=lambda kv: kv[1].get("thinking_chars") or 0)
    out["b_ollama_sft_longest"] = {"item": top[0], "thinking_chars": top[1]["thinking_chars"], "eval_count": top[1]["tokens"],
                                   "truncated": top[1]["truncated"], "thinking_text_recorded": False,
                                   "same_item_other_cells": {n: {"thinking_chars": firsts[n][top[0]].get("thinking_chars"),
                                                                 "truncated": firsts[n][top[0]].get("truncated")}
                                                             for n in VENDOR}}
    # b: valid98
    vcells = valid_cells(vg)
    for label, cell in vcells.items():
        values = [f["thinking_chars"] for f in cell["first"].values()]
        thinking[f"valid98 {label}"] = {**(dist(values) or {}),
                                        "first_call_truncated": sum(f["truncated"] for f in cell["first"].values()),
                                        "all_calls_truncated": cell["truncated_calls"], "device": cell["device"]}
        if label in SELECTED.values():
            for item_id, f in cell["first"].items():
                if f["truncated"] or f["thinking_chars"] > 20000:
                    loops[f"valid98 {label}/{item_id}"] = {**loop_metrics(f["thinking"]), "truncated": f["truncated"]}
    # 생성 상한에 걸린 모든 HF 호출(첫 계획과 재질의 모두): 끝부분 반복 여부
    truncated_all = {}
    raw_files = {f"업체100 {n}": raw for n, (_p, raw) in VENDOR.items() if raw is not None}
    raw_files.update({f"valid98 {label}": raw for label, (_p, raw) in VALID.items()})
    for name, raw in raw_files.items():
        calls = [r for r in read_jsonl(raw) if r.get("done_reason") == "length"
                 and (not name.startswith("valid98") or r["id"] in vg)]
        metrics = [loop_metrics(split_think(r["raw_text"])[0] or r["raw_text"]) for r in calls]
        truncated_all[name] = {"truncated_calls": len(calls),
                               "tail_repeats>=3": sum(1 for m in metrics if m and m["tail_repeats"] >= 3),
                               "zlib_ratio_max": max((m["zlib_ratio"] for m in metrics if m), default=None),
                               "calls": [f"{r['id']}#{r['call']}" for r in calls]}
    out["b_truncated_all_calls"] = truncated_all
    # 비교용: 정상 종료한 thinking의 압축률 분포(HF-E, base valid98)
    normal = [loop_metrics(f["thinking"])["zlib_ratio"] for f in firsts["HF-E"].values()
              if f.get("thinking") and not f.get("truncated")]
    out["b_thinking"] = thinking
    out["b_loops"] = loops
    out["b_normal_zlib_ratio_HF-E"] = dist([round(x * 1000) for x in normal])  # 천분율

    # c: valid98 오류 유형
    c_types, c_items = {}, {}
    for key, label in SELECTED.items():
        counter, per_item = error_types(vcells[label]["rows"])
        c_types[key] = dict(counter.most_common())
        c_items[key] = per_item
    all_types = sorted(set().union(*[set(v) for v in c_types.values()]))
    out["c_valid98_error_types"] = {t: {k: c_types[k].get(t, 0) for k in SELECTED} for t in all_types}
    out["c_valid98_grounding_ok"] = {k: vcells[label]["grounding_ok"] for k, label in SELECTED.items()}
    trans = {}
    for a, b in (("base", "SFT"), ("SFT", "최종"), ("base", "최종")):
        ra, rb = vcells[SELECTED[a]]["rows"], vcells[SELECTED[b]]["rows"]
        gained = sorted(k for k in ra if not ra[k]["grounding_ok"] and rb[k]["grounding_ok"])
        lost = sorted(k for k in ra if ra[k]["grounding_ok"] and not rb[k]["grounding_ok"])
        trans[f"{a}→{b}"] = {"b": len(gained), "c": len(lost), "mcnemar_p": round(J.mcnemar(len(gained), len(lost)), 4),
                             "gained": gained, "lost": lost}
    out["c_valid98_transitions"] = trans
    out["c_valid98_error_items"] = c_items
    out["c_training_profile"] = training_profile()
    gold_feats = Counter()
    for item in vg.values():
        g = EV.gold_grounding(item)
        if g is None:
            gold_feats["정답 grounding 없음"] += 1
            continue
        factors = g.get("factors") or {}
        gold_feats.update(f"factor:{k}" for k in factors)
        gold_feats["factor:aggregation_spec" if any(k in factors for k in ("bucket", "aggregation", "rollup"))
                   else "집계 없음"] += 1
    out["c_valid98_gold_features"] = dict(gold_feats.most_common())
    # 결정 23 습관: 첫 응답 JSON 기준, 정답과 비교
    hab = {}
    for key, label in SELECTED.items():
        hab[f"valid98 {key}"] = habit_summary([habits(f["json"], EV.gold_grounding(vg[i]))
                                               for i, f in vcells[label]["first"].items()])
    for name in VENDOR:
        hab[f"업체100 {name}"] = habit_summary([habits(f.get("json"), EV.gold_grounding(vgold[i]))
                                              for i, f in firsts[name].items() if i in vgold])
    gold_places = [habits(EV.gold_grounding(vg[i]), None) for i in vg if EV.gold_grounding(vg[i]) is not None]
    hab["valid98 정답(참고)"] = habit_summary(gold_places)
    out["c_habits"] = hab

    # d: 경로 차이
    def agree(a, b):
        A, B = cells[a]["scored"], cells[b]["scored"]
        keys = sorted(set(A) & set(B))
        ok_diff = [k for k in keys if A[k]["grounding_ok"] != B[k]["grounding_ok"]]
        same_json = sum(1 for k in keys if firsts[a][k].get("json") is not None
                        and firsts[a][k].get("json") == firsts[b][k].get("json"))
        same_final = sum(1 for k in keys if cells[a]["rows"][k].get("grounding") is not None
                         and cells[a]["rows"][k].get("grounding") == cells[b]["rows"][k].get("grounding"))
        return {"grounding_ok": [sum(A[k]["grounding_ok"] for k in keys), sum(B[k]["grounding_ok"] for k in keys)],
                "grounding_ok_differs": len(ok_diff), "items": ok_diff,
                "first_json_equal": same_json, "final_grounding_equal": same_final,
                "only_first_ok": sum(1 for k in ok_diff if A[k]["grounding_ok"]),
                "only_second_ok": sum(1 for k in ok_diff if B[k]["grounding_ok"])}
    out["d_paths"] = {"학습 전 HF-E vs E": agree("HF-E", "E"), "학습 전 HF-E vs B-conv": agree("HF-E", "B-conv"),
                      "학습 전 E vs B-conv": agree("E", "B-conv"),
                      "SFT HF vs Ollama": agree("HF-SFT", "Ollama-SFT"),
                      "최종 HF vs Ollama": agree("HF-최종", "Ollama-최종")}

    # e: 장치
    out["e_valid98_devices"] = {label: {"device": c["device"], "grounding_ok": c["grounding_ok"],
                                        "truncated_calls": c["truncated_calls"]} for label, c in vcells.items()}

    (HERE / "analysis.json").write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k not in ("a_worse_items", "c_valid98_error_items", "b_loops")},
                     ensure_ascii=False, indent=1, default=str)[:20000])


if __name__ == "__main__":
    main()
