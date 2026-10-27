# -*- coding: utf-8 -*-
"""batch013 검토 시트와 J-b013·J-p9-b013·J-b2f-b013 초안 기준 판정(pilot_010 준비 C2, 결정 243). ``batch012/build_review12.py``의 판정 함수(``judge_raw``·``first``)를
그대로 불러 쓴다(그 파일은 그대로). 모델 호출 없음. **승인하지 않는다.**

    hfvenv/bin/python sft_dpo_inventory/batch013/build_review13.py   # -> review/batch013_review_v1.xlsx, jb013_draft_judgement.json, review/summary.json

신호(초안 gold 기준, 승인 아님; 모두 답하는 문항):
- 응답 grounding이 초안과 같은가(``EV.grounding_check``), 그리고 거부(모델 ``{"unsupported": true}`` 또는 응답 grounding이 gold 파이프라인(mock)에서 거부로 끝남)로 끝났는가(과잉 거부).
- J-b013 첫 응답(base greedy)·표본(greedy 1 + 8), J-p9-b013(P9-o43 checkpoint-1993 greedy), J-b2f-b013(B2 F-o11 checkpoint-1811 greedy).
- 우선순위: 높음 = base 표본 일치 ≤ 3/9, 또는 P9·B2 F 첫 응답이 거부로 끝남. 그 밖 보통(판정 아님).
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
RAW = ROOT / "training/generated/pilot_010/self/raw"
TAIL = R12.TAIL
SUB = {"bucket": "묶음(bucket+rollup)", "dimension": "장소 없는 차원", "taxi_type": "택시 유형", "daily_agg": "일 단위 값의 집계", "record": "지난 기간 실적",
       "rpm": "RPM 최솟값", "passage_count": "통과량 건수 H3", "trip_count": "실차 건수 차원"}


def mark(r):
    return ("같음" if r.get("matches_gold") else "다름") + (", 거부" + ("(모델)" if r.get("model_refusal") else "") if r.get("refusal_any") else "") if r.get("parse_state") else ""


def main():
    cands = {c["id"]: c for c in json.loads((HERE / "candidates_checked.json").read_text(encoding="utf-8"))["candidates"]}
    bf = R12.first(HERE / "base_first_response.jsonl", RAW / "Jb013_first_raw.jsonl", cands)
    pf = R12.first(HERE / "p9_first_response.jsonl", RAW / "Jp9b013_first_raw.jsonl", cands)
    ff = R12.first(HERE / "b2f_first_response.jsonl", RAW / "Jb2fb013_first_raw.jsonl", cands)
    bs = R12.judge_raw(RAW / "Jb013_full_raw.jsonl", cands)
    (HERE / "jb013_draft_judgement.json").write_text(json.dumps({"gold": "batch013 초안(승인 아님)", "base_first": bf, "p9_first": pf, "b2f_first": ff, "base_samples": bs},
                                                              ensure_ascii=False, indent=1, default=list) + "\n", encoding="utf-8")
    rows, counts = [], Counter()
    for i, c in cands.items():
        s = bs.get(i, {})
        n = s.get("samples", 0)
        f, p, b = bf.get(i, {}), pf.get(i, {}), ff.get(i, {})
        sig_s = f"일치 {s.get('match', 0)}/{n}, 거부 {s.get('refusal_any', 0)}/{n}" if n else ""
        pr = "높음" if (n and s.get("match", 0) <= 3) or p.get("refusal_any") or b.get("refusal_any") else "보통"
        counts[pr] += 1
        why = ("지원되는 질문(" + c["rationale"] + "). 정답 호출이 질문과 맞다. 검증 사슬·결정 120 겹침 검사·기간·묶음 길이 통과(" +
               ("batch010 빈 구조" if c["group"] == "c1" else "free_structures13 family 밖 구조") + ").")
        rows.append([i, pr, c["group"], SUB[c["subtype"]], c["gap"], c["question"], c["gold_text"], c["rationale"], mark(f), sig_s, mark(p), mark(b),
                     c["decision_120"], "승인", why, *[""] * len(TAIL)])
    rows.sort(key=lambda r: (r[1] != "높음", r[0]))
    (HERE / "review").mkdir(exist_ok=True)
    guide = [["무엇인가", "batch013 후보 검토 시트 v1(Claude 초안, 승인 아님). pilot_010 학습용 요금 지표 중심 근접 대조(결정 243): c1 요금 지표 48·c2 다른 tool 29(초안 80 중 검사 통과 77). 설계·검사는 README.md"],
             ["가까운 거부 범주", "겉모습이 비슷하지만 답할 수 없는 질문 범주(batch011·012 r2와 같은 이름). TEACH-C 지시에 붙는다."],
             ["신호", "J-b013 첫 응답 = base greedy, J-b013 표본 = base greedy 1 + 8, J-p9-b013 = P9-o43 greedy, J-b2f-b013 = B2 F-o11 greedy. "
                     "'같음' = 초안과 같은 grounding, '거부' = 모델 거부 출력 또는 응답 grounding이 gold 파이프라인에서 거부로 끝남(과잉 거부)."],
             ["우선순위", "높음 = base 표본 일치 ≤ 3/9, 또는 P9·B2 F 첫 응답이 거부로 끝남. 판정이 아니다."],
             ["Claude 2차 검토 권고", "초안 작성자도 Claude다. 같은 눈으로 본 의견이므로 사람이 정답 호출이 질문과 맞는지 직접 본다."],
             ["결정 칸", "승인 / 수정 / 보류 / 제외, 수정 질문, 수정 정답(호출), 메모, 검토자, 검토일"]]
    R12.B4.write_workbook(HERE / "review/batch013_review_v1.xlsx", [
        ("안내", ["항목", "설명"], guide),
        ("batch013", ["id", "우선순위", "묶음", "유형", "가까운 거부 범주", "질문", "초안 정답", "근거", "J-b013 첫 응답(base)", "J-b013 표본(base, 9개)",
                      "J-p9-b013 첫 응답(P9-o43)", "J-b2f-b013 첫 응답(B2 F-o11)", "결정 120 분류", "Claude 2차 검토 권고", "Claude 근거", *TAIL], rows)])
    ids = list(cands)

    def agg(sel):
        return {"items": len(sel),
                "base_first_match": sum(bool(bf[i].get("matches_gold")) for i in sel), "base_first_refusal": sum(bool(bf[i].get("refusal_any")) for i in sel),
                "base_samples_total": sum(bs.get(i, {}).get("samples", 0) for i in sel), "base_samples_match": sum(bs.get(i, {}).get("match", 0) for i in sel),
                "base_samples_refusal": sum(bs.get(i, {}).get("refusal_any", 0) for i in sel),
                "items_with_base_match_sample": sum(1 for i in sel if bs.get(i, {}).get("match", 0) > 0),
                "p9_first_match": sum(bool(pf[i].get("matches_gold")) for i in sel), "p9_first_refusal": sum(bool(pf[i].get("refusal_any")) for i in sel),
                "p9_first_model_refusal": sum(bool(pf[i].get("model_refusal")) for i in sel),
                "b2f_first_match": sum(bool(ff[i].get("matches_gold")) for i in sel), "b2f_first_refusal": sum(bool(ff[i].get("refusal_any")) for i in sel),
                "b2f_first_model_refusal": sum(bool(ff[i].get("model_refusal")) for i in sel)}
    summary = {"candidates": len(cands), "priority": dict(counts), "all": agg(ids),
               "by_group": {g: agg([i for i in ids if cands[i]["group"] == g]) for g in ("c1", "c2")},
               "by_subtype": {s: agg([i for i in ids if cands[i]["subtype"] == s]) for s in SUB},
               "p9_first_refusal_ids": sorted(i for i in ids if pf[i].get("refusal_any")),
               "b2f_first_refusal_ids": sorted(i for i in ids if ff[i].get("refusal_any"))}
    (HERE / "review/summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
