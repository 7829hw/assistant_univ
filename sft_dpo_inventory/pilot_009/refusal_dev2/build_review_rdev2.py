# -*- coding: utf-8 -*-
"""refusal_dev 확장 검토 시트(개발 셋 초안, 승인 아님; ``pilot_008/refusal_dev/build_review_rdev.py`` 사본)와 J-rdev2 진단. 모델 호출 없음. **승인하지 않는다.**

    hfvenv/bin/python sft_dpo_inventory/pilot_009/refusal_dev2/build_review_rdev2.py   # -> review/refusal_dev2_review_v1.xlsx, review/summary.json

신호(J-rdev2, 거부 60 모두): base·F-o11(B2-F-o11)·P8 다섯(순서 seed 43·1016·7·11·2027) 각 k=4의 올바른 거부 수(결과 상태 unsupported·needs_clarification,
분석 tool 없음)와 경로(M = UNSUPPORTED_QUESTION, C = needs_clarification, P = 그 밖). 모델·seed별, 범주별 올바른 거부율을 summary에 적는다(진단, 판정 아님).
우선순위: 높음 = base 0/4 그리고 P8 다섯 합 0/20(어느 모델도 거부하지 않음 — 질문이 정말 미지원인지 사람이 먼저 볼 문항). 판정이 아니다.
"""
import importlib.util
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
P9 = HERE.parent
ROOT = P9.parents[1]
sys.path.insert(0, str(ROOT))
_spec = importlib.util.spec_from_file_location("b004_review", ROOT / "sft_dpo_inventory/batch004/build_review.py")
B4 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(B4)
TAIL = ["결정(승인/수정/보류/제외)", "수정 질문", "수정 정답", "메모", "검토자", "검토일"]
REFUSED = ("unsupported", "needs_clarification")
MODELS = {"base": "rdev2_base", "o11": "rdev2_o11", **{f"p8_{o}": f"rdev2_p8_{o}" for o in ("o43", "o1016", "o7", "o11", "o2027")}}


def main():
    cands = {c["id"]: c for c in json.loads((HERE / "candidates_checked.json").read_text(encoding="utf-8"))["candidates"]}
    sig = {m: defaultdict(lambda: {"refused": 0, "n": 0, "M": 0, "P": 0, "C": 0}) for m in MODELS}
    for m, label in MODELS.items():
        for k in range(1, 5):
            p = P9 / f"cells/{label}_s{k}.json"
            if not p.exists():
                continue
            for r in json.loads(p.read_text(encoding="utf-8"))["rows"]:
                analysis = sum(1 for x in (r.get("calls") or []) if x.get("tool") != "get_place_scope")
                refused = r.get("outcome") in REFUSED and analysis == 0
                s = sig[m][r["id"]]
                s["n"] += 1
                s["refused"] += refused
                if refused:
                    s["M" if r.get("error_code") == "UNSUPPORTED_QUESTION" else "C" if r.get("outcome") == "needs_clarification" else "P"] += 1
    rows, counts = [], Counter()
    p8 = [m for m in MODELS if m.startswith("p8_")]
    for i, c in cands.items():
        b, o = sig["base"][i], sig["o11"][i]
        p8r, p8n = sum(sig[m][i]["refused"] for m in p8), sum(sig[m][i]["n"] for m in p8)
        pr = "높음" if b["n"] and b["refused"] == 0 and p8n and p8r == 0 else "보통"
        counts[pr] += 1
        why = "계약 개념·factor로 적을 수 없는 질문(" + c["rationale"] + "). 정답 = 거부. 질문·Jaccard 겹침(batch011·batch012·RC6·refusal_dev v1) 통과."
        fmt = lambda s: f"{s['refused']}/{s['n']}(M{s['M']}·P{s['P']}·C{s['C']})" if s["n"] else ""  # noqa: E731
        rows.append([i, pr, c["gap"], c["question"], fmt(b), fmt(o), f"{p8r}/{p8n}" if p8n else "", " ".join(f"{sig[m][i]['refused']}" for m in p8),
                     c["decision_120"], "승인", why, *[""] * len(TAIL)])
    rows.sort(key=lambda r: (r[1] != "높음", r[0]))
    (HERE / "review").mkdir(exist_ok=True)
    guide = [["무엇인가", "refusal_dev 확장 검토 시트 v1(Claude 초안, 승인 아님) — 거부 60(지표·묶음 단위·개별 단위·예측·다른 교통수단·도메인 밖 각 10). 개발 셋(학습·최종 판정에 쓰지 않음). "
                         "승인 뒤 v1(거부 30·대조 30)과 합쳐 거부 90·대조 30."],
             ["신호", "J-rdev2 = base·F-o11·P8 다섯 각 k=4(동시 8, seed_base 20261100). 올바른 거부 수와 경로(M 모델 거부·P 프로그램 거부·C 확인 요청)."],
             ["우선순위", "높음 = base 0/4이고 P8 다섯 합 0/20. 판정이 아니다."],
             ["Claude 2차 검토 권고", "초안 작성자도 Claude다. 사람이 질문이 정말 지원되지 않는지 직접 본다(예: 시간대 하나는 지원되지만 시간 단위 묶음은 지원되지 않음)."],
             ["결정 칸", "승인 / 수정 / 보류 / 제외, 수정 질문, 수정 정답, 메모, 검토자, 검토일"]]
    B4.write_workbook(HERE / "review/refusal_dev2_review_v1.xlsx", [
        ("안내", ["항목", "설명"], guide),
        ("refusal_dev2", ["id", "우선순위", "범주", "질문", "J-rdev2 base(k=4)", "J-rdev2 F-o11(k=4)", "J-rdev2 P8 합(5 × k=4)", "P8 seed별(43·1016·7·11·2027)",
                          "결정 120 분류", "Claude 2차 검토 권고", "Claude 근거", *TAIL], rows)])
    by_model = {m: round(100 * sum(s["refused"] for s in sig[m].values()) / max(1, sum(s["n"] for s in sig[m].values())), 2) for m in MODELS}
    gaps = sorted({c["gap"] for c in cands.values()})
    by_gap = {m: {g: round(100 * sum(sig[m][i]["refused"] for i in cands if cands[i]["gap"] == g) /
                         max(1, sum(sig[m][i]["n"] for i in cands if cands[i]["gap"] == g)), 1) for g in gaps} for m in MODELS}
    p8_gap = {g: round(sum(by_gap[m][g] for m in p8) / len(p8), 1) for g in gaps}
    routes = {m: {r: sum(s[r] for s in sig[m].values()) for r in ("M", "P", "C")} for m in MODELS}
    summary = {"candidates": len(cands), "priority": dict(counts), "samples": {m: sum(s["n"] for s in sig[m].values()) for m in MODELS},
               "correct_refusal_pct_by_model": by_model, "p8_mean_pct": round(sum(by_model[m] for m in p8) / len(p8), 2),
               "correct_refusal_pct_by_gap": by_gap, "p8_mean_pct_by_gap": p8_gap, "routes": routes}
    (HERE / "review/summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
