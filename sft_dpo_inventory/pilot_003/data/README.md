# pilot_003 학습 데이터(`thinking_pilot003_t2pc`)

작성: 2026-10-13. 스크립트 `build_pilot003.py`(= `pilot_002/data/build_pilot002.py` + batch006 HF trace·teacher). 기록 `summary.json`, `candidates_pilot003.json`,
`teacher_batch005.json`, `teacher_batch006.json`. trace 원본 모음(`training/generated/pilot_003/combined_traces.jsonl`)은 ignore 경로다.

| 항목 | 값 |
|---|---|
| sha256 | sft_train `f19a308bd51a023665c4e952182afb5b930f2e1e4ee4eab4490a17be79e31a4d`, dpo_train `64c109358ddb7b1a831fb3eea5e2eb0896b88830b757da6f7fd6bda25ad46e7e`, manifest `c16d4cb2e81c7dda92fa3ed5593b5b70393ddc80cccb045d9766585439c9a9c1`(valid 두 파일은 빈 파일) |
| 규모 | **SFT 460(131질문), DPO 348쌍(53질문)**. 모두 train. gold `reviewed_gold_v006_t2pc`(135질문) |
| pilot_002와의 관계 | pilot_002 레코드 SFT 379·DPO 288은 순서·내용까지 그대로 들어 있다(같은 원천·필터·seed). 더한 것: batch006 SFT 81, DPO 60 |
| SFT 출처 | HF v004 124(27.0%), HF batch005 86(18.7%), HF batch006 17(3.7%), teacher17 68(14.8%), teacher batch005 101(22.0%), teacher batch006 64(13.9%). HF 227 : teacher 233 |
| DPO 출처 | HF trace 쌍만(교차 DPO 없음, 결정 48·50·81). v003 102, batch004 59, batch005 127, batch006 60. 질문당 최대 8쌍(결정 52, 상한에 걸린 질문 23) |
| 유형 분포(TV, 개발 셋 대비) | SFT 질문 0.117, SFT 레코드 0.124, DPO 쌍 0.140(pilot_002: 0.133·0.149·0.162, `../../pilot_002/data/summary.json`) |
| 실차 통행량 대조(결정 66) | SFT 레코드 occupied 24 · vacant 16 · plain 20 · trip 21(각 6질문). DPO 쌍 vacant 20 · plain 16 · trip 24, **occupied 0**(occupied 6질문 모두 HF 정답 표본이 없어 teacher SFT만 있다) |
| 정지 target SFT 레코드 | 31(결정 14) |
| SFT 응답 길이(token, EOS 포함) | p50 915, p90 1,488, max 4,050 |

## batch006에서 빠진 것과 이유

- HF trace(`../traces/batch006_filtered.json`): 24질문 중 정답 표본이 있는 질문 8. SFT 후보 18 → 17(결정 4 tokenize 불일치 1).
  DPO 후보 108 → 92(결정 4 12, 결정 6 운영 경로에서 같아짐 4) → 결정 52 상한으로 60.
- teacher(결정 81, qwen3.8:27b, Ollama 0.35.1 연속 방식, GPU 3, 결정 55 guard 통과·최소 77.8 tok/s): 16질문 128표본 중 정답 125, 필터 통과 125,
  질문당 4개 상한으로 64(seed 20261008 + batch006 대상 질문 순번).
- 검토 queue 쌍(결정 80)은 thinking DPO에 쓰지 않는다(pilot_002와 같음). 결정 80에서 뺀 쌍의 응답을 rejected로 쓰는 trace 쌍은 0이었다.
- 승인 질문 중 SFT가 없는 질문: pilot_002와 같은 4개(b004-19, b004-35, b005-11, b005-60). batch006은 0.

## 검사(`checks.log`, `loss_tokens.json`, `overlap.json`)

- SFT·DPO `--dry-run`, `--tokenizer-check` 통과(SFT 460, DPO 348).
- SFT 손실 token이 `</think>` 뒤 JSON + EOS에만 있다: 460/460(132–338개).
- 겹침(selection_v2, aux_test_v1, valid98, 업체 100): 질문·id 0. template·family 겹침은 valid98(template 4, family 7)과 업체 100(template 3,
  family 17)뿐이고, 모두 결정 54로 그대로 두기로 한 pilot_002의 기존 겹침이거나 결정 15 항목이다. 새 겹침 0.
