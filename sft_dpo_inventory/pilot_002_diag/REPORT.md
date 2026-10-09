# pilot_002 결과 진단 보고(결정 59–63, 2026-10-09)

## 범위

- 학습 없는 진단이다(결정 59). 개발 셋 selection_v1(100문항)과 valid98만 썼다. 업체 100과 aux_test_v1은 새로 재지도, 근거로 쓰지도 않았다.
- prompt `87048d0c`와 `SEMANTIC_CODE` 파일은 바꾸지 않았다. 지문 `791c4a68…`은 작업 내내 같았다.
- 다음 문서와 기록은 고치지 않았다:
  - PROTOCOL 문서, pilot_002 `PLAN.md`;
  - selection_v1·valid98의 gold와 구성;
  - 기존 기록과 보고서.
- Ollama 컨테이너는 옮기거나 재시작하지 않았다. 기존 모델은 지우거나 덮어쓰지 않았다. 새로 등록한 것은 결정 61의 진단용 모델 3개뿐이다.
- 모든 Ollama 셀은 한 번만 측정했다. 결정 55 확인은 모두 통과했고, 중단된 셀이나 다시 잰 셀은 없다.

| 작업 | 문서 | 커밋 |
|---|---|---|
| 0 결정 기록(59–63) | `DECISIONS.md` | 5684ddb |
| 1 GGUF 비교, E-1 실제 적용 파라미터 | `conversion_diag/GGUF_COMPARE.md` | 6e951b9, 8d87db0 |
| 2 진단 모델 등록·렌더링 확인 | `conversion_diag/GGUF_COMPARE.md` 5절, `registration/`, `render/` | 6e951b9 |
| 3 selection_v1 Ollama 셀 | `conversion_diag/SELECTION_CELLS.md`, `selection/` | 4642c5a … f0d8b49(셀마다), 이 커밋 |
| 4 계약 표기 실행 여부(E-2) | `conversion_diag/CANONICAL_BOTH.md` | 55310b1 |
| 5 실차 통행량(E-3) | `selection_decline/PASSAGE_STATUS.md` | 이 커밋 |
| 6 selection_v1 하락 | `selection_decline/ANALYSIS.md` | 4768e69 |

## 1. 결론

### 1.1 U 증가는 변환 경로에서 오는가, 학습에서 오는가

**개발 셋으로는 어느 쪽인지 가를 수 없다(미확인).** 학습과 무관한 조건만 바꿔도 같은 크기로 U가 흔들렸기 때문이다(확인됨).

- 원본 가중치:
  - 공식 qwen3:8b의 원본은 HF `Qwen/Qwen3-8B@b968826d`와 같다(확인됨).
  - 공식본과 직접 변환본(B-conv)의 차이는 attn_v 정밀도(F16/Q6_K), 같은 타입의 양자화 반올림, TEMPLATE뿐이다.
  - 실제 적용 파라미터와 harness 요청 옵션은 모든 모델에서 같다.
- selection_v1의 U(Ollama 셀, 한 번 측정):
  - base 계열: E 7, c 2, B-conv 7, d 4.
  - 학습 모델: Ollama-final 10, e 3.
  - 학습 쌍의 U 변화는 Q4_K_M(B-conv → Ollama-final)에서 7 → 10, Q8_0(d → e)에서 4 → 3이다. 방향이 서로 다르다.
  - 같은 학습 모델을 Q4_K_M에서 Q8_0으로만 바꿔도 10 → 3이다.
- 조건 하나만 다른 Ollama 쌍들은 grounding_ok 순 변화가 ±1이지만, 문항은 21–31개씩 뒤바뀌었다. 바꾼 조건은 TEMPLATE, 변환, 양자화다.
- 공식 가중치 위의 학습 효과는 측정하지 못했다. Ollama 0.35.1이 LoRA adapter 등록을 거부했다(`"LoRA adapters are no longer supported"`).
- 반복해서 나타난 U는 세 종류다.
  - 실차 통행량(n33은 Ollama 6셀 모두에서 U).
  - dimension_target 누락.
  - 출발·도착 역할(g11, c03c).
  - 결정 62의 관찰 2(Ollama에서만 dimension_target이 빠짐)와 같은 모양이다. selection_v1에서 dimension_target 누락은 HF-final 2, Ollama-final 5, e(Q8_0) 2다.

### 1.2 selection_v1 하락(HF: base 82 → 최종 80)

- **라벨 표기 차이는 주원인이 아니다(확인됨).** 잃은 9문항 중 표기 때문은 1문항이다.
- **장소·역할 오류가 늘었다(확인됨, base 1 → checkpoint 4–6).**
  - 통행량·rpm·속도에 `od_role both`를 붙여 NO_OPERATOR로 멈춘다.
  - 도착을 출발로 바꾼다.
  - region을 빼거나 나눈다.
  - 학습 데이터의 `od_role both`는 모두 trip_count 정답이다. 이것과 관련이 있을 가능성이 있다.
- thinking 길이, 생성 상한, 루프는 0–2문항만 설명한다(확인됨).
- valid98이 오른 이유는 대부분 설명된다(확인됨). base의 "질문에 없는 `aggregation: sum`"이 15에서 5로 줄었다. selection_v1의 HF base에는 이런 경우가 적었다(3–4).
- **Ollama 경로에서는 같은 학습이 selection_v1을 올렸다(69 → 75, 70 → 75, p ≥ 0.29).** 집계 추가가 줄어든 것과 같은 방향이다(10 → 7, 15 → 6).
- 결정 60의 중단 규칙(선택 셋 최고 checkpoint가 base보다 낮으면 멈춤)을 pilot_002 HF 기록에 대입했다(대입만 한 것).
  - 최고 checkpoint DPO 144가 80으로 base 82보다 낮다.
  - 이 규칙이 그때 있었다면 등록과 업체 100 평가 전에 멈췄을 것이다.

### 1.3 HF 경로와 Ollama 경로의 차이(이번에 새로 확인)

- **같은 원본, 같은 렌더링에서도 HF BF16 base 82와 Ollama Q8_0 base(d) 70이 달랐다(5 / 17, p 0.017, 확인됨).**
  - 잃은 17문항 중 9개는 Ollama 출력이 질문에 없는 aggregation을 붙인 경우다. 이것은 plan 응답 원문에 있다.
  - 집계 추가는 Ollama base 네 셀 모두 10–15개이고 HF base는 4개다. 원본, TEMPLATE, 양자화 수준과 무관하게 나타났다.
- 원인은 미확인이다. 후보는 BF16과 Q8_0의 수치 차이, torch와 llama.cpp의 차이, 실제 입력 토큰의 동일성이다.
  - 렌더링 확인은 주석 10문항의 토큰 수만 비교했다.
- 그래서 HF 경로에서 고른 checkpoint의 효과가 운영 경로(Ollama)에서 같은 방향으로 나타난다는 보장이 이 셋에서는 없다. selection_v1에서는 학습 효과 방향이 HF −2, Ollama +5·+6으로 반대였다.

### 1.4 계약 표기(한 장소 both)는 실행되는가

- **된다(확인됨).** 같은 조건 90칸에서 한 장소 both 표기와 옛 표기(장소 두 개)의 결과가 모두 같았다. 표기 때문에 멈춘 칸은 0이다.
- 093의 HF-최종이 멈춘 원인은 질문에 없는 `aggregation: min`(UNCONSUMED_CONDITION)이다.
- 표기와 무관하게 멈추는 조건은 둘이다.
  - dayofweek(합성 단계의 INVALID_PARAM_VALUE).
  - 장소 이상 단위의 dimension과 일부 h3. mock 도구 자료가 막는다.
  - 두 조건 모두 학습 정답이 0개다.

### 1.5 "실차 통행량" 오독은 개발 셋에도 있는가

- **있다(확인됨).** 학습하지 않은 base(HF-base, E, c, B-conv, d)가 selection_v1의 실차 3문항 중 2–3개를 trip_count로 읽는다. valid98 h30도 HF-base가 trip_count로 읽었다.
- 학습 후에도 1–3/3으로 줄지 않았다.
- 학습 데이터에는 passage_count + occupied 정답이 0개다. 반면 "실차"가 든 질문의 trip_count 정답은 SFT 50, DPO 28개다.
- 결론: **데이터 보강 근거 있음**(개발 셋에서 확인). 보강 효과는 추정하지 않았다.

## 2. 사람 검토가 필요한 항목

1. **U 판정 규칙의 해석.**
   - 한 번 측정에서 학습과 무관한 조건만으로 U가 2–10으로 움직였다.
   - PROTOCOL의 "U 순증 ≥ 3 → 악화"를 그대로 쓸지, 반복 측정이나 다른 기준을 넣을지 정해야 한다.
   - 이번 작업에서는 판단하지 않았다.
2. **운영 경로의 양자화 수준(Q4_K_M 대 Q8_0).**
   - 두 수준은 grounding_ok가 같거나 1 차이였다.
   - Q8_0은 지연 중앙값이 약 1.3배(11–12초 → 15초)이고 U는 더 적게 나왔다(4·3 대 7·10). 단, 1.1의 흔들림 안에 있다.
3. **HF와 Ollama 출력 차이의 원인 확인 여부와 방법.** 모델 호출이 필요하다.
4. 표기 차이와 `sum` 추가를 grounding_ok에서 X로 볼지. 대상 문항은 `selection_decline/ANALYSIS.md` 7절에 있다.
   - valid98 h06·t02의 gold가 sum을 생략한 표기인지도 함께 본다.
5. 계약 표기가 멈추는 두 조건(dayofweek, 장소 이상 단위의 dimension)이 의도한 지원 범위인지. 근거는 `conversion_diag/CANONICAL_BOTH.md` 5절에 있다.
6. 실차 통행량 데이터 보강을 할지, 하면 어떤 대조 쌍으로 할지.
   - 같은 질문 틀에서 trip_count(실차 건수)와 passage_count + occupied(실차 통행량)를 대조하는 방식이 한 예다.
7. Ollama 저장소에 남은 LoRA blob. (a)·(b) 등록 시도 때 올라갔고, 어떤 모델도 참조하지 않는다.
   - 파일은 `qwen3-8b-pilot002-final-dpo144-lora-f32.gguf`, 174,622,464 바이트다.
   - 지우지 않았다. 지울지는 사람이 정한다.
8. 진단 모델 3개((c), (d), (e), `geoflow-diag-…`)를 남길지.

## 3. 다음 판단에 필요한 최소 자료

| 자료 | 값 | 위치 |
|---|---|---|
| selection_v1 grounding_ok | HF-base 82, HF-final 80; E 71, c 70, B-conv 69, d 70, Ollama-final 75, e 75 | `conversion_diag/SELECTION_CELLS.md` 1절 |
| selection_v1 U(Ollama) | E 7, c 2, B-conv 7, d 4, Ollama-final 10, e 3 | 같은 곳 |
| 조건 하나만 바꾼 쌍의 문항 뒤바뀜 | 21–31문항(순 변화 ±1) | 같은 곳 2절 |
| HF ↔ Ollama(같은 원본) | 82 → 70, 5 / 17, p 0.017; 집계 추가 4 → 15 | 같은 곳 2·3절 |
| 학습 효과 방향 | HF −2(7 / 9), Ollama Q4_K_M +6(14 / 8), Q8_0 +5(13 / 8) | 같은 곳 2절 |
| 원본 가중치 | 공식 = HF b968826d. 차이는 attn_v 정밀도, 양자화 반올림, TEMPLATE | `conversion_diag/GGUF_COMPARE.md` |
| 실제 적용 파라미터 | 모두 같음(context 40960, temperature 0만 전송) | 같은 곳 4절 |
| 실차 통행량 | base 2–3/3 오독, 학습 후 1–3/3, 학습 정답 0 | `selection_decline/PASSAGE_STATUS.md` |
| 계약 표기 | 90칸 모두 옛 표기와 같은 결과 | `conversion_diag/CANONICAL_BOTH.md` |
| 하락 원인 | 장소·역할 오류 1 → 4–6, 표기 1/9 | `selection_decline/ANALYSIS.md` |

### pilot_003 선택지(효과는 추정하지 않음)

- **A. 측정 흔들림 먼저 재기.** 같은 Ollama 셀을 같은 조건으로 여러 번 재서 U와 grounding_ok의 반복 차이를 본다. 판정 규칙(1번 검토 항목)을 정하는 근거가 된다.
  - 이것은 "다시 실행"이 아니라 새 측정 설계이므로 사용자 승인이 필요하다.
- **B. 운영 경로의 양자화 수준을 Q8_0으로 바꾸어 평가하기.** 결정이 필요하다.
- **C. HF와 Ollama 차이의 원인 가르기.** 예를 들어 같은 GGUF를 Ollama 없이 llama.cpp로 돌리거나, HF에서 Q8_0과 같은 수준으로 양자화한다.
  - 모델 호출과 GPU 사용이 필요하다.
- **D. 데이터 보강.** 대상은 세 가지다.
  - passage_count + occupied.
  - `od_role both`를 trip_count 밖의 측정값에서 쓰지 않는 대조.
  - 질문에 집계가 없을 때 aggregation을 붙이지 않는 예.
  - 결정 60의 중단 규칙을 함께 적용한다.
- **E. 선택 셋 평가를 운영 경로(Ollama)에서도 하기.** HF에서만 고른 checkpoint의 방향이 Ollama와 달랐기 때문이다(1.3).
  - LoRA는 Ollama에서 등록할 수 없으므로, 병합한 뒤 변환하는 경로만 가능하다.
