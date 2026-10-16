# -*- coding: utf-8 -*-
"""batch009 검토 시트(batch007 v2 형식)와 J12 초안 기준 판정. 모델 호출 없음. **승인하지 않는다.**

    hfvenv/bin/python sft_dpo_inventory/batch009/build_review.py   # -> review/batch009_review_v1.xlsx, j12_draft_judgement.json

- 신호: base 첫 응답(J11, vLLM BF16 greedy, Full prompt)이 초안과 같은가, J12 arm별 표본 9개(greedy 1 + 8) 중 초안과 같은 grounding 수
  (조건 계층 전 원응답, Partial은 completion 뒤 — ``judge6``와 같은 규칙, gold = 초안 grounding).
- 우선순위: 높음 = J11 다름, 또는 어느 arm이든 J12 ≤ 3/9, 또는 측정 span 미확인. 그 밖 보통.
- Claude 2차 검토 권고 열(결정 130 G0과 같은 방식: Claude 2차 검토 → 사용자 결정): 초안 작성자도 Claude라 같은 눈으로 본 의견이다. 검증 사슬·겹침 검사 통과는 승인이 아니다.
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
RAW = ROOT / "training/generated/pilot_006/self_2b/raw"
TAIL = ["결정(승인/수정/보류/제외)", "수정 grounding(JSON)", "수정 질문", "메모", "검토자", "검토일"]


def judge_j12(cands):
    import evaluate_vendor100 as EV
    from geoflow.planner import parse_planner_json
    from grounding.completion import complete_grounding_payload
    from training.data.thinking import split_response
    out = {}
    for arm in ("full", "partial"):
        p = RAW / f"J12_{arm}_raw.jsonl"
        if not p.exists():
            continue
        per = {}
        for line in p.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            c = cands.get(r["id"])
            if c is None:
                continue
            ok = False
            try:
                if r["done_reason"] != "length" and "</think>" in r["raw_text"]:
                    pl = parse_planner_json(split_response(r["raw_text"])[1])
                    pl = complete_grounding_payload(pl) if arm == "partial" else pl
                    ok = bool(EV.grounding_check({"gold_grounding": c["draft_grounding"], "gold": None}, pl)[0])
            except Exception:  # noqa: BLE001
                ok = False
            q = per.setdefault(r["id"], {"samples": 0, "correct": 0, "correct_trace_ids": []})
            q["samples"] += 1
            q["correct"] += ok
            if ok:
                q["correct_trace_ids"].append(r["trace_id"])
        out[arm] = per
    return out


def main():
    cands = {c["id"]: c for c in json.loads((HERE / "candidates_checked.json").read_text(encoding="utf-8"))["candidates"]}
    first = {}
    fp = HERE / "base_first_response.jsonl"
    if fp.exists():
        rows = [json.loads(l) for l in fp.read_text(encoding="utf-8").splitlines() if l.strip()]
        first = {r["id"]: r for r in rows[1:]}
    j12 = judge_j12(cands)
    (HERE / "j12_draft_judgement.json").write_text(json.dumps({"gold": "batch009 초안(승인 아님)", "arms": j12}, ensure_ascii=False, indent=1) + "\n",
                                                   encoding="utf-8")
    rows, counts = [], Counter()
    for i, c in cands.items():
        bm = first.get(i, {}).get("matches_gold")
        jf = j12.get("full", {}).get(i, {}).get("correct")
        jp = j12.get("partial", {}).get(i, {}).get("correct")
        span = bool(c.get("span_flags"))
        pr = "높음" if bm is False or (jf is not None and jf <= 3) or (jp is not None and jp <= 3) or span else "보통"
        counts[pr] += 1
        rec = "수정(측정 span)" if span else "승인"
        why = ("질문에 측정 표현(건수)이 없어 span을 찾지 못했다. 뜻은 정답 호출과 맞지만 측정 text가 비어 학습 레코드의 측정 span이 없다. "
               "질문에 '건수'를 넣는 수정 또는 그대로 승인(측정 text 없이)을 사람이 정한다." if span else
               "정답 호출이 질문의 장소 끝(od_role)·묶는 끝(dimension_target)·묶음 단위·순위와 맞다. 검증 사슬·결정 120 겹침 검사 통과. "
               + ("결정 54식 예외: " + c["decision_120"] if c["decision_120"].startswith("남김(") else ""))
        rows.append([i, pr, c["gap"], c["question"], json.dumps(c["draft_grounding"], ensure_ascii=False), c["rationale"],
                     "" if bm is None else ("같음" if bm else "다름"), "" if jf is None else f"{jf}/9", "" if jp is None else f"{jp}/9",
                     c["decision_120"], rec, why, *[""] * len(TAIL)])
    rows.sort(key=lambda r: (r[1] != "높음", r[0]))
    (HERE / "review").mkdir(exist_ok=True)
    guide = [["무엇인가", "batch009 후보 검토 시트 v1(Claude 초안, 승인 아님). R2 약점 보강(지시 H3). 설계·겹침 검사·빠진 후보는 README.md"],
             ["신호", "J11 = base 첫 응답(vLLM BF16 greedy, Full prompt)이 초안과 같은가. J12 = arm별 base 표본 9개 중 초안과 같은 grounding 수(조건 계층 전)."],
             ["우선순위", "높음 = J11 다름, 또는 J12 ≤ 3/9(어느 arm이든), 또는 측정 span 미확인. 그 밖 보통. 우선순위는 판정이 아니다."],
             ["Claude 2차 검토 권고", "초안 작성자도 Claude다. 같은 눈으로 본 의견이므로 사람이 정답 호출과 질문을 직접 대조한다."],
             ["결정 칸", "승인 / 수정 / 보류 / 제외, 수정 grounding(JSON), 수정 질문, 메모, 검토자, 검토일"]]
    B4.write_workbook(HERE / "review/batch009_review_v1.xlsx", [
        ("안내", ["항목", "설명"], guide),
        ("batch009", ["id", "우선순위", "약점", "질문", "초안 grounding", "근거", "J11 첫 응답", "J12 Full 일치(9개 중)", "J12 Partial 일치(9개 중)",
                      "결정 120 분류", "Claude 2차 검토 권고", "Claude 근거", *TAIL], rows)])
    summary = {"candidates": len(cands), "priority": dict(counts), "j11_available": bool(first), "j12_arms": sorted(j12),
               "j11_matches": sum(1 for i in cands if first.get(i, {}).get("matches_gold")),
               "j12_with_correct": {arm: sum(1 for q in per.values() if q["correct"]) for arm, per in j12.items()},
               "recommend": dict(Counter(r[10] for r in rows))}
    (HERE / "review/summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
