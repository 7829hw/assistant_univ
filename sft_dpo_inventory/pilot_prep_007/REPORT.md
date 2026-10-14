# pilot_004 준비 7: flashinfer, vLLM FP8, PROTOCOL_v4, 데이터 규모

작성: 2026-10-14. 결정 90–94(AE–AI). 학습하지 않았다. prompt·`SEMANTIC_CODE` 변경 없음, 지문 `791c4a68`(작업 끝에 확인).
업체 100과 aux_test_v1은 쓰지 않았다(selection_v2만). 결론 표시: **확인됨 / 가능성 있음 / 미확인**.

## 0. 결정 기록

결정 AE–AI → **90–94**(`../DECISIONS.md`, `a0531f0`).

## 1. flashinfer 적용(결정 90, `../serving_vllm_fp8/REPORT.md` 1–2절)

- **확인됨:** attention backend와 sampler 모두 flashinfer로 돈다(서버 로그 `AttentionBackendEnum.FLASHINFER`, "Using FlashInfer for top-p & top-k sampling").
- 빌드 실패 두 번과 조치(저장소 밖, venv 안):
  1. nvcc 13.4.92와 CUDA 런타임 헤더 13.0이 맞지 않음 → `nvidia-cuda-nvcc`·`crt`·`nvvm` 13.0.88(2025-09-04 공개) 설치.
  2. `libcudart.so`가 없어 링크 실패 → `/home/hwkim/sftdpo_work/cuda_link/libcudart.so`(→ `.so.13`)를 `LIBRARY_PATH`에.
- 요청 로그를 켰다(결정 93). 모든 셀에서 seed를 뺀 sampling 값이 한 종류였고 요청값과 같다. LoRA 이름도 셀과 맞다.
- **확인됨:** 입력 token 일치 10/10(BF16·FP8 서버 모두). HF와의 token 확률 차이는 이전 PyTorch sampler 경로와 같다(\|Δlog p\| 0.0125 대 0.0124, 학습 신호 보존율 1.00).
- 오프라인 채점 엔진이 한 번 채점을 끝낸 뒤 종료 단계에서 크래시했다(출력 완전, 그대로 씀). 서버 쪽에서는 일어나지 않았다.

## 2. vLLM FP8 확인(결정 91, `../serving_vllm_fp8/REPORT.md`)

- 구성: 온라인 FP8(`--quantization fp8`, per-tensor, CutlassFP8ScaledMM, Ada sm89) + pilot_003 최종 adapter를 LoRA로. **FP8 base에 LoRA가 붙었다**(병합 방식 쓰지 않음).
- token 확률: FP8의 HF와의 차이 \|Δlog p\| 0.041(BF16 0.012, llama.cpp Q8_0 0.017, Q4_K_M 0.096). 학습 신호 보존율 0.987, 기울기 0.924, 상관 0.899.
- sampling 셀(selection_v2, k=4, 동시 요청 8, flashinfer, GPU 0 한 장):

| 셀 | 평균 | U | 조용한 오답 |
|---|---:|---:|---:|
| vLLM-BF16-base | 75.00 | 4.08 | 2.04 |
| vLLM-BF16-최종 | 80.36 | 6.63 | 2.30 |
| vLLM-FP8-base | 73.21 | 3.32 | 3.32 |
| vLLM-FP8-최종 | 76.53 | 7.40 | 2.55 |

| 비교 | 차이 [CI] | U [CI] | 조용한 오답 [CI] |
|---|---|---|---|
| 정밀도(base) BF16 → FP8 | −1.79 [−6.89, 3.06] | −0.77 [−3.57, 1.79] | +1.28 [−0.77, 3.57] |
| 정밀도(최종) BF16 → FP8 | **−3.83 [−7.40, −0.51]** | +0.77 [−1.79, 3.06] | +0.26 [−1.02, 1.53] |
| 학습 효과 BF16 | **+5.36 [1.02, 9.69]** | **+2.55 [0.26, 5.36]** | +0.26 [−1.28, 1.79] |
| 학습 효과 FP8 | +3.32 [−1.53, 8.16] | **+4.08 [1.53, 6.89]** | −0.77 [−3.06, 1.28] |
| 학습 효과 차이 FP8 − BF16 | −2.04 [−7.65, 3.57] | +1.53 [−1.79, 4.85] | −1.02 [−3.57, 1.02] |
| 동시 요청·커널 영향(최종): 이전 순차 → 새 셀 | −0.26 [−3.32, 3.06] | +1.02 [−1.28, 3.57] | −0.26 [−1.79, 1.28] |

- 지연(고정 30문항 순차): 문항 모델 시간 중앙값 BF16-base 16.3 s, BF16-최종 21.2 s, FP8-base 11.7 s, FP8-최종 15.1 s, E 8.3 s.
  생성 속도 BF16 47.5–50.6, FP8 66.4–72.4, E 114.3 tok/s. FP8/BF16 문항 쌍 생성 속도 1.40–1.44배(CI 하한 > 1).
- 답:
  - **FP8에서 학습 효과가 유지되는가:** token 신호는 대체로 유지(확인됨). 정답률 학습 효과는 CI가 0을 포함해 **확인되지 않음**. BF16과의 효과 차이도 구분되지 않음.
  - **FP8은 얼마나 빠른가:** 생성 속도 약 1.4배, 문항 지연 약 0.71배(확인됨). E보다는 느리다(문항 지연 1.8배).
  - **FP8에서 U·조용한 오답이 늘었는가:** 정밀도 비교에서 증가가 확인되지 않음. 다만 FP8-최종 정답률이 BF16-최종보다 낮다(확인됨).
- 함께 본 것:
  - **확인됨:** 학습 모델의 U 증가(BF16 +2.55, FP8 +4.08, CI 하한 > 0, selection_v2).
  - **구분되지 않음:** 동시 요청(과 커널 변경)이 정답률 분포를 바꾸는지.
  - vicinity 빠짐(결정 94): selection_v2의 gold vicinity 문항이 1개라 네 셀 모두 0/4. 이 셋으로는 감시가 어렵다.

## 3. PROTOCOL_v4(`../vendor100_protocol/PROTOCOL_v4.md`, 확정 대기)

- 운영 경로 vLLM 0.30.0 + flashinfer(attention·sampler), LoRA로 adapter, token id 직접 전달, 요청 로그 요약을 셀 meta에.
- 정답률 셀은 동시 요청 8. 지연은 고정 30문항 순차로 따로 재고, 같은 경로·정밀도의 base 대비 1.5배 기준이다.
- seed 재현 불가를 받아들이고 통계로만 판단한다. 짝 비교 셀은 같은 GPU에서 잰다.
- 판정 지표·k·중단 규칙은 v3과 같다. 참고 셀 E는 Ollama 0.40.3 연속 방식이다. 감시 지표는 vicinity 빠짐이다.
- 예상 평가 시간은 BF16 약 7시간, FP8 약 6시간이다(GPU 1장).
- **정밀도 후보 규칙 적용 결과는 BF16**이다. 조건 2(FP8-최종 대 BF16-최종 차이 CI가 0 포함)를 만족하지 않았다. 정밀도는 사용자 확인을 기다린다.

## 4. pilot_004 데이터 규모(데이터는 만들지 않음, `../pilot_004_prep/data_scale.json`, `type_caps_exempt.json`)

- 결정 88 도구에 예외 옵션(`type_caps.py --exempt-contrast`, `capped(..., exempt)`)을 더했다. 시험 `tests/test_type_caps.py`에 3개를 더해 8개가 통과했고, 전체 1,320개가 통과했다.
- pilot_003 데이터에 결정 86(출처별 손실)과 결정 92(실차 대조 묶음은 상한 예외)를 적용한 수치:

| 항목 | 값 |
|---|---|
| SFT 레코드(질문) | **460(131)**. 상한으로 빠지는 레코드 0 |
| DPO 쌍(질문) | **348(53)**. 빠지는 쌍 0 |
| 손실 token(결정 86) | teacher 227,454(**82.3%**, full_response, 233레코드), HF 48,963(17.7%, json_only, 227레코드) |
| TV(개발 셋 대비) 질문 / 레코드 / DPO | **0.117 / 0.124 / 0.140**(0.09 초과, 결정 92대로 그대로 적음) |
| 예외를 뺀 나머지만의 TV | 0.016 / 0.080 / 0.087(모두 0.09 이하라 상한이 걸리지 않음) |
| 실차 대조 묶음 SFT 레코드 | occupied 24, vacant 16, 상태 없음(plain) 20, 실차 건수(trip) 21 |
| 실차 대조 묶음 DPO 쌍 | occupied 0, vacant 20, plain 16, trip 24 |

- **확인됨:** 예외를 두면 상한이 아무 레코드도 빼지 않는다. TV 초과는 모두 실차 대조 묶음(batch006 24질문)에서 온다. 나머지 부분은 pilot_002와 같은 분포다.
- A(레코드 상한)·B(질문 → 레코드 상한) 두 시나리오의 결과가 같다.

## 5. pilot_004 전에 남은 일

1. **정밀도 확인**: BF16 또는 FP8(규칙 적용 결과는 BF16). 확인되면 PROTOCOL_v4의 4절을 채우고 확정한다(sha256 기록).
2. **PROTOCOL_v4 확정**: 정밀도 외 항목(동시 요청 8, 지연 30문항 순차, vicinity 감시, E 0.40.3)을 함께 확인한다.
3. **데이터 구성**: 위 수치대로 pilot_004 데이터를 만든다(결정 86 `by_source` 표시 + 결정 92 예외 상한). occupied DPO 쌍 0은 그대로다.
   - 실차 보강 방식(교차 DPO, 표본 수 늘리기)은 정해지지 않았다.
   - 데이터 검사(dry-run, tokenizer, 손실 token, 평가 셋 겹침)를 다시 한다.
4. **학습 계획 고정**: 학습 config에 `thinking.loss_scope: by_source`를 넣고, 나머지 설정(pilot_003과 같은지), 저장 시점, 선택 절차(vLLM 경로)를 PLAN에 적고 커밋한 뒤 학습한다.
5. **checkpoint 선택 경로 준비**: checkpoint 여러 개를 LoRA로 한 서버에 올리는 설정(`--max-loras`), 선택 셀을 같은 GPU에서 재는 순서.
6. **감시 지표의 셋**: selection_v2는 vicinity 문항이 1개뿐이다. 감시를 어떤 셋으로 볼지 정한다(업체 100·aux_test_v1은 판정 단계에서 보고).
7. (참고) 학습 모델의 U 증가가 vLLM에서도 확인됐다. pilot_004 판정에서 U 조건을 넘을지 주시한다.

## 6. 산출물

- `../serving_vllm_fp8/`: 서버·셀·채점·지연 스크립트와 기록, `REPORT.md`.
- `../vendor100_protocol/PROTOCOL_v4.md`(확정 대기).
- `../pilot_004_prep/`: `type_caps.py`(예외 옵션), `type_caps_exempt.json`, `data_scale.py`, `data_scale.json`. 시험 `tests/test_type_caps.py`.
