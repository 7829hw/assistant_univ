# -*- coding: utf-8 -*-
"""protected_final_v1 작성 서식(xlsx) 만들기(H5). 빈 서식만 만든다(문항 없음).

    hfvenv/bin/python make_template.py   # -> protected_final_v1_template.xlsx
"""
import importlib.util

from common import COLUMNS, DIFFICULTY, DIFFICULTY_TARGET, FACTOR_MIN, HERE, MARKS, REFUSAL, ROOT, SHEET, SIZE, TYPE_BY_TOOL, TYPE_TARGET

_spec = importlib.util.spec_from_file_location("b004_review", ROOT / "sft_dpo_inventory/batch004/build_review.py")
B4 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(B4)


def main():
    guide = [["무엇인가", "pilot_006 최종 판정 보호 셋 protected_final_v1 작성 서식(결정 106·135, protected_final_v1_SPEC.md). 작성은 사람이 한다."],
             ["저장 위치", "작성 중·완성본 모두 저장소 밖 /home/hwkim/sftdpo_work/protected_final_v1/ (권한 700). 저장소에 넣지 않는다."],
             ["행", f"'{SHEET}' 시트에 한 행 = 한 문항, 번호 1–{SIZE}. 열: " + ", ".join(COLUMNS)],
             ["질문", "사용자가 물을 법한 한국어 질문. 보호 셋·학습 데이터 문장을 보거나 바꿔 쓰지 않는다. 장소는 mock gazetteer 이름만."],
             ["정답 호출", "업체 형식 Tool 호출, 한 줄에 하나(예: get_place_scope(name=..., region=...) 다음 줄 get_trip_count(...)). 거부 문항은 비운다."],
             ["거부 문항", " / ".join(REFUSAL) + " — 지원하지 않는 질문이면 '예'(정답 = 거부)."],
             ["난이도", " / ".join(DIFFICULTY) + " — 쉬움 = hard factor 0, 보통 = 1, 어려움 = 2 이상."],
             ["hard factor", "쉼표로: " + ", ".join(MARKS) + " (dt·od≠dt·주변·묶음·집계는 정답 호출에서 자동으로 센다)"],
             ["유형 목표", ", ".join(f"{k} {v}" for k, v in TYPE_TARGET.items())],
             ["factor 최소", ", ".join(f"{k} {v}" for k, v in FACTOR_MIN.items())],
             ["난이도 목표", ", ".join(f"{k} {v}" for k, v in DIFFICULTY_TARGET.items())],
             ["검사", "validate.py --xlsx <파일>: 형식·compile·mock·분포·겹침. 출력은 수치와 문제 행 번호뿐."]]
    codes = [[tool, name] for tool, name in TYPE_BY_TOOL.items()] + [["(정답 호출 없음, 거부 문항 예)", "거부"]]
    B4.write_workbook(HERE / "protected_final_v1_template.xlsx", [
        ("안내", ["항목", "설명"], guide),
        (SHEET, COLUMNS, [[str(i), "", "", "아니오", "", "", ""] for i in range(1, SIZE + 1)]),
        ("코드표", ["마지막 정답 tool", "유형"], codes)])
    print("ok")


if __name__ == "__main__":
    main()
