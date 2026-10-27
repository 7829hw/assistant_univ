# pilot_010 선택 단계 계획(학습 전 고정) — 변형 V4·V8 × 순서 seed 3, 사전 등록 선택 규칙

결정 247–255(AB1–AB9). 이 문서와 `FREEZE_S.json`이 학습 시작 전에 커밋된다. 결과를 본 뒤 선택 규칙·T-C2 통과 규칙을 바꾸지 않는다.
판정 단계(새 seed 5) 학습·최종 판정·protected_final_v2 고정·v2 문항 열람·주 셋 평가는 이 단계에서 하지 않는다. Ollama는 T-C2·TEACH-C에만 썼다.

## 1. 데이터(결정 247–250)

- 빌드: `build/build10w.py --variant V4|V8`(build10v에서 RC7 안 순서 하나만 바꾼 2판, 아래), 손실 검사 `build/mask_audit10.py`. 산출 `build/<V>/full/sft_train.jsonl`, `build_summary.json`, `mask_audit.json`, 순서 파일 `order_b2_o{43,20261016,7}.json`.
- 공통: RC7 답하는 레코드 1,834 중 남은 1,280(밀려난 RC7 질문 129개 = 레코드 554) + batch013 8b `json_only` 217(64문항; 8b 정답 표본 없는 문항 12) + 근접 대조 teacher `full_response` 408(질문당 2, 204문항 — 요금 지표 70/93·batch011 r2 31/40·batch012 r2 27/40·batch013 76/77). 유형 상한 C-1 τ 0.09, TV 0.0897, 상한에서 잘린 새 문항 2.

| 변형 | 레코드 | 질문 | RC7 남음 | batch013 8b | 근접 대조 teacher | 거부 | 손실 비중 % 거부 / 근접 대조 teacher / 나머지 | 순서 연속 최대 | 질문 목록 sha256 |
|---|---:|---:|---:|---:|---:|---:|---|---:|---|
| V4 | 1,984 | 494 | 1,280 | 217 (64문항) | 408 (204문항) | 79 (3.98%; S-1 10·teacher 69, 74문항) | 2.24 / 36.79 / 60.98 | 2 | `d559b3e1acca…` |
| V8 | 2,071 | 537 | 1,280 | 217 (64문항) | 408 (204문항) | 166 (8.02%; S-1 10·teacher 156, 117문항) | 4.88 / 35.79 / 59.33 | 2 | `3878a2e79c1e…` |

- 검사(두 변형): 12,288 초과 0, teacher 질문 문장 불일치 0, 순서 파일 3개 연속 길이 ≤ 4(최대 2), mask audit 문제 0(근접 대조 completion = canonical Full JSON), 거부 비율 채움(V4 3.98%·V8 8.02%).
- **빌드 2판(build10w)**: build10v 첫 빌드에서 근접 대조 대상 250 중 180만 남았다(68은 RC7 질문으로 유형 상한에 밀려남, 요금 지표 58/93). 결정 250 "요금 지표 93 포함"과 정지 규칙("상한을 못 채우면 가능한 만큼")에 따라
  C-1(τ·예외·새 문항 먼저)은 두고, 남은 자리를 채울 RC7 질문 순서에서 근접 대조 대상을 먼저 두었다 → 204문항. 나머지 46(요금 지표 23 포함)은 RC7 자리가 남지 않은 칸(집계 있음·dim 있음·dt 없음: 상한 32, 새 문항 34) 등에 있어 채울 수 없다.
  첫 빌드 값: `build/<V>/build_summary_build10v_first.json`·`mask_audit_build10v_first.json`. 학습 전·결과 전 변경이다.
- 밀려난 RC7 질문 129개(레코드 554, 지난 판 RC7 답하는 레코드의 30%)는 대부분 "집계 있음|dim 없음|dt 없음"(새 문항 70)과 "집계 있음|dim 있음|dt 없음"(새 문항 32, RC7 자리 0) 칸이다.
- TEACH-C(결정 249): 250문항 × 8 = 2,000 trace, 통과 1,949, 통과 없는 문항 0, guard 최저 66.0 tok/s(`teacher/teachc_analysis.json`, 읽기 `teacher/TEACH_C2_READ.md` 끌어냄 10/10).

## 2. 학습(결정 251)

- 변형마다 순서 seed 43·20261016·7(o43·o1016·o7) → 6개(`train/configs_s10/S-{V4,V8}-o*.yaml`). config는 P9 config에서 데이터·순서 파일·출력만 바꿨다(`configs_s10/DIFF.md`).
  recipe R1''(1 epoch, lr 2e-4 → 0, batch 1·accum 1, warmup 1 step, LoRA r16/α32, max_seq 12,288), 모델 seed 43, wrapper `pilot_007/train/train_b7b.py`(O4' slot 순서, SequentialSampler).
- 순서 seed "1016"은 pilot_009와 같이 20261016이다(라벨 o1016).
- S-V4-o43: 레코드 = step 1,984, lr 합 0.1984, 마지막 step lr 1.01e-07
- S-V4-o1016: 레코드 = step 1,984, lr 합 0.1984, 마지막 step lr 1.01e-07
- S-V4-o7: 레코드 = step 1,984, lr 합 0.1984, 마지막 step lr 1.01e-07
- S-V8-o43: 레코드 = step 2,071, lr 합 0.2071, 마지막 step lr 9.66e-08
- S-V8-o1016: 레코드 = step 2,071, lr 합 0.2071, 마지막 step lr 9.66e-08
- S-V8-o7: 레코드 = step 2,071, lr 합 0.2071, 마지막 step lr 9.66e-08
- 참고 lr 합: P9-F 0.1993, B2 F 0.1811, P8-F 0.2005. dry-run·tokenizer-check 12/12 exit 0, 순서 파일 일치 12/12(`configs_s10/dryrun.log`, `configs_s10/lr_check.json`).
- checkpoint는 고르지 않는다. epoch 끝(step = 레코드 수)을 쓴다. adapter는 지우지 않고 위치·sha256만 기록한다(커밋 안 함).
- 배치(결정 251): 첫 바퀴 S-V4-o43·S-V8-o43·S-V4-o1016, 둘째 바퀴 S-V8-o1016·S-V4-o7·S-V8-o7(작업 표 우선 숫자 1–6). 작업 하나 = GPU 하나, 학습 중인 GPU에 다른 작업 없음.
- 미리 정한 예외: OOM·NaN이면 한 번 다시 한다. 또 실패하면 그 seed를 선택에서 빼고(`spec_s10.json`의 `excluded_seeds`) 보고한다. dry-run 불일치면 그 학습은 하지 않는다.

## 3. 평가 셀(`gpu/jobs_S2.json`, seed `gpu/cell_seeds_S.json`)

| 셀 | 대상 | 셋 | k |
|---|---|---|---:|
| 변형 모델마다(ES-<V>-<o>) | S-<V>-<o> epoch 끝 checkpoint | refusal_dev v2(거부 90 + 대조 30), valid98, aux | 4 |
| base(있는 셀) | vLLM-base Full prompt | refusal_dev v2 k=12(pilot_009), valid98·aux k=4(pilot_006_prep) | – |
| B2 F(있는 셀) | B2-F-o43·o1016·o7·o11·o2027 checkpoint-1811 | valid98·aux(pilot_007 B2), refusal_dev v2(pilot_009) | 4 |
| P9(보조, 있는 셀) | P9-F 다섯 checkpoint-1993 | valid98·aux·refusal_dev v2(pilot_009) | 4 |

- 주 셋(selection_v2·holdout)은 재지 않는다(판정 단계 셋, 결정 252).
- 측정 경로: vLLM 0.30.0 BF16, 17,408, 동시 8, PROTOCOL_v4 3절 sampling, 회차 seed S_k = 20261100 + k(`run_cell6x.py`) — base·B2 F·P9 셀과 같은 seed.
- 스케줄러 `gpu/scheduler12.py` 하나(세 장, `--ollama-uuid` GPU 2), TEACH-C가 끝나고 `/api/ps`가 빈 뒤 이 작업 표로 새로 시작한다. 일정은 `gpu/plan_S.json`.

## 4. 선택 규칙(결정 252, 도구 `gates/select_s10.py`, spec `gates/spec_s10.json`)

실행: `hfvenv/bin/python sft_dpo_inventory/pilot_010/gates/select_s10.py --spec sft_dpo_inventory/pilot_010/gates/spec_s10.json --out sft_dpo_inventory/pilot_010/results/selection_s10.json`.
smoke: pilot_009 셀(P9을 V4 자리, P8을 V8 자리)로 base 27.96%를 그대로 재현했다(`gates/smoke_s10.json`, B2 F 과잉 거부 0.98% → 상한 3.98%).

- 표본 값: refused = 결과 상태 ∈ {unsupported, needs_clarification} 그리고 분석 tool 실행 없음(`compute_p9.sample_values`), 경로 M(UNSUPPORTED_QUESTION)·C(needs_clarification)·P(그 밖).
  ok = `compute_gates.load_arm`(견고성 패치 grounding_ok).
- 변형 값 = seed마다 문항 평균을 낸 뒤 seed 3개(빠진 seed는 빼고) 평균. 비교는 %p 소수 둘째 자리 반올림 값.

| 규칙 | 지표 | 기준 |
|---|---|---|
| (가) 거부 비열등 | refusal_dev v2 거부 90 올바른 거부율 | ≥ base 27.96%(셀에서 다시 계산) |
| (나) 과잉 거부 | 거부 아닌 문항(valid98·aux 답하는 문항 + refusal_dev 대조 30) 과잉 거부율 | ≤ B2 F(같은 문항, 다섯 seed 평균) + 3%p |
| 고르기 | 개발 셋(valid98 + aux, 문항 수 가중) 정답률 | (가)·(나)를 모두 만족하는 변형 중 높은 쪽. 둘 다 만족하고 차 < 0.5%p면 V4 |

- 둘 다 (가)·(나)를 만족하지 못하면 판정 단계로 가지 않고 보고한다.
- 보조(선택에 쓰지 않음): seed별 값, 거부 경로 M/P/C, 범주별 올바른 거부율(V4·V8·base·B2 F·P9), 요금 지표 문항(정답 호출에 `get_billing_metrics`)의 과잉 거부(P9 비교),
  일 단위 집계 문항(요금 지표 정답 호출에 `aggregation`이 있고 `bucket`이 없음)의 거부 표본 수.

## 5. 다시 돌리기 규칙(지시 2.1, pilot_009와 같음)

- 개발 셋 셀(valid98·aux): 잘림 또는 서버 오류 > 1%면 같은 seed로 한 번만 다시 돌린다.
- refusal_dev v2 셀: 잘림 호출 ≥ 2 또는 서버 오류 행 ≥ 2일 때만.
- 원본은 `cells/replaced_S/`에 보관하고 결과와 무관하게 교체한다(`results/completeness10.py`, `gpu/make_jobs_rerun10.py`, `RERUNS_S.json`).

## 6. 보고 형식

- 변형 구성·손실 비중(거부 / 근접 대조 teacher / 나머지)·밀려난 질문·TV·빌드 검사, lr 합·순서 연속 길이.
- 결과표(변형 × seed): refusal_dev v2 올바른 거부율, 과잉 거부, 개발 셋 정답률, 거부 경로. base·B2 F를 함께.
- 선택 결과와 근거(`results/S_RESULTS.md`, `results/selection_s10.json`).
- 보조 진단: 요금 지표 과잉 거부(P9 비교), 일 단위 집계 문항 거부 수, 범주별 거부율.
- 다시 돌린 셀, GPU 작업 표·사용률·유휴.
