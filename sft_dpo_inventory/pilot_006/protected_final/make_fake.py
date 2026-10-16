# -*- coding: utf-8 -*-
"""도구 시험용 가짜 문항 5개 xlsx(H5). mock 장소로 만든 무의미한 문항이며 protected_final_v1과 무관하다.

    hfvenv/bin/python make_fake.py OUT.xlsx
"""
import importlib.util
import sys

from common import COLUMNS, ROOT, SHEET

_spec = importlib.util.spec_from_file_location("b004_review", ROOT / "sft_dpo_inventory/batch004/build_review.py")
B4 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(B4)
FAKE = [
    ["1", "가짜시험 알파 동대구역 통행량 하나", "get_place_scope(name=동대구역)\nget_passage_count(scope=$resolve.scope)", "아니오", "쉬움", "", ""],
    ["2", "가짜시험 베타 수성구에서 태운 건수 셀별 내린곳", "get_place_scope(name=수성구, region=대구)\n"
     "get_trip_count(scope_pickup=$pickup.scope, date=last_week, dimension=h3, dimension_target=dropoff)", "아니오", "어려움", "동사형끝점", ""],
    ["3", "가짜시험 감마 거부 문항", "", "예", "보통", "", ""],
    ["4", "가짜시험 델타 scope:gz:3982 이름", "get_scope_name(scope=scope:gz:3982)", "아니오", "보통", "값없는장소", ""],
    ["5", "가짜시험 엡실론 잘못된 호출", "get_nothing(x=1)", "아니오", "중간", "엉뚱한표시", ""],
]
QUESTIONS = [r[1] for r in FAKE]

if __name__ == "__main__":
    B4.write_workbook(sys.argv[1], [(SHEET, COLUMNS, FAKE)])
    print("ok")
