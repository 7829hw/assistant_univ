# -*- coding: utf-8 -*-
"""protected_final_v2 도구 공통(결정 238·239 Z6·Z7). 서식 열 이름·코드표·명세 2판 분포 목표(변경 1 반영). 문항 내용은 여기 없다.
``pilot_006/protected_final/common.py``(v1, 그대로 둠)와 같은 역할."""
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SHEET = "작성"
COLUMNS = ["번호", "질문", "정답 호출", "거부 문항", "거부 형", "거부 범주", "근접 대조", "난이도", "hard factor", "메모"]
SIZE = 150
REFUSAL = ("예", "아니오")
FORMS = ("M", "P", "C")
NONE = "-"
DIFFICULTY = ("쉬움", "보통", "어려움")
#: 작성자가 표시하는 hard factor. dt·od≠dt·vicinity·묶음·차원·집계는 정답 호출에서 자동으로 센다.
MARKS = ("동사형끝점", "운행상태표현", "값없는장소")
#: 거부 범주(M) = 근접 대조 범주. 명세 2판 3.2·3.3.
M_CATEGORIES = ("없는 지표", "없는 묶음 단위", "개별 단위", "예측", "다른 교통수단", "도메인 밖")
TYPE_BY_TOOL = {"get_passage_count": "통과량 건수", "get_passage_metrics": "통과량 지표", "get_drive_metrics": "운행 지표", "get_trip_count": "통행 건수",
                "get_trip_metrics": "통행 지표", "get_billing_metrics": "요금 지표", "get_scope_name": "장소 이름(역방향)"}
#: 명세 2판 3.1 + 결정 238 변경 1(장소 이름 6 → 5, 통과량 건수 18 → 19). 답하는 100.
TYPE_TARGET = {"통과량 건수": 19, "통과량 지표": 15, "운행 지표": 11, "통행 건수": 22, "통행 지표": 14, "요금 지표": 14, "장소 이름(역방향)": 5}
TYPE_TOL = 2  # v1 validate.py와 같은 허용 폭(유형별)
REFUSAL_TARGET = 50
FORM_TARGET = {"M": 34, "P": 10, "C": 6}
M_CATEGORY_MIN = {"없는 지표": 6, "없는 묶음 단위": 6, "개별 단위": 6, "예측": 5, "다른 교통수단": 5, "도메인 밖": 6}
FORM_DISTINCT_MIN = {"P": 4, "C": 3}
CONTRAST_TARGET = 25
FACTOR_MIN = {"dt": 22, "od_ne_dt": 9, "동사형끝점": 11, "운행상태표현": 11, "vicinity": 9, "bucket_or_dimension": 13, "aggregation": 45}
DIFFICULTY_TARGET = {"쉬움": 45, "보통": 60, "어려움": 45}
DIFFICULTY_TOL = 8
#: 결정 238 변경 1: 장소 이름 문항에 다시 쓸 수 있는 scope(v1이 쓴 5개, 학습 데이터 장소 이름 문항에 없음).
SCOPE_NAME_ALLOWED = ("scope:district:2729000000", "scope:district:2723010200", "scope:district:2623010700", "scope:district:2723000000", "scope:district:2617000000")
BASE_DATE = "2026-10-26"
