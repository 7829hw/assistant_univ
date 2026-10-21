# pilot_007 B2단계 계획(학습 전 고정) — 질문을 섞은 공유 순서(O4')로 Full 대 Partial 재비교(순서 seed 5개)

결정 205–210(U1–U6). 이 문서와 `FREEZE_B2.json`이 학습 시작 전에 커밋된다. 결과를 본 뒤 판정 규칙·마진·채택 규칙·셀 구성을 바꾸지 않는다.

## 0. B단계와의 관계(결정 205)

- B단계 판정("채택 후보 없음", `PLAN_B.md`·`FREEZE_B.json`·`results/B_RESULTS.md`)은 기록으로 남는다. 고치거나 다시 계산하지 않는다.
- B2단계는 B단계 결과를 본 뒤 새로 사전 등록하는 판정이다. 이유: B단계 순서(O4, 결정 168)가 한 질문의 레코드를 연달아 놓았고(평균 run 4.6, 최대 8), 그 순서에서 F가 A3(무작위 순서)보다
  크게 낮았다(같은 seed 주 셋 o1016 81.79 → 65.23). 질문 단위 배치는 결정 168 규칙 문구를 그대로 구현한 결과다.
- 바뀌는 것은 순서(O4 → O4')와, 그에 따른 wrapper·config 키·작업 ID뿐이다. 데이터·recipe·평가 셀 설정·base 셀·판정 도구·판정 규칙은 B단계와 같다.

## 1. 순서(결정 206 O4')

- slot: arm마다 한 질문 안 레코드를 `order7.within_key`(teacher `trace_id` 순 → 8b `trace_sha256` 순, O4 규칙) 순으로 놓고 k = 0, 1, 2, …; 키 = (질문 id, k).
- 두 arm slot 키 합집합(1,811개)을 정렬한 뒤 `numpy.random.default_rng(순서 seed).permutation`으로 한 번 섞는다. 각 arm은 그 순열에서 자기 slot만 차례로 쓴다.
- 도구: `train/order7b.py`(새 파일, order7은 고치지 않음), `train/make_order7b.py` → `build/RC5/order_b2_o{43,20261016,7,11,2027}.json`, 시험 `tests/test_order7b.py`.
- 학습: `train/train_b7b.py`(train_b7 사본, 순서 부분만 order7b) — 순서 파일 seed·순열 재현·arm slot 순서 sha256을 확인하고 `SequentialSampler`로 trainer 쪽 섞기를 끈다.
- 학습 전 확인(`build/RC5/run_length_B2.json`, `train/configs_b2/dryrun.log`):

| 순서 seed | order sha256 | 질문 목록 sha256(두 arm) | 공통 slot 상대 순서 | 최대 run F / P | 평균 run F / P |
|---|---|---|---|---|---|
| 43 | 38a60d2e… | 22406d92…(같음) | 같음 | 2 / 2 | 1.0039 / 1.0040 |
| 20261016 | 426be368… | 같음 | 같음 | 2 / 2 | 1.0011 / 1.0023 |
| 7 | b1b02907… | 같음 | 같음 | 2 / 2 | 1.0017 / 1.0028 |
| 11 | de3d43de… | 같음 | 같음 | 2 / 2 | 1.0050 / 1.0034 |
| 2027 | 2dab9c37… | 같음 | 같음 | 2 / 2 | 1.0017 / 1.0011 |

  비교: A3 무작위 순서(F, accelerate SeedableRandomSampler 재현) 최대 2, 평균 1.0017–1.0033; B단계 O4 최대 8, 평균 F 4.63 / P 4.54(run ≥ 2 비율 93–94%).
  최대 run > 4인 seed 없음 → 다섯 seed 모두 학습.

## 2. 데이터·recipe(결정 207)

- RC5 그대로(파일 11개 sha256 = `FREEZE_A3.json`, `session_B2_check.txt`). R1'' 그대로: 1 epoch, lr 2e-4 → 0 선형, batch 1·accum 1, warmup 1 step, LoRA r16/α32, max_seq_length 12,288, 모델 seed 43.
- config: `train/configs_b2/B2-{F,P}-o*.yaml`(B config에서 순서 키·출력만 바꿈, `configs_b2/DIFF.md`). F 1,811 step·lr 합 0.1811, P 1,775 step·0.1775(P/F 0.9801, `configs_b2/lr_check.json`).
- 평가 checkpoint = 100%(F `checkpoint-1811`, P `checkpoint-1775`). adapter는 지우지 않고 `adapters_B2.json`에 위치·sha256(커밋 안 함, 결정 210).

## 3. GPU 작업(결정 208·210, `gpu/jobs_B2.json`·`gpu/make_jobs_B2.py`, 일정 `gpu/plan_B2.json`)

스케줄러 `gpu/scheduler8.py` 하나(세 장, `--ollama-uuid` = GPU 2 `48f798cc…`, 작업 하나 = GPU 하나, 고정 commit worktree).

| 우선 | 작업 | 내용 |
|---:|---|---|
| 1 | B2-F-o43, B2-P-o43, B2-F-o1016 | 학습(바퀴 1) |
| 2 | B2-P-o1016, B2-F-o7, B2-P-o7 | 학습(바퀴 2) |
| 3 | B2-F-o11, B2-P-o11, B2-F-o2027 | 학습(바퀴 3) |
| 4 | B2-P-o2027 | 학습 |
| 5 | E-B2-main_{F,P}-o* (10) | 주 셋 selection_v2 98 + holdout 53, k=4, seed_base 20261100 |
| 7 | E-B2-dev_{F,P}-o* (10) | valid98·aux k=4, seed_base 20261100 |
| 8 | L-B2 | 지연 창 base → F-o43 → P-o43(`latency6.py`, 고정 30문항, 한 GPU, 동시 1), 다른 작업이 모두 끝난 뒤 다른 두 GPU가 빌 때까지 최대 25분 기다린 뒤 |

- 셀 sampling seed: `gpu/cell_seeds_B2.json`(S2, 실행 전 커밋). base 셀은 새로 재지 않는다.
- 셀 잘림·서버 오류 > 1%면 그 셀만 같은 seed로 한 번 다시 돌리고 결과와 무관하게 교체, 원본은 `cells/replaced_B2/`(`B_RERUNS.md` 방법, `gpu/make_jobs_B2_rerun.py`, 주 큐가 끝난 뒤).
- GPU 2 작업 전 `/api/ps` 빔 확인. 업체 100·Ollama·protected_final_v1 쓰지 않음.

## 4. 판정(결정 209 = PLAN_B 3절 그대로)

도구: `gates/compute_gates_b.py` **커밋 `a5e96c6147b9197a576ab5faf2c7bbd2befa3634`**(B단계와 같음, 고친 것 없음). spec: `gates/gate_spec_B2.json`(`gpu/make_jobs_B2.py`가 만듦, 이 계획과 함께 고정).
실행: `hfvenv/bin/python sft_dpo_inventory/pilot_007/gates/compute_gates_b.py --spec sft_dpo_inventory/pilot_007/gates/gate_spec_B2.json --out sft_dpo_inventory/pilot_007/results/gates_B2.json`.

- 주 셋 151. base: selection_v2 = B1 + X2 + B-base3(k=12), holdout = B2 + B-base3(k=8) — B단계 판정과 같은 셀.
- 계층 bootstrap(J1): 반복 10,000, 비교마다 새 `numpy.random.default_rng(20261109)`, 순서 seed S개와 문항 n개를 각각 복원 추출, P − F는 같은 순서 seed끼리 짝, 95% CI = 2.5·97.5 백분위.
- 선행 조건(arm마다 대 base): 정답률 차 CI 하한 > 0, U 차 CI 하한 ≤ 0.
- Gate A: P − F 정답률 CI 하한 ≥ −5%p(불통과이고 반폭 > 5%p면 "판정 불가"로 그대로 보고, 마진 불변). Gate B: dt_missing P − F 하한 ≤ 0. Gate C: 조용한 오답 P − F 하한 ≤ 0.
  Gate D(결정 153): (1) MM+NM P − F 하한 ≤ 0 그리고 (2) 구조 오류·grounding failure·repair 중 하나 이상 P − F 상한 < 0.
  Gate E(결정 154): (1) 지연 비(o43 / base) F·P ≤ 1.5 (2) JSON token 중앙값 P ≤ 0.7·F (3) 생성 token 중앙값 P ≤ F.
- **채택(결정 209, 도구의 현재 해석)**: F·P 둘 다 선행 통과 그리고 Gate A–E 모두 통과 → **P 채택 후보**. F가 선행 불통과면 F 대 P는 해석하지 않고 P도 채택하지 않는다.
  P가 채택되지 않고 F가 선행 통과 → **F 채택 후보**. 그 밖은 후보 없음.
- 보조: J2(순서 seed마다 P − F 방향 일치), arm별 seed sd, 결정 140 family(spec 두 목록) 별도, 개발 셋(같은 계층 bootstrap).
- 예상 반폭(Gate A, S = 5): A3 sd 2.50 가정 4.34–4.86(결정 190), B단계 실제 6.85(F sd 5.24·P 3.44). B2의 sd가 A3에 가까우면 5%p 안, B에 가까우면 넘을 수 있다.
- 미리 정한 예외: 학습 OOM·NaN은 한 번 다시, 또 실패하면 그 순서 seed의 F·P 짝을 spec에서 빼고 남은 seed로 판정(보고). 순서·dry-run 확인 불일치면 그 seed 학습 안 함(같은 규칙).
- 최종 판정(protected_final_v1, 채택 후보 대 base)은 이 단계에서 하지 않는다 — 후보가 나오면 절차만 제안.

## 5. 보고 형식

순서 확인 표, 주 셋 표(모델·seed별 정답률·U·dt 누락, base), 선행 조건·Gate A–E 표(값·CI·반폭·통과), 채택 결과, J2·seed sd·예상 대 실제 반폭, family, 개발 셋, 지연 창, 진단(A3·B·B2 같은 seed),
다시 돌린 셀과 영향, GPU 작업 표·사용률·10분 넘는 유휴.
