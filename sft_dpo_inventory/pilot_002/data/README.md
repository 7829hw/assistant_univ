# pilot_002 학습 데이터(`thinking_pilot002_t2pc`)

작성: 2026-10-08. 모델을 부르지 않았다(tokenizer만 CPU). 만드는 법: `build_pilot002.py` 머리 주석.

## 1. 결과

| 항목 | 값 |
|---|---|
| 판 | `training/generated/thinking_pilot002_t2pc`(결정 33에 따라 커밋) |
| sha256 | sft_train `398d1991…`, dpo_train `4047769f…`, manifest `ca029a3e…` |
| SFT | 379 레코드, 107질문. 전부 train |
| DPO | 288쌍, 45질문(constraint 194, semantic 94). HF base trace 쌍만이다 |
| 정지 target SFT 레코드(결정 14) | 31 |
| SFT 레코드가 없는 gold 질문 | 4: b004-19, b004-35, b005-11, b005-60 |

**SFT 출처**

| 출처 | 레코드 | 비율 |
|---|---:|---:|
| HF v004(r1과 같음) | 124 | 32.7% |
| HF batch005 | 86 | 22.7% |
| teacher 17질문(결정 48·49) | 68 | 17.9% |
| teacher batch005 27질문(결정 50) | 101 | 26.6% |

- HF 210 / teacher 169.
- 질문 원천별 레코드: v003 144(35질문), v004 batch004 48(16질문), batch005 187(56질문).
- 질문 원천별 DPO 쌍: v003 102, batch004 59, batch005 127.

**유형 분포(개발 셋 454질문 대비 TV)**

| 단위 | TV |
|---|---:|
| SFT 질문 | 0.016 |
| SFT 레코드 | 0.080 |
| DPO 쌍 | 0.087 |

- 레코드 단위에서 "집계 있음·묶음 없음"은 36.4%(개발 28.4%), "dim+dt"는 25.6%(개발 28.0%)다. 칸별 값은 `summary.json`의 `final.type`에 있다.

**길이(응답 token, EOS 포함)**

| | 최소 | 중앙 | p90 | 최대 |
|---|---:|---:|---:|---:|
| SFT | 471 | 915 | 1,503 | 4,050 |
| DPO(쌍의 긴 쪽) | 578 | 1,213 | 2,342 | 4,050 |

- SFT 전체 token 최대는 11,325(한도 11,392)다.
- SFT 손실 token은 레코드당 132–338개, 합계 82,034다(`loss_tokens.json`).

## 2. 빠진 레코드와 이유

| 단계 | SFT | DPO |
|---|---:|---:|
| 계약 필터(v004, pilot_001 r1 builder와 같음) | 8 | 37(chosen 계약 실패) |
| 결정 18 길이(config 한도) | 0 | 5(batch005, 응답 > 4,096) |
| 결정 40-D 루프 | 0 | 0 |
| 결정 51(검토 쌍과 같은 응답을 rejected로 쓰는 trace 쌍) | – | 0 |
| 결정 52 질문당 8쌍 상한 | – | 123(v004 51, batch005 72) |
| teacher batch005: 오답 34, 중복 0. 필터 통과 182 중 질문당 4개 상한 | 81 | – |

- 결정 52: 19질문에 상한을 적용했다. 상한 뒤에도 질문마다 rejected 오류 유형(필드 이름 집합)의 종류 수는 줄지 않았다.
- 결정 51: 검토 queue의 HF 첫 응답 쌍(v004 39, batch005 36)은 chosen에 추론이 없어 thinking DPO에 쓰지 않는다(pilot_001과 같다).
  14개 쌍은 결정 51로 빠진다. 같은 응답이 trace 쌍의 rejected로 남아 있지 않은 것도 확인했다.
- batch005 단계 앞의 필터(결정 4·6 등)는 `../../pilot_prep_005/traces/batch005_filtered.json`, v004는 `../../pilot_001/data/summary.json`에 있다.

## 3. 검사

| 검사 | 결과 |
|---|---|
| `train_sft --dry-run`, `--tokenizer-check` | 통과(`checks.log`) |
| `train_dpo --dry-run`, `--tokenizer-check` | 통과 |
| SFT 손실 token이 `</think>` 뒤 JSON + EOS에만 있고 0보다 큼 | 379/379(`loss_tokens.json`) |
| 겹침(`overlap.json`) | 아래 |

**겹침**

- 질문·id 겹침: selection_v1, aux_test_v1, valid98, 업체 100 모두 0이다.
- selection_v1, aux_test_v1: template·family 겹침도 0이다.
- valid98·업체 100: template·family 겹침이 있다. 모두 v004 승인 corpus 문항이다. 사용자가 그대로 진행하기로 했다(결정 54).
  - valid98: b004-05·20·21·23(pilot_001에도 있음), ann-e645cbc1·b004-06(teacher로 새로 들어옴).
  - 업체 100: ann-7fae41a3(012·093 template), ann-f7808786(076 template), ann-e645cbc1(016 family), 결정 15 문항(b004-05·06·15·30·31).

## 4. 파일

| 파일 | 내용 |
|---|---|
| `build_pilot002.py` | 데이터 구성 |
| `candidates_pilot002.json` | 최종 후보 id(원문 없음) |
| `teacher_batch005.json` | 결정 50 필터·선택 |
| `summary.json` | 단계별 수, 레코드별 판정, 분포, sha256 |
| `check_loss_tokens.py` → `loss_tokens.json` | 손실 token 검사 |
| `check_overlap.py` → `overlap.json` | 평가 셋 겹침 |
| `checks.log` | dry-run·tokenizer 검사 출력 |

trace 원본 모음(`training/generated/pilot_002/combined_traces.jsonl`, sha256 `43c34514…`)은 ignore 경로에 두고 커밋하지 않는다.
