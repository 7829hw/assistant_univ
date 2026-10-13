# R70 mechanism probe 결과

2026-10-13. 계획 `../PLAN.md` 5–7절(커밋 `b9ba5b7`). 숫자는 `analysis.json`(`../analyze_probe.py`).

## 1. 실행

| run | 시각(UTC) | 시간 | rc |
|---|---|---:|---|
| R70-json | 15:42–16:35 | 53분 | 0 |
| R70-full | 16:35–17:16 | 41분 | 0 |

- panel은 56문항. 조건은 Base·p0_sft_001과 같다(P0 `d7f4c12a`, greedy, thinking 켬, 8192).
- Base는 p0_sft_001 결과를 재사용했다.

## 2. 결과(panel 56문항)

| 지표 | Base | R70-json | R70-full |
|---|---:|---:|---:|
| `<think>` emission | 56/56 | **56/56** | **56/56** |
| 첫 token `{`(direct-JSON) | 0 | 0 | 0 |
| thinking 글자 중앙값 | 3,006 | 2,357 | 2,674 |
| 생성 token 중앙값 | 855 | 661 | 758 |
| 생성 상한(8192) 도달 호출 | 2 | 10 | 4 |
| semantic correctness(정답) | **38** | 28 | 34 |
| malformed JSON(첫 응답) | 2 | 5 | 2 |
| first-response structural error | 5 | 13 | 10 |

stratum별 정답:

| stratum | Base | R70-json | R70-full |
|---|---:|---:|---:|
| scope 역조회 6 | 5 | 1 | 3 |
| refusal 8 | 4 | 5 | 6 |
| od_ne_dt 10 | 6 | 4 | 4 |
| dimension_target 10 | 7 | 5 | 4 |
| bucket 10 | 10 | 8 | 10 |
| ordinary 12 | 6 | 5 | 7 |

## 3. gate(사전 등록 정의)

- R70-full emission 100%, R70-json emission 100%, 차이 0, R70-full thinking 중앙값 2,674.
- **판정: FAIL**(정의상 "R70-full − R70-json ≥ 50%p"를 만족하지 못함). 사전 등록대로 403문항 진단 평가는 하지 않는다.
- FAIL의 내용은 사전 등록이 예상한 "R70-full도 thinking이 거의 없음"이 아니다.
  - **대조군 R70-json이 thinking을 억제하지 않았다.**
  - 두 arm 모두 base처럼 thinking한다.

## 4. 원인 확인(보조 검증, 결과 뒤 추가, 모델 호출 없음: `../first_token_audit.py` → `../first_token_audit.json`)

학습 데이터에서 assistant 첫 위치(`<|im_start|>assistant\n` 바로 뒤) token이 손실을 받는지:

| 학습 | 레코드 | assistant 첫 위치 |
|---|---:|---|
| p0_sft_001 Gold-only(json_only) | 154 | **LOSS `{"` 154** |
| p0_sft_001 Clean-Hybrid(json_only) | 154 | **LOSS `{"` 84**, MASK 70 |
| p0_sft_002 R70-json(json_only) | 70 | MASK 70(손실 없음) |
| p0_sft_002 R70-full(full_response) | 70 | LOSS `<think>` 70 |

- p0_sft_001에서 thinking이 사라진 직접 원인은 json_only 자체가 아니다.
  - 원인은 **답만 있는 레코드가 assistant 첫 token으로 `{`를 학습시킨 것**이다.
  - Clean-Hybrid에서는 첫 위치에 손실이 걸린 레코드가 전부 `{`였다(84). reasoning 레코드 70은 그 위치가 MASK라 반대 신호를 주지 못했다.
- json_only라도 답만 있는 레코드가 없으면(R70-json), 첫 위치에 학습 압력이 없어 base의 thinking 행동이 남는다.
- full_response(R70-full)는 첫 위치에 `<think>`를 직접 학습시킨다.

## 5. semantic 관찰(56문항, 기술 통계)

- 두 arm 모두 Base(38)보다 낮다. R70-full 34, R70-json 28.
- R70-full은 R70-json보다 malformed(2 대 5), 생성 상한 도달(4 대 10), structural(10 대 13)이 적다.
- p0_sft_001에서 좋아졌던 dimension_target·od_ne_dt는 R70 두 arm에서 Base보다 낮다(4–5 대 6–7).
  - R70 데이터의 dimension_target 예제는 적다(Gap A 5, Gap B 11 포함 70).
