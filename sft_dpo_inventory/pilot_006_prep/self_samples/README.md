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
