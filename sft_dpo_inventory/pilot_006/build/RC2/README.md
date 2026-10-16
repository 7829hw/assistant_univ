# RC2 — 학습 전 후보, PLAN 고정 전(pilot_006 세션 2c, P7)

**학습에 쓰지 않는다(아직).** 빌드: `../build6rc.py --out RC2 --label RC2`(승인 corpus v2), 검사: `../rc_checks.py --rc RC2`.

## 구성

| 항목 | 값 |
|---|---|
| 승인 corpus v2(정규화 질문으로 합친 뒤) | 473질문(580레코드) |
| 두 arm 모두 레코드 있음 | 350 → 평가 셋 강한 겹침 14 → 유형 상한(τ 0.09) 56 → **280질문** |
| 빠진 이유(질문) | 두 arm 모두 레코드 없음 56, Partial만 없음 32, Full만 없음 35, 강한 겹침 14, 유형 상한 56 |
| 최종 질문 출처 | aug300 126, trunk 90, pg 27, batch007 17, batch009 13, batch008 7 |
| 질문 목록 sha256(두 arm 같음) | `ff9068ac4cedcbb6af7ecd5e1b657a91bb21e8fee4b1d2355898baf846228f6c` |
| 레코드 | Full 885, Partial 896 — **모두 8b 자체(`json_only`), teacher 0** |
| 8b 출처(계약 통과 정답, 상한 전) | Full J1 1,594·J9 263·S32F-a 100·S32F-b 28·J10 53·J12 52·S64F 28·J13 81 / Partial J6 1,583·J8 337·S32P-a 104·S32P-b 38·J10 72·J12 65·S64P 47 |
| 길이 | Full 최대 10,703(p90 8,642), Partial 최대 12,580(p90 9,876); 12,288 초과 2 뺌(빠진 질문 0) |
| 결정 140 family(scope 이름 조회) | 승인 corpus 19질문 중 **RC2에 1**(aug300-367). 나머지 18은 Partial 8b 정답이 없어 빠짐(J13 Partial 0/9) |
| 업체 100 겹침 | 보고만(결정 143) |

## 검사(`checks_summary.json`)

두 arm 모두 dry-run·tokenizer-check·출처별 손실 token·마스크 audit 통과. 손실 token: Full 189,075(8b JSON + EOS만, p50 216), Partial 109,568(p50 121).

## teacher 비율 — **지시 5절 보고 대상**

| | teacher 레코드 비율 | teacher 손실 token 비율 |
|---|---:|---:|
| pilot_004·005 | – | 81.8% |
| RC2 | **0%** | **0%** |

T0'(v2)·T0''(v3a·v3b)가 모두 불통과라 TEACH를 하지 않았다(결정 131·144, `../teacher/T0V2_REPORT.md`, `T0V3_REPORT.md`). 결정 86 출처 구성(teacher `full_response`)과 다르고,
한 arm이라도 레코드가 없어 빠진 질문이 123개다(8b 정답이 없는 teacher 필수 113 + 정답 표본이 학습 계약 검사에서 빠진 10). 장소 이름 조회 family 18질문이 여기에 들어 있다.

## RC3

teacher를 모은 뒤(지시 수정 → 확인 통과 → TEACH, 원문 `training/generated/pilot_006/teacher_v3/traces.jsonl` 또는 새 경로):
```
hfvenv/bin/python sft_dpo_inventory/pilot_006/build/build6rc.py --out sft_dpo_inventory/pilot_006/build/RC3 --label RC3 [--teach PATH --teach-variant v3x]
hfvenv/bin/python sft_dpo_inventory/pilot_006/build/rc_checks.py --rc RC3
```
