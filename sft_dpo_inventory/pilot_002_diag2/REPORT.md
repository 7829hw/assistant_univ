# pilot_002 진단 2 — 운영 경로에서 학습 효과가 줄어드는 곳, 공식 방식 Q4(결정 70–75)

작성: 2026-10-12. 상태: 진단 기록. 효과 크기를 추정하거나 무엇을 정하지 않는다. 판단은 사용자가 한다.
학습·prompt·`SEMANTIC_CODE` 변경 없음, 지문 `791c4a68…`. Dev 셋만 썼다(업체 100·aux_test_v1 미사용).

근거 자료:

| 작업 | 자료 | 커밋 |
|---|---|---|
| 결정 70–75 기록 | `../DECISIONS.md` | `a18767a` |
| 1. 공식 방식 Q4 만들기 | `../quant_recipe/RECIPE.md`, `compare_types.json` | `3366145` |
| 2. 경로별 token 확률 | `../logprob_diag/REPORT.md`, `analysis.json` | `198e748` |
| 3. 진단 모델 등록·렌더링 | `../quant_recipe/registration/`, `render/` | `8355e17` |
| 3. sampling 셀 B-off·F-off | `../quant_recipe/runs/`, `SAMPLING.md`, `analysis.json` | `8eada51`, `d9ffdc2`, `5bd32d2` |
| 4. PROTOCOL_v3 초안 | `../vendor100_protocol/PROTOCOL_v3.md` | `fa7f600` |

## 1. 학습 효과가 운영 경로의 어느 단계에서 줄어드는가

학습 효과 = 같은 경로의 base → 최종(pilot_002 DPO step 144). sampling 값은 selection_v1, k=4, 문항 단위 쌍 bootstrap 95% CI(%p).

| 단계 | token 확률(teacher forcing, llama.cpp b11434) | sampling(selection_v1, k=4) |
|---|---|---|
| HF + adapter | 기준 | **+4.50 [0.50, 8.75]**(HF-base → HF-final) |
| HF 병합 BF16 | 학습 신호 상관 0.97(thinking)·1.00(JSON) | 재지 않음 |
| GGUF BF16 | 0.97·1.00, 기준과의 차이는 HF↔llama.cpp 구현 차이 크기 | 재지 않음 |
| GGUF Q8_0 | 0.94·1.00, 강한 token 기울기 0.98 | **−2.50 [−7.50, 2.50]**((d) → (e)) |
| 공식 방식 Q4 | 0.67·0.94, KL은 Q8의 약 20배 | **+0.75 [−4.00, 5.50]**(B-off → F-off) |
| 자체 Q4 | 0.53·0.92, KL은 Q8의 약 27배 | +2.00 [−3.00, 7.00](B-conv → Ollama-final) |

- **병합과 BF16 변환에서는 줄지 않는다 — 확인됨(token 확률 수준).**
- **Q4 양자화에서 token 단위 학습 신호가 잡음에 묻힌다 — 확인됨(token 확률 수준).** sampling 정답률로 이어지는지는 가능성 있음.
- **Q8_0에서도 sampling 학습 효과가 보이지 않는다 — 확인됨(이 셋·k에서 CI가 0 포함, 점 추정은 음수).**
  그러나 token 확률에서는 Q8_0이 학습 신호를 남긴다. 그러므로 **"token 확률은 남는데 Ollama sampling에서 효과가 사라지는" 구간이 있다. 원인은 미확인이다.** 후보:
  1. Ollama 0.35.1 실행 경로와 b11434의 차이(안의 llama.cpp 판, flash attention 끔).
  2. sampler 적용 순서(HF는 온도 → top-k·top-p, llama.cpp 기본은 top-k·top-p → 온도. Ollama의 순서는 확인하지 않음).
  3. 노출 편향: teacher forcing은 경로마다 자기 출력에서 쌓이는 차이를 보지 않는다. thinking이 7–8k token 문맥 뒤에 수백 token 이어진다.
  4. 우연: 각 CI 폭이 ±4.5–5%p다.
- 비대칭이 있다. base는 Ollama Q8에서 HF와 같은 수준이다(HF-base 74.00, (d) 75.50, HF-base→(d) +1.50 [−2.25, 5.50]). 최종만 떨어진다
  (HF-final 78.50, (e) 73.00, −5.50 [−10.25, −0.50]). 공식 방식 Q4에서도 같다(B-off 72.25는 HF-base −1.75, F-off 73.00은 HF-final −5.50).
- 어디서 잃는가(기록, 해석하지 않음, 400 문항·표본 중 개수):
  - `aggregation_added`의 감소(HF 11.5% → 5.0%)는 Ollama 경로에도 남는다((d) 11.5% → (e) 6.25%, F-off 4.75%).
  - 오류 유형 분류에 걸리지 않는 오답이 늘었다: HF-final 29 → (e) 52, F-off 49(HF-base 30, (d) 32, B-off 55).
    대부분 파이프라인 오류 응답("안전한 실패")과 조용한 오답이다. 오류 코드가 넓게 퍼져 있다(HF-final 42 → (e) 59, F-off 51; `UNCONSUMED_CONDITION`, `VALUELESS_CONCEPT`, `NO_MEASURE` 등).

## 2. 공식 방식 Q4는 Q8_0과 같은 수준인가(결정 74 후보 규칙)

- **규칙 결과: 최종·base 모두 "공식 방식 Q4".** 정답률 차이와 U 차이의 CI가 모두 0을 포함한다(selection_v1·v2 같음).

  | 쌍 | grounding_ok | U | 조용한 오답 |
  |---|---|---|---|
  | (e) Q8_0 → F-off(최종) | 0.00 [−4.50, 4.50] | +1.25 [−1.75, 4.25] | +0.75 [−1.50, 2.75] |
  | (d) Q8_0 → B-off(base) | −3.25 [−8.00, 1.50] | +2.00 [−0.50, 4.75] | 0.00 [−1.75, 1.75] |

- 규칙은 "나쁘다고 확인되지 않음"이다. 같음을 보인 것이 아니다. base는 점 추정 −3.25, U CI 아래 끝 −0.50으로 0에 가깝다.
- 자체 Q4보다 낫다: 최종 U −3.00 [−5.75, −0.25], 정답률 +3.00 [−2.00, 8.00]. base 정답률 +4.25 [−1.25, 9.50](selection_v2 +5.61 [0.51, 10.71]).
  token 확률에서도 공식 방식이 HF에 더 가깝다(KL 0.028 대 0.038).
- base 공식 방식 Q4(B-off)는 공식 blob(c)과 구분되지 않는다(−2.50 [−7.25, 2.25]). 텐서 타입 배치가 같다(399/399).
- 지연 중앙값: 공식 방식 Q4 11.6–12.1 s, Q8_0 15.2–15.3 s. 표본 하나 약 24분 대 약 31분.
- 최종의 HF 대비 차이: 자체 Q4 −8.50 → 공식 방식 −5.50(Q8과 같음). U 차이는 +4.75(CI > 0) → +1.75(CI 0 포함). HF와의 차이는 남는다.

## 3. PROTOCOL_v3 확정에 남은 항목(`../vendor100_protocol/PROTOCOL_v3.md` 9절)

1. **양자화 수준**(4절). 후보 규칙 결과는 "공식 방식 Q4"이고, 근거를 4절에 적었다.
2. **등록 범위**: 선택용 checkpoint(단계당 2개)와 같은 방식으로 변환한 base의 `ollama create` 승인(결정 20·61·75 범위 밖), 이름 규칙,
   선택 뒤 남길 모델과 지울 모델(지우기는 사용자 승인 뒤에만), 디스크(checkpoint마다 약 37–41 GB).
3. 고른 SFT 모델을 업체 100에서 참고 셀로 잴지.
4. aux_test_v1의 k(8 또는 4).
5. HF 참고 셀(최종, k=4)을 잴지.
6. 같은 방식으로 변환한 base를 업체 100에서 잴 때의 기록 위치와 이름.

함께 볼 점(정하지 않음):

- pilot_002를 PROTOCOL_v3의 중단 규칙(7절 6)에 넣어 보면, 운영 경로의 base 변환본 → 최종 차이 CI가 0을 포함한다(Q4 +0.75, Q8 −2.50, selection_v1).
  같은 학습이면 업체 100 전에 멈추는 형태다. selection_v1 결과이고 selection_v2·checkpoint 2개 절차로 잰 값이 아니다.
- 주 비교 형태(E → 최종)에서 조용한 오답 차이의 CI 아래 끝이 0보다 크다(F-off +2.50 [0.50, 4.75]). (e) +1.75 [−0.25, 4.25], 자체 Q4 +2.00 [0.00, 4.25]로 같은 방향이다.
  결정 72의 악화 규칙을 업체 100에 적용하면 해당하는 형태다.
- 최소 검출 차이는 k=4에서 약 6.9%p, k=8에서 약 5.1%p다(calibration_001). HF에서 본 학습 효과 +4.50은 그보다 작다.

## 4. pilot_003 준비 항목

1. **결정 66 "실차 통행량" 대조 묶음**: 실차 통행량(passage_count + taxi_status occupied), 공차 통행량(+ vacant), 상태 없는 통행량, 실차 건수(trip_count).
   학습 데이터에 이 유형의 정답이 0개이고 valid98 h30에서 같은 오류가 확인됐다. selection_v1과 업체 100은 근거로 쓰지 않는다(결정 36).
2. **업체 질문(`../vendor_questions_pending.md`, 결정 67)**: 실차 구간 건수의 dayofweek 묶기, 장소보다 같거나 넓은 단위로 묶기. 답이 오기 전에는 이 두 형태를 학습 정답으로 만들 수 없다.
3. **운영 경로 선택 준비**(PROTOCOL_v3 7절): 학습 config에 단계별 checkpoint 2개를 미리 적기, merge → BF16 GGUF → 양자화 → 등록 → 렌더링 확인 스크립트
   (`gguf_convert.sh`의 `QUANT_RECIPE=official`이 공식 방식 Q4를 만든다), 같은 방식으로 변환한 base의 선택 기준값 셀.
4. **1절의 미확인 구간**(token 확률은 남는데 Ollama sampling에서 효과가 사라짐)을 더 볼지. 모델 호출 없이 할 수 있는 것과 필요한 것:
   - 이미 있는 기록으로: Ollama 경로 최종에서 늘어난 파이프라인 오류 응답의 문항·호출 단위 비교(HF-final 대 (e)·F-off).
   - 모델 호출이 필요한 것: llama.cpp b11434 직접 sampling 셀(Ollama 아님), Ollama의 sampler 순서 확인. 둘 다 새 승인이 필요하다.
5. **남은 진단 모델 정리**: 결정 67로 (c)·(d)·(e)는 "sampling 보정 실험이 끝날 때까지" 남긴다. 결정 75의 두 진단 모델(B-off·F-off용)도 남아 있다.
   지울지와 그 시점은 사용자가 정한다(지우지 않았다).
6. **채점 기준**: 결정 65(질문에 없는 aggregation은 X)와 결정 71(h06·t02 "총 몇 건"은 집계 아님)을 pilot_003 학습 데이터 검사에도 적용할지.

## 5. 확인 상태 요약

| 항목 | 상태 |
|---|---|
| 병합·BF16 변환이 학습 신호를 남김 | 확인됨(token 확률) |
| Q8_0이 token 학습 신호를 남김 | 확인됨(token 확률) |
| Q4에서 token 학습 신호가 잡음에 묻힘 | 확인됨(token 확률) |
| Q4 잡음이 sampling 정답률 차이로 이어짐 | 가능성 있음 |
| 공식 방식 Q4가 자체 Q4보다 HF에 가까움 | 확인됨(token 확률), sampling은 U에서 확인·정답률은 CI 0 포함 |
| 공식 방식 Q4가 Q8_0보다 나쁘다고 확인되지 않음(결정 74 규칙) | 확인됨(selection_v1·v2, k=4) |
| Ollama Q8_0에서 최종 모델만 HF보다 떨어지는 원인 | 미확인 |
