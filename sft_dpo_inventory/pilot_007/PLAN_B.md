# pilot_007 B단계 계획(학습 전 고정) — 같은 순서를 공유한 Full 대 Partial 판정(순서 seed 5개)

결정 194–200(R1–R7). 이 문서와 `FREEZE_B.json`이 학습 시작 전에 커밋된다. 결과를 본 뒤 판정 규칙·마진·셀 구성을 바꾸지 않는다.

## 1. 데이터·recipe(결정 194·195)

- 데이터: RC5 그대로(파일 11개 sha256 = `FREEZE_A3.json`, `session_B_check.txt`). 두 arm은 같은 순서 파일을 쓴다(결정 168, `train/train_b7.py`·`train/order7.py`).
- 순서 seed: 43, 20261016("1016"), 7, 11, 2027. 순서 파일 `build/RC5/order_o{43,20261016,7,11,2027}.json`(o11·o2027은 이번에 같은 도구로 만듦; sha256 앞자리
  893431a5 / 80b99c5b / 77fdacde / 283acba4 / 463726b0). dry-run에서 열 개 모두 `order_file_match` True.
- recipe R1'': 1 epoch, lr 2e-4 → 0 선형, batch 1·accum 1, warmup 1 step, LoRA r16/α32, max_seq_length 12,288, 모델 seed 43, 나머지 A3와 같음
  (`train/configs_b/B-{F,P}-o*.yaml`, A3 R1''-o43과의 차이는 `configs_b/DIFF.md`).
- step·lr 합(dry-run): F 1,811 step·lr 합 0.1811, P 1,775 step·0.1775(P/F 0.980). 평가 checkpoint = 100%(F `checkpoint-1811`, P `checkpoint-1775`).
- 학습 10개 밖의 학습은 하지 않는다. adapter는 지우지 않고 위치·sha256을 `adapters_B.json`에 적으며 커밋하지 않는다(결정 199).

## 2. GPU 작업(결정 196·198, `gpu/jobs_B.json`·`gpu/make_jobs_B.py`)

스케줄러 `gpu/scheduler8.py`(세 장, `--ollama-uuid` = GPU 2 `48f798cc…`, 작업 하나 = GPU 하나, 작업마다 고정 commit의 worktree).

| 우선 | 작업 | 내용 |
|---:|---|---|
| 1 | B-F-o43, B-P-o43, B-F-o1016 | 학습(바퀴 1) |
| 2 | B-P-o1016, B-F-o7, B-P-o7 | 학습(바퀴 2) |
| 3 | B-F-o11, B-P-o11, B-F-o2027 | 학습(바퀴 3) |
| 4 | B-P-o2027 | 학습 |
| 5 | E-B-main_{F,P}-o* (10) | 주 셋 selection_v2 98 + holdout 53, k=4, seed_base 20261100 |
| 6 | E-B-base3 | vLLM-base Full prompt, 주 셋 k=4, **seed_base 20261300**(B1·X2·B2의 20261100과 다른 표본), 바퀴 1 학습 뒤 |
| 7 | E-B-dev_{F,P}-o* (10) | valid98·aux k=4, seed_base 20261100 |
| 8 | L-B | 지연 창: base → F-o43 → P-o43, `pilot_006/latency/latency6.py`(고정 30문항, PROTOCOL_v4 6절), 한 서버·한 GPU, 동시 1. 다른 작업이 모두 끝난 뒤(`notrain` + `done:` 전부), 다른 두 GPU가 빌 때까지 최대 25분 기다린 뒤 시작; 측정 중 30초마다 두 GPU 확인 |

- 셀 sampling seed: `gpu/cell_seeds_B.json`(S1, 실행 전 커밋). 서버: vLLM 0.30.0 BF16, max_model_len 17,408, LoRA 병합 없음(`serve7.sh`).
- GPU 2 작업은 시작 전 `/api/ps` 빔 확인; 모델이 있으면 내리지 않고 다른 GPU부터(결정 191·198). 업체 100·Ollama 측정 없음.

## 3. 판정(결정 197 = 결정 170 그대로)

도구: `gates/compute_gates_b.py` **커밋 `a5e96c6147b9197a576ab5faf2c7bbd2befa3634`** (pilot_006 `gates/compute_gates.py`의 채점·지표·Gate 정의를 그대로 쓰고, CI만 계층 bootstrap).
spec: `gates/gate_spec_B.json`(같은 커밋). 실행: `hfvenv/bin/python sft_dpo_inventory/pilot_007/gates/compute_gates_b.py --spec sft_dpo_inventory/pilot_007/gates/gate_spec_B.json --out sft_dpo_inventory/pilot_007/results/gates_B.json`.

- 주 셋 151(selection_v2 98 + holdout 53). holdout base 천장(83.0)은 한계로 적는다.
- base: selection_v2 = B1 + X2 + B-base3(k=12), holdout = B2 + B-base3(k=8). 결정 196의 "기존 B1·X2와 합쳐"는 selection_v2에 해당한다(holdout에는 B1·X2가 없고 기존 holdout base는 B2).
  세션 3의 BASE3는 쓰지 않는다(지시대로 이번 F·P 평가와 같은 시간대의 새 셀).
- 문항 값 = 셀 k표본 평균. **계층 bootstrap(J1)**: 반복 10,000, 비교마다 새 `numpy.random.default_rng(20261109)`; 한 반복에서 순서 seed S개와 문항 n개를 각각 복원 추출,
  P − F는 같은 순서 seed끼리 짝. 95% CI = 2.5·97.5 백분위.
- 선행 조건(arm마다 대 base): 정답률 차 CI 하한 > 0, U 차 CI 하한 ≤ 0(같은 계층 방식, base는 문항만 재추출).
- Gate A: P − F 정답률 CI 하한 ≥ −5%p. 불통과이고 반폭 > 5%p면 "판정 불가"로 그대로 보고(마진 불변).
- Gate B: dt_missing P − F CI 하한 ≤ 0. Gate C: 조용한 오답 P − F CI 하한 ≤ 0.
- Gate D(결정 153): (1) MM+NM P − F CI 하한 ≤ 0 그리고 (2) 구조 오류·grounding failure·repair 중 하나 이상 P − F CI 상한 < 0.
- Gate E(결정 154): (1) 지연 비(o43 모델 / base) F·P 모두 ≤ 1.5 (2) JSON token 중앙값 P ≤ 0.7·F (3) 생성 token 중앙값 P ≤ F(다섯 seed 문항 값 모두).
- 채택: 선행 F·P와 Gate A–E 모두 통과 → **P 채택 후보**; 아니고 F가 선행 통과 → **F 채택 후보**; 그 밖은 후보 없음. 채택 후보 대 base 최종 판정(protected_final_v1)은 이번 단계에서 하지 않는다.
- 보조(판정에 쓰지 않음): J2(순서 seed마다 P − F 방향이 모두 같은지), arm별 seed sd, 결정 140 family 진단 부분집합(spec의 두 목록), 개발 셋(valid98·aux, 같은 계층 bootstrap).
- 미리 정한 예외: 학습 OOM·NaN은 한 번 다시 돌리고, 또 실패하면 그 순서 seed의 F·P 짝을 spec에서 빼고 남은 seed로 판정(빠진 seed와 이유 보고). dry-run 불일치면 그 학습을 건너뜀(같은 규칙).
  셀에서 잘림 또는 서버 오류가 1% 넘으면 그 셀을 다시 돌린다(교체, 기록).

## 4. 공개 순서(결정 200, R7)

- `protected_final_v1` 고정 확인(셋 다): `sft_dpo_inventory/pilot_006/protected_final/manifest_v1.json`이 원격에 커밋됨, 그 manifest의 sha256 = 서버 파일 sha256, validate.py `ok: true`.
- 확인 전: 평가 셀의 정답률·U·gate 값을 계산·출력·커밋하지 않는다. `compute_gates_b`·요약 표·그래프를 만들지 않는다. 허용은 완료성(셀 파일 존재·줄 수·sha256, 잘림 건수, 서버 오류)뿐.
- 세션 끝까지 확인되지 않으면 "판정 대기"로 완료성만 보고하고 멈춘다. 확인되면 3절 명령 한 번으로 계산하고 `results/B_RESULTS.md`에 적는다.

## 5. 보고 형식(확인 뒤)

선행 조건 표(arm × ok·U 차, CI), Gate A–E 표(값·CI·반폭·통과), 채택 후보, J2·seed sd, 순서 seed별 P − F, 진단 부분집합, 개발 셋, 학습(step·lr 합·loss·시간)·GPU 사용률.
