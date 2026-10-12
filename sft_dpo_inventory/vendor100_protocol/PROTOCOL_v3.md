# 업체 100 평가 절차 v3 (pilot_003) — **초안(사용자 확정 전)**

작성: 2026-10-12(결정 70–75). 상태: **초안**. 빈칸(☐)과 9절의 확정 항목을 사용자가 정한 뒤 확정판으로 만든다.

- 확정한 뒤에는 이 문서를 고치지 않는다. 바꿔야 하면 새 판을 만든다.
- `PROTOCOL.md`(v1), `PROTOCOL_v2.md`, `ADDENDUM_three_way.md`는 고치지 않는다.
- 근거 자료: `../calibration_001/REPORT.md`(sampling 잡음·검정력), `../logprob_diag/REPORT.md`(경로별 token 확률), `../quant_recipe/`(공식 방식 Q4), `../pilot_002_diag2/REPORT.md`.

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

바뀌는 것(결정 72·73):

| 항목 | v2 | v3 |
|---|---|---|
| 생성 | greedy(HF)·temperature 0(Ollama) 한 번 | **sampling k표본**(calibration_001 설정) |
| 지표 | grounding_ok 개수 | **문항별 평균 grounding_ok**(k표본 평균)의 문항 평균 |
| 검정 | McNemar(b·c) | **문항 단위 쌍 bootstrap 95% 신뢰구간** |
| U·조용한 오답 | 순증 ≥ 3이면 악화 | **비율 차이의 95% CI 하한 > 0**이면 악화 |
| 판정 경로 | HF(학습 효과)와 Ollama(운영) 따로 판정 | **운영 경로(Ollama) 주 비교 하나로만 판정** |
| 주 비교 | 최종 대 기준(HF-E / E) | **E 대 학습 모델(운영 경로)** |
| checkpoint 선택 | HF, selection_v1, greedy | **운영 경로, selection_v2, k = 4** |
| 중단 규칙(결정 60) | 최고 checkpoint가 base보다 낮으면 멈춤 | **최고 checkpoint의 개선이 CI로 확인될 때만 진행**(결정 73) |
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

| 항목 | 운영 경로(Ollama) | HF 참고 셀(선택) |
|---|---|---|
| sampling | temperature 0.6, top_p 0.95, top_k 20, min_p 0, repeat_penalty 1, presence·frequency penalty 0(요청에 명시) | do_sample, 같은 값, repetition_penalty 1 |
| seed | 표본 k의 회차 seed `S_k = 20261100 + k`, 호출 seed `EV.call_seed(S_k, 문항 id, 호출 번호)` | 같음 |
| thinking | think 미지정(thinking 켬으로 동작) | `enable_thinking=True`, max_new_tokens 8192 |
| 양자화 | **☐ 결정 74로 확정(4절)** | BF16 |
| TEMPLATE·PARAMETER | 등록 모델은 HF 형식 TEMPLATE(`e38a19eb`)·PARAMETER(`cff3f395`). E는 공식 그대로 | — |
| 격리 | 문항마다 모델 내림(E와 같음), 표본 사이 모델 내림 대기 | 프로세스 하나 |

- **실행 조건**(각 셀 시작 전):
  - 결정 31: Ollama 버전이 기준 셀과 같은지(지금 0.35.1) 확인한다. 다르면 같은 버전에서 기준 셀을 다시 잰다. 등록 모델은 렌더링 확인 10문항을 통과해야 잰다.
  - 결정 55: precheck(컨테이너가 기준 GPU를 봄, 버전, 올라간 모델 없음, GPU에 다른 프로세스 없음), 첫 문항 100% GPU, 모든 호출 30 tok/s 이상. 멈추면 `ABORTED_*`로 남기고 원인이 풀린 뒤 그 표본을 처음부터 잰다.
  - 기본 GPU는 GPU 3(결정 69). HF와 Ollama는 동시에 돌리지 않는다(`CLAUDE.md` 7번). 한 번에 셀 하나씩 잰다.
  - 지문·prompt sha·gold sha·모델 digest·adapter sha256을 실행 전에 계획과 대조하고, 결과 meta에 남긴다. sampler 실제 적용 값은 Ollama 서버 로그로 남긴다.
  - 셀 안에서 장치가 바뀌면 결정 68의 장치 일치 확인을 한다.
- **재측정.** 셀(표본)마다 한 번만 잰다. 예외는 v1 5절의 기반 장애와 결정 55 중단뿐이다.

## 4. 운영 경로의 양자화 수준(결정 74) — ☐ 사용자 확정

- **값: ☐** (공식 방식 Q4_K_M 또는 Q8_0)
- 후보 규칙(결정 74): 공식 방식 Q4가 Q8_0보다 정답률과 U 모두 나쁘다고 확인되지 않으면(두 95% CI가 모두 0을 포함하면) 공식 방식 Q4, 아니면 Q8_0.
- 근거(이 초안을 쓸 때의 결과, 판단은 사용자):
  - **후보 규칙의 결과: 최종·base 모두 "공식 방식 Q4"**(`../quant_recipe/SAMPLING.md`, selection_v1 k=4, 결정 75 진단 셀; selection_v2도 같음).
    - 최종: (e) Q8_0 → F-off 공식 방식 Q4 grounding_ok 0.00 [−4.50, 4.50], U +1.25 [−1.75, 4.25], 조용한 오답 +0.75 [−1.50, 2.75].
    - base: (d) Q8_0 → B-off grounding_ok −3.25 [−8.00, 1.50], U +2.00 [−0.50, 4.75].
    - 규칙은 "나쁘다고 확인되지 않음"이다. CI 폭이 ±4.5%p라 4%p 안팎의 차이는 가를 수 없다.
  - HF 대비(최종): 자체 Q4 −8.50 [−13.75, −3.50] → 공식 방식 Q4 −5.50 [−9.75, −1.25]. Q8_0(e)도 −5.50 [−10.25, −0.50]. U 차이는 자체 Q4만 CI > 0(+4.75).
  - token 확률(`../logprob_diag/REPORT.md`): Q8_0은 학습 신호를 남긴다(thinking 상관 0.94). Q4는 잡음에 묻힌다(자체 0.53, 공식 방식 0.67). KL은 Q8의 20–27배.
    그러나 sampling에서는 Q8_0(e)와 공식 방식 Q4(F-off)가 같은 수준이었다.
  - 지연 중앙값: 공식 방식 Q4 11.6 s, Q8_0 15.2 s(최종). 표본 하나 약 24분 대 약 31분.
  - 운영 경로의 학습 효과는 두 수준 모두 보이지 않았다(같은 방식 base 대비 Q4 +0.75 [−4.00, 5.50], Q8 −2.50 [−7.50, 2.50]; HF는 +4.50 [0.50, 8.75]).
- 공식 방식 Q4는 `../quant_recipe/RECIPE.md`의 방법이다(`gguf_convert.sh QUANT_RECIPE=official`, attn_v F16, 텐서 399개 타입이 공식 qwen3:8b와 같음).
- 같은 방식으로 변환한 base(5·6절의 보조 비교와 선택 기준값)도 같은 양자화 수준으로 만든다.

## 5. 셀과 k

| 단계 | 셋 | 셀 | k |
|---|---|---|---|
| checkpoint 선택 | selection_v2 | 같은 방식으로 변환한 base(기준값), 단계마다 checkpoint 2개(예: 중간·끝) | 4 |
| 판정 | 업체 100 | E(기준), 고른 최종 모델(주 비교), 같은 방식으로 변환한 base(보조 비교) | **8** |
| 함께 보고 | aux_test_v1 | 업체 100과 같은 셀 | ☐(9절) |
| HF 참고(선택) | 업체 100 | 최종 모델만, HF BF16 + adapter | 4 |

- **주 비교(판정): E → 고른 최종 모델**(운영 경로). 결정 72.
- **보조 비교(판정 없이 보고)**:
  - 같은 방식으로 변환한 base → 최종 모델(학습 효과의 운영 경로 값).
  - E → 같은 방식으로 변환한 base(변환 효과).
  - 고른 SFT 모델을 잴지는 9절의 확정 항목이다.
- **삼자 비교**(ADDENDUM과 같은 뜻, 판정에 쓰지 않음): E, 같은 방식으로 변환한 base, 최종 모델. 변환 효과(E → base 변환본)와 학습 효과(base 변환본 → 최종)로 나눈다.
- HF 경로는 업체 100에서 판정에 쓰지 않는다(결정 72). HF 참고 셀을 재면 판정 없이 운영 경로와의 차이로 보고한다.

## 6. 판정 규칙(결정 72)

모든 비교는 같은 문항의 쌍이다. 문항 i의 셀 X 값은 k표본의 평균 `p_Xi`(grounding_ok), `u_Xi`(U), `s_Xi`(조용한 오답)이다.
차이 `d_i = p_Bi − p_Ai`의 문항 평균이 효과이고, 95% 신뢰구간은 문항 단위 bootstrap 10,000회의 2.5·97.5 percentile이다
(numpy `default_rng(20261109)`, calibration_001 `analyze_cal.py`와 같은 계산).

- **개선**(모두 만족):
  1. 주 비교에서 grounding_ok 차이의 95% CI 하한 > 0.
  2. U 비율 차이의 95% CI 하한 ≤ 0(U 증가가 확인되지 않음).
  3. 조용한 오답 비율 차이의 95% CI 하한 ≤ 0.
  4. 지연 중앙값이 기준 셀의 1.5배 이하.
- **악화**(하나라도 해당):
  1. grounding_ok 차이의 95% CI 상한 < 0.
  2. U 비율 차이의 95% CI 하한 > 0(U 증가가 확인됨).
  3. 조용한 오답 비율 차이의 95% CI 하한 > 0.
  4. 지연 중앙값이 기준 셀의 1.5배를 넘음(v1 그대로).
- **차이 없음**: 개선도 악화도 아님. "같다"가 아니라 "이 셋·k에서 구분되지 않는다"는 뜻이다.
- 판정은 주 비교 하나로만 한다. 다중 비교 보정은 하지 않는다(판정이 하나뿐이다). 다른 비교는 같은 지표로 판정 없이 보고한다.
- 함께 적는 것: 셀별 평균·표본별 값, 안정 정답 문항 수(k/k 정답, 보조 지표), 새로 생긴·사라진 U와 조용한 오답 문항 목록, 오류 유형 비율, greedy 기록이 있으면 그 값(기록만), 잡음 폭(같은 셀 두 k표본 평균 차이의 95% 폭).
- 참고(calibration_001, 문항 100): 최소 검출 차이(양측 0.05, 검정력 0.8)는 grounding_ok k=4 약 6.9%p, k=8 약 5.1%p, U k=8 약 3.2%p다.
- **family 분리 보고**(v1 7절, 결정 15): 업체 100 전체와 함께, 학습 데이터의 의미 family에 속한 문항과 속하지 않은 문항으로 나눠 같은 지표를 적는다. 판정은 전체로 한다.

## 7. checkpoint 선택 절차와 중단 규칙(결정 73, 결정 60을 대신함)

1. 학습 단계(SFT, DPO)마다 checkpoint 2개(예: 단계 중간과 끝)를 미리 정해 둔다(학습 config에 적고 커밋).
2. 각 checkpoint를 운영 경로로 변환·등록한다(merge → llama.cpp b11434 BF16 GGUF → 4절의 양자화 → 새 이름 등록, base와 같은 TEMPLATE·PARAMETER) 그리고 렌더링 확인(결정 31)을 한다.
3. 같은 방식으로 변환한 base를 같은 조건으로 한 번 잰다(selection_v2, k=4). 이것이 선택 기준값이다.
4. 각 checkpoint를 selection_v2, k=4로 잰다.
5. 문항 평균 grounding_ok가 가장 높은 checkpoint를 고른다. 같으면 U 비율이 낮은 것, 그다음 늦은 step.
   - 단계 사이의 관계(DPO의 시작 checkpoint 등)는 그 pilot의 학습 계획을 따른다. 이 문서는 정하지 않는다.
6. **중단 규칙**: 고른 최종 checkpoint의 (같은 방식으로 변환한 base → checkpoint) grounding_ok 차이의 95% CI 하한이 0보다 클 때만 업체 100으로 간다.
   확인되지 않으면 업체 100 평가 전에 멈추고 보고한다.
   - 선택용 셋에서 같은 표본으로 고르고 판정하므로 최고값에는 선택 편향이 있다. 그래서 진행 조건만 CI로 보고, 크기는 업체 100에서 다시 잰다.
7. 고른 checkpoint, 선택표, adapter sha256, 등록 digest를 커밋·push한 뒤 업체 100을 잰다.

## 8. 예상 평가 시간

calibration_001과 quant_recipe 실측(100문항 표본 하나, GPU 3 한 장, 순차, Ollama는 표본 사이 내림 대기 약 5분 포함).

| 경로 | 표본 하나 | k=4 셀 | k=8 셀 |
|---|---|---|---|
| Ollama Q4_K_M(자체·공식) | 23–28분 | 약 1.9시간 | 약 3.8시간 |
| Ollama Q8_0 | 30–33분 | 약 2.4시간 | 약 4.8시간 |
| HF BF16 + adapter | 58–63분 | 약 4.0시간 | — |

- checkpoint 하나의 변환·등록·렌더링 확인: 약 7–10분(pilot_002 실측 5분 + 렌더링 확인 2분).
- **선택**(selection_v2, k=4): base 변환본 1 + checkpoint 4(단계 2 × 2) = 5셀 → Q4 약 9.5시간, Q8 약 12시간.
- **업체 100 판정**(k=8): E, 최종, base 변환본 3셀 → Q4 약 11.5시간, Q8 약 13–14시간(E는 공식 Q4라 Q4 시간).
- **aux_test_v1**(51문항): k=8이면 업체 100의 약 절반(Q4 약 6시간). k는 9절.
- **HF 참고 셀**(선택): 약 4시간.
- 합계(선택 + 판정, HF 참고와 aux 제외): Q4 약 21시간, Q8 약 25–26시간.

## 9. 확정 항목(사용자)

1. **운영 경로의 양자화 수준**(4절, 결정 74).
2. **등록 범위**: 운영 경로 선택에는 checkpoint마다 변환과 등록이 필요하다.
   - 선택용 checkpoint(단계당 2개)와 같은 방식으로 변환한 base의 `ollama create`를 승인할지(결정 20·61·75의 범위 밖).
   - 이름 규칙(예: `geoflow-<pilot>-<단계>-step<N>:<양자화>-hfthink`).
   - **선택 뒤 남길 모델과 지울 모델**: 고른 모델과 기준 모델은 남긴다. 고르지 않은 checkpoint 모델을 지울지, 언제 지울지.
     지우는 것은 사용자가 승인한 뒤에만 한다(`CLAUDE.md` 12번: 기존 모델을 덮어쓰거나 지우지 않음).
   - 디스크: checkpoint마다 병합본 16 GB + BF16 GGUF 16 GB + 양자화본 5–9 GB(+ Ollama blob 사본).
3. 고른 SFT 모델을 업체 100에서 참고 셀로 잴지(v1·v2는 SFT를 참고로 쟀다).
4. aux_test_v1의 k(8 또는 4).
5. HF 참고 셀을 잴지.
6. 같은 방식으로 변환한 base를 업체 100에서 처음 잴 때의 기록 위치와 이름.

## 10. 산출물

`sft_dpo_inventory/<pilot 이름>/`:

- 선택: 셀별 결과(표본별 json·jsonl·log, guard·precheck 기록, sampler 적용 값), 선택표, 중단 규칙 판단.
- 판정: 업체 100·aux_test_v1 셀별 결과, 비교 표(평균 차이, CI, U·조용한 오답 CI와 문항 목록, 지연), 판정, family 분리, 삼자 비교.
- 원문(thinking 포함)은 ignore 경로, 기록은 커밋. weights·adapter·GGUF·cache는 커밋하지 않는다.
- 이 문서의 확정판 sha256.
