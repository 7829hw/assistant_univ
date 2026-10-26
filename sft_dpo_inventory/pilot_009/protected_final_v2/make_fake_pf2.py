# -*- coding: utf-8 -*-
"""도구 시험용 합성 서식(결정 239 Z7). mock 장소로 만든 무의미한 가짜 문항이며 protected_final_v2와 무관하다(행마다 기대 문제 코드가 정해져 있음).

    hfvenv/bin/python make_fake_pf2.py OUT.xlsx
"""
import importlib.util
import sys

from common_pf2 import COLUMNS, ROOT, SHEET

_spec = importlib.util.spec_from_file_location("b004_review", ROOT / "sft_dpo_inventory/batch004/build_review.py")
B4 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(B4)
S = "get_place_scope(name=대구)\n"
#: (행, 기대 문제 코드 집합)
FAKE = [
    (["1", "가짜시험 알파 동대구역 통행량 하나", "get_place_scope(name=동대구역)\nget_passage_count(scope=$resolve.scope)", "아니오", "-", "-", "-", "쉬움", "", ""], set()),
    (["2", "가짜시험 베타 대구 지난달 요금 평균", S + "get_trip_metrics(metric=fare, scope=$resolve.scope, date=last_month, aggregation=avg)", "아니오", "-", "-", "예측", "보통", "", ""],
     set()),
    (["3", "가짜시험 감마 모델 거부", "", "예", "M", "예측", "-", "보통", "", ""], set()),
    (["4", "가짜시험 델타 모델 거부 호출 있음", S + "get_passage_count(scope=$resolve.scope)", "예", "M", "도메인 밖", "-", "보통", "", ""], {"m_has_calls"}),
    (["5", "가짜시험 엡실론 대구 지난달 개인택시 요금 평균",
      S + "get_trip_metrics(metric=fare, scope=$resolve.scope, date=last_month, taxi_type=private, aggregation=avg)", "예", "P", "P-1", "-", "어려움", "", ""], set()),
    (["6", "가짜시험 제타 대구 지난달 요금 평균 P 표시",
      S + "get_trip_metrics(metric=fare, scope=$resolve.scope, date=last_month, aggregation=avg)", "예", "P", "P-1", "-", "보통", "", ""], {"p_not_unsupported:answered:None"}),
    (["7", "가짜시험 에타 대구 작년 월별 매출 최대",
      S + "get_billing_metrics(metric=revenue, scope=$resolve.scope, date=last_year, bucket=month, rollup=max)", "예", "C", "C-1", "-", "보통", "", ""], set()),
    (["8", "가짜시험 세타 거기 지난달 실차 건수", "get_trip_count(date=last_month)", "예", "C", "C-3", "-", "쉬움", "", ""], {"c_not_clarification:answered:None"}),
    (["9", "가짜시험 이오타 scope:gz:3982 이름", "get_scope_name(scope=scope:gz:3982)", "아니오", "-", "-", "-", "보통", "값없는장소", ""], {"scope_name_not_allowed"}),
    (["10", "가짜시험 카파 잘못된 코드", "", "예", "X", "-", "-", "중간", "엉뚱한표시", ""], {"form_code", "difficulty_code", "hard_factor_code"}),
    (["10", "가짜시험 람다 번호 겹침", "get_place_scope(name=동대구역)\nget_passage_count(scope=$resolve.scope, date=last_week)", "아니오", "-", "-", "-", "쉬움", "", ""],
     {"duplicate_number"}),
    (["12", "가짜시험 뮤 답하는 문항에 거부 형", "get_place_scope(name=동대구역)\nget_passage_count(scope=$resolve.scope, date=last_month)", "아니오", "P", "P-1", "개별", "쉬움", "", ""],
     {"form_on_answered", "category_on_answered", "contrast_code"}),
    (["13", "가짜시험 누 알 수 없는 tool", "get_nothing(x=1)", "아니오", "-", "-", "-", "쉬움", "", ""], {"unknown_tool"}),
]
QUESTIONS = [r[0][1] for r in FAKE]

if __name__ == "__main__":
    B4.write_workbook(sys.argv[1], [(SHEET, COLUMNS, [r for r, _ in FAKE])])
    print("ok")
