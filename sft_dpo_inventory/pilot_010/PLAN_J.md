# pilot_010 PLAN_J — 판정 단계(확인 측정) 계획, 측정 전 고정

결정 267(사용자, 2026-11-18). 이 문서와 `FREEZE_J.json`은 학습 전에, 분석 스크립트와 평가 도구(`FREEZE_J_tools.json`)는 측정 전에 커밋한다.
결과를 본 뒤 지표·기준·셋·seed·채점 규칙을 바꾸지 않는다. 결과가 나빠도 그대로 보고한다. 근거 초안: `PLAN_J_DRAFT.md`(결정 253), `PLAN_J2_DRAFT.md`(결정 262).

**목적**: 투고 원고의 한계("개발 셋(valid98+aux)과 refusal_dev v2는 V4 선택에 쓴 셋이라 V4 수치가 유리하게 치우쳤을 수 있다")를 없애는 확인 수치(추정값, 95% CI).
선택에 쓰지 않은 순서 seed(PLAN_J 예약 seed)와 선택에 쓰지 않은 문항(H-final, protected_final_v2)으로 V4를 한 번 잰다.

## 1. 학습(D2)

- 데이터: `pilot_010/build/V4/full/sft_train.jsonl`(1,984레코드, 파일 sha256 `3575c7f0…`, 질문 목록 sha256 `d559b3e1…`). 다시 빌드하지 않는다. 근접 대조 보강·batch014 없음.
- recipe R1''(1 epoch, lr 2e-4 → 0 linear, batch 1·accum 1, warmup 1, LoRA r16/α32/dropout 0.05·7 모듈, 12,288), 모델 seed 43(`seed`·`data_seed` 43), bf16,
  thinking ON(`enable_thinking: true`, `loss_scope: by_source`), 프롬프트 87048d0c, grounding_target full(코드 지문 791c4a68), `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`.
- wrapper `pilot_007/train/train_b7b.py`(O4' slot 순서, SequentialSampler). 쓰는 checkpoint = epoch 끝 `checkpoint-1984`(lr 0). 25·50·75% 저장분은 쓰지 않는다.
- 순서 seed(PLAN_J 예약) 101·523·2029·31·20271027. 순서 파일 `build/V4/order_b2_o<seed>.json`(`build/make_orders_j.py`: seed 43 재현 바이트 일치, 최대 연속 2 ≤ 4).
  바퀴 1 = 101·523·2029(GPU 3장), 바퀴 2 = 31·20271027(GPU 2장).
- config `train/configs_j/J-V4-o<seed>.yaml`(`train/make_j_configs.py`: `configs_s10/S-V4-o43.yaml`에서 순서 seed·순서 파일·출력만 바꿈, 그 밖 키 같음 검사). CPU dry-run 5개 통과(`configs_j/dryrun.log`).
- 출력 `/data/hwkim/sftdpo_work/pilot_010/train_j/J-V4-o<seed>`. 어댑터는 지우지 않고 커밋하지 않는다(위치·sha256만 기록, 결정 255).
- 학습 실패(OOM·NaN·그 밖 비정상 종료)는 같은 seed·같은 config로 한 번만 다시 한다(실패 출력은 `.failed1`로 옮김). 또 실패하면 그 seed 없이 진행하고 보고한다. 다른 seed로 바꾸지 않는다.

## 2. arm(D3)

| arm | 모델 | seed |
|---|---|---|
| V4 | 위 1절 5개(`J-V4-o<seed>/checkpoint-1984`), LoRA 비병합 | 순서 seed 5 |
| base | Qwen3-8B@b968826d, 같은 Full 프롬프트 | 없음 |
| B2 F | pilot_007 B2 F(거부 목표 없는 SFT) 기존 어댑터 `B2-F-o{43,1016,7,11,2027}/checkpoint-1811`(`/data/hwkim/sftdpo_work/pilot_007/train_b2`) | 순서 seed 5(43·20261016·7·11·2027) |

- B2 F 어댑터 5개의 sha256은 `pilot_007/adapters_B2.json`과 모두 같다(2026-11-18 확인). 평가만 하고 다시 학습하지 않는다.

## 3. 셋(D1)

| 셋 | 문항 | 쓰는 지표 | 파일 |
|---|---:|---|---|
| PF2 = protected_final_v2 | 150 = 거부 50(M 34·P 10·C 6) + 답하는 100(그중 근접 대조 25) | P1·P2·P3 | 원본 `/data/hwkim/sftdpo_work/protected_final_v2/protected_final_v2.xlsx`(sha256 `c7174e71…`, 고정 `protected_final_v2/MANIFEST_PF2_J.json`, 제외 행 0) |
| H-final | 3,000(template_group 160, pool independent 1,332 · vendor100_date_variant 1,668) | P4 | `ablation_012/e2/h_final.yaml`(sha256 `bbc42650…`, 봉인은 이번 한 번만 푼다) |

- refusal_dev v2와 개발 셋(valid98·aux)은 판정에 쓰지 않는다. 시간이 남을 때만 참고로 잰다(7절).
- PF2 평가 gold는 고정 원본에서 변환 도구(`protected_final_v2/convert_pf2_gold.py`, 측정 전 커밋)로 저장소 밖 700 디렉터리에 만든다. 기준일 2026-10-26(명세 8절 변경 2).
  변환 확인: 150문항, 거부 50, 답하는 100문항 모두 gold mock match·`grounding_check` 참, 거부 P·C 문항 gold mock 결과가 명세 형(P unsupported, C needs_clarification)과 같음. 하나라도 아니면 PF2를 재지 않고 보고한다.
- H-final은 기존 셋 그대로(gold_check 3,000/3,000 match, ablation_012).

## 4. 셀(D4)

| 셀 | arm | 셋 | k(회차 seed) | 동시 | 비고 |
|---|---|---|---|---:|---|
| PF-V4-o<seed> | V4 5 | PF2 150 | 4 (20261101–04) | 8 | 잘림 다시 돌리기 없음 |
| PF-base | base | PF2 150 | 8 (20261101–08) | 8 | 같음 |
| PF-B2F-o<seed> | B2 F 5 | PF2 150 | 4 (20261101–04) | 8 | 같음 |
| HF-V4-o<seed> | V4 5 | H-final 3,000 | 1 (20261101) | 32 | H-dev 하네스 |
| HF-base | base | H-final 3,000 | 1 × 2 (20261101·20261102) | 32 | 같음 |
| HF-B2F-o<seed> | B2 F 5 | H-final 3,000 | 1 (20261101) | 32 | 시간이 남을 때만(7절) |

- 경로 = PROTOCOL_v5: vLLM 0.30.0 BF16, flashinfer(attention·sampler), LoRA 비병합(`max_lora_rank` 16), `--max-model-len` 17,408, PROTOCOL_v4 3절 sampling
  (temperature 0.6, top_p 0.95, top_k 20, min_p 0, max_tokens 8192), thinking on. 서버 `ablation_011/gpu/serve_a11.sh`(기존 셀과 같음).
- 호출 seed = `EV.call_seed(S_k, 문항 id, 호출 번호)`, S_k = 20261100 + k(기존 셀 규칙).
- H-final 셀은 H-dev 셀(ablation_012·013)과 같은 실행기 `pilot_006_prep/gpu_data/run_cell6x.py`(`--concurrency 32 --seed-base 20261100 --all-items`)와 같은 client·채점·기준일(2026-09-25).
- PF2 셀은 protected_final_v1 측정(pilot_007 PLAN_FINAL 3절)과 같은 방식: `run_cell6x.py`의 사본이 gold를 저장소 밖에서 읽고 셀 json·원문·실행 출력을
  `/data/hwkim/sftdpo_work/protected_final_v2/{cells,raw,logs}`(700, 파일 600)에만 쓴다. 저장소의 작업 로그에는 정답률·질문·응답이 없다(`--sealed`).
- 한 비교의 셀은 backend(vLLM BF16)·sampler·동시 요청 수가 같다(PF2는 모두 동시 8, H-final은 모두 동시 32).

## 5. 채점

- 거부 판정(`pilot_009/gates/compute_p9.sample_values`와 같음): refused = 결과 상태 ∈ {unsupported, needs_clarification} 그리고 실행된 분석 호출(`get_place_scope` 아닌 호출) 0.
  경로 = M(`error_code` UNSUPPORTED_QUESTION) · C(needs_clarification) · P(그 밖 unsupported).
- PF2 문항 값(표본 하나):
  - 거부 문항: 올바른 거부 = refused.
  - 답하는 문항: 과잉 거부 = refused. 정답 = `grounding_ok`(robust_scoring 패치를 건 `compute_gates` 로더의 `EV.grounding_check`, pilot_006 판정과 같음) 참 그리고 refused 아님
    (pilot_007 PLAN_FINAL 4절 `final_ok`와 같음).
- H-final 문항 값: 정답 = 셀 행 `category == "match"`(H-dev 분석 `ablation_012/analysis/analyze_a12.load_broad`와 같음).
- 문항 값은 셀(seed) 안 k 표본의 평균이다. base는 PF2 k=8 평균, H-final 두 회차 평균.

## 6. 분석(D5) — `results/analyze_j.py`(측정 전 커밋)

- **CI = 계층 bootstrap 10,000회**(결정 253 U1). 반복마다 (1) 문항을 n개 복원 추출하고 같은 번호를 모든 arm에 쓴다(문항 짝 유지),
  (2) seed가 있는 arm(V4·B2 F)은 arm마다 따로 seed를 그 arm의 seed 수만큼 복원 추출한다. 통계량 = 재추출 seed의 (재추출 문항 평균)의 평균. base는 문항만 재추출한다.
  차이 = (arm X 통계량) − (arm Y 통계량). 95% CI = 2.5·97.5 백분위. 점추정 = 원래 seed·문항의 평균(차이).
- rng: 비교(통계량)마다 새 `numpy.random.default_rng(20261109)`(pilot_009·PLAN_J_DRAFT와 같은 값). 한 arm 단독 CI도 같은 방법(seed·문항 재추출).
- **P1 올바른 거부율**(PF2 거부 50): V4 seed 평균, V4 − B2 F, V4 − base(각 CI). 경로(M·P·C)별·M 범주별(6)·P·C별 올바른 거부율 표(arm별, 기술).
- **P2 과잉 거부율**(PF2 답하는 100, 근접 대조 25는 따로): V4, V4 − B2 F, V4 − base.
- **P3 정답률**(PF2 답하는 100): V4, V4 − B2 F, V4 − base.
- **P4 H-final 정답률**: V4 seed별·평균·표준편차·최저, V4 − base(CI), pool별(independent·date_variant)·유형(`category`)별 정답률,
  30문항 이상 template_group 가운데 base보다 20%p·30%p 넘게 낮은 그룹 수(seed별, 보고만; base 그룹 정답률 = 두 회차 평균).
- 함께 보고: 문항당 LLM 호출 수, wall p50·p95, 잘림 호출 수(셀별·arm별), 학습·평가 소요 시간, 서버 오류 행, 개발 셋 기준 기존 수치와 나란히 놓은 표(8절).

## 7. 사전 기준(D5) — 통과·미달을 표시만 한다(미달이어도 수치는 그대로 보고)

| 기준 | 정의 | (c) 없을 때 |
|---|---|---|
| C1 거부 개선 | P1 (V4 − B2 F) 95% CI 하한 > 0 | 판정 불가 |
| C2 거부 비열등 | P1 (V4 − base) 95% CI 하한 ≥ −15%p | — |
| C3 과잉 거부 | P2 답하는 100 (V4 − B2 F) 95% CI 상한 ≤ +3%p | V4 − base로 본다 |
| C4 정답률 | H-final V4 seed 평균 ≥ base(두 회차 평균) + 5%p, 그리고 최저 seed ≥ base | — |

- n은 실제로 학습·측정이 끝난 V4 seed 수다(5, 시간 규칙이면 3). B2 F PF2 셀이 다섯 seed 모두 없으면 있는 seed로 계산하고 그 사실을 적는다.

## 8. 시간 규칙과 순서(D6)

- 보고 마감 2026-11-20 12:00 KST. **바퀴 2 학습(o31·o20271027)은 2026-11-20 05:00 KST(마감 7시간 전) 뒤에는 시작하지 않는다**(스케줄러 `not_after`). 그러면 n = 3으로 판정하고 기록한다.
- 측정 우선순위: V4 PF2 → base PF2 → V4 H-final → base H-final → B2 F PF2 → (남으면) B2 F H-final, 개발 셋·refusal_dev v2(참고, 판정에 안 씀).
- 실행: GPU 3장(UUID `2445b100…`·`a5ce83d0…`·`48f798cc…`), 결정 114(작업 하나 = GPU 하나, 커밋 고정 worktree, `gpu/J/timeline.jsonl`), 규칙 5·6·13
  (학습 전 host UUID·메모리·다른 프로세스·torch UUID, Ollama GPU `48f798cc…`는 `/api/ps`가 빌 때만; 컨테이너가 없으면 server_down = 빔, 컨테이너는 건드리지 않음).
  스케줄러 `gpu/scheduler17.py` = `ablation_013/gpu/scheduler15.py` 사본(새 파일). 다른 점: 기록 위치, 작업별 고정 커밋(`commit`) 허용(평가 도구 커밋에 고정),
  작업별 다시 돌리기 끔(`no_rerun`, PF2), 작업별 시작 기한(`not_after`, 바퀴 2), 작업별 출력 목록(`outputs`, PF2 저장소 밖 셀).
- 순서: 바퀴 1 학습(3장) → 바퀴 2 학습(2장) + 남는 1장에서 base PF2 → base H-final → B2 F PF2 → 바퀴 1 V4 모델 평가(끝나는 대로) → 나머지 평가 → 분석.
  우선순위 숫자는 작업 표(`gpu/J/jobs_j.json`)에 둔다. 새 작업 시작 마감(스케줄러 `--deadline`) 2026-11-20 09:00 KST.

## 9. 무효 측정과 다시 돌리기

- PF2: 잘림은 그대로 채점하고 건수만 보고한다. 다시 돌리기 없음.
- H-final: H-dev 하네스와 같게, 셀이 끝나면 PLAN_S 5절 규칙(잘림 호출 > 1%)을 자동 검사해 같은 seed로 한 번 다시 돌린다(원본은 `cells/J/replaced/`, `RERUNS_J.json`).
  규칙은 정답 여부와 무관하고 결과를 보기 전에 기계가 적용한다. 원본·교체 셀 수를 보고한다.
- 실행 조건 위반(flashinfer 미사용, 장치 확인 실패, 서버 장애, 셀 행 수 부족)으로 무효인 셀은 결과를 보기 전에 이유를 기록하고 처음부터 한 번 다시 잰다(무효 측정의 교체). 또 무효면 멈추고 보고한다.
- 실패 출력은 `ABORTED_`로 남기고 판정·기준선에 쓰지 않는다.

## 10. 계획 변경(명세·초안과 달라진 점)

1. PF2 측정 설계: 명세 2판 1절의 "채택 후보 하나를 base와 k=8로 한 번" → **V4 seed 5개 각각 k=4 + base k=8 + B2 F seed 5개 k=4, seed 평균 비교**(결정 267 D4).
   판정 규칙도 명세 5절(J-c: 정답률 개선 + 거부 비열등)에서 7절 C1–C4로 바뀐다. 명세의 U·조용한 오답·지연 비는 판정에 쓰지 않는다(시간이 남으면 보고만).
2. PLAN_J_DRAFT 2절 조건 1–4(refusal_dev v2·개발 셋)와 후보 seed 규칙은 쓰지 않는다(D1, 후보 하나를 고르지 않음).
3. PLAN_J2_DRAFT 2절 F1–F5 중 F1·F2는 C4로 남고, F3(유형 붕괴)는 보고만(P4), F4·F5는 PF2 기준 C1–C3으로 바뀐다.
4. H-final 다시 돌리기 규칙은 H-dev 하네스를 따른다(9절). PF2에는 쓰지 않는다.
5. PF2 셀 위치: 명세 1판 결정 215 방식(저장소 밖 700). 집계 수치(문항 번호별 값, 문장 없음)만 저장소에 둔다.

## 11. 보고(`results/J_RESULTS.md`, `results/j_judgment.json`)

- 논문 표: 행 = base / B2 F / V4(새 seed), 열 = PF2 올바른 거부율, PF2 과잉 거부율(100·근접 25), PF2 정답률, H-final 정답률. 칸마다 seed 평균과 95% CI, seed별 값.
- P1–P4 차이와 CI, C1–C4 통과 여부, 거부 경로·범주별 표, H-final pool·유형별, 문항당 LLM 호출 수, wall p50·p95, 잘림 수, 학습·평가 소요 시간, 계획과 달라진 점 전부.
- 개발 셋 기준 기존 수치(선택 단계 3 seed: V4 86.48 / 2.17 / 71.81, B2 F 13.17 / 0.98 / 71.04, base 27.96 / 4.44 / 58.05 — refusal_dev v2 올바른 거부 / 과잉 거부 / 개발 셋 정답률)와 나란히 놓은 비교 표.
- PF2 질문 문장·정답 호출·모델 응답은 저장소·보고·대화에 옮기지 않는다. PF2 변환·측정·집계는 `pilot_009/protected_final_v2/access_log.md`에 한 줄씩 적는다.
