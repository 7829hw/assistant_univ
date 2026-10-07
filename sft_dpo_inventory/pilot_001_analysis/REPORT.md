# pilot_001 원인 분석

- 범위: 결정 34–38(2026-10-07). 학습은 하지 않았다. 새 모델 호출은 2절의 E·B-conv 장치 확인 측정뿐이다.
- 따른 규칙: `CLAUDE.md`, `../DECISIONS.md`, `../vendor100_protocol/PROTOCOL.md`(확정판).
  - 확정된 PROTOCOL 판정(`../pilot_001/vendor100/judgment.json`)은 바꾸지 않았다.
  - 실행 의미 코드 지문은 작업 내내 `791c4a68…`이다.
- 결정 36: 업체 100 결과는 원인 설명에만 쓴다.
  - 3절 a·d의 업체 100 문항 분석은 설명용이다.
  - 다음 데이터 설계의 근거(3절 c, 4절)는 valid98과 학습 데이터에서만 찾았다.
- 결론마다 붙인 표시:
  - **확인됨**: 기록에서 직접 셌다.
  - **가능성 있음**: 기록과 맞지만 다른 설명을 배제하지 못했다.
  - **미확인**: 기록으로 가릴 수 없다. 확인에 필요한 최소 실험을 적었다(실행하지 않음).

## 0. 결정 기록

- 결정 34–38을 `DECISIONS.md`에 2026-10-07 날짜로 추가했다. 앞 번호와 겹치지 않아 번호는 바꾸지 않았다.
- `CLAUDE.md` 4·5·6번(GPU 규칙)을 결정 38대로 고쳤다.
  - Ollama는 GPU 2(`GPU-a644de12…`)에 둔다.
  - HF 작업·학습은 GPU 3(`GPU-48f798cc…`)이 기본이다.
  - GPU 2는 Ollama 모델이 없을 때만 HF 작업에 쓴다.
  - 쓰기 전에 host `nvidia-smi`로 UUID·메모리·다른 프로세스를 확인한다.
- 커밋: `354bd8b`.

## 1. 업체 100 정답률 문서

- `../VENDOR100_ACCURACY.md`(커밋 `ce5c91b`).
- 숫자는 `accuracy/collect.py`로 결과 파일에서 다시 셌다(`accuracy/accuracy.json`). 판정 쌍은 judgment.json을 그대로 옮겼다.

## 2. 장치 확인(결정 37)

- E와 B-conv를 GPU 2의 Ollama에서 업체 100으로 한 번씩 다시 쟀다. 결과 파일은 `device_check/`에 있고, 커밋은 `3ff2294`다.
- 조건은 PROTOCOL과 같다: 0.35.1, Q4_K_M, think·num_predict 미지정, 문항마다 내림, HF 측정 없음.
- 측정 직전 확인(`device_check/runs.log`): 버전 0.35.1, GPU 2 사용 2MiB, 다른 프로세스 0, 올라간 모델 0.

| 셀 | 첫 응답 바이트 일치 | 모든 호출 일치 | grounding_ok(GPU 3 → 2) | 분류 일치 | U | 조용한 오답 | 지연 중앙값(초) |
|---|---|---|---|---|---|---|---|
| E | 100/100 | 100/100 | 79 → 79 | 100/100 | 3 → 3 | 1 → 1 | 10.93 → 11.84 |
| B-conv | 100/100 | 100/100 | 77 → 77 | 100/100 | 6 → 6 | 0 → 0 | 10.39 → 11.66 |

- **확인됨:** 첫 응답이 모두 같다. 이번 비교에서 장치 차이는 정답률 차이의 원인이 아니었다.
  - 같은 장치 기준으로 판정·삼자 비교를 다시 계산할 필요가 없었다. 다시 계산해도 값이 같다.
  - PROTOCOL 판정은 그대로다.
- **확인됨:** 지연만 GPU 2가 8–12% 느렸다.
  - 같은 장치의 E에 대한 학습 모델 지연 비율은 최종 1.03, SFT 1.06이다(`comparison.json`; 판정 쌍에서는 1.12, 1.15).
  - 판정은 바꾸지 않는다.
- `VENDOR100_ACCURACY.md`에 "장치 확인" 절로 덧붙였다. 기존 표는 고치지 않았다.

## 3. 원인 분석

근거 스크립트는 `analyze.py`, 결과는 `analysis.json`이다. 기록된 출력만 읽었다.

### a. 악화 사유 문항(업체 100, 설명용)

대상은 판정에서 새로 생긴 U·조용한 오답 11문항이다.
- HF-최종 U 016·030·044·054
- Ollama-최종 조용한 오답 077·100, U 040
- HF-SFT 조용한 오답 077, U 037
- Ollama-SFT U 026·044·059·093, 조용한 오답 077·100

표에서 "멈춘 단계"가 "답함"이면 실행이 끝까지 가서 답을 냈다는 뜻이다.

| 문항 | 생긴 셀 | 같은 경로 base의 결과 | 학습 모델의 grounding 차이(정답 → 모델) | 오류 유형 | 멈춘 단계 | 다른 셀의 같은 오류 |
|---|---|---|---|---|---|---|
| 016 | HF-최종 | HF-E 정답 | `dimension_target` dropoff → 없음 | U2(집계 기준 위치 누락) | 답함 | 없음(나머지 6셀 정답) |
| 030 | HF-최종 | HF-E: 질문에 없는 `aggregation: sum`을 넣음(분류는 정상 답변) | `dimension_target` pickup → 없음 | U2 | 답함 | 없음. Ollama-최종은 UNCONSUMED_CONDITION으로 멈춤 |
| 044 | HF-최종, Ollama-SFT | HF-E·E 정답 | `dimension_target` pickup → 없음 | U2 | 답함 | 두 셀만 |
| 026 | Ollama-SFT | E 정답 | `dimension_target` pickup → 없음 | U2 | 답함 | 없음 |
| 040 | Ollama-최종 | E: `aggregation: sum`을 넣음(분류는 정상 답변) | `dimension_target` pickup → 없음 | U2 | 답함 | B-conv에도 같은 오류 |
| 054 | HF-최종 | HF-E 정답 | 측정값 통행량 → 승차 건수, 장소에 pickup 추가, `taxi_status` 누락 | U1·U2·U3 | 답함 | E와 Ollama-SFT에도 같은 오류 |
| 037 | HF-SFT | HF-E: MISSING_RELATION_QUALIFIER로 멈춤 | 054와 같은 유형 | U1·U2·U3 | 답함 | 다른 셀은 모두 멈춤 |
| 059 | Ollama-SFT | E: UNGROUNDED_SCOPE로 멈춤(planner) | 장소 "대구"를 버림 | U2(scope) | 답함 | Ollama-최종도 E처럼 멈춤 |
| 093 | Ollama-SFT | E: MISSING_RELATION_QUALIFIER로 멈춤(composition) | 장소 od_role pickup+dropoff → pickup만 | U2 | 답함 | B-conv에도 같은 오류 |
| 077 | HF-SFT, Ollama-SFT, Ollama-최종 | HF-E·E 정답 | 집계 sum → 없음 | 조용한 오답 | 답함 | 학습 모델 3셀(HF-최종은 정답) |
| 100 | Ollama-SFT, Ollama-최종 | E·B-conv: UNGROUNDED_SCOPE로 멈춤(planner) | 묶음 집계 max → min | 조용한 오답 | 답함 | Ollama 학습 모델 2셀만 |

결론:
- **확인됨:** 11문항 모두 학습 모델이 끝까지 실행해 답을 냈다(멈춤 없음).
  - 4문항(037, 059, 093, 100)은 같은 경로의 base가 멈추던(안전한 실패) 문항이다. 학습 모델은 여기서 답을 내며 틀렸다.
  - 나머지 7문항은 base가 grounding을 맞혔거나 정상 답변으로 분류된 문항이다.
- **확인됨:** 오류 유형은 넷이다.
  - `dimension_target` 누락: 5문항(016, 026, 030, 040, 044)
  - 통행량을 승차 건수로 읽음: 2문항(037, 054)
  - 장소 범위: 2문항(059, 093)
  - 집계 값: 2문항(077, 100)
- **가능성 있음:** 상당수는 학습이 만든 새 오류라기보다 문항 단위의 흔들림이다.
  - 054(E), 040·093(B-conv)은 학습 전 셀에도 같은 오류가 있다.
  - 학습 전에도 두 Ollama 셀(E와 B-conv)은 grounding_ok가 22문항에서 달랐다(d절).
  - 확인하려면 새 실험이 아니라 더 큰 평가 셋이 필요하다. 업체 100은 100문항이라 이 정도 흔들림을 가르지 못한다.
- **확인됨:** 학습이 `dimension_target` 누락을 체계적으로 늘렸다는 근거는 없다.
  - 업체 100에서 이 오류는 HF 1 → SFT 1·최종 3, Ollama E 0·B-conv 2 → SFT 2·최종 1이다.
  - valid98에서는 base 4 → SFT 4 → 최종 5다(c절, 정답에 `dimension_target`이 있는 문항 37개).

### b. thinking 길이

첫 계획 호출의 thinking 글자 수다.
- "상한"은 생성 상한(HF 8192 token)에 걸린 호출 수다(재질의 포함). Ollama는 상한이 없다(num_predict 미지정).
- 출처: `analysis.json` `b_thinking`.

| 셀 | 장치 | 중앙값 | p90 | 최대 | 2만 자 초과 | 상한 |
|---|---|---:|---:|---:|---:|---:|
| 업체100 HF-E | GPU 2 | 2,301 | 5,073 | 10,070 | 0 | 2 |
| 업체100 HF-SFT | GPU 2 | 2,518 | 6,110 | 32,634 | 1 | 6 |
| 업체100 HF-최종 | GPU 2 | 2,203 | 3,909 | 9,947 | 0 | 0 |
| 업체100 E | GPU 3 | 2,101 | 4,153 | 8,987 | 0 | – |
| 업체100 B-conv | GPU 3 | 2,127 | 4,807 | 29,136 | 1 | – |
| 업체100 Ollama-SFT | GPU 2 | 1,917 | 4,000 | 95,432 | 2 | –(시간 초과 1) |
| 업체100 Ollama-최종 | GPU 2 | 1,916 | 4,806 | 28,398 | 1 | – |
| valid98 base | GPU 2 | 2,732 | 5,346 | 34,856 | 2 | 4 |
| valid98 SFT 62 | GPU 2 | 2,495 | 6,439 | 35,900 | 4 | 6 |
| valid98 **SFT 124(선택)** | GPU 3 | 2,372 | 4,686 | 24,770 | 1 | 0 |
| valid98 SFT 186 | GPU 2 | 2,546 | 6,915 | 36,649 | 3 | 6 |
| valid98 SFT 248 | GPU 3 | 2,565 | 5,752 | 9,413 | 0 | 0 |
| valid98 DPO 53 | GPU 2 | 2,586 | 6,777 | 34,980 | 2 | 4 |
| valid98 DPO 106 | GPU 2 | 2,579 | 8,753 | 35,547 | 3 | 6 |
| valid98 DPO 159 | GPU 2 | 2,527 | 6,456 | 37,140 | 3 | 8 |
| valid98 **DPO 212(선택)** | GPU 2 | 2,730 | 7,823 | 35,443 | 4 | 8 |

학습 데이터의 thinking 길이도 같이 봤다(`c_training_profile.thinking_chars`).

| 데이터 | 중앙값 | p90 | 최대 |
|---|---:|---:|---:|
| SFT target | 2,955 | 4,772 | 16,941 |
| DPO chosen | 3,353 | 7,810 | 16,941 |
| DPO rejected | 3,165 | 6,908 | 9,438 |

- 학습 데이터에는 2만 자를 넘는 thinking도, 끝나지 않은 thinking도 없다.
- DPO 212쌍 중 99쌍은 rejected가 chosen보다 길다.

결론:
- **확인됨:** HF 기록에서 생성 상한에 걸린 호출 50개는 모두 반복 루프다(`b_truncated_all_calls`).
  - 50개는 업체 100 8개와 valid98 9개 run의 42개다.
  - 압축률이 0.024–0.086이다. 정상 종료한 thinking은 HF-E 업체 100에서 중앙값 0.44, 최대 0.54다.
  - 50개 중 46개는 끝부분에서 같은 덩어리가 3번 이상 그대로 반복된다.
  - 예: HF-SFT 032는 같은 줄이 36번, 2,746자 덩어리가 끝에서 8번 반복된다.
  - 루프는 base에도 있다: 업체 100 HF-E 2개, valid98 base 4개.
- **확인됨:** Ollama-SFT의 95,432자는 문항 082다.
  - 20,645 token, 222초를 생성하고 stop으로 끝났다. 그 뒤 NO_MEASURE로 실패했다.
  - 같은 문항의 thinking은 HF-SFT 9,092자, 다른 셀은 3,596–6,197자다.
  - Ollama-SFT에서는 024의 첫 계획 호출도 300초 시간 초과(ReadTimeout)로 실패했고, 재시도에서 정상으로 끝났다.
- **미확인:** 082와 024가 반복 루프인지.
  - Ollama 기록에는 thinking 원문이 없고 길이만 있다.
  - 최소 실험: Ollama-SFT로 082와 024를 thinking 원문을 저장하게 해 1회씩 호출한다. 설명용이다.
- **가능성 있음(가설):** SFT의 `json_only`는 thinking에 loss를 주지 않는다.
  - 그래서 thinking 길이나 끝맺음을 직접 바꾸는 학습 신호가 없다. 그래도 LoRA 가중치가 바뀌면 thinking 생성도 달라질 수 있다.
  - 업체 100에서는 SFT 쪽에서 긴 thinking이 늘었다:
    - HF-SFT p90 6,110, 상한 6
    - Ollama-SFT 2만 자 초과 2, 시간 초과 1
  - valid98의 SFT 124는 오히려 짧고 상한이 0이다. 장치가 달라(e절) 이 반례는 가려지지 않는다.
- **가능성 있음(가설):** DPO의 `full_response`는 thinking까지 학습한다.
  - 그러나 chosen이 rejected보다 짧지 않고, 학습 데이터에 루프 예시가 없다. 그래서 루프를 끊는 쪽의 신호는 거의 없다.
  - 관찰은 엇갈린다: HF-최종은 업체 100에서 상한 0·p90 3,909로 짧지만, valid98 DPO 212는 상한 8로 base 4보다 많다.
  - 최소 실험: valid98에서 상한에 걸린 문항만(base 2, SFT 62·186 합 6, DPO 212 4) base·SFT 124·DPO 212로 같은 GPU에서 다시 잰다. 루프가 학습과 함께 늘고 주는지 본다.

### c. 학습 쪽 진단(다음 데이터 설계의 근거로 쓸 수 있는 부분)

valid98 grounding_ok(`c_valid98_transitions`):
- base 55 → 고른 SFT 61 → 최종 65.
- base→최종: b 14 / c 4, McNemar p 0.031.
- base→SFT: 13 / 7, p 0.26.
- SFT→최종: 14 / 10, p 0.54.
- 주의: valid98은 checkpoint 8개 가운데 가장 높은 것을 고른 셋이다.
  - checkpoint 사이 값이 52–65로 흔들렸으므로 선택된 값은 낙관적이다.
  - 업체 100에서는 같은 크기의 이득이 보이지 않았다(HF 84 → 86, p 0.80).

valid98 오류 유형(틀린 문항 수; 한 문항이 여러 유형일 수 있음, `c_valid98_error_types`):

| 유형 | base | SFT | 최종 |
|---|---:|---:|---:|
| 질문에 없는 집계를 넣음(`aggregation_spec` 추가) | 20 | 16 | 13 |
| 집계 값이 다름 | 3 | 2 | 3 |
| 장소가 다름 | 10 | 9 | 3 |
| 장소 추가 | 1 | 1 | 0 |
| `dimension_target`(누락 / 다름 / 추가) | 4 / 1 / 2 | 4 / 0 / 1 | 5 / 2 / 2 |
| `dimension`(누락 / 다름 / 추가) | 0 / 6 / 2 | 1 / 3 / 1 | 1 / 6 / 1 |
| 측정값이 다름 | 2 | 3 | 1 |
| `limit`·`order`·`taxi_status` 누락 | 3 | 3 | 3 |
| 멈춤: 생성 상한(OUTPUT_TRUNCATED) | 2 | 0 | 4 |
| 멈춤: INVALID_PLACE | 0 | 1 | 2 |
| 멈춤: 그 밖(VALUELESS_CONCEPT, MULTIPLE_MEASURES, INVALID_CONCEPT, 확인 질문) | 3 | 3 | 1 |
| 틀린 문항 합계 | 43 | 37 | 33 |

학습 데이터와 valid98 정답의 유형별 규모(`c_training_profile`, `c_valid98_gold_features`):

| 특징 | SFT target 124개(34문항) | DPO에서 chosen·rejected가 갈리는 쌍(212쌍 중) | valid98 정답 98개 |
|---|---:|---:|---:|
| 집계(bucket·aggregation·rollup) 있음 | 99(80%) | 53 | 27(28%) |
| 집계 없음 | 25(20%) | – | 71(72%) |
| `dimension` | 25(20%) | 16 | 48(49%) |
| `dimension_target` | 11(9%) | 7–8 | 37(38%) |
| `limit`·`order` | 25 | 13 | 28 |
| 장소 2개 | 3 | 6 | 기록 없음(세지 않음) |
| 정지 target(지원 불가) | 7 | – | 5(확인 질문·지원 불가 기대) |

결론:
- **확인됨:** 줄어든 오류와 늘어난 오류.
  - 줄어든 것: "질문에 없는 집계를 넣음"(20 → 13), "장소가 다름"(10 → 3).
  - 늘어난 것: "생성 상한 멈춤"(2 → 4), INVALID_PLACE(0 → 2), `dimension_target` 합계(7 → 9).
- **확인됨:** 학습 데이터의 유형 분포가 valid98과 다르다.
  - SFT target의 80%가 집계 질문이지만, valid98 정답은 72%가 집계 없는 질문이다.
  - `dimension_target`은 학습 9% 대 valid98 38%, `dimension`은 20% 대 49%다.
- **가능성 있음:** 남은 주 오류(집계를 넣음 13, `dimension_target`·`dimension` 오류)는 이 분포 차이와 관련 있다.
  - 학습 데이터의 집계 질문이 모델에 "집계를 붙이는" 쪽을 보여 주는데도 이 오류가 줄었다. 그래서 단순한 관계는 아니다.
  - 최소 실험: 같은 설정으로 집계 없는 질문과 `dimension_target` 질문의 비중만 바꾼 데이터로 SFT를 한 번 돌려 valid98 유형별 수를 비교한다. 학습이 필요하므로 이번에는 하지 않았다.
- **확인됨:** 결정 23에서 본 습관 두 가지는 학습 후 늘지 않았다(`c_habits`, 첫 응답 JSON 기준).
  - 장소 role COND(정답은 SUBCOND):
    - valid98: base 20/109 → SFT 19/108 → 최종 16/97.
    - 업체 100 HF: 22/96 → 16/96 → 16/100.
    - 업체 100 Ollama: E 11/94, B-conv 17/99 → SFT 6/94 → 최종 1/95.
  - `answer: value`(정답에 없음):
    - valid98: 18 → 14 → 12.
    - 업체 100 HF: 4 → 4 → 4.
    - 업체 100 Ollama: 7, 8 → 4 → 7.
  - 학습 데이터에는 이 습관이 훨씬 많았다.
    - SFT target: 장소 COND 36/105, `answer: value` 68/124.
    - DPO chosen은 rejected보다 이 습관이 더 많다(COND 81 대 45, `answer: value` 65 대 42).
  - 두 필드는 채점이 보지 않으므로 grounding_ok에는 직접 영향이 없다.
- **미확인:** 세 번째 습관인 "지어낸 사실"이 늘었는지.
  - 자동으로 셀 수 없다.
  - 최소 실험: 결정 23과 같은 방식으로 valid98의 같은 문항 10개에서 base와 최종의 thinking을 사람이 검토한다.

### d. 경로 차이(HF와 Ollama, 설명용)

출처: `d_paths`. "첫 응답 JSON 같음"은 첫 계획 호출의 JSON이 같은 문항 수다.

| 비교 | grounding_ok | 차이 | grounding_ok가 갈린 문항 | 첫 응답 JSON 같음 |
|---|---|---:|---:|---:|
| 학습 전 HF-E vs E | 84 vs 79 | 5 | 17 | 26 |
| 학습 전 HF-E vs B-conv(같은 가중치) | 84 vs 77 | 7 | 17 | 21 |
| 학습 전 E vs B-conv(둘 다 Ollama) | 79 vs 77 | 2 | 22 | 23 |
| SFT HF vs Ollama(같은 가중치) | 82 vs 80 | 2 | 24 | 27 |
| 최종 HF vs Ollama(같은 가중치) | 86 vs 77 | 9 | 23 | 29 |

결론:
- **확인됨:** 같은 가중치라도 HF(BF16)와 Ollama(Q4_K_M)의 첫 응답은 71–79문항에서 다르다. 이것은 학습 전과 후가 비슷하다.
- **미확인:** 학습 모델에서 변환 경로의 영향이 커졌는지.
  - 같은 가중치 기준 차이는 최종에서 7 → 9로 커졌지만, SFT에서는 7 → 2로 줄었다.
  - 갈린 문항은 17 → 23–24로 늘었다. 그런데 학습 전 Ollama 두 셀끼리도 22문항이 갈렸다.
  - 업체 100에서 보인 차이는 이 흔들림 범위 안이다.
  - 최소 실험: 이미 등록된 B-conv와 Ollama-최종을 valid98로 한 번씩 잰다(약 30분씩). HF valid98 기록(base 55, 최종 65)과의 차이를 학습 전후로 비교한다. 업체 100은 쓰지 않는다.

### e. 장치

- **확인됨:** valid98 checkpoint 평가에서 생성 상한 호출이 0인 run은 GPU 3에서 잰 SFT 124·248 둘뿐이다(`e_valid98_devices`).
  - GPU 2에서 잰 7개 run(base 포함)은 4–8개였다.
  - 장치가 checkpoint와 겹쳐 있어(홀수 번째 SFT checkpoint는 GPU 2, 짝수 번째는 GPU 3), 장치 때문인지 checkpoint 때문인지 기록으로는 가를 수 없다.
- **확인됨:** HF 경로는 같은 장치에서 결정적이다. HF-E 1·2회차(둘 다 GPU 2)의 원출력 118개가 바이트 단위로 모두 같다.
- **미확인:** HF 경로가 GPU 2와 GPU 3에서 같은 출력을 내는지.
  - 이것이 다르면 SFT 124 선택(61, 상한 0)에도 장치가 섞였을 수 있다.
  - 최소 실험: SFT 124를 GPU 2에서 valid98로 한 번 다시 잰다(약 60–80분). 더 작게는, SFT 62·186이 GPU 2에서 상한에 걸린 6문항(t14, t19, t26, h15, h16, h19)만 SFT 124로 GPU 2에서 잰다.
- **확인됨(Ollama 경로):** GPU 2와 GPU 3에서 E·B-conv의 출력이 바이트 단위로 같았다(2절).
  - 그래서 업체 100 운영 셀의 장치 차이(기준 GPU 3, 학습 모델 GPU 2)는 결과 차이를 설명하지 않는다.
  - 다만 이것은 Ollama(llama.cpp) 경로의 결과다. HF 경로가 장치 사이에서 같은지는 위의 미확인 항목으로 남는다.

## 4. pilot_002 선택지(정하지 않음)

근거는 3절 c(valid98과 학습 데이터)다. 효과는 추정하지 않는다.

예상 시간은 pilot_001 실측 기준이다.
- SFT 26분, DPO 86분(reference 계산 포함).
- valid98 평가: checkpoint당 59–107분.
- 등록: 모델당 약 7분.
- 업체 100: HF 57–95분, Ollama 약 45분.

| 선택지 | 내용 | 필요한 자료 | 사람 검토량 | 예상 시간 | 업체 100을 다시 공정한 시험으로 쓸 수 있는가(결정 36) |
|---|---|---|---|---|---|
| A. teacher trace 17문항 포함 | 정답 표본이 없던 학습 질문 17개에 qwen3.8:27b trace(질문별 정답 4–8/8)를 넣는다. 질문 34 → 51 | 이미 수집됨(`training/generated/thinking_traces/teacher_qwen3.8_27b/`) | 결정 23 방식의 추론 표본 검토(10개 안팎). 27b thinking의 문체가 다르므로 표본을 따로 본다 | 데이터 반나절 + 학습·선택 약 8–12시간 + 업체 100 약 4시간 | 가능. 학습 질문만 늘고 업체 100 내용을 쓰지 않는다 |
| B. loss 범위 조정 | (1) SFT `full_response`(결정 3으로 복귀), (2) DPO `json_only`, (3) DPO 생략 중 하나 | (2)는 DPO 학습 코드 구현이 필요하다(현재 미지원, `SEMANTIC_CODE` 밖) | (1)은 결정 23 기준의 trace 타당성 판단이 다시 필요하다 | (2)는 구현·테스트 반나절 + 학습·평가 약 1일. (1)·(3)은 학습·평가 약 1일 | 가능 |
| C. 학습 쪽 유형 보강 | valid98과의 분포 차이(집계 없는 질문, `dimension`·`dimension_target`)를 줄이도록 새 학습 질문을 annotation한다. valid98 문항 자체는 쓰지 않는다 | 새 annotation 묶음(batch005)과 thinking trace 수집 | annotation 검토(결정 13과 같은 방식, 묶음당 수십 문항) | annotation·검토 1–2일 + trace 수집 수 시간 + 학습·평가 약 1일 | 형식상 가능. 다만 이번 분석에서 업체 100의 오류 유형(`dimension_target` 누락)을 이미 봤고 보강 유형과 겹친다. 완전히 독립된 시험이라고 하기 어렵다는 점을 기록해야 한다 |
| D. thinking 길이 제어 | (1) 학습 trace의 길이 상한, (2) 학습 질문에서 나온 루프 출력을 rejected로 둔 DPO 쌍. 평가의 생성 상한은 PROTOCOL 조건이라 바꾸지 않는다 | (2)는 학습 질문에서 루프 표본을 새로 모아야 한다 | 적음(루프는 자동 판별 가능, b절 지표) | 표본 수집 수 시간 + 학습·평가 약 1일 | 가능 |
| E. 파인튜닝 트랙 보류 | 운영 기본값 T2PC(qwen3.8:27b)를 유지하고 학습을 멈춘다. 등록한 모델은 분석용으로 남긴다(결정 34) | 없음 | 없음 | 없음 | 해당 없음(업체 100은 다음 사용 때까지 그대로) |

모든 선택지에 해당하는 사항:
- **valid98은 이번 분석에서 데이터 설계의 근거로 쓰였다.**
  - 다음 판에서 같은 셋으로 checkpoint를 고르면, 설계와 선택이 같은 셋에 기대게 된다.
  - 새 선택용 셋을 둘지, 이 점을 기록하고 그대로 쓸지 정해야 한다.
- 3절 d·e의 미확인 사항은 학습 없이 1–2시간으로 확인할 수 있다(HF 작업은 결정 38에 따라 GPU 3 기본):
  - valid98로 B-conv·Ollama-최종을 잰다.
  - GPU 2에서 SFT 124를 잰다.
  - 선택지 A–D의 결과를 읽기 전에 할지는 따로 정할 일이다.

## 5. 파일

| 파일 | 내용 |
|---|---|
| `analyze.py`, `analysis.json` | 3절 원인 분석 스크립트와 결과 |
| `accuracy/collect.py`, `accuracy/accuracy.json` | 1절 정답률 문서의 재집계 |
| `device_check/run.sh`, `runs.log` | 2절 측정 실행 명세와 순서·사전 확인 기록 |
| `device_check/E.*`, `device_check/B-conv.*` | 2절 GPU 2 측정 결과(json·jsonl·spec·log) |
| `device_check/compare.py`, `comparison.json` | 2절 GPU 3 기록과의 비교 |
