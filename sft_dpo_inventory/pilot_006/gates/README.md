# Gate 계산 도구(C7) — 세션 3 사전 등록 때 그대로 고정

`compute_gates.py --spec SPEC.json --out OUT.json`. PLAN_DRAFT 5절 Gate A–E와 arm별 선행 조건(대 base, 보정 없음). 계산 규칙은 파일 머리 주석.
표본 채점·분류는 `calibration_001/analyze_cal.load_sample`(pilot_005·judge_v3와 같음), CI는 문항 단위 쌍 bootstrap 10,000회 `default_rng(20261109)`.

## 시험(`selftest/`, 봉인 셀은 쓰지 않음)

| 시험 | 기대 | 결과 |
|---|---|---|
| F = B1, P = X2(같은 조건 반복) | P − F 차이가 0 근처 | A +3.06 [−1.28, 7.40](0 포함), B 0.00 [−1.28, 1.28], C +0.51 [−1.28, 2.04]. 표 정상 |
| F = pilot_005 v1_step467, P = v2_step934(가짜 F·P) | 표 형식, 대 base 수치가 pilot_005 기록과 같음 | v1_step467 대 base +11.22 [5.10, 17.86](pilot_005 +11.22). A −1.53 [−5.87, 2.55](불통과), D 통과(repair 개선), E 불통과(지연 1.566) |
| 합성 경계 사례(`tests/test_compute_gates.py`, 6개) | 동일 arm, 개선 arm, 마진 경계, dt 증가, 지연 1.5 초과, 선행 조건 | 통과 |

- token 분해(입력, thinking, 최종 JSON, 전체 생성)는 셀 meta의 원문 파일(`hf.raw_out`)을 Qwen3-8B tokenizer로 나눈다. 원문이 없으면 해당 값은 비어 있다.
- 지연 비는 `latency`(지연 도구 C8의 셀 json, 문항별 server_seconds 합의 중앙값)로 넣는다.
