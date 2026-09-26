-- reference provider 기대값을 provider·compiler 코드와 독립적으로 계산하는 SQL(SQLite).
-- 입력: synthetic_operation_days.csv를 테이블 ops로 읽은 것(revenue_krw 빈칸은 NULL).
-- 주: 월요일 시작, 기간 경계에서 자름. 주 시작 = date(service_date, 'weekday 0', '-6 days').
-- 매개변수: :scope, :taxi_type('all'이면 조건 없음), :start, :end (YYYY-MM-DD, 양 끝 포함).
-- tests/test_reference_provider.py가 각 문을 이름으로 꺼내 실행하고, 손으로 센 값과도 대조한다.

-- name: filtered
-- 조건에 맞고 매출이 결측이 아닌 레코드.
SELECT record_id, service_date, revenue_krw FROM ops
WHERE scope = :scope
  AND (:taxi_type = 'all' OR taxi_type = :taxi_type)
  AND service_date BETWEEN :start AND :end
  AND revenue_krw IS NOT NULL;

-- name: overall
SELECT COUNT(*) AS n, SUM(revenue_krw) AS total, AVG(revenue_krw) AS mean FROM ops
WHERE scope = :scope
  AND (:taxi_type = 'all' OR taxi_type = :taxi_type)
  AND service_date BETWEEN :start AND :end
  AND revenue_krw IS NOT NULL;

-- name: weeks
-- 기간의 모든 주(자료가 없는 주도 포함)와 주별 통계. 자료가 없는 주는 n=0, total/mean NULL.
WITH RECURSIVE days(d) AS (
  SELECT :start UNION ALL SELECT date(d, '+1 day') FROM days WHERE d < :end
),
week_of AS (
  SELECT d, date(d, 'weekday 0', '-6 days') AS monday FROM days
),
spans AS (
  SELECT monday, MIN(d) AS first_day, MAX(d) AS last_day FROM week_of GROUP BY monday
)
SELECT replace(s.first_day, '-', '') || '-' || replace(s.last_day, '-', '') AS label,
       COUNT(o.record_id) AS n, SUM(o.revenue_krw) AS total, AVG(o.revenue_krw) AS mean
FROM spans s
LEFT JOIN ops o
  ON o.service_date BETWEEN s.first_day AND s.last_day
 AND o.scope = :scope
 AND (:taxi_type = 'all' OR o.taxi_type = :taxi_type)
 AND o.revenue_krw IS NOT NULL
GROUP BY s.monday
ORDER BY s.monday;
