# -*- coding: utf-8 -*-
"""protected_final_v1 도구 공통(결정 135 G5, H5). 서식 열 이름·코드표·SPEC 분포 목표. 문항 내용은 여기 없다."""
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SHEET = "작성"
COLUMNS = ["번호", "질문", "정답 호출", "거부 문항", "난이도", "hard factor", "메모"]
DIFFICULTY = ("쉬움", "보통", "어려움")
REFUSAL = ("예", "아니오")
#: 작성자가 표시하는 hard factor(자동 계산이 어려운 두 가지 + 확인용). 나머지는 정답 호출에서 자동으로 센다.
MARKS = ("동사형끝점", "운행상태표현", "값없는장소")
TYPE_BY_TOOL = {"get_passage_count": "통과량 건수", "get_passage_metrics": "통과량 지표", "get_drive_metrics": "운행 지표", "get_trip_count": "통행 건수",
                "get_trip_metrics": "통행 지표", "get_billing_metrics": "요금 지표", "get_scope_name": "장소 이름(역방향)"}
#: protected_final_v1_SPEC.md 3절(120문항)
TYPE_TARGET = {"통과량 건수": 20, "통과량 지표": 16, "운행 지표": 12, "통행 건수": 24, "통행 지표": 16, "요금 지표": 16, "장소 이름(역방향)": 6, "거부": 10}
FACTOR_MIN = {"dt": 24, "dt_pickup": 10, "dt_dropoff": 10, "od_ne_dt": 10, "동사형끝점": 12, "운행상태표현": 12, "vicinity": 10, "bucket_or_dimension": 15,
              "aggregation": 50, "값없는장소": 6}
DIFFICULTY_TARGET = {"쉬움": 36, "보통": 48, "어려움": 36}
SIZE = 120
