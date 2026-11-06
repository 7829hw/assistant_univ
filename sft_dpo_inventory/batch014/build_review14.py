# -*- coding: utf-8 -*-
"""batch014 검토 시트와 J-b014 진단(결정 263 D5, ablation_013 PLAN 5.4). ``batch012/build_review12.py``의 ``pipeline_refusal``·``first``의 방식과
``batch004/build_review.write_workbook``을 그대로 불러 쓴다(그 파일들은 그대로). 모델 호출 없음. **승인하지 않는다.** 진단, 판정 아님.

    runtime/envs/hf/bin/python sft_dpo_inventory/batch014/build_review14.py
    # -> review/batch014_review_v1.xlsx·batch014_review_v1.md, jb014_draft_judgement.json, review/summary.json
    # J-b014 원문이 아직 없으면 신호 칸이 빈 시트(v1)만 만든다.

신호(초안 gold 기준, 승인 아님; 모두 답하는 문항):
- 표본 하나: 응답 grounding이 초안과 같은가(``EV.grounding_check``), 거부로 끝났는가(모델 ``{"unsupported": true}`` 또는 응답 grounding이 gold 파이프라인(mock)에서 거부로 끝남),
  오답 = 거부 아님 & 초안과 다름. batch012 ``judge_text``와 같은 판정이되, 일치 계산을 r2만이 아니라 T5(``general_answer``)에도 한다.
- J-b014 첫 응답(base greedy)·표본(greedy 1 + 8), J-b014-v4(V4 o1016·o7·o43, A0 o1102·o211102·o2026113 greedy).
- T5 출발 역할: 응답 grounding의 ``dimension_target`` 값이 초안과 다른 수(예: pickup ↔ both), 장소 끝(od_role: pickup·dropoff)이 초안과 다른 수.
- 우선순위(판정 아님): 높음 = base 표본 일치 ≤ 3/9, 또는 V4 6 seed 중 3개 이상이 거부로 끝남.
- 2차 검토 권고: base 표본 일치 ≤ 1/9이고 V4 6 seed 일치 ≤ 1이면 "수정 권고(질문 표현·정답 대조)"(J-b014 결과를 본 뒤 더한 규칙, 권고일 뿐).
"""
import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
_spec = importlib.util.spec_from_file_location("b012_review", ROOT / "sft_dpo_inventory/batch012/build_review12.py")
R12 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(R12)
RAW = ROOT / "training/generated/ablation_013/self/raw"
TAIL = R12.TAIL
V4N = ("V4_o1016", "V4_o7", "V4_o43", "A0_o1102", "A0_o211102", "A0_o2026113")
GROUP = {"T1v": "운행 요금 × POI 주변(대체, 지시 범위 밖)", "T3": "요금 지표 × 시도·요일", "T4": "실차 건수 × 하루 × POI 주변 도착", "T5": "OD 상위 N(일반 답하는 문항)"}


def roles(payload):
    """payload 안의 dimension_target 값과 LOCATION od_role 목록(정렬)."""
    dts, ods = [], []

    def walk(x):
        if isinstance(x, dict):
            for k, v in x.items():
                if k == "dimension_target" and isinstance(v, str):
                    dts.append(v)
                if k == "od_role" and isinstance(v, str) and v:
                    ods.append(v)
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(payload)
    return sorted(set(dts)), sorted(ods)


def judge_text(raw_text, done_reason, cand):
    import evaluate_vendor100 as EV
    from geoflow.planner import parse_planner_json
    from training.data.thinking import split_response
    out = {"model_refusal": False, "pipeline_refusal": False, "match": False, "outcome": "parse_failed", "dt_diff": False, "od_diff": False, "parsed": False}
    if done_reason == "length" or "</think>" not in (raw_text or ""):
        out["outcome"] = "truncated_or_no_think"
        return out
    try:
        pl = parse_planner_json(split_response(raw_text)[1])
    except Exception:  # noqa: BLE001
        return out
    if pl is None:
        return out
    out["parsed"] = True
    if pl.get("unsupported"):
        out.update(model_refusal=True, outcome="unsupported:UNSUPPORTED_QUESTION")
        return out
    out["match"] = bool(EV.grounding_check({"gold_grounding": cand["draft_grounding"], "gold": None}, pl)[0])
    gdt, god = roles(cand["draft_grounding"])
    rdt, rod = roles(pl)
    out["dt_diff"], out["od_diff"] = gdt != rdt, god != rod
    out["pipeline_refusal"], out["outcome"] = R12.pipeline_refusal(pl, cand["question"])
    return out


def judge_raw(path, cands):
    per = {}
    if not path.exists():
        return per
    for line in path.read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        c = cands.get(r["id"])
        if c is None:
            continue
        j = judge_text(r.get("raw_text"), r.get("done_reason"), c)
        q = per.setdefault(r["id"], {"samples": 0, "model_refusal": 0, "pipeline_refusal": 0, "refusal_any": 0, "match": 0, "wrong": 0, "dt_diff": 0, "od_diff": 0,
                                     "outcomes": Counter(), "refusal_trace_ids": [], "match_trace_ids": []})
        ref = j["model_refusal"] or j["pipeline_refusal"]
        q["samples"] += 1
        q["model_refusal"] += j["model_refusal"]
        q["pipeline_refusal"] += j["pipeline_refusal"]
        q["refusal_any"] += ref
        q["match"] += j["match"]
        q["wrong"] += (not ref) and not j["match"]
        q["dt_diff"] += (not ref) and j["dt_diff"]
        q["od_diff"] += (not ref) and j["od_diff"]
        q["outcomes"][j["outcome"]] += 1
        if ref:
            q["refusal_trace_ids"].append(r.get("trace_id"))
        if j["match"]:
            q["match_trace_ids"].append(r.get("trace_id"))
    for q in per.values():
        q["outcomes"] = dict(q["outcomes"])
    return per


def first(path, raw_path, cands):
    rows = {}
    if path.exists():
        rows = {r["id"]: r for r in (json.loads(l) for l in path.read_text(encoding="utf-8").splitlines()[1:] if l.strip())}
    j = judge_raw(raw_path, cands)
    return {i: {"matches_gold": rows.get(i, {}).get("matches_gold"), "parse_state": rows.get(i, {}).get("parse_state"), **(j.get(i) or {})} for i in cands}


def mark(r):
    if not r.get("samples"):
        return ""
    return ("같음" if r.get("match") else "다름") + (", 거부" + ("(모델)" if r.get("model_refusal") else "") if r.get("refusal_any") else "")


def why_text(c):
    g = c["group"]
    if g == "T5":
        return "지원되는 OD 상위 N 질문. 출발·도착 끝과 dimension_target·순위 방향·개수가 질문과 맞다. 검증 사슬·결정 120 겹침·CT10K·H-dev·H-final(내용 비공개) 검사 통과(free_structures14 family 밖)."
    base = f"지원되는 질문(짝지을 거부: {c.get('pair_refusal_memo')}). 정답 호출이 질문과 맞다. 검증 사슬·결정 120 겹침·CT10K·H-dev·H-final(내용 비공개) 검사 통과(free_structures14 family 밖)."
    if g == "T1v":
        return base + " 지시 범위(T1–T5) 밖 대체 묶음이다. T1·T2(운행 요금 × 시도·없음·시군구)는 모든 구조가 보호 넷 family에 걸려 쓸 수 없었다."
    return base


def rec(c, base_match=None, v4_match=None):
    """2차 검토 권고(승인 아님). base 표본·V4 6 seed 모두 일치 ≤ 1이면 질문 표현과 정답을 다시 맞춰 보라는 수정 권고."""
    if base_match is not None and v4_match is not None and base_match <= 1 and v4_match <= 1:
        note = " — '일대'를 모델이 POI 주변(vicinity)으로 읽지 않음: '근처'·'주변'으로 바꾸기 권고" if "일대" in c["question"] else ""
        return "수정 권고(질문 표현·정답 대조)" + note
    return "범위 결정 뒤 승인(대체 묶음)" if c["group"] == "T1v" else "승인"


def main():
    cands = {c["id"]: c for c in json.loads((HERE / "candidates_checked.json").read_text(encoding="utf-8"))["candidates"]}
    bf = first(HERE / "base_first_response.jsonl", RAW / "Jb014_first_raw.jsonl", cands)
    bs = judge_raw(RAW / "Jb014_full_raw.jsonl", cands)
    vf = {n: first(HERE / f"v4_first_response_{n}.jsonl", RAW / f"Jv4b014_{n}_first_raw.jsonl", cands) for n in V4N}
    have = {"base_first": any(v.get("samples") for v in bf.values()), "base_samples": bool(bs), **{n: any(v.get("samples") for v in vf[n].values()) for n in V4N}}
    (HERE / "jb014_draft_judgement.json").write_text(json.dumps({"gold": "batch014 초안(승인 아님)", "available": have, "base_first": bf, "base_samples": bs, "v4_first": vf},
                                                              ensure_ascii=False, indent=1, default=list) + "\n", encoding="utf-8")
    rows, counts, md = [], Counter(), []
    for i, c in cands.items():
        s = bs.get(i, {})
        n = s.get("samples", 0)
        v4ref = sum(1 for m in V4N if vf[m][i].get("refusal_any"))
        v4n = sum(1 for m in V4N if vf[m][i].get("samples"))
        sig_s = f"일치 {s.get('match', 0)}/{n}, 거부 {s.get('refusal_any', 0)}/{n}" if n else ""
        sig_v = f"거부 {v4ref}/{v4n}, 일치 {sum(1 for m in V4N if vf[m][i].get('match'))}/{v4n}" if v4n else ""
        pr = "높음" if (n and s.get("match", 0) <= 3) or v4ref >= 3 else ("보통" if n or v4n else "")
        mt = (s.get("match", 0), sum(1 for m in V4N if vf[m][i].get("match"))) if n and v4n else (None, None)
        counts[pr or "신호 없음"] += 1
        rows.append([i, pr, c["group"], GROUP[c["group"]], c["subtype"], c["gap"], c.get("pair_refusal_memo") or "", c["question"], c["gold_text"],
                     mark(bf[i]), sig_s, sig_v, *[mark(vf[m][i]) for m in V4N], c["decision_120"], rec(c, *mt), why_text(c), *[""] * len(TAIL)])
        md.append(f"| {i} | {pr} | {c['group']} | {c['question']} | `{c['gold_text'].replace(chr(10), ' ; ')}` | {c.get('pair_refusal_memo') or ''} | {mark(bf[i])} | {sig_s} | {sig_v} | {rec(c, *mt)} |")
    rows.sort(key=lambda r: (r[1] != "높음", r[0]))
    (HERE / "review").mkdir(exist_ok=True)
    guide = [["무엇인가", "batch014 후보 검토 시트 v1(Claude 초안, 승인 아님, 학습에 쓰지 않음). 결정 263 D5: 근접 대조 보강(T1v 대체·T3·T4) + OD 상위 N(T5). 설계·검사는 README.md"],
             ["T1·T2가 없는 이유", "운행 요금 × 시도·없음·시군구 구조는 모두 보호 넷(selection_v2·holdout·valid98·aux_test_v1)·selection_v1·확장·thor family에 걸린다(free_structures14.json, 72/72). T1v는 POI 주변 대체 묶음(지시 범위 밖)."],
             ["짝지을 거부 패턴", "메모 열. teacher 입력에는 넣지 않는다(결정 248)."],
             ["신호", "J-b014 첫 응답 = base greedy, 표본 = base greedy 1 + 8, V4 6 seed = V4 o1016·o7·o43 + A0 o1102·o211102·o2026113 greedy. "
                     "'같음' = 초안과 같은 grounding, '거부' = 모델 거부 출력 또는 응답 grounding이 gold 파이프라인에서 거부로 끝남."],
             ["우선순위", "높음 = base 표본 일치 ≤ 3/9, 또는 V4 6 seed 중 3개 이상 거부. 판정이 아니다."],
             ["Claude 2차 검토 권고", "초안 작성자도 Claude다. 권고일 뿐 승인이 아니다. 사람이 정답 호출이 질문과 맞는지 직접 본다."],
             ["결정 칸", "승인 / 수정 / 보류 / 제외, 수정 질문, 수정 정답(호출), 메모, 검토자, 검토일"]]
    head = ["id", "우선순위", "묶음", "묶음 설명", "유형", "가까운 거부 범주", "짝지을 거부 패턴(메모)", "질문", "초안 정답", "J-b014 첫 응답(base)", "J-b014 표본(base, 9개)",
            "J-b014-v4(6 seed)", *[f"V4 {m}" for m in V4N], "결정 120 분류", "Claude 2차 검토 권고", "Claude 근거", *TAIL]
    R12.B4.write_workbook(HERE / "review/batch014_review_v1.xlsx", [("안내", ["항목", "설명"], guide), ("batch014", head, rows)])
    (HERE / "review/batch014_review_v1.md").write_text(
        "# batch014 검토 시트 v1(초안, 승인 아님)\n\n같은 내용의 XLSX: `batch014_review_v1.xlsx`(결정 칸 포함). 신호 칸이 비어 있으면 J-b014가 아직 돌지 않은 것이다.\n\n"
        + "\n".join(f"- **{a}**: {b}" for a, b in guide) + "\n\n"
        + "| id | 우선순위 | 묶음 | 질문 | 초안 정답 | 짝지을 거부 패턴 | base 첫 응답 | base 표본 | V4 6 seed | Claude 2차 검토 권고 |\n|---|---|---|---|---|---|---|---|---|---|\n"
        + "\n".join(md) + "\n", encoding="utf-8")
    ids = list(cands)

    def agg(sel):
        out = {"items": len(sel), "base_first_match": sum(bool(bf[i].get("match")) for i in sel), "base_first_refusal": sum(bool(bf[i].get("refusal_any")) for i in sel),
               "base_samples_total": sum(bs.get(i, {}).get("samples", 0) for i in sel), "base_samples_match": sum(bs.get(i, {}).get("match", 0) for i in sel),
               "base_samples_refusal": sum(bs.get(i, {}).get("refusal_any", 0) for i in sel),
               "items_with_base_match_sample": sum(1 for i in sel if bs.get(i, {}).get("match", 0) > 0),
               "v4_first_by_seed": {m: {"answered": sum(1 for i in sel if vf[m][i].get("samples")), "refusal": sum(bool(vf[m][i].get("refusal_any")) for i in sel),
                                        "match": sum(bool(vf[m][i].get("match")) for i in sel), "wrong": sum(bool(vf[m][i].get("wrong")) for i in sel),
                                        "dt_diff": sum(bool(vf[m][i].get("dt_diff")) for i in sel), "od_diff": sum(bool(vf[m][i].get("od_diff")) for i in sel)} for m in V4N}}
        tot = sum(v["answered"] for v in out["v4_first_by_seed"].values())
        out["v4_6seed"] = {k: sum(v[k] for v in out["v4_first_by_seed"].values()) for k in ("refusal", "match", "wrong", "dt_diff", "od_diff")}
        out["v4_6seed"]["samples"] = tot
        out["v4_6seed"].update({f"{k}_pct": round(100 * out["v4_6seed"][k] / tot, 1) if tot else None for k in ("refusal", "match", "wrong")})
        out["base_first_dt_diff"] = sum(bool(bf[i].get("dt_diff")) for i in sel)
        out["base_first_od_diff"] = sum(bool(bf[i].get("od_diff")) for i in sel)
        out["base_samples_dt_diff"] = sum(bs.get(i, {}).get("dt_diff", 0) for i in sel)
        out["base_samples_od_diff"] = sum(bs.get(i, {}).get("od_diff", 0) for i in sel)
        return out
    summary = {"note": "진단, 판정 아님. 초안 gold 기준(승인 아님).", "candidates": len(cands), "available": have, "priority": dict(counts), "all": agg(ids),
               "by_group": {g: agg([i for i in ids if cands[i]["group"] == g]) for g in GROUP},
               "by_subtype": {s: agg([i for i in ids if cands[i]["subtype"] == s]) for s in sorted({c["subtype"] for c in cands.values()})},
               "v4_refusal_ids": {m: sorted(i for i in ids if vf[m][i].get("refusal_any")) for m in V4N}}
    (HERE / "review/summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("candidates", "available", "priority")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
