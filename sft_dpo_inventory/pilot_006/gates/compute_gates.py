# -*- coding: utf-8 -*-
"""pilot_006 Gate A–E와 arm별 선행 조건(PLAN_DRAFT 5절, 결정 109·112·113). 세션 3 사전 등록 때 이 파일을 그대로 고정한다. 모델 호출 없음.

    hfvenv/bin/python compute_gates.py --spec SPEC.json --out OUT.json

SPEC: {"sets": {"<셋>": "<gold yaml(저장소 상대)>", ...},
       "cells": {"base": {"<셋>": ["<셀 json 경로>", ...]}, "F": {...}, "P": {...}},
       "latency": {"base": "<지연 셀 json>", "F": ..., "P": ...}  (선택),
       "label": "..."}
- 표본 채점·분류: ``calibration_001/analyze_cal.load_sample``(grounding_check, U1–U4·조용한 오답 분류, dt_missing 등 오류 유형). judge_v3·pilot_005와 같다.
- 문항 값 = 그 셀 k표본 평균. 셋 여러 개면 문항을 이어 붙인다(주 셋 = selection_v2 ∪ augmentation_holdout_v1).
- 차이의 95% CI: 문항 단위 쌍 bootstrap 10,000회, 비교마다 새 ``numpy.random.default_rng(20261109)``(PROTOCOL_v4·v5).
- 지표: ok(grounding_ok), U, silent(조용한 오답), dt_missing, 구조 오류(첫 응답이 계획 단계에서 실패한 코드 — MULTIPLE_MEASURES, NO_MEASURE, INVALID_*,
  JSON_NOT_FOUND 등), grounding failure(최종 outcome failed이고 오류가 planner 단계), repair 호출(호출 2회 이상), token(입력, thinking, 최종 JSON, 전체 생성;
  원문 파일 ``meta.hf.raw_out``이 있으면 Qwen3-8B tokenizer로 thinking·JSON을 나눈다).
- 판정:
  - 선행(arm마다, 대 base): ok 차이 CI 하한 > 0 그리고 U 차이 CI 하한 ≤ 0(보정 없음, 결정 112).
  - A: P − F ok 차이 CI 하한 ≥ −5%p(결정 109). B: dt_missing P − F CI 하한 ≤ 0. C: silent P − F CI 하한 ≤ 0.
  - D: (1) MULTIPLE_MEASURES + NO_MEASURE 비율 P − F CI 하한 ≤ 0 그리고 (2) 구조 오류·grounding failure·repair 비율 중 하나 이상에서 P − F CI 상한 < 0.
  - E(지시 3절 3): (1) P와 F 각각 지연 중앙값 비(대 base, 순차 고정 30문항) ≤ 1.5, (2) 최종 JSON token 중앙값 P가 F보다 30% 이상 적음, (3) 생성 token 중앙값 P ≤ F.
  - 채택 = A–E 모두 통과. A 불통과이고 CI 반폭 > 5%p면 "판정 불가"로 적는다.
"""
import argparse
import json
import statistics
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/calibration_001"))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/thinking_prep_001"))

SEED, REPS, MARGIN = 20261109, 10000, -0.05
STRUCT_CODES = ("MULTIPLE_MEASURES", "NO_MEASURE", "JSON_NOT_FOUND", "INVALID_JSON", "INVALID_CONCEPT", "INVALID_SUBTYPE", "INVALID_ROLE",
                "INVALID_FACTOR", "INVALID_FACTOR_COMBINATION", "INVALID_VALUE", "UNKNOWN_KEY")


def ci(d):
    rng = np.random.default_rng(SEED)
    idx = rng.integers(0, len(d), size=(REPS, len(d)))
    m = d[idx].mean(axis=1)
    return float(d.mean()), [float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))]


def first_code(row):
    tr = row.get("planner_trace") or {}
    att = tr.get("attempts") or []
    if att and att[0].get("status") == "planning_failed":
        return att[0].get("error_code")
    return None


_TOK = None


def tok():
    global _TOK
    if _TOK is None:
        import hf_thinking as H
        from transformers import AutoTokenizer
        _TOK = AutoTokenizer.from_pretrained(H.MODEL, revision=H.REVISION)
    return _TOK


def token_parts(path, meta):
    raw = Path(((meta.get("hf") or {}).get("raw_out")) or "")
    out = {}
    if not raw.exists():
        return out
    for line in raw.read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        text = r["raw_text"]
        th, js = (text.split("</think>", 1) + [""])[:2] if "</think>" in text else (text, "")
        d = out.setdefault(r["id"], {"thinking": 0, "json": 0})
        d["thinking"] += len(tok()(th, add_special_tokens=False)["input_ids"])
        d["json"] += len(tok()(js.strip(), add_special_tokens=False)["input_ids"])
    return out


def scorer():
    """judge_v3(pilot_003)·judge5(pilot_005)와 같은 채점 준비: U 분류기가 원본 gold를 찾도록 셋 파일을 등록한다.
    judge_v3 import가 final_v12 등록과 업체 100 id(“/” 없음) → dev/<id> 보정을 한다. 더해서 valid98 원본 셋 셋(judge5와 같음)과
    augmentation_holdout_v1(id ``aug300-NNN`` → ``aug300/aug300-NNN``, pilot_006에서 더함)."""
    sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_003/vendor100"))
    import judge_v3 as J
    A = J.A
    if not getattr(A, "_pilot006_registered", False):
        A.C.R.C.GOLD_FILES.update({"stage_v7": "evaluation/grounding_v7/stage_contrast_questions.yaml",
                                   "heldout_v8": "evaluation/grounding_v8/heldout_questions.yaml",
                                   "heldout_v9": "evaluation/grounding_v9/heldout_questions.yaml",
                                   "aug300": "sft_dpo_inventory/pilot_006_prep/aug300/augmentation_holdout_v1_gold.yaml"})
        inner = A.C.R.unacceptable
        A.C.R.unacceptable = lambda key, row, src: inner(f"aug300/{key}" if key.startswith("aug300-") else key, row, src)
        A._pilot006_registered = True
    return A


def load_arm(spec_cells, sets, with_tokens=True):
    A = scorer()
    import evaluate_vendor100 as EV
    items, mats = [], {}
    fields = ("ok", "U", "silent", "dt_missing", "mm_nm", "struct", "gfail", "repair", "input_tokens", "gen_tokens", "thinking_tokens", "json_tokens")
    per_set = {}
    for set_name, paths in spec_cells.items():
        gold = {i["id"]: i for i in EV.load_gold(ROOT / sets[set_name])["items"]}
        samples = []
        for p in paths:
            p = ROOT / p
            raw_dir = Path((json.loads(p.read_text(encoding="utf-8"))["meta"].get("hf") or {}).get("raw_out") or ".").parent
            A.RAW = raw_dir
            meta, rows = A.load_sample(p, gold)
            src = {r["id"]: r for r in json.loads(p.read_text(encoding="utf-8"))["rows"]}
            tp = token_parts(p, meta) if with_tokens else {}
            for i, r in rows.items():
                s = src[i]
                code = first_code(s)
                r["silent"] = r["class"] == A.CS.SILENT
                r["U"] = r["class"] == A.CS.U_CLASS
                r["mm_nm"] = code in ("MULTIPLE_MEASURES", "NO_MEASURE")
                r["struct"] = code is not None and (code in STRUCT_CODES or code.startswith("INVALID_"))
                r["gfail"] = s.get("outcome") == "failed" and (s.get("planner_trace") or {}).get("error_stage") == "planner"
                r["repair"] = len(s.get("llm_calls") or []) > 1
                calls = s.get("hf_calls") or []
                r["input_tokens"] = calls[0]["prompt_tokens"] if calls else 0
                r["gen_tokens"] = sum(c["generated_tokens"] for c in calls)
                r["thinking_tokens"] = (tp.get(i) or {}).get("thinking")
                r["json_tokens"] = (tp.get(i) or {}).get("json")
            samples.append(rows)
        ids = list(samples[0])
        per_set[set_name] = len(ids)
        for f in fields:
            arr = np.array([[float(s[i][f]) if s[i][f] is not None else np.nan for s in samples] for i in ids])
            mats.setdefault(f, []).append(arr.mean(axis=1))
        items += [f"{set_name}/{i}" for i in ids]
    return items, {f: np.concatenate(v) for f, v in mats.items()}, per_set


def cmp(a, b, field):
    d = b[field] - a[field]
    mean, (lo, hi) = ci(d)
    return {"diff_pp": round(100 * mean, 2), "ci95_pp": [round(100 * lo, 2), round(100 * hi, 2)]}


def latency(path):
    d = json.loads((ROOT / path).read_text(encoding="utf-8"))
    secs = [sum(c["server_seconds"] for c in r["hf_calls"]) for r in d["rows"]]
    return statistics.median(secs)


def gates(spec):
    sets = spec["sets"]
    loaded = {arm: load_arm(spec["cells"][arm], sets) for arm in spec["cells"]}
    items = {arm: v[0] for arm, v in loaded.items()}
    if len({tuple(v) for v in items.values()}) != 1:
        raise SystemExit("cells cover different items")
    m = {arm: v[1] for arm, v in loaded.items()}
    lat = None
    if spec.get("latency"):
        lb = latency(spec["latency"]["base"])
        lat = {arm: round(latency(spec["latency"][arm]) / lb, 3) for arm in ("F", "P")}
    out = decide(m, lat)
    out.update(label=spec.get("label"), items=len(items["F"]), per_set_items=loaded["F"][2])
    return out


def decide(m, latency_ratio=None):
    """문항별 행렬(m[arm][지표] = 문항 값 배열)과 지연 비로 선행 조건과 Gate A–E를 계산한다(합성 데이터 시험용으로 분리)."""
    out = {"cells": {}}
    for arm, mm in m.items():
        out["cells"][arm] = {f: round(100 * float(np.nanmean(mm[f])), 2) for f in ("ok", "U", "silent", "dt_missing", "mm_nm", "struct", "gfail", "repair")}
        out["cells"][arm]["tokens_median"] = {f: float(np.nanmedian(mm[f])) for f in ("input_tokens", "gen_tokens", "thinking_tokens", "json_tokens")}
    if "base" in m:
        out["prerequisite"] = {}
        for arm in ("F", "P"):
            okc, uc = cmp(m["base"], m[arm], "ok"), cmp(m["base"], m[arm], "U")
            out["prerequisite"][arm] = {"ok_vs_base": okc, "U_vs_base": uc, "pass": okc["ci95_pp"][0] > 0 and uc["ci95_pp"][0] <= 0}
    F, P = m["F"], m["P"]
    a = cmp(F, P, "ok")
    half = (a["ci95_pp"][1] - a["ci95_pp"][0]) / 2
    g = {"A": {**a, "rule": "P−F ok CI 하한 ≥ −5%p", "pass": a["ci95_pp"][0] >= 100 * MARGIN,
               "undecidable_if_fail": half > 5.0}}
    b = cmp(F, P, "dt_missing")
    g["B"] = {**b, "rule": "dt_missing P−F CI 하한 ≤ 0", "pass": b["ci95_pp"][0] <= 0}
    c = cmp(F, P, "silent")
    g["C"] = {**c, "rule": "조용한 오답 P−F CI 하한 ≤ 0", "pass": c["ci95_pp"][0] <= 0}
    d1 = cmp(F, P, "mm_nm")
    d2 = {k: cmp(F, P, k) for k in ("struct", "gfail", "repair")}
    g["D"] = {"mm_nm": d1, "improve_any": d2, "rule": "(1) MM+NM P−F CI 하한 ≤ 0 그리고 (2) 구조·grounding failure·repair 중 하나 이상 P−F CI 상한 < 0",
              "pass": d1["ci95_pp"][0] <= 0 and any(v["ci95_pp"][1] < 0 for v in d2.values())}
    e = {"rule": "(1) P·F 지연 비 ≤ 1.5 (2) JSON token 중앙값 P ≤ 0.7·F (3) 생성 token 중앙값 P ≤ F"}
    jf, jp = np.nanmedian(F["json_tokens"]), np.nanmedian(P["json_tokens"])
    gf, gp = np.nanmedian(F["gen_tokens"]), np.nanmedian(P["gen_tokens"])
    e["json_tokens_median"] = {"F": float(jf), "P": float(jp), "reduction_pct": round(float(100 * (1 - jp / jf)), 2) if jf else None}
    e["gen_tokens_median"] = {"F": float(gf), "P": float(gp)}
    e["input_tokens_median"] = {"F": float(np.nanmedian(F["input_tokens"])), "P": float(np.nanmedian(P["input_tokens"]))}
    e["thinking_tokens_median"] = {"F": float(np.nanmedian(F["thinking_tokens"])), "P": float(np.nanmedian(P["thinking_tokens"]))}
    cond2 = bool(jf) and bool(jp <= 0.7 * jf)
    cond3 = bool(gp <= gf)
    if latency_ratio:
        e["latency_ratio"] = latency_ratio
        cond1 = all(v <= 1.5 for v in latency_ratio.values())
    else:
        e["latency_ratio"], cond1 = None, None
    e["conditions"] = {"1_latency": cond1, "2_json_reduction": cond2, "3_gen_tokens": cond3}
    e["pass"] = None if cond1 is None else (cond1 and cond2 and cond3)
    g["E"] = e
    out["gates"] = g
    passes = [g[k]["pass"] for k in "ABCDE"]
    out["adopt"] = None if any(x is None for x in passes) else all(passes)
    return out


def table(out):
    g = out["gates"]
    lines = ["| Gate | 지표 | P − F [95% CI] | 통과 조건 | 결과 |", "|---|---|---|---|---|"]
    lines.append(f"| A | grounding_ok | {g['A']['diff_pp']:+.2f} {g['A']['ci95_pp']} | 하한 ≥ −5%p | {'통과' if g['A']['pass'] else ('판정 불가' if g['A']['undecidable_if_fail'] else '불통과')} |")
    lines.append(f"| B | dt_missing | {g['B']['diff_pp']:+.2f} {g['B']['ci95_pp']} | 하한 ≤ 0 | {'통과' if g['B']['pass'] else '불통과'} |")
    lines.append(f"| C | 조용한 오답 | {g['C']['diff_pp']:+.2f} {g['C']['ci95_pp']} | 하한 ≤ 0 | {'통과' if g['C']['pass'] else '불통과'} |")
    d = g["D"]
    lines.append(f"| D | MM+NM / 구조·gfail·repair | {d['mm_nm']['diff_pp']:+.2f} {d['mm_nm']['ci95_pp']} / "
                 + ", ".join(f"{k} {v['diff_pp']:+.2f} {v['ci95_pp']}" for k, v in d["improve_any"].items()) + f" | (1)·(2) | {'통과' if d['pass'] else '불통과'} |")
    e = g["E"]
    lines.append(f"| E | 지연 비 {e['latency_ratio']}, JSON token {e['json_tokens_median']}, 생성 token {e['gen_tokens_median']} | – | (1)(2)(3) | "
                 f"{'통과' if e['pass'] else ('미측정' if e['pass'] is None else '불통과')} |")
    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--spec", required=True)
    p.add_argument("--out", required=True)
    a = p.parse_args()
    spec = json.loads(Path(a.spec).read_text(encoding="utf-8"))
    out = gates(spec)
    out["table_md"] = table(out)
    Path(a.out).write_text(json.dumps(out, ensure_ascii=False, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o)) + "\n", encoding="utf-8")
    print(out["table_md"])
    print(json.dumps({"prerequisite": out.get("prerequisite"), "adopt": out["adopt"], "cells": out["cells"]}, ensure_ascii=False, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o)))


if __name__ == "__main__":
    main()
