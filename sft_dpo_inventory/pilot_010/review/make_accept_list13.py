# -*- coding: utf-8 -*-
"""pilot_010 선택 단계 P0(결정 247): batch013 받아들일 목록을 만든다(검사·기록 전에 커밋). 모델 호출 없음. ``pilot_009/review/make_accept_lists9.py``와 같은 방식.

    python3 sft_dpo_inventory/pilot_010/review/make_accept_list13.py   # -> review/b013_accept_list.json
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
INV = HERE.parents[1]
REVIEWER = "사용자(이름 기록 안 함), 2차 검토 권고 채택"


def main():
    cb = json.loads((INV / "batch013/candidates_checked.json").read_text(encoding="utf-8"))["candidates"]
    rows = [{"id": c["id"], "kind": c["kind"], "group": c["group"], "subtype": c["subtype"], "gap": c["gap"], "decision": "approve"} for c in cb]
    out = {"decision": "247 (AB1)", "reviewer": REVIEWER, "source": "sft_dpo_inventory/batch013/candidates_checked.json", "rows": rows,
           "counts": {"approve": len(rows)},
           "note": "77건 모두 초안 그대로 승인. 2차 검토 확인: 일 단위 집계(b013-035·036·037·038·039·041·042)는 aggregation으로 답할 수 있음(b011-015·b012-001·039의 짝), "
                   "bucket 기간이 묶음에 맞고 집계·rollup 있음, 차원 문항은 장소 없이 시도·요일, H3·읍면동 묶음은 묶음 가능한 장소에서 mock 통과, 실적·기록(b013-044–050)은 지난 기간."}
    (HERE / "b013_accept_list.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(len(rows))


if __name__ == "__main__":
    main()
