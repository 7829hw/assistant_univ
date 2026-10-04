# 실차 구간과 운행 상태 조건 구분 (grounding_v10)

- 사전 등록과 실행 기록: `preregistration.md`.
- **결론: 후보 T1은 소규모 통과 기준 5(지원 불가 조건의 보존)를 충족하지 못해 탈락했다.**
  - 사전 등록대로 후보가 하나였으므로 전체 평가와 새 held-out을 실행하지 않았다.
  - 제품 기본 조합(qwen3:8b + prompt 522aa3b1)을 유지한다. 모델 교체는 이번에도 확정하지 않는다.
- 새 held-out(48, sha256 `cde49448…`)은 실행하지 않아 아직 아무 결과도 보지 않은 독립 셋으로 남는다.

## 1. 원인 확정

### 실행 계약
- `taxi_status`를 받는 Tool은 `get_passage_count`(통행량)뿐이다.
- `get_trip_count`·`get_trip_metrics`는 `taxi_status`와 `taxi_type`을 받지 않는다(`schemas/tims.yaml`).

### 모델이 받은 설명 (D prompt 8f3b19c2)
- trip 측정값 제목 "trip (승하차 기준 실차 구간)", "trip_count = 실차 구간 건수".
- 혼동 쌍의 **"통행량" 항목 안**: "'실차 통행량', '공차 택시 통행량'도 passage_count이며 실차·공차·대기영업은 taxi_status 조건입니다.
  '실차 구간 건수'만 AMOUNT/trip_count입니다."
- factor 의미 `taxi_status`: "운행 상태 조건." — 어느 측정값이 받는지 없다.
- trip이 정의상 실차라는 문장, taxi_status가 통행량에만 적용된다는 문장은 어디에도 없다.

### 원인 사슬 (qwen3.8:27b + D, `status_chain.py`)
grounding_v9 정지 24건(개발 15, OD 대조 8, v9 held-out 1)이 모두 같다.

| 단계 | 내용 |
|---|---|
| 최초 모델 출력 | 측정값 `AMOUNT/trip_count`(맞음) + `taxi_status=occupied` |
| 조건 계층 | 질문에 "실차 택시·실차 통행량" 같은 조건 표현이 없고 "실차" 단서만 있음 → 모델 값을 바꾸거나 더하지 않고 보존(`held`, `unparsed_status_cue`) |
| 합성 | trip 계산에 이 조건을 받을 변환이 없음 → `UNCONSUMED_CONDITION`(taxi_status), 부당한 거부 |

대표 사례:
- o02a "지난달 대구 수성구에서 출발한 실차를 하차 읍면동별로 셌을 때 가장 많은 두 곳은?" → `{dimension: emd, dimension_target: dropoff,
  order: top, limit: 2, taxi_status: occupied}` → held → `UNCONSUMED_CONDITION`.
- m10 "평일 18시~20시에 부산진구에서 대구 중구로 넘어간 실차 건수는?" → 같은 사슬.
- n26 "주말 부산 수영구를 공차로 달리던 택시들의 평균 속도는?"도 같은 사슬이지만 질문이 요구한 조건이므로 **정당한** 멈춤이다.

### 왜 적는가 (thinking 원문, `think_D.jsonl`)
- m10에서 모델은 통행량 항목의 두 문장("실차·공차·대기영업은 taxi_status 조건", "'실차 구간 건수'만 trip_count")을 인용한다.
  그리고 "trip 맥락에서 실차는 occupied(공차와 구별)"라고 판단해 trip에도 조건을 붙였다.
- 같은 모델이 c02a("출발한 실차의 도착 읍면동")에서는 "실차 = trip"으로 읽고 붙이지 않았다.
- **판단:** 지시끼리의 정면 충돌이 아니다. 범위가 적히지 않은 통행량 규칙을 trip으로 **확장**한 것이고, 그것을 막는 설명이 없다.
  "'실차 구간 건수'만"이라는 문구는 정확히 그 문구가 아닌 "실차"를 상태 단어로 읽을 여지를 만든다.
- "그 조건을 빼면 정답 grounding과 같다"(v9 `status_attribution.py`)는 원인 진단에만 썼고 성과로 세지 않았다.

### 설명으로 바뀌지 않는 경로
- 조건 계층은 상태 단어 뒤에 "택시·통행량"이 오면("실차 택시") 질문 표현으로 상태 값을 채운다.
- 기존 평가 셋의 trip 문항에는 이 형태가 없다(0건).
- 대조 s27("동대구역에서 실차 택시가 태운 손님은 몇 건")에서는 T1 모델이 조건을 적지 않았는데도 조건 계층이 `occupied`를 채워
  세 조합 모두 멈췄다. 이번 작업에서는 코드를 바꾸지 않았다.

## 2. 후보 T1 (설명만, D 위; `grounding-v10-status` `5d39b37`, prompt 24df8c84)

1. trip 측정값: 실차 구간은 손님을 태운 운행 한 번이고 그 자체가 실차다. 이 대상을 가리키는 "실차"는 taxi_status로 적지 않는다.
2. 통행량 항목: "통행량에서" 실차·공차·대기영업은 taxi_status 조건이다. "'실차 구간 건수'만"을 빼고 "'구간'이라는 말이 없어도 trip_count"로 바꿨다.
3. `taxi_status` 의미: 받는 측정값은 통행량뿐이다. 질문이 공차·대기영업 같은 상태를 요구하면 측정값과 관계없이 적는다.
   받지 않으면 지원 불가로 멈춘다.

코드 경로는 바꾸지 않았다. 계약과 설명의 일치는 `tests/test_status_contract.py`가 지킨다.

## 3. 소규모 결과 (운행 상태 대조 27 + OD 대조 16 + 원인 확인 16 = 59)

| | qwen3:8b + 522aa3b1 | qwen3.8:27b + D | qwen3.8:27b + D + T1 |
|---|---|---|---|
| 정상 / 정당 거부 / 조용한 오답 / 부당 거부 / 실패 | 42 / 5 / 4 / 1 / 7 | 24 / 6 / 0 / 28 / 1 | **51 / 6 / 0 / 2 / 0** |
| 답해야 할 문항의 taxi_status 정지 | 1(s27) | 27 | **1(s27)** |
| OD 대조 16 정상 | 11 | 8 | **16** |
| 원인 확인 개발 15 정상 | 13 | 0 | **15** |
| 대조 A(trip 대상) 7 정상 | 6 | 4 | 7 |
| 대조 B(통행량 상태) 5 정상 | 4 | 5 | 5 |
| 대조 C(지원 불가) 6: 정당 거부 / 조건을 버리고 답함 | 4 / 0 | 5 / 0 | 5 / 0 |
| 대조 D 4 / E 4 정상 | 4 / 4 | 4 / 3 | 4 / 4 |
| **지원 불가 7(C 6 + n26): 요구 조건이 grounding에 남음** | 5 | **7** | **2** |
| 지원 불가 멈춤 이유 | UNCONSUMED_CONDITION 5, 실패 2 | UNCONSUMED_CONDITION 6, NO_OPERATOR 1 | **UNSUPPORTED_QUESTION 5**, UNCONSUMED_CONDITION 1, NO_OPERATOR 1 |
| grounding 의미 정확(/59): 최초 / 조건 보존 뒤 / 재질의 뒤 | 16 / 26 / 37 | 22 / 27 / 27 | 41 / 46 / 47 |
| trip 실행 호출 장소 끝·묶는 끝 둘 다 | 33 | 13 | 40 |
| 재질의 호출 / 지연 중앙값 / 최대 | 21 / 14.5 / 178초 | 0 / 20.7 / 44초 | 1 / 21.7 / 32초 |

### 사전 등록 소규모 기준

| 기준 | 결과 | 판정 |
|---|---|---|
| 1. taxi_status 정지 ≤ 27b+D의 1/4 | 27 → 1 | 충족 |
| 2. 대조 C에서 조건을 버리고 답함 0 | 0 | 충족 |
| 3. B ≥ 5, E ≥ 3 | 5, 4 | 충족 |
| 4. OD 대조 ≥ 11 | 16 | 충족 |
| 5. n26 정당한 거부 + 요구된 vacant가 grounding에 남음 | 거부는 정당, grounding 없음 | **미충족** |

### 실패 원인
- T1에서 qwen3.8:27b는 s14·s16·s18·n26 등 5문항에서 grounding 대신 `{"unsupported": true}`만 냈다.
- thinking(`think_T1_n26.jsonl`)은 T1의 세 번째 문장 "이 조건을 받는 측정값은 통행량뿐이다 … 받지 않으면 지원 불가로 멈춘다"를
  인용해 "속도는 taxi_status를 받지 않으므로 unsupported"라고 스스로 판단한다.
- 즉 계약 사실을 모델에게 알려 주자 모델이 실행 가능성 판단을 떠맡았다.
  - 조용한 오답은 없다. 하지만 요구된 조건과 정확한 멈춤 이유("운행 상태 조건을 받는 변환이 없음")가 기록에서 사라지고,
    일반적인 "지원하는 분석 개념으로 표현할 수 없음"으로 바뀐다.
  - "의미는 LLM이 표현하고 실행 가능성은 코드가 판단한다"는 책임 분담에 어긋난다.
- 첫 두 문장(trip 대상 정의, 통행량 범위)이 정지 27 → 1과 OD 대조 16/16을 만든 것으로 보인다. 다만 세 문장을 나눠 재지 않았으므로
  각 문장의 기여는 확정하지 않는다.

### 그 밖의 관찰
- s13 "지난달 대구 수성구에서 출발한 공차 운행 건수": 두 27b 조합 모두 통행량 + 공차 + 출발 장소로 읽었다. 장소 역할 때문에
  `NO_OPERATOR`로 멈춰 조용한 오답은 아니지만 이유가 틀렸다(부당한 거부로 셈).
- qwen3:8b: 대조 C에서 조건을 버리고 답한 문항은 없지만 2문항이 형식 오류로 실패했다(s13 측정값 누락, s16 `time=weekend`).

## 4. 판정

| 항목 | 판정 | 근거 |
|---|---|---|
| T1 설명 정정 | **채택하지 않음** | 소규모 기준 5 미충족. 지원 불가 조건 보존 7 → 2 |
| 모델 교체(qwen3.8:27b) | **확정하지 않음, 현재 기본값 유지** | 교체 조건이던 T1 조합이 탈락. v9의 qwen3.8:27b + D는 OD 대조 기준 2 미충족 그대로 |
| 기본 설정 | qwen3:8b + prompt 522aa3b1(`geoflow/dev-v2`) | 바꾸지 않음. 재질의 예산·날짜 정책·위임 기준도 그대로 |

모델 간 차이는 이번 실행 조합(빌드 digest, Q4_K_M, temperature 0, think 미지정, Ollama 0.34.4, 이 prompt)의 효과로만 보고한다.

## 5. 남은 원인과 다음 가설 하나

> **T1의 처음 두 문장(trip 대상 정의, 통행량 범위)을 유지하고, 세 번째 문장을 "질문이 요구한 운행 상태는 측정값과 관계없이 적는다.
> 계산할 수 있는지는 프로그램이 판단하므로 이 이유로 unsupported를 내지 않는다"로 바꾸면, taxi_status 정지 해소(27 → 1)와
> OD 대조 16/16을 유지하면서 지원 불가 조건이 grounding에 남고 `UNCONSUMED_CONDITION`으로 멈춘다.**

- 검증 순서: 같은 소규모 기준(특히 5) → 전체 → 아직 쓰지 않은 v10 held-out.
- 별도 경로(이번 범위 밖, 보고만):
  - 조건 계층이 "실차 택시"로 trip 질문에 상태를 채우는 것(s27). 기존 평가 셋에는 0건이다.
  - "공차 운행 건수"를 통행량으로 읽는 것(s13).

## 6. 기록·재현

- 원인: `status_chain.py`, `think_D.jsonl`(D), `think_T1_n26.jsonl`(T1), `think_probe.py`
- 대조 셋: `status_contrast_questions.yaml`, 정답 실행기 `runs/gold_status_contrast.json`
- 실측: `runs/small/t1/`, `runs/status/q27_D/`, `runs/status/q8_cur/`. 그 밖의 기준 기록은 `grounding_v9/runs/full/`이다.
- 보고: `report.py`, `runs/small_report.json`

```
PY=<venv python>; R=evaluation/grounding_v10/run_set.sh
$R qwen3.8:27b t1 <grounding-v10-status worktree> small
$R qwen3.8:27b q27_D <grounding-v9-desc worktree> status
$R qwen3:8b q8_cur $PWD status
$PY evaluation/grounding_v10/report.py --scope small \
  --arm q27D evaluation/grounding_v9/runs/full/q27_D --extra q27D=status:evaluation/grounding_v10/runs/status/q27_D/status.json \
  --arm t1 evaluation/grounding_v10/runs/small/t1 \
  --arm q8 evaluation/grounding_v9/runs/full/q8_cur --extra q8=status:evaluation/grounding_v10/runs/status/q8_cur/status.json
```
