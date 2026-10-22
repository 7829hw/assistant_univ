# -*- coding: utf-8 -*-
"""refusal_dev 검토 시트(개발 셋 초안, 승인 아님)와 J-rdev 문항별 신호. 모델 호출 없음. **승인하지 않는다.**

    hfvenv/bin/python sft_dpo_inventory/pilot_008/refusal_dev/build_review_rdev.py   # -> review/refusal_dev_review_v1.xlsx, review/summary.json

신호(J-rdev, base·F-o11 각 k=4): 거부 문항은 올바른 거부 수(결과 상태 unsupported·needs_clarification, 분석 tool 없음), 대조 문항은 정답 수(grounding_ok, 거부로 끝나면 오답)와 거부 수.
우선순위: 높음 = 거부 문항에서 base 0/4, 또는 대조 문항에서 base 정답 ≤ 1/4(판정 아님).
"""
import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
P8 = HERE.parent
ROOT = P8.parents[1]
sys.path.insert(0, str(ROOT))
_spec = importlib.util.spec_from_file_location("b004_review", ROOT / "sft_dpo_inventory/batch004/build_review.py")
B4 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(B4)
TAIL = ["결정(승인/수정/보류/제외)", "수정 질문", "수정 정답(호출 또는 거부)", "메모", "검토자", "검토일"]
REFUSED = ("unsupported", "needs_clarification")


def main():
    import evaluate_vendor100 as EV
    cands = {c["id"]: c for c in json.loads((HERE / "candidates_checked.json").read_text(encoding="utf-8"))["candidates"]}
    gold = {i["id"]: i for i in EV.load_gold(HERE / "rdev_gold.yaml")["items"]}
    sig = {m: {} for m in ("base", "o11")}
    for m in sig:
        for k in range(1, 5):
            for r in json.loads((P8 / f"cells/rdev_{m}_s{k}.json").read_text(encoding="utf-8"))["rows"]:
                analysis = sum(1 for x in (r.get("calls") or []) if x.get("tool") != "get_place_scope")
                refused = r.get("outcome") in REFUSED and analysis == 0
                ok = bool(EV.grounding_check(gold[r["id"]], r.get("grounding"))[0]) and r.get("outcome") not in REFUSED if gold[r["id"]]["gold"] else None
                s = sig[m].setdefault(r["id"], {"refused": 0, "ok": 0, "n": 0})
                s["n"] += 1
                s["refused"] += refused
                s["ok"] += bool(ok)
    rows, counts = [], Counter()
    for i, c in cands.items():
        b, o = sig["base"].get(i, {}), sig["o11"].get(i, {})
        if c["kind"] == "r1_refusal":
            sb, so = f"거부 {b.get('refused', 0)}/{b.get('n', 0)}", f"거부 {o.get('refused', 0)}/{o.get('n', 0)}"
            pr = "높음" if b.get("refused", 0) == 0 else "보통"
            why = "계약 개념·factor로 적을 수 없는 질문(" + c["rationale"] + "). 정답 = 거부. 질문·Jaccard 겹침(batch011 포함) 통과."
        else:
            sb, so = f"정답 {b.get('ok', 0)}/{b.get('n', 0)}, 거부 {b.get('refused', 0)}", f"정답 {o.get('ok', 0)}/{o.get('n', 0)}, 거부 {o.get('refused', 0)}"
            pr = "높음" if b.get("ok", 0) <= 1 else "보통"
            why = "지원되는 근접 대조(batch010 빈 구조). 검증 사슬·결정 120 겹침 검사 통과."
        counts[pr] += 1
        rows.append([i, pr, c["kind"], c["gap"], c["question"], c.get("gold_text") or c.get("target", ""), sb, so, c["decision_120"], "승인", why, *[""] * len(TAIL)])
    rows.sort(key=lambda r: (r[1] != "높음", r[0]))
    (HERE / "review").mkdir(exist_ok=True)
    guide = [["무엇인가", "refusal_dev 검토 시트 v1(Claude 초안, 승인 아님) — 거부를 따로 재는 개발 셋(학습·최종 판정에 쓰지 않음). 거부 30·근접 대조 30."],
             ["신호", "J-rdev = base·F-o11 각 k=4(동시 8, seed_base 20261100). 거부 문항은 올바른 거부 수, 대조 문항은 정답 수와 거부 수."],
             ["우선순위", "높음 = 거부 문항에서 base 0/4 또는 대조 문항에서 base 정답 ≤ 1/4. 판정이 아니다."],
             ["Claude 2차 검토 권고", "초안 작성자도 Claude다. 사람이 질문이 정말 지원되지 않는지(거부)·정답 호출이 맞는지(대조)를 직접 본다."],
             ["결정 칸", "승인 / 수정 / 보류 / 제외, 수정 질문, 수정 정답, 메모, 검토자, 검토일"]]
    B4.write_workbook(HERE / "review/refusal_dev_review_v1.xlsx", [
        ("안내", ["항목", "설명"], guide),
        ("refusal_dev", ["id", "우선순위", "종류", "묶음", "질문", "초안 정답", "J-rdev base(k=4)", "J-rdev F-o11(k=4)", "결정 120 분류", "Claude 2차 검토 권고", "Claude 근거", *TAIL], rows)])
    summary = {"candidates": len(cands), "priority": dict(counts)}
    (HERE / "review/summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
