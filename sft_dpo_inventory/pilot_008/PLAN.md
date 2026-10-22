# pilot_008 계획(학습 전 고정) — 거부 데이터 반영(RC6), F 순서 seed 5 학습·평가, 단계 판정

결정 221–226(X1–X6). 이 문서와 `FREEZE_008.json`이 학습 시작 전에 커밋된다. 결과를 본 뒤 조건·마진·후보 규칙을 바꾸지 않는다. 최종 판정(protected_final_v2)은 이 단계에서 하지 않는다.

## 1. 데이터(결정 221–223)

- 검토 반영: batch011 100 승인(99 그대로, b011-015 질문 수정 — 재검사 통과), refusal_dev v1 60 승인(58 그대로, rdev-046·048 date `last_year` — 검증 사슬·겹침 통과).
  승인 corpus v4 = v3 630 + batch011 100 = 730(`pilot_006_prep/approved/approved_train_v4.jsonl`, `manifest_v4.json`). refusal_dev 승인본 `refusal_dev/approved/rdev_v1_gold.yaml`(거부 30·대조 30, 개발 셋 — 학습·최종 판정에 쓰지 않음).
- **RC6**(`build/RC6`, `build/build8rc6.py`): 2,005레코드·466질문.

| 구성 | 레코드 | 질문 |
|---|---:|---:|
| RC5 Full 유지(유형 상한 C-1로 기존 14질문 밀림: aug300 5·b010 5·t2pc 4) | 1,743 | 377 |
| r2 근접 대조(J-b011 base 정답 표본, 질문당 상한 4; 표본 없는 11문항 빠짐) | 102 | 29 |
| r1 거부 S-1(base 순수 모델 거부 표본, JSON = `{"unsupported": true}`) | 10 | 5 |
| r1 거부 S-2(`build/refusal_targets8.py` 짧은 중립 근거 + `{"unsupported": true}`) | 150 | 60(S-1과 겹침) |

  거부 160 = **7.98%**(목표 8%: R = round(0.08 × 1,845 / 0.92) = 160, 채움). 질문당 2–4. 손실 범위 모두 json_only(결정 86), 손실 가중 없음 — 거부 손실 token 0.14%(`build/RC6/mask_audit.json`).
  TV(답하는 문항, 개발 분포 대비) 0.090(τ 0.09). 모델 거부 표본이 생긴 범주의 r2: 지표 7/7, 도메인 밖 4/6(b011-095·096은 base 정답 표본이 없어 들어가지 못함).
- 빌드 검사: 12,288 초과 0, 마스크 audit ok(거부 completion = `{"unsupported": true}` + EOS, thinking은 prompt 쪽; S-1 하나는 같은 JSON의 줄바꿈 형식),
  질문 목록 sha256 `build_summary.json`, O4' 순서 파일 5개(43·20261016·7·11·2027) 최대 run 2(≤ 4).

## 2. 학습(결정 224)

- F만, R1''(1 epoch, lr 2e-4 → 0, batch 1·accum 1, warmup 1 step, LoRA r16/α32, max_seq 12,288), 모델 seed 43, RC6, O4' 순서 seed 5 → 5개(`train/configs_p8/P8-F-o*.yaml`,
  B2 F config에서 데이터·순서 파일·출력만 바꿈, `configs_p8/DIFF.md`). wrapper `pilot_007/train/train_b7b.py`.
- dry-run·tokenizer-check 10/10(`configs_p8/dryrun.log`): 2,005 step, 최고 lr 2e-4, 끝 lr 0, 순서 파일 일치, SequentialSampler. lr 합 0.2005(B2 F 0.1811, `configs_p8/lr_check.json`).
- checkpoint는 고르지 않는다 — epoch 끝(`checkpoint-2005`). adapter는 지우지 않고 위치·sha256 기록(커밋 안 함).
- 미리 정한 예외: OOM·NaN은 한 번 다시, 또 실패하면 그 seed를 판정에서 빼고 보고. dry-run 불일치면 그 학습 안 함.

## 3. 평가 셀(`gpu/jobs_main.json`, seed `gpu/cell_seeds_main.json`)

| 셀 | 대상 | 셋 | k |
|---|---|---|---:|
| P8 모델마다 | P8-F-o*(checkpoint-2005) | 주 셋 151, valid98, aux, refusal_dev v1 | 4 |
| B2 F | B2-F-o*(checkpoint-1811) | refusal_dev v1(새로), 주 셋·valid98·aux는 pilot_007 B2 셀 재사용 | 4 |
| base | vLLM-base Full prompt | refusal_dev v1(새로) k=12, 주 셋 k=12/8·valid98·aux k=4는 기존 셀 재사용 | 12 |

- vLLM 0.30.0 BF16, 17,408, 동시 8, PROTOCOL_v4 3절 sampling, 회차 seed S_k = 20261100 + k. 잘림·서버 오류 > 1% 셀은 같은 seed로 한 번만 다시(원본 보관, 결과와 무관하게 교체).
- 스케줄러 `gpu/scheduler10.py` 하나(세 장, `--ollama-uuid` GPU 2), 일정 `gpu/plan_main.json`(약 8h).

## 4. 단계 판정(결정 225, 도구 `gates/compute_p8.py` **커밋 `3bc9749fa09b5c93a1bf4b7fa97f033dedef71d7`**, spec `gates/spec_p8.json`)

실행: `hfvenv/bin/python sft_dpo_inventory/pilot_008/gates/compute_p8.py --spec sft_dpo_inventory/pilot_008/gates/spec_p8.json --out sft_dpo_inventory/pilot_008/results/judgment_p8.json`.

- 표본 값: refused = 결과 상태 ∈ {unsupported, needs_clarification} 그리고 분석 tool 실행 없음; 경로 M(UNSUPPORTED_QUESTION)·C(needs_clarification)·P(그 밖); ok = `compute_gates.load_arm`(견고성 패치 grounding_ok).
- 지표: 올바른 거부율(refusal_dev 거부 30), 과잉 거부율(주 셋 151 + valid98·aux의 답하는 문항 + refusal_dev 대조 30), 정답률(주 셋 151).
- 비교: P8 대 B2 F는 같은 순서 seed 짝, 순서 seed × 문항 계층 bootstrap(`compute_gates_b.hier_ci`, 반복 10,000, `default_rng(20261109)`, 비교마다 새 rng). P8 대 base는 base 문항만 재추출.

| 조건 | 지표 | 기준 |
|---|---|---|
| 1 거부 개선 | 올바른 거부율 P8 − B2 F | CI 하한 > 0 |
| 2 거부 비열등 | 올바른 거부율 P8 − base(k=12) | CI 하한 ≥ −15%p |
| 3 과잉 거부 | 과잉 거부율 P8 − B2 F | CI 상한 ≤ +3%p |
| 4 정답률 비열등 | 주 셋 정답률 P8 − B2 F | CI 하한 ≥ −5%p |

- **넷 모두 통과면 통과.** 불통과이고 CI가 너무 넓으면(반폭 > 마진, 조건 1은 CI가 0을 포함) "판정 불가" 표시, 마진 불변.
- **후보(통과 시)**: seed 단위 거부 비열등(그 seed의 refusal_dev 올바른 거부율 ≥ base 율)을 만족하는 seed 중 개발 셋(valid98 + aux 문항 평균) 정답률 최대, 같으면 seed 숫자가 작은 쪽.
  최종 판정은 protected_final_v2 고정 뒤 따로 지시.
- 보조(판정 아님): 거부 경로 M·P·C, 범주별 올바른 거부율, 개발 셋 정답률, 주 셋 대 base, 대 B2 F dt 누락·구조 오류·U.
- smoke: 기존 셀(B2-F-o11 대 자기 자신, 준비 세션 초안 refusal_dev 셀)로 도구가 돌아 J-rdev 진단값(−15.0 [−30.0, −0.8])을 재현함을 확인했다(판정 아님).

## 5. 보고 형식

RC6 구성·검사, lr 합·순서 연속 길이, seed별 결과표(주 셋·개발 셋·refusal_dev 올바른 거부율·과잉 거부·경로; base·B2 F 함께), 조건 1–4 값·CI·결과, 후보, 진단(C3: M 경로 발생, 범주별,
과잉 거부 유형, S-1·S-2 기여, 정답률 변화 유형), 다시 돌린 셀, GPU 작업 표·사용률·유휴.
