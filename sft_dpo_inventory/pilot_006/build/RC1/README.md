# RC1 — 학습 전 후보, PLAN 고정 전(pilot_006 세션 2b, H8)

**학습에 쓰지 않는다(아직).** PLAN 고정과 학습은 세션 3. 빌드: `../build6rc.py --out RC1 --label RC1`, 검사: `../rc_checks.py --rc RC1`.

## 구성

| 항목 | 값 |
|---|---|
| 승인 corpus(정규화 질문으로 합친 뒤) | 416질문(523레코드, 같은 질문 107 합침) |
| 두 arm 모두 레코드 있음 | 311 → 평가 셋 강한 겹침 14 제외 → 유형 상한(τ 0.09) 63 제외 → **234질문** |
| 빠진 이유(질문) | 두 arm 모두 레코드 없음 49, Partial만 없음 23, Full만 없음 33, 평가 셋 강한 겹침 14, 유형 상한 63 |
| 최종 질문 출처 | aug300 115, trunk 74, pg 23, batch007 15, batch008 7 |
| 질문 목록 sha256(두 arm 같음) | `3838db4c34c54f3b4e6ab2276d2f66ab34519705a8bf404ad5472cb73d900b93` |
| 레코드 | Full 776, Partial 779 — **모두 8b 자체(`json_only`)**, teacher 0 |
| 8b 자체 출처(계약 통과 정답 표본, 상한 전) | Full: J1 1,544, J9 263, S32F-a 100, S32F-b 28, J10 53(계약 위반 50 뺌) / Partial: J6 1,580, J8 337, S32P-a 104, S32P-b 38, J10 72(계약 위반 40 뺌) |
| 길이(상한 전 후보) | Full 최대 10,703(p90 8,622), Partial 최대 12,580(p90 9,812). 12,288 초과 2(Partial: aug300-281 J6, b004-20 S32P-a) 뺌, 빠진 질문 0 |
| 업체 100 겹침 | 빼지 않고 보고만(결정 106; `build_summary.json` `vendor100_overlap`) |

## 검사(`checks_summary.json`, `checks.log`)

| arm | dry-run | tokenizer-check | 출처별 손실 token | 마스크 audit |
|---|---|---|---|---|
| Full | 통과 | 통과 | 통과(8b 자체 776, JSON + EOS만, 손실 token p50 216) | 통과 |
| Partial | 통과 | 통과 | 통과(8b 자체 779, p50 122) | 통과 |

## 빠진 것과 RC2

- **teacher가 없다**: T0'(teacher 지시 v2 확인)가 불통과라 TEACH를 시작하지 않았다(결정 131, `../../teacher/T0V2_REPORT.md`). 그래서 8b 정답 표본이 한 arm이라도 없는
  질문(teacher 필수 98, `../../../pilot_006_prep/self_samples/r1/teacher_targets_h6.json`)은 RC1에서 빠졌고, 결정 86의 teacher `full_response` 출처가 0이다.
- batch009(43 후보)는 승인 전이라 넣지 않았다.
- RC2 만드는 법(teacher 수집과 batch009 승인 뒤):
  ```
  hfvenv/bin/python sft_dpo_inventory/pilot_006/build/build6rc.py --out sft_dpo_inventory/pilot_006/build/RC2 --label RC2
  hfvenv/bin/python sft_dpo_inventory/pilot_006/build/rc_checks.py --rc RC2
  ```
  teacher 원문은 `training/generated/pilot_006/teacher_v2/traces.jsonl`(TEACH 출력 경로)에서 자동으로 읽는다. batch009는 R0과 같은 방식으로 승인 corpus에 넣은 뒤
  (`approved_train_v1.jsonl`의 새 판) J12 표본을 승인 gold로 판정해 `SELF`에 더한다(빌드 도구에 출처 한 줄 추가).
