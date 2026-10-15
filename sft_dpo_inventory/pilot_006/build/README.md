# pilot_006 데이터 빌드 도구(C6, 세션 2)

- `build6.py`: canonical + teacher trace + 8b 자체 표본 → 두 arm SFT 레코드(결정 86 출처별 손실 범위, 유형 상한 τ 0.09, 평가 셋 강한 겹침 제외,
  두 arm 질문 목록 sha256 일치, 미승인·EDIT_REQUIRED·결정 119 제외 자동 제외, F4 길이 후보와 `L_req`, M1 세트). 상세는 머리 주석.
- `check_loss_tokens6.py CONFIG OUT`: 출처별 손실 token 검사(teacher = 응답 전체 + EOS, 8b 자체 = JSON + EOS).
- `loss_mask_audit6.py CONFIG OUT`: partial-grounding loss-mask audit 방법(collator label 확인)을 출처별 기대로.
- `m1_run.py`: 메모리 확인 학습(결정 129, F4 규칙 판정). 스케줄러가 `session2_ready/M1.json`으로 부른다.
- 학습 코드: `training/trainer_common.py`에 `data.grounding_target` 분기(기본 full, partial이면 P0.3 system과 completion 뒤 계약 검사).
  Full 동작은 그대로(`tests/test_trainer_grounding_target.py`).

## PROVISIONAL/ — 시험 빌드(**학습에 쓰지 않음**, `--with-j6`)

지금 승인된 데이터만: trunk pilot_004 판 131질문, pg 수용(결정 121) 중 trunk와 겹치지 않는 40질문, J1·J6 정답 표본(pg 질문). teacher는 pilot_004 판의 기존 teacher 레코드와
pg reasoning_v001의 27b teacher thinking을 그대로 썼다(**표현 중립 지시가 아님**, `teacher_neutral: false`). 답 JSON은 canonical 렌더.

| 항목 | 값 |
|---|---|
| 질문 풀 / 두 arm 모두 레코드 있음 / 평가 셋 강한 겹침 / 유형 상한 뒤 | 171 / 85 / 0 / **52**(질문 목록 sha256 `064b211b…`) |
| 한쪽만 레코드 | Full만 76, Partial만 2, 둘 다 없음 8 — trunk 131질문은 Partial 8b 자체 표본이 없다(J1·J6 대상 밖) |
| 레코드 | Full 198(teacher 180, 8b 자체 18), Partial 194(teacher 180, 8b 자체 14) |
| 8b 자체 표본 계약 필터 | 채점은 맞지만 계약 위반(INVALID_FACTOR_COMBINATION, MULTIPLE_MEASURES)으로 뺀 표본 Full 10, Partial 6 |
| dry-run·tokenizer-check | 두 arm 통과(`checks.log`, configs/provisional_*.yaml, max_seq_length 12,800) |
| 출처별 손실 token | Full teacher 97.5% / 8b 자체 2.5%, Partial teacher 98.8% / 8b 자체 1.2%(`loss_tokens_*.json` all_ok) |
| 손실 마스크 audit | 두 arm 기대와 다른 레코드 0(`loss_mask_audit_*.json`) |
| 길이(`lengths.json`) | `L_req` **12,800**(최댓값 12,701: Partial J6 표본 aug300-340). Partial 8b 자체 표본 중 11,392 초과 8건. Full 최대 11,325 |

**세션 3에 넘길 것**: trunk 131질문의 Partial arm 8b 자체 표본이 없다(J1·J6은 aug300·pg·batch007 401질문). 두 arm 출처 구성을 맞추려면 131질문 × 9를 Partial로 모아야 한다
(약 50분). Full은 pilot_004 판의 HF 8b 자체 레코드가 있으나 생성 경로가 HF(vLLM 아님)라, 같은 vLLM 경로로 Full도 다시 모을지 결정이 필요하다.
