# -*- coding: utf-8 -*-
"""protected_final_v2 작성 서식(xlsx) 만들기(결정 239 Z7). 빈 서식만 만든다(문항 없음). ``pilot_006/protected_final/make_template.py``(v1)와 같은 방식.

    hfvenv/bin/python make_template_pf2.py   # -> protected_final_v2_template.xlsx
"""
import importlib.util

from common_pf2 import (BASE_DATE, COLUMNS, CONTRAST_TARGET, DIFFICULTY, DIFFICULTY_TARGET, DIFFICULTY_TOL, FACTOR_MIN, FORM_DISTINCT_MIN, FORM_TARGET, FORMS, HERE,
                        M_CATEGORIES, M_CATEGORY_MIN, MARKS, NONE, REFUSAL, REFUSAL_TARGET, ROOT, SCOPE_NAME_ALLOWED, SHEET, SIZE, TYPE_BY_TOOL, TYPE_TARGET)

_spec = importlib.util.spec_from_file_location("b004_review", ROOT / "sft_dpo_inventory/batch004/build_review.py")
B4 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(B4)


def main():
    guide = [["무엇인가", "최종 판정 보호 셋 protected_final_v2 작성 서식(결정 238·239, pilot_009/protected_final_v2_SPEC.md 2판). 작성은 사람이 한다."],
             ["저장 위치", "작성 중·완성본 모두 저장소 밖 /home/hwkim/sftdpo_work/protected_final_v2/ (권한 700). 저장소에 넣지 않는다."],
             ["기준일", f"{BASE_DATE}(월). 상대 기간(지난주·지난달·작년 등)은 이 날 기준."],
             ["행", f"'{SHEET}' 시트에 한 행 = 한 문항, 번호 1–{SIZE}. 열: " + ", ".join(COLUMNS)],
             ["질문", "사용자가 물을 법한 한국어 질문. 보호 셋·학습 데이터·개발 셋 문장을 보거나 바꿔 쓰지 않는다. 장소는 mock gazetteer 이름만."],
             ["정답 호출", "업체 형식 Tool 호출, 한 줄에 하나. 답하는 문항: 일반 호출. 거부 형 M: 비움. P·C: 질문을 그대로 옮긴 호출(계산할 수 있는지와 관계없이)."],
             ["거부 문항", " / ".join(REFUSAL) + " — 정답이 거부(지원하지 않음·확인 요청)면 '예'."],
             ["거부 형", " / ".join(FORMS) + f" / {NONE} — M 모델 거부(계약 개념·factor로 적을 수 없음), P 프로그램 거부(적을 수 있지만 계산할 수 없는 조합, mock 결과 unsupported), "
                       f"C 확인 요청(질문만으로 조건을 정할 수 없음, mock 결과 needs_clarification). 답하는 문항은 {NONE}."],
             ["거부 범주", "M: " + " / ".join(M_CATEGORIES) + ". P·C: 패턴 목록(protected_final_v2_pc_patterns.md)의 패턴 번호. 답하는 문항은 " + NONE + "."],
             ["근접 대조", f"답하는 문항 가운데 거부 범주와 짝이 되는 지원 질문이면 그 범주 이름(" + " / ".join(M_CATEGORIES) + f"), 아니면 {NONE}. 목표 {CONTRAST_TARGET}."],
             ["난이도", " / ".join(DIFFICULTY) + " — 쉬움 = hard factor 0, 보통 = 1, 어려움 = 2 이상."],
             ["hard factor", "쉼표로: " + ", ".join(MARKS) + " (dt·od≠dt·주변·묶음·차원·집계는 정답 호출에서 자동으로 센다)"],
             ["유형 목표(답하는 100)", ", ".join(f"{k} {v}" for k, v in TYPE_TARGET.items())],
             ["거부 목표", f"거부 {REFUSAL_TARGET} = " + ", ".join(f"{k} {v}" for k, v in FORM_TARGET.items())
                        + "; M 범주 최소 " + ", ".join(f"{k} {v}" for k, v in M_CATEGORY_MIN.items())
                        + "; 서로 다른 범주 " + ", ".join(f"{k} {v}개 이상" for k, v in FORM_DISTINCT_MIN.items())],
             ["factor 최소", ", ".join(f"{k} {v}" for k, v in FACTOR_MIN.items())],
             ["난이도 목표", ", ".join(f"{k} {v}" for k, v in DIFFICULTY_TARGET.items()) + f"(각 ±{DIFFICULTY_TOL})"],
             ["장소 이름 문항", "학습 데이터에 없는 scope만. 결정 238 예외로 다시 쓸 수 있는 scope: " + ", ".join(SCOPE_NAME_ALLOWED)],
             ["검사", "validate_pf2.py --xlsx <파일>: 형식·compile·mock·거부 형 결과·분포·겹침. 출력은 수치와 문제 행 번호·코드뿐."]]
    codes = ([["마지막 정답 tool → 유형", tool, name] for tool, name in TYPE_BY_TOOL.items()]
             + [["거부 형", f, d] for f, d in (("M", "모델 거부: 정답 호출 비움"), ("P", "프로그램 거부: mock 결과 unsupported"), ("C", "확인 요청: mock 결과 needs_clarification"),
                                                (NONE, "답하는 문항"))]
             + [["거부 범주(M)·근접 대조", c, f"M 최소 {M_CATEGORY_MIN[c]}"] for c in M_CATEGORIES]
             + [["난이도", d, ""] for d in DIFFICULTY] + [["hard factor", m, ""] for m in MARKS])
    B4.write_workbook(HERE / "protected_final_v2_template.xlsx", [
        ("안내", ["항목", "설명"], guide),
        (SHEET, COLUMNS, [[str(i), "", "", "", "", "", "", "", "", ""] for i in range(1, SIZE + 1)]),
        ("코드표", ["구분", "코드", "뜻"], codes)])
    print("ok")


if __name__ == "__main__":
    main()
