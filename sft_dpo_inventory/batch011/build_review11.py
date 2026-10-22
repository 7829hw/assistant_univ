# -*- coding: utf-8 -*-
"""batch011 검토 시트(``batch010/build_review10.py`` 사본을 거부 문항에 맞게 바꿈)와 J-b011·J-o11-b011 초안 기준 판정. 모델 호출 없음. **승인하지 않는다.**

    hfvenv/bin/python sft_dpo_inventory/batch011/build_review11.py   # -> review/batch011_review_v1.xlsx, jb011_draft_judgement.json, review/summary.json

신호(초안 gold 기준, 승인 아님):
- r1 거부: (모델) 응답 JSON이 ``{"unsupported": true}``인가, (파이프라인) 응답 grounding을 gold 파이프라인(``EV._GoldPlanner``, mock)에 넣었을 때 결과 상태가
  거부(unsupported·needs_clarification)이고 분석 tool 실행이 없는가 — 둘 중 하나면 "올바른 거부". 표본(greedy 1 + 8)에서 각각 센다.
- r2 근접 대조: 응답 grounding이 초안과 같은가(``EV.grounding_check``, 조건 계층 전), 그리고 거부(모델·파이프라인)로 끝난 표본 수(과잉 거부).
- J-b011 첫 응답(base greedy)·J-o11-b011 첫 응답(F-o11 greedy)은 ``collect6b``/``collect8`` 채점 결과 + 위 파이프라인 판정.
- 우선순위: 높음 = r1에서 base 표본 9개 중 올바른 거부 0, 또는 r2에서 base 표본 일치 ≤ 3/9. 그 밖 보통(판정 아님).
"""
import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
_spec = importlib.util.spec_from_file_location("b004_review", ROOT / "sft_dpo_inventory/batch004/build_review.py")
B4 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(B4)
RAW = ROOT / "training/generated/pilot_008/self/raw"
TAIL = ["결정(승인/수정/보류/제외)", "수정 질문", "수정 정답(호출 또는 거부)", "메모", "검토자", "검토일"]
REFUSED = ("unsupported", "needs_clarification")


def pipeline_refusal(payload, question):
    """응답 grounding → gold 파이프라인(mock) 결과 상태. (거부 여부, outcome:code)."""
    import evaluate_vendor100 as EV
    try:
        obs = EV.run_item(EV._pipeline(EV._GoldPlanner(payload)), question)
    except Exception as error:  # noqa: BLE001
        return False, f"error:{type(error).__name__}"
    analysis = sum(1 for c in (obs.get("calls") or []) if c.get("tool") != "get_place_scope")
    return obs.get("outcome") in REFUSED and analysis == 0, f"{obs.get('outcome')}:{obs.get('error_code')}"


def judge_text(raw_text, done_reason, cand):
    """표본 원문 하나 → {model_refusal, pipeline_refusal, match, outcome}."""
    import evaluate_vendor100 as EV
    from geoflow.planner import parse_planner_json
    from training.data.thinking import split_response
    out = {"model_refusal": False, "pipeline_refusal": False, "match": False, "outcome": "parse_failed"}
    if done_reason == "length" or "</think>" not in (raw_text or ""):
        out["outcome"] = "truncated_or_no_think"
        return out
    try:
        pl = parse_planner_json(split_response(raw_text)[1])
    except Exception:  # noqa: BLE001
        return out
    if pl is None:
        return out
    if pl.get("unsupported"):
        out.update(model_refusal=True, outcome="unsupported:UNSUPPORTED_QUESTION")
        return out
    if cand["kind"] == "r2_contrast":
        out["match"] = bool(EV.grounding_check({"gold_grounding": cand["draft_grounding"], "gold": None}, pl)[0])
    out["pipeline_refusal"], out["outcome"] = pipeline_refusal(pl, cand["question"])
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
        q = per.setdefault(r["id"], {"samples": 0, "model_refusal": 0, "pipeline_refusal": 0, "refusal_any": 0, "match": 0, "outcomes": Counter(),
                                     "refusal_trace_ids": [], "match_trace_ids": []})
        q["samples"] += 1
        q["model_refusal"] += j["model_refusal"]
        q["pipeline_refusal"] += j["pipeline_refusal"]
        q["refusal_any"] += j["model_refusal"] or j["pipeline_refusal"]
        q["match"] += j["match"]
        q["outcomes"][j["outcome"]] += 1
        if j["model_refusal"] or j["pipeline_refusal"]:
            q["refusal_trace_ids"].append(r.get("trace_id"))
        if j["match"]:
            q["match_trace_ids"].append(r.get("trace_id"))
    for q in per.values():
        q["outcomes"] = dict(q["outcomes"])
    return per


def first(path, raw_path, cands):
    """첫 응답: collect 채점(matches_gold) + 원문으로 거부 판정."""
    rows = {}
    if path.exists():
        rows = {r["id"]: r for r in (json.loads(l) for l in path.read_text(encoding="utf-8").splitlines()[1:] if l.strip())}
    j = judge_raw(raw_path, cands)
    return {i: {"matches_gold": rows.get(i, {}).get("matches_gold"), "parse_state": rows.get(i, {}).get("parse_state"), **(j.get(i) or {})} for i in cands}


def main():
    cands = {c["id"]: c for c in json.loads((HERE / "candidates_checked.json").read_text(encoding="utf-8"))["candidates"]}
    bf = first(HERE / "base_first_response.jsonl", RAW / "Jb011_first_raw.jsonl", cands)
    of = first(HERE / "o11_first_response.jsonl", RAW / "Jo11b011_first_raw.jsonl", cands)
    bs = judge_raw(RAW / "Jb011_full_raw.jsonl", cands)
    (HERE / "jb011_draft_judgement.json").write_text(json.dumps({"gold": "batch011 초안(승인 아님)", "base_first": bf, "o11_first": of, "base_samples": bs},
                                                              ensure_ascii=False, indent=1, default=list) + "\n", encoding="utf-8")
    rows, counts = [], Counter()
    for i, c in cands.items():
        s = bs.get(i, {})
        n = s.get("samples", 0)
        f, o = bf.get(i, {}), of.get(i, {})
        if c["kind"] == "r1_refusal":
            sig_first = "거부" if f.get("refusal_any") else "답함/실패"
            sig_o11 = "거부" if o.get("refusal_any") else ("답함/실패" if o.get("samples") else "")
            sig_s = f"{s.get('refusal_any', 0)}/{n}(모델 {s.get('model_refusal', 0)}·파이프라인 {s.get('pipeline_refusal', 0)})" if n else ""
            pr = "높음" if n and s.get("refusal_any", 0) == 0 else "보통"
            rec, why = "승인", "질문의 측정값·조건·대상을 계약 개념·factor로 적을 수 없다(" + c["rationale"] + "). 정답 = {\"unsupported\": true}. 질문·Jaccard 겹침 검사 통과."
        else:
            sig_first = "같음" if f.get("matches_gold") else "다름"
            sig_o11 = ("같음" if o.get("matches_gold") else "다름") if o.get("parse_state") else ""
            sig_s = f"일치 {s.get('match', 0)}/{n}, 거부 {s.get('refusal_any', 0)}/{n}" if n else ""
            pr = "높음" if n and s.get("match", 0) <= 3 else "보통"
            rec, why = "승인", "지원되는 질문(" + c["rationale"] + "). 정답 호출이 질문과 맞다. 검증 사슬·결정 120 겹침 검사 통과(batch010 빈 구조)."
        counts[pr] += 1
        rows.append([i, pr, c["kind"], c["gap"], c["question"], c.get("gold_text") or c.get("target", ""), c["rationale"], sig_first, sig_s, sig_o11,
                     c["decision_120"], rec, why, *[""] * len(TAIL)])
    rows.sort(key=lambda r: (r[1] != "높음", r[0]))
    (HERE / "review").mkdir(exist_ok=True)
    guide = [["무엇인가", "batch011 후보 검토 시트 v1(Claude 초안, 승인 아님). pilot_008 거부 보강(결정 219): r1 거부 60·r2 근접 대조 40. 설계·검사는 README.md"],
             ["r1 정답", "{\"unsupported\": true}(모델 거부, refusal_contract.md 1절 (M)) — 정답 호출 없음"],
             ["신호", "J-b011 첫 응답 = base greedy, J-b011 표본 = base greedy 1 + 8, J-o11-b011 = F-o11 greedy. r1은 '올바른 거부'(모델 거부 출력 또는 응답 grounding이 "
                     "gold 파이프라인에서 거부로 끝남), r2는 초안과 같은 grounding 수와 거부로 끝난 수(과잉 거부)."],
             ["우선순위", "높음 = r1에서 base 표본 중 올바른 거부 0, 또는 r2에서 base 표본 일치 ≤ 3/9. 판정이 아니다."],
             ["Claude 2차 검토 권고", "초안 작성자도 Claude다. 같은 눈으로 본 의견이므로 사람이 질문이 정말 지원되지 않는지(r1)·정답 호출이 맞는지(r2)를 직접 본다."],
             ["결정 칸", "승인 / 수정 / 보류 / 제외, 수정 질문, 수정 정답(호출 또는 거부), 메모, 검토자, 검토일"]]
    B4.write_workbook(HERE / "review/batch011_review_v1.xlsx", [
        ("안내", ["항목", "설명"], guide),
        ("batch011", ["id", "우선순위", "종류", "묶음", "질문", "초안 정답", "근거", "J-b011 첫 응답(base)", "J-b011 표본(base, 9개)", "J-o11-b011 첫 응답(F-o11)",
                      "결정 120 분류", "Claude 2차 검토 권고", "Claude 근거", *TAIL], rows)])
    r1 = [i for i, c in cands.items() if c["kind"] == "r1_refusal"]
    r2 = [i for i, c in cands.items() if c["kind"] == "r2_contrast"]
    summary = {"candidates": len(cands), "priority": dict(counts), "recommend": dict(Counter(r[11] for r in rows)),
               "r1": {"items": len(r1),
                      "base_first_refusal": sum(bool(bf[i].get("refusal_any")) for i in r1), "base_first_model_refusal": sum(bool(bf[i].get("model_refusal")) for i in r1),
                      "o11_first_refusal": sum(bool(of[i].get("refusal_any")) for i in r1), "o11_first_model_refusal": sum(bool(of[i].get("model_refusal")) for i in r1),
                      "base_samples_total": sum(bs.get(i, {}).get("samples", 0) for i in r1),
                      "base_samples_refusal": sum(bs.get(i, {}).get("refusal_any", 0) for i in r1),
                      "base_samples_model_refusal": sum(bs.get(i, {}).get("model_refusal", 0) for i in r1),
                      "items_with_base_refusal_sample": sum(1 for i in r1 if bs.get(i, {}).get("refusal_any", 0) > 0),
                      "items_with_base_model_refusal_sample": sum(1 for i in r1 if bs.get(i, {}).get("model_refusal", 0) > 0),
                      "by_gap_items_with_refusal_sample": dict(Counter(cands[i]["gap"] for i in r1 if bs.get(i, {}).get("refusal_any", 0) > 0))},
               "r2": {"items": len(r2), "base_first_match": sum(bool(bf[i].get("matches_gold")) for i in r2),
                      "o11_first_match": sum(bool(of[i].get("matches_gold")) for i in r2),
                      "base_first_refusal": sum(bool(bf[i].get("refusal_any")) for i in r2), "o11_first_refusal": sum(bool(of[i].get("refusal_any")) for i in r2),
                      "base_samples_total": sum(bs.get(i, {}).get("samples", 0) for i in r2), "base_samples_match": sum(bs.get(i, {}).get("match", 0) for i in r2),
                      "base_samples_refusal": sum(bs.get(i, {}).get("refusal_any", 0) for i in r2),
                      "items_with_base_match_sample": sum(1 for i in r2 if bs.get(i, {}).get("match", 0) > 0)}}
    (HERE / "review/summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
