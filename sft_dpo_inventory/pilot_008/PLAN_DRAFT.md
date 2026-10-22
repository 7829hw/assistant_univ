# pilot_008 계획 초안(결정 219) — 거부 능력 회복, F-o11 수준 정답률 유지

**초안이다. 정하지 않는다.** 순서 seed 수·성공 기준·데이터 구성·최종 판정 범주는 사용자 결정(7절). 이 문서는 준비 세션(2026-10-22) 산출물이며 학습·승인·RC6 빌드는 하지 않았다.

## 1. 목표와 범위(결정 219)

- 목표: F-o11(pilot_007 채택, 결정 218) 수준의 정답률을 지키면서 거부 능력을 되살린다 — 지원하지 않는 질문은 거부, 지원하는 질문은 거부하지 않음.
- 범위: Full arm만(결정 213), recipe R1''(1 epoch, lr 2e-4 → 0, batch 1·accum 1, warmup 1, LoRA r16/α32, max_seq 12,288, 모델 seed 43), 순서 O4'(slot 순열, `train/order7b.py`).
- 데이터: RC6 = RC5 + batch011 승인분(거부 보강) — 구성 선택지는 `RC6_PLAN.md`.
- 근거: `refusal_contract.md` — 학습 데이터에 모델 거부(`{"unsupported": true}`) target이 0, F-o11은 protected_final_v1 거부 문항에서 4/80(base 38/80).

## 2. 학습(선택지)

| 선택지 | 학습 | GPU 세 장 일정(학습 약 3.0–3.3h, RC6 레코드 수에 비례) | 쓰임 |
|---|---|---|---|
| S3 | 순서 seed 3(43·1016·7) | 1바퀴(3개 동시) ≈ 3.3h + 평가 ≈ 1.5h → **약 5h** | seed sd 추정 자유도 2 |
| S5 | 순서 seed 5(43·1016·7·11·2027, B·B2와 같음) | 2바퀴(3 + 2) ≈ 6.6h + 평가 ≈ 2h → **약 9h** | F-o11 비교를 같은 seed로 짝지을 수 있음(B2 F 셀 재사용) |

- 대조(재학습 없음): B2의 F 다섯 셀(RC5, 같은 recipe·순서 seed)을 그대로 쓴다 → 같은 순서 seed끼리 짝(pilot_008 F 대 B2 F).
  단, RC6는 레코드가 늘어 O4' 순열 자체가 달라진다(같은 seed라도 순서 파일이 다름) — 짝은 "같은 순서 seed"이지 "같은 순서"가 아니다.
- checkpoint: 100%(lr 0)만 판정에 쓰고 25·50·75%는 보고만(A·A3와 같음). checkpoint 고르기를 하면 refusal_dev로만.

## 3. 평가 셀(모델마다)

| 셋 | k | 비고 |
|---|---:|---|
| 주 셋 151(selection_v2 98 + holdout 53) | 4 | base는 B단계까지의 k=12(B1·X2·B-base3) 재사용, F-o11 비교는 B2 F 셀 |
| valid98·aux | 4 | 개발 셋(base b3·b4 k=4 재사용) |
| refusal_dev 60(거부 30·대조 30) | 4 | **새 개발 셋**(P3, 승인 뒤). base·F-o11 셀은 준비 세션 J-rdev로 이미 있음(진단용 초안 셀 — 승인 뒤 같은 seed로 다시 잴지 결정) |

- 셀마다 함께 보고: 과잉 거부(거부 아닌 문항 표본 중 결과 상태 unsupported·needs_clarification, `analysis/refusal_p1.py` 분류: 모델 거부·프로그램 거부·확인 요청), 올바른 거부율.
- 지연 창: 후보 하나와 base(PROTOCOL_v4 6절, 고정 30문항) — pilot_007과 같은 방법.

## 4. 성공 기준 후보(고르지 않음)

| 기준 | 후보 | 계산 |
|---|---|---|
| 거부 | (R-a) refusal_dev 거부 문항 올바른 거부율 ≥ base(점 추정) / (R-b) 차이 CI 하한 > 0 대 F-o11 / (R-c) CI 하한 ≥ base − 마진 | 문항 단위 bootstrap(arm 대 base), 순서 seed × 문항 계층(arm 대 F-o11) |
| 과잉 거부 | (O-a) refusal_dev 대조 문항과 주 셋에서 F-o11보다 늘지 않음(차이 CI 하한 ≤ 0) / (O-b) 점 추정 ≤ F-o11 + 1%p | 같은 순서 seed 짝(B2 F 셀) |
| 정답률 | (A-a) 주 셋에서 F-o11 대비 비열등, 마진 −3%p / (A-b) 마진 −5%p(pilot_007 Gate A와 같음) | 같은 순서 seed 짝, 계층 bootstrap(결정 170 방식) |

- 예상 반폭(정답률 비열등, 같은 seed 짝): B2 F seed sd 3.99 기준 S5 ≈ 4.0–4.5%p, S3 ≈ 5–6%p — 마진 −3%p는 S5에서도 판정 불가 가능성이 크다(`analysis/pf2_power.json` 참고).
- 거부 기준의 검정력: refusal_dev 거부 30 × k=4에서 base(J-rdev) 대비 차이의 반폭 — `analysis/pf2_power.json`.

## 5. 최종 판정

- protected_final_v2(`protected_final_v2_SPEC.md`)에서 새 후보 하나 대 base, k=8 한 번.
- 선택지: (F1) 정답률만 판정 범주(PROTOCOL_v4 6절 그대로), 거부는 함께 보고 / (F2) 거부 조건을 판정 범주에 넣음(예: 올바른 거부율 차이 CI 하한 > 0 그리고 과잉 거부 차이 CI 하한 ≤ 0).
- F-o11을 함께 재는지(후보 둘 대 base)는 v2 SPEC 1절 "후보 하나"와 충돌 — 하려면 SPEC 결정이 필요.

## 6. 일정(초안)

1. batch011·refusal_dev 2차 검토 → 사용자 결정(승인분).
2. protected_final_v2 작성 시작(학습 전, 결정 220) — 새 대화 작성·사용자 검토, Claude Code는 검사만.
3. RC6 빌드(`RC6_PLAN.md` 선택지 결정 뒤) → PLAN 고정 → 학습(S3 약 5h / S5 약 9h) → 평가 → 판정.
4. 최종 판정은 protected_final_v2 고정 뒤.

## 7. 사용자 결정 목록

1. 순서 seed 수: S3 / S5.
2. 성공 기준: 거부(R-a / R-b / R-c와 마진), 과잉 거부(O-a / O-b), 정답률(A-a −3 / A-b −5%p), 셋의 결합(모두 / 거부 + 정답률).
3. RC6 구성: 거부 비율 목표(5·8·10%), 거부 레코드 출처(base 올바른 거부 표본 / json_only 거부 target / 둘 다), r2 근접 대조 레코드 출처(`RC6_PLAN.md`).
4. refusal_dev 승인 뒤 base·F-o11 셀을 다시 잴지(초안 셀은 진단용).
5. checkpoint 고르기를 할지(refusal_dev로만) 100%만 쓸지.
6. 최종 판정 범주(F1 / F2)와 protected_final_v2 분포(SPEC 사용자 결정).
7. 운영 반영 조건(결정 218: 거부 문제 해결 뒤) — 어떤 결과면 "해결"로 볼지.
