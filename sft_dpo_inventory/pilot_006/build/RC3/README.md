# RC3 — 학습 전 후보(pilot_006 세션 2d, P5). PLAN 확정본의 데이터

빌드: `../build6rc.py --out RC3 --label RC3 --teach-variant v3b`(승인 corpus v2), 검사: `../rc_checks.py --rc RC3` — **두 arm 모두 dry-run·tokenizer-check·출처별 손실 token·마스크 audit 통과**.

| 항목 | 값 |
|---|---|
| 질문 | 473 → 두 arm 레코드 있음 467 → 강한 겹침 17·유형 상한 64 → **386**(질문 목록 sha256 `6b06bb2cbc1ff91dccf90432327c02d814a6c77fbe6e55c1b006991c48e4b773`, 두 arm 같음) |
| 출처 | aug300 164, trunk 113, batch009 42, pg 33, batch007 27, batch008 7 |
| 한 arm이라도 레코드 없어 빠진 질문 | 6(두 arm 모두 없음 1, Partial만 없음 3, Full만 없음 2) |
| 레코드 | Full 1,861(teacher 836 + 8b 1,025, `sft_train.jsonl` sha256 `756160fe…`), Partial 1,826(teacher 836 + 8b 990, `00ce1f9e…`) |
| teacher | TEACH v3b 1,960 trace 중 통과 1,846(결정 149 L1), 질문당 최대 4(결정 48) |
| 손실 token 비율(teacher / 8b) | Full **71.3% / 28.7%**, Partial **81.0% / 19.0%** — pilot_004·005 teacher 81.8%와 비교: Full −10.5%p, Partial −0.8%p(±20%p 안) |
| 레코드 비율(teacher) | Full 44.9%, Partial 45.8% |
| 길이 | teacher Full 최대 8,890 / Partial 10,323, 8b Full 10,703 / Partial 12,580. 12,288 초과 2(Partial 8b: aug300-281 J6, b004-20 S32P-a) 뺌 — F4 규칙 3, 빠진 질문 0 |
| 결정 140 family | 최종 16질문(승인 corpus 19 중) |
| 업체 100 겹침 | 보고만(결정 143) |

## 알려진 문제(미결, `../teacher/TEACH_READ.md` 3절)

teacher 레코드의 **69%(Full 575/836, Partial 582/836)** thinking에 받은 결론을 의식한 표현("결론과 일치한다", "결론을 확인", "conclusion" 등)이 있다(검사 (c) 목록 밖).
학습 때는 결론이 입력에 없다. 이 RC3를 그대로 쓸지, 거른 판(RC3s)을 만들지는 사용자 결정(PLAN.md 9절).
