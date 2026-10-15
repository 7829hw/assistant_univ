# 8b 자체 표본 판정(C2·C3)

`judge_self.py --arm full|partial` → `j1_judgement.json`(J1 Full), `j6_judgement.json`(J6 Partial). 모델 호출 없음. 필터·import는 하지 않았다(세션 3 데이터 빌드).

- 판정 기준(PLAN_DRAFT 3절): 조건 계층 **전** 원응답의 최종 JSON을 gold와 `evaluate_vendor100.grounding_check`로 비교(Partial은 completion 뒤). 조건 계층 뒤 일치는 참고로만.
  잘림·JSON 없음은 오답.
- gold 상태: `approved_pg`(결정 121 수용 147), `held_edit_required`(7), `draft`(aug300 train 207 + batch007 27, **초안 기준 — 승인 뒤 다시 판정**), `excluded_e4`(결정 119로 제외된 13).

## J1(Full, 401질문 × 9 = 3,609)

| gold 상태 | 질문 | 정답 표본 있음 | 없음 | greedy 정답 | 정답 표본 수 |
|---|---:|---:|---:|---:|---:|
| draft | 234 | 194 | 40 | 150 | 1,312 |
| approved_pg | 147 | 84 | 63 | 33 | 316 |
| held_edit_required | 7 | 4 | 3 | 1 | 13 |
| excluded_e4 | 13 | 12 | 1 | 11 | 89 |

- teacher 우선 대상(8b 정답 표본 없음, approved_pg + draft): **103질문**(`j1_judgement.json`의 `no_correct_questions(teacher priority)`).
- 많은 오답 차이: 장소 692, 집계 548, 날짜 438, vicinity 380, dimension_target 221, taxi_status 163(표본 단위, 한 표본에 여러 개).

## J6(Partial, P0.3 prompt, 401질문 × 9 = 3,609, 결정 117 17,408 서버)

| gold 상태 | 질문 | 정답 표본 있음 | 없음 | greedy 정답 | 정답 표본 수 |
|---|---:|---:|---:|---:|---:|
| draft | 234 | 181 | 53 | 138 | 1,262 |
| approved_pg | 147 | 85 | 62 | 44 | 348 |
| held_edit_required | 7 | 4 | 3 | 1 | 16 |
| excluded_e4 | 13 | 6 | 7 | 4 | 42 |

- teacher 우선 대상(Partial 8b 정답 표본 없음): 115질문. 오답 차이(표본 단위): dimension_target 380(J1 221), 측정값 185(J1 94), 집계 293(J1 548).

## 두 arm 대조(C3, `compare_arms.py` → `arm_comparison.json`)

| gold 상태 | 둘 다 정답 표본 | Full만 | Partial만 | 둘 다 없음 |
|---|---:|---:|---:|---:|
| draft | 176 | 18 | 5 | 35 |
| approved_pg | 70 | 14 | 15 | 48 |
| held_edit_required | 4 | 0 | 0 | 3 |
| excluded_e4 | 6 | 6 | 0 | 1 |

- 한쪽 arm에만 정답 표본이 있는 질문 목록: `arm_comparison.json`의 `full_only`·`partial_only`(세션 3 빌드에서 그 arm의 8b 자체 레코드가 비는 질문 → teacher로 채움).
- **Partial 실패와 risk tag**(aug300 표본 중 그 차이가 난 비율): dimension_target 차이는 dt_pickup 문항 Full 0.17 → Partial 0.58, dt_dropoff 0.08 → 0.28, od_both_dt_one 0 → 0.11,
  silcha_trip 0.19 → 0.28. 측정값 차이는 occupied_passage(실차 통행량) 문항에 몰린다(Full 0.31, Partial 0.44).
- J5S'의 실패(old44/g02·g04·g12, MISSING_RELATION_QUALIFIER — 끝 묶음 누락)와 **같은 패턴**이다: Partial(P0.3) base는 승차·하차 끝으로 묶는 판단(dimension_target)을 더 자주 빠뜨린다.
  partial-grounding의 P0.2·P0.3 기록("dt 누락 증가")과도 같다.
