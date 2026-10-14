# pilot_003 후속 보고(aux E 셀, 원인 분석, vLLM 서빙 경로, pilot_004 준비)

작성: 2026-10-14. 결정 85–89(Z–AD). 학습하지 않았다. prompt·`SEMANTIC_CODE` 변경 없음, 지문 `791c4a68`(작업 끝에 다시 확인).
업체 100은 쓰지 않았다(2a의 U 종류 설명에만 기존 기록을 썼다, 결정 36). aux_test_v1은 작업 1의 E 셀 측정에만 썼다(그 셀의 생성 속도를 vLLM 지연 비교에 옮겼다).

결론 표시: **확인됨 / 가능성 있음 / 미확인**.

## 0. 결정 기록

- 결정 Z–AD → **85–89**(`../DECISIONS.md`, `ba7047b`). 결정 24에 "결정 86(AA)으로 바뀜(teacher 출처만)"을 표시했다.
- `CLAUDE.md` 15번: 실행 중인 스크립트 파일을 고치지 않는다(결정 88). 5번 예외에 결정 89(vLLM 확인의 GPU 사용)를 덧붙였다.

## 1. aux_test_v1 E 참고 셀(결정 87, 판정 없음)

- 조건: qwen3:8b digest `500a1f067a9f`, Ollama **0.40.3**(측정 전 확인), 연속 방식, Ollama GPU `48f798cc`, k=4(seed 20261101–04), PROTOCOL_v3 3절 sampling.
  sampler 적용 값이 요청과 같다(`aux_e/runs/aux_E_s*_sampler_params.txt`). 결정 55 guard 4표본 모두 통과(최소 78.7 tok/s, 기준 30). 다시 잰 표본 없음.
- 스크립트 `run_aux_e.sh`, 표 `aux_e_table.py` → `aux_e/comparison.json`(측정 `320d0e0`, 표 `f5b0a6d`).

| 셀 | 평균 | 표본별 | U | 조용한 오답 | 안정 정답 | 지연 중앙값 | 잡음 폭(s1–2 vs s3–4) |
|---|---:|---|---:|---:|---:|---:|---|
| HF-base(pilot_003) | 60.29 | 35 33 26 29 | 3.92 | 5.39 | 20 | 25.09 s | +12.75 [3.92, 21.57] |
| HF-최종(pilot_003) | 63.24 | 30 31 35 33 | 8.82 | 6.37 | 21 | 28.52 s | −6.86 [−16.67, 2.94] |
| **E(0.40.3)** | 54.90 | 31 28 26 27 | 8.82 | 9.80 | 15 | 8.70 s | +5.88 [−2.94, 15.69] |

| 참고 비교 | 차이 [CI] | U [CI] | 조용한 오답 [CI] | 지연 비 |
|---|---|---|---|---:|
| HF-base → HF-최종 | +2.94 [−2.94, 8.82] | +4.90 [1.47, 8.82] | +0.98 [−2.94, 4.90] | 1.14 |
| E → HF-base | +5.39 [−1.96, 13.24] | −4.90 [−9.31, −1.47] | −4.41 [−10.29, 1.47] | 2.88 |
| E → HF-최종 | +8.33 [0.00, 17.16] | 0.00 [−3.92, 3.92] | −3.43 [−8.33, 0.98] | 3.28 |

- E의 U 비율은 HF-최종과 같고 HF-base보다 높다. HF-최종에 새로 생긴 U 5문항 중 f02·f31·f33은 E에서도 U가 있다.
- aux는 51문항이라 같은 셀의 반쪽 표본 차이도 크다(HF-base +12.75 [3.92, 21.57]).

## 2. 기록으로 본 원인 분석(`ANALYSIS.md`, `analysis.json`, 모델 호출 없음)

### a. aux U 증가

- **확인됨:** 새 U 5문항(f02, f31, f33, f50, f53)은 모두 HF-최종 4표본 중 **1표본만** U다. 종류는 vicinity 빠짐 2(f33, f53), 장소 빠짐 1(f50),
  dimension_target 빠짐 1(f02), 실차 오독 1(f31). 고정된 오류로 바뀐 문항은 없다.
- **확인됨:** U 표본 수 HF-base → HF-최종: selection_v2 18 → 29(차이 CI 0 포함), aux 8 → 18, 업체 100 31 → 32. vicinity 빠짐은 세 셋 모두에 새로 나타났고(0→2, 2→6, 0→1),
  장소 범위 U와 U3:tool도 세 셋에서 늘었다.
- **가능성 있음:** aux만의 현상이 아니라 학습 모델이 장소·주변·dimension_target을 가끔 빠뜨리는 경향이 공통으로 생겼다. aux에서 CI가 0을 넘은 것은 해당 형태가 많은 문항 구성 때문일 수 있다.
- **미확인:** 학습 데이터와의 관계. vicinity 레코드는 pilot_002 84 → pilot_003 116(늘어난 32 중 teacher 28)으로 오히려 늘었다. f31의 "장소 od_role both + trip_count"는 batch006 형태와 같다(가능성 있음).

### b. 실차 통행량이 고쳐지지 않은 이유

- **확인됨:** HF-최종의 thinking은 여전히 "실차 → trip(trip_count)"으로 추론한다. selection_v2 g02·g04·n33 12표본에서 첫 계획에 taxi_status occupied를 넣은 경우 0,
  g02는 학습 뒤 4/4가 trip_count(학습 전 2/4). 지침의 "실차 통행량 = passage_count"를 언급한 뒤에도 trip_count를 고른 표본이 있다. valid98 h30도 trip_count.
- **확인됨:** occupied 변형 학습 신호는 SFT teacher 24레코드(6질문)뿐이고 손실은 JSON에만 걸렸다(`json_only`). HF trace 0, DPO 쌍 0(HF base가 8표본 중 한 번도 맞히지 못함).
- **가능성 있음:** "`json_only`에서 teacher 추론은 입력으로만 쓰여 8b 자신의 추론이 바뀌지 않았다." 기록과 맞지만, 양이 적은 것(SFT의 5.2%)과 평가 문장 형태 차이를 배제하지 못한다.

## 3. vLLM 서빙 경로(결정 89, `../serving_vllm/REPORT.md`)

- 설치: vLLM 0.30.0(2026-09-22 공개), `/home/hwkim/sftdpo_work/vllmvenv`, torch 2.13.0+cu130, 드라이버 595.99.02(CUDA 13.2) 호환.
  시스템 Python에 개발 헤더가 없어 uv 0.12.20으로 받은 standalone CPython 3.12.14로 venv를 만들었다. flashinfer sampler(JIT 빌드)를 끄고 PyTorch sampler를 썼다.
- **입력 일치 확인됨:** selection_v2 10문항 token id열이 HF와 같다(서버 자체 렌더링도 같다).
- **token 확률 확인됨:** vLLM ↔ HF 평균 |Δlog p| 0.012, top-1 불일치 0.7%(HF 병합본·GGUF BF16과 같은 크기). 학습 신호 보존율 1.00, 상관 0.98.
- **학습 효과가 vLLM에서도 유지됨(확인됨):** vLLM-base 72.19% → vLLM-최종 80.61%, +8.42 [3.06, 13.78]. HF는 +6.89 [1.28, 13.01]. 효과 차이 +1.53 [−5.61, 8.16](구분 안 됨).
- 정답률 경로 차이(HF → vLLM)는 base −3.06 [−7.40, 1.28], 최종 −1.53 [−6.63, 3.32]로 구분되지 않는다. 원문 일치는 0/392(커널이 다름).
- **지연은 E 수준에 못 미친다:** 단일 요청 생성 속도 vLLM 48–51 tok/s, HF 31–38, E 117(aux 셀). 문항 지연 중앙값 vLLM 16.5–17.2 s(HF 22.5–27.3 s, 같은 셋). E 8.7 s는 다른 셋 값이다.
- **seed 재현 안 됨(확인됨):** 같은 서버·같은 seed 두 번에도 원문이 달랐다. 장치 규칙에 따라 두 셀을 GPU 하나에서 쟀다. 원인은 미확인.

## 4. pilot_004 준비(학습 없음, `../pilot_004_prep/README.md`)

- **결정 86 구현:** `training/data/thinking.py`에 `loss_scope: by_source`(SFT 전용; teacher → full_response, HF → json_only), `assign_loss_scope`, `sft_loss_scope`.
  시험 `tests/test_thinking_loss_by_source.py` 9개 통과. teacher 레코드는 thinking과 JSON 모두에, HF 레코드는 `</think>` 뒤 JSON에만 손실이 걸리고, prompt는 추론 때 렌더링과 같다.
  pilot_003 SFT 460레코드에 적용(메모리 안) 460/460 통과(`loss_scope_check.json`). 손실 token의 82%가 teacher 레코드에서 나온다(227,454 / 276,417).
- **결정 88 도구:** `type_caps.py`(시험 `tests/test_type_caps.py` 5개 통과). pilot_003 데이터에 τ = 0.09로 적용한 수치(`type_caps.json`):

| 시나리오 | SFT 레코드(질문) | DPO 쌍 | TV 질문 / 레코드 / DPO | 실차 대조 SFT occupied |
|---|---|---:|---|---:|
| 상한 없음 | 460(131) | 348 | 0.117 / 0.124 / 0.140 | 24 |
| A. 레코드 상한 | 431(131) | 312 | 0.117 / 0.089 / 0.090 | 14 |
| B. 질문 → 레코드 상한 | 431(125) | 312 | 0.087 / 0.089 / 0.090 | 16 |

- 전체 시험 1,317개 통과(`python -m unittest discover -s tests`, 건너뜀 2, 예상된 실패 2는 기존). 지문 `791c4a68` 그대로(`training/`은 `SEMANTIC_CODE` 밖).

## 5. 다음 단계 선택지(효과는 추정하지 않고, 정하지 않는다)

1. **운영 경로를 vLLM으로 둘지**
   - vLLM BF16 + LoRA를 운영 경로로 둔다(학습 효과·token 확률이 HF와 같은 수준으로 확인됨, HF보다 빠름).
   - HF BF16을 운영 경로로 유지하고 vLLM은 평가 가속에만 쓴다(재현성: vLLM은 seed 바이트 재현이 안 됨).
   - 지연 목표를 정한 뒤 고른다: 같은 셋에서 E와 vLLM을 함께 재기, vLLM 배치 처리량 재기, 양자화(FP8 등) vLLM 경로를 따로 확인하기.
   - seed 재현성이 필요하면 prefix cache 끄기 등 설정을 바꾼 재현성 확인이 따로 필요하다(이번에는 바꾸지 않았다).
2. **실차 통행량 보강 방식**
   - 결정 86(teacher `full_response`)을 적용해 teacher 추론까지 학습한다.
   - occupied 변형 질문·표본 수를 늘린다(현재 6질문 24레코드).
   - teacher chosen × HF rejected 교차 DPO를 허용한다(결정 48·50·81은 지금 만들지 않음).
   - 평가의 묶음 없는 "실차 통행량" 형태(결정 81)를 학습 형태에 더한다.
3. **pilot_004 구성**
   - 유형 상한 시나리오 A(질문 TV 0.117 남음) 또는 B(세 TV 모두 ≤ 0.09, 질문 6개 빠짐).
   - 유형 상한과 실차 대조 레코드 유지의 우선순위(두 시나리오 모두 occupied 레코드가 24 → 14·16으로 준다).
   - 결정 86 적용 시 teacher 손실 token 비중(82%)을 그대로 둘지.
   - aux에서 보인 조건 빠짐(vicinity·장소·dimension_target) U를 다음 판 평가에서 어떻게 볼지.
