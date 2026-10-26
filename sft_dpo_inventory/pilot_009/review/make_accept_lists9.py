# -*- coding: utf-8 -*-
"""pilot_009 S0(결정 233·234): 받아들일 목록을 만든다(검사·기록 전에 커밋). 모델 호출 없음.

    python3 sft_dpo_inventory/pilot_009/review/make_accept_lists9.py   # -> review/b012_accept_list.json, review/rdev2_accept_list.json
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
INV = HERE.parents[1]
REVIEWER = "사용자(이름 기록 안 함), 2차 검토 권고 채택"
MODIFY = {
    "b012-001": ("지난달 대구 택시 기사들 각자의 평균 수입을 이름과 함께 보여줘",
                 "\"한 사람당 평균 수입\"은 택시 평균 수입(aggregation=avg)으로 읽힐 수 있다. 기사 단위가 드러나게 바꿨다."),
    "b012-021": ("지난달 서울 택시 기사 가운데 수입이 딱 중간인 기사가 누구인지 알려줘",
                 "수입 중간값(aggregation=med)으로 읽힐 수 있다. 개인을 특정하게 바꿨다."),
    "b012-039": ("지난달 초량동 택시 RPM을 날짜별로 하나씩 평균 내서 나열해줘",
                 "\"하루씩 평균\"은 평균 RPM으로 읽힐 수 있다. 일별 나열임을 분명히 했다."),
}


def main():
    cb = json.loads((INV / "batch012/candidates_checked.json").read_text(encoding="utf-8"))["candidates"]
    rows = []
    for c in cb:
        r = {"id": c["id"], "kind": c["kind"], "decision": "modify" if c["id"] in MODIFY else "approve"}
        if c["id"] in MODIFY:
            q, why = MODIFY[c["id"]]
            r.update(original_question=c["question"], corrected_question=q, reason=why, gold="{\"unsupported\": true} 그대로")
        rows.append(r)
    out = {"decision": "233 (Z1)", "reviewer": REVIEWER, "source": "sft_dpo_inventory/batch012/candidates_checked.json", "rows": rows,
           "counts": {"approve": sum(r["decision"] == "approve" for r in rows), "modify": sum(r["decision"] == "modify" for r in rows)}}
    (HERE / "b012_accept_list.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    cr = json.loads((INV / "pilot_009/refusal_dev2/candidates_checked.json").read_text(encoding="utf-8"))["candidates"]
    rows = [{"id": c["id"], "kind": c["kind"], "gap": c["gap"], "decision": "approve"} for c in cr]
    out = {"decision": "234 (Z2)", "reviewer": REVIEWER, "source": "sft_dpo_inventory/pilot_009/refusal_dev2/candidates_checked.json", "rows": rows,
           "counts": {"approve": len(rows)},
           "note": "refusal_dev v2 = 거부 90(v1 승인본 30 + 확장 60) + 대조 30(v1 승인본). 경계 확인: rdev-075·079(시간대 셋을 따로 — 한 호출로 적을 수 없음), rdev-088(차종 ≠ 택시 유형)."}
    (HERE / "rdev2_accept_list.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(len(cb), len(cr))


if __name__ == "__main__":
    main()
