# 업체 100 평가 절차 v3 (pilot_003) — **확정(2026-10-12, 사용자)**

작성: 2026-10-12(결정 70–73, 76–79). 상태: **확정(2026-10-12, 사용자)**. 초안(`fa7f600`)을 결정 76(R)·78(T)·79(U)에 맞게 고쳤다.

- 확정한 뒤에는 이 문서를 고치지 않는다. 바꿔야 하면 새 판을 만든다.
- `PROTOCOL.md`(v1), `PROTOCOL_v2.md`, `ADDENDUM_three_way.md`는 고치지 않는다.
- 근거 자료: `../calibration_001/REPORT.md`(sampling 잡음·검정력), `../operational_gap/ANALYSIS.md`(HF와 Ollama 차이의 원인, 조용한 오답),
  `../logprob_diag/REPORT.md`, `../quant_recipe/SAMPLING.md`, `../pilot_002_diag2/REPORT.md`.

## 1. 이어받는 것과 바뀌는 것

이어받는 문서(원문이 우선한다, 아래에서 바꾼 것만 다르다):

| 문서 | 결정 | sha256 |
|---|---|---|
| `PROTOCOL.md`(확정 2026-10-06) | 22 | `ca9cd3aa44ddca6c8fdaae0eb46bf810a865569e0e8248c6a69cfd714e92a818` |
| `ADDENDUM_three_way.md`(고정 2026-10-06) | 30 | `bae0c0cad6a7f9984153f283d7ba383103b86d67032126642b68718657008d47` |
| `PROTOCOL_v2.md`(확정 2026-10-08) | 44·46 | `f129bdd9dab64b61bd728078c78dc38ad9316da9f1c3c92c3b291f0940eae031` |

그대로 이어받는 것:

- 업체 100은 평가 전용이고, 셀마다 한 번만 잰다. 결과를 보고 checkpoint, 설정, prompt, 코드를 바꾸지 않는다(v1 1·5절).
- 기준일 2026-09-25, 조건 계층 켬, mock·legacy, 실행 명세 기록과 사전 확인(v1 4절).
- U(U1–U4)와 조용한 오답(v4 "오답" 중 U 아님)의 정의, 따로 판정하기(v1 6절).
- 보조 시험 셋은 판정에 쓰지 않고 함께 보고(v2 2.2절).

바뀌는 것(결정 72·73·76·78·79):

| 항목 | v2 | v3 |
|---|---|---|
| 운영 경로 | Ollama(공식 qwen3:8b와 등록 모델) | **HF transformers BF16**(base Qwen3-8B@b968826d, 학습 모델은 그 위 adapter)(결정 76) |
| 생성 | greedy 한 번 | **sampling k표본**(calibration_001 설정) |
| 지표 | grounding_ok 개수 | **문항별 평균 grounding_ok**(k표본 평균)의 문항 평균 |
| 검정 | McNemar(b·c) | **문항 단위 쌍 bootstrap 95% 신뢰구간** |
| U·조용한 오답 | 순증 ≥ 3이면 악화 | **비율 차이의 95% CI 하한 > 0**이면 악화 |
| 주 비교 | HF와 Ollama 따로 판정 | **HF-base → HF-최종 하나로만 판정**(결정 76) |
| E(공식 Ollama qwen3:8b) | 기준 셀 | **참고 셀**(보고만, 판정 안 함)(결정 76) |
| checkpoint 선택 | HF, selection_v1, greedy | **HF BF16, selection_v2, k = 4, 단계마다 2개**(결정 73·78) |
| 중단 규칙(결정 60) | 최고 checkpoint가 base보다 낮으면 멈춤 | **최고 checkpoint의 개선이 CI로 확인될 때만 진행**(결정 73, HF 경로 값) |
| 지연 기준 | E 대비 1.5배 | **같은 경로의 HF-base 대비 1.5배**(결정 76) |
| Ollama 측정 방식 | 문항마다 모델 내림(격리) | **연속**(모델을 내리지 않음)(결정 79) |
| greedy | 판정 | 기록만 |

## 2. 셋

| 셋 | 용도 | 경로 | 문항 | sha256 |
|---|---|---|---:|---|
| `selection_v2`(결정 65) | checkpoint 선택 | `sft_dpo_inventory/calibration_001/selection_v2_items.json`(문항 id sha256 `5b1d4d80…`) | 98 | `ee5c02a86d899444a97054a6d245b36b99746eee5945a84349ba429256e8ea76` |
| `aux_test_v1`(결정 42·46) | 함께 보고, 판정에 쓰지 않음 | `sft_dpo_inventory/pilot_prep_005/sets/aux_test_items.json` | 51 | `692b792fdfd1a95f9bd46c27262ed347d816076d15744070c1ca35ac25779aa0` |
| 업체 100 | 판정 | `evaluation/vendor100/gold.yaml` | 100 | `f99bc5fdef623e973901e5b339ede3c7f4e36cfa133887ea933e9683a7d8b4f0` |

- 채점은 결정 65(질문에 없는 aggregation 추가는 grounding_ok X)와 결정 71(valid98 h06·t02의 "총 몇 건"은 집계 아님)을 따른다.
- 세 셋 모두 평가 전용이다. 학습, trace 선택, annotation 후보에 쓰지 않는다. aux_test_v1과 업체 100은 checkpoint 선택에도 쓰지 않는다.

## 3. 생성 설정과 실행 조건

| 항목 | 운영 경로(HF, 판정) | 참고 셀 E(Ollama) |
|---|---|---|
| 모델 | Qwen/Qwen3-8B@`b968826d9c46dd6066d109eabc6255188de91218`, BF16, SDPA. 학습 모델은 PEFT adapter를 얹는다(병합하지 않음) | `qwen3:8b`(digest `500a1f067a9f`), 공식 TEMPLATE 그대로 |
| sampling | do_sample, temperature 0.6, top_p 0.95, top_k 20, min_p 0, repetition_penalty 1 | 같은 값, repeat_penalty 1, presence·frequency penalty 0(요청에 명시) |
| seed | 표본 k의 회차 seed `S_k = 20261100 + k`, 호출 seed `EV.call_seed(S_k, 문항 id, 호출 번호)`, 호출마다 `torch.manual_seed`·`cuda.manual_seed_all` | 같은 회차·호출 seed |
| thinking | `enable_thinking=True`, max_new_tokens 8192 | think 미지정(thinking 켬으로 동작) |
| 실행 | `thinking_prep_001/hf_eval_thinking.py`(calibration_001 `run_cal.sh hf`와 같은 인자) | `evaluate_vendor100.py llm --model-state keep_loaded`(연속, 시작할 때도 내리지 않음) |
| 측정 방식 | 프로세스 하나 | **연속**(결정 79). 방식은 meta(`pipeline.isolation`, `pipeline.start_unload`)에 남는다 |

- 공통: prompt `87048d0c…`, 기준일 2026-09-25, 조건 계층 켬, mock·legacy, 실행 의미 코드 지문 `791c4a68…`.
- **실행 조건**(각 셀 시작 전):
  - HF: GPU 3(결정 69, 예비 GPU 2). host `nvidia-smi`로 다른 사용자의 프로세스가 없는지, torch device UUID가 맞는지 확인한다. Ollama 모델이 그 GPU에 올라가 있지 않아야 한다.
  - E(Ollama): 결정 55 guard(precheck: 컨테이너가 기준 GPU를 봄, 버전, 다른 모델 없음, GPU에 다른 프로세스 없음; 측정 중: 첫 문항 100% GPU, 모든 호출 30 tok/s 이상).
    멈추면 `ABORTED_*`로 남기고 원인이 풀린 뒤 그 표본을 처음부터 잰다. Ollama 버전(지금 0.35.1)을 기록한다.
  - HF와 Ollama는 동시에 돌리지 않는다(`CLAUDE.md` 7번). 한 번에 셀 하나씩 재고, 측정 중 다른 모델 호출을 하지 않는다.
  - 지문·prompt sha·gold sha·adapter sha256(또는 모델 digest)을 실행 전에 계획과 대조하고, 결과 meta에 남긴다.
  - 셀 안에서 장치가 바뀌면 결정 68의 장치 일치 확인을 한다.
- **E의 기준값**: 격리 방식으로 잰 예전 E 기록(calibration_001 등)과 연속 방식 E를 직접 비교하지 않는다. E와의 비교가 필요하면 E를 연속 방식으로 새로 잰다(결정 79).
- **재측정.** 셀(표본)마다 한 번만 잰다. 예외는 v1 5절의 기반 장애와 결정 55 중단뿐이다.

## 4. 운영 경로(결정 76)

- 운영 경로는 HF transformers BF16이다. Ollama 양자화 경로(Q4·Q8)는 운영 대상이 아니다. 결정 74의 양자화 후보 규칙은 쓰지 않는다.
- 실제 배포의 서빙 엔진과 CLI 연결은 이 문서가 정하지 않는다(결정 76). 정해지면 그 경로와 HF BF16의 차이는 따로 잰다.
- 근거: `../operational_gap/ANALYSIS.md`. HF와 Ollama 학습 모델의 차이는 응답 처리(분리·파싱)가 아니라 모델 출력의 차이였고(확인됨), 같은 학습 효과가
  Ollama 경로에서는 나타나지 않았다(HF +4.50 [0.50, 8.75], Ollama Q8 −2.50 [−7.50, 2.50], selection_v1). 원인은 미확인이다.

## 5. 셀과 k

| 단계 | 셋 | 셀 | k |
|---|---|---|---|
| checkpoint 선택 | selection_v2 | HF-base(기준값), 단계(SFT, DPO)마다 checkpoint 2개 | 4 |
| 판정 | 업체 100 | **HF-base(기준), HF-최종(주 비교)**, E(참고) | **8** |
| 함께 보고 | aux_test_v1 | HF-base, HF-최종, E(참고) | **4**(결정 78) |

- **주 비교(판정): HF-base → HF-최종**(결정 76). 판정은 최종 모델 하나로 한다(결정 78).
- **참고 비교(판정 없이 보고)**: E → HF-base, E → HF-최종(현재 운영 모델과의 차이). E는 연속 방식이다.
- **업체 100에서 재지 않는 셀**(결정 78): 고른 SFT 모델(참고 셀), 추가 HF 참고 셀, Ollama 등록 모델(변환본·양자화본). 판정에 필요한 셀은 HF-base와 HF-최종뿐이다.
- 삼자 비교(ADDENDUM)는 E, HF-base, HF-최종으로 하고 판정에 쓰지 않는다. 변환 효과 대신 "현재 운영 모델(E) → 같은 base의 HF 경로", 학습 효과는 "HF-base → HF-최종"이다.

## 6. 판정 규칙(결정 72, 주 비교는 결정 76)

모든 비교는 같은 문항의 쌍이다. 문항 i의 셀 X 값은 k표본의 평균 `p_Xi`(grounding_ok), `u_Xi`(U), `s_Xi`(조용한 오답)이다.
차이 `d_i = p_Bi − p_Ai`의 문항 평균이 효과이고, 95% 신뢰구간은 문항 단위 bootstrap 10,000회의 2.5·97.5 percentile이다
(numpy `default_rng(20261109)`, calibration_001 `analyze_cal.py`와 같은 계산). A = HF-base, B = HF-최종.

- **개선**(모두 만족):
  1. grounding_ok 차이의 95% CI 하한 > 0.
  2. U 비율 차이의 95% CI 하한 ≤ 0(U 증가가 확인되지 않음).
  3. 조용한 오답 비율 차이의 95% CI 하한 ≤ 0.
  4. HF-최종의 지연 중앙값이 HF-base의 1.5배 이하.
- **악화**(하나라도 해당):
  1. grounding_ok 차이의 95% CI 상한 < 0.
  2. U 비율 차이의 95% CI 하한 > 0(U 증가가 확인됨).
  3. 조용한 오답 비율 차이의 95% CI 하한 > 0.
  4. HF-최종의 지연 중앙값이 HF-base의 1.5배를 넘음.
- **차이 없음**: 개선도 악화도 아님. "같다"가 아니라 "이 셋·k에서 구분되지 않는다"는 뜻이다.
- 판정은 주 비교 하나로만 한다. 다중 비교 보정은 하지 않는다(판정이 하나뿐이다). 다른 비교는 같은 지표로 판정 없이 보고한다.
- 함께 적는 것: 셀별 평균·표본별 값, 안정 정답 문항 수(k/k 정답, 보조 지표), 새로 생긴·사라진 U와 조용한 오답 문항 목록, 오류 유형 비율, greedy 기록이 있으면 그 값(기록만), 잡음 폭(같은 셀 두 k표본 평균 차이의 95% 폭).
- 참고(calibration_001, 문항 100): 최소 검출 차이(양측 0.05, 검정력 0.8)는 grounding_ok k=4 약 6.9%p, k=8 약 5.1%p, U k=8 약 3.2%p다.
- **family 분리 보고**(v1 7절, 결정 15): 업체 100 전체와 함께, 학습 데이터의 의미 family에 속한 문항과 속하지 않은 문항으로 나눠 같은 지표를 적는다. 판정은 전체로 한다.

### 확정 시 참고(`../operational_gap/ANALYSIS.md` 6절, 규칙은 바꾸지 않음)

- HF 경로의 조용한 오답 비율은 낮다(selection_v1에서 HF-base 1.50%, HF-최종 2.00%, 문항 5–7개). pilot_002의 HF-base → HF-최종 차이는 +0.50 [−0.75, 2.00]이었다.
  k=4·100문항에서 이 CI의 폭은 약 ±1.4%p라, 문항 몇 개의 변화로 하한이 0을 넘을 수 있다.
- HF 경로의 조용한 오답 대부분은 aggregation_spec 차이(결정 65의 질문에 없는 집계 추가)다. 조용한 오답 악화 판정은 주로 이 유형의 증감을 본다.

## 7. checkpoint 선택 절차와 중단 규칙(결정 73, HF 경로, 결정 60을 대신함)

1. 학습 단계(SFT, DPO)마다 checkpoint 2개(예: 단계 중간과 끝)를 미리 정해 둔다(학습 config에 적고 커밋).
2. HF-base를 selection_v2, k=4로 한 번 잰다. 이것이 선택 기준값이다.
3. 각 checkpoint(base + adapter, 병합하지 않음)를 같은 조건으로 잰다. Ollama 변환·등록은 하지 않는다(결정 78).
4. 문항 평균 grounding_ok가 가장 높은 checkpoint를 고른다. 같으면 U 비율이 낮은 것, 그다음 늦은 step.
   - 단계 사이의 관계(DPO의 시작 checkpoint 등)는 그 pilot의 학습 계획을 따른다. 이 문서는 정하지 않는다.
5. **중단 규칙**: 고른 최종 checkpoint의 (HF-base → checkpoint) grounding_ok 차이의 95% CI 하한이 0보다 클 때만 업체 100으로 간다.
   확인되지 않으면 업체 100 평가 전에 멈추고 보고한다.
   - 선택용 셋에서 같은 표본으로 고르고 판정하므로 최고값에는 선택 편향이 있다. 그래서 진행 조건만 CI로 보고, 크기는 업체 100에서 다시 잰다.
6. 고른 checkpoint, 선택표, adapter sha256을 커밋·push한 뒤 업체 100을 잰다.

## 8. 예상 평가 시간

calibration_001 실측(GPU 3 한 장, 순차, 100문항 표본 하나): HF-base 47–50분, HF + adapter 58–63분, Ollama E(격리 방식) 24분 + 표본 사이 내림 대기 5분.
연속 방식 E는 문항마다 내림·적재와 표본 사이 대기가 없어 표본 하나 약 24분 이하로 본다(아직 재지 않음).

| 셀 | 셋(문항) | k | 시간 |
|---|---|---|---|
| HF-base | selection_v2(98) | 4 | 약 3.2시간 |
| checkpoint 4개(HF + adapter) | selection_v2(98) | 4 | 약 16시간(셀당 약 4시간) |
| HF-base | 업체 100 | 8 | 약 6.5시간 |
| HF-최종 | 업체 100 | 8 | 약 8시간 |
| E(연속) | 업체 100 | 8 | 약 3.2시간 이하 |
| HF-base, HF-최종 | aux_test_v1(51) | 4 | 약 3.6시간 |
| E(연속) | aux_test_v1(51) | 4 | 약 0.8시간 이하 |

- 선택: 약 19시간. 업체 100 판정·참고: 약 18시간. aux: 약 4.4시간. 합계 약 41시간(GPU 하나, 순차).
- pilot_002의 지연 중앙값(selection_v1): HF-base 22.5 s, HF-최종 28.6 s(1.27배).

## 9. 확정 항목(결정 78로 정함)

1. 운영 경로: HF BF16(결정 76). 양자화 수준은 정하지 않는다(운영 대상 아님).
2. 등록 범위: checkpoint 선택은 HF BF16 경로에서 하므로 Ollama 등록은 필요 없다.
3. 업체 100에서 SFT 참고 셀과 추가 HF 참고 셀을 재지 않는다. 판정은 최종 모델 하나로 한다.
4. aux_test_v1은 k=4로 보고만 한다.
5. HF 참고 셀: 운영 경로가 HF이므로 따로 두지 않는다.
6. Ollama 진단 모델과 pilot 모델: `../ollama_cleanup_list.md`에 지울 목록으로 정리했다. 지우는 것은 사용자가 승인한 뒤에만 한다. 이 문서를 확정할 때 지운 것은 없다.

## 10. 산출물

`sft_dpo_inventory/<pilot 이름>/`:

- 선택: 셀별 결과(표본별 json·log, GPU 확인 기록), 선택표, 중단 규칙 판단.
- 판정: 업체 100·aux_test_v1 셀별 결과, 비교 표(평균 차이, CI, U·조용한 오답 CI와 문항 목록, 지연), 판정, family 분리, 삼자 비교. E는 guard·precheck 기록과 sampler 적용 값을 함께 남긴다.
- 원문(thinking 포함)은 ignore 경로, 기록은 커밋. weights·adapter·GGUF·cache는 커밋하지 않는다.
- 이 문서의 확정판 sha256.
