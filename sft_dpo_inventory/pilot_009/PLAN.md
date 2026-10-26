# pilot_009 계획(학습 전 고정) — RC7(teacher 거부 추론), F 순서 seed 5 학습·평가, 단계 판정

결정 233–240(Z1–Z8). 이 문서와 `FREEZE_009.json`이 학습 시작 전에 커밋된다. 결과를 본 뒤 조건·마진·후보 규칙을 바꾸지 않는다.
최종 판정, protected_final_v2 고정, v2 문항 작성·열람은 이 단계에서 하지 않는다. Ollama는 쓰지 않는다.

## 1. 데이터(결정 233–235)

- 검토 반영(`review/apply9.py`, `review/apply9_checks.json`):
  - batch012 100 승인(97 그대로, b012-001·021·039 질문 수정, 재검사 통과, 최대 Jaccard 0.216).
  - 승인 corpus v5 = v4 730 + batch012 100 = 830(`pilot_006_prep/approved/approved_train_v5.jsonl`, `manifest_v5.json`).
  - refusal_dev v2 승인본 120 = 거부 90(v1 30 + 확장 60) + 대조 30(`refusal_dev2/approved/rdev_v2_gold.yaml`). 개발 셋이며 학습·최종 판정에 쓰지 않는다.
- teacher 거르기(`build/teacher_filter9.py`, 규칙과 테스트는 실행 전 커밋 `adc74a1`, 결과는 `build/teacher_filter9.json`):
  - 절 이름은 지시 파일에서 한 줄 전체가 `[이름]`인 줄의 이름이다.
  - 그중 학생 Full system prompt에 같은 글자로 있는 이름은 허용한다. 거부 지시에서는 "출력"만 허용된다.
  - 금지 이름: 거부 지시의 "분석으로 답할 수 있는 것"·"사용자 메시지", v3b의 "판단할 다섯 가지"·"확정된 결론을 받을 때".
  - 금지 이름이 생각에 있는 trace는 통째로 뺀다(괄호 유무 무관).
  - 결과: 거부 통과 938에서 586이 빠졌다. 질문을 고친 3문항의 23은 원래 질문을 인용하므로 쓰지 않는다.
  - 남은 trace가 0인 20질문은 금지 이름이 든 줄만 지워 보완했다. 결정 185 c2 방식(손실 조건 같음)이고, 모두 손실 없이 재검사를 통과했다.
  - 쓸 수 있는 거부 trace는 117질문 487개다. r2 v3b 통과 32에는 인용이 없다.
- **RC7**(`build/build9rc7.py`, `build/RC7`): 1,993레코드·526질문, 질문 목록 sha256 `d4b44b7b…`.

| 구성 | 레코드 | 질문 |
|---|---:|---:|
| RC6 답하는 레코드 유지(유형 상한 C-1로 기존 32질문·136레코드 밀림: aug300 10·b010 6·pg 5·t2pc 5·b011 4·b009 2) | 1,709 | 374 |
| r2 batch012(J-b012 base 정답 표본, 질문당 ≤ 4) | 103 | 27 |
| r2 batch011 teacher(TEACH-R v3b 통과, c2·절 이름 거르기, `full_response`, 질문당 ≤ 4) | 22 | 8 |
| 거부 S-1(J-b011 base 순수 모델 거부, `json_only`) | 10 | 5 |
| 거부 teacher(TEACH-R 거부 trace, `full_response`, 질문당 합 ≤ 4로 고르게) | 149 | 113 |

- 거부 질문은 117이다(S-1 5 ∪ teacher 113). 374 + 27 + 8 + 117 = 526.
- 거부 레코드 159 = **7.98%**(R = round(0.08 × 1,834 / 0.92) = 159, 다 채움).
  - 질문당 레코드: 1개 78, 2개 37, 3개 1, 4개 1, 0개 3. 0개인 3은 질문을 고친 b012-001·021·039로, 원래 질문으로 모은 trace·표본이라 쓰지 않았다.
  - S-2는 쓰지 않았다. batch012 S-1은 0이다. J-b012의 모델 거부 7표본은 모두 `"unsupported": true`가 섞인 더 큰 JSON이라, 정확히 `{"unsupported": true}`가 아니었다.
- 빠진 r2:
  - batch012 base 정답 표본이 없는 11과, 정답 표본이 계약 검사(`target_ok`)에서 모두 빠진 2(b012-064·090)가 빠졌다(결정 235 규칙과 RC6 빌드 규칙).
  - b011-089·090·091도 빠졌다.
- teacher 레코드 878/1,993 = **44.05%**.
- 손실 token(`build/RC7/mask_audit.json`):
  - teacher 손실 68.84%(RC6 67.2%).
  - **거부 손실 6.05%**(RC6 0.14%). 그중 teacher 거부는 레코드당 중앙값 286 token, S-1은 6이다.
- TV 0.0896(τ 0.09).
- 빌드 검사:
  - 12,288 초과 0, teacher 레코드 질문 = TEACH-R 대상 질문.
  - 마스크 audit ok: 거부 teacher completion = `<think>…</think>` + `{"unsupported": true}` + EOS, S-1은 JSON만.
  - O4' 순서 파일 5개(43·20261016·7·11·2027)는 모두 최대 run 2(≤ 4).

## 2. 학습(결정 236)

- F만 학습한다.
  - recipe: R1''(1 epoch, lr 2e-4 → 0, batch 1·accum 1, warmup 1 step, LoRA r16/α32, max_seq 12,288).
  - 모델 seed 43, 데이터 RC7, O4' 순서 seed 5개 → 학습 5개(`train/configs_p9/P9-F-o*.yaml`).
  - config는 B2 F config에서 데이터·순서 파일·출력만 바꿨다(`configs_p9/DIFF.md`). wrapper는 `pilot_007/train/train_b7b.py`.
- dry-run·tokenizer-check 10/10 통과(`configs_p9/dryrun.log`):
  - 1,993 step, 최고 lr 2e-4, 끝 lr 0, 순서 파일 일치, SequentialSampler.
  - lr 합 0.1993(B2 F 0.1811, P8 0.2005, `configs_p9/lr_check.json`).
- checkpoint는 고르지 않는다. epoch 끝 `checkpoint-1993`을 쓴다. adapter는 지우지 않고 위치와 sha256만 기록한다(커밋 안 함).
- 미리 정한 예외:
  - OOM이나 NaN이면 한 번 다시 한다. 또 실패하면 그 seed를 판정에서 빼고 보고한다.
  - dry-run이 불일치면 그 학습은 하지 않는다.

## 3. 평가 셀(`gpu/jobs_main.json`, seed `gpu/cell_seeds_main.json`)

| 셀 | 대상 | 셋 | k |
|---|---|---|---:|
| P9 모델마다 | P9-F-o*(checkpoint-1993) | 주 셋 151(selection_v2 98 + holdout 53), valid98, aux, refusal_dev v2 | 4 |
| B2 F | B2-F-o*(checkpoint-1811) | refusal_dev v2(새로). 주 셋·valid98·aux는 pilot_007 B2 셀 재사용 | 4 |
| P8(보조) | P8-F-o*(checkpoint-2005) | refusal_dev v2(새로). 주 셋·valid98·aux는 pilot_008 셀 재사용 | 4 |
| base | vLLM-base Full prompt | refusal_dev v2(새로) k=12. 주 셋 k=12/8·valid98·aux k=4는 pilot_008 판정과 같은 기존 셀 | 12 |

- 측정 경로: vLLM 0.30.0 BF16, 17,408, 동시 8, PROTOCOL_v4 3절 sampling, 회차 seed S_k = 20261100 + k(`run_cell6x.py`).
- 스케줄러는 `gpu/scheduler11.py` 하나(세 장, `--ollama-uuid` GPU 2)다. 일정은 `gpu/plan_main.json`(약 10h).
  - 우선 1: 학습 5. 우선 2: base·B2 F·P8의 refusal_dev v2. 우선 3: P9 평가(해당 학습 끝).
  - 작업 하나 = GPU 하나이고, 학습 중인 GPU에는 다른 작업을 올리지 않는다. GPU 2 작업 전에는 `/api/ps`를 확인한다.

## 4. 단계 판정(결정 237)

도구는 `gates/compute_p9.py`, spec은 `gates/spec_p9.json`이다. 도구 커밋은 FREEZE_009에 기록한다.
`pilot_008/gates/compute_p8.py`의 사본이고, 판정 규칙과 bootstrap은 같다. smoke: pilot_008 셀로 pilot_008 판정값을 그대로 재현했다(`gates/smoke_p8cells.json`).

실행: `hfvenv/bin/python sft_dpo_inventory/pilot_009/gates/compute_p9.py --spec sft_dpo_inventory/pilot_009/gates/spec_p9.json --out sft_dpo_inventory/pilot_009/results/judgment_p9.json`.

- 표본 값:
  - refused = 결과 상태 ∈ {unsupported, needs_clarification} 그리고 분석 tool 실행 없음.
  - 경로: M(UNSUPPORTED_QUESTION), C(needs_clarification), P(그 밖).
  - ok = `compute_gates.load_arm`(견고성 패치 grounding_ok).
- 지표:
  - 올바른 거부율: refusal_dev v2 거부 90.
  - 과잉 거부율: 주 셋 151 + valid98·aux의 답하는 문항 + refusal_dev 대조 30.
  - 정답률: 주 셋 151.
  - 개발 셋: valid98 + aux 문항(문항 수 가중).
- 비교:
  - P9 대 B2 F(그리고 보조 P8)는 같은 순서 seed끼리 짝짓는다. CI는 순서 seed × 문항 계층 bootstrap(`compute_gates_b.hier_ci`, 결정 170 방식, 반복 10,000, `default_rng(20261109)`, 비교마다 새 rng)으로 낸다.
  - P9 대 base는 base 문항만 재추출한다.

| 조건 | 지표 | 기준 |
|---|---|---|
| 1 거부 개선 | 올바른 거부율 P9 − B2 F | CI 하한 > 0 |
| 2 거부 비열등 | 올바른 거부율 P9 − base(k=12) | CI 하한 ≥ −15%p |
| 3 과잉 거부 | 과잉 거부율 P9 − B2 F | CI 상한 ≤ +3%p |
| 4 정답률 비열등 | 주 셋 정답률 P9 − B2 F | CI 하한 ≥ −5%p |

- **넷 모두 통과면 통과다.** 불통과인데 CI가 너무 넓으면 "판정 불가"로 표시한다. 기준은 반폭 > 마진이고, 조건 1은 CI가 0을 포함할 때다. 마진은 바꾸지 않는다.
- **후보(통과 시)**:
  - seed 단위로 refusal_dev v2 올바른 거부율 ≥ base 율인 seed만 대상이다.
  - 그 가운데 개발 셋(valid98 + aux, 문항 수 가중) 정답률이 가장 높은 seed를 고르고, 같으면 seed 숫자가 작은 쪽을 고른다.
  - 최종 판정은 protected_final_v2 고정 뒤 따로 지시를 받아 한다.
- 보조(판정 아님):
  - `compute_p9.py`가 내는 것: P8 대비 같은 지표(P9 − P8, 같은 seed 짝), 거부 경로 M·P·C, 범주별 올바른 거부율(P9·B2 F·P8·base), 개발 셋 정답률, 주 셋 대 base, 대 B2 F의 dt 누락·구조 오류·U.
  - C3 진단 도구(`analysis/diag_p9.py`, 결과 전 정의)가 내는 것: thinking 안 지시문 인용과 "결론"류 문장 비율.
    - 대상: refusal_dev v2와 주 셋 표본 원문(P9·P8·B2 F·base).
    - 지시문 인용: 생각(`</think>` 앞)에 1절 금지 절 이름이 있는 표본 비율.
    - "결론"류 문장: 생각에 `teacher_refusal9.CONCL_LINE`에 맞는 줄("결론: …")이 있는 표본 비율.
    - 셋별·모델별로 낸다. 과잉 거부 문항 유형도 함께 낸다.

## 5. 다시 돌리기 규칙(지시 2.1)

- 주 셋·개발 셋 셀: 잘림 또는 서버 오류가 1%를 넘으면 같은 seed로 한 번만 다시 돌린다.
- refusal_dev v2 셀: 호출 수가 적어 1%를 쉽게 넘으므로, 잘림 호출 ≥ 2 또는 서버 오류 행 ≥ 2일 때만 다시 돌린다.
- 원본은 `cells/replaced_main/`에 보관하고, 결과와 무관하게 교체한다(`results/completeness9.py`, `gpu/make_jobs_rerun9.py`, `RERUNS_main.json`).

## 6. 보고 형식

- RC7 구성·검사, teacher 거르기 결과, lr 합·순서 연속 길이
- seed별 결과표: 주 셋, 개발 셋, refusal_dev v2 올바른 거부율, 과잉 거부, 경로. base·B2 F·P8을 함께 적는다.
- 조건 1–4의 값·CI·결과와 후보
- 진단(C3): 경로, 범주별, seed 간 퍼짐(P8과 비교), thinking 지시문 인용·"결론"류 비율, 과잉 거부 문항 유형
- 다시 돌린 셀, GPU 작업 표·사용률·유휴
