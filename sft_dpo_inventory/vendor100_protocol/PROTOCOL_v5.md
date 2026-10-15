# 업체 100 평가 절차 v5 (pilot_005) — **확정(2026-10-15, 사용자)**

작성: 2026-10-15(결정 101–105). 상태: **확정(2026-10-15, 사용자; 결정 101–105).** 학습 변형 셋과 후보 7개(결정 101·102), 여러 후보에서 고르는 데 대한
Bonferroni 보정과 고르는 방법(결정 103), GPU 사용(결정 105)을 반영했다.

- PROTOCOL_v4(확정 2026-10-14, sha256 `9e75c2a63d17def9f82525392e72bd2a291593b71451c79a96925e7075a2d7b1`)를 이어받는다. 아래에서 바꾼 것만 다르고,
  나머지는 v4 원문(그리고 v4가 이어받은 v3 원문)이 우선한다.
- v1–v4, `ADDENDUM_three_way.md`는 고치지 않는다. 확정한 뒤에는 이 문서를 고치지 않고, 바꿔야 하면 새 판을 만든다.
- 근거 자료: `../pilot_004/REPORT.md`, `../pilot_004/selection_sft.json`, `../pilot_004/selection_dpo.json`.

## 1. 바뀌는 것

| 항목 | v4 | v5 |
|---|---|---|
| 학습 | SFT 1개 → 고른 SFT에서 DPO 1개(순서대로, GPU 1장) | **변형 셋(V1, V2, V3)을 GPU 3장에서 동시에**(결정 101·105). 데이터는 pilot_004와 같은 판 |
| 후보 | 단계마다 checkpoint 2개, SFT에서 1개 고르고 DPO에서 1개 고름 | **후보 7개를 미리 고정**(결정 102): V1 2개, V2 2개, V3 2개, pilot_004 SFT 934 |
| 고르는 방법 | 평균 정답률 최대, 같으면 U 낮은 것, 그다음 늦은 step | **U 조건을 만족한 후보 중 평균 정답률 최대**, 같으면 U 낮은 것, 그다음 **학습 step이 적은 것**(결정 103, 3절) |
| 중단 규칙 | 고른 checkpoint의 정답률 차이 95% CI 하한 > 0 그리고 U 차이 95% CI 하한 ≤ 0 | **정답률 차이의 99.29% CI(양측, 1 − 0.05/7) 하한 > 0**(bootstrap 20,000회) 그리고 **U 차이 95% CI 하한 ≤ 0(보정 없음)**(결정 103, 4절) |
| 평가 GPU | 학습이 끝난 뒤 서버 3개 | **학습이 끝나 비는 GPU부터** 평가에 쓴다. 한 서버에 LoRA 여러 개를 함께 올릴 수 있다(결정 105) |

그대로인 것: 셋(v4 2절), 정밀도 BF16(v4 4절), vLLM 0.30.0·flashinfer attention과 sampler·서버 인자·sampling·seed 규칙·입력(v4 3절), 동시 요청 8,
k(선택 4, 업체 100 8, aux 4, valid98 4, 27b 4), 판정 지표·규칙(v4 6절, 업체 100 판정은 **보정 없이** 그대로), 업체 100 셀과 참고 셀 E·27b(v4 5절),
vicinity 감시(v4 7절), 결정 55 guard, 업체 100·aux_test_v1은 평가 전용, 재측정 규칙(v4 3절).

## 2. 학습 변형과 후보(결정 101·102)

데이터: `training/generated/thinking_pilot004_t2pc`(pilot_004와 같은 판, 같은 sha256). 변형마다 학습 설정은 아래에 적은 것만 pilot_004 config와 다르다.
설정 파일, seed, 예상 step은 pilot_005 `PLAN.md`에 고정한다.

| 변형 | 출발 | pilot_004와 다른 것 | 저장 시점(후보) |
|---|---|---|---|
| V1 | base Qwen3-8B@b968826d(새 LoRA) | SFT, **seed만 다름**(2 epoch) | epoch 1, epoch 2 |
| V2 | base Qwen3-8B@b968826d(새 LoRA) | SFT, **3 epoch**(학습률 스케줄은 3 epoch 길이로 선형 감소) | epoch 2, epoch 3 |
| V3 | pilot_004 SFT checkpoint-934(reference는 그 SFT, 미리 계산) | DPO, **학습률 절반(5e-6)**, **학습 길이 절반(0.5 epoch)** | 자기 학습 길이의 50%, 100% |
| (기존) | – | pilot_004 SFT checkpoint-934(새로 학습하지 않음) | – |

- 후보 수 **m = 7**로 고정한다. 학습이 실패한 변형이 있어도 보정의 m은 7이다(결정 102). 실패한 변형의 후보는 표에 "없음(학습 실패)"으로 남긴다.
- 학습 step(고르는 방법의 마지막 동점 기준)은 **base에서부터 센 누적 optimizer step**이다. V1·V2는 자기 step, V3은 934(출발 SFT) + 자기 step, SFT 934는 934.
- 학습 중 메모리 부족 등 외부 요인으로 멈춘 변형은 장애로 기록하고 그 변형만 처음부터 다시 돌린다(결정 105). 멈춘 출력은 `ABORTED_*`로 남기고 쓰지 않는다.

## 3. 후보 평가와 고르는 방법(결정 103)

- 셋과 조건: selection_v2(98문항), k=4, v4 3절의 vLLM BF16·flashinfer·LoRA(병합하지 않음)·sampling·seed 규칙, **동시 요청 8**. 한 서버에는 한 번에 셀 하나만 돌린다.
- 기준값(vLLM-base): v4 5절과 같이 pilot_prep_007 `../serving_vllm_fp8/runs/vllm-bf16-base_s1–4.json`을 다시 쓴다.
- **pilot_004 SFT 934의 기록은 다시 쓴다**(`../pilot_004/selection/runs/sft_step934_s1–4.json`, 원문 `training/generated/pilot_004/raw`). 근거:
  - 같은 vLLM 0.30.0, flashinfer 0.6.18.post1, torch 2.13.0+cu130, transformers 5.19.0(셀 meta와 2026-10-15의 venv가 같다), BF16, flashinfer attention과 sampler(서버 로그 확인),
    동시 요청 8, 같은 sampling 값(요청 로그 1종), 같은 seed 규칙, selection_v2 98문항, 코드 지문 `791c4a68`, prompt `87048d0c`.
  - 다른 점은 서버에 함께 올라 있던 adapter(pilot_004에서는 467·934 두 개, `--max-loras 2`)와 GPU다. 요청마다 자기 LoRA만 쓰고, 결정 93·100·105로 장치 일치를
    요구하지 않으며 vLLM 표본은 어차피 바이트 재현되지 않는다. 그래서 새 후보 6개와 같은 조건의 셀로 본다.
  - 위 조건 가운데 하나라도 다르면(venv·커널·동시 요청·sampling·셋 변경) 다시 잰다.
- 후보마다 기록: 평균 정답률, base 대비 차이의 95% CI와 99.29% CI, U·조용한 오답 비율, U 차이의 95% CI, 조용한 오답 차이의 95% CI, 오류 유형, 생성 상한·루프 수,
  실차 통행량 오독 수(“실차” 표현 문항 `old44/g02`·`old44/g04`와 `indepv2/n33`을 나눠서), vicinity 빠짐(v4 7절), 학습 기록(loss, step당 시간, peak 메모리, adapter sha256).
- **고르는 방법**:
  1. U 조건: base 대비 U 비율 차이의 문항 단위 쌍 bootstrap **95% CI 하한 ≤ 0**(U 증가가 확인되지 않음, 보정 없음). v4와 같은 계산(10,000회, `default_rng(20261109)`).
  2. U 조건을 만족한 후보 가운데 **평균 정답률(문항 평균 grounding_ok)이 가장 높은 것**.
  3. 동점이면 U 비율이 낮은 것, 그것도 같으면 학습 step(2절의 누적 step)이 적은 것.
  - U 조건을 만족한 후보가 없으면 고르지 않고 4절의 중단 규칙을 불통과로 본다.
- 같은 표본으로 고르고 검정하므로 생기는 낙관은 4절의 Bonferroni 보정으로 다룬다. 고르는 방법은 업체 100 결과를 쓰지 않는다.

## 4. 중단 규칙(결정 103)

고른 후보와 vLLM-base를 selection_v2에서 비교해 **둘 다** 만족할 때만 업체 100으로 간다.

1. **정답률 조건**: grounding_ok 차이(base → 고른 후보)의 문항 단위 쌍 bootstrap **99.29% CI**(양측, 신뢰수준 1 − 0.05/7 = 0.992857) **하한 > 0**.
   - 문항 i의 값은 k=4 표본 평균, 차이는 문항별 (후보 − base). 재추출 **20,000회**, `numpy.random.default_rng(20261109)`, 백분위 [0.05/14, 1 − 0.05/14] = [0.357%, 99.643%].
   - 문항 순서는 gold 순서(v4와 같은 순서).
2. **U 조건**: 같은 비교에서 U 비율 차이의 95% CI 하한 ≤ 0(보정 없음, 3절 1과 같은 계산).

하나라도 만족하지 않으면 업체 100을 평가하지 않고 보고한다. 95% CI(10,000회)도 함께 적지만 판정에는 99.29% CI만 쓴다.

## 5. 업체 100 판정(통과했을 때만)

- v4 5·6절을 **보정 없이** 그대로 쓴다. "vLLM-최종"을 "고른 후보"로 읽는다.
  - 주 비교: vLLM-base → vLLM-고른 후보, 업체 100, k=8, 동시 요청 8, 같은 정밀도·커널. 판정 규칙 v3 6절(95% CI, 10,000회, `default_rng(20261109)`).
  - 지연: 고정 30문항(`../serving_vllm_fp8/latency_ids.txt`) 순차, base 대비 1.5배 이하.
  - 참고 셀: E(Ollama 0.40.3, `qwen3:8b`, 연속 방식, k=8), 27b(Ollama `qwen3.8:27b`, k=4, 연속 방식, 실제 운영 greedy와 조건이 다름). 측정 전에 버전과 digest를 확인하고
    결정 55 guard를 켠다. Ollama 측정 중에는 Ollama GPU에서 다른 작업을 하지 않고 vLLM 서버를 내린다.
  - 함께 보고: aux_test_v1(base, 고른 후보, E; k=4). 보조 보고: valid98(base, 고른 후보; k=4). vicinity 빠짐은 모든 셋에서.
- 업체 100 vLLM 셀(base, 고른 후보)은 같은 서버 구성(같은 서버에 base와 고른 adapter)으로, 셀 단위로 GPU 3장에 나눌 수 있다. 셀마다 장치를 meta에 남긴다.
- pilot_004에서 만든 업체 100 단계 도구(`../pilot_004/run_vendor4.sh`, `vendor100/judge4.py`, `vllm_eval_thinking4.py`, `run_cell4v.py`, `valid98/valid98_gold.yaml`)를 쓰면,
  쓰기 전에 이 문서와 맞는지 확인하고, 고칠 것이 있으면 새 파일(pilot_005 아래)로 만든다.

## 6. GPU 사용(결정 105, 결정 100을 이어받음)

- GPU 3장(같은 RTX 6000 Ada). 학습 변형마다 GPU 1장. 번호가 아니라 UUID로 배정한다(Ollama GPU는 UUID `48f798cc…`).
- 쓰기 전마다 UUID, 상태, 다른 사용자 프로세스, 사용 중 메모리를 확인한다(`../pilot_003/gpu_lib.sh` `gpu_ok`). Ollama GPU에서 학습하거나 vLLM을 띄울 때는
  Ollama에 모델이 올라가 있지 않은지(`/api/ps`) 확인한다.
- 평가는 학습이 끝나 비는 GPU부터 쓴다. 한 vLLM 서버에 그때까지 끝난 adapter 여럿을 LoRA로 함께 올릴 수 있고(`--max-loras`는 올린 수), 필요한 adapter가 없으면
  서버를 내리고 새 목록으로 다시 띄운다. 한 서버에서는 한 번에 셀 하나(동시 요청 8)만 돈다. 학습 중인 GPU에서는 평가하지 않는다.
- 한 비교 안의 셀은 같은 backend(flashinfer), sampler(flashinfer), 동시 요청 수(8), 정밀도(BF16)다. 표본마다 GPU UUID를 셀 meta에 남긴다.

## 7. 예상 시간

pilot_004 실측: SFT 5.91초/step(934 step 1.54시간, peak 43.9 GB), DPO 18.1초/step(385 step), DPO 전체 2.46시간(그중 reference 미리 계산과 적재 약 0.5시간).
selection_v2 98문항 표본 하나 약 5.5–8분(GPU 1장, 동시 요청 8). 세 학습이 동시에 도는 동안의 속도 저하는 모른다(실측해 기록한다).

| 단계 | 내용 | 예상 |
|---|---|---|
| 학습 V1 | SFT 934 step | 약 1.6시간 |
| 학습 V2 | SFT 1,401 step | 약 2.4시간 |
| 학습 V3 | reference 미리 계산(385쌍) + DPO 193 step | 약 1.5시간 |
| 후보 평가 | 새 후보 6개 × k=4 = 셀 24개(SFT 934는 기록을 다시 씀), GPU가 비는 대로 | V2가 끝난 뒤 약 0.5시간, 시작부터 약 3시간 |
| 분석 | 선택과 중단 규칙(모델 호출 없음) | 수 분 |
| 업체 100(통과 때만) | v4 9절과 같음: vLLM 셀 GPU 3장에 약 1–1.5시간, Ollama 셀(E, 27b, aux E) 약 4.3시간, 지연 약 0.4시간 | 약 6시간 |

## 8. 산출물

v4 10절과 같다. 더해서: 변형별 학습 기록(`pilot_005/train_logs/<variant>_*`), 후보 7개 비교표(`pilot_005/selection.json`, 99.29% CI 포함), 서버 기록(adapter 목록 포함).
weights·adapter·checkpoint는 저장소 밖에 두고 경로와 sha256만 남긴다. 확정본의 sha256은 pilot_005 `PLAN.md`에 기록한다.
