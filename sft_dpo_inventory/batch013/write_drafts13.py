# -*- coding: utf-8 -*-
"""batch013 초안(pilot_010 준비 P2, 결정 243 AA3): 요금 지표 중심 근접 대조(학습용). **승인이 아니다.** Claude가 손으로 적음.

    python3 write_drafts13.py   # -> candidates_draft.yaml

- 보호 셋·개발 셋·protected_final 문장을 보지 않고 새로 썼다(batch011·012·refusal_dev와 겹치지 않게 표현을 바꿈). 장소는 mock gazetteer 이름만. 기준일 2026-10-26(월).
- 모두 답하는 문항(``kind: r2_contrast``). ``gap`` = 겉모습이 비슷한 거부 범주(batch011·012 r2 이름과 같음, TEACH-C 지시의 "가까운 거부 범주").
- c1 요금 지표(``get_billing_metrics``) 50: 묶음(bucket + rollup) 14, 장소 없는 요일별·시도별 차원 10, 택시 유형 10, 일 단위 값의 집계 8, 지난 기간 기록·실적 8.
  구조는 batch010 빈 구조(``batch010/free_structures10.json``, 보호 넷·확장·thor family 밖)에서만 골랐다.
- c2 다른 tool 30: RPM 최솟값 4, 통과량 건수 H3 셀별 8, 실차 건수 차원 18. 구조는 ``free_structures13.json``(같은 방법)에서 family가 막히지 않은 것만.
  통과량 속도·운행 지표(공차율)·통행 지표(요금)는 거부 패턴이 아닌 구조가 모두 보호 넷·확장 family에 걸려 넣지 않았다(README 2절).
- 거부 패턴(``protected_final_v2_pc_patterns.md``)에 해당하는 조합은 쓰지 않았다: 속도·RPM·공차율의 합계, 순위에 개수 없음, 요금 지표의 장소와 차원을 함께,
  bucket에 집계나 rollup이 빠짐, 통행 건수·요금 지표에 택시 운행 상태, 통행 건수에 택시 유형.
- 2차: 1차 검사(``excluded_round1.json``)에서 빠진 22(Jaccard 7, 같은 정답 grounding 5, mock 조합 10 — 통과량 건수 H3 셀별은 대구 장소만, 실차 건수 짝(both)은 읍면동만 답함)를
  바꿨다. 줄 끝 주석에 1차 문장.
- 기간은 묶음에 맞췄다(월별 ≥ 2개월: 작년·올해·2026년 3–8월·5–7월; 주별 ≥ 2주: 지난달·이번 달·2026년 9월). 이번 주는 쓰지 않았다(기준일이 월요일).
"""
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent


def bm(place, region, args):
    """요금 지표 호출(장소가 있으면 get_place_scope 먼저)."""
    if place:
        pc = f"get_place_scope(name={place}" + (f", region={region}" if region else "") + ")\n"
        return pc + f"get_billing_metrics({args.replace('SCOPE', 'scope=$resolve.scope')})"
    return f"get_billing_metrics({args})"


def pc(place, region):
    return f"get_place_scope(name={place}" + (f", region={region}" if region else "") + ")"


#: (묶음, 유형, gap, 질문, 정답 호출, 짝 설명)
C1 = [
    # 묶음(bucket + rollup) 14 — 분기·반기·하루·시간 단위 묶음 거부와 짝
    ("c1", "bucket", "r2_bucket", "작년 부산 택시 수입을 월별 최댓값으로 구한 뒤 그 평균은?",
     bm("부산", None, "metric=revenue, SCOPE, date=last_year, aggregation=max, bucket=month, rollup=avg"), "월별(분기별 묶음 거부와 대조)"),
    ("c1", "bucket", "r2_bucket", "올해 서울 택시 수입을 월별 최솟값으로 낸 다음 그중 가장 큰 값은?",
     bm("서울", None, "metric=revenue, SCOPE, date=this_year, aggregation=min, bucket=month, rollup=max"), "월별(반기별 묶음 거부와 대조)"),
    ("c1", "bucket", "r2_bucket", "지난달 인천 택시 수입을 주별 중간값으로 구한 뒤 그 최댓값은?",
     bm("인천", None, "metric=revenue, SCOPE, date=last_month, aggregation=med, bucket=week, rollup=max"), "주별(하루 단위 묶음 거부와 대조)"),
    ("c1", "bucket", "r2_bucket", "이번 달 대구 수성구 택시 수입을 주별 합계로 낸 뒤 가장 작은 주의 값은?",
     bm("수성구", "대구", "metric=revenue, SCOPE, date=this_month, aggregation=sum, bucket=week, rollup=min"), "주별(날짜마다 합계 거부와 대조)"),
    ("c1", "bucket", "r2_bucket", "2026년 3월부터 8월까지 부산 활성 택시 대수를 월별 평균으로 낸 뒤 다시 평균하면?",
     bm("부산", None, "metric=active_taxi_count, SCOPE, date=20260301-20260831, aggregation=avg, bucket=month, rollup=avg"), "월별(3개월 단위 묶음 거부와 대조)"),
    ("c1", "bucket", "r2_bucket", "지난달 대구 활성 택시 대수를 주별 최댓값으로 구하고 그중 최솟값은?",
     bm("대구", None, "metric=active_taxi_count, SCOPE, date=last_month, aggregation=max, bucket=week, rollup=min"), "주별(매일 최댓값 거부와 대조)"),
    ("c1", "bucket", "r2_bucket", "작년 대구 동구 택시 가동률을 달마다 중간값으로 정리한 다음 그중 제일 높은 값은?",
     bm("동구", "대구", "metric=active_taxi_ratio, SCOPE, date=last_year, aggregation=med, bucket=month, rollup=max"), "월별(분기마다 가동률 거부와 대조)"),  # 2차(1차: 작년 인천 택시 가동률을 월별 중간값으로 낸 뒤 그 최댓값은?)
    ("c1", "bucket", "r2_bucket", "이번 달 대구 달서구 택시 가동률을 주별 평균으로 구한 다음 그중 가장 높은 값은?",
     bm("달서구", "대구", "metric=active_taxi_ratio, SCOPE, date=this_month, aggregation=avg, bucket=week, rollup=max"), "주별(시간마다 가동률 거부와 대조)"),
    ("c1", "bucket", "r2_bucket", "올해 서울 택시들의 운행일수를 한 달씩 모두 더한 값 가운데 가장 큰 달의 값은?",
     bm("서울", None, "metric=operating_days, SCOPE, date=this_year, aggregation=sum, bucket=month, rollup=max"), "월별(연 단위 묶음 거부와 대조)"),  # 2차(1차: 올해 부산 수영구 택시 운행일수를 월별 합계로 낸 뒤 그 최댓값은?)
    ("c1", "bucket", "r2_bucket", "지난달 서울 택시 운행일수를 주별 최솟값으로 구한 뒤 평균을 내줘",
     bm("서울", None, "metric=operating_days, SCOPE, date=last_month, aggregation=min, bucket=week, rollup=avg"), "주별(2주 단위 묶음 거부와 대조)"),
    ("c1", "bucket", "r2_bucket", "올해 대구 서구 택시 가동률을 월별 최솟값으로 구한 뒤 그 평균은?",
     bm("서구", "대구", "metric=active_taxi_ratio, SCOPE, date=this_year, aggregation=min, bucket=month, rollup=avg"), "월별(반년 단위 거부와 대조)"),
    ("c1", "bucket", "r2_bucket", "2026년 5월부터 7월까지 대구 중구 택시 수입을 월별 최댓값으로 구한 뒤 중간값은?",
     bm("중구", "대구", "metric=revenue, SCOPE, date=20260501-20260731, aggregation=max, bucket=month, rollup=med"), "월별(분기 한 번 묶음 거부와 대조)"),
    ("c1", "bucket", "r2_bucket", "작년 서울 활성 택시 대수를 월별 최솟값으로 구한 뒤 그중 가장 큰 값은?",
     bm("서울", None, "metric=active_taxi_count, SCOPE, date=last_year, aggregation=min, bucket=month, rollup=max"), "월별(해마다 비교 거부와 대조)"),
    ("c1", "bucket", "r2_bucket", "2026년 9월 한 달 동안 인천 택시 운행일수를 주별 평균으로 낸 뒤 합계는?",
     bm("인천", None, "metric=operating_days, SCOPE, date=20260901-20260930, aggregation=avg, bucket=week, rollup=sum"), "주별(열흘 단위 묶음 거부와 대조)"),
    # 장소 없는 요일별·시도별 차원 10 — 시간 단위 나눔·개별 단위 거부와 짝
    ("c1", "dimension", "r2_bucket", "2026년 1월부터 6월까지 요일별 택시 평균 수입을 보여줘",
     bm(None, None, "metric=revenue, date=20260101-20260630, aggregation=avg, dimension=dayofweek"), "요일별(시간대별로 자르기 거부와 대조)"),  # 2차(1차: 작년 요일별 택시 평균 수입을 보여줘)
    ("c1", "dimension", "r2_bucket", "올해 요일별 택시 수입 최댓값이 가장 큰 두 요일은?",
     bm(None, None, "metric=revenue, date=this_year, aggregation=max, dimension=dayofweek, order=top, limit=2"), "요일별 순위(날짜별 순위 거부와 대조)"),
    ("c1", "dimension", "r2_entity", "지난달 시도별 택시 수입 중간값을 알려줘",
     bm(None, None, "metric=revenue, date=last_month, aggregation=med, dimension=sido"), "시도별(기사별 중간값 거부와 대조)"),
    ("c1", "dimension", "r2_entity", "올해 들어 택시 수입의 최솟값을 시도마다 냈을 때 가장 낮은 두 시도는?",
     bm(None, None, "metric=revenue, date=this_year, aggregation=min, dimension=sido, order=bottom, limit=2"), "시도 순위(수입 적은 회사 거부와 대조)"),  # 2차(1차: 작년 시도별 택시 수입 최솟값이 가장 작은 두 곳은?)
    ("c1", "dimension", "r2_bucket", "이번 달 택시 활성 대수 기준으로 하위 두 요일은?",
     bm(None, None, "metric=active_taxi_count, date=this_month, dimension=dayofweek, order=bottom, limit=2"), "요일 순위(시간대 순위 거부와 대조)"),
    ("c1", "dimension", "r2_entity", "이번 달 택시 운행일수를 시도별로 모두 합하면 어느 두 시도가 가장 적어?",
     bm(None, None, "metric=operating_days, date=this_month, aggregation=sum, dimension=sido, order=bottom, limit=2"), "시도 순위(운행일수 적은 차량 거부와 대조)"),  # 2차(1차: 지난달 시도별 택시 운행일수 합계가 가장 작은 두 곳은?)
    ("c1", "dimension", "r2_bucket", "2026년 7월부터 9월까지 택시 가동률을 요일마다 최댓값으로 보면 가장 높은 두 요일은?",
     bm(None, None, "metric=active_taxi_ratio, date=20260701-20260930, aggregation=max, dimension=dayofweek, order=top, limit=2"), "요일 순위(월초·월말 나눔 거부와 대조)"),  # 2차(1차: 작년 요일별 택시 가동률 최댓값이 높은 두 요일은?)
    ("c1", "dimension", "r2_bucket", "올해 요일별 택시 운행일수 중간값은?",
     bm(None, None, "metric=operating_days, date=this_year, aggregation=med, dimension=dayofweek"), "요일별(주차별 나눔 거부와 대조)"),
    ("c1", "dimension", "r2_entity", "이번 달 시도별 택시 가동률 중간값이 높은 두 곳은?",
     bm(None, None, "metric=active_taxi_ratio, date=this_month, aggregation=med, dimension=sido, order=top, limit=2"), "시도 순위(가동률 높은 회사 거부와 대조)"),
    ("c1", "dimension", "r2_entity", "작년 시도별 택시 평균 수입을 비교해줘",
     bm(None, None, "metric=revenue, date=last_year, aggregation=avg, dimension=sido"), "시도별 평균(기사 한 사람당 평균 수입 거부와 대조)"),
    # 택시 유형 10 — 기사·회사·차량별 거부와 짝
    ("c1", "taxi_type", "r2_entity", "작년 부산 법인택시 수입을 월별 최솟값으로 구한 뒤 모두 더하면?",
     bm("부산", None, "metric=revenue, SCOPE, date=last_year, taxi_type=corporate, aggregation=min, bucket=month, rollup=sum"), "법인택시(법인 회사별 수입 거부와 대조)"),
    ("c1", "taxi_type", "r2_entity", "지난달 시도별 개인택시 수입 최댓값이 큰 두 곳은?",
     bm(None, None, "metric=revenue, date=last_month, taxi_type=private, aggregation=max, dimension=sido, order=top, limit=2"), "개인택시·시도 순위(수입 많은 기사 거부와 대조)"),
    ("c1", "taxi_type", "r2_entity", "올해 요일별 개인택시 운행일수 최댓값을 보여줘",
     bm(None, None, "metric=operating_days, date=this_year, taxi_type=private, aggregation=max, dimension=dayofweek"), "개인택시·요일별(기사별 운행일수 거부와 대조)"),
    ("c1", "taxi_type", "r2_entity", "지난달 인천 법인택시 활성 대수를 주별 중간값으로 낸 뒤 평균은?",
     bm("인천", None, "metric=active_taxi_count, SCOPE, date=last_month, taxi_type=corporate, aggregation=med, bucket=week, rollup=avg"), "법인택시(운수회사별 대수 거부와 대조)"),
    ("c1", "taxi_type", "r2_entity", "이번 달 서울에서 법인택시 가동률이 가장 낮았던 값은 얼마야?",
     bm("서울", None, "metric=active_taxi_ratio, SCOPE, date=this_month, taxi_type=corporate, aggregation=min"), "법인택시(가동률 낮은 회사 거부와 대조)"),
    ("c1", "taxi_type", "r2_entity", "작년 한 해 대구 개인택시의 활성 대수 최댓값을 알려줘",
     bm("대구", None, "metric=active_taxi_count, SCOPE, date=last_year, taxi_type=private, aggregation=max"), "개인택시(차량 번호별 거부와 대조)"),
    ("c1", "taxi_type", "r2_entity", "이번 달 요일별 법인택시 수입 중간값이 낮은 두 요일은?",
     bm(None, None, "metric=revenue, date=this_month, taxi_type=corporate, aggregation=med, dimension=dayofweek, order=bottom, limit=2"), "법인택시·요일 순위(사업자별 수입 거부와 대조)"),
    ("c1", "taxi_type", "r2_entity", "올해 대구 수성구 개인택시 운행일수를 월별 평균으로 구한 뒤 그 최댓값은?",
     bm("수성구", "대구", "metric=operating_days, SCOPE, date=this_year, taxi_type=private, aggregation=avg, bucket=month, rollup=max"), "개인택시(개인 사업자마다 거부와 대조)"),
    ("c1", "taxi_type", "r2_entity", "올해 부산 법인택시 활성 대수의 중간값은?",
     bm("부산", None, "metric=active_taxi_count, SCOPE, date=this_year, taxi_type=corporate, aggregation=med"), "법인택시(회사 한 곳의 대수 거부와 대조)"),
    ("c1", "taxi_type", "r2_entity", "작년 시도별 개인택시 수입 최솟값이 큰 두 곳은?",
     bm(None, None, "metric=revenue, date=last_year, taxi_type=private, aggregation=min, dimension=sido, order=top, limit=2"), "개인택시·시도 순위(기사 순위 거부와 대조)"),
    # 일 단위 값의 집계 8 — b011-015·b012-001·039(개별 단위·날짜별 나열 거부)의 답할 수 있는 짝
    ("c1", "daily_agg", "r2_entity", "이번 달 인천 활성 택시 대수의 하루 최댓값은 몇 대야?",
     bm("인천", None, "metric=active_taxi_count, SCOPE, date=this_month, aggregation=max"), "기간 안 최댓값(기사 각자의 값 거부와 대조)"),
    ("c1", "daily_agg", "r2_bucket", "지난달 대구 택시 가동률의 하루 중간값은?",
     bm("대구", None, "metric=active_taxi_ratio, SCOPE, date=last_month, aggregation=med"), "기간 안 중간값(날짜별로 하나씩 나열 거부와 대조)"),
    ("c1", "daily_agg", "r2_bucket", "올해 서울 택시 가동률이 하루 기준으로 가장 낮았던 값은?",
     bm("서울", None, "metric=active_taxi_ratio, SCOPE, date=this_year, aggregation=min"), "기간 안 최솟값(하루 단위 묶음 거부와 대조)"),
    ("c1", "daily_agg", "r2_entity", "작년 부산 하루하루 활성 택시 대수의 중간값을 알려줘",
     bm("부산", None, "metric=active_taxi_count, SCOPE, date=last_year, aggregation=med"), "기간 안 중간값(수입이 중간인 기사 거부와 대조)"),
    ("c1", "daily_agg", "r2_entity", "올해 시도별로 활성 택시 대수의 하루 평균을 알려줘",
     bm(None, None, "metric=active_taxi_count, date=this_year, aggregation=avg, dimension=sido"), "시도별 평균(기사들 각자의 평균 거부와 대조)"),  # 2차(1차: 지난달 시도별 활성 택시 대수 하루 평균을 보여줘)
    ("c1", "daily_agg", "r2_bucket", "작년 요일마다 택시 가동률의 하루 평균은 얼마였어?",
     bm(None, None, "metric=active_taxi_ratio, date=last_year, aggregation=avg, dimension=dayofweek"), "요일별 평균(날짜별 평균 나열 거부와 대조)"),  # 2차(1차: 이번 달 요일별 택시 가동률 하루 평균은?)
    ("c1", "daily_agg", "r2_entity", "작년 시도별 하루 활성 택시 대수 최댓값을 알려줘",
     bm(None, None, "metric=active_taxi_count, date=last_year, aggregation=max, dimension=sido"), "시도별 최댓값(차량마다 값 거부와 대조)"),
    ("c1", "daily_agg", "r2_bucket", "올해 요일별 활성 택시 대수의 하루 최솟값이 작은 두 요일은?",
     bm(None, None, "metric=active_taxi_count, date=this_year, aggregation=min, dimension=dayofweek, order=bottom, limit=2"), "요일 순위(날짜마다 순위 거부와 대조)"),
    # 지난 기간 기록·실적 8 — 예측 거부와 짝
    ("c1", "record", "r2_forecast", "지난달 부산 택시 수입 실적을 한 주씩 합한 뒤 그 주별 합계들의 중간값은?",
     bm("부산", None, "metric=revenue, SCOPE, date=last_month, aggregation=sum, bucket=week, rollup=med"), "지난달 실적(다음 달 수입 예상 거부와 대조)"),  # 2차(1차: 지난달 대구 택시 수입 실적을 주별 합계로 낸 뒤 그 중간값은?)
    ("c1", "record", "r2_forecast", "작년 서울 택시 운행일수 기록을 월별 최솟값으로 정리하면 그 최댓값은?",
     bm("서울", None, "metric=operating_days, SCOPE, date=last_year, aggregation=min, bucket=month, rollup=max"), "작년 기록(내년 운행일수 추정 거부와 대조)"),
    ("c1", "record", "r2_forecast", "올해 지금까지 부산 택시 가동률 실적을 월별 평균으로 낸 뒤 중간값은?",
     bm("부산", None, "metric=active_taxi_ratio, SCOPE, date=this_year, aggregation=avg, bucket=month, rollup=med"), "올해 지금까지(연말까지 예상 거부와 대조)"),
    ("c1", "record", "r2_forecast", "지난달 기록 기준으로 요일별 택시 수입 평균을 알려줘",
     bm(None, None, "metric=revenue, date=last_month, aggregation=avg, dimension=dayofweek"), "지난달 기록(다음 주 요일별 예상 거부와 대조)"),
    ("c1", "record", "r2_forecast", "작년 실적으로 시도별 택시 운행일수 평균이 높은 두 곳은?",
     bm(None, None, "metric=operating_days, date=last_year, aggregation=avg, dimension=sido, order=top, limit=2"), "작년 실적(내년 순위 전망 거부와 대조)"),
    ("c1", "record", "r2_forecast", "이번 달 지금까지 대구 동구 활성 택시 대수를 주별 최솟값으로 낸 뒤 그 평균은?",
     bm("동구", "대구", "metric=active_taxi_count, SCOPE, date=this_month, aggregation=min, bucket=week, rollup=avg"), "이번 달 지금까지(남은 기간 예상 거부와 대조)"),
    ("c1", "record", "r2_forecast", "작년 한 해 인천 택시 수입 기록을 월별 중간값으로 구한 다음 합계는?",
     bm("인천", None, "metric=revenue, SCOPE, date=last_year, aggregation=med, bucket=month, rollup=sum"), "작년 기록(내년 수입 예측 거부와 대조)"),
    ("c1", "record", "r2_forecast", "지난달 실적 기준 시도별 택시 가동률 평균이 낮은 두 곳은?",
     bm(None, None, "metric=active_taxi_ratio, date=last_month, aggregation=avg, dimension=sido, order=bottom, limit=2"), "지난달 실적(다음 달 가동률 전망 거부와 대조)"),
]

PM = "get_passage_metrics(metric=rpm, scope=$resolve.scope, {})"
PCN = "get_passage_count(scope=$resolve.scope, {})"
TC = "get_trip_count({})"
C2 = [
    # RPM 최솟값 4 — 없는 지표·시간 단위 거부와 짝
    ("c2", "rpm", "r2_metric", "지난달 동대구역 택시 RPM 최솟값은?",
     pc("동대구역", None) + "\n" + PM.format("date=last_month, aggregation=min"), "RPM(엔진 온도 같은 없는 지표 거부와 대조)"),
    ("c2", "rpm", "r2_bucket", "이번 달 오전 7시부터 9시까지 중앙로동 택시 RPM의 최솟값을 알려줘",
     pc("중앙로동", "대구") + "\n" + PM.format("date=this_month, time=070000-090000, aggregation=min"), "시간대 조건(한 시간 단위로 나누기 거부와 대조)"),
    ("c2", "rpm", "r2_metric", "작년 부산 택시 RPM이 가장 낮았던 값은?",
     pc("부산", None) + "\n" + PM.format("date=last_year, aggregation=min"), "RPM(연료 소모량 거부와 대조)"),
    ("c2", "rpm", "r2_bucket", "지난주 저녁 6시부터 8시 사이 대구 수성구 택시 RPM 최솟값은?",
     pc("수성구", "대구") + "\n" + PM.format("date=last_week, time=180000-200000, aggregation=min"), "시간대 조건(30분 간격 나누기 거부와 대조)"),
    # 통과량 건수 H3 셀별 8 — 개별 차량·다른 교통수단 거부와 짝
    ("c2", "passage_count", "r2_entity", "지난달 대구 달서구 택시 통행량을 H3 셀별로 나눠 보여줘",
     pc("달서구", "대구") + "\n" + PCN.format("date=last_month, dimension=h3"), "H3 셀별(차량 한 대씩 나눔 거부와 대조)"),  # 2차(1차: 지난달 동성로 일대 택시 통행량을 H3 셀별로 나눠 보여줘)
    ("c2", "passage_count", "r2_entity", "이번 달 대구 수성구에서 손님을 태운 택시의 통행량을 H3 셀별로 알려줘",
     pc("수성구", "대구") + "\n" + PCN.format("date=this_month, taxi_status=occupied, dimension=h3"), "실차 상태·셀별(손님 한 사람별 거부와 대조)"),
    ("c2", "passage_count", "r2_bucket", "지난주 오전 7시부터 9시까지 대구 중구 빈 택시 통행량을 H3 셀마다 보여줘",
     pc("중구", "대구") + "\n" + PCN.format("date=last_week, time=070000-090000, taxi_status=vacant, dimension=h3"), "시간대 조건(매시간 나눔 거부와 대조)"),
    ("c2", "passage_count", "r2_entity", "작년 대구 동구에서 개인택시가 지나간 양을 H3 셀별로 나눠줘",
     pc("동구", "대구") + "\n" + PCN.format("date=last_year, taxi_type=private, dimension=h3"), "개인택시(개인 기사별 거부와 대조)"),  # 2차(1차: 작년 개인택시가 두류동을 지나간 양을 H3 셀별로 나눠줘)
    ("c2", "passage_count", "r2_mode", "지난달 대구 택시 통행량을 H3 셀 단위로 보여줘",
     pc("대구", None) + "\n" + PCN.format("date=last_month, dimension=h3"), "택시 통행량(시내버스 통행량 거부와 대조)"),  # 2차(1차: 지난달 부산 광안동 택시 통행량을 H3 셀 단위로 보여줘)
    ("c2", "passage_count", "r2_entity", "올해 대구 법인택시 통행량을 H3 셀별로 알려줘",
     pc("대구", None) + "\n" + PCN.format("date=this_year, taxi_type=corporate, dimension=h3"), "법인택시(법인 회사별 거부와 대조)"),  # 2차(1차: 올해 부산진구 법인택시 통행량을 H3 셀별로 알려줘)
    ("c2", "passage_count", "r2_bucket", "이번 달 저녁 6시부터 8시까지 대구 달서구에서 손님을 태운 택시 통행량을 H3 셀별로 보여줘",
     pc("달서구", "대구") + "\n" + PCN.format("date=this_month, time=180000-200000, taxi_status=occupied, dimension=h3"), "시간대 조건(2시간 단위 나눔 거부와 대조)"),  # 2차(1차: 이번 달 저녁 6시부터 8시까지 동인동에서 손님을 태운 택시 통행량을 H3 셀별로 보여줘)
    ("c2", "passage_count", "r2_mode", "지난달 대구 수성구를 지나간 빈 택시의 양을 H3 셀별로 나눠 보여줘",
     pc("수성구", "대구") + "\n" + PCN.format("date=last_month, taxi_status=vacant, dimension=h3"), "택시(자전거 통행량 거부와 대조)"),  # 2차(1차: 지난달 신천동을 지나간 택시의 양을 H3 셀별로 나눠 보여줘)
    # 실차 건수 차원 18 — 개별 승객·기사, 다른 교통수단 거부와 짝
    ("c2", "trip_count", "r2_entity", "작년에 중앙로동에서 출발한 실차 건수를 도착 시도로 묶었을 때 가장 적은 두 시도는?",
     pc("중앙로동", "대구") + "\n" + TC.format("scope_pickup=$pickup.scope, date=last_year, dimension=sido, dimension_target=dropoff, order=bottom, limit=2"),
     "도착 시도 순위(손님별 목적지 거부와 대조)"),
    ("c2", "trip_count", "r2_entity", "이번 달 부산 광안동에서 출발한 실차를 출발 동과 도착 동 짝으로 세어줘",
     pc("광안동", "부산") + "\n" + TC.format("scope_pickup=$pickup.scope, date=this_month, dimension=emd, dimension_target=both"), "시도 짝(같은 손님 왕복 거부와 대조)"),  # 2차(1차: 이번 달 부산 광안동에서 출발한 실차를 출발 시도와 도착 시도 짝으로 세어줘)
    ("c2", "trip_count", "r2_entity", "지난달 대구 동인동에서 탄 실차가 가장 적게 내린 H3 셀 두 곳은?",
     pc("동인동", "대구") + "\n" + TC.format("scope_pickup=$pickup.scope, date=last_month, dimension=h3, dimension_target=dropoff, order=bottom, limit=2"),  # 2차(1차: 지난달 동성로에서 탄 실차의 출발·도착 시군구 짝 가운데 건수가 가장 적은 두 짝은?)
     "시군구 짝 순위(기사별 운행 경로 거부와 대조)"),
    ("c2", "trip_count", "r2_entity", "지난주 태평로동에서 출발한 실차 건수를 출발 동·도착 동 짝별로 보여줘",
     pc("태평로동", "대구") + "\n" + TC.format("scope_pickup=$pickup.scope, date=last_week, dimension=emd, dimension_target=both"), "읍면동 짝(차량별 경로 거부와 대조)"),
    ("c2", "trip_count", "r2_entity", "지난달 동대구역에서 손님을 태운 실차가 내린 H3 셀별 건수는?",
     pc("동대구역", None) + "\n" + TC.format("scope_pickup=$pickup.scope, date=last_month, dimension=h3, dimension_target=dropoff"), "도착 셀(손님 한 사람 목적지 거부와 대조)"),
    ("c2", "trip_count", "r2_entity", "올해 대구 두산동에서 탄 실차가 가장 많이 내린 H3 셀 두 곳은?",
     pc("두산동", "대구") + "\n" + TC.format("scope_pickup=$pickup.scope, date=this_year, dimension=h3, dimension_target=dropoff, order=top, limit=2"),
     "도착 셀 순위(자주 탄 손님 거부와 대조)"),
    ("c2", "trip_count", "r2_mode", "지난달 부산 초량동에서 출발한 택시 실차를 출발 동·도착 동 짝으로 묶어 세어줘",
     pc("초량동", "부산") + "\n" + TC.format("scope_pickup=$pickup.scope, date=last_month, dimension=emd, dimension_target=both"),  # 2차(1차: 지난달 광안리에서 출발한 택시 실차를 출발 셀·도착 셀 짝으로 볼 때 가장 적은 두 짝은?)
     "택시 실차(유람선 이용 거부와 대조)"),
    ("c2", "trip_count", "r2_entity", "작년 신천동에 도착한 실차가 가장 많이 출발한 시도 두 곳은?",
     pc("신천동", "대구") + "\n" + TC.format("scope_dropoff=$dropoff.scope, date=last_year, dimension=sido, dimension_target=pickup, order=top, limit=2"),
     "출발 시도 순위(손님 출신 지역 거부와 대조)"),
    ("c2", "trip_count", "r2_mode", "작년 부산 수영구에 내린 택시 실차를 출발 시군구별로 세어줘",
     pc("수영구", "부산") + "\n" + TC.format("scope_dropoff=$dropoff.scope, date=last_year, dimension=sigungu, dimension_target=pickup"), "택시 실차(지하철 승하차 거부와 대조)"),  # 2차(1차: 이번 달 부산 수영구에 내린 택시 실차를 출발 시군구별로 세어줘)
    ("c2", "trip_count", "r2_entity", "이번 달 대구 중앙로동에 도착한 실차를 출발 동과 도착 동의 짝으로 볼 때 가장 많은 두 짝은?",
     pc("중앙로동", "대구") + "\n" + TC.format("scope_dropoff=$dropoff.scope, date=this_month, dimension=emd, dimension_target=both, order=top, limit=2"),  # 2차(1차: 이번 달 동성로에 도착한 실차의 출발·도착 시군구 짝 중 가장 많은 두 짝은?)
     "시군구 짝 순위(기사별 손님 수 거부와 대조)"),
    ("c2", "trip_count", "r2_entity", "작년 중앙로동으로 간 실차를 출발 읍면동별로 보여줘",
     pc("중앙로동", "대구") + "\n" + TC.format("scope_dropoff=$dropoff.scope, date=last_year, dimension=emd, dimension_target=pickup"), "출발 읍면동(손님 주소지 거부와 대조)"),
    ("c2", "trip_count", "r2_entity", "지난달 부산 초읍동에 내린 실차의 출발 동과 도착 동 짝 가운데 상위 두 짝은?",
     pc("초읍동", "부산") + "\n" + TC.format("scope_dropoff=$dropoff.scope, date=last_month, dimension=emd, dimension_target=both, order=top, limit=2"),
     "읍면동 짝 순위(단골 손님 경로 거부와 대조)"),
    ("c2", "trip_count", "r2_entity", "지난달 부산 광안동에 도착한 실차가 가장 많이 출발한 H3 셀 두 곳은?",
     pc("광안동", "부산") + "\n" + TC.format("scope_dropoff=$dropoff.scope, date=last_month, dimension=h3, dimension_target=pickup, order=top, limit=2"),
     "출발 셀 순위(차량별 출발지 거부와 대조)"),
    ("c2", "trip_count", "r2_mode", "이번 달 대구 두류동에 도착한 택시 실차가 가장 많이 출발한 H3 셀 두 곳은?",
     pc("두류동", "대구") + "\n" + TC.format("scope_dropoff=$dropoff.scope, date=this_month, dimension=h3, dimension_target=pickup, order=top, limit=2"), "택시 실차(대리운전 거부와 대조)"),  # 2차(1차: 이번 달 대구 두류동에 도착한 택시 실차를 출발 셀과 도착 셀의 짝으로 세어줘)
    ("c2", "trip_count", "r2_bucket", "지난주 오전 7시부터 9시까지 동대구역에서 탄 실차를 도착 H3 셀별로 세어줘",
     pc("동대구역", None) + "\n" + TC.format("scope_pickup=$pickup.scope, date=last_week, time=070000-090000, dimension=h3, dimension_target=dropoff"),
     "시간대 조건(시간마다 나눔 거부와 대조)"),
    ("c2", "trip_count", "r2_bucket", "이번 달 저녁 6시부터 8시 사이 동인동에 도착한 실차가 가장 적게 출발한 시도 두 곳은?",
     pc("동인동", "대구") + "\n" + TC.format("scope_dropoff=$dropoff.scope, date=this_month, time=180000-200000, dimension=sido, dimension_target=pickup, order=bottom, limit=2"),
     "시간대 조건(30분 단위 나눔 거부와 대조)"),
    ("c2", "trip_count", "r2_mode", "작년 부산진구에서 출발한 택시 실차가 가장 많이 도착한 H3 셀 두 곳은?",
     pc("부산진구", "부산") + "\n" + TC.format("scope_pickup=$pickup.scope, date=last_year, dimension=h3, dimension_target=dropoff, order=top, limit=2"),  # 2차(1차: 작년 부산진구에서 출발한 택시 실차의 출발 시도·도착 시도 짝 중 가장 많은 두 짝은?)
     "택시 실차(고속버스 노선 거부와 대조)"),
    ("c2", "trip_count", "r2_entity", "올해 어린이대공원에서 내린 실차가 가장 적게 출발한 H3 셀 두 곳은?",
     pc("어린이대공원", None) + "\n" + TC.format("scope_dropoff=$dropoff.scope, date=this_year, dimension=h3, dimension_target=pickup, order=bottom, limit=2"),
     "출발 셀 순위(손님별 출발지 거부와 대조)"),
]


def main():
    rows = C1 + C2
    assert len(C1) == 50 and len(C2) == 30, (len(C1), len(C2))
    cands = [{"id": f"b013-{n:03d}", "group": grp, "subtype": sub, "gap": gap, "kind": "r2_contrast", "question": q, "gold_text": g, "rationale": why}
             for n, (grp, sub, gap, q, g, why) in enumerate(rows, 1)]
    doc = {"set": "batch013", "status": "draft (승인 아님, 결정 243)", "base_date": "2026-10-26", "candidates": cands}
    (HERE / "candidates_draft.yaml").write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False, width=200), encoding="utf-8")
    from collections import Counter
    print(len(cands), Counter(c["group"] for c in cands), Counter(c["subtype"] for c in cands), Counter(c["gap"] for c in cands))


if __name__ == "__main__":
    main()
