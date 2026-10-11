# Partial-P0.2 측정 계획 — 확정 2026-10-11(사용자, 결정 59)

가설: P0.1의 하락(Full 대비 −6.8%p, `REPORT_P0_1.md`)은 Partial contract 자체가 아니라 output_format 교체에서
scope/place value 보존 규칙이 빠졌기 때문이다. P0.2는 그 규칙만 복원하고 나머지는 P0.1로 고정한다.

## 1. prompt

`evaluation/partial_grounding/prompts/partial_p0_2.yaml`, 결합 system prompt hash `87fd3441…`. P0.1과 다른 곳은
output_format뿐이고 추가만 있다: 규칙 10(place·scope value 보존, 장소 자체가 답이면 value 없는 place)과 예시 6
(`scope:edge:1742`의 평균 속도). P0.1의 경계 규칙 1–9, 예시 1–5, task, 의미 설명 section, 재질의 요청문은 그대로다.
factor 오류(dimension에 pickup·week, time 형식)에는 규칙을 더하지 않는다. 예시 1–6과 규칙 10의 장소 예는 고정
parser/composer(mock)에서 모두 answered다. 실행 의미 코드 지문 `ab88a19e` 그대로.

## 2. 셀과 분석

`run_p0_2.sh`: smoke(001–003) → greedy → sampling r1–r5(seed 20261010–20261014). 조건·장비 절차·guard·중단 규칙은
`PLAN.md` 1·2절과 같다. Full·P0·P0.1은 기존 셀을 다시 쓴다.

`analyze.py --arms full,p0_2`(gate), `--arms p0_1,p0_2`(가설 확인). gate는 `PLAN.md` 4절과 같다.
가설 확인: scope id 문항 8개(009, 029, 042, 051, 066, 082, 088, 094)가 Full·P0 수준으로 돌아오고, 나머지 92문항과
P0.1이 겨냥한 경계 오류(INVALID_CONCEPT, UNKNOWN_ATTRIBUTE, NO_MEASURE) 감소가 P0.1과 같은 수준으로 유지되는가.
