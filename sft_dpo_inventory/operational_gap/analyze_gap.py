# -*- coding: utf-8 -*-
"""기록만 쓰는 원인 분석(결정 77, operational_gap). 모델 호출 없음.

    tokvenv/bin/python sft_dpo_inventory/operational_gap/analyze_gap.py

입력: calibration_001(``calibration_001/runs``)과 quant_recipe(``quant_recipe/runs``)의 selection_v1 sampling 기록(k=4)과
저장된 응답 원문(``training/generated/{calibration_001,quant_recipe}/raw``, ignore 경로).
출력: ``analysis.json``(문항 id·오류 코드·개수만, 응답 원문과 질문 문장은 넣지 않는다).

1. 오류 유형 분류(analyze_cal의 ERRORS)에 걸리지 않는 오답을 셀마다 다섯 갈래로 나눈다. 한 문항·표본의 호출 중 하나라도
   해당하면 앞 갈래부터 붙인다.
   - split: 본문이 비었거나, 본문에 ``<think>``·``</think>``가 남았거나, HF에서 ``</think>``가 닫히지 않았거나,
     thinking에만 JSON이 있고 본문이 빈 경우.
   - truncated: done_reason이 stop이 아니거나 HF 생성 token이 8192에 닿음.
   - json: 본문에서 planner의 ``parse_planner_json``이 JSON 객체를 읽지 못함(파이프라인과 같은 함수).
   - contract: plan 호출 JSON에 계약 밖 key(최상위·factor·attributes)가 있거나 오류 코드가 UNKNOWN_KEY·UNKNOWN_FACTOR·UNKNOWN_ATTRIBUTE.
   - other: 위 넷이 아님. 형식은 맞고 계약 안의 값으로 뜻이 틀림. 결과(outcome)와 오류 코드로 더 나눈다.
2. 문항별 정답 비율 차이(HF-final − Ollama 학습 모델)가 큰 문항의 오류 코드.
3. 조용한 오답의 문항 목록과 유형(grounding 차이의 항목 이름), HF-base → HF-final 조용한 오답 비율 차이의 95% CI.
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/calibration_001"))
import analyze_cal as A  # noqa: E402
from geoflow.factors import FACTOR_SPECS  # noqa: E402
from geoflow.planner import IGNORABLE_KEYS, UNSUPPORTED_KEY, PlannerError, parse_planner_json  # noqa: E402

CAL = ROOT / "sft_dpo_inventory/calibration_001/runs"
QR = ROOT / "sft_dpo_inventory/quant_recipe/runs"
RAW = {CAL: ROOT / "training/generated/calibration_001/raw", QR: ROOT / "training/generated/quant_recipe/raw"}
CELLS = {"HF-base": CAL, "HF-final": CAL, "E": CAL, "c": CAL, "d": CAL, "B-conv": CAL, "B-off": QR,
         "Ollama-final": CAL, "e": CAL, "F-off": QR}
PATH = {"HF-base": "HF BF16 base", "HF-final": "HF BF16 + adapter", "E": "Ollama 공식 qwen3:8b", "c": "Ollama 공식 blob + HF TEMPLATE",
        "d": "Ollama base Q8_0", "B-conv": "Ollama base 자체 Q4", "B-off": "Ollama base 공식 방식 Q4",
        "Ollama-final": "Ollama 최종 자체 Q4", "e": "Ollama 최종 Q8_0", "F-off": "Ollama 최종 공식 방식 Q4"}
CONTRACT_CODES = {"UNKNOWN_KEY", "UNKNOWN_FACTOR", "UNKNOWN_ATTRIBUTE"}
BUCKETS = ("split", "truncated", "json", "contract", "other")
HF_MAX = 8192


def raw_calls(raw_dir, cell, k):
    out = defaultdict(dict)
    for line in (raw_dir / f"{cell}_s{k}_raw.jsonl").read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        out[r["id"]][int(r["call"])] = r
    return out


def contract_extra(payload):
    extra = set(payload) - {"concepts", "factors", UNSUPPORTED_KEY} - IGNORABLE_KEYS
    factors = payload.get("factors")
    if isinstance(factors, dict):
        extra |= {f"factor:{x}" for x in set(factors) - set(FACTOR_SPECS)}
    for c in payload.get("concepts") or []:
        if isinstance(c, dict) and isinstance(c.get("attributes"), dict):
            extra |= {f"attribute:{x}" for x in set(c["attributes"]) - {"od_role"}}
    return sorted(extra)


def bucket(src, raws):
    """한 문항·표본의 갈래와 근거."""
    calls = src.get("llm_calls") or []
    hf = src.get("hf_calls")
    notes = []
    for n, call in enumerate(calls):
        content = call.get("content") or ""
        raw = raws.get(n, {})
        thinking = raw.get("thinking")
        if thinking is None and "raw_text" in raw:
            thinking = raw["raw_text"].split("</think>", 1)[0]
        closed = (hf[n].get("think_closed") if hf and n < len(hf) else True)
        if not content.strip() or "<think>" in content or "</think>" in content or closed is False:
            notes.append(("split", n, "empty" if not content.strip() else ("unclosed" if closed is False else "think_tag")))
        tokens = (hf[n].get("generated_tokens") if hf and n < len(hf) else call.get("eval_count")) or 0
        if call.get("done_reason") not in (None, "stop") or (hf and tokens >= HF_MAX):
            notes.append(("truncated", n, call.get("done_reason")))
        try:
            payload = parse_planner_json(content)
        except PlannerError as error:
            notes.append(("json", n, error.code))
            continue
        if call.get("kind", "plan") == "plan":
            extra = contract_extra(payload)
            if extra:
                notes.append(("contract", n, ",".join(extra)))
    if src.get("error_code") in CONTRACT_CODES:
        notes.append(("contract", None, src["error_code"]))
    for b in BUCKETS[:-1]:
        hit = [x for x in notes if x[0] == b]
        if hit:
            return b, hit
    return "other", []


def diff_type(src, gold_item):
    ok, diffs = A.EV.grounding_check(gold_item, src.get("grounding"))
    names = sorted({str(d[0]).replace("factor:", "") for d in diffs}) if diffs else ["(없음)"]
    return "+".join(names)


def main():
    gold = {i["id"]: i for i in A.EV.load_gold(A.CS.GOLD)["items"]}
    ids = list(gold)
    per = {}      # cell -> k -> id -> record
    for cell, runs in CELLS.items():
        per[cell] = []
        for k in range(1, A.K + 1):
            path = runs / f"{cell}_s{k}.json"
            _, rows = A.load_sample(path, gold)
            src = {r["id"]: r for r in json.loads(path.read_text(encoding="utf-8"))["rows"]}
            raws = raw_calls(RAW[runs], cell, k)
            sample = {}
            for i in ids:
                r, s = rows[i], src[i]
                rec = {"ok": r["ok"], "class": r["class"], "outcome": s.get("outcome"), "error_code": s.get("error_code"),
                       "categorized": [e for e in A.ERRORS if r[e]], "calls": r["calls"]}
                rec["bucket"], rec["bucket_notes"] = bucket(s, raws.get(i, {}))
                rec["silent"] = r["class"] == A.CS.SILENT
                rec["diff_type"] = diff_type(s, gold[i]) if not r["ok"] else None
                calls = s.get("llm_calls") or []
                rec["plan_tokens"] = ((s.get("hf_calls") or [{}])[0].get("generated_tokens") if s.get("hf_calls")
                                      else (calls[0].get("eval_count") if calls else None))
                sample[i] = rec
            per[cell].append(sample)

    result = {"note": "기록만 씀. 모델 호출 없음. 응답 원문·질문 문장은 넣지 않음.", "cells": {}, "format_checks_all_calls": {},
              "items_gap": {}, "silent": {}, "silent_ci": {}}
    for cell in CELLS:
        recs = [s[i] for s in per[cell] for i in ids]
        wrong = [r for r in recs if not r["ok"]]
        unc = [r for r in wrong if not r["categorized"]]
        b = Counter(r["bucket"] for r in unc)
        other = [r for r in unc if r["bucket"] == "other"]
        result["cells"][cell] = {
            "path": PATH[cell], "item_samples": len(recs), "wrong": len(wrong), "uncategorized_wrong": len(unc),
            "buckets": {x: b.get(x, 0) for x in BUCKETS},
            "bucket_notes": [{"bucket": r["bucket"], "notes": r["bucket_notes"]} for r in unc if r["bucket"] != "other"],
            "other_by_outcome": dict(Counter(r["outcome"] for r in other).most_common()),
            "other_by_error_code": dict(Counter(f"{r['outcome']}:{r['error_code']}" for r in other).most_common()),
            "other_silent": sum(r["silent"] for r in other),
            "all_wrong_by_error_code": dict(Counter(f"{r['outcome']}:{r['error_code']}" for r in wrong if r["error_code"]).most_common()),
            "multi_call_rate_pct": round(100 * sum(r["calls"] > 1 for r in recs) / len(recs), 2),
            "plan_tokens_median": float(np.median([r["plan_tokens"] for r in recs if r["plan_tokens"]])),
        }
        # 모든 호출(맞은 것 포함)의 형식 확인: 분리·잘림·JSON 문제가 셀 전체에 몇 번 있었나
        result["format_checks_all_calls"][cell] = dict(Counter(r["bucket"] for r in recs if r["bucket"] != "other"))

    # 2. 학습 모델: HF-final은 맞고 Ollama 학습 모델은 틀린 문항
    for ol in ("e", "F-off", "Ollama-final"):
        rows = []
        for i in ids:
            hf = sum(s[i]["ok"] for s in per["HF-final"]) / A.K
            o = sum(s[i]["ok"] for s in per[ol]) / A.K
            if hf - o >= 0.5:
                rows.append({"id": i, "hf_final_ok": hf, "ollama_ok": o,
                             "ollama_wrong": dict(Counter(
                                 "+".join(s[i]["categorized"]) or f"{s[i]['outcome']}:{s[i]['error_code']}"
                                 for s in per[ol] if not s[i]["ok"]))})
        rev = sum(1 for i in ids if sum(s[i]["ok"] for s in per[ol]) / A.K - sum(s[i]["ok"] for s in per["HF-final"]) / A.K >= 0.5)
        result["items_gap"][ol] = {"hf_better_by_0.5_or_more": rows, "count": len(rows), "reverse_count": rev}

    # 3. 조용한 오답
    for cell in CELLS:
        items = defaultdict(list)
        for s in per[cell]:
            for i in ids:
                if s[i]["silent"]:
                    items[i].append(s[i]["diff_type"])
        result["silent"][cell] = {
            "item_samples": sum(len(v) for v in items.values()), "items": len(items),
            "by_type": dict(Counter(t for v in items.values() for t in v).most_common()),
            "list": {i: dict(Counter(v)) for i, v in sorted(items.items())}}
    for set_name in ("selection_v1", "selection_v2"):
        sub = [i for i in ids if set_name == "selection_v1" or i not in A.V2_REMOVED]
        rng = np.random.default_rng(A.SEED)
        out = {}
        for a, b in (("HF-base", "HF-final"), ("HF-base", "E"), ("HF-final", "E")):
            ma = np.array([[float(s[i]["silent"]) for s in per[a]] for i in sub])
            mb = np.array([[float(s[i]["silent"]) for s in per[b]] for i in sub])
            d = mb.mean(axis=1) - ma.mean(axis=1)
            out[f"{a}→{b}"] = {"a_pct": round(100 * ma.mean(), 2), "b_pct": round(100 * mb.mean(), 2),
                               "diff_pct": round(100 * d.mean(), 2), "ci95_pct": [round(100 * x, 2) for x in A.boot_ci(d, rng)],
                               "items_new": sorted(i for i, x in zip(sub, d) if x > 0),
                               "items_gone": sorted(i for i, x in zip(sub, d) if x < 0)}
        result["silent_ci"][set_name] = out

    (HERE / "analysis.json").write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for cell, c in result["cells"].items():
        print(f"{cell:13s} wrong {c['wrong']:3d} unc {c['uncategorized_wrong']:3d} {c['buckets']} multi {c['multi_call_rate_pct']} "
              f"tok {c['plan_tokens_median']}")
        print("   other", c["other_by_outcome"], "silent", c["other_silent"])
    print("format all", result["format_checks_all_calls"])
    for ol, g in result["items_gap"].items():
        print("gap", ol, g["count"], "reverse", g["reverse_count"])
    for s, v in result["silent_ci"].items():
        for k, x in v.items():
            print("silent", s, k, x["a_pct"], x["b_pct"], x["diff_pct"], x["ci95_pct"])


if __name__ == "__main__":
    main()
